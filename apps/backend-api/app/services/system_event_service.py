from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system_event import SystemEvent


def list_system_events(
    db: Session,
    *,
    category: str | None = None,
    severity: str | None = None,
    actor_username: str | None = None,
) -> list[SystemEvent]:
    stmt = select(SystemEvent).order_by(SystemEvent.created_at.desc()).limit(1000)
    if category:
        stmt = stmt.where(SystemEvent.category == category)
    if severity:
        stmt = stmt.where(SystemEvent.severity == severity)
    if actor_username:
        stmt = stmt.where(SystemEvent.actor_username == actor_username)
    return list(db.scalars(stmt).all())
