from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageRead
from app.services import assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/messages", response_model=list[ChatMessageRead])
def list_messages(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return assistant_service.list_for_user(db, current_user)


@router.post("/messages", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
def send_message(
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return assistant_service.send_message(db, current_user, payload.content)


@router.delete("/messages", status_code=status.HTTP_204_NO_CONTENT)
def clear_messages(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    assistant_service.clear_for_user(db, current_user)
