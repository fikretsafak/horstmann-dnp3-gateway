import json
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.notification_settings import NotificationSettings
from app.models.user import User
from app.services.event_service import record_event


def handle_alarm_created(payload: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        settings_row = db.get(NotificationSettings, 1)
        if settings_row is None:
            return
        users = list(db.scalars(select(User)).all())
        message = (
            f"Alarm: {payload.get('device_name', 'Bilinmeyen cihaz')} - "
            f"{payload.get('signal_key', 'sinyal')} ({payload.get('quality', 'unknown')})"
        )
        if settings_row.smtp_enabled:
            _send_email_notifications(settings_row, users, message)
        if settings_row.sms_enabled:
            _send_sms_notifications(settings_row, users, message)
        record_event(
            db,
            category="notification",
            event_type="alarm_notification_dispatched",
            severity="info",
            message="Alarm bildirimi dağıtımı tamamlandı",
            metadata={"device_code": payload.get("device_code")},
        )
        db.commit()
    except Exception as ex:
        record_event(
            db,
            category="notification",
            event_type="alarm_notification_failed",
            severity="error",
            message=f"Alarm bildirimi gönderilemedi: {ex}",
        )
        db.commit()
    finally:
        db.close()


def _send_email_notifications(settings_row: NotificationSettings, users: list[User], body: str) -> None:
    recipients = [user.email for user in users if user.email]
    if not recipients or not settings_row.smtp_host:
        return

    mail = EmailMessage()
    mail["From"] = settings_row.smtp_from_email
    mail["To"] = ", ".join(recipients)
    mail["Subject"] = "Horstman Alarm Bildirimi"
    mail.set_content(body)

    if settings_row.smtp_port == 465:
        with smtplib.SMTP_SSL(settings_row.smtp_host, settings_row.smtp_port, context=ssl.create_default_context()) as server:
            if settings_row.smtp_username:
                server.login(settings_row.smtp_username, settings_row.smtp_password)
            server.send_message(mail)
    else:
        with smtplib.SMTP(settings_row.smtp_host, settings_row.smtp_port) as server:
            server.ehlo()
            if settings_row.smtp_username:
                server.starttls(context=ssl.create_default_context())
                server.login(settings_row.smtp_username, settings_row.smtp_password)
            server.send_message(mail)


def _send_sms_notifications(settings_row: NotificationSettings, users: list[User], body: str) -> None:
    if settings_row.sms_provider == "mock":
        return
    if not settings_row.sms_api_url or not settings_row.sms_api_key:
        return

    recipients = [user.phone_number for user in users if user.phone_number]
    if not recipients:
        return

    payload = json.dumps(
        {
            "api_key": settings_row.sms_api_key,
            "to": recipients,
            "message": body,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        settings_row.sms_api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10):
        pass
