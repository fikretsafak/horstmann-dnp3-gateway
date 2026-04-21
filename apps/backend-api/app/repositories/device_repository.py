from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_devices(self) -> list[Device]:
        stmt = select(Device).order_by(Device.name.asc())
        return list(self.db.scalars(stmt).all())

    def list_devices_by_gateway(self, gateway_code: str) -> list[Device]:
        stmt = select(Device).where(Device.gateway_code == gateway_code).order_by(Device.name.asc())
        return list(self.db.scalars(stmt).all())

    def get_by_code(self, code: str) -> Device | None:
        stmt = select(Device).where(Device.code == code)
        return self.db.scalar(stmt)

    def create(self, payload: DeviceCreate) -> Device:
        device = Device(**payload.model_dump())
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def update(self, device: Device, payload: DeviceUpdate) -> Device:
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(device, key, value)
        self.db.commit()
        self.db.refresh(device)
        return device

    def delete(self, device: Device) -> None:
        self.db.delete(device)
        self.db.commit()
