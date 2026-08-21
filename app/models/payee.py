from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Payee(Base):
    __tablename__ = "payees"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    payee_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "company" | "person"
    pay_method: Mapped[str] = mapped_column(String(10), nullable=False)  # "bill_pay" | "zelle"
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)

    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(34), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mailing_address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    contact_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="payees")
