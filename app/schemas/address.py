from pydantic import BaseModel


class AddressSuggestion(BaseModel):
    display_name: str
    street: str
    city: str
    state: str
    state_abbreviation: str
    zip_code: str


class AddressSearchOut(BaseModel):
    service_available: bool
    results: list[AddressSuggestion]
