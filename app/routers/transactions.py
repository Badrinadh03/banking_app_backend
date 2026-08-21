from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.transaction import TransactionRead
from app.services import transfer_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionRead])
def list_all_transactions(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return transfer_service.get_all_transactions_for_user(db, current_user)
