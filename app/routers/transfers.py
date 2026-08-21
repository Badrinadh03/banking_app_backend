from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.transaction import ExternalTransferCreate, TransactionRead, TransferCreate
from app.services import transfer_service

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transfer(
    transfer_in: TransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return transfer_service.execute_transfer(
        db,
        current_user,
        transfer_in.from_account_id,
        transfer_in.to_account_id,
        transfer_in.amount,
        transfer_in.description,
    )


@router.post("/external", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_external_transfer(
    transfer_in: ExternalTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return transfer_service.execute_external_transfer(
        db,
        current_user,
        transfer_in.from_account_id,
        transfer_in.amount,
        transfer_in.description,
        transfer_in.recipient_name,
        transfer_in.external_account_number,
        transfer_in.external_routing_number,
        transfer_in.external_bank_name,
        transfer_in.otp_channel,
        transfer_in.otp_code,
    )
