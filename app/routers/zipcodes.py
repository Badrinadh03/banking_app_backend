from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.zipcode import ZipCodeLookupOut
from app.services import zipcode_service

router = APIRouter(prefix="/zipcodes", tags=["zipcodes"])


@router.get("/{zip_code}", response_model=ZipCodeLookupOut)
def lookup_zip_code(zip_code: str, current_user: User = Depends(get_current_user)):
    result = zipcode_service.lookup_zip_code(zip_code)
    if not result["service_available"]:
        # Lookup service unreachable — don't block the user over it, just
        # skip showing a confirmation.
        return ZipCodeLookupOut(valid=True)
    if not result["found"]:
        return ZipCodeLookupOut(valid=False)
    return ZipCodeLookupOut(
        valid=True,
        city=result["city"],
        state=result["state"],
        state_abbreviation=result["state_abbreviation"],
    )
