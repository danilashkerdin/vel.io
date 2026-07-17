"""add sponsored territories, user balance, transactions

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT to_regclass(:name)"),
        {"name": name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if not table_exists("sponsored_territories"):
        op.create_table(
            "sponsored_territories",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("business_name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("polygon", Geometry("GEOMETRY", srid=4326), nullable=False),
            sa.Column("monthly_budget_rub", sa.Integer(), nullable=False, server_default="5000"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("image_url", sa.String(500), nullable=True),
            sa.Column("link_url", sa.String(500), nullable=True),
            sa.Column("color", sa.String(7), nullable=False, server_default="#FFD700"),
            sa.Column("current_owner_id", sa.UUID(), nullable=True),
            sa.Column("owned_since", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["current_owner_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sponsored_polygon", "sponsored_territories", ["polygon"], postgresql_using="gist")

    if not table_exists("user_balances"):
        op.create_table(
            "user_balances",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("balance_rub", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_earned_rub", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )

    if not table_exists("transactions"):
        op.create_table(
            "transactions",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("amount_rub", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("sponsored_territory_id", sa.UUID(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="completed"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sponsored_territory_id"], ["sponsored_territories.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
        op.create_index("ix_transactions_created_at", "transactions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_created_at", table_name="transactions")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("user_balances")
    op.drop_index("ix_sponsored_polygon", table_name="sponsored_territories")
    op.drop_table("sponsored_territories")
