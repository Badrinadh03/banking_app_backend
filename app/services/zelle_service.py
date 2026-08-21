from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import normalize_phone
from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.models.zelle_request import ZelleRequest
from app.services import account_service, auth_service, email_service, fraud_service, notification_service


def _resolve_user_by_contact(db: Session, identifier: str) -> User | None:
    normalized_phone = normalize_phone(identifier)
    return (
        db.query(User)
        .filter(or_(User.email == identifier, User.phone_number == normalized_phone))
        .first()
    )


def pay(
    db: Session,
    user: User,
    from_account_id: int,
    contact_identifier: str,
    amount: Decimal,
    description: str | None,
    otp_channel: str,
    otp_code: str,
) -> Transaction:
    auth_service.consume_step_up_code(db, user, otp_channel, otp_code)
    return execute_zelle_payment(db, user, from_account_id, contact_identifier, amount, description)


def execute_zelle_payment(
    db: Session,
    user: User,
    from_account_id: int,
    contact_identifier: str,
    amount: Decimal,
    description: str | None,
) -> Transaction:
    """The actual Zelle-payment logic, with no OTP gate — used both by the
    user-facing `pay` (after step-up) and by recurring payments, which have
    no live user present to enter a code."""
    if amount <= 0:
        raise BadRequestError("Amount must be greater than zero")

    matched_user = _resolve_user_by_contact(db, contact_identifier)
    matched_account = None
    if matched_user is not None and matched_user.id != user.id:
        matched_account = (
            db.query(Account)
            .filter(Account.user_id == matched_user.id)
            .order_by(Account.id)
            .first()
        )

    if matched_account is not None:
        ordered_ids = sorted([from_account_id, matched_account.id])
        locked_accounts = (
            db.query(Account)
            .filter(Account.id.in_(ordered_ids))
            .order_by(Account.id)
            .with_for_update()
            .all()
        )
        accounts_by_id = {a.id: a for a in locked_accounts}
        from_account = accounts_by_id.get(from_account_id)
        to_account = accounts_by_id.get(matched_account.id)
    else:
        from_account = (
            db.query(Account).filter(Account.id == from_account_id).with_for_update().first()
        )
        to_account = None

    if from_account is None:
        raise NotFoundError("Account not found")
    if not account_service.user_can_access_account(db, user, from_account):
        raise ForbiddenError("You do not have access to this account")
    if from_account.balance < amount:
        raise BadRequestError("Insufficient funds")

    from_account.balance -= amount
    if to_account is not None:
        to_account.balance += amount

    transaction = Transaction(
        from_account_id=from_account.id,
        to_account_id=to_account.id if to_account is not None else None,
        amount=amount,
        transaction_type="zelle_payment",
        status="completed",
        description=description,
        zelle_contact=contact_identifier,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    notification_service.record_transaction_notifications(db, user, transaction, from_account, to_account)
    if to_account is not None:
        notification_service.record_incoming_transfer_notification(
            db, matched_user, transaction, from_account, to_account
        )
    fraud_service.evaluate_transaction(db, user, transaction)

    return transaction


def request(db: Session, user: User, target_identifier: str, amount: Decimal, note: str | None) -> ZelleRequest:
    if amount <= 0:
        raise BadRequestError("Amount must be greater than zero")

    matched_user = _resolve_user_by_contact(db, target_identifier)
    if matched_user is not None and matched_user.id == user.id:
        raise BadRequestError("You can't request money from yourself")

    zelle_request = ZelleRequest(
        requester_user_id=user.id,
        target_identifier=target_identifier,
        matched_user_id=matched_user.id if matched_user else None,
        amount=amount,
        note=note,
    )
    db.add(zelle_request)
    db.commit()
    db.refresh(zelle_request)

    if "@" in target_identifier:
        message = (
            f"{user.full_name} has requested ${amount:.2f} via Zelle on Northline Bank. "
            f"Log in to your account to pay this request."
        )
        email_service.send_email(target_identifier, "You have a Zelle request", message)

    return zelle_request


def list_incoming_requests(db: Session, user: User) -> list[ZelleRequest]:
    return (
        db.query(ZelleRequest)
        .filter(ZelleRequest.matched_user_id == user.id, ZelleRequest.status == "pending")
        .order_by(ZelleRequest.created_at.desc())
        .all()
    )


def pay_request(
    db: Session,
    user: User,
    request_id: int,
    from_account_id: int,
    otp_channel: str,
    otp_code: str,
) -> Transaction:
    zelle_request = db.get(ZelleRequest, request_id)
    if zelle_request is None:
        raise NotFoundError("Request not found")
    if zelle_request.matched_user_id != user.id:
        raise ForbiddenError("You do not have access to this request")
    if zelle_request.status != "pending":
        raise BadRequestError("This request has already been resolved")

    transaction = pay(
        db,
        user,
        from_account_id,
        zelle_request.requester.email,
        zelle_request.amount,
        zelle_request.note or "Zelle request payment",
        otp_channel,
        otp_code,
    )
    zelle_request.status = "paid"
    db.commit()
    return transaction


def decline_request(db: Session, user: User, request_id: int) -> ZelleRequest:
    zelle_request = db.get(ZelleRequest, request_id)
    if zelle_request is None:
        raise NotFoundError("Request not found")
    if zelle_request.matched_user_id != user.id:
        raise ForbiddenError("You do not have access to this request")
    if zelle_request.status != "pending":
        raise BadRequestError("This request has already been resolved")

    zelle_request.status = "declined"
    db.commit()
    db.refresh(zelle_request)

    message = (
        f"{user.full_name} declined your Zelle request for ${zelle_request.amount:.2f}."
    )
    notification_service.record_general_notification(db, zelle_request.requester, message)

    return zelle_request


def get_recent_activity(db: Session, user: User, limit: int = 15) -> list[Transaction]:
    account_ids = account_service.get_accessible_account_ids(db, user)
    if not account_ids:
        return []
    return (
        db.query(Transaction)
        .filter(
            Transaction.transaction_type == "zelle_payment",
            Transaction.from_account_id.in_(account_ids),
        )
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )
