from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountAccessCreate(BaseModel):
    contact_identifier: str = Field(min_length=3)


class AccountAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    user_id: int
    user_name: str
    created_at: datetime
