import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.system_event import SystemEvent


def record_event(
    db: Session,
    *,
    category: str,
    event_type: str,
    message: str,
    severity: str = "info",
    actor_username: str | None = None,
    device_code: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    row = SystemEvent(
        category=category,
        event_type=event_type,
        severity=severity,
        message=message,
        actor_username=actor_username,
        device_code=device_code,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
