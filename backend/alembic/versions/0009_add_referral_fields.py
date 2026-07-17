"""add referral fields to users

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referred_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("users", sa.Column("referral_bonuses", sa.Integer(), server_default="0", nullable=False))
    op.create_index(op.f("ix_users_referred_by"), "users", ["referred_by"])


def downgrade() -> None:
    op.drop_index(op.f("ix_users_referred_by"), table_name="users")
    op.drop_column("users", "referral_bonuses")
    op.drop_column("users", "referred_by")
