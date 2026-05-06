"""Poll dongusunun cekirdegi: okunacak cihazi bulur, adapter'dan okur, event uretir.

Bu modul her cihaz icin ayri okuma + publish yapar. `main.py` bu fonksiyonu ana
thread dongusunde periyodik olarak cagirir. Tek gateway 100 cihaza kadar olculdugu
icin seri okuma (100 x timeout) bir cycle'i saniyeler surer; bu yuzden
`max_parallel` parametresi ile esik ustunde cihaz varsa ThreadPoolExecutor ile
paralel okuma yapilir. Publisher thread-safe oldugu icin (bkz. rabbit_publisher)
coklu thread ayni kanali paylasabilir.

Kritik dayaniklilik ozellikleri:
  * Cihaz basina **timeout**: TCP read deadlock veya broken DNP3 master'da bir
    cihaz pool worker'i sonsuz tutmaz. Default 15s; cycle global cap = device
    count * 1.5 + 30s.
  * **mark_read her durumda cagirilir**: timeout/exception yolunda da cihaz
    "okundu" kabul edilir; aksi halde "due" kalip her cycle'da retry edilir
    ve worker pool sürekli dolar.
  * **OutboxFullError circuit breaker**: publisher disk-full sinyali verdiyse
    cycle'i derhal kir; sessizce devam etmiyoruz (veri kaybi onlemi).
"""

from __future__ import annotations

import atexit
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, wait
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dnp3_gateway.adapters import SignalReading, TelemetryReader
from dnp3_gateway.backend import DeviceConfig, SignalConfig
from dnp3_gateway.messaging import OutboxFullError, RabbitPublisher  # noqa: F401  (geri uyumluluk)
from dnp3_gateway.state import GatewayState

logger = logging.getLogger(__name__)


# Module-level thread pool: her cycle'da yeniden create/destroy etmek yerine
# tek pool'u tekrar kullaniriz. 100 cihaz × 5sn cycle = saniyede 12 cycle, eski
# yontemde her cycle'da 25 thread spawn + teardown = ~600 thread spawn/dakika
# overhead. Module-level pool'da threadler reuse edilir.
#
# Pool atexit'te kapatilir; sentinel olarak 'None' kullaniliyor (lazy init).
# max_workers ilk kullanan cycle'in max_parallel degeriyle yaratilir; sonraki
# cycle'larda bu deger artarsa yeni pool olusturulur (rare; SIGHUP tarzi).
_pool_lock = threading.Lock()
_pool: ThreadPoolExecutor | None = None
_pool_max_workers: int = 0


def _get_or_create_pool(max_workers: int) -> ThreadPoolExecutor:
    """Module-level singleton ThreadPoolExecutor. Capacity asilirsa yeni pool."""
    global _pool, _pool_max_workers
    with _pool_lock:
        if _pool is None or max_workers > _pool_max_workers:
            old_pool = _pool
            _pool = ThreadPoolExecutor(
                max_workers=max(1, int(max_workers)),
                thread_name_prefix="poll",
            )
            _pool_max_workers = max(1, int(max_workers))
            if old_pool is not None:
                # Eski pool'u kapat (in-flight'larin bitmesini bekleme — yeni
                # pool kullanilacak, eski thread'ler kendiliginden cikar).
                # cancel_futures Python 3.9+; safety icin try
                try:
                    old_pool.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    old_pool.shutdown(wait=False)
        return _pool


def _shutdown_pool() -> None:
    """atexit'te modul kapanmadan once pool'u temizle."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                _pool.shutdown(wait=False)
            _pool = None


atexit.register(_shutdown_pool)


# Tek bir cihazi okuma + tum sinyallerini publish etme icin maksimum sure.
# DNP3 response_timeout default 15s; 1 cihaz birden fazla scan yapmaz, fakat
# stale guard veya broker yavasligi yer kapayabilir. 30s tipik 100 cihazda
# bile yetisir — timeout asilirsa cihaz hangi olarak kabul edilir.
DEFAULT_DEVICE_POLL_TIMEOUT_SEC: float = 30.0

# Tum cycle icin global timeout. Cycle suresi = max(due_devices) * device_timeout
# olabilir, fakat genelde paralel oldugu icin coklu cihaz aynı timeout penceresi
# icinde biter. Yine de bir worker hang ederse digerleri de bekler — global
# guard koymak lazim.
DEFAULT_CYCLE_TIMEOUT_SEC: float = 120.0


# Gateway cihazdan okunabilen tum tipleri yayinlar. Frontend kalite/timestamp
# gostergesi icin string tipi de tasinir; numeric value=0 olur, gercek metin
# (varsa) `value_string` alaninda iletilir. binary_output komut kanali oldugu
# icin yayindan haric kalir (master->outstation komut yonu).
READABLE_DATA_TYPES = frozenset(
    {"analog", "binary", "counter", "analog_output", "string"}
)


def build_telemetry_payload(
    *,
    gateway_code: str,
    device: DeviceConfig,
    reading: SignalReading,
    correlation_id: str,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Raw telemetry event'ini tek yerde olusturur. Schema: TelemetryRawReceivedEvent."""

    # string tipinde numeric value anlamsiz; frontend 0 yerine bos / "—"
    # gostermesi icin null yolla. Gercek metin (varsa) value_string'te.
    is_string = reading.data_type == "string"
    return {
        "message_id": str(uuid4()),
        "correlation_id": correlation_id,
        "source_gateway": gateway_code,
        "device_code": device.code,
        "signal_key": reading.signal_key,
        "signal_source": reading.source,
        "signal_data_type": reading.data_type,
        "value": None if is_string else reading.scaled_value,
        "value_string": reading.value_string,
        "quality": reading.quality,
        "source_timestamp": now_iso or datetime.now(timezone.utc).isoformat(),
    }


