from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BeneficiaryCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    relationship_label: str = Field(min_length=1, max_length=50)
    allocation_percentage: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    contact_email: str | None = None
    contact_phone: str | None = None


class BeneficiaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    relationship_label: str
    allocation_percentage: Decimal | None
    contact_email: str | None
    contact_phone: str | None
    created_at: datetime
