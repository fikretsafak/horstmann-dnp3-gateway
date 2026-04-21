from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alarm import AlarmComment, AlarmEvent
from app.models.user import User
from app.schemas.alarm import AlarmAssignRequest, AlarmCommentCreate, AlarmCommentRead, AlarmEventRead
from app.services.event_service import record_event

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("/events", response_model=list[AlarmEventRead])
def list_alarm_events(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(AlarmEvent).order_by(AlarmEvent.created_at.desc()).limit(500)
    return list(db.scalars(stmt).all())


@router.patch("/events/{alarm_id}/assign", response_model=AlarmEventRead)
def assign_alarm(
    alarm_id: int,
    payload: AlarmAssignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alarm = db.get(AlarmEvent, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alarm not found")
    alarm.assigned_to = payload.assigned_to.strip() if payload.assigned_to else None
    record_event(
        db,
        category="alarm",
        event_type="alarm_assigned",
        severity="info",
        actor_username=_.username,
        message=f"Alarm #{alarm.id} ataması güncellendi",
        metadata={"alarm_id": alarm.id, "assigned_to": alarm.assigned_to},
    )
    db.commit()
    db.refresh(alarm)
    return alarm


@router.get("/events/{alarm_id}/comments", response_model=list[AlarmCommentRead])
def list_alarm_comments(alarm_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    alarm = db.get(AlarmEvent, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alarm not found")
    stmt = select(AlarmComment).where(AlarmComment.alarm_event_id == alarm_id).order_by(AlarmComment.created_at.desc())
    return list(db.scalars(stmt).all())


@router.post("/events/{alarm_id}/comments", response_model=AlarmCommentRead, status_code=status.HTTP_201_CREATED)
def create_alarm_comment(
    alarm_id: int,
    payload: AlarmCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alarm = db.get(AlarmEvent, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alarm not found")
    comment_text = payload.comment.strip()
    if not comment_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment cannot be empty")

    row = AlarmComment(
        alarm_event_id=alarm_id,
        author_username=current_user.username,
        comment=comment_text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    record_event(
        db,
        category="alarm",
        event_type="alarm_comment_added",
        severity="info",
        actor_username=current_user.username,
        message=f"Alarm #{alarm.id} için yorum eklendi",
        metadata={"alarm_id": alarm.id},
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/events/{alarm_id}/ack", response_model=AlarmEventRead)
def acknowledge_alarm(alarm_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    alarm = db.get(AlarmEvent, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alarm not found")
    alarm.acknowledged = True
    alarm.acknowledged_at = datetime.now(timezone.utc)
    record_event(
        db,
        category="alarm",
        event_type="alarm_acknowledged",
        severity="info",
        actor_username=_.username,
        message=f"Alarm #{alarm.id} onaylandı",
        metadata={"alarm_id": alarm.id},
    )
    db.commit()
    db.refresh(alarm)
    return alarm


@router.patch("/events/{alarm_id}/reset", response_model=AlarmEventRead)
def reset_alarm(alarm_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    alarm = db.get(AlarmEvent, alarm_id)
    if alarm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alarm not found")
    alarm.reset = True
    alarm.reset_at = datetime.now(timezone.utc)
    record_event(
        db,
        category="alarm",
        event_type="alarm_reset",
        severity="warning",
        actor_username=_.username,
        message=f"Alarm #{alarm.id} resetlendi",
        metadata={"alarm_id": alarm.id},
    )
    db.commit()
    db.refresh(alarm)
    return alarm


@router.post("/events/ack-all", response_model=list[AlarmEventRead])
def acknowledge_all_alarms(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(AlarmEvent).order_by(AlarmEvent.created_at.desc()).limit(500)
    alarms = list(db.scalars(stmt).all())
    now = datetime.now(timezone.utc)
    for alarm in alarms:
        alarm.acknowledged = True
        alarm.acknowledged_at = now
    record_event(
        db,
        category="alarm",
        event_type="alarm_acknowledge_all",
        severity="info",
        actor_username=_.username,
        message="Tüm alarmlar onaylandı",
        metadata={"count": len(alarms)},
    )
    db.commit()
    return alarms


@router.post("/events/reset-all", response_model=list[AlarmEventRead])
def reset_all_alarms(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(AlarmEvent).order_by(AlarmEvent.created_at.desc()).limit(500)
    alarms = list(db.scalars(stmt).all())
    now = datetime.now(timezone.utc)
    for alarm in alarms:
        alarm.reset = True
        alarm.reset_at = now
    record_event(
        db,
        category="alarm",
        event_type="alarm_reset_all",
        severity="warning",
        actor_username=_.username,
        message="Tüm alarmlar resetlendi",
        metadata={"count": len(alarms)},
    )
    db.commit()
    return alarms
