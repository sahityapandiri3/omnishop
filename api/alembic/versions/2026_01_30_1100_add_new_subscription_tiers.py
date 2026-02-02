"""add_new_subscription_tiers

Revision ID: d3e4f5g6h7i8
Revises: c2d3e4f5g6h7
Create Date: 2026-01-30 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5g6h7i8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5g6h7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_value_exists(conn, enum_name: str, value: str) -> bool:
    """Check if a value exists in a PostgreSQL enum type."""
    result = conn.execute(
        sa.text(
            """
            SELECT 1 FROM pg_enum
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = :enum_name)
            AND enumlabel = :value
        """
        ),
        {"enum_name": enum_name, "value": value},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Add new subscription tier values to the enum."""
    conn = op.get_bind()

    # Add new enum values if they don't exist
    new_values = ["basic", "basic_plus", "advanced", "curator", "upgraded"]

    for value in new_values:
        if not _enum_value_exists(conn, "subscriptiontier", value):
            # Use ALTER TYPE to add enum value
            conn.execute(sa.text(f"ALTER TYPE subscriptiontier ADD VALUE IF NOT EXISTS '{value}'"))
            conn.execute(sa.text("COMMIT"))


def downgrade() -> None:
    """
    Note: PostgreSQL doesn't support removing enum values directly.
    To downgrade, you would need to:
    1. Create a new enum without the unwanted values
    2. Update all columns to use the new enum
    3. Drop the old enum and rename the new one

    For simplicity, we leave the enum values in place during downgrade.
    """
    pass
