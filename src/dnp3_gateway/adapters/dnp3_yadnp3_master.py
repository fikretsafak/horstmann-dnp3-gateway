"""yadnp3 (OpenDNP3) tabanli DNP3 master adapter.

Mimari farki (dnp3_master.py / nfm-dnp3 ile karsilastir):
  - **Tam DNP3 standart implementasyonu** (OpenDNP3 reference). Outstation
    yadnp3 ile yazildigi icin protokol uyumu %100; nfm-dnp3'teki
    'Transport segment data too short' / TCP RST sorunlarinin kayna iki
    farkli kutuphane idi, bu adapter o sorunu cozer.
  - **Event-driven mimari** built-in: master.AddClassScan ile periyodik
    Class 0/1/2/3 scanlari arka planda calisir, her gelen olcum ISOEHandler
    callback'i ile cache'e yazilir. read_device sadece cache snapshot'i alir.
  - **Octet String (Group 110) destegi** vardir: bytes -> UTF-8 metin.

Tasarim:
  - Tek bir DNP3Manager (process basina), N device icin N master.
  - Her cihaz icin ayri TCPClient channel + master + ISOEHandler.
  - Cache: (object_group, index) -> son raw deger / metin. Thread-safe.
  - read_device cache'den okur; deger yoksa 'no_change' (frontend son iyi
    degeri korur — kullanici istegi).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from dnp3_gateway.adapters.base import SignalReading, TelemetryReader
from dnp3_gateway.backend import DeviceConfig, SignalConfig

logger = logging.getLogger(__name__)


try:  # pragma: no cover - opsiyonel bagimlilik
    import opendnp3  # yadnp3 wheel saglar

    _YADNP3_AVAILABLE = True
    _YADNP3_IMPORT_ERROR: Exception | None = None
except Exception as _exc:  # noqa: BLE001
    opendnp3 = None  # type: ignore[assignment]
    _YADNP3_AVAILABLE = False
    _YADNP3_IMPORT_ERROR = _exc


_OBJECT_GROUP_BINARY_INPUT = 1
_OBJECT_GROUP_BINARY_OUTPUT = 10
_OBJECT_GROUP_COUNTER = 20
_OBJECT_GROUP_ANALOG_INPUT = 30
_OBJECT_GROUP_ANALOG_OUTPUT = 40
_OBJECT_GROUP_STRING = 110


class Yadnp3AdapterError(RuntimeError):
    """yadnp3 adapter'inda olusan hata."""


class _DeviceCache:
    """Cihaz basina son-okunan degerler. ISOEHandler yazar, read_device okur."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # (group, index) -> (raw_float, value_string_or_None)
        self._values: dict[tuple[int, int], tuple[float, str | None]] = {}
        self._connected = False
        self._last_update_at: float = 0.0

    def set(self, group: int, index: int, raw: float, value_string: str | None = None) -> None:
        with self._lock:
            self._values[(group, index)] = (raw, value_string)
            self._last_update_at = time.time()

    def get(self, group: int, index: int) -> tuple[float, str | None] | None:
        with self._lock:
            return self._values.get((group, index))

    def set_connected(self, ok: bool) -> None:
        with self._lock:
            self._connected = ok

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def size(self) -> int:
        with self._lock:
            return len(self._values)

    def last_update_at(self) -> float:
        with self._lock:
            return self._last_update_at


def _make_soe_handler(cache: _DeviceCache, device_code: str) -> Any:
    """ISOEHandler subclass: gelen olcumleri cihaz cache'ine yazar."""
    if not _YADNP3_AVAILABLE:
        raise Yadnp3AdapterError(f"yadnp3 yuklu degil: {_YADNP3_IMPORT_ERROR}")

    class _CacheSOEHandler(opendnp3.ISOEHandler):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()

        def BeginFragment(self, info):  # noqa: N802
            pass

        def EndFragment(self, info):  # noqa: N802
            pass

        def OnDeviceAttribute(self, info, set_, variation, value):  # noqa: N802
            pass

        def Process(self, info, values):  # noqa: N802
            if not values:
                return
            first = values[0].value
            try:
                if isinstance(first, opendnp3.Binary):
                    for it in values:
                        cache.set(_OBJECT_GROUP_BINARY_INPUT, it.index, 1.0 if it.value.value else 0.0)
                elif isinstance(first, opendnp3.Analog):
                    for it in values:
                        cache.set(_OBJECT_GROUP_ANALOG_INPUT, it.index, float(it.value.value))
                elif isinstance(first, opendnp3.Counter):
                    for it in values:
                        cache.set(_OBJECT_GROUP_COUNTER, it.index, float(it.value.value))
                elif isinstance(first, opendnp3.BinaryOutputStatus):
                    for it in values:
                        cache.set(_OBJECT_GROUP_BINARY_OUTPUT, it.index, 1.0 if it.value.value else 0.0)
                elif isinstance(first, opendnp3.AnalogOutputStatus):
                    for it in values:
                        cache.set(_OBJECT_GROUP_ANALOG_OUTPUT, it.index, float(it.value.value))
                elif isinstance(first, opendnp3.OctetString):
                    for it in values:
                        try:
                            raw = bytes(it.value.ToBytes())
                        except Exception:  # noqa: BLE001
                            raw = b""
                        # Bos/bos-baslangic byte'lari NUL'lardan temizle, UTF-8 dene
                        text = raw.rstrip(b"\x00").decode("utf-8", errors="replace") or None
                        cache.set(_OBJECT_GROUP_STRING, it.index, 0.0, value_string=text)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "yadnp3_soe_process_error device=%s error=%s",
                    device_code,
                    exc,
                )

    return _CacheSOEHandler()


