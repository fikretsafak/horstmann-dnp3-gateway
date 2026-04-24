import random
from datetime import datetime, timezone
from uuid import uuid4

from collector_dnp3.config_client import SignalConfig


def _mock_value_for(signal: SignalConfig) -> tuple[float, str]:
    """Horstmann SN2 sinyal tipine göre akla uygun mock değer üret.

    Gerçek DNP3 entegrasyonu yapıldığında bu fonksiyon adapter tarafından
    değiştirilecek; interface aynı kalacak.
    """
    key = signal.key.lower()
    data_type = signal.data_type

    if data_type in {"binary", "binary_output"}:
        value = 1.0 if random.random() < 0.04 else 0.0
        return value, "good"

    if data_type == "counter":
        return float(random.randint(0, 50)), "good"

    if data_type == "string":
        # Ham string değerleri numeric kanalda taşımıyoruz; placeholder.
        return 0.0, "good"

    # analog + analog_output - Horstmann SN2'ye özgü makul aralıklar.
    if "actual_current" in key or "average_current" in key:
        return random.uniform(0, 1500), "good"  # mA
    if "fault_current" in key:
        return random.uniform(0, 8000), "good"
    if "min_current" in key or "minimum_current" in key:
        return random.uniform(0, 200), "good"
    if "max_current" in key or "maximum_current" in key:
        return random.uniform(500, 2500), "good"
    if "trip_level" in key or "trip_current" in key:
        return random.uniform(400, 800), "good"
    if "last_good_known_current" in key:
        return random.uniform(50, 1200), "good"
    if "fault_duration" in key:
        return random.uniform(30, 400), "good"  # ms
    if "actual_voltage" in key or "minimum_voltage" in key or "maximum_voltage" in key or "nominal_voltage" in key:
        return random.uniform(10000, 11500), "good"  # V (orta gerilim)
    if "battery_voltage" in key:
        return random.uniform(320, 420), "good"  # scale=0.01 → 3.2..4.2V (eğer scale 0.01 ise)
    if "conductor_temperature" in key:
        return random.uniform(2000, 8500), "good"  # 1/100 °C
    if "device_temperature" in key:
        return random.uniform(-500, 4500), "good"  # 1/100 °C
    if "phase_angle" in key:
        return random.uniform(-1800, 1800), "good"  # 1/10°
    if "pitch_angle" in key:
        return random.uniform(-4500, 4500), "good"  # 1/100°
    if "modem_rssi" in key or "rssi_satellite" in key:
        return random.uniform(-120, -60), "good"  # dBm
    if "latitude" in key or "longitude" in key:
        return random.uniform(0, 60), "good"
    if "reporting_period" in key:
        return 15.0, "good"
    if "test_point_level" in key:
        return random.uniform(0, 100), "good"
    if "instantaneous_factor" in key:
        return random.uniform(1, 10), "good"
    if "serial_number" in key or "firmware_version" in key or "hardware_revision" in key:
        return 0.0, "good"

    return random.uniform(0, 100), "good"


def read_device_telemetry(
    *,
    gateway_code: str,
    device_code: str,
    signals: list[SignalConfig],
) -> list[dict]:
    """Tek bir cihaz için tüm standart sinyalleri okur ve telemetry event'i oluşturur.

    Her telemetri mesajı `source` alanı taşır (master/sat01/sat02).
    Alarm-service ve tag-engine bu alanı device+signal+source üçlüsü halinde
    izleyebilir — bu sayede Horstmann SN2'de alarmın hangi faz/üniteden
    geldiği asla karışmaz.

    Scale/offset uygulandıktan sonraki "gerçek" değer yayına verilir.
    """
    correlation_id = str(uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    readings: list[dict] = []
    for signal in signals:
        raw, quality = _mock_value_for(signal)
        value = raw * signal.scale + signal.offset
        readings.append(
            {
                "message_id": str(uuid4()),
                "correlation_id": correlation_id,
                "source_gateway": gateway_code,
                "device_code": device_code,
                "signal_key": signal.key,
                "signal_source": signal.source,
                "signal_data_type": signal.data_type,
                "value": round(value, 4),
                "quality": quality,
                "source_timestamp": now_iso,
            }
        )
    return readings
