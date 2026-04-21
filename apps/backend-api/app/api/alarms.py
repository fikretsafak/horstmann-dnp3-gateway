from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alarm import AlarmEvent
from app.models.user import User
from app.schemas.alarm import AlarmEventRead

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("/events", response_model=list[AlarmEventRead])
def list_alarm_events(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(AlarmEvent).order_by(AlarmEvent.created_at.desc()).limit(500)
    return list(db.scalars(stmt).all())
