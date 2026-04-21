from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.system_event import SystemEvent
from app.models.user import User
from app.schemas.event import SystemEventRead

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[SystemEventRead])
def list_events(
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    actor_username: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(SystemEvent).order_by(SystemEvent.created_at.desc()).limit(1000)
    if category:
        stmt = stmt.where(SystemEvent.category == category)
    if severity:
        stmt = stmt.where(SystemEvent.severity == severity)
    if actor_username:
        stmt = stmt.where(SystemEvent.actor_username == actor_username)
    return list(db.scalars(stmt).all())
