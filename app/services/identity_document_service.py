from sqlalchemy.orm import Session

from app.exceptions import ForbiddenError, NotFoundError
from app.models.identity_document import IdentityDocument
from app.models.user import User

ALLOWED_DOCUMENT_TYPES = {"drivers_license", "passport", "state_id"}


def save(
    db: Session,
    user: User,
    document_type: str,
    front_bytes: bytes,
    front_content_type: str,
    back_bytes: bytes | None,
    back_content_type: str | None,
) -> IdentityDocument:
    document = IdentityDocument(
        user_id=user.id,
        document_type=document_type,
        front_image=front_bytes,
        front_content_type=front_content_type,
        back_image=back_bytes,
        back_content_type=back_content_type,
    )
    db.add(document)
    db.flush()
    return document


def get_image(db: Session, user: User, side: str) -> tuple[bytes, str]:
    document = (
        db.query(IdentityDocument)
        .filter(IdentityDocument.user_id == user.id)
        .order_by(IdentityDocument.created_at.desc())
        .first()
    )
    if document is None:
        raise NotFoundError("No identity document on file")
    if document.user_id != user.id:
        raise ForbiddenError("You do not have access to this document")

    if side == "front":
        return document.front_image, document.front_content_type
    if document.back_image is None or document.back_content_type is None:
        raise NotFoundError("This document has no back image")
    return document.back_image, document.back_content_type
