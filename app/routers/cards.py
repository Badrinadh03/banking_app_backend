from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.card import CardIssueIn, CardRead, CardRevealIn, CardRevealOut, WalletLinkIn
from app.services import card_service

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=list[CardRead])
def list_cards(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return card_service.list_cards(db, current_user)


@router.post("", response_model=CardRead, status_code=status.HTTP_201_CREATED)
def issue_card(
    card_in: CardIssueIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return card_service.issue_card(
        db, current_user, card_in.account_id, card_in.otp_channel, card_in.otp_code
    )


@router.post("/{card_id}/reveal", response_model=CardRevealOut)
def reveal_card(
    card_id: int,
    reveal_in: CardRevealIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return card_service.reveal_card(
        db, current_user, card_id, reveal_in.otp_channel, reveal_in.otp_code
    )


@router.post("/{card_id}/freeze", response_model=CardRead)
def freeze_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return card_service.freeze_card(db, current_user, card_id)


@router.post("/{card_id}/unfreeze", response_model=CardRead)
def unfreeze_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return card_service.unfreeze_card(db, current_user, card_id)


@router.post("/{card_id}/wallet", response_model=CardRead)
def link_wallet(
    card_id: int,
    wallet_in: WalletLinkIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return card_service.link_wallet(db, current_user, card_id, wallet_in.provider)
