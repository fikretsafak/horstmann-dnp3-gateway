"""Gateway'in calisma anindaki durumunu tutan thread-safe yapidir.

Ayni state'i birden fazla thread okur/yazar:

  * `main._run_config_refresh`  -> `update()` ile yeni config bastirir
  * `main._poll_cycle`          -> `due_devices()` / `signals()` ile okuma yapar
  * `main._poll_cycle`          -> `mark_read()` ile son okuma zamanini yazar
  * `health_server`             -> `snapshot()` ile durum raporu uretir

Bu yuzden tum erisimler tek bir `Lock` altindadir.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from dnp3_gateway.backend import DeviceConfig, GatewayConfig, SignalConfig


class GatewayState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._devices: list[DeviceConfig] = []
        self._signals: list[SignalConfig] = []
        self._last_read_at: dict[str, float] = {}
        self._config_version: str = ""
        self._gateway_active: bool = False
        self._gateway_name: str = ""

    def update(self, config: GatewayConfig) -> bool:
        """Yeni config gelince state'i gunceller. Degistiyse True doner."""
        with self._lock:
            changed = config.config_version != self._config_version
            self._devices = list(config.devices)
            self._signals = list(config.signals)
            self._gateway_active = config.is_active
            self._gateway_name = config.gateway_name
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

    def config_version(self) -> str:
        with self._lock:
            return self._config_version

    def mark_read(self, device_code: str, monotonic_ts: float) -> None:
        with self._lock:
            self._last_read_at[device_code] = monotonic_ts

    def due_devices(self, now_monotonic: float) -> list[DeviceConfig]:
        """poll_interval_sec gecmisse okunmasi gereken cihazlari listeler."""
        with self._lock:
            due: list[DeviceConfig] = []
            for device in self._devices:
                last = self._last_read_at.get(device.code, 0.0)
                interval = max(1, device.poll_interval_sec)
                if now_monotonic - last >= interval:
                    due.append(device)
            return due

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "gateway_name": self._gateway_name,
                "config_version": self._config_version,
                "device_count": len(self._devices),
                "signal_count": len(self._signals),
                "active": self._gateway_active,
                "devices": [device.code for device in self._devices],
                "devices_detail": [
                    {
                        "code": d.code,
                        "ip_address": d.ip_address,
                        "dnp3_tcp_port": d.dnp3_tcp_port,
                        "dnp3_address": d.dnp3_address,
                    }
                    for d in self._devices
                ],
            }
