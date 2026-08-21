import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.account import Account
from app.models.check_deposit import CheckDeposit
from app.models.transaction import Transaction
from app.models.user import User
from app.services import account_service, notification_service

# Real banks hold a mobile check deposit for 1-5 business days before the
# funds are available. Compressed to a couple of minutes here so the hold
# is actually observable in a demo/testing session — the frontend labels
# this as an accelerated demo hold, not real-bank timing.
HOLD_DURATION = timedelta(minutes=2)

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "checks"


def _save_image(content: bytes, extension: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    (UPLOAD_DIR / filename).write_bytes(content)
    return filename


def submit(
    db: Session,
    user: User,
    account_id: int,
    amount: Decimal,
    front_image_bytes: bytes,
    front_image_ext: str,
    back_image_bytes: bytes,
    back_image_ext: str,
) -> CheckDeposit:
    if amount <= 0:
        raise BadRequestError("Amount must be greater than zero")
    account_service.get_account_for_user(db, user, account_id)

    front_path = _save_image(front_image_bytes, front_image_ext)
    back_path = _save_image(back_image_bytes, back_image_ext)

    deposit = CheckDeposit(
        user_id=user.id,
        account_id=account_id,
        amount=amount,
        front_image_path=front_path,
        back_image_path=back_path,
        status="pending",
        hold_release_at=datetime.now(timezone.utc) + HOLD_DURATION,
    )
    db.add(deposit)
    db.commit()
    db.refresh(deposit)
    return deposit


def list_for_user(db: Session, user: User) -> list[CheckDeposit]:
    return (
        db.query(CheckDeposit)
        .filter(CheckDeposit.user_id == user.id)
        .order_by(CheckDeposit.created_at.desc())
        .all()
    )


def get_image_path(db: Session, user: User, check_deposit_id: int, side: str) -> Path:
    deposit = db.get(CheckDeposit, check_deposit_id)
    if deposit is None:
        raise NotFoundError("Check deposit not found")
    if deposit.user_id != user.id:
        raise ForbiddenError("You do not have access to this check deposit")
    filename = deposit.front_image_path if side == "front" else deposit.back_image_path
    return UPLOAD_DIR / filename


def clear_due_holds(db: Session) -> int:
    """Called by the scheduler: for every pending deposit past its release
    time, credits the account for real (same balance-update + notification
    pattern as a normal deposit) and marks it cleared."""
    now = datetime.now(timezone.utc)
    due = (
        db.query(CheckDeposit)
        .filter(CheckDeposit.status == "pending", CheckDeposit.hold_release_at <= now)
        .all()
    )

    cleared = 0
    for deposit in due:
        account = db.query(Account).filter(Account.id == deposit.account_id).with_for_update().first()
        if account is None:
            continue
        user = db.get(User, deposit.user_id)

        account.balance += deposit.amount
        transaction = Transaction(
            from_account_id=None,
            to_account_id=account.id,
            amount=deposit.amount,
            transaction_type="deposit",
            status="completed",
            description="Mobile check deposit",
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        deposit.status = "cleared"
        deposit.cleared_transaction_id = transaction.id
        db.commit()

        notification_service.record_transaction_notifications(db, user, transaction, None, account)
        cleared += 1

    return cleared
