from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import BadRequestError
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
from app.services import auth_service, identity_document_service
from app.utils.uploads import read_image_upload

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    phone_number: str = Form(...),
    date_of_birth: date = Form(...),
    government_id_last4: str = Form(...),
    address: str = Form(...),
    zip_code: str = Form(...),
    employer_name: str | None = Form(None),
    annual_income: Decimal | None = Form(None),
    document_type: str = Form(...),
    id_front_image: UploadFile = File(...),
    id_back_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if document_type not in identity_document_service.ALLOWED_DOCUMENT_TYPES:
        raise BadRequestError("Unsupported document type")

    try:
        user_in = UserCreate(
            email=email,
            password=password,
            full_name=full_name,
            phone_number=phone_number,
            date_of_birth=date_of_birth,
            government_id_last4=government_id_last4,
            address=address,
            zip_code=zip_code,
            employer_name=employer_name,
            annual_income=annual_income,
        )
    except ValidationError as exc:
        raise BadRequestError(exc.errors()[0]["msg"]) from exc

    front_bytes, _ = await read_image_upload(id_front_image)
    front_content_type = id_front_image.content_type

    back_bytes: bytes | None = None
    back_content_type: str | None = None
    if id_back_image is not None:
        back_bytes, _ = await read_image_upload(id_back_image)
        back_content_type = id_back_image.content_type

    return auth_service.create_user(
        db,
        user_in,
        document_type,
        front_bytes,
        front_content_type,
        back_bytes,
        back_content_type,
    )


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
