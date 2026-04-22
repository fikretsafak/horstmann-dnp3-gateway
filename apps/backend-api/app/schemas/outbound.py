from pydantic import BaseModel


class OutboundTargetCreate(BaseModel):
    name: str
    protocol: str
    endpoint: str
    topic: str | None = None
    event_filter: str = "all"
    auth_header: str | None = None
    auth_token: str | None = None
    qos: int = 0
    retain: bool = False
    is_active: bool = True


class OutboundTargetUpdate(BaseModel):
    endpoint: str | None = None
    topic: str | None = None
    event_filter: str | None = None
    auth_header: str | None = None
    auth_token: str | None = None
    qos: int | None = None
    retain: bool | None = None
    is_active: bool | None = None


class OutboundTargetRead(BaseModel):
    id: int
    name: str
    protocol: str
    endpoint: str
    topic: str | None = None
    event_filter: str
    auth_header: str | None = None
    auth_token: str | None = None
    qos: int
    retain: bool
    is_active: bool

    class Config:
        from_attributes = True
