import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ZIP_CODE_PATTERN = re.compile(r"^\d{5}(-\d{4})?$")


class PayeeCreate(BaseModel):
    payee_type: Literal["company", "person"]
    pay_method: Literal["bill_pay", "zelle"]
    nickname: str = Field(min_length=1, max_length=100)

    company_name: str | None = Field(default=None, max_length=255)
    account_number: str | None = Field(default=None, min_length=4, max_length=17)
    zip_code: str | None = Field(default=None, min_length=5, max_length=10)

    recipient_name: str | None = Field(default=None, max_length=255)
    mailing_address: str | None = Field(default=None, max_length=500)

    contact_identifier: str | None = Field(default=None, max_length=255)

    @field_validator("account_number")
    @classmethod
    def _validate_account_number(cls, value: str | None) -> str | None:
        if value is not None and not value.isdigit():
            raise ValueError("Account number must contain only digits")
        return value

    @field_validator("zip_code")
    @classmethod
    def _validate_zip_code(cls, value: str | None) -> str | None:
        if value is not None and not ZIP_CODE_PATTERN.match(value):
            raise ValueError("Zip code must be in the format 12345 or 12345-6789")
        return value

    @model_validator(mode="after")
    def _validate_fields_for_type(self):
        if self.payee_type == "company":
            if self.pay_method != "bill_pay":
                raise ValueError("Companies can only be paid via Bill Pay")
            if not (self.company_name and self.account_number and self.zip_code):
                raise ValueError("Company payees require a company name, account number, and zip code")
        elif self.pay_method == "zelle":
            if not self.contact_identifier:
                raise ValueError("Zelle payees require an email or phone number")
        elif self.pay_method == "bill_pay":
            if not (self.recipient_name and self.mailing_address):
                raise ValueError("Person Bill Pay payees require a recipient name and mailing address")
        return self


class PayeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payee_type: str
    pay_method: str
    nickname: str
    company_name: str | None
    account_number: str | None
    zip_code: str | None
    recipient_name: str | None
    mailing_address: str | None
    contact_identifier: str | None
    created_at: datetime
