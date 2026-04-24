from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.processed_message import ProcessedMessage


def is_processed(db: Session, *, consumer_name: str, message_id: str) -> bool:
    if not message_id:
        return False
    stmt = (
        select(ProcessedMessage.id)
        .where(ProcessedMessage.consumer_name == consumer_name)
        .where(ProcessedMessage.message_id == message_id)
        .limit(1)
    )
    return db.scalar(stmt) is not None


def mark_processed(db: Session, *, consumer_name: str, message_id: str) -> None:
    if not message_id:
        return
    row = ProcessedMessage(
        consumer_name=consumer_name,
        message_id=message_id,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(row)
