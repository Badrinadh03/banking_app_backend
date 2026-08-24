from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IdentityDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_type: str
    created_at: datetime
