from pydantic import BaseModel


class ZipCodeLookupOut(BaseModel):
    valid: bool
    city: str | None = None
    state: str | None = None
    state_abbreviation: str | None = None
