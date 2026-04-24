from datetime import datetime

from pydantic import BaseModel


class InternalAlarmIngest(BaseModel):
    device_id: int | None = None
    device_code: str | None = None
    level: str = "critical"
    title: str
    description: str
    source_timestamp: datetime | None = None
    message_id: str | None = None
    correlation_id: str | None = None
    source_gateway: str | None = None
