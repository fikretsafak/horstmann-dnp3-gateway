from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.gateway import Gateway
from app.models.gateway_ingest_batch import GatewayIngestBatch
from app.models.telemetry import Telemetry
from app.schemas.telemetry import GatewayTelemetryBatch, TelemetryIn
from app.services.event_bus import event_bus
from app.services.event_service import record_event


def list_latest_telemetry(db: Session) -> list[Telemetry]:
    stmt = select(Telemetry).order_by(Telemetry.source_timestamp.desc()).limit(200)
    return list(db.scalars(stmt).all())


def ingest_direct_telemetry(db: Session, readings: list[TelemetryIn]) -> int:
    accepted = _persist_readings(db=db, readings=readings)
    db.commit()
    return accepted


def validate_gateway_token(db: Session, gateway_code: str, x_gateway_token: str | None) -> Gateway:
    gateway = db.scalar(select(Gateway).where(Gateway.code == gateway_code))
    if gateway is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway not found")
    if not gateway.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Gateway is inactive")
    if not x_gateway_token or x_gateway_token != gateway.token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway token")
    return gateway


def ingest_gateway_batch(db: Session, payload: GatewayTelemetryBatch, x_gateway_token: str | None) -> int:
    gateway = validate_gateway_token(db, payload.gateway_code, x_gateway_token)
    if gateway.code != payload.gateway_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gateway code mismatch")

    batch_row = GatewayIngestBatch(
        gateway_code=payload.gateway_code,
        sequence_no=payload.sequence_no,
        sent_at=payload.sent_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(batch_row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return 0

    accepted = _persist_readings(db=db, readings=payload.readings)
    gateway.last_seen_at = datetime.now(timezone.utc)
    record_event(
        db,
        category="telemetry",
        event_type="gateway_batch_ingested",
        severity="info",
        message=f"{gateway.name} gateway batch işlendi",
        metadata={"gateway_code": payload.gateway_code, "sequence_no": payload.sequence_no, "accepted": accepted},
    )
    db.commit()
    return accepted


def ingest_gateway_legacy(
    db: Session,
    gateway_code: str,
    readings: list[TelemetryIn],
    x_gateway_token: str | None,
) -> int:
    gateway = validate_gateway_token(db, gateway_code, x_gateway_token)
    accepted = _persist_readings(db=db, readings=readings)
    gateway.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return accepted


def _persist_readings(db: Session, readings: list[TelemetryIn]) -> int:
    _ = db
    accepted = 0
    for reading in readings:
        event_bus.publish_event("telemetry.raw_received", reading.model_dump(mode="json"))
        accepted += 1
    return accepted
