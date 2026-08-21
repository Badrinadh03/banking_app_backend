from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import normalize_phone


def _validate_password_strength(value: str) -> str:
    if not any(c.isalpha() for c in value):
        raise ValueError("Password must contain at least one letter")
    if not any(c.isdigit() for c in value):
        raise ValueError("Password must contain at least one number")
    return value


def _validate_government_id_last4(value: str) -> str:
    if not (value.isdigit() and len(value) == 4):
        raise ValueError("Must be exactly 4 digits")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    phone_number: str = Field(min_length=7, max_length=20)

    _validate_password = field_validator("password")(_validate_password_strength)

    @field_validator("phone_number")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_phone(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    phone_number: str | None
    address: str | None
    government_id_last4: str | None
    remember_device: bool
    primary_contact_method: str
    is_verified: bool
    password_changed_at: datetime | None
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None
    address: str | None = None
    # Not persisted directly — used only to re-validate the ZIP embedded in
    # `address` server-side, mirroring PayeeCreate's zip check.
    zip_code: str | None = None
    government_id_last4: str | None = None
    primary_contact_method: str | None = None
    email: EmailStr | None = None
    # Required only when `email` is being changed — proves ownership of the
    # account before its login identifier changes.
    otp_channel: Literal["email", "phone"] | None = None
    otp_code: str | None = Field(default=None, min_length=6, max_length=6)

    _validate_government_id_last4 = field_validator("government_id_last4")(
        lambda v: _validate_government_id_last4(v) if v else v
    )


class SettingsUpdate(BaseModel):
    remember_device: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

    _validate_password = field_validator("new_password")(_validate_password_strength)


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    current_password: str


class LoginEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
