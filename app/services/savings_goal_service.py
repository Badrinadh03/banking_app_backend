from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.savings_goal import SavingsGoal
from app.models.user import User
from app.services import account_service


def create(
    db: Session, user: User, account_id: int, name: str, target_amount: Decimal, target_date: date | None
) -> SavingsGoal:
    account_service.get_account_for_user(db, user, account_id)
    goal = SavingsGoal(
        user_id=user.id, account_id=account_id, name=name,
        target_amount=target_amount, target_date=target_date,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def list_for_user(db: Session, user: User) -> list[SavingsGoal]:
    return (
        db.query(SavingsGoal).filter(SavingsGoal.user_id == user.id).order_by(SavingsGoal.created_at).all()
    )


def delete(db: Session, user: User, goal_id: int) -> None:
    goal = db.get(SavingsGoal, goal_id)
    if goal is None or goal.user_id != user.id:
        raise NotFoundError("Savings goal not found")
    db.delete(goal)
    db.commit()


def to_progress_dict(goal: SavingsGoal) -> dict:
    """Progress is never stored — always computed live from the linked
    account's real balance, so it can never drift out of sync."""
    balance = goal.account.balance
    percent = float(min(balance / goal.target_amount, 1) * 100) if goal.target_amount else 0.0
    return {
        "id": goal.id,
        "account_id": goal.account_id,
        "name": goal.name,
        "target_amount": goal.target_amount,
        "target_date": goal.target_date,
        "current_balance": balance,
        "percent_complete": percent,
        "created_at": goal.created_at,
    }
