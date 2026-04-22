from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.device import Device
from app.schemas.telemetry import TelemetryIn
from app.services.event_bus import EventBus, event_bus
from app.services.event_service import record_event
from app.services.tag_engine_service import process_telemetry_reading


def _on_raw_telemetry_received(payload: dict) -> None:
    db = SessionLocal()
    try:
        reading = TelemetryIn.model_validate(payload)
        device = db.scalar(select(Device).where(Device.code == reading.device_code))
        if device is None:
            return

        telemetry, event_payload = process_telemetry_reading(device, reading)
        db.add(telemetry)

        if event_payload["previous_status"] != event_payload["next_status"]:
            communication_up = event_payload["next_status"] == "online"
            record_event(
                db,
                category="communication",
                event_type="communication_up" if communication_up else "communication_down",
                severity="info" if communication_up else "warning",
                device_code=device.code,
                message=f"{device.name} haberleşmesi {'geldi' if communication_up else 'gitti'}",
                metadata={"device_id": device.id, "quality": telemetry.quality},
            )

        record_event(
            db,
            category="telemetry",
            event_type="telemetry_received",
            severity="info",
            device_code=device.code,
            message=f"{device.name} cihazından telemetri alındı",
            metadata={"signal_key": reading.signal_key, "quality": telemetry.quality},
        )
        event_bus.publish_event("telemetry.received", event_payload)
        db.commit()
    except Exception as ex:
        record_event(
            db,
            category="telemetry",
            event_type="tag_worker_failed",
            severity="error",
            message=f"Tag worker hatası: {ex}",
            metadata={"payload": payload},
        )
        db.commit()
    finally:
        db.close()


def register_tag_consumers(bus: EventBus) -> None:
    bus.consume_event("telemetry.raw_received", _on_raw_telemetry_received)