def filter_readable_signals(signals: list[SignalConfig]) -> list[SignalConfig]:
    return [s for s in signals if s.data_type in READABLE_DATA_TYPES]


def poll_device(
    *,
    gateway_code: str,
    device: DeviceConfig,
    signals: list[SignalConfig],
    reader: TelemetryReader,
    publisher: Any,
) -> int:
    """Tek bir cihazin tum sinyallerini okur ve yayinlar. Yayinlanan sayisini doner.

    OutboxFullError publish sirasinda raise edilirse caller'a (cycle) yayilir;
    cycle bunu yakalayip cycle'i durdurur (disk-full circuit breaker).
    """

    if not signals:
        return 0
    correlation_id = str(uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        readings = reader.read_device(device=device, signals=signals)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "poll_device_read_failed gateway=%s device=%s error=%s",
            gateway_code,
            device.code,
            exc,
        )
        return 0

    published = 0
    for reading in readings:
        # Event-driven adapter: no_change = bu cycle'da degismedi, yayinlama.
        # Kalan kalite: good | invalid | offline | comm_lost | restart -> hepsi yayinlanir.
        if reading.quality == "no_change":
            continue
        payload = build_telemetry_payload(
            gateway_code=gateway_code,
            device=device,
            reading=reading,
            correlation_id=correlation_id,
            now_iso=now_iso,
        )
        try:
            publisher.publish(
                payload,
                message_id=payload["message_id"],
                correlation_id=correlation_id,
                headers={
                    "source_gateway": gateway_code,
                    "device_code": device.code,
                    "signal_key": reading.signal_key,
                },
            )
            published += 1
        except OutboxFullError:
            # Disk-full circuit breaker: caller'a yay, cycle dursun.
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "poll_device_publish_failed gateway=%s device=%s signal=%s error=%s",
                gateway_code,
                device.code,
                reading.signal_key,
                exc,
            )
    return published


