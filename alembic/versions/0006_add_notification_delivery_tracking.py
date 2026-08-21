"""add delivered/delivery_error tracking to notifications

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("notifications", sa.Column("delivery_error", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("notifications", "delivery_error")
    op.drop_column("notifications", "delivered")
