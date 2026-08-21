from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.account import AccountCreate, AccountRead
from app.schemas.account_access import AccountAccessCreate, AccountAccessRead
from app.schemas.transaction import DepositCreate, TransactionRead
from app.services import account_access_service, account_service, transfer_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _to_account_read(account, user: User) -> AccountRead:
    return AccountRead(
        id=account.id,
        account_number=account.account_number,
        account_type=account.account_type,
        balance=account.balance,
        status=account.status,
        is_owner=account.user_id == user.id,
        created_at=account.created_at,
    )


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(
    account_in: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = account_service.create_account(
        db,
        current_user,
        account_in.account_type,
        address=account_in.address,
        government_id_last4=account_in.government_id_last4,
    )
    if account_in.initial_deposit:
        transfer_service.execute_deposit(
            db, current_user, account.id, account_in.initial_deposit, "Account opening deposit"
        )
        db.refresh(account)
    return _to_account_read(account, current_user)


@router.get("", response_model=list[AccountRead])
def list_accounts(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return [_to_account_read(a, current_user) for a in account_service.list_accounts(db, current_user)]


@router.get("/{account_id}", response_model=AccountRead)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = account_service.get_account_for_user(db, current_user, account_id)
    return _to_account_read(account, current_user)


@router.post("/{account_id}/deposit", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def deposit(
    account_id: int,
    deposit_in: DepositCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return transfer_service.execute_deposit(
        db, current_user, account_id, deposit_in.amount, deposit_in.description
    )


@router.get("/{account_id}/transactions", response_model=list[TransactionRead])
def get_transaction_history(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return transfer_service.get_transaction_history(db, current_user, account_id)


@router.post("/{account_id}/close", response_model=AccountRead)
def close_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = account_service.close_account(db, current_user, account_id)
    return _to_account_read(account, current_user)


def _to_access_read(access) -> AccountAccessRead:
    return AccountAccessRead(
        id=access.id,
        account_id=access.account_id,
        user_id=access.user_id,
        user_name=access.user.full_name,
        created_at=access.created_at,
    )


@router.post("/{account_id}/access", response_model=AccountAccessRead, status_code=status.HTTP_201_CREATED)
def grant_access(
    account_id: int,
    payload: AccountAccessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    access = account_access_service.grant_access(
        db, current_user, account_id, payload.contact_identifier
    )
    return _to_access_read(access)


@router.get("/{account_id}/access", response_model=list[AccountAccessRead])
def list_access(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    access_list = account_access_service.list_access(db, current_user, account_id)
    return [_to_access_read(a) for a in access_list]


@router.delete("/{account_id}/access/{access_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_access(
    account_id: int,
    access_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account_access_service.revoke_access(db, current_user, account_id, access_user_id)
