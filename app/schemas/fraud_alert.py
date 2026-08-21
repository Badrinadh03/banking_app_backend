from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FraudAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int | None
    rule: str
    message: str
    acknowledged: bool
    created_at: datetime
