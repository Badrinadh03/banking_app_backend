from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.exceptions import BadRequestError
from app.models.user import User
from app.services import account_service, statement_service

router = APIRouter(prefix="/statements", tags=["statements"])

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _period_label(start: date, end: date) -> str:
    if start.day == 1 and start.year == end.year and start.month == end.month:
        return f"{MONTH_NAMES[start.month - 1]} {start.year}"
    return f"{start.isoformat()} to {end.isoformat()}"


@router.get("/download")
def download_statement(
    account_id: int | None = None,
    start: date = Query(...),
    end: date = Query(...),
    format: Literal["pdf", "csv"] = "pdf",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if end < start:
        raise BadRequestError("End date must be after start date")

    account = (
        account_service.get_account_for_user(db, current_user, account_id)
        if account_id is not None
        else None
    )
    transactions = statement_service.get_statement_transactions(
        db, current_user, account_id, start, end
    )
    period_label = _period_label(start, end)

    if format == "pdf":
        content = statement_service.generate_statement_pdf(
            current_user, account, transactions, period_label
        )
        media_type = "application/pdf"
    else:
        content = statement_service.generate_statement_csv(
            current_user, account, transactions, period_label
        )
        media_type = "text/csv"

    account_slug = account.account_type if account else "all-accounts"
    filename = f"northline-statement-{account_slug}-{start.isoformat()}-to-{end.isoformat()}.{format}"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
