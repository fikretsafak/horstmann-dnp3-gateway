from app.core.config import settings
from app.services.alarm_worker_service import register_alarm_consumers
from app.services.event_bus import EventBus
from app.services.outbound_worker_service import register_outbound_consumers
from app.services.tag_worker_service import register_tag_consumers


def bootstrap_consumers(bus: EventBus) -> None:
    role = settings.service_role.lower().strip()
    if role in {"tag", "all"}:
        register_tag_consumers(bus)
    if role in {"alarm", "all"}:
        register_alarm_consumers(bus)
    if role in {"outbound", "all"}:
        register_outbound_consumers(bus)
