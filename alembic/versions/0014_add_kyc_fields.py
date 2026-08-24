"""add kyc fields to users and identity_documents table

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("employer_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("annual_income", sa.Numeric(12, 2), nullable=True))

    op.create_table(
        "identity_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("front_image", mysql.LONGBLOB(), nullable=False),
        sa.Column("front_content_type", sa.String(length=50), nullable=False),
        sa.Column("back_image", mysql.LONGBLOB(), nullable=True),
        sa.Column("back_content_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_identity_documents_user_id", "identity_documents", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_identity_documents_user_id", table_name="identity_documents")
    op.drop_table("identity_documents")
    op.drop_column("users", "annual_income")
    op.drop_column("users", "employer_name")
    op.drop_column("users", "date_of_birth")
