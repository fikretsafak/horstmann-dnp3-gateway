import json
import threading
from typing import Any

import pika


class RabbitPublisher:
    """Tek bağlantı üzerinden publisher-confirm moduyla event yayını yapar.

    Bağlantı veya kanal koptuğunda bir sonraki `publish` çağrısında otomatik
    olarak yeniden kurulur. Aynı publisher birden fazla thread'den kullanılırsa
    dahili kilit ile korunur.
    """

    def __init__(self, *, url: str, exchange: str, routing_key: str) -> None:
        self.url = url
        self.exchange = exchange
        self.routing_key = routing_key
        self._connection: pika.BlockingConnection | None = None
        self._channel: Any = None
        self._lock = threading.Lock()

    def _ensure_channel(self) -> Any:
        if self._connection is None or self._connection.is_closed:
            self._connection = pika.BlockingConnection(pika.URLParameters(self.url))
            self._channel = None
        if self._channel is None or self._channel.is_closed:
            channel = self._connection.channel()
            channel.exchange_declare(exchange=self.exchange, exchange_type="topic", durable=True)
            channel.confirm_delivery()
            self._channel = channel
        return self._channel

    def publish(self, payload: dict[str, Any], *, message_id: str) -> None:
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
                    ),
                )
            except (pika.exceptions.AMQPError, OSError):
                # Bağlantı düştüyse bir sonraki denemede yeniden kuracak şekilde sıfırla
                self.close()
                raise

    def close(self) -> None:
        try:
            if self._channel is not None and not self._channel.is_closed:
                self._channel.close()
        except Exception:
            pass
        try:
            if self._connection is not None and not self._connection.is_closed:
                self._connection.close()
        except Exception:
            pass
        self._channel = None
        self._connection = None
