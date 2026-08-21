from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import _validate_password_strength


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3)
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OtpRequestIn(BaseModel):
    identifier: str = Field(min_length=3)
    channel: Literal["email", "phone"]


class OtpRequestOut(BaseModel):
    channel: Literal["email", "phone"]
    masked_target: str
    demo_code: str | None = None


class OtpVerifyIn(BaseModel):
    identifier: str = Field(min_length=3)
    channel: Literal["email", "phone"]
    code: str = Field(min_length=6, max_length=6)


class VerifyAccountOut(BaseModel):
    verified: bool


class ResetPasswordIn(BaseModel):
    identifier: str = Field(min_length=3)
    channel: Literal["email", "phone"]
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)

    _validate_password = field_validator("new_password")(_validate_password_strength)


class ResetPasswordOut(BaseModel):
    reset: bool
