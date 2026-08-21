from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    to_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False, default="transfer")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_account_number: Mapped[str | None] = mapped_column(String(34), nullable=True)
    external_routing_number: Mapped[str | None] = mapped_column(String(9), nullable=True)
    external_bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zelle_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_id: Mapped[int | None] = mapped_column(
        ForeignKey("payees.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    from_account = relationship(
        "Account", foreign_keys=[from_account_id], back_populates="sent_transactions"
    )
    to_account = relationship(
        "Account", foreign_keys=[to_account_id], back_populates="received_transactions"
    )
    payee = relationship("Payee")
