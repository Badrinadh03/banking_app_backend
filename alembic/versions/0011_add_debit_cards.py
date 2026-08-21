"""add debit_cards table

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "debit_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("cardholder_name", sa.String(length=255), nullable=False),
        sa.Column("last4", sa.String(length=4), nullable=False),
        sa.Column("encrypted_number", sa.String(length=255), nullable=False),
        sa.Column("encrypted_cvv", sa.String(length=255), nullable=False),
        sa.Column("expiry_month", sa.Integer(), nullable=False),
        sa.Column("expiry_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="active"),
        sa.Column("apple_wallet_linked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("google_wallet_linked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_debit_cards_account_id", "debit_cards", ["account_id"])
    op.create_index("ix_debit_cards_user_id", "debit_cards", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_debit_cards_user_id", table_name="debit_cards")
    op.drop_index("ix_debit_cards_account_id", table_name="debit_cards")
    op.drop_table("debit_cards")
