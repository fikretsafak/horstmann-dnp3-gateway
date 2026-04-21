from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: UserRole

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    role: UserRole


class ResetPasswordRequest(BaseModel):
    new_password: str


class SelfProfileUpdateRequest(BaseModel):
    full_name: str
    email: EmailStr


class SelfPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
