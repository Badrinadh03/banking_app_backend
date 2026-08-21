from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecurringPaymentCreate(BaseModel):
    from_account_id: int
    payment_type: Literal["transfer", "bill_pay", "zelle"]
    to_account_id: int | None = None
    payee_id: int | None = None
    zelle_contact: str | None = None
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str | None = None
    frequency: Literal["weekly", "monthly"]
    next_run_date: date

    @model_validator(mode="after")
    def _validate_target_for_type(self):
        if self.payment_type == "transfer" and not self.to_account_id:
            raise ValueError("A recurring transfer needs a destination account")
        if self.payment_type == "bill_pay" and not self.payee_id:
            raise ValueError("A recurring bill payment needs a payee")
        if self.payment_type == "zelle" and not self.zelle_contact:
            raise ValueError("A recurring Zelle payment needs a contact")
        return self


class RecurringPaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_account_id: int
    payment_type: str
    to_account_id: int | None
    payee_id: int | None
    zelle_contact: str | None
    amount: Decimal
    description: str | None
    frequency: str
    next_run_date: date
    is_active: bool
    last_run_at: datetime | None
    created_at: datetime
