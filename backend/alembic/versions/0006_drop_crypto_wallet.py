"""drop crypto_wallet from users

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-08

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "crypto_wallet")


def downgrade() -> None:
    op.add_column("users", sa.Column("crypto_wallet", sa.String(255), nullable=True))
