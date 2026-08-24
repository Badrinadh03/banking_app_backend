from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    government_id_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(nullable=True)
    employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    annual_income: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bill_pay_enrolled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bill_pay_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remember_device: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primary_contact_method: Mapped[str] = mapped_column(String(20), nullable=False, default="phone")
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    login_events = relationship(
        "LoginEvent", back_populates="user", cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    otp_codes = relationship("OtpCode", back_populates="user", cascade="all, delete-orphan")
    payees = relationship("Payee", back_populates="user", cascade="all, delete-orphan")
    zelle_requests_sent = relationship(
        "ZelleRequest",
        back_populates="requester",
        foreign_keys="ZelleRequest.requester_user_id",
        cascade="all, delete-orphan",
    )
    recurring_payments = relationship(
        "RecurringPayment", back_populates="user", cascade="all, delete-orphan"
    )
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    savings_goals = relationship(
        "SavingsGoal", back_populates="user", cascade="all, delete-orphan"
    )
    beneficiaries = relationship(
        "Beneficiary", back_populates="user", cascade="all, delete-orphan"
    )
    check_deposits = relationship(
        "CheckDeposit", back_populates="user", cascade="all, delete-orphan"
    )
    fraud_alerts = relationship(
        "FraudAlert", back_populates="user", cascade="all, delete-orphan"
    )
    chat_messages = relationship(
        "ChatMessage", back_populates="user", cascade="all, delete-orphan"
    )
    identity_documents = relationship(
        "IdentityDocument", back_populates="user", cascade="all, delete-orphan"
    )
