"""add_subscription_tier_to_users

Revision ID: c2d3e4f5g6h7
Revises: fb1cd2a025d2
Create Date: 2026-01-19 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5g6h7"
down_revision: Union[str, Sequence[str], None] = "fb1cd2a025d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_exists(conn, enum_name: str) -> bool:
    """Check if an enum type exists in PostgreSQL."""
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": enum_name}
    )
    return result.fetchone() is not None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add subscription_tier column to users table."""
    conn = op.get_bind()

    # Create the enum type if it doesn't exist
    if not _enum_exists(conn, "subscriptiontier"):
        subscriptiontier = sa.Enum("free", "build_your_own", name="subscriptiontier")
        subscriptiontier.create(conn, checkfirst=True)

    # Add the column if it doesn't exist
    if not _column_exists(conn, "users", "subscription_tier"):
        op.add_column(
            "users",
            sa.Column(
                "subscription_tier",
                sa.Enum("free", "build_your_own", name="subscriptiontier", create_type=False),
                nullable=False,
                server_default="free",
            ),
        )
        op.create_index(
            op.f("ix_users_subscription_tier"),
            "users",
            ["subscription_tier"],
            unique=False,
        )


def downgrade() -> None:
    """Remove subscription_tier column from users table."""
    conn = op.get_bind()

    if _column_exists(conn, "users", "subscription_tier"):
        op.drop_index(op.f("ix_users_subscription_tier"), table_name="users")
        op.drop_column("users", "subscription_tier")
