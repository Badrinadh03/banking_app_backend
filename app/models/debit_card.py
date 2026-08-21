from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DebitCard(Base):
    __tablename__ = "debit_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    cardholder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    # Full number/CVV are symmetrically encrypted (not one-way hashed) since
    # the owning user must be able to view them again after a step-up check.
    encrypted_number: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_cvv: Mapped[str] = mapped_column(String(255), nullable=False)
    expiry_month: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    apple_wallet_linked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    google_wallet_linked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account = relationship("Account", back_populates="debit_card")
