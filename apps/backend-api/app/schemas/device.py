from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CommunicationStatus


class DeviceBase(BaseModel):
    code: str
    name: str
    description: str | None = None
    gateway_code: str | None = None
    ip_address: str
    dnp3_address: int = 1
    poll_interval_sec: int = 5
    timeout_ms: int = 3000
    retry_count: int = 2
    signal_profile: str = "horstmann_sn2_fixed"
    latitude: float
    longitude: float


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    gateway_code: str | None = None
    ip_address: str | None = None
    dnp3_address: int | None = None
    poll_interval_sec: int | None = None
    timeout_ms: int | None = None
    retry_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class DeviceRead(DeviceBase):
    id: int
    battery_percent: float
    communication_status: CommunicationStatus
    alarm_active: bool
    last_update_at: datetime | None

    class Config:
        from_attributes = True
