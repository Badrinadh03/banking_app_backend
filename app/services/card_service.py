import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.card_crypto import decrypt_value, encrypt_value
from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.debit_card import DebitCard
from app.models.user import User
from app.services import account_service, auth_service

ELIGIBLE_ACCOUNT_TYPES = {"checking", "savings"}
CARD_VALIDITY_YEARS = 4


def _luhn_check_digit(digits: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return str((10 - (total % 10)) % 10)


def _generate_card_number() -> str:
    # Visa-style prefix purely for a realistic look — this is a simulated
    # card, not tied to any real payment network or issuer BIN.
    body = "4" + "".join(str(secrets.randbelow(10)) for _ in range(14))
    return body + _luhn_check_digit(body)


def _generate_cvv() -> str:
    return f"{secrets.randbelow(1000):03d}"


def issue_card(
    db: Session, user: User, account_id: int, otp_channel: str, otp_code: str
) -> DebitCard:
    account = account_service.get_account_for_user(db, user, account_id)
    if account.account_type not in ELIGIBLE_ACCOUNT_TYPES:
        raise BadRequestError("Only checking and savings accounts are eligible for a debit card")
    if db.query(DebitCard).filter(DebitCard.account_id == account.id).first() is not None:
        raise BadRequestError("This account already has a debit card")

    auth_service.consume_step_up_code(db, user, otp_channel, otp_code)

    card_number = _generate_card_number()
    now = datetime.now(timezone.utc)
    expiry = now.replace(year=now.year + CARD_VALIDITY_YEARS)

    card = DebitCard(
        account_id=account.id,
        user_id=user.id,
        cardholder_name=user.full_name,
        last4=card_number[-4:],
        encrypted_number=encrypt_value(card_number),
        encrypted_cvv=encrypt_value(_generate_cvv()),
        expiry_month=expiry.month,
        expiry_year=expiry.year,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def list_cards(db: Session, user: User) -> list[DebitCard]:
    account_ids = account_service.get_accessible_account_ids(db, user)
    if not account_ids:
        return []
    return (
        db.query(DebitCard)
        .filter(DebitCard.account_id.in_(account_ids))
        .order_by(DebitCard.id)
        .all()
    )


def get_card_for_user(db: Session, user: User, card_id: int) -> DebitCard:
    card = db.get(DebitCard, card_id)
    if card is None:
        raise NotFoundError("Card not found")
    if not account_service.user_can_access_account(db, user, card.account):
        raise ForbiddenError("You do not have access to this card")
    return card


def reveal_card(db: Session, user: User, card_id: int, otp_channel: str, otp_code: str) -> dict:
    card = get_card_for_user(db, user, card_id)
    auth_service.consume_step_up_code(db, user, otp_channel, otp_code)
    return {
        "card_number": decrypt_value(card.encrypted_number),
        "cvv": decrypt_value(card.encrypted_cvv),
        "expiry_month": card.expiry_month,
        "expiry_year": card.expiry_year,
        "cardholder_name": card.cardholder_name,
    }


def freeze_card(db: Session, user: User, card_id: int) -> DebitCard:
    card = get_card_for_user(db, user, card_id)
    card.status = "frozen"
    db.commit()
    db.refresh(card)
    return card


def unfreeze_card(db: Session, user: User, card_id: int) -> DebitCard:
    card = get_card_for_user(db, user, card_id)
    card.status = "active"
    db.commit()
    db.refresh(card)
    return card


def link_wallet(db: Session, user: User, card_id: int, provider: str) -> DebitCard:
    card = get_card_for_user(db, user, card_id)
    if card.status == "frozen":
        raise BadRequestError("Unfreeze the card before linking it to a wallet")
    if provider == "apple":
        card.apple_wallet_linked = True
    else:
        card.google_wallet_linked = True
    db.commit()
    db.refresh(card)
    return card
