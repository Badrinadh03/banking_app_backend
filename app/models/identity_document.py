from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# MySQL's default LargeBinary is BLOB (64KB max) — too small for a photo.
# LONGBLOB is MySQL-specific, so it's only swapped in on that dialect; other
# dialects (e.g. SQLite in tests) fall back to their own native unbounded
# binary type.
_IMAGE_BLOB = LargeBinary().with_variant(LONGBLOB(), "mysql")


class IdentityDocument(Base):
    __tablename__ = "identity_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    front_image: Mapped[bytes] = mapped_column(_IMAGE_BLOB, nullable=False)
    front_content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    back_image: Mapped[bytes | None] = mapped_column(_IMAGE_BLOB, nullable=True)
    back_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="identity_documents")
