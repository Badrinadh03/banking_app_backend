"""add bill pay enrollment, payees, zelle requests

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("bill_pay_enrolled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("bill_pay_enrolled_at", sa.DateTime(), nullable=True))

    op.create_table(
        "payees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("payee_type", sa.String(length=10), nullable=False),
        sa.Column("pay_method", sa.String(length=10), nullable=False),
        sa.Column("nickname", sa.String(length=100), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("account_number", sa.String(length=34), nullable=True),
        sa.Column("zip_code", sa.String(length=10), nullable=True),
        sa.Column("recipient_name", sa.String(length=255), nullable=True),
        sa.Column("mailing_address", sa.String(length=500), nullable=True),
        sa.Column("contact_identifier", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_payees_user_id", "payees", ["user_id"])

    op.create_table(
        "zelle_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "requester_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_identifier", sa.String(length=255), nullable=False),
        sa.Column(
            "matched_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_zelle_requests_requester_user_id", "zelle_requests", ["requester_user_id"])
    op.create_index("ix_zelle_requests_matched_user_id", "zelle_requests", ["matched_user_id"])
    op.create_index("ix_zelle_requests_created_at", "zelle_requests", ["created_at"])

    op.add_column("transactions", sa.Column("zelle_contact", sa.String(length=255), nullable=True))
    op.add_column(
        "transactions",
        sa.Column(
            "payee_id", sa.Integer(), sa.ForeignKey("payees.id", ondelete="SET NULL"), nullable=True
        ),
    )
    op.create_index("ix_transactions_payee_id", "transactions", ["payee_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_payee_id", table_name="transactions")
    op.drop_column("transactions", "payee_id")
    op.drop_column("transactions", "zelle_contact")

    op.drop_index("ix_zelle_requests_created_at", table_name="zelle_requests")
    op.drop_index("ix_zelle_requests_matched_user_id", table_name="zelle_requests")
    op.drop_index("ix_zelle_requests_requester_user_id", table_name="zelle_requests")
    op.drop_table("zelle_requests")

    op.drop_index("ix_payees_user_id", table_name="payees")
    op.drop_table("payees")

    op.drop_column("users", "bill_pay_enrolled_at")
    op.drop_column("users", "bill_pay_enrolled")
