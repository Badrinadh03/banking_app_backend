from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CardIssueIn(BaseModel):
    account_id: int
    otp_channel: Literal["email", "phone"] = "email"
    otp_code: str = Field(min_length=6, max_length=6)


class CardRevealIn(BaseModel):
    otp_channel: Literal["email", "phone"] = "email"
    otp_code: str = Field(min_length=6, max_length=6)


class WalletLinkIn(BaseModel):
    provider: Literal["apple", "google"]


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    cardholder_name: str
    last4: str
    expiry_month: int
    expiry_year: int
    status: str
    apple_wallet_linked: bool
    google_wallet_linked: bool
    created_at: datetime


class CardRevealOut(BaseModel):
    card_number: str
    cvv: str
    expiry_month: int
    expiry_year: int
    cardholder_name: str