def _make_master_app(cache: _DeviceCache, device_code: str) -> Any:
    if not _YADNP3_AVAILABLE:
        raise Yadnp3AdapterError(f"yadnp3 yuklu degil: {_YADNP3_IMPORT_ERROR}")

    class _MasterApp(opendnp3.IMasterApplication):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()

        def OnReceiveIIN(self, iin):  # noqa: N802
            pass

        def OnTaskStart(self, type, id):  # noqa: N802, A002
            pass

        def OnTaskComplete(self, info):  # noqa: N802
            pass

        def OnOpen(self):  # noqa: N802
            cache.set_connected(True)
            logger.info("yadnp3_master_link_open device=%s", device_code)

        def OnClose(self):  # noqa: N802
            cache.set_connected(False)
            logger.info("yadnp3_master_link_close device=%s", device_code)

        def AssignClassDuringStartup(self):  # noqa: N802
            return False

        def Now(self):  # noqa: N802
            return opendnp3.DNPTime(int(time.time() * 1000))

    return _MasterApp()


class _ManagedMaster:
    """Bir cihaz icin TCP client + master + cache."""

    def __init__(
        self,
        manager: Any,
        *,
        device: DeviceConfig,
        local_address: int,
        tcp_port: int,
        scan_interval_sec: int,
        baseline_interval_sec: int,
    ) -> None:
        self.device = device
        self.cache = _DeviceCache()
        self._manager = manager
        self._scan_interval_sec = max(1, int(scan_interval_sec))
        self._baseline_interval_sec = max(self._scan_interval_sec, int(baseline_interval_sec))
        self._channel = manager.AddTCPClient(
            f"ch_{device.code}",
            opendnp3.levels.NORMAL,
            opendnp3.ChannelRetry.Default(),
            [opendnp3.IPEndpoint(device.ip_address.strip(), int(tcp_port))],
            "0.0.0.0",
            None,
        )
        self._soe = _make_soe_handler(self.cache, device.code)
        self._app = _make_master_app(self.cache, device.code)
        cfg = opendnp3.MasterStackConfig()
        # Outstation unsolicited frame'leri SOE handler tarafindan dogal islenir;
        # disable etmiyoruz (kucuk mesaj ek yuk yok).
        cfg.master.disableUnsolOnStartup = False
        cfg.master.responseTimeout = opendnp3.TimeDuration.Seconds(10)
        cfg.master.taskRetryPeriod = opendnp3.TimeDuration.Seconds(5)
        cfg.master.maxTaskRetryPeriod = opendnp3.TimeDuration.Minutes(1)
        cfg.link.LocalAddr = int(local_address)
        cfg.link.RemoteAddr = int(device.dnp3_address)
        self._master = self._channel.AddMaster(
            f"m_{device.code}", self._soe, self._app, cfg
        )
        # Periyodik scan'ler — event-driven cache guncellemesi:
        #   - Class 1/2/3 (event) sik (her scan_interval_sec)
        #   - Class 0 (statik baseline) seyrek (baseline_interval_sec)
        self._scan_event = self._master.AddClassScan(
            opendnp3.ClassField(False, True, True, True),  # 1+2+3
            opendnp3.TimeDuration.Seconds(self._scan_interval_sec),
            self._soe,
            opendnp3.TaskConfig.Default(),
        )
        self._scan_class0 = self._master.AddClassScan(
            opendnp3.ClassField(True, False, False, False),  # 0
            opendnp3.TimeDuration.Seconds(self._baseline_interval_sec),
            self._soe,
            opendnp3.TaskConfig.Default(),
        )
        self._master.Enable()
        logger.info(
            "yadnp3_master_enabled device=%s ip=%s:%s remote=%s local=%s "
            "event_scan=%ss baseline_scan=%ss",
            device.code,
            device.ip_address,
            tcp_port,
            device.dnp3_address,
            local_address,
            self._scan_interval_sec,
            self._baseline_interval_sec,
        )

    def shutdown(self) -> None:
        try:
            self._master.Disable()
        except Exception:  # noqa: BLE001
            logger.debug("yadnp3_master_disable_error", exc_info=True)


