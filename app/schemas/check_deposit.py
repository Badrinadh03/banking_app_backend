from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CheckDepositRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    amount: Decimal
    status: str
    hold_release_at: datetime
    cleared_transaction_id: int | None
    created_at: datetime
