from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CommunicationStatus


class DeviceBase(BaseModel):
    code: str
    name: str
    ip_address: str
    latitude: float
    longitude: float


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: str | None = None
    ip_address: str | None = None
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
