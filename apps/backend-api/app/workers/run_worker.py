import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from app.core.config import settings
from app.services.event_bus import event_bus
from app.services.worker_bootstrap import bootstrap_consumers


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        _ = format, args
        return


def _start_health_server() -> None:
    port = settings.worker_health_port
    if port <= 0:
        return
    server = HTTPServer((settings.worker_health_host, port), _HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()


def main() -> None:
    bootstrap_consumers(event_bus)
    _start_health_server()
    print(f"worker-running role={settings.service_role} backend={settings.event_bus_backend}")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
