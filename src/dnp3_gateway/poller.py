"""Poll dongusunun cekirdegi: okunacak cihazi bulur, adapter'dan okur, event uretir.

Bu modul her cihaz icin ayri okuma + publish yapar. `main.py` bu fonksiyonu ana
thread dongusunde periyodik olarak cagirir. Tek gateway 100 cihaza kadar olculdugu
icin seri okuma (100 x timeout) bir cycle'i saniyeler surer; bu yuzden
`max_parallel` parametresi ile esik ustunde cihaz varsa ThreadPoolExecutor ile
paralel okuma yapilir. Publisher thread-safe oldugu icin (bkz. rabbit_publisher)
coklu thread ayni kanali paylasabilir.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dnp3_gateway.adapters import SignalReading, TelemetryReader
from dnp3_gateway.backend import DeviceConfig, SignalConfig
from dnp3_gateway.messaging import RabbitPublisher  # noqa: F401  (geri uyumluluk)
from dnp3_gateway.state import GatewayState

logger = logging.getLogger(__name__)


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
    """Tek bir cihazin tum sinyallerini okur ve yayinlar. Yayinlanan sayisini doner."""

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
) -> int:
    """State'ten okunma vakti gelen cihazlari cekip okur.

    `max_parallel` 1 ise eski davranis (seri). 1'den buyukse thread pool ile
    paralel okuma yapilir; bu, 100+ cihazda cycle suresini onemli olcude dusurur.
    Cihaz basina `mark_read` her durumda cagirilir (ayri zamanda okundu kabul
    edilir), boylece bir sonraki cycle'da interval hesaplari saglikli kalir.
    """
    if not state.is_active():
        return 0
    signals = filter_readable_signals(state.signals())
    if not signals:
        return 0
    due = state.due_devices(now_monotonic)
    if not due:
        return 0

    if max_parallel <= 1 or len(due) == 1:
        total = 0
        for device in due:
            count = poll_device(
                gateway_code=gateway_code,
                device=device,
                signals=signals,
                reader=reader,
                publisher=publisher,
            )
            state.mark_read(device.code, now_monotonic)
            total += count
        return total

    workers = min(max_parallel, len(due))
    total = 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="poll") as pool:
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
        for future in as_completed(futures):
            device = futures[future]
            try:
                count = future.result()
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
    return total
