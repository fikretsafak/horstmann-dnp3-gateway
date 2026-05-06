"""Kucuk HTTP sunucusu: `/health`, `/info`, `/metrics` endpoint'leri.

Cati yazilimin operasyon panosu / Smart Logger backend bu endpoint'leri TCP
sondajlayarak gateway'in ayakta olup olmadigini, anlik metriklerini ve
yapilandirma versiyonunu ogrenir. Sayilar `GatewayMetrics` icinde tutulur ve
poller tarafindan thread-safe artirilir.

/health durum semantigi:
  * status="ok"       — her sey saglikli, polling ve broker calisiyor
  * status="starting" — ilk config bekleniyor
  * status="degraded" — calisiyor ama bir uyari var (cache stale,
                        config_fetch_error, uzun outage vs.)
  * status="unhealthy"— ciddi sorun, container restart gerekebilir
                        (outbox dolu, vs.) → HTTP 503 doner

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


# Config refresh basarisiz olduginda kac saniye gectikten sonra durumu degraded
# kabul ederiz. config_refresh_sec * 5 makul; default 30s * 5 = 150s.
DEFAULT_REFRESH_DEGRADED_THRESHOLD_SEC = 150


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


def _outbox_snapshot(publisher: Any) -> dict[str, Any]:
    """ResilientPublisher'dan outbox + circuit breaker durumunu cikarir."""
    snap: dict[str, Any] = {
        "outbox_full": False,
        "outbox_full_since_epoch": None,
        "outbox_pending": None,
        "outbox_dead_letter": None,
        "outbox_max_pending": None,
        "last_outbox_error": None,
    }
    if publisher is None:
        return snap
    try:
        snap["outbox_full"] = bool(getattr(publisher, "outbox_full", False))
        full_since = getattr(publisher, "outbox_full_since", None)
        if full_since is not None:
            snap["outbox_full_since_epoch"] = float(full_since)
        last_err = getattr(publisher, "last_outbox_error", None)
        if last_err:
            snap["last_outbox_error"] = str(last_err)[:200]
        outbox = getattr(publisher, "_outbox", None)
        if outbox is not None:
            try:
                snap["outbox_pending"] = int(outbox.pending_count())
            except Exception:  # noqa: BLE001
                pass
            try:
                snap["outbox_dead_letter"] = int(outbox.dead_letter_count())
            except Exception:  # noqa: BLE001
                pass
            try:
                snap["outbox_max_pending"] = int(outbox.max_pending)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        # Saglik endpoint'i hicbir sekilde crash etmemeli
        pass
    return snap


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
    publisher_provider: Any,
) -> type[BaseHTTPRequestHandler]:
    """HTTP handler class'ini state'e + metrics'e bagli olarak dinamik ureten helper."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path in ("/health", "/healthz"):
                body, status_code = _build_health_body(
                    state=state,
                    gateway_code=gateway_code,
                    gateway_mode=gateway_mode,
                    config_ready=config_ready,
                    instance_id=instance_id,
                    app_environment=app_environment,
                    health_port=actual_port_provider(),
                    publisher=publisher_provider() if publisher_provider else None,
                    metrics=metrics,
                )
                self._respond_json(body, status_code=status_code)
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
                outbox_snap = _outbox_snapshot(publisher_provider() if publisher_provider else None)
                body = {
                    "gateway_code": gateway_code,
                    "gateway_instance_id": instance_id,
                    "config_version": state.config_version(),
                    **metrics.snapshot(),
                    **outbox_snap,
                }
                self._respond_json(body)
                return
            self.send_response(404)
            self.end_headers()

        def _respond_json(self, body: dict[str, Any], *, status_code: int = 200) -> None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
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
    publisher: Any,
    metrics: GatewayMetrics,
) -> tuple[dict[str, Any], int]:
    """Health body + HTTP status code uretir.

    Status semantigi:
      * "starting" -> ilk config bekleniyor (HTTP 200, kibarca; LB henuz prob cevabini bekleyebilir)
      * "ok"       -> her sey iyi (HTTP 200)
      * "degraded" -> uyarilar var (HTTP 200; monitoring alert'i tetikleyebilir)
      * "unhealthy"-> ciddi (HTTP 503; LB / orchestrator restart isaretiyle)
    """
    cfg_snapshot = state.snapshot()
    outbox_snap = _outbox_snapshot(publisher)
    metrics_snap = metrics.snapshot()

    issues: list[str] = []
    severity_score = 0  # 0=ok 1=degraded 2=unhealthy

    if not config_ready.is_set():
        # Henuz ilk config alinmadi; gateway acilis surecinde
        severity_score = max(severity_score, 0)
        # Note: starting status'u asagida secilir
    if cfg_snapshot.get("config_cache_stale"):
        issues.append("config_cache_stale")
        severity_score = max(severity_score, 1)
    if cfg_snapshot.get("last_refresh_error"):
        # Backend'e ulasilamadi son denemede; cache valid ise degraded
        secs_since_ok = cfg_snapshot.get("seconds_since_last_refresh_ok")
        if secs_since_ok is None or secs_since_ok > DEFAULT_REFRESH_DEGRADED_THRESHOLD_SEC:
            issues.append("config_refresh_failing")
            severity_score = max(severity_score, 1)
    if outbox_snap.get("outbox_full"):
        issues.append("outbox_full")
        severity_score = max(severity_score, 2)
    if outbox_snap.get("outbox_pending") and outbox_snap.get("outbox_max_pending"):
        # Outbox %80 dolu ise warn
        pending = int(outbox_snap["outbox_pending"])
        cap = int(outbox_snap["outbox_max_pending"])
        if cap > 0 and pending >= int(cap * 0.8):
            issues.append("outbox_near_capacity")
            severity_score = max(severity_score, 1)
    if outbox_snap.get("outbox_dead_letter") and int(outbox_snap["outbox_dead_letter"]) > 0:
        issues.append("dead_letter_messages_present")
        severity_score = max(severity_score, 1)

    # Polling durumu kontrolu — gateway aktif ama hic cycle calismadiysa
    if state.is_active() and metrics_snap["poll_cycles_total"] == 0:
        # Yeni baslamis olabilir; uptime kontrolu
        if metrics_snap["uptime_sec"] > 60:
            issues.append("no_poll_cycles_yet")
            severity_score = max(severity_score, 1)

    if not config_ready.is_set():
        status = "starting"
        http_code = 200
    elif severity_score >= 2:
        status = "unhealthy"
        http_code = 503
    elif severity_score >= 1:
        status = "degraded"
        http_code = 200
    else:
        status = "ok"
        http_code = 200

    body = {
        "status": status,
        "issues": issues,
        "service": "dnp3-gateway",
        "version": __version__,
        "gateway_code": gateway_code,
        "gateway_instance_id": instance_id,
        "app_environment": app_environment,
        "worker_health_port": health_port,
        "mode": gateway_mode,
        "config": cfg_snapshot,
        "outbox": outbox_snap,
        "metrics": {
            "uptime_sec": metrics_snap["uptime_sec"],
            "poll_cycles_total": metrics_snap["poll_cycles_total"],
            "signals_published_total": metrics_snap["signals_published_total"],
            "publish_errors_total": metrics_snap["publish_errors_total"],
            "read_errors_total": metrics_snap["read_errors_total"],
            "last_cycle_at_epoch": metrics_snap["last_cycle_at_epoch"],
            "last_cycle_devices": metrics_snap["last_cycle_devices"],
            "last_cycle_published": metrics_snap["last_cycle_published"],
        },
    }
    return body, http_code


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
    publisher_provider: Any = None,
) -> tuple[HTTPServer, GatewayMetrics, int]:
    """Sunucuyu ayaga kaldirir.

    `port=0` verilirse OS rastgele bos port atar; gercek port `actual_port`
    olarak doner. Caller bu portu log + /health'te gosterir.

    `publisher_provider`: caller tarafindan saglanan ve mevcut
    ResilientPublisher'i donen 0-arglik callable. /health endpoint'i bu
    publisher uzerinden outbox/circuit-breaker durumunu raporlar.
    Boylece health_server publisher'a dogrudan referans tutmaz; restart/replace
    senaryolarinda yine canli pointer'i okur.
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
        publisher_provider=publisher_provider,
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
