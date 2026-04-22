from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.event import SystemEventRead
from app.services.system_event_service import list_system_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[SystemEventRead])
def list_events(
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    actor_username: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return list_system_events(db, category=category, severity=severity, actor_username=actor_username)
