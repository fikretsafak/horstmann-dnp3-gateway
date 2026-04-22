from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.notification import NotificationSettingsRead, NotificationSettingsUpdate
from app.services.event_service import record_event
from app.services.notification_settings_service import get_or_create_notification_settings

router = APIRouter(prefix="/notification-settings", tags=["notification-settings"])


@router.get("", response_model=NotificationSettingsRead)
def get_notification_settings(
    _: User = Depends(require_roles([UserRole.ENGINEER, UserRole.INSTALLER])),
    db: Session = Depends(get_db),
):
    return get_or_create_notification_settings(db)


@router.put("", response_model=NotificationSettingsRead)
def update_notification_settings(
    payload: NotificationSettingsUpdate,
    current_user: User = Depends(require_roles([UserRole.ENGINEER, UserRole.INSTALLER])),
    db: Session = Depends(get_db),
):
    settings_row = get_or_create_notification_settings(db)
    settings_row.smtp_enabled = payload.smtp_enabled
    settings_row.smtp_host = payload.smtp_host
    settings_row.smtp_port = payload.smtp_port
    settings_row.smtp_username = payload.smtp_username
    settings_row.smtp_password = payload.smtp_password
    settings_row.smtp_from_email = payload.smtp_from_email
    settings_row.sms_enabled = payload.sms_enabled
    settings_row.sms_provider = payload.sms_provider
    settings_row.sms_api_url = payload.sms_api_url
    settings_row.sms_api_key = payload.sms_api_key
    record_event(
        db,
        category="settings",
        event_type="notification_settings_updated",
        severity="info",
        actor_username=current_user.username,
        message="Bildirim ayarları güncellendi",
    )
    db.commit()
    db.refresh(settings_row)
    return settings_row
