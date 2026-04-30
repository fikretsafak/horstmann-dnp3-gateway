"""Kucuk HTTP sunucusu: `/health`, `/info`, `/metrics` endpoint'leri.

Cati yazilimin operasyon panosu / Smart Logger backend bu endpoint'leri TCP
sondajlayarak gateway'in ayakta olup olmadigini, anlik metriklerini ve
yapilandirma versiyonunu ogrenir. Sayilar `GatewayMetrics` icinde tutulur ve
poller tarafindan thread-safe artirilir.

Multi-instance: Ayni PC'de N gateway calistirilabilir; port=0 verilirse OS
rastgele bos port atar (frontend / supervisor portu instance_id ile keseyilir).
"""

from __future__ import annotations

import json
import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Lock, Thread
from typing import Any

from dnp3_gateway import __version__
from dnp3_gateway.state import GatewayState

logger = logging.getLogger(__name__)


class GatewayMetrics:
    """Thread-safe metrik sayaclari. Poller tarafindan artirilir, /metrics yansitir."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._started_at_monotonic = time.monotonic()
        self._started_at_epoch = time.time()
        self.poll_cycles_total = 0
        self.signals_published_total = 0
        self.signals_skipped_no_change_total = 0
        self.publish_errors_total = 0
        self.read_errors_total = 0
        self.last_cycle_at_epoch: float | None = None
        self.last_cycle_published: int = 0
        self.last_cycle_devices: int = 0

    def record_cycle(self, *, devices: int, published: int) -> None:
        with self._lock:
            self.poll_cycles_total += 1
            self.signals_published_total += published
            self.last_cycle_at_epoch = time.time()
            self.last_cycle_published = published
            self.last_cycle_devices = devices

    def inc_skipped_no_change(self, n: int = 1) -> None:
        with self._lock:
            self.signals_skipped_no_change_total += n

    def inc_publish_error(self, n: int = 1) -> None:
        with self._lock:
            self.publish_errors_total += n

    def inc_read_error(self, n: int = 1) -> None:
        with self._lock:
            self.read_errors_total += n

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "started_at_epoch": self._started_at_epoch,
                "uptime_sec": round(time.monotonic() - self._started_at_monotonic, 2),
                "poll_cycles_total": self.poll_cycles_total,
                "signals_published_total": self.signals_published_total,
                "signals_skipped_no_change_total": self.signals_skipped_no_change_total,
                "publish_errors_total": self.publish_errors_total,
                "read_errors_total": self.read_errors_total,
                "last_cycle_at_epoch": self.last_cycle_at_epoch,
                "last_cycle_published": self.last_cycle_published,
                "last_cycle_devices": self.last_cycle_devices,
            }


def _make_handler(
    *,
    state: GatewayState,
    gateway_code: str,
    gateway_mode: str,
    config_ready: Event,
    instance_id: str,
    app_environment: str,
    metrics: GatewayMetrics,
    actual_port_provider: Any,
) -> type[BaseHTTPRequestHandler]:
    """HTTP handler class'ini state'e + metrics'e bagli olarak dinamik ureten helper."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path in ("/health", "/healthz"):
                body = _build_health_body(
                    state=state,
                    gateway_code=gateway_code,
                    gateway_mode=gateway_mode,
                    config_ready=config_ready,
                    instance_id=instance_id,
                    app_environment=app_environment,
                    health_port=actual_port_provider(),
                )
                self._respond_json(body)
                return
            if self.path == "/info":
                body = {
                    "service": "dnp3-gateway",
                    "version": __version__,
                    "gateway_code": gateway_code,
                    "gateway_instance_id": instance_id,
                    "app_environment": app_environment,
                    "mode": gateway_mode,
                    "worker_health_port": actual_port_provider(),
                    "config_version": state.config_version(),
                    "active": state.is_active(),
                }
                self._respond_json(body)
                return
            if self.path == "/metrics":
                body = {
                    "gateway_code": gateway_code,
                    "gateway_instance_id": instance_id,
                    "config_version": state.config_version(),
                    **metrics.snapshot(),
                }
                self._respond_json(body)
                return
            self.send_response(404)
            self.end_headers()

        def _respond_json(self, body: dict[str, Any]) -> None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            _ = format, args

    return _Handler


def _build_health_body(
    *,
    state: GatewayState,
    gateway_code: str,
    gateway_mode: str,
    config_ready: Event,
    instance_id: str,
    app_environment: str,
    health_port: int,
) -> dict[str, Any]:
    return {
        "status": "ok" if config_ready.is_set() else "starting",
        "service": "dnp3-gateway",
        "version": __version__,
        "gateway_code": gateway_code,
        "gateway_instance_id": instance_id,
        "app_environment": app_environment,
        "worker_health_port": health_port,
        "mode": gateway_mode,
        "config": state.snapshot(),
    }


def start_health_server(
    *,
    host: str,
    port: int,
    state: GatewayState,
    gateway_code: str,
    gateway_mode: str,
    config_ready: Event,
    instance_id: str,
    app_environment: str,
    metrics: GatewayMetrics | None = None,
) -> tuple[HTTPServer, GatewayMetrics, int]:
    """Sunucuyu ayaga kaldirir.

    `port=0` verilirse OS rastgele bos port atar; gercek port `actual_port`
    olarak doner. Caller bu portu log + /health'te gosterir.
    """
    metrics = metrics or GatewayMetrics()

    # actual_port baslangicta bilinmiyor (port=0); bind sonrasi server.server_address[1]
    # uzerinden okunur. Handler handler kapsami icinde okunabilir olsun diye closure.
    actual_port_holder: dict[str, int] = {"port": port}

    def _actual_port_provider() -> int:
        return actual_port_holder["port"]

    handler_cls = _make_handler(
        state=state,
        gateway_code=gateway_code,
        gateway_mode=gateway_mode,
        config_ready=config_ready,
        instance_id=instance_id,
        app_environment=app_environment,
        metrics=metrics,
        actual_port_provider=_actual_port_provider,
    )
    server = HTTPServer((host, port), handler_cls)
    actual_port = int(server.server_address[1])
    actual_port_holder["port"] = actual_port
    Thread(target=server.serve_forever, name="health-http", daemon=True).start()
    if port == 0:
        logger.info(
            "health_server_started host=%s port=%s (auto-assigned, requested=0)",
            host,
            actual_port,
        )
    else:
        logger.info("health_server_started host=%s port=%s", host, actual_port)
    return server, metrics, actual_port
