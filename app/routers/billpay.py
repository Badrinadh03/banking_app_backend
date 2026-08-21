from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.billpay import BillPaymentCreate, BillPayStatus
from app.schemas.transaction import TransactionRead
from app.services import billpay_service

router = APIRouter(prefix="/billpay", tags=["billpay"])


@router.post("/enroll", response_model=BillPayStatus)
def enroll(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = billpay_service.enroll(db, current_user)
    return BillPayStatus(enrolled=user.bill_pay_enrolled, enrolled_at=user.bill_pay_enrolled_at)


@router.get("/status", response_model=BillPayStatus)
def status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return BillPayStatus(
        enrolled=current_user.bill_pay_enrolled, enrolled_at=current_user.bill_pay_enrolled_at
    )


@router.post("/pay", response_model=TransactionRead)
def pay_bill(
    payment_in: BillPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return billpay_service.pay_bill(
        db,
        current_user,
        payment_in.from_account_id,
        payment_in.payee_id,
        payment_in.amount,
        payment_in.description,
        payment_in.otp_channel,
        payment_in.otp_code,
    )


@router.get("/activity", response_model=list[TransactionRead])
def get_activity(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return billpay_service.get_activity(db, current_user)
