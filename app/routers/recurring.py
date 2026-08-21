from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.recurring_payment import RecurringPaymentCreate, RecurringPaymentRead
from app.services import recurring_payment_service

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.post("", response_model=RecurringPaymentRead, status_code=status.HTTP_201_CREATED)
def create_recurring_payment(
    payload: RecurringPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return recurring_payment_service.create(db, current_user, payload)


@router.get("", response_model=list[RecurringPaymentRead])
def list_recurring_payments(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return recurring_payment_service.list_for_user(db, current_user)


@router.post("/{recurring_id}/cancel", response_model=RecurringPaymentRead)
def cancel_recurring_payment(
    recurring_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return recurring_payment_service.cancel(db, current_user, recurring_id)
