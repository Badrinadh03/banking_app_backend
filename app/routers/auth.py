from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import (
    LoginRequest,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    ResetPasswordIn,
    ResetPasswordOut,
    Token,
    VerifyAccountOut,
)
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    return auth_service.create_user(db, user_in)


@router.post("/login", response_model=Token)
def login(credentials: LoginRequest, request: Request, db: Session = Depends(get_db)):
    access_token = auth_service.login(
        db,
        credentials.identifier,
        credentials.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Token(access_token=access_token)


@router.post("/otp/request", response_model=OtpRequestOut)
def request_otp(payload: OtpRequestIn, db: Session = Depends(get_db)):
    return auth_service.request_otp(db, payload.identifier, payload.channel)


@router.post("/otp/verify", response_model=Token)
def verify_otp(payload: OtpVerifyIn, request: Request, db: Session = Depends(get_db)):
    access_token = auth_service.verify_otp(
        db,
        payload.identifier,
        payload.channel,
        payload.code,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Token(access_token=access_token)


@router.post("/verify-account", response_model=VerifyAccountOut)
def verify_account(payload: OtpVerifyIn, db: Session = Depends(get_db)):
    auth_service.verify_account(db, payload.identifier, payload.channel, payload.code)
    return VerifyAccountOut(verified=True)


@router.post("/reset-password", response_model=ResetPasswordOut)
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)):
    auth_service.reset_password(
        db, payload.identifier, payload.channel, payload.code, payload.new_password
    )
    return ResetPasswordOut(reset=True)
