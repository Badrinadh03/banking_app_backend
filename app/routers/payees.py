from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.payee import PayeeCreate, PayeeRead
from app.services import payee_service

router = APIRouter(prefix="/payees", tags=["payees"])


@router.post("", response_model=PayeeRead, status_code=status.HTTP_201_CREATED)
def create_payee(
    payee_in: PayeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return payee_service.create_payee(db, current_user, payee_in)


@router.get("", response_model=list[PayeeRead])
def list_payees(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return payee_service.list_payees(db, current_user)
