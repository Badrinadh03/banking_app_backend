from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int | None
    channel: str
    recipient: str
    message: str
    delivered: bool
    delivery_error: str | None
    created_at: datetime
