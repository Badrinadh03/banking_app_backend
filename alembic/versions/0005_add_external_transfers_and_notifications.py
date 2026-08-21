"""add external transfer fields to transactions, add notifications table

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("external_recipient_name", sa.String(length=255), nullable=True))
    op.add_column("transactions", sa.Column("external_account_number", sa.String(length=34), nullable=True))
    op.add_column("transactions", sa.Column("external_routing_number", sa.String(length=9), nullable=True))
    op.add_column("transactions", sa.Column("external_bank_name", sa.String(length=255), nullable=True))

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(length=10), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_transaction_id", "notifications", ["transaction_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_column("transactions", "external_bank_name")
    op.drop_column("transactions", "external_routing_number")
    op.drop_column("transactions", "external_account_number")
    op.drop_column("transactions", "external_recipient_name")
