from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.transaction import TransactionRead
from app.schemas.zelle import (
    ZellePayRequestIn,
    ZellePaymentCreate,
    ZelleRequestCreate,
    ZelleRequestRead,
)
from app.services import zelle_service

router = APIRouter(prefix="/zelle", tags=["zelle"])


def _to_request_read(zelle_request) -> ZelleRequestRead:
    return ZelleRequestRead(
        id=zelle_request.id,
        requester_user_id=zelle_request.requester_user_id,
        requester_name=zelle_request.requester.full_name,
        target_identifier=zelle_request.target_identifier,
        matched_user_id=zelle_request.matched_user_id,
        amount=zelle_request.amount,
        note=zelle_request.note,
        status=zelle_request.status,
        created_at=zelle_request.created_at,
    )


@router.post("/pay", response_model=TransactionRead)
def pay(
    payment_in: ZellePaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return zelle_service.pay(
        db,
        current_user,
        payment_in.from_account_id,
        payment_in.contact_identifier,
        payment_in.amount,
        payment_in.description,
        payment_in.otp_channel,
        payment_in.otp_code,
    )


@router.post("/request", response_model=ZelleRequestRead)
def request_money(
    request_in: ZelleRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    zelle_request = zelle_service.request(
        db, current_user, request_in.target_identifier, request_in.amount, request_in.note
    )
    return _to_request_read(zelle_request)


@router.get("/requests", response_model=list[ZelleRequestRead])
def list_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    requests = zelle_service.list_incoming_requests(db, current_user)
    return [_to_request_read(r) for r in requests]


@router.post("/requests/{request_id}/pay", response_model=TransactionRead)
def pay_request(
    request_id: int,
    payload: ZellePayRequestIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return zelle_service.pay_request(
        db, current_user, request_id, payload.from_account_id, payload.otp_channel, payload.otp_code
    )


@router.post("/requests/{request_id}/decline", response_model=ZelleRequestRead)
def decline_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    zelle_request = zelle_service.decline_request(db, current_user, request_id)
    return _to_request_read(zelle_request)


@router.get("/activity", response_model=list[TransactionRead])
def get_activity(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return zelle_service.get_recent_activity(db, current_user)