def run_poll_cycle(
    *,
    gateway_code: str,
    state: GatewayState,
    reader: TelemetryReader,
    publisher: Any,
    now_monotonic: float,
    max_parallel: int = 1,
    device_timeout_sec: float = DEFAULT_DEVICE_POLL_TIMEOUT_SEC,
    cycle_timeout_sec: float = DEFAULT_CYCLE_TIMEOUT_SEC,
) -> int:
    """State'ten okunma vakti gelen cihazlari cekip okur.

    `max_parallel` 1 ise eski davranis (seri). 1'den buyukse thread pool ile
    paralel okuma yapilir; bu, 100+ cihazda cycle suresini onemli olcude dusurur.

    Timeout davranisi:
      * `device_timeout_sec` her cihaz icin: bir cihaz hang ederse o cihaz
        timeout edilir, mark_read cagirilip diger cihazlar etkilenmez.
      * `cycle_timeout_sec` tum cycle icin: ust sinir; asilirsa pending
        future'lar iptal edilir ve cycle return eder.

    Cihaz basina `mark_read` HER DURUMDA cagirilir (success/error/timeout),
    boylece bir sonraki cycle'da interval hesaplari saglikli kalir ve hang eden
    cihaz worker pool'u tikamaz.

    Disk-full circuit breaker:
      * Publisher OutboxFullError raise ederse cycle DURDURULUR. Pending
        cihazlar mark_read edilir (sonraki cycle'da retry); broker geri gelene
        kadar yeni publish denenmez.
    """
    if not state.is_active():
        return 0
    signals = filter_readable_signals(state.signals())
    if not signals:
        return 0
    # Cycle basinda silinen cihazlarin acik master/channel'larini kapat.
    # Bu olmazsa zombie master'lar yeni cihazlarla TCP/DNP3 link layer
    # catismasina yol acar (ornek: ayni IP'de iki cihaz, biri silindiginde
    # diger cihazin baglantisi flap yapar). state.devices() tum config'teki
    # cihazlari verir (sadece due olanlar degil), boylece geride kalan
    # cihazlarin master'i da hayatta tutulur.
    try:
        all_active_codes = {d.code for d in state.devices()}
        if hasattr(reader, "forget_devices"):
            cleaned = reader.forget_devices(all_active_codes)
            if cleaned:
                logger.info(
                    "reader_forgot_stale_devices count=%d active=%d",
                    cleaned,
                    len(all_active_codes),
                )
    except Exception:  # noqa: BLE001 — cleanup hatasi cycle'i blocklamasin
        logger.debug("reader_forget_devices_error", exc_info=True)
    due = state.due_devices(now_monotonic)
    if not due:
        return 0

    # Disk-full breaker erken kontrol: publisher zaten dolu durumdaysa cycle'a
    # girmeden mark_read yap ve cik (yeni publish denemesi yok)
    if getattr(publisher, "outbox_full", False):
        logger.warning(
            "poll_cycle_skipped_outbox_full pending=%d devices=%d — broker "
            "geri gelene kadar publish yapilmaz",
            getattr(publisher, "_outbox", None) and publisher._outbox.pending_count() or -1,
            len(due),
        )
        # Mark_read yapma: cihazlar sonraki cycle'da yine due olur ama o cycle'da
        # da skip edilir; broker dogrulandiginda otomatik resume eder.
        return 0

    if max_parallel <= 1 or len(due) == 1:
        total = 0
        for device in due:
            try:
                count = poll_device(
                    gateway_code=gateway_code,
                    device=device,
                    signals=signals,
                    reader=reader,
                    publisher=publisher,
                )
            except OutboxFullError:
                # Disk-full → cycle'i kir, kalan cihazlari mark_read et
                state.mark_read(device.code, now_monotonic)
                logger.error(
                    "poll_cycle_aborted_outbox_full device=%s remaining=%d",
                    device.code,
                    len(due) - (due.index(device) + 1),
                )
                return total
            state.mark_read(device.code, now_monotonic)
            total += count
        return total

    workers = min(max_parallel, len(due))
    total = 0
    breaker_tripped = False
    # Module-level pool: thread'ler reuse edilir; her cycle'da spawn/destroy
    # overhead'i yok. Pool capacity yetmezse yeniden create eder.
    pool = _get_or_create_pool(max_workers=workers)
    futures = {
        pool.submit(
            poll_device,
            gateway_code=gateway_code,
            device=device,
            signals=signals,
            reader=reader,
            publisher=publisher,
        ): device
        for device in due
    }
    # Tum cycle icin global timeout: belirlenen sure asilirsa pending
    # future'lar iptal edilir.
    done, not_done = wait(futures.keys(), timeout=cycle_timeout_sec)

    # Bitenlerden sonuclari topla
    for future in done:
        device = futures[future]
        try:
            count = future.result(timeout=0)  # zaten done; timeout=0 OK
        except OutboxFullError:
            breaker_tripped = True
            count = 0
            logger.error(
                "poll_cycle_aborted_outbox_full device=%s",
                device.code,
            )
        except FuturesTimeoutError:
            count = 0
            logger.warning(
                "poll_device_timeout gateway=%s device=%s timeout=%.1fs",
                gateway_code,
                device.code,
                device_timeout_sec,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "poll_device_future_failed gateway=%s device=%s error=%s",
                gateway_code,
                device.code,
                exc,
            )
            count = 0
        state.mark_read(device.code, now_monotonic)
        total += count

    # Cycle timeout sonrasi hala calisan future'lar var → cancel + log
    if not_done:
        logger.warning(
            "poll_cycle_global_timeout exceeded=%.1fs pending=%d "
            "(donmeyen cihazlar mark_read edilip cancel edilecek)",
            cycle_timeout_sec,
            len(not_done),
        )
        for future in not_done:
            device = futures[future]
            future.cancel()  # interrupt etmez ama mark_read kayit altina
            # mark_read: cihazi "okundu" kabul et ki sonraki cycle'da
            # tekrar due olsun (her cycle'da retry sürmesin)
            state.mark_read(device.code, now_monotonic)
            logger.warning(
                "poll_device_cycle_timeout gateway=%s device=%s — bu cycle'da "
                "yanit alinamadi, sonraki cycle'da yeniden denenecek",
                gateway_code,
                device.code,
            )

    if breaker_tripped:
        logger.error(
            "poll_cycle_outbox_full_breaker total_published=%d due=%d — "
            "broker dogrulanana kadar yeni cycle'lar skip edilecek",
            total,
            len(due),
        )
    return total
