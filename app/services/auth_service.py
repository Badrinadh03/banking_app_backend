import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_access_token, hash_password, normalize_phone, verify_password
from app.exceptions import BadRequestError, ForbiddenError, TooManyRequestsError
from app.models.login_event import LoginEvent
from app.models.otp_code import OtpCode
from app.models.user import User
from app.schemas.user import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    SettingsUpdate,
    UserCreate,
    UserUpdate,
)
from app.services import email_service, identity_document_service, zipcode_service

OTP_TTL_MINUTES = 5
OTP_RESEND_COOLDOWN_SECONDS = 45
OTP_MAX_ATTEMPTS = 5
OTP_MAX_REQUESTS_PER_WINDOW = 5
OTP_REQUEST_WINDOW_MINUTES = 15


def _resolve_user_by_identifier(db: Session, identifier: str) -> User | None:
    normalized_phone = normalize_phone(identifier)
    return (
        db.query(User)
        .filter(or_(User.email == identifier, User.phone_number == normalized_phone))
        .first()
    )


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*" * max(len(local) - 1, 1)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _mask_phone(phone: str) -> str:
    digits = phone[-4:] if len(phone) >= 4 else phone
    return f"•••• {digits}"


def create_user(
    db: Session,
    user_in: UserCreate,
    document_type: str,
    front_image_bytes: bytes,
    front_image_content_type: str,
    back_image_bytes: bytes | None = None,
    back_image_content_type: str | None = None,
) -> User:
    existing_email = db.query(User).filter(User.email == user_in.email).first()
    if existing_email is not None:
        raise BadRequestError("A user with this email already exists")

    existing_phone = db.query(User).filter(User.phone_number == user_in.phone_number).first()
    if existing_phone is not None:
        raise BadRequestError("A user with this phone number already exists")

    zip_result = zipcode_service.lookup_zip_code(user_in.zip_code)
    if zip_result["service_available"] and not zip_result["found"]:
        raise BadRequestError("That doesn't look like a real US zip code")

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        phone_number=user_in.phone_number,
        date_of_birth=user_in.date_of_birth,
        government_id_last4=user_in.government_id_last4,
        address=user_in.address,
        employer_name=user_in.employer_name,
        annual_income=user_in.annual_income,
        is_verified=False,
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    identity_document_service.save(
        db,
        user,
        document_type,
        front_image_bytes,
        front_image_content_type,
        back_image_bytes,
        back_image_content_type,
    )

    db.commit()
    db.refresh(user)
    return user


