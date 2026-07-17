"""create initial tables (users, territories, notifications)

Revision ID: 0001
Revises: 
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


revision: str = "0001"
down_revision: Union[str, None] = None
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
    if not table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("username", sa.String(100), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("captures_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_premium", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("stripe_customer_id", sa.String(255), nullable=True),
            sa.Column("crypto_wallet", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )

    if not table_exists("territories"):
        op.create_table(
            "territories",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False, server_default="Безымянный"),
            sa.Column("polygon", Geometry("GEOMETRY", srid=4326), nullable=False),
            sa.Column("area", sa.Float(), nullable=False),
            sa.Column("closures_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("parts_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("source", sa.String(50), nullable=False, server_default="gpx"),
            sa.Column("color", sa.String(7), nullable=False, server_default="#4CAF50"),
            sa.Column("image_url", sa.String(500), nullable=True),
            sa.Column("description", sa.String(1000), nullable=True),
            sa.Column("link_url", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_territories_user_id", "territories", ["user_id"])
        op.create_index("ix_territories_polygon", "territories", ["polygon"], postgresql_using="gist")
        op.create_index("ix_territories_created_at", "territories", ["created_at"])

    if not table_exists("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("message", sa.String(500), nullable=False),
            sa.Column("territory_id", sa.UUID(), nullable=True),
            sa.Column("read", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["territory_id"], ["territories.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_notifications_user_id_read", "notifications", ["user_id", "read"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id_read", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_territories_created_at", table_name="territories")
    op.drop_index("ix_territories_polygon", table_name="territories")
    op.drop_index("ix_territories_user_id", table_name="territories")
    op.drop_table("territories")
    op.drop_table("users")
