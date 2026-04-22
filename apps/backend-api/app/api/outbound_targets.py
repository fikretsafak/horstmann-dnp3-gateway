from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.outbound_target import OutboundTarget
from app.models.user import User
from app.schemas.outbound import OutboundTargetCreate, OutboundTargetRead, OutboundTargetUpdate

router = APIRouter(prefix="/outbound-targets", tags=["outbound-targets"])


@router.get("", response_model=list[OutboundTargetRead])
def list_outbound_targets(
    _: User = Depends(require_roles([UserRole.ENGINEER, UserRole.INSTALLER])),
    db: Session = Depends(get_db),
):
    stmt = select(OutboundTarget).order_by(OutboundTarget.name.asc())
    return list(db.scalars(stmt).all())


@router.post("", response_model=OutboundTargetRead, status_code=status.HTTP_201_CREATED)
def create_outbound_target(
    payload: OutboundTargetCreate,
    _: User = Depends(require_roles([UserRole.ENGINEER, UserRole.INSTALLER])),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(OutboundTarget).where(OutboundTarget.name == payload.name))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Outbound target already exists")
    row = OutboundTarget(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{target_id}", response_model=OutboundTargetRead)
def update_outbound_target(
    target_id: int,
    payload: OutboundTargetUpdate,
    _: User = Depends(require_roles([UserRole.ENGINEER, UserRole.INSTALLER])),
    db: Session = Depends(get_db),
):
    row = db.get(OutboundTarget, target_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outbound target not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outbound_target(
    target_id: int,
    _: User = Depends(require_roles([UserRole.ENGINEER, UserRole.INSTALLER])),
    db: Session = Depends(get_db),
):
    row = db.get(OutboundTarget, target_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outbound target not found")
    db.delete(row)
    db.commit()
    return None
