"""Publisher-confirm destekli, thread-safe, yeniden-baglanan RabbitMQ yayinci.

Gateway tek baglanti + tek channel uzerinden mesaj yayinlar. Baglanti dustugunde
bir sonraki `publish()` cagrisinda otomatik yeniden kurulur. Ayni publisher birden
fazla thread'den cagrilirsa dahili lock ile korunur.

Exchange `hsl.events` (topic, durable) olarak declare edilir; tag-engine ayni
exchange'de binding yapar. Mesajlar `delivery_mode=2` (persistent) + publisher
confirms modunda gonderilir, bu sayede RabbitMQ broker mesaji disk'e yazmadan
publish cagrisi geri donmez.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

import pika
from pika.exceptions import AMQPError

logger = logging.getLogger(__name__)


class RabbitPublisher:
    def __init__(self, *, url: str, exchange: str, routing_key: str) -> None:
        self.url = url
        self.exchange = exchange
        self.routing_key = routing_key
        self._connection: pika.BlockingConnection | None = None
        self._channel: Any = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ API ---
    def publish(
        self,
        payload: dict[str, Any],
        *,
        message_id: str,
        correlation_id: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Tek bir telemetri event'ini exchange'e yayinlar.

        Hata durumunda baglanti sifirlanir ve exception re-raise edilir.
        Ust katmanda (`main._poll_cycle`) try/except ile loglanir.
        """
        with self._lock:
            try:
                channel = self._ensure_channel()
                channel.basic_publish(
                    exchange=self.exchange,
                    routing_key=self.routing_key,
                    body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=2,
                        message_id=message_id,
                        correlation_id=correlation_id or message_id,
                        headers=headers or None,
                    ),
                )
            except (AMQPError, OSError):
                self._force_close()
                raise

    def close(self) -> None:
        with self._lock:
            self._force_close()

    # ---------------------------------------------------------- internal ---
    def _ensure_channel(self) -> Any:
        if self._connection is None or self._connection.is_closed:
            self._connection = pika.BlockingConnection(pika.URLParameters(self.url))
            self._channel = None
        if self._channel is None or self._channel.is_closed:
            channel = self._connection.channel()
            channel.exchange_declare(
                exchange=self.exchange, exchange_type="topic", durable=True
            )
            channel.confirm_delivery()
            self._channel = channel
            logger.debug("rabbit_publisher_channel_opened exchange=%s", self.exchange)
        return self._channel

    def _force_close(self) -> None:
        try:
            if self._channel is not None and not self._channel.is_closed:
                self._channel.close()
        except Exception:  # noqa: BLE001
            logger.debug("rabbit_publisher_channel_close_error", exc_info=True)
        try:
            if self._connection is not None and not self._connection.is_closed:
                self._connection.close()
        except Exception:  # noqa: BLE001
            logger.debug("rabbit_publisher_connection_close_error", exc_info=True)
        self._channel = None
        self._connection = None
