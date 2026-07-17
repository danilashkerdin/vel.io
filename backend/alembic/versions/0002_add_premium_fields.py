"""add premium fields to users

Revision ID: 0002
Revises: 
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if not column_exists("users", "captures_count"):
        op.add_column("users", sa.Column("captures_count", sa.Integer(), nullable=False, server_default="0"))
    if not column_exists("users", "is_premium"):
        op.add_column("users", sa.Column("is_premium", sa.Boolean(), nullable=False, server_default="false"))
    if not column_exists("users", "stripe_customer_id"):
        op.add_column("users", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("users", "is_premium")
    op.drop_column("users", "captures_count")