class Yadnp3TelemetryReader(TelemetryReader):
    """yadnp3 (OpenDNP3) tabanli, event-driven, kayipsiz veri okuyucu."""

    def __init__(
        self,
        *,
        local_address: int,
        default_dnp3_tcp_port: int,
        scan_interval_sec: int = 5,
        baseline_interval_sec: int = 60,
        log_level: str = "NORMAL",
    ) -> None:
        if not _YADNP3_AVAILABLE:
            raise Yadnp3AdapterError(
                "yadnp3 (opendnp3) yuklu degil. Wheel kurulu olmali. "
                f"Import error: {_YADNP3_IMPORT_ERROR}"
            )
        self._local_address = int(local_address)
        self._default_dnp3_tcp_port = int(default_dnp3_tcp_port)
        self._scan_interval_sec = int(scan_interval_sec)
        self._baseline_interval_sec = int(baseline_interval_sec)
        # 1 manager, N master. Manager paylasimli executor'unu kullanir.
        self._manager = opendnp3.DNP3Manager(2)
        self._masters: dict[str, _ManagedMaster] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _resolve_tcp_port(device: DeviceConfig, default_port: int) -> int:
        p = device.dnp3_tcp_port
        if p is not None and 1 <= p <= 65535:
            return int(p)
        return int(default_port)

    def _ensure_master(self, device: DeviceConfig) -> _ManagedMaster:
        with self._lock:
            existing = self._masters.get(device.code)
            if existing is not None:
                return existing
            port = self._resolve_tcp_port(device, self._default_dnp3_tcp_port)
            mm = _ManagedMaster(
                self._manager,
                device=device,
                local_address=self._local_address,
                tcp_port=port,
                scan_interval_sec=self._scan_interval_sec,
                baseline_interval_sec=self._baseline_interval_sec,
            )
            self._masters[device.code] = mm
            return mm

    def read_device(
        self,
        *,
        device: DeviceConfig,
        signals: list[SignalConfig],
    ) -> list[SignalReading]:
        mm = self._ensure_master(device)
        cache = mm.cache
        connected = cache.is_connected()

        # Bagi koptu/kopuk: TUM sinyaller 'comm_lost' kalitesinde yayinlanir.
        # Frontend bu kalitedeki cihazi "haberlesme yok" olarak gosterir.
        # value/value_string son iyi degerleri tasiyabilir (bilgi amacli),
        # ama quality=comm_lost ile frontend stale uyari yapar.
        if not connected:
            return [
                SignalReading(
                    signal_key=s.key,
                    source=s.source,
                    data_type=s.data_type,
                    raw_value=0.0,
                    scaled_value=0.0,
                    quality="comm_lost",
                    value_string=None,
                )
                for s in signals
            ]

        readings: list[SignalReading] = []
        for s in signals:
            entry = cache.get(s.dnp3_object_group, s.dnp3_index)
            if entry is None:
                # Henuz okunmadi (yeni bagi/yeni nokta): 'no_change' — frontend
                # son iyi degeri korur, poller bunu yayinlamaz.
                readings.append(
                    SignalReading(
                        signal_key=s.key,
                        source=s.source,
                        data_type=s.data_type,
                        raw_value=0.0,
                        scaled_value=0.0,
                        quality="no_change",
                        value_string=None,
                    )
                )
                continue
            raw, value_string = entry
            scaled = raw * s.scale + s.offset
            readings.append(
                SignalReading(
                    signal_key=s.key,
                    source=s.source,
                    data_type=s.data_type,
                    raw_value=raw,
                    scaled_value=round(scaled, 4),
                    quality="good",
                    value_string=value_string,
                )
            )
        return readings

    def close(self) -> None:
        with self._lock:
            for mm in list(self._masters.values()):
                try:
                    mm.shutdown()
                except Exception:  # noqa: BLE001
                    logger.debug("yadnp3_master_shutdown_error", exc_info=True)
            self._masters.clear()
        try:
            self._manager.Shutdown()
        except Exception:  # noqa: BLE001
            logger.debug("yadnp3_manager_shutdown_error", exc_info=True)
