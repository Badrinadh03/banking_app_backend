from sqlalchemy.orm import Session

from app.constants import BANK_ROUTING_NUMBER_ELECTRONIC
from app.models.account import Account
from app.models.notification import Notification
from app.models.transaction import Transaction
from app.models.user import User
from app.services import email_service


def _build_sender_message(
    transaction: Transaction, from_account: Account | None, to_account: Account | None
) -> str:
    amount = f"${transaction.amount:.2f}"

    if transaction.transaction_type == "deposit":
        return (
            f"A deposit of {amount} to account ending {to_account.account_number[-4:]} "
            f"(routing {BANK_ROUTING_NUMBER_ELECTRONIC}) was completed."
        )

    if transaction.transaction_type == "external_transfer":
        return (
            f"A transfer of {amount} from account ending {from_account.account_number[-4:]} "
            f"(routing {BANK_ROUTING_NUMBER_ELECTRONIC}) to {transaction.external_recipient_name}'s "
            f"account ending {transaction.external_account_number[-4:]} "
            f"(routing {transaction.external_routing_number}) was completed."
        )

    if transaction.transaction_type == "bill_payment":
        payee_label = transaction.payee.nickname if transaction.payee else "your payee"
        return (
            f"A bill payment of {amount} from account ending {from_account.account_number[-4:]} "
            f"to {payee_label} was completed."
        )

    if transaction.transaction_type == "zelle_payment":
        if to_account is not None:
            return (
                f"A Zelle payment of {amount} from account ending {from_account.account_number[-4:]} "
                f"to {transaction.zelle_contact} was completed."
            )
        return (
            f"A Zelle payment of {amount} from account ending {from_account.account_number[-4:]} "
            f"to {transaction.zelle_contact} was sent."
        )

    return (
        f"A transfer of {amount} from account ending {from_account.account_number[-4:]} to "
        f"account ending {to_account.account_number[-4:]} "
        f"(routing {BANK_ROUTING_NUMBER_ELECTRONIC}) was completed."
    )


def _build_recipient_message(
    transaction: Transaction, from_account: Account, to_account: Account
) -> str:
    amount = f"${transaction.amount:.2f}"
    return (
        f"You received a transfer of {amount} to account ending {to_account.account_number[-4:]} "
        f"from account ending {from_account.account_number[-4:]} "
        f"(routing {BANK_ROUTING_NUMBER_ELECTRONIC})."
    )


def _notify_user(
    db: Session, user: User, message: str, transaction: Transaction | None = None
) -> list[Notification]:
    delivered, delivery_error = email_service.send_email(
        user.email, "Banking App transaction notification", message
    )
    transaction_id = transaction.id if transaction is not None else None

    notifications = [
        Notification(
            user_id=user.id,
            transaction_id=transaction_id,
            channel="email",
            recipient=user.email,
            message=message,
            delivered=delivered,
            delivery_error=delivery_error,
        )
    ]
    if user.phone_number:
        notifications.append(
            Notification(
                user_id=user.id,
                transaction_id=transaction_id,
                channel="sms",
                recipient=user.phone_number,
                message=message,
            )
        )

    db.add_all(notifications)
    db.commit()
    return notifications


def record_transaction_notifications(
    db: Session,
    user: User,
    transaction: Transaction,
    from_account: Account | None,
    to_account: Account | None,
) -> list[Notification]:
    message = _build_sender_message(transaction, from_account, to_account)
    return _notify_user(db, user, message, transaction=transaction)


def record_incoming_transfer_notification(
    db: Session,
    recipient_user: User,
    transaction: Transaction,
    from_account: Account,
    to_account: Account,
) -> list[Notification]:
    message = _build_recipient_message(transaction, from_account, to_account)
    return _notify_user(db, recipient_user, message, transaction=transaction)


def record_general_notification(db: Session, user: User, message: str) -> list[Notification]:
    """For notifications not tied to a completed Transaction, e.g. a
    declined Zelle request."""
    return _notify_user(db, user, message)


def get_notifications(db: Session, user: User, limit: int = 50) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
