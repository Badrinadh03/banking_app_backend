from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.savings_goal import SavingsGoalCreate, SavingsGoalRead
from app.services import savings_goal_service

router = APIRouter(prefix="/savings-goals", tags=["savings-goals"])


@router.post("", response_model=SavingsGoalRead, status_code=status.HTTP_201_CREATED)
def create_savings_goal(
    payload: SavingsGoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = savings_goal_service.create(
        db, current_user, payload.account_id, payload.name, payload.target_amount, payload.target_date
    )
    return savings_goal_service.to_progress_dict(goal)


@router.get("", response_model=list[SavingsGoalRead])
def list_savings_goals(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    goals = savings_goal_service.list_for_user(db, current_user)
    return [savings_goal_service.to_progress_dict(g) for g in goals]


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_savings_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    savings_goal_service.delete(db, current_user, goal_id)
