"""add phone_number and address to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("address", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "address")
    op.drop_column("users", "phone_number")
