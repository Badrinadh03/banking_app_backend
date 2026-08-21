from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions import BadRequestError
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.services import account_service, auth_service, fraud_service, notification_service, payee_service


def enroll(db: Session, user: User) -> User:
    user.bill_pay_enrolled = True
    user.bill_pay_enrolled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def pay_bill(
    db: Session,
    user: User,
    from_account_id: int,
    payee_id: int,
    amount: Decimal,
    description: str | None,
    otp_channel: str,
    otp_code: str,
) -> Transaction:
    auth_service.consume_step_up_code(db, user, otp_channel, otp_code)
    return execute_bill_payment(db, user, from_account_id, payee_id, amount, description)


def execute_bill_payment(
    db: Session,
    user: User,
    from_account_id: int,
    payee_id: int,
    amount: Decimal,
    description: str | None,
) -> Transaction:
    """The actual bill-payment logic, with no OTP gate — used both by the
    user-facing `pay_bill` (after step-up) and by recurring payments, which
    have no live user present to enter a code (already authorized for real
    when the recurring payment was set up)."""
    if not user.bill_pay_enrolled:
        raise BadRequestError("Enroll in Bill Pay before making a payment")
    if amount <= 0:
        raise BadRequestError("Amount must be greater than zero")

    payee = payee_service.get_payee_for_user(db, user, payee_id)
    if payee.pay_method != "bill_pay":
        raise BadRequestError("This payee is paid via Zelle, not Bill Pay")

    account = db.query(Account).filter(Account.id == from_account_id).with_for_update().first()
    if account is None:
        raise BadRequestError("Account not found")
    if not account_service.user_can_access_account(db, user, account):
        raise BadRequestError("You do not have access to this account")
    if account.balance < amount:
        raise BadRequestError("Insufficient funds")

    account.balance -= amount

    label = payee.company_name or payee.recipient_name or payee.nickname
    transaction = Transaction(
        from_account_id=account.id,
        to_account_id=None,
        amount=amount,
        transaction_type="bill_payment",
        status="completed",
        description=description or f"Bill payment to {label}",
        payee_id=payee.id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    notification_service.record_transaction_notifications(db, user, transaction, account, None)
    fraud_service.evaluate_transaction(db, user, transaction)

    return transaction


def get_activity(db: Session, user: User) -> list[Transaction]:
    account_ids = account_service.get_accessible_account_ids(db, user)
    if not account_ids:
        return []
    return (
        db.query(Transaction)
        .filter(
            Transaction.transaction_type == "bill_payment",
            Transaction.from_account_id.in_(account_ids),
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )
