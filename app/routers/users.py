from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    LoginEventRead,
    SettingsUpdate,
    UserRead,
    UserUpdate,
)
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserRead)
def update_me(
    update_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return auth_service.update_profile(db, current_user, update_in)


@router.patch("/me/settings", response_model=UserRead)
def update_settings(
    settings_in: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return auth_service.update_settings(db, current_user, settings_in)


@router.post("/me/change-password", response_model=UserRead)
def change_password(
    change_in: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return auth_service.change_password(db, current_user, change_in)


@router.post("/me/change-email", response_model=UserRead)
def change_email(
    change_in: ChangeEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return auth_service.change_email(db, current_user, change_in)


@router.get("/me/login-history", response_model=list[LoginEventRead])
def login_history(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return auth_service.get_login_history(db, current_user)
