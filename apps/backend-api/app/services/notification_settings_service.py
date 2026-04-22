from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification_settings import NotificationSettings


def get_or_create_notification_settings(db: Session) -> NotificationSettings:
    settings_row = db.get(NotificationSettings, 1)
    if settings_row is not None:
        return settings_row

    settings_row = NotificationSettings(
        id=1,
        smtp_enabled=settings.smtp_enabled,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password=settings.smtp_password,
        smtp_from_email=settings.smtp_from_email,
        sms_enabled=settings.sms_enabled,
        sms_provider=settings.sms_provider,
        sms_api_url=settings.sms_api_url,
        sms_api_key=settings.sms_api_key,
    )
    db.add(settings_row)
    db.commit()
    db.refresh(settings_row)
    return settings_row
