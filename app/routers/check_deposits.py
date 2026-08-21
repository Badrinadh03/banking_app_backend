from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.exceptions import BadRequestError
from app.models.user import User
from app.schemas.check_deposit import CheckDepositRead
from app.services import check_deposit_service

router = APIRouter(prefix="/check-deposits", tags=["check-deposits"])

ALLOWED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


async def _read_image(upload: UploadFile) -> tuple[bytes, str]:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError("Check images must be JPEG, PNG, or WebP")
    content = await upload.read()
    if not content:
        raise BadRequestError("Uploaded image is empty")
    return content, ALLOWED_CONTENT_TYPES[upload.content_type]


@router.post("", response_model=CheckDepositRead, status_code=status.HTTP_201_CREATED)
async def submit_check_deposit(
    account_id: int = Form(...),
    amount: Decimal = Form(...),
    front_image: UploadFile = File(...),
    back_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    front_bytes, front_ext = await _read_image(front_image)
    back_bytes, back_ext = await _read_image(back_image)
    return check_deposit_service.submit(
        db, current_user, account_id, amount, front_bytes, front_ext, back_bytes, back_ext
    )


@router.get("", response_model=list[CheckDepositRead])
def list_check_deposits(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return check_deposit_service.list_for_user(db, current_user)


@router.get("/{check_deposit_id}/image/{side}")
def get_check_deposit_image(
    check_deposit_id: int,
    side: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if side not in {"front", "back"}:
        raise BadRequestError("side must be 'front' or 'back'")
    path: Path = check_deposit_service.get_image_path(db, current_user, check_deposit_id, side)
    return FileResponse(path)
