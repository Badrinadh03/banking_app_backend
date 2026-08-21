from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.fraud_alert import FraudAlert
from app.models.transaction import Transaction
from app.models.user import User
from app.services import notification_service

LARGE_AMOUNT_THRESHOLD = Decimal("2000")
RAPID_ACTIVITY_WINDOW = timedelta(minutes=10)
RAPID_ACTIVITY_THRESHOLD = 4


def evaluate_transaction(db: Session, user: User, transaction: Transaction) -> list[FraudAlert]:
    """Two simple, real rule checks — not AI/ML, just thresholds — run
    after a money-movement transaction is already committed. Alerts are
    informational, not blocking: nothing about the transaction that already
    happened changes."""
    alerts: list[FraudAlert] = []

    if transaction.amount >= LARGE_AMOUNT_THRESHOLD:
        alerts.append(
            _create_alert(
                db, user, transaction, "large_transaction",
                f"A transaction of ${transaction.amount:.2f} is larger than your usual activity.",
            )
        )

    if transaction.from_account_id is not None:
        window_start = datetime.now(timezone.utc) - RAPID_ACTIVITY_WINDOW
        recent_count = (
            db.query(Transaction)
            .filter(
                Transaction.from_account_id == transaction.from_account_id,
                Transaction.created_at >= window_start,
            )
            .count()
        )
        if recent_count >= RAPID_ACTIVITY_THRESHOLD:
            alerts.append(
                _create_alert(
                    db, user, transaction, "rapid_activity",
                    f"{recent_count} outgoing transactions from the same account in the last "
                    f"{int(RAPID_ACTIVITY_WINDOW.total_seconds() // 60)} minutes.",
                )
            )

    return alerts


def _create_alert(
    db: Session, user: User, transaction: Transaction, rule: str, message: str
) -> FraudAlert:
    alert = FraudAlert(user_id=user.id, transaction_id=transaction.id, rule=rule, message=message)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    notification_service.record_general_notification(db, user, f"Security alert: {message}")
    return alert


def list_for_user(db: Session, user: User) -> list[FraudAlert]:
    return (
        db.query(FraudAlert)
        .filter(FraudAlert.user_id == user.id)
        .order_by(FraudAlert.created_at.desc())
        .all()
    )


def acknowledge(db: Session, user: User, alert_id: int) -> FraudAlert:
    alert = db.get(FraudAlert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise NotFoundError("Fraud alert not found")
    alert.acknowledged = True
    db.commit()
    db.refresh(alert)
    return alert
