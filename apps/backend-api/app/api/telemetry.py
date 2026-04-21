from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device
from app.models.telemetry import Telemetry
from app.models.user import User
from app.schemas.telemetry import TelemetryIn, TelemetryRead

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
        device.last_update_at = datetime.now(timezone.utc)
        db.add(telemetry)
    db.commit()
    return {"accepted": len(payload)}
