from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import ResetPasswordRequest, UserCreate, UserRead, UserUpdate
from app.services.auth_service import get_password_hash
from app.services.event_service import record_event

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    _: User = Depends(require_role(UserRole.INSTALLER)),
    db: Session = Depends(get_db),
):
    stmt = select(User).order_by(User.username.asc())
    return list(db.scalars(stmt).all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_role(UserRole.INSTALLER)),
    db: Session = Depends(get_db),
):
    existing_username = db.scalar(select(User).where(User.username == payload.username))
    if existing_username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    existing_email = db.scalar(select(User).where(User.email == payload.email))
    if existing_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        phone_number=payload.phone_number,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
    )
    db.add(user)
    record_event(
        db,
        category="user",
        event_type="user_created",
        severity="info",
        actor_username=current_user.username,
        message=f"{current_user.username} yeni kullanıcı oluşturdu: {user.username}",
        metadata={"target_username": user.username, "target_role": user.role.value},
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_role(UserRole.INSTALLER)),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    deleted_username = target.username
    db.delete(target)
    record_event(
        db,
        category="user",
        event_type="user_deleted",
        severity="warning",
        actor_username=current_user.username,
        message=f"{current_user.username} kullanıcı sildi: {deleted_username}",
        metadata={"target_username": deleted_username},
    )
    db.commit()
    return None


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_role(UserRole.INSTALLER)),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.email = payload.email
    target.phone_number = payload.phone_number
    target.full_name = payload.full_name
    target.role = payload.role
    record_event(
        db,
        category="user",
        event_type="user_updated",
        severity="info",
        actor_username=current_user.username,
        message=f"{current_user.username} kullanıcı güncelledi: {target.username}",
        metadata={"target_username": target.username, "target_role": target.role.value},
    )
    db.commit()
    db.refresh(target)
    return target


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    current_user: User = Depends(require_role(UserRole.INSTALLER)),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.hashed_password = get_password_hash(payload.new_password)
    record_event(
        db,
        category="user",
        event_type="password_reset",
        severity="warning",
        actor_username=current_user.username,
        message=f"{current_user.username}, {target.username} için şifre sıfırladı",
        metadata={"target_username": target.username},
    )
    db.commit()
    return None
