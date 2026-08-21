from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.beneficiary import BeneficiaryCreate, BeneficiaryRead
from app.services import beneficiary_service

router = APIRouter(prefix="/beneficiaries", tags=["beneficiaries"])


@router.post("", response_model=BeneficiaryRead, status_code=status.HTTP_201_CREATED)
def create_beneficiary(
    payload: BeneficiaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return beneficiary_service.create(db, current_user, payload)


@router.get("", response_model=list[BeneficiaryRead])
def list_beneficiaries(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return beneficiary_service.list_for_user(db, current_user)


@router.delete("/{beneficiary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_beneficiary(
    beneficiary_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    beneficiary_service.delete(db, current_user, beneficiary_id)
