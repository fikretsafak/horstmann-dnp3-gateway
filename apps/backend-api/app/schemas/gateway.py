from datetime import datetime

from pydantic import BaseModel


class GatewayCreate(BaseModel):
    code: str
    name: str
    host: str
    listen_port: int
    upstream_url: str
    batch_interval_sec: int = 5
    max_devices: int = 200
    device_code_prefix: str | None = None
    token: str
    is_active: bool = True


class GatewayUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    listen_port: int | None = None
    upstream_url: str | None = None
    batch_interval_sec: int | None = None
    max_devices: int | None = None
    device_code_prefix: str | None = None
    token: str | None = None
    is_active: bool | None = None


class GatewayRead(BaseModel):
    id: int
    code: str
    name: str
    host: str
    listen_port: int
    upstream_url: str
    batch_interval_sec: int
    max_devices: int
    device_code_prefix: str | None = None
    token: str
    is_active: bool
    last_seen_at: datetime | None = None

    class Config:
        from_attributes = True
