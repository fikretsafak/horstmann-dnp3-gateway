from datetime import datetime

from pydantic import BaseModel


class SystemEventRead(BaseModel):
    id: int
    category: str
    event_type: str
    severity: str
    message: str
    actor_username: str | None = None
    device_code: str | None = None
    metadata_json: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
