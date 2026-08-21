from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransferCreate(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str | None = None


class ExternalTransferCreate(BaseModel):
    from_account_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str | None = None
    recipient_name: str = Field(min_length=1, max_length=255)
    external_account_number: str = Field(min_length=4, max_length=17)
    external_routing_number: str = Field(min_length=9, max_length=9)
    external_bank_name: str | None = None
    otp_channel: Literal["email", "phone"] = "email"
    otp_code: str = Field(min_length=6, max_length=6)

    @field_validator("external_account_number")
    @classmethod
    def validate_account_number(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Account number must contain only digits")
        return value

    @field_validator("external_routing_number")
    @classmethod
    def validate_routing_number(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Routing number must be exactly 9 digits")
        return value


class DepositCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_account_id: int | None
    to_account_id: int | None
    amount: Decimal
    transaction_type: str
    status: str
    description: str | None
    external_recipient_name: str | None
    external_account_number: str | None
    external_routing_number: str | None
    external_bank_name: str | None
    zelle_contact: str | None
    payee_id: int | None
    created_at: datetime
