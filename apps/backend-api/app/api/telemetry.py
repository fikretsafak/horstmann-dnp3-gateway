from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device
from app.models.enums import CommunicationStatus
from app.models.gateway import Gateway
from app.models.telemetry import Telemetry
from app.models.user import User
from app.schemas.telemetry import TelemetryIn, TelemetryRead
from app.services.event_service import record_event

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/latest", response_model=list[TelemetryRead])
def list_latest(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(Telemetry).order_by(Telemetry.source_timestamp.desc()).limit(200)
    return list(db.scalars(stmt).all())


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def ingest(payload: list[TelemetryIn], db: Session = Depends(get_db)):
    for item in payload:
        device_stmt = select(Device).where(Device.code == item.device_code)
        device = db.scalar(device_stmt)
        if device is None:
            continue
        telemetry = Telemetry(
            device_id=device.id,
            signal_key=item.signal_key,
            value=item.value,
            quality=item.quality,
            source_timestamp=item.source_timestamp,
        )
        quality = item.quality.lower()
        next_status = CommunicationStatus.OFFLINE if quality in {"bad", "offline", "invalid"} else CommunicationStatus.ONLINE
        if device.communication_status != next_status:
            event_type = "communication_up" if next_status == CommunicationStatus.ONLINE else "communication_down"
            severity = "info" if next_status == CommunicationStatus.ONLINE else "warning"
            message = (
                f"{device.name} haberleşmesi geldi"
                if next_status == CommunicationStatus.ONLINE
                else f"{device.name} haberleşmesi gitti"
            )
            record_event(
                db,
                category="communication",
                event_type=event_type,
                severity=severity,
                device_code=device.code,
                message=message,
                metadata={"device_id": device.id, "quality": item.quality},
            )
        device.communication_status = next_status
        device.last_update_at = datetime.now(timezone.utc)
        db.add(telemetry)
        record_event(
            db,
            category="telemetry",
            event_type="telemetry_received",
            severity="info",
            device_code=device.code,
            message=f"{device.name} cihazından telemetri alındı",
            metadata={"signal_key": item.signal_key, "quality": item.quality},
        )
    db.commit()
    return {"accepted": len(payload)}


@router.post("/gateway/{gateway_code}", status_code=status.HTTP_202_ACCEPTED)
def ingest_from_gateway(
    gateway_code: str,
    payload: list[TelemetryIn],
    db: Session = Depends(get_db),
    x_gateway_token: str | None = Header(default=None),
):
    gateway = db.scalar(select(Gateway).where(Gateway.code == gateway_code))
    if gateway is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway not found")
    if not gateway.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Gateway is inactive")
    if not x_gateway_token or x_gateway_token != gateway.token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway token")

    accepted = 0
    for item in payload:
        device_stmt = select(Device).where(Device.code == item.device_code)
        device = db.scalar(device_stmt)
        if device is None:
            continue
        telemetry = Telemetry(
            device_id=device.id,
            signal_key=item.signal_key,
            value=item.value,
            quality=item.quality,
            source_timestamp=item.source_timestamp,
        )
        quality = item.quality.lower()
        next_status = CommunicationStatus.OFFLINE if quality in {"bad", "offline", "invalid"} else CommunicationStatus.ONLINE
        device.communication_status = next_status
        device.last_update_at = datetime.now(timezone.utc)
        db.add(telemetry)
        accepted += 1

    gateway.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return {"accepted": accepted}
