"""RabbitPublisher + Outbox wrapper: at-least-once, kaybolmayan teslimat.

Akis:
  poller -> ResilientPublisher.publish(payload, ...)
              |
              v
        RabbitPublisher.publish (gercek broker)
              |
              +-- basarili    -> done (broker confirm aldi)
              |
              +-- exception  -> Outbox.enqueue (SQLite, kalici)
                                ardindan return (no raise)
                                arka thread retry yapar

  Boylece poller ASLA mesaj kaybetmez; broker dusukse mesaj diskte birikir,
  broker geri gelince OutboxRetrier hizla bosaltir.

Disk-full / outbox-full circuit breaker:
  * Outbox dolarsa (Outbox.max_pending asilirsa) `OutboxFullError`
    raise edilir. Caller (poller) bu durumu yakalayip cycle'i durdurmali;
    health endpoint UNHEALTHY donmeli.
  * Cevirdigimiz davranis: ResilientPublisher OutboxFullError'i RAISE eder
    (eski "MESSAGE LOST" sessiz drop yerine). Poller yakalayip cycle'i kirar.

Mevcut `RabbitPublisher` API'sini birebir taklit eder; poller degisiklik
gerektirmez (ayni `publish(...)` imzasi).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from dnp3_gateway.messaging.outbox import Outbox, OutboxFullError
from dnp3_gateway.messaging.rabbit_publisher import RabbitPublisher

logger = logging.getLogger(__name__)


class ResilientPublisher:
    def __init__(self, *, broker: RabbitPublisher, outbox: Outbox) -> None:
        self._broker = broker
        self._outbox = outbox
        self._consecutive_failures = 0
        # Disk-full / outbox-full circuit breaker durumu (health endpoint
        # ve poller cycle bunu okur).
        self._lock = threading.Lock()
        self._outbox_full: bool = False
        self._outbox_full_since: float | None = None
        self._last_outbox_error: str | None = None

    @property
    def outbox_full(self) -> bool:
        with self._lock:
            return self._outbox_full

    @property
    def outbox_full_since(self) -> float | None:
        with self._lock:
            return self._outbox_full_since

    @property
    def last_outbox_error(self) -> str | None:
        with self._lock:
            return self._last_outbox_error

    def _set_outbox_full(self, error: str) -> None:
        with self._lock:
            if not self._outbox_full:
                self._outbox_full_since = time.time()
            self._outbox_full = True
            self._last_outbox_error = error[:500]

    def _clear_outbox_full(self) -> None:
        with self._lock:
            if self._outbox_full:
                logger.info("outbox_full_cleared — disk-full durumu sona erdi")
            self._outbox_full = False
            self._outbox_full_since = None
            self._last_outbox_error = None

    def publish(
        self,
        payload: dict[str, Any],
        *,
        message_id: str,
        correlation_id: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Mesaji broker'a publish etmeyi dener; basarisizsa outbox'a yazar.

        Outbox dolu ise (disk-full senaryosu) `OutboxFullError` raise eder —
        caller (poller) bu istisnayi yakalayip cycle'i durdurmali. Sessiz
        veri kaybi yok.
        """
        try:
            self._broker.publish(
                payload,
                message_id=message_id,
                correlation_id=correlation_id,
                headers=headers,
            )
            if self._consecutive_failures:
                logger.info(
                    "resilient_publisher_recovered after_failures=%s",
                    self._consecutive_failures,
                )
                self._consecutive_failures = 0
            # Basarili publish → outbox-full durumunu da temizle (broker normal'e
            # dondu, retrier outbox'i bosaltacak)
            if self._outbox_full:
                self._clear_outbox_full()
        except Exception as exc:  # noqa: BLE001
            self._consecutive_failures += 1
            try:
                self._outbox.enqueue(
                    message_id=message_id,
                    correlation_id=correlation_id,
                    headers=headers,
                    payload=payload,
                    last_error=str(exc),
                )
            except OutboxFullError as full_exc:
                # Outbox max_pending'e ulasti — disk-full circuit breaker.
                # Caller'in poll cycle'i durdurmasi gerek; veri kaybi olmasin.
                self._set_outbox_full(str(full_exc))
                logger.error(
                    "outbox_full_circuit_breaker message_id=%s pending=%d limit=%d "
                    "publish_error=%s — POLLER DURDURULMALI, RabbitMQ broker'a uzun "
                    "suredir baglanilamiyor olabilir",
                    message_id,
                    self._outbox.pending_count(),
                    self._outbox.max_pending,
                    exc,
                )
                # Cycle'in devam etmesini engellemek icin EXCEPTION YAY.
                # Eski davranis "sessiz drop" idi; bu artik bilincli olarak yok.
                raise full_exc
            except Exception as enq_exc:  # noqa: BLE001
                # Outbox SQLite write hatasi (disk IO, vb). Bu durumda da
                # circuit breaker'i tetikle ve raise et — sessiz drop yok.
                self._set_outbox_full(f"outbox_io_error: {enq_exc}")
                logger.error(
                    "outbox_enqueue_failed_after_publish_fail message_id=%s "
                    "publish_error=%s outbox_error=%s — POLLER DURDURULMALI",
                    message_id,
                    exc,
                    enq_exc,
                )
                raise enq_exc
            # Outbox enqueue basarili — sessiz fail edilmedi, retrier alir
            if self._consecutive_failures in (1, 5, 50, 500):
                logger.warning(
                    "publish_failed_outboxed message_id=%s error=%s consecutive=%s "
                    "(retrier arka planda yeniden deneyecek)",
                    message_id,
                    exc,
                    self._consecutive_failures,
                )

    def close(self) -> None:
        self._broker.close()

    # Outbox retrier publish_fn icin kullanilan kanca: row -> broker.publish()
    def publish_outbox_row(self, row: dict[str, Any]) -> None:
        self._broker.publish(
            row["payload"],
            message_id=row["message_id"],
            correlation_id=row.get("correlation_id"),
            headers=row.get("headers"),
        )
        # Outbox'tan basarili gonderim → broker calisiyor demek; circuit
        # breaker'i da temizle.
        if self._outbox_full:
            self._clear_outbox_full()
