from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.device import Device
from app.models.enums import UserRole
from app.models.signal_catalog import SignalCatalog
from app.models.telemetry import Telemetry
from app.models.user import User
from app.schemas.signal_catalog import (
    SignalCatalogCreate,
    SignalCatalogRead,
    SignalCatalogUpdate,
    SignalLiveValue,
)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalCatalogRead])
def list_signals(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tum roller standart sinyal listesini okuyabilir."""
    stmt = select(SignalCatalog).order_by(SignalCatalog.display_order.asc(), SignalCatalog.key.asc())
    return list(db.scalars(stmt).all())


@router.post("", response_model=SignalCatalogRead, status_code=status.HTTP_201_CREATED)
def create_signal(
    payload: SignalCatalogCreate,
    _: User = Depends(require_role(UserRole.INSTALLER)),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(SignalCatalog).where(SignalCatalog.key == payload.key))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Signal key already exists")
    row = SignalCatalog(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{signal_key}", response_model=SignalCatalogRead)
def update_signal(
    signal_key: str,
    payload: SignalCatalogUpdate,
    _: User = Depends(require_role(UserRole.INSTALLER)),
    db: Session = Depends(get_db),
):
    row = db.scalar(select(SignalCatalog).where(SignalCatalog.key == signal_key))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{signal_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_signal(
    signal_key: str,
    _: User = Depends(require_role(UserRole.INSTALLER)),
    db: Session = Depends(get_db),
):
    row = db.scalar(select(SignalCatalog).where(SignalCatalog.key == signal_key))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    db.delete(row)
    db.commit()
    return None


@router.get("/live", response_model=list[SignalLiveValue])
def list_live_values(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sinyal bazli canli degerler: her (cihaz, sinyal) icin son telemetri satiri."""
    latest_stmt = (
        select(Telemetry)
        .order_by(Telemetry.device_id, Telemetry.signal_key, Telemetry.source_timestamp.desc())
        .limit(2000)
    )
    telemetries = list(db.scalars(latest_stmt).all())

    devices = {row.id: row for row in db.scalars(select(Device)).all()}
    signals = {row.key: row for row in db.scalars(select(SignalCatalog)).all()}

    latest_by_pair: dict[tuple[int, str], Telemetry] = {}
    for row in telemetries:
        pair = (row.device_id, row.signal_key)
        if pair not in latest_by_pair:
            latest_by_pair[pair] = row

    result: list[SignalLiveValue] = []
    for (device_id, signal_key), row in latest_by_pair.items():
        device = devices.get(device_id)
        if device is None:
            continue
        signal = signals.get(signal_key)
        result.append(
            SignalLiveValue(
                signal_key=signal_key,
                signal_label=signal.label if signal else signal_key,
                unit=signal.unit if signal else None,
                source=signal.source if signal else "master",
                device_id=device_id,
                device_code=device.code,
                device_name=device.name,
                value=row.value,
                quality=row.quality,
                source_timestamp=row.source_timestamp.isoformat(),
            )
        )
    result.sort(key=lambda item: (item.device_code, item.source, item.signal_key))
    return result
