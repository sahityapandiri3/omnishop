"""change budget_tier from enum to varchar

Revision ID: b8c31a3ae707
Revises: b8d4e5f6a7c9
Create Date: 2026-01-07 19:35:42.728103

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c31a3ae707"
down_revision: Union[str, Sequence[str], None] = "b8d4e5f6a7c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Change budget_tier column from native PostgreSQL enum to VARCHAR(20).
    This fixes asyncpg compatibility issues with enum types.
    """
    # Change the column type from enum to varchar, casting existing values
    op.execute(
        """
        ALTER TABLE curated_looks
        ALTER COLUMN budget_tier TYPE VARCHAR(20)
        USING budget_tier::text
    """
    )

    # Also change it in stores table if it exists there
    op.execute(
        """
        ALTER TABLE stores
        ALTER COLUMN budget_tier TYPE VARCHAR(20)
        USING budget_tier::text
    """
    )

    # Drop the enum type since we're no longer using it
    op.execute("DROP TYPE IF EXISTS budgettier")


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate the enum type
    op.execute(
        """
        CREATE TYPE budgettier AS ENUM ('pocket_friendly', 'mid_tier', 'premium', 'luxury')
    """
    )

    # Change column back to enum
    op.execute(
        """
        ALTER TABLE curated_looks
        ALTER COLUMN budget_tier TYPE budgettier
        USING budget_tier::budgettier
    """
    )

    op.execute(
        """
        ALTER TABLE stores
        ALTER COLUMN budget_tier TYPE budgettier
        USING budget_tier::budgettier
    """
    )
