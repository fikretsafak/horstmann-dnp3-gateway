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
    """Bir cihaz icin master session + cache.

    Iki kanal modu desteklenir:

    - ``listening`` (default): cihaz dinler, gateway TCP client olarak
      ``device.ip_address:tcp_port``'a baglanir. ``AddTCPClient``.
    - ``initiating``: cihaz master'a outbound baglanir (4G/SIM saha
      cihazlari icin). Gateway bu cihaza ozel ``master_ip_port``
      uzerinde ``AddTCPServer`` ile dinler. OpenDNP3 TCP server kanali
      tek client kabul ettigi icin cihaz basina ayri port gerek; backend
      bunu otomatik atar (20100..20700).
    """

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
        # String sinyalleri icin son yayinlanan deger cache'i — ayni metin tekrar
        # yayinlanmaz (modem'i bos yere uyandirma). Key: signal_key, Value: text.
        self._last_published_string: dict[str, str] = {}
        self._last_published_lock = threading.Lock()

        endpoint_type = (device.ip_endpoint_type or "listening").lower()
        channel_mode: str
        channel_endpoint_label: str
        if endpoint_type == "initiating":
            # Gateway TCP server modunda dinler; cihaz buraya baglanir.
            # master_ip_port backend tarafindan atanir; yoksa fallback olarak
            # tcp_port'u kullaniriz.
            listen_port = int(device.master_ip_port or tcp_port)
            self._channel = manager.AddTCPServer(
                f"ch_{device.code}",
                opendnp3.levels.NORMAL,
                opendnp3.ServerAcceptMode.CloseExisting,
                opendnp3.IPEndpoint("0.0.0.0", listen_port),
                None,
            )
            channel_mode = "initiating(server)"
            channel_endpoint_label = f"0.0.0.0:{listen_port}"
        else:
            self._channel = manager.AddTCPClient(
                f"ch_{device.code}",
                opendnp3.levels.NORMAL,
                opendnp3.ChannelRetry.Default(),
                [opendnp3.IPEndpoint(device.ip_address.strip(), int(tcp_port))],
                "0.0.0.0",
                None,
            )
            channel_mode = "listening(client)"
            channel_endpoint_label = f"{device.ip_address}:{tcp_port}"

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
        #   - Integrity scan (Class 0+1+2+3) baseline ile ayni sikta — bu,
        #     outstation'da Class 0'a atanmamis ama static olan objeleri
        #     (ozellikle G110 OctetString) getirir. ClassField(True,True,True,True)
        #     opendnp3 icinde "AllClasses" anlamina gelir ve outstation tum static
        #     ve event verisini tek istekle yollar.
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
        # Integrity scan — Class 0+1+2+3 birlikte. Cihazda G110 noktalari
        # Class 0'a atanmamis olabilir (Horstmann'da default boyle); bu scan
        # tum sinif atanmis objeleri tek istekte getirir.
        self._scan_integrity = self._master.AddClassScan(
            opendnp3.ClassField(True, True, True, True),  # 0+1+2+3
            opendnp3.TimeDuration.Seconds(self._baseline_interval_sec),
            self._soe,
            opendnp3.TaskConfig.Default(),
        )

        # G110 (Octet String) icin SPESIFIK range scan — cihazda 'Not Class 0'
        # olarak isaretli oldugu icin class scan G110 getirmez. AddRangeScan
        # outstation'a "G110 noktalarini direct oku" der; sinif atamasindan
        # bagimsiz. Index range genis tutuldu (0-65535).
        #
        # ONEMLI: String degerler STATIK (cihaz seri no, firmware vb.) — surekli
        # okumak modem'i uyandirir, pil tuketir. Bu yuzden interval cok seyrek
        # (1 saat). OnOpen handler'da bagli oldugumuzda manuel bir kerelik scan
        # tetiklenir — startup'ta hemen okunur, sonra saatte bir tazelenir.
        try:
            self._scan_g110 = self._master.AddRangeScan(
                opendnp3.GroupVariationID(110, 0),  # G110 Var0 (default variation)
                0,
                65535,
                opendnp3.TimeDuration.Seconds(3600),  # 1 saat — string'ler statik
                self._soe,
                opendnp3.TaskConfig.Default(),
            )
            logger.info(
                "yadnp3_g110_range_scan_added device=%s interval=3600s (statik)",
                device.code,
            )
        except Exception as exc:  # noqa: BLE001
            # Eski yadnp3 surumlerinde AddRangeScan yoksa veya GroupVariationID
            # imzasi farkli ise sessizce devam et — integrity scan zaten ekli.
            logger.warning(
                "yadnp3_g110_range_scan_failed device=%s error=%s",
                device.code,
                exc,
            )
            self._scan_g110 = None

        self._master.Enable()

        # Bagli olur olmaz string'leri hemen oku — saatlik scan'i beklemeden.
        # Background thread, link acildiktan birkac saniye sonra G110 scan
        # tetikler. Daha sonra periyodik olarak baseline'da yapilir (1 saat).
        def _trigger_initial_g110_scan() -> None:
            # Link kurulmasini bekle (max 30 saniye), kuruldu ise demand et.
            for _ in range(30):
                if self.cache.is_connected():
                    break
                time.sleep(1)
            else:
                return
            scan = getattr(self, "_scan_g110", None)
            if scan is None:
                return
            try:
                scan.Demand()
                logger.info("yadnp3_g110_initial_scan_demanded device=%s", device.code)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "yadnp3_g110_initial_scan_failed device=%s error=%s",
                    device.code,
                    exc,
                )

        threading.Thread(
            target=_trigger_initial_g110_scan,
            name=f"g110_initial_scan_{device.code}",
            daemon=True,
        ).start()
        logger.info(
            "yadnp3_master_enabled device=%s mode=%s endpoint=%s remote=%s local=%s "
            "event_scan=%ss baseline_scan=%ss",
            device.code,
            channel_mode,
            channel_endpoint_label,
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

    @staticmethod
    def _resolve_local_address(device: DeviceConfig, default_addr: int) -> int:
        a = device.master_address
        if a is not None and 0 <= a <= 65519:
            return int(a)
        return int(default_addr)

    def _ensure_master(self, device: DeviceConfig) -> _ManagedMaster:
        with self._lock:
            existing = self._masters.get(device.code)
            if existing is not None:
                return existing
            port = self._resolve_tcp_port(device, self._default_dnp3_tcp_port)
            local_addr = self._resolve_local_address(device, self._local_address)
            mm = _ManagedMaster(
                self._manager,
                device=device,
                local_address=local_addr,
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

        # Stale-data guard: OpenDNP3'in `OnOpen`/`OnClose` callback'leri her
        # turde TCP kopmasinda tetiklenmeyebilir (channel auto-retry icin
        # session ayakta gorunmeye devam edebilir). Bu yuzden link flag'ine
        # ek olarak "son frame'den bu yana gecen sure" kontrolune da bakariz.
        # Threshold = max(2*baseline, 3*scan, 30s) — cihazdan beklenen poll
        # ritminin bir kac katini gecince kesin kopuk sayariz.
        threshold = max(
            self._baseline_interval_sec * 2,
            self._scan_interval_sec * 3,
            30,
        )
        last_update = cache.last_update_at()
        now = time.time()
        stale = last_update == 0.0 or (now - last_update) > threshold

        # Bagi koptu/kopuk veya veri eski: TUM sinyaller 'comm_lost' kalitesinde
        # yayinlanir. Frontend bu kalitedeki cihazi "haberlesme yok" olarak
        # gosterir; canli sinyal sayfasinda quality "bad" donmesi icin de
        # device.communicationStatus collector'da downstream tarafindan
        # comm_lost sinyallerine bakilarak set edilir.
        if not connected or stale:
            if connected and stale:
                logger.warning(
                    "yadnp3_device_stale device=%s ip=%s last_data_age=%ds threshold=%ds "
                    "(link kopmadi gozukuyor ama veri eskidi - comm_lost yayinlaniyor)",
                    device.code,
                    device.ip_address,
                    int(now - last_update) if last_update else -1,
                    threshold,
                )
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

            # String sinyaller (DNP3 G110): cihaz seri no, firmware vb. STATIK.
            # Surekli yayinlamak modem'i uyandirir, pil tuketir. Son yayinlanan
            # ile ayni ise 'no_change' don — poller bunu yayinlamaz.
            if s.data_type == "string":
                txt = value_string or ""
                with mm._last_published_lock:
                    last_txt = mm._last_published_string.get(s.key)
                if last_txt == txt:
                    readings.append(
                        SignalReading(
                            signal_key=s.key,
                            source=s.source,
                            data_type=s.data_type,
                            raw_value=raw,
                            scaled_value=0.0,
                            quality="no_change",
                            value_string=None,
                        )
                    )
                    continue
                # Ilk kez veya degismis: yayinla ve cache'e kaydet.
                with mm._last_published_lock:
                    mm._last_published_string[s.key] = txt
                readings.append(
                    SignalReading(
                        signal_key=s.key,
                        source=s.source,
                        data_type=s.data_type,
                        raw_value=raw,
                        scaled_value=0.0,
                        quality="good",
                        value_string=value_string,
                    )
                )
                continue

            readings.append(
                SignalReading(
                    signal_key=s.key,
                    source=s.source,
                    data_type=s.data_type,
                    raw_value=raw,
                    # 6 ondalik basamak: DNP3 G30v6 (64-bit double) tipindeki
                    # cihazlardan gelen elektrik olcumlerinde (V/A) anlamli
                    # hassasiyet 4-6 basamaga kadar gider. 4 basamak bazi
                    # voltaj olcumlerinde anlamli digit'i kesebiliyordu.
                    scaled_value=round(scaled, 6),
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
