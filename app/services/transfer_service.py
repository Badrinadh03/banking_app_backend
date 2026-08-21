from decimal import Decimal

from sqlalchemy.orm import Session

from app.constants import BANK_ROUTING_NUMBER_ELECTRONIC
from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.services import account_service, auth_service, fraud_service, notification_service


def execute_transfer(
    db: Session,
    user: User,
    from_account_id: int,
    to_account_id: int,
    amount: Decimal,
    description: str | None,
) -> Transaction:
    if from_account_id == to_account_id:
        raise BadRequestError("Source and destination accounts must be different")
    if amount <= 0:
        raise BadRequestError("Amount must be greater than zero")

    # Lock accounts in a consistent order (ascending id) to avoid deadlocks
    # between concurrent transfers involving the same pair of accounts.
    ordered_ids = sorted([from_account_id, to_account_id])
    locked_accounts = (
        db.query(Account)
        .filter(Account.id.in_(ordered_ids))
        .order_by(Account.id)
        .with_for_update()
        .all()
    )
    accounts_by_id = {account.id: account for account in locked_accounts}

    from_account = accounts_by_id.get(from_account_id)
    to_account = accounts_by_id.get(to_account_id)

    if from_account is None or to_account is None:
        raise NotFoundError("One or both accounts were not found")
    if not account_service.user_can_access_account(db, user, from_account):
        raise ForbiddenError("You do not have access to the source account")
    if from_account.balance < amount:
        raise BadRequestError("Insufficient funds")

    from_account.balance -= amount
    to_account.balance += amount

    transaction = Transaction(
        from_account_id=from_account.id,
        to_account_id=to_account.id,
        amount=amount,
        transaction_type="transfer",
        status="completed",
        description=description,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    notification_service.record_transaction_notifications(db, user, transaction, from_account, to_account)
    fraud_service.evaluate_transaction(db, user, transaction)

    return transaction


def execute_external_transfer(
    db: Session,
    user: User,
    from_account_id: int,
    amount: Decimal,
    description: str | None,
    recipient_name: str,
    external_account_number: str,
    external_routing_number: str,
    external_bank_name: str | None,
    otp_channel: str,
    otp_code: str,
) -> Transaction:
    if amount <= 0:
        raise BadRequestError("Amount must be greater than zero")
    auth_service.consume_step_up_code(db, user, otp_channel, otp_code)

    # If the routing number matches our own bank and the account number is
    # real, this "external" transfer is actually to another account at the
    # same bank — credit it for real instead of just simulating a debit.
    matched_account_id = None
    if external_routing_number == BANK_ROUTING_NUMBER_ELECTRONIC:
        matched = (
            db.query(Account).filter(Account.account_number == external_account_number).first()
        )
        if matched is not None and matched.id != from_account_id:
            matched_account_id = matched.id

    if matched_account_id is not None:
        # Lock both accounts in a consistent order to avoid deadlocks,
        # same as an internal transfer.
        ordered_ids = sorted([from_account_id, matched_account_id])
        locked_accounts = (
            db.query(Account)
            .filter(Account.id.in_(ordered_ids))
            .order_by(Account.id)
            .with_for_update()
            .all()
        )
        accounts_by_id = {account.id: account for account in locked_accounts}
        from_account = accounts_by_id.get(from_account_id)
        to_account = accounts_by_id.get(matched_account_id)
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
        transaction_type="external_transfer",
        status="completed",
        description=description,
        external_recipient_name=recipient_name,
        external_account_number=external_account_number,
        external_routing_number=external_routing_number,
        external_bank_name=external_bank_name,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    notification_service.record_transaction_notifications(db, user, transaction, from_account, to_account)
    if to_account is not None:
        notification_service.record_incoming_transfer_notification(
            db, to_account.user, transaction, from_account, to_account
        )
    fraud_service.evaluate_transaction(db, user, transaction)

    return transaction


def execute_deposit(
    db: Session,
    user: User,
    account_id: int,
    amount: Decimal,
    description: str | None,
) -> Transaction:
    if amount <= 0:
        raise BadRequestError("Amount must be greater than zero")

    account = db.query(Account).filter(Account.id == account_id).with_for_update().first()
    if account is None:
        raise NotFoundError("Account not found")
    if not account_service.user_can_access_account(db, user, account):
        raise ForbiddenError("You do not have access to this account")

    account.balance += amount

    transaction = Transaction(
        from_account_id=None,
        to_account_id=account.id,
        amount=amount,
        transaction_type="deposit",
        status="completed",
        description=description,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    notification_service.record_transaction_notifications(db, user, transaction, None, account)

    return transaction


def get_all_transactions_for_user(db: Session, user: User) -> list[Transaction]:
    account_ids = account_service.get_accessible_account_ids(db, user)
    if not account_ids:
        return []

    return (
        db.query(Transaction)
        .filter(
            (Transaction.from_account_id.in_(account_ids))
            | (Transaction.to_account_id.in_(account_ids))
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )


def get_transaction_history(db: Session, user: User, account_id: int) -> list[Transaction]:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    if not account_service.user_can_access_account(db, user, account):
        raise ForbiddenError("You do not have access to this account")

    return (
        db.query(Transaction)
        .filter(
            (Transaction.from_account_id == account_id)
            | (Transaction.to_account_id == account_id)
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )
