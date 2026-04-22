from pydantic import BaseModel, EmailStr


class NotificationSettingsRead(BaseModel):
    smtp_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    sms_enabled: bool
    sms_provider: str
    sms_api_url: str
    sms_api_key: str

    class Config:
        from_attributes = True


class NotificationSettingsUpdate(BaseModel):
    smtp_enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: EmailStr
    sms_enabled: bool
    sms_provider: str
    sms_api_url: str
    sms_api_key: str
