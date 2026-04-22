import json
import threading
from collections.abc import Callable
from typing import Any, Protocol

from app.core.config import settings

try:
    import pika
except ImportError:  # pragma: no cover - optional dependency
    pika = None


EventHandler = Callable[[dict[str, Any]], None]


class EventBus(Protocol):
    def publish_event(self, topic: str, payload: dict[str, Any]) -> None: ...

    def consume_event(self, topic: str, handler: EventHandler) -> None: ...


class InProcessEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}

    def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        for handler in self._subscribers.get(topic, []):
            handler(payload)

    def consume_event(self, topic: str, handler: EventHandler) -> None:
        handlers = self._subscribers.setdefault(topic, [])
        handlers.append(handler)


class RabbitMqEventBus:
    def __init__(self, url: str, exchange: str) -> None:
        if pika is None:
            raise RuntimeError("RabbitMQ backend selected but 'pika' dependency is missing.")
        self._url = url
        self._exchange = exchange
        self._subscribers: dict[str, list[EventHandler]] = {}

    def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        connection = pika.BlockingConnection(pika.URLParameters(self._url))
        try:
            channel = connection.channel()
            channel.exchange_declare(exchange=self._exchange, exchange_type="topic", durable=True)
            channel.basic_publish(
                exchange=self._exchange,
                routing_key=topic,
                body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            )
        finally:
            connection.close()
        for handler in self._subscribers.get(topic, []):
            handler(payload)

    def consume_event(self, topic: str, handler: EventHandler) -> None:
        handlers = self._subscribers.setdefault(topic, [])
        handlers.append(handler)

        def _consume_loop() -> None:
            connection = pika.BlockingConnection(pika.URLParameters(self._url))
            channel = connection.channel()
            channel.exchange_declare(exchange=self._exchange, exchange_type="topic", durable=True)
            result = channel.queue_declare(queue="", exclusive=True)
            queue_name = result.method.queue
            channel.queue_bind(exchange=self._exchange, queue=queue_name, routing_key=topic)

            def _on_message(ch, method, properties, body) -> None:  # noqa: ANN001
                _ = method, properties
                payload = json.loads(body.decode("utf-8"))
                handler(payload)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=20)
            channel.basic_consume(queue=queue_name, on_message_callback=_on_message)
            channel.start_consuming()

        thread = threading.Thread(target=_consume_loop, daemon=True)
        thread.start()


def build_event_bus() -> EventBus:
    if settings.event_bus_backend.lower() == "rabbitmq":
        return RabbitMqEventBus(settings.rabbitmq_url, settings.rabbitmq_exchange)
    return InProcessEventBus()


event_bus = build_event_bus()
