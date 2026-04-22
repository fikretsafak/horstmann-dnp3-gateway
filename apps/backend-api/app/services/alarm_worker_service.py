from app.db.session import SessionLocal
from app.services.alarm_engine_service import handle_telemetry_alarm_event
from app.services.event_bus import EventBus
from app.services.event_service import record_event


def _on_telemetry_received(payload: dict) -> None:
    db = SessionLocal()
    try:
        handle_telemetry_alarm_event(db, payload)
        db.commit()
    except Exception as ex:
        record_event(
            db,
            category="alarm",
            event_type="alarm_worker_failed",
            severity="error",
            message=f"Alarm worker hatası: {ex}",
            metadata={"device_code": payload.get("device_code")},
        )
        db.commit()
    finally:
        db.close()


def register_alarm_consumers(bus: EventBus) -> None:
    bus.consume_event("telemetry.received", _on_telemetry_received)
