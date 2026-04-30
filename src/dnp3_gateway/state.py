"""Gateway'in calisma anindaki durumunu tutan thread-safe yapidir.

Ayni state'i birden fazla thread okur/yazar:

  * `main._run_config_refresh`  -> `update()` ile yeni config bastirir
  * `main._poll_cycle`          -> `due_devices()` / `signals()` ile okuma yapar
  * `main._poll_cycle`          -> `mark_read()` ile son okuma zamanini yazar
  * `health_server`             -> `snapshot()` ile durum raporu uretir

Bu yuzden tum erisimler tek bir `Lock` altindadir.

Persistence: opsiyonel olarak disk'e (`/app/.gateway_state/config.json`)
yazilir. Boylece backend kapali iken / container restart'ta gateway en son
gordugu config ile (cihaz IP'leri, sinyal listesi, master_address) calismaya
devam eder; backend'e ulasilmadan da DNP3 cihazlari okunmaya basar. Yeni
config geldiginde diskteki snapshot uzerine yazilir.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Any

from dnp3_gateway.backend import DeviceConfig, GatewayConfig, SignalConfig

logger = logging.getLogger(__name__)


class GatewayState:
    def __init__(self, *, cache_path: str | os.PathLike | None = None) -> None:
        self._lock = Lock()
        self._devices: list[DeviceConfig] = []
        self._signals: list[SignalConfig] = []
        self._last_read_at: dict[str, float] = {}
        self._config_version: str = ""
        self._gateway_active: bool = False
        self._gateway_name: str = ""
        self._cache_path: Path | None = Path(cache_path) if cache_path else None

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
        # disk yazimi lock disinda — dosya I/O sirasinda okuyucular bloklanmasin
        if changed:
            self._persist_unsafe(config)
        return changed

    def load_from_cache(self) -> bool:
        """Disk'teki son config snapshot'unu okur (varsa). True donerse hazirdir.

        Backend baslangicta kapali olsa bile gateway hemen polling'e baslar.
        Snapshot yoksa veya bozuksa sessizce False doner.
        """

        if self._cache_path is None or not self._cache_path.exists():
            return False
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            devices = [
                DeviceConfig(**{k: v for k, v in d.items() if k in DeviceConfig.__dataclass_fields__})
                for d in data.get("devices", [])
            ]
            signals = [
                SignalConfig(**{k: v for k, v in s.items() if k in SignalConfig.__dataclass_fields__})
                for s in data.get("signals", [])
            ]
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("config_cache_load_failed path=%s error=%s", self._cache_path, exc)
            return False
        with self._lock:
            self._devices = devices
            self._signals = signals
            self._gateway_active = bool(data.get("is_active", True))
            self._gateway_name = str(data.get("gateway_name") or "")
            self._config_version = str(data.get("config_version") or "")
        logger.info(
            "config_cache_loaded path=%s devices=%d signals=%d version=%s",
            self._cache_path,
            len(devices),
            len(signals),
            data.get("config_version"),
        )
        return True

    def _persist_unsafe(self, config: GatewayConfig) -> None:
        """Best-effort: yeni config'i disk'e atomik (tmp + rename) yazar."""

        if self._cache_path is None:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "config_version": config.config_version,
                "gateway_code": config.gateway_code,
                "gateway_name": config.gateway_name,
                "is_active": config.is_active,
                "batch_interval_sec": config.batch_interval_sec,
                "max_devices": config.max_devices,
                "devices": [asdict(d) for d in config.devices],
                "signals": [asdict(s) for s in config.signals],
            }
            # Atomic write: tmp + os.replace
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._cache_path.parent),
                prefix=".config-",
                suffix=".json.tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._cache_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            logger.warning(
                "config_cache_persist_failed path=%s error=%s",
                self._cache_path,
                exc,
            )

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
