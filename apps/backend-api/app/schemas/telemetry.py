from datetime import datetime

from uuid import uuid4

from pydantic import BaseModel
from pydantic import Field


class TelemetryIn(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    source_gateway: str | None = None
    device_code: str
    signal_key: str
    value: float
    quality: str = "good"
    source_timestamp: datetime


class GatewayTelemetryBatch(BaseModel):
    gateway_code: str
    sequence_no: int
    sent_at: datetime
    readings: list[TelemetryIn]


class TelemetryRead(BaseModel):
    id: int
    device_id: int
    signal_key: str
    value: float
    quality: str
    source_timestamp: datetime

    class Config:
        from_attributes = True
