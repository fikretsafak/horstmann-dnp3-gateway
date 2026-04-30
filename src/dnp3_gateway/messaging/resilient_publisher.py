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

Mevcut `RabbitPublisher` API'sini birebir taklit eder; poller degisiklik
gerektirmez (ayni `publish(...)` imzasi).
"""

from __future__ import annotations

import logging
from typing import Any

from dnp3_gateway.messaging.outbox import Outbox
from dnp3_gateway.messaging.rabbit_publisher import RabbitPublisher

logger = logging.getLogger(__name__)


class ResilientPublisher:
    def __init__(self, *, broker: RabbitPublisher, outbox: Outbox) -> None:
        self._broker = broker
        self._outbox = outbox
        self._consecutive_failures = 0

    def publish(
        self,
        payload: dict[str, Any],
        *,
        message_id: str,
        correlation_id: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
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
            except Exception as enq_exc:  # noqa: BLE001
                # Outbox da fail (disk dolu vb): SADECE bu durumda kayip riski var.
                # Yine de raise etmeyelim, gateway loop devam etsin.
                logger.error(
                    "outbox_enqueue_failed_after_publish_fail message_id=%s "
                    "publish_error=%s outbox_error=%s — MESSAGE LOST",
                    message_id,
                    exc,
                    enq_exc,
                )
                return
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
