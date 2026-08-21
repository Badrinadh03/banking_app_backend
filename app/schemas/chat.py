from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class SuggestedAction(BaseModel):
    label: str
    path: str


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    suggested_actions: list[SuggestedAction] | None
    created_at: datetime
