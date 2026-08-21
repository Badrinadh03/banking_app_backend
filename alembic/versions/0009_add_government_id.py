"""add government_id_last4 to users

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("government_id_last4", sa.String(length=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "government_id_last4")
