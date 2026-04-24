import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Lock, Thread

from collector_dnp3.config import settings
from collector_dnp3.config_client import (
    BackendConfigClient,
    DeviceConfig,
    GatewayConfig,
    GatewayConfigError,
    SignalConfig,
)
from collector_dnp3.dnp3_adapter import read_device_telemetry
from collector_dnp3.publisher import RabbitPublisher


class _GatewayState:
    """Gateway calisma durumu: aktif cihaz listesi + cihaz bazli son okuma zamani + sinyal katalogu."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._devices: list[DeviceConfig] = []
        self._signals: list[SignalConfig] = []
        self._last_read_at: dict[str, float] = {}
        self._config_version: str = ""
        self._gateway_active: bool = False

    def update(self, config: GatewayConfig) -> bool:
        with self._lock:
            changed = config.config_version != self._config_version
            self._devices = list(config.devices)
            self._signals = list(config.signals)
            self._gateway_active = config.is_active
            known = {device.code for device in self._devices}
            for key in list(self._last_read_at.keys()):
                if key not in known:
                    self._last_read_at.pop(key, None)
            self._config_version = config.config_version
            return changed

    def devices(self) -> list[DeviceConfig]:
        with self._lock:
            return list(self._devices)

    def signals(self) -> list[SignalConfig]:
        with self._lock:
            return list(self._signals)

    def is_active(self) -> bool:
        with self._lock:
            return self._gateway_active

    def mark_read(self, device_code: str, ts: float) -> None:
        with self._lock:
            self._last_read_at[device_code] = ts

    def due_devices(self, now: float) -> list[DeviceConfig]:
        with self._lock:
            due: list[DeviceConfig] = []
            for device in self._devices:
                last = self._last_read_at.get(device.code, 0.0)
                interval = max(1, device.poll_interval_sec)
                if now - last >= interval:
                    due.append(device)
            return due

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "config_version": self._config_version,
                "device_count": len(self._devices),
                "signal_count": len(self._signals),
                "active": self._gateway_active,
                "devices": [device.code for device in self._devices],
            }


_STATE = _GatewayState()
_CONFIG_READY = Event()


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            snapshot = _STATE.snapshot()
            body = {
                "status": "ok" if _CONFIG_READY.is_set() else "starting",
                "service": "collector-dnp3",
                "gateway_code": settings.gateway_code,
                "config": snapshot,
            }
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        _ = format, args
        return


def _start_health_server() -> None:
    server = HTTPServer((settings.worker_health_host, settings.worker_health_port), _HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()


_LAST_ACTIVE_LOG: dict[str, bool] = {}


def _run_config_refresh(client: BackendConfigClient, stop_event: Event) -> None:
    """Backend API'den gateway konfigurasyonunu periyodik olarak cekip state'i gunceller."""
    while not stop_event.is_set():
        try:
            config = client.fetch_config()
            changed = _STATE.update(config)
            _CONFIG_READY.set()
            if changed:
                print(
                    f"collector-config-refresh gateway={config.gateway_code} "
                    f"version={config.config_version} devices={len(config.devices)} "
                    f"signals={len(config.signals)} active={config.is_active}"
                )
            # is_active degisimini loglayalim; kontrol panelinden disable/enable
            # yapildiginda collector log'larinda goze carpsin.
            prev_active = _LAST_ACTIVE_LOG.get(config.gateway_code)
            if prev_active is None or prev_active != config.is_active:
                _LAST_ACTIVE_LOG[config.gateway_code] = config.is_active
                if config.is_active:
                    print(
                        f"collector-active gateway={config.gateway_code} -> polling resumed"
                    )
                else:
                    print(
                        f"collector-suspended gateway={config.gateway_code} -> "
                        "is_active=False; polling askiya alindi, proses hazir bekliyor"
                    )
        except GatewayConfigError as exc:
            print(f"collector-config-error gateway={settings.gateway_code} error={exc}")
        stop_event.wait(timeout=max(5, settings.config_refresh_sec))


_READABLE_DATA_TYPES = {"analog", "binary", "counter", "analog_output"}


def _poll_cycle(publisher: RabbitPublisher) -> int:
    """Okunma vakti gelen tum cihazlar icin telemetry yayinla."""
    if not _STATE.is_active():
        return 0
    all_signals = _STATE.signals()
    # Collector sadece okunabilir tipleri yayinlar; binary_output sadece komut,
    # string ise ayri kanaldan metin bilgisi olarak yonetilir.
    signals = [s for s in all_signals if s.data_type in _READABLE_DATA_TYPES]
    if not signals:
        return 0
    now = time.monotonic()
    due = _STATE.due_devices(now)
    published = 0
    for device in due:
        readings = read_device_telemetry(
            gateway_code=settings.gateway_code,
            device_code=device.code,
            signals=signals,
        )
        try:
            for payload in readings:
                publisher.publish(payload, message_id=payload["message_id"])
            _STATE.mark_read(device.code, now)
            published += len(readings)
        except Exception as exc:  # noqa: BLE001
            print(f"collector-publish-error device={device.code} error={exc}")
    return published


def main() -> None:
    _start_health_server()
    publisher = RabbitPublisher(
        url=settings.rabbitmq_url,
        exchange=settings.rabbitmq_exchange,
        routing_key=settings.rabbitmq_routing_key,
    )
    config_client = BackendConfigClient(
        base_url=settings.backend_api_url,
        gateway_code=settings.gateway_code,
        gateway_token=settings.gateway_token,
        timeout_sec=settings.config_timeout_sec,
    )
    stop_event = Event()
    refresh_thread = Thread(target=_run_config_refresh, args=(config_client, stop_event), daemon=True)
    refresh_thread.start()

    print(
        f"collector-dnp3-running mode={settings.gateway_mode} gateway={settings.gateway_code} "
        f"health={settings.worker_health_host}:{settings.worker_health_port} "
        f"backend={settings.backend_api_url}"
    )

    # Ilk config gelene kadar bekle (en fazla 15 saniye), yoksa bos dongu bas
    _CONFIG_READY.wait(timeout=15)
    try:
        while not stop_event.is_set():
            published = _poll_cycle(publisher)
            if published:
                print(
                    f"collector-cycle gateway={settings.gateway_code} "
                    f"published={published} version={_STATE.snapshot().get('config_version')}"
                )
            time.sleep(max(1, settings.default_poll_interval_sec))
    except KeyboardInterrupt:
        print("collector-dnp3 stopped")
    finally:
        stop_event.set()
        publisher.close()


if __name__ == "__main__":
    main()
