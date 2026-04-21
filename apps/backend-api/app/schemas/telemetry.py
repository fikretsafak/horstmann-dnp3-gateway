from datetime import datetime

from pydantic import BaseModel


class TelemetryIn(BaseModel):
    device_code: str
    signal_key: str
    value: float
    quality: str = "good"
    source_timestamp: datetime


class TelemetryRead(BaseModel):
    id: int
    device_id: int
    signal_key: str
    value: float
    quality: str
    source_timestamp: datetime

    class Config:
        from_attributes = True
