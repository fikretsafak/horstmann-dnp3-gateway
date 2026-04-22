from app.db.session import SessionLocal
from app.services.event_bus import EventBus
from app.services.notification_hook_service import handle_alarm_created
from app.services.outbound_dispatch_service import dispatch_event


def register_outbound_consumers(bus: EventBus) -> None:
    bus.consume_event("alarm.created", _on_alarm_created)
    bus.consume_event("telemetry.received", _on_telemetry_received)


def _on_alarm_created(payload: dict) -> None:
    handle_alarm_created(payload)
    db = SessionLocal()
    try:
        dispatch_event(db, event_kind="alarm", payload=payload)
        db.commit()
    finally:
        db.close()


def _on_telemetry_received(payload: dict) -> None:
    db = SessionLocal()
    try:
        dispatch_event(db, event_kind="telemetry", payload=payload)
        db.commit()
    finally:
        db.close()
