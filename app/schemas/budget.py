from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BudgetCreate(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    monthly_limit: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    monthly_limit: Decimal
    created_at: datetime


class BudgetProgress(BaseModel):
    budget: BudgetRead
    spent: Decimal
    remaining: Decimal
    percent_used: float
