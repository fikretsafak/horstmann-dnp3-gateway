from datetime import datetime, timezone
from typing import Any

from app.models.device import Device
from app.models.enums import CommunicationStatus
from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryIn


def normalize_quality(raw_quality: str) -> str:
    return (raw_quality or "good").strip().lower()


def map_quality_to_status(quality: str) -> CommunicationStatus:
    return CommunicationStatus.OFFLINE if quality in {"bad", "offline", "invalid"} else CommunicationStatus.ONLINE


def process_telemetry_reading(device: Device, reading: TelemetryIn) -> tuple[Telemetry, dict[str, Any]]:
    normalized_quality = normalize_quality(reading.quality)
    previous_status = device.communication_status
    next_status = map_quality_to_status(normalized_quality)

    telemetry = Telemetry(
        device_id=device.id,
        signal_key=reading.signal_key,
        value=reading.value,
        quality=normalized_quality,
        source_timestamp=reading.source_timestamp,
    )

    device.communication_status = next_status
    device.last_update_at = datetime.now(timezone.utc)

    event_payload = {
        "message_id": reading.message_id,
        "correlation_id": reading.correlation_id or reading.message_id,
        "device_id": device.id,
        "device_code": device.code,
        "device_name": device.name,
        "signal_key": reading.signal_key,
        "quality": normalized_quality,
        "previous_status": previous_status.value if previous_status else None,
        "next_status": next_status.value,
        "source_timestamp": reading.source_timestamp.isoformat(),
    }
    return telemetry, event_payload
