import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import settings

try:
    import pika
except ImportError:  # pragma: no cover - optional dependency
    pika = None


EventHandler = Callable[[dict[str, Any]], None]


@dataclass
class ConsumerConfig:
    queue_name: str
    durable: bool = True
    prefetch_count: int = 20
    dead_letter_exchange: str = ""
    dead_letter_routing_key: str = ""


class EventBus(Protocol):
    def publish_event(self, topic: str, payload: dict[str, Any], *, message_id: str = "") -> None: ...

    def consume_event(self, topic: str, handler: EventHandler, *, config: ConsumerConfig | None = None) -> None: ...


class InProcessEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}

    def publish_event(self, topic: str, payload: dict[str, Any], *, message_id: str = "") -> None:
        _ = message_id
        for handler in self._subscribers.get(topic, []):
            handler(payload)

    def consume_event(self, topic: str, handler: EventHandler, *, config: ConsumerConfig | None = None) -> None:
        _ = config
        handlers = self._subscribers.setdefault(topic, [])
        handlers.append(handler)


class RabbitMqEventBus:
    def __init__(self, url: str, exchange: str) -> None:
        if pika is None:
            raise RuntimeError("RabbitMQ backend selected but 'pika' dependency is missing.")
        self._url = url
        self._exchange = exchange
        self._subscribers: dict[str, list[EventHandler]] = {}

    def publish_event(self, topic: str, payload: dict[str, Any], *, message_id: str = "") -> None:
        connection = pika.BlockingConnection(pika.URLParameters(self._url))
        try:
            channel = connection.channel()
            channel.exchange_declare(exchange=self._exchange, exchange_type="topic", durable=True)
            properties = pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=message_id or payload.get("message_id", ""),
            )
            channel.basic_publish(
                exchange=self._exchange,
                routing_key=topic,
                body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                properties=properties,
            )
        finally:
            connection.close()
        for handler in self._subscribers.get(topic, []):
            handler(payload)

    def consume_event(self, topic: str, handler: EventHandler, *, config: ConsumerConfig | None = None) -> None:
        handlers = self._subscribers.setdefault(topic, [])
        handlers.append(handler)
        consumer_cfg = config or ConsumerConfig(
            queue_name=f"{settings.service_name}.{topic}".replace(".", "_"),
            prefetch_count=settings.rabbitmq_prefetch_count,
            dead_letter_exchange=settings.rabbitmq_dlx_exchange,
            dead_letter_routing_key=f"{topic}.dead",
        )

        def _consume_loop() -> None:
            while True:
                try:
                    connection = pika.BlockingConnection(pika.URLParameters(self._url))
                    channel = connection.channel()
                    channel.exchange_declare(exchange=self._exchange, exchange_type="topic", durable=True)
                    if consumer_cfg.dead_letter_exchange:
                        channel.exchange_declare(
                            exchange=consumer_cfg.dead_letter_exchange,
                            exchange_type="topic",
                            durable=True,
                        )

                    queue_arguments = {}
                    if consumer_cfg.dead_letter_exchange:
                        queue_arguments["x-dead-letter-exchange"] = consumer_cfg.dead_letter_exchange
                    if consumer_cfg.dead_letter_routing_key:
                        queue_arguments["x-dead-letter-routing-key"] = consumer_cfg.dead_letter_routing_key

                    channel.queue_declare(
                        queue=consumer_cfg.queue_name,
                        durable=consumer_cfg.durable,
                        arguments=queue_arguments or None,
                    )
                    channel.queue_bind(exchange=self._exchange, queue=consumer_cfg.queue_name, routing_key=topic)
                    if consumer_cfg.dead_letter_exchange:
                        dlq_name = f"{consumer_cfg.queue_name}.dlq"
                        channel.queue_declare(queue=dlq_name, durable=True)
                        channel.queue_bind(
                            exchange=consumer_cfg.dead_letter_exchange,
                            queue=dlq_name,
                            routing_key=consumer_cfg.dead_letter_routing_key or f"{topic}.dead",
                        )

                    def _on_message(ch, method, properties, body) -> None:  # noqa: ANN001
                        _ = properties
                        try:
                            payload = json.loads(body.decode("utf-8"))
                            handler(payload)
                        except Exception:
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                            return
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                    channel.basic_qos(prefetch_count=max(1, consumer_cfg.prefetch_count))
                    channel.basic_consume(queue=consumer_cfg.queue_name, on_message_callback=_on_message)
                    channel.start_consuming()
                except Exception:
                    try:
                        connection.close()
                    except Exception:
                        pass
                    time.sleep(2)

        thread = threading.Thread(target=_consume_loop, daemon=True)
        thread.start()


def build_event_bus() -> EventBus:
    if settings.event_bus_backend.lower() == "rabbitmq":
        return RabbitMqEventBus(settings.rabbitmq_url, settings.rabbitmq_exchange)
    return InProcessEventBus()


event_bus = build_event_bus()
