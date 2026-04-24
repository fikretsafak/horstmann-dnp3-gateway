import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pika

RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "hsl.events")
INCOMING_TOPIC = os.getenv("NOTIFICATION_INCOMING_TOPIC", "alarm.created")
QUEUE_NAME = os.getenv("NOTIFICATION_QUEUE", "hsl.notification_service.alarm")
DLX_EXCHANGE = os.getenv("RABBITMQ_DLX_EXCHANGE", "hsl.events.dlx")
HEALTH_HOST = os.getenv("WORKER_HEALTH_HOST", "127.0.0.1")
HEALTH_PORT = int(os.getenv("WORKER_HEALTH_PORT", "8013"))


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"notification-service"}')
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        _ = format, args
        return


def _start_health_server() -> None:
    server = HTTPServer((HEALTH_HOST, HEALTH_PORT), _HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()


def main() -> None:
    _start_health_server()
    print("notification-service-starting")
    while True:
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBIT_URL))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            channel.exchange_declare(exchange=DLX_EXCHANGE, exchange_type="topic", durable=True)
            channel.queue_declare(
                queue=QUEUE_NAME,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": DLX_EXCHANGE,
                    "x-dead-letter-routing-key": "alarm.created.dead",
                },
            )
            channel.queue_bind(exchange=EXCHANGE, queue=QUEUE_NAME, routing_key=INCOMING_TOPIC)
            channel.basic_qos(prefetch_count=20)

            def _on_message(ch, method, properties, body):  # noqa: ANN001
                _ = properties
                try:
                    payload = json.loads(body.decode("utf-8"))
                    print(
                        "notification-dispatch "
                        f"alarm_msg={payload.get('message_id')} device={payload.get('device_code')}"
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as ex:
                    print(f"notification-service-failed error={ex}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)
            print("notification-service-running")
            channel.start_consuming()
        except Exception as ex:
            print(f"notification-service-reconnect error={ex}")
            time.sleep(3)
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
