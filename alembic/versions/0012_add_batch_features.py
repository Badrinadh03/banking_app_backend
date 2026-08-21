"""add recurring payments, budgets, savings goals, joint account access,
account closure, beneficiaries, check deposits, fraud alerts

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("status", sa.String(length=10), nullable=False, server_default="active"),
    )

    op.create_table(
        "account_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_account_access_account_id", "account_access", ["account_id"])
    op.create_index("ix_account_access_user_id", "account_access", ["user_id"])

    op.create_table(
        "recurring_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "from_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("payment_type", sa.String(length=10), nullable=False),
        sa.Column(
            "to_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "payee_id", sa.Integer(), sa.ForeignKey("payees.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("zelle_contact", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_recurring_payments_user_id", "recurring_payments", ["user_id"])
    op.create_index("ix_recurring_payments_next_run_date", "recurring_payments", ["next_run_date"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])

    op.create_table(
        "savings_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_savings_goals_user_id", "savings_goals", ["user_id"])

    op.create_table(
        "beneficiaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("relationship_label", sa.String(length=50), nullable=False),
        sa.Column("allocation_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_beneficiaries_user_id", "beneficiaries", ["user_id"])

    op.create_table(
        "check_deposits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("front_image_path", sa.String(length=255), nullable=False),
        sa.Column("back_image_path", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="pending"),
        sa.Column("hold_release_at", sa.DateTime(), nullable=False),
        sa.Column(
            "cleared_transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_check_deposits_user_id", "check_deposits", ["user_id"])
    op.create_index("ix_check_deposits_created_at", "check_deposits", ["created_at"])

    op.create_table(
        "fraud_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rule", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_fraud_alerts_user_id", "fraud_alerts", ["user_id"])
    op.create_index("ix_fraud_alerts_created_at", "fraud_alerts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_fraud_alerts_created_at", table_name="fraud_alerts")
    op.drop_index("ix_fraud_alerts_user_id", table_name="fraud_alerts")
    op.drop_table("fraud_alerts")

    op.drop_index("ix_check_deposits_created_at", table_name="check_deposits")
    op.drop_index("ix_check_deposits_user_id", table_name="check_deposits")
    op.drop_table("check_deposits")

    op.drop_index("ix_beneficiaries_user_id", table_name="beneficiaries")
    op.drop_table("beneficiaries")

    op.drop_index("ix_savings_goals_user_id", table_name="savings_goals")
    op.drop_table("savings_goals")

    op.drop_index("ix_budgets_user_id", table_name="budgets")
    op.drop_table("budgets")

    op.drop_index("ix_recurring_payments_next_run_date", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_user_id", table_name="recurring_payments")
    op.drop_table("recurring_payments")

    op.drop_index("ix_account_access_user_id", table_name="account_access")
    op.drop_index("ix_account_access_account_id", table_name="account_access")
    op.drop_table("account_access")

    op.drop_column("accounts", "status")
