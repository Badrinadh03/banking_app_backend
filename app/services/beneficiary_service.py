from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.beneficiary import Beneficiary
from app.models.user import User
from app.schemas.beneficiary import BeneficiaryCreate


def create(db: Session, user: User, payload: BeneficiaryCreate) -> Beneficiary:
    beneficiary = Beneficiary(user_id=user.id, **payload.model_dump())
    db.add(beneficiary)
    db.commit()
    db.refresh(beneficiary)
    return beneficiary


def list_for_user(db: Session, user: User) -> list[Beneficiary]:
    return (
        db.query(Beneficiary)
        .filter(Beneficiary.user_id == user.id)
        .order_by(Beneficiary.created_at)
        .all()
    )


def delete(db: Session, user: User, beneficiary_id: int) -> None:
    beneficiary = db.get(Beneficiary, beneficiary_id)
    if beneficiary is None or beneficiary.user_id != user.id:
        raise NotFoundError("Beneficiary not found")
    db.delete(beneficiary)
    db.commit()
