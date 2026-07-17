"""add crypto_wallet to users

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'crypto_wallet'"
        )
    )
    if result.scalar() is None:
        op.add_column("users", sa.Column("crypto_wallet", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "crypto_wallet")
