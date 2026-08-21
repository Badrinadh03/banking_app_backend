from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import normalize_phone
from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.account import Account
from app.models.account_access import AccountAccess
from app.models.user import User


def _resolve_user_by_contact(db: Session, identifier: str) -> User | None:
    normalized_phone = normalize_phone(identifier)
    return (
        db.query(User)
        .filter(or_(User.email == identifier, User.phone_number == normalized_phone))
        .first()
    )


def grant_access(db: Session, owner: User, account_id: int, contact_identifier: str) -> AccountAccess:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    if account.user_id != owner.id:
        raise ForbiddenError("Only the account owner can grant shared access")

    grantee = _resolve_user_by_contact(db, contact_identifier)
    if grantee is None:
        raise BadRequestError("No account found for that email or phone number")
    if grantee.id == owner.id:
        raise BadRequestError("You already own this account")

    existing = (
        db.query(AccountAccess)
        .filter(AccountAccess.account_id == account_id, AccountAccess.user_id == grantee.id)
        .first()
    )
    if existing is not None:
        raise BadRequestError("This person already has access to this account")

    access = AccountAccess(account_id=account_id, user_id=grantee.id, granted_by_user_id=owner.id)
    db.add(access)
    db.commit()
    db.refresh(access)
    return access


def list_access(db: Session, owner: User, account_id: int) -> list[AccountAccess]:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    if account.user_id != owner.id:
        raise ForbiddenError("Only the account owner can view shared access")
    return db.query(AccountAccess).filter(AccountAccess.account_id == account_id).all()


def revoke_access(db: Session, owner: User, account_id: int, access_user_id: int) -> None:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    if account.user_id != owner.id:
        raise ForbiddenError("Only the account owner can revoke shared access")

    access = (
        db.query(AccountAccess)
        .filter(AccountAccess.account_id == account_id, AccountAccess.user_id == access_user_id)
        .first()
    )
    if access is None:
        raise NotFoundError("Shared access not found")

    db.delete(access)
    db.commit()
