"""add yoomoney_wallet to users

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("yoomoney_wallet", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "yoomoney_wallet")
