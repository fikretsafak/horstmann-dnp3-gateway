import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox_event import OutboxEvent
from app.services.event_bus import event_bus


def enqueue_outbox_event(db: Session, *, topic: str, payload: dict, dedup_key: str) -> None:
    if not dedup_key:
        raise ValueError("outbox dedup_key zorunludur")
    existing = db.scalar(select(OutboxEvent).where(OutboxEvent.dedup_key == dedup_key))
    if existing is not None:
        return
    row = OutboxEvent(
        topic=topic,
        dedup_key=dedup_key,
        payload_json=json.dumps(payload, ensure_ascii=False),
        published=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)


def flush_outbox(db: Session, *, limit: int = 100) -> int:
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.published.is_(False))
        .order_by(OutboxEvent.id.asc())
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    published = 0
    for row in rows:
        payload = json.loads(row.payload_json)
        event_bus.publish_event(row.topic, payload, message_id=row.dedup_key)
        row.published = True
        row.published_at = datetime.now(timezone.utc)
        published += 1
    if published:
        db.commit()
    return published
