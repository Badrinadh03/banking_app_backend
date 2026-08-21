from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user import _validate_government_id_last4


class AccountCreate(BaseModel):
    account_type: str = Field(default="checking", pattern="^(checking|savings)$")
    address: str | None = None
    government_id_last4: str | None = None
    initial_deposit: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    _validate_government_id_last4 = field_validator("government_id_last4")(
        lambda v: _validate_government_id_last4(v) if v else v
    )


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_number: str
    account_type: str
    balance: Decimal
    status: str
    is_owner: bool
    created_at: datetime
