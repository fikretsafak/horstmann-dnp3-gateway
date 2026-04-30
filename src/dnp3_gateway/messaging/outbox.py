"""SQLite tabanli persistent outbox: RabbitMQ'ya gonderilemeyen mesajlari kaybetmez.

Mimari:
  poller -> publish() try -> RabbitMQ
                          \-> fail/exception -> outbox.enqueue(mesaj) -> SQLite
  background OutboxRetrier thread -> outbox.dequeue_batch()
                                  -> publisher.publish()
                                  -> basarili: outbox.delete(id), basarisiz: retry_count++

Garantiler:
  - Process restart'a dayanikli: SQLite diskte; baslangicta queue okunur.
  - At-least-once delivery: ayni mesaj iki kere gidebilir; tag-engine idempotent
    (`message_id` bazli) tasarlanmistir, yan etki yok.
  - At-most-once kayip yok: publish exception olsa bile mesaj outbox'ta.

Goldman: ayri SQLite dosyasi her gateway icin (`GATEWAY_STATE_DIR/outbox_<CODE>.db`).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    correlation_id TEXT,
    headers TEXT,
    payload TEXT NOT NULL,
    enqueued_at REAL NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS ix_outbox_enqueued_at ON outbox(enqueued_at);
"""


class Outbox:
    """Thread-safe SQLite tabanli persistent kuyruk."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False: thread-safe lock disaridan saglaniyor.
        # WAL: yazma+okuma birlikte olabilsin (retrier vs enqueue).
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as c:
            c.executescript(_DDL)
            c.commit()

    def enqueue(
        self,
        *,
        message_id: str,
        correlation_id: str | None,
        headers: dict[str, Any] | None,
        payload: dict[str, Any],
        last_error: str | None = None,
    ) -> int:
        with self._lock, self._connect() as c:
            cur = c.execute(
                "INSERT INTO outbox (message_id, correlation_id, headers, payload, enqueued_at, last_error) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    message_id,
                    correlation_id,
                    json.dumps(headers, ensure_ascii=False) if headers else None,
                    json.dumps(payload, ensure_ascii=False),
                    time.time(),
                    last_error,
                ),
            )
            c.commit()
            return int(cur.lastrowid or 0)

    def fetch_batch(self, limit: int = 200) -> list[dict[str, Any]]:
        """En eski mesajlardan limit kadarini doner."""
        with self._lock, self._connect() as c:
            rows = c.execute(
                "SELECT id, message_id, correlation_id, headers, payload, retry_count "
                "FROM outbox ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "message_id": r[1],
                "correlation_id": r[2],
                "headers": json.loads(r[3]) if r[3] else None,
                "payload": json.loads(r[4]),
                "retry_count": r[5],
            }
            for r in rows
        ]

    def delete(self, row_id: int) -> None:
        with self._lock, self._connect() as c:
            c.execute("DELETE FROM outbox WHERE id = ?", (row_id,))
            c.commit()

    def mark_retry(self, row_id: int, error: str) -> None:
        with self._lock, self._connect() as c:
            c.execute(
                "UPDATE outbox SET retry_count = retry_count + 1, last_error = ? WHERE id = ?",
                (error[:500], row_id),
            )
            c.commit()

    def pending_count(self) -> int:
        with self._lock, self._connect() as c:
            (n,) = c.execute("SELECT COUNT(*) FROM outbox").fetchone()
            return int(n)


class OutboxRetrier:
    """Arka thread: outbox'taki mesajlari periyodik olarak yeniden gondermeye calisir.

    `publish_fn`: outbox kaydini alan ve broker'a gonderen callable. Basarili
    donerse mesaj outbox'tan silinir; raise ederse retry_count++ ve sonraki
    interval'da tekrar denenir. Exponential backoff yok (RabbitMQ'nun re-konek
    ettiginde hizla bosaltmak istiyoruz).
    """

    def __init__(
        self,
        outbox: Outbox,
        publish_fn: Callable[[dict[str, Any]], None],
        *,
        poll_interval_sec: float = 2.0,
        batch_size: int = 100,
    ) -> None:
        self._outbox = outbox
        self._publish_fn = publish_fn
        self._poll_interval = max(0.5, float(poll_interval_sec))
        self._batch_size = max(1, int(batch_size))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="outbox-retrier", daemon=True)
        self._thread.start()
        logger.info(
            "outbox_retrier_started db=%s interval_sec=%s batch=%s",
            self._outbox.db_path,
            self._poll_interval,
            self._batch_size,
        )

    def stop(self, timeout_sec: float = 3.0) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=timeout_sec)
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                rows = self._outbox.fetch_batch(self._batch_size)
            except Exception as exc:  # noqa: BLE001
                logger.warning("outbox_fetch_failed error=%s", exc)
                self._stop.wait(self._poll_interval)
                continue
            if not rows:
                self._stop.wait(self._poll_interval)
                continue
            sent = 0
            for row in rows:
                if self._stop.is_set():
                    break
                try:
                    self._publish_fn(row)
                except Exception as exc:  # noqa: BLE001
                    self._outbox.mark_retry(row["id"], str(exc))
                    # broker hala dusukse alttaki mesajlar da fail eder; donguyu kir
                    logger.debug(
                        "outbox_retry_failed id=%s retry=%s error=%s",
                        row["id"],
                        row["retry_count"] + 1,
                        exc,
                    )
                    break
                self._outbox.delete(row["id"])
                sent += 1
            if sent:
                logger.info("outbox_drained sent=%s remaining_in_batch=%s", sent, len(rows) - sent)
            self._stop.wait(self._poll_interval)
