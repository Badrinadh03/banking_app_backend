"""add primary_contact_method to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "primary_contact_method", sa.String(length=20), nullable=False, server_default="phone"
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "primary_contact_method")
