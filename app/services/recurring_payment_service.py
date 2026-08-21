import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, NotFoundError
from app.models.recurring_payment import RecurringPayment
from app.models.user import User
from app.services import account_service, billpay_service, notification_service, transfer_service, zelle_service


def _advance_date(d: date, frequency: str) -> date:
    if frequency == "weekly":
        return d + timedelta(days=7)
    month = d.month + 1
    year = d.year
    if month > 12:
        month = 1
        year += 1
    last_day_of_month = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day_of_month))


def create(db: Session, user: User, payload) -> RecurringPayment:
    account = account_service.get_account_for_user(db, user, payload.from_account_id)
    if payload.to_account_id:
        account_service.get_account_for_user(db, user, payload.to_account_id)

    recurring = RecurringPayment(
        user_id=user.id,
        from_account_id=account.id,
        payment_type=payload.payment_type,
        to_account_id=payload.to_account_id,
        payee_id=payload.payee_id,
        zelle_contact=payload.zelle_contact,
        amount=payload.amount,
        description=payload.description,
        frequency=payload.frequency,
        next_run_date=payload.next_run_date,
    )
    db.add(recurring)
    db.commit()
    db.refresh(recurring)
    return recurring


def list_for_user(db: Session, user: User) -> list[RecurringPayment]:
    return (
        db.query(RecurringPayment)
        .filter(RecurringPayment.user_id == user.id)
        .order_by(RecurringPayment.next_run_date)
        .all()
    )


def cancel(db: Session, user: User, recurring_id: int) -> RecurringPayment:
    recurring = db.get(RecurringPayment, recurring_id)
    if recurring is None or recurring.user_id != user.id:
        raise NotFoundError("Recurring payment not found")
    recurring.is_active = False
    db.commit()
    db.refresh(recurring)
    return recurring


def process_due_payments(db: Session) -> int:
    """Executes every active recurring payment whose next_run_date has
    arrived, reusing the exact same money-movement logic real user-initiated
    payments use. Called by the scheduler, not by any request. A failure
    (e.g. insufficient funds) skips that payment for this cycle rather than
    retrying — it'll be attempted again on its next scheduled date."""
    today = date.today()
    due = (
        db.query(RecurringPayment)
        .filter(RecurringPayment.is_active.is_(True), RecurringPayment.next_run_date <= today)
        .all()
    )

    processed = 0
    for recurring in due:
        user = db.get(User, recurring.user_id)
        try:
            if recurring.payment_type == "transfer":
                transfer_service.execute_transfer(
                    db, user, recurring.from_account_id, recurring.to_account_id,
                    recurring.amount, recurring.description,
                )
            elif recurring.payment_type == "bill_pay":
                billpay_service.execute_bill_payment(
                    db, user, recurring.from_account_id, recurring.payee_id,
                    recurring.amount, recurring.description,
                )
            else:  # zelle
                zelle_service.execute_zelle_payment(
                    db, user, recurring.from_account_id, recurring.zelle_contact,
                    recurring.amount, recurring.description,
                )
            recurring.next_run_date = _advance_date(recurring.next_run_date, recurring.frequency)
            recurring.last_run_at = datetime.now(timezone.utc)
            db.commit()
            processed += 1
        except (BadRequestError, NotFoundError) as exc:
            db.rollback()
            notification_service.record_general_notification(
                db, user,
                f"Your recurring payment of ${recurring.amount:.2f} couldn't be completed: {exc.detail}",
            )
    return processed
