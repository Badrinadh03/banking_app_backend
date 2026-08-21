import secrets

from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.account import Account
from app.models.account_access import AccountAccess
from app.models.user import User


def _generate_account_number() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(10))


def create_account(
    db: Session,
    user: User,
    account_type: str,
    address: str | None = None,
    government_id_last4: str | None = None,
) -> Account:
    if address:
        user.address = address
    if government_id_last4:
        user.government_id_last4 = government_id_last4
    if address or government_id_last4:
        db.commit()

    if not user.address:
        raise BadRequestError("Add your mailing address before opening an account")
    if not user.government_id_last4:
        raise BadRequestError(
            "Add the last 4 digits of a government ID before opening an account"
        )

    account_number = _generate_account_number()
    while db.query(Account).filter(Account.account_number == account_number).first():
        account_number = _generate_account_number()

    account = Account(user_id=user.id, account_number=account_number, account_type=account_type)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_accounts(db: Session, user: User) -> list[Account]:
    accessible_ids = get_accessible_account_ids(db, user)
    if not accessible_ids:
        return []
    return db.query(Account).filter(Account.id.in_(accessible_ids)).order_by(Account.id).all()


def user_can_access_account(db: Session, user: User, account: Account) -> bool:
    """True for the account's owner, or a user who's been granted joint
    access to it — the single check every money-movement/card/statement
    path should go through instead of comparing account.user_id directly."""
    if account.user_id == user.id:
        return True
    return (
        db.query(AccountAccess)
        .filter(AccountAccess.account_id == account.id, AccountAccess.user_id == user.id)
        .first()
        is not None
    )


def get_accessible_account_ids(db: Session, user: User) -> list[int]:
    """All account ids the user can act on: their own plus any granted
    joint access."""
    owned_ids = [a.id for a in db.query(Account.id).filter(Account.user_id == user.id)]
    shared_ids = [
        a.account_id for a in db.query(AccountAccess.account_id).filter(AccountAccess.user_id == user.id)
    ]
    return list(set(owned_ids) | set(shared_ids))


def get_account_for_user(db: Session, user: User, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    if not user_can_access_account(db, user, account):
        raise ForbiddenError("You do not have access to this account")
    return account


def close_account(db: Session, user: User, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    if account.user_id != user.id:
        raise ForbiddenError("Only the account owner can close it")
    if account.status == "closed":
        raise BadRequestError("This account is already closed")
    if account.balance != 0:
        raise BadRequestError("Account balance must be $0 before it can be closed")

    account.status = "closed"
    db.commit()
    db.refresh(account)
    return account
