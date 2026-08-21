from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ZellePaymentCreate(BaseModel):
    from_account_id: int
    contact_identifier: str = Field(min_length=3)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str | None = None
    otp_channel: Literal["email", "phone"] = "email"
    otp_code: str = Field(min_length=6, max_length=6)


class ZelleRequestCreate(BaseModel):
    target_identifier: str = Field(min_length=3)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    note: str | None = None


class ZellePayRequestIn(BaseModel):
    from_account_id: int
    otp_channel: Literal["email", "phone"] = "email"
    otp_code: str = Field(min_length=6, max_length=6)


class ZelleRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_user_id: int
    requester_name: str
    target_identifier: str
    matched_user_id: int | None
    amount: Decimal
    note: str | None
    status: str
    created_at: datetime
