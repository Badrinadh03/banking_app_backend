from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.payee import Payee
from app.models.user import User
from app.schemas.payee import PayeeCreate
from app.services import zipcode_service


def create_payee(db: Session, user: User, payee_in: PayeeCreate) -> Payee:
    if payee_in.zip_code:
        result = zipcode_service.lookup_zip_code(payee_in.zip_code)
        if result["service_available"] and not result["found"]:
            raise BadRequestError("That doesn't look like a real US zip code")

    payee = Payee(user_id=user.id, **payee_in.model_dump())
    db.add(payee)
    db.commit()
    db.refresh(payee)
    return payee


def list_payees(db: Session, user: User) -> list[Payee]:
    return db.query(Payee).filter(Payee.user_id == user.id).order_by(Payee.created_at.desc()).all()


def get_payee_for_user(db: Session, user: User, payee_id: int) -> Payee:
    payee = db.get(Payee, payee_id)
    if payee is None:
        raise NotFoundError("Payee not found")
    if payee.user_id != user.id:
        raise ForbiddenError("You do not have access to this payee")
    return payee
