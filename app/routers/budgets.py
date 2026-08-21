from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetProgress, BudgetRead
from app.services import budget_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.post("", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return budget_service.create(db, current_user, payload.category, payload.monthly_limit)


@router.get("", response_model=list[BudgetRead])
def list_budgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return budget_service.list_for_user(db, current_user)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget_service.delete(db, current_user, budget_id)


@router.get("/progress", response_model=list[BudgetProgress])
def get_progress(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return budget_service.get_progress(db, current_user, year, month)
