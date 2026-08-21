from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.address import AddressSearchOut
from app.services import address_service

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("/search", response_model=AddressSearchOut)
def search_addresses(q: str = Query(..., min_length=1), current_user: User = Depends(get_current_user)):
    return address_service.search_addresses(q)
