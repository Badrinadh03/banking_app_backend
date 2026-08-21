from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.budget import Budget
from app.models.user import User
from app.services import transfer_service


def create(db: Session, user: User, category: str, monthly_limit: Decimal) -> Budget:
    budget = Budget(user_id=user.id, category=category, monthly_limit=monthly_limit)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def list_for_user(db: Session, user: User) -> list[Budget]:
    return db.query(Budget).filter(Budget.user_id == user.id).order_by(Budget.created_at).all()


def delete(db: Session, user: User, budget_id: int) -> None:
    budget = db.get(Budget, budget_id)
    if budget is None or budget.user_id != user.id:
        raise NotFoundError("Budget not found")
    db.delete(budget)
    db.commit()


def get_progress(db: Session, user: User, year: int, month: int) -> list[dict]:
    """Spend per budget = this-month transactions whose description
    contains the budget's category (case-insensitive substring match) —
    the same "match by description text" convention already used by
    SpendingPage's category breakdown, not a real transaction-category
    system."""
    budgets = list_for_user(db, user)
    if not budgets:
        return []

    transactions = transfer_service.get_all_transactions_for_user(db, user)
    month_spend_by_description = [
        tx for tx in transactions
        if tx.created_at.year == year
        and tx.created_at.month == month
        and tx.transaction_type != "deposit"
    ]

    results = []
    for budget in budgets:
        category_lower = budget.category.lower()
        spent = sum(
            (tx.amount for tx in month_spend_by_description
             if tx.description and category_lower in tx.description.lower()),
            Decimal("0"),
        )
        remaining = budget.monthly_limit - spent
        percent_used = float(spent / budget.monthly_limit * 100) if budget.monthly_limit else 0.0
        results.append(
            {"budget": budget, "spent": spent, "remaining": remaining, "percent_used": percent_used}
        )
    return results
