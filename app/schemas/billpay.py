from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class BillPayStatus(BaseModel):
    enrolled: bool
    enrolled_at: datetime | None


class BillPaymentCreate(BaseModel):
    from_account_id: int
    payee_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str | None = None
    otp_channel: Literal["email", "phone"] = "email"
    otp_code: str = Field(min_length=6, max_length=6)
