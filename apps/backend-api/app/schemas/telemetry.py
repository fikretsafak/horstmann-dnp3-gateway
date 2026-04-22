from datetime import datetime

from pydantic import BaseModel


class TelemetryIn(BaseModel):
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