def update_profile(db: Session, user: User, update_in: UserUpdate) -> User:
    updates = update_in.model_dump(exclude_unset=True)

    zip_code = updates.pop("zip_code", None)
    otp_channel = updates.pop("otp_channel", None)
    otp_code = updates.pop("otp_code", None)

    if zip_code:
        result = zipcode_service.lookup_zip_code(zip_code)
        if result["service_available"] and not result["found"]:
            raise BadRequestError("That doesn't look like a real US zip code")

    if "government_id_last4" in updates and user.government_id_last4:
        if updates["government_id_last4"] != user.government_id_last4:
            raise BadRequestError(
                "Government ID can't be changed once it's on file. Contact support if it needs to be corrected."
            )
        updates.pop("government_id_last4")

    if updates.get("phone_number"):
        normalized = normalize_phone(updates["phone_number"])
        existing = (
            db.query(User).filter(User.phone_number == normalized, User.id != user.id).first()
        )
        if existing is not None:
            raise BadRequestError("A user with this phone number already exists")
        updates["phone_number"] = normalized

    if "email" in updates:
        if updates["email"] == user.email:
            updates.pop("email")
        else:
            if not otp_code:
                raise BadRequestError("A verification code is required to change your email address")
            consume_step_up_code(db, user, otp_channel or "email", otp_code)
            existing = (
                db.query(User).filter(User.email == updates["email"], User.id != user.id).first()
            )
            if existing is not None:
                raise BadRequestError("A user with this email already exists")

    for field, value in updates.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def update_settings(db: Session, user: User, settings_in: SettingsUpdate) -> User:
    user.remember_device = settings_in.remember_device
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, change_in: ChangePasswordRequest) -> User:
    if not verify_password(change_in.current_password, user.hashed_password):
        raise BadRequestError("Current password is incorrect")

    user.hashed_password = hash_password(change_in.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def change_email(db: Session, user: User, change_in: ChangeEmailRequest) -> User:
    if not verify_password(change_in.current_password, user.hashed_password):
        raise BadRequestError("Current password is incorrect")

    existing = db.query(User).filter(User.email == change_in.new_email, User.id != user.id).first()
    if existing is not None:
        raise BadRequestError("A user with this email already exists")

    user.email = change_in.new_email
    db.commit()
    db.refresh(user)
    return user


def record_login_event(
    db: Session, user: User, ip_address: str | None, user_agent: str | None
) -> LoginEvent:
    event = LoginEvent(user_id=user.id, ip_address=ip_address, user_agent=user_agent)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_login_history(db: Session, user: User, limit: int = 20) -> list[LoginEvent]:
    return (
        db.query(LoginEvent)
        .filter(LoginEvent.user_id == user.id)
        .order_by(LoginEvent.created_at.desc())
        .limit(limit)
        .all()
    )


def _issue_session_token(
    db: Session, user: User, ip_address: str | None, user_agent: str | None
) -> str:
    if not user.is_verified:
        raise ForbiddenError("Please verify your account before logging in")

    record_login_event(db, user, ip_address, user_agent)

    expire_minutes = (
        settings.jwt_remember_device_expire_minutes if user.remember_device else None
    )
    return create_access_token(subject=str(user.id), expire_minutes=expire_minutes)


def authenticate_user(db: Session, identifier: str, password: str) -> User:
    user = _resolve_user_by_identifier(db, identifier)
    if user is None or not verify_password(password, user.hashed_password):
        raise BadRequestError("Incorrect credentials")
    return user


def login(
    db: Session,
    identifier: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    user = authenticate_user(db, identifier, password)
    return _issue_session_token(db, user, ip_address, user_agent)


def request_otp(db: Session, identifier: str, channel: str) -> dict:
    user = _resolve_user_by_identifier(db, identifier)
    if user is None:
        raise BadRequestError("No account found for that identifier")
    if channel == "phone" and not user.phone_number:
        raise BadRequestError("No phone number on file for this account")

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=OTP_REQUEST_WINDOW_MINUTES)
    recent = (
        db.query(OtpCode)
        .filter(
            OtpCode.user_id == user.id,
            OtpCode.channel == channel,
            OtpCode.created_at >= window_start,
        )
        .order_by(OtpCode.created_at.desc())
        .all()
    )
    if recent and (now - recent[0].created_at.replace(tzinfo=timezone.utc)).total_seconds() < (
        OTP_RESEND_COOLDOWN_SECONDS
    ):
        raise TooManyRequestsError("Please wait before requesting another code")
    if len(recent) >= OTP_MAX_REQUESTS_PER_WINDOW:
        raise TooManyRequestsError("Too many code requests. Try again later.")

    # Invalidate any still-live code so verify_otp never has to reason about
    # which of several valid codes is "the" one.
    db.query(OtpCode).filter(
        OtpCode.user_id == user.id, OtpCode.channel == channel, OtpCode.consumed_at.is_(None)
    ).update({"consumed_at": now})

    code = f"{secrets.randbelow(1_000_000):06d}"
    otp = OtpCode(
        user_id=user.id,
        channel=channel,
        code_hash=hash_password(code),
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(otp)
    db.commit()

    if channel == "email":
        delivered, _ = email_service.send_email(
            user.email, "Your Northline Bank login code", f"Your one-time code is {code}. It expires in 5 minutes."
        )
        masked = _mask_email(user.email)
    else:
        delivered = False  # no real SMS provider configured — always simulated
        masked = _mask_phone(user.phone_number)

    return {"channel": channel, "masked_target": masked, "demo_code": None if delivered else code}


def _consume_otp(db: Session, identifier: str, channel: str, code: str) -> User:
    user = _resolve_user_by_identifier(db, identifier)
    if user is None:
        raise BadRequestError("Incorrect code")

    otp = (
        db.query(OtpCode)
        .filter(
            OtpCode.user_id == user.id,
            OtpCode.channel == channel,
            OtpCode.consumed_at.is_(None),
        )
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if otp is None or otp.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise BadRequestError("Code expired or not found. Request a new one.")
    if otp.attempt_count >= OTP_MAX_ATTEMPTS:
        raise TooManyRequestsError("Too many attempts. Request a new code.")

    if not verify_password(code, otp.code_hash):
        otp.attempt_count += 1
        db.commit()
        raise BadRequestError("Incorrect code")

    otp.consumed_at = datetime.now(timezone.utc)
    db.commit()
    return user


def consume_step_up_code(db: Session, user: User, channel: str, code: str) -> None:
    """Confirms a sensitive action (Zelle/Bill Pay/external transfer) with a
    one-time code sent to the current user's own email or phone — reuses
    the same OTP mechanics as login/verification/reset, just scoped to a
    known user instead of resolving an identifier."""
    identifier = user.email if channel == "email" else user.phone_number
    if channel == "phone" and not identifier:
        raise BadRequestError("No phone number on file for this account")
    _consume_otp(db, identifier, channel, code)


def verify_otp(
    db: Session,
    identifier: str,
    channel: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    user = _consume_otp(db, identifier, channel, code)

    # Successfully proving ownership of a channel always implies the
    # account is verified, whether this call was a login or a dedicated
    # verify-account flow.
    if not user.is_verified:
        user.is_verified = True
        db.commit()

    return _issue_session_token(db, user, ip_address, user_agent)


def verify_account(db: Session, identifier: str, channel: str, code: str) -> None:
    user = _consume_otp(db, identifier, channel, code)
    if not user.is_verified:
        user.is_verified = True
        db.commit()


def reset_password(
    db: Session, identifier: str, channel: str, code: str, new_password: str
) -> None:
    user = _consume_otp(db, identifier, channel, code)
    user.hashed_password = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
