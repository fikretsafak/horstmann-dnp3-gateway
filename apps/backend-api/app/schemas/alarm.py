from datetime import datetime

from pydantic import BaseModel


class AlarmEventRead(BaseModel):
    id: int
    device_id: int
    level: str
    title: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True
