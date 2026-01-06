"""add_budget_tier_to_curated_looks

Revision ID: a75e7a12d020
Revises: 72c81130317d
Create Date: 2026-01-05 13:10:12.941764

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "a75e7a12d020"
down_revision: Union[str, Sequence[str], None] = "72c81130317d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - idempotent (safe to run multiple times)."""
    conn = op.get_bind()
    inspector = inspect(conn)

    # Create the enum type if it doesn't exist
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE budgettier AS ENUM ('pocket_friendly', 'mid_tier', 'premium', 'luxury');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # Check if column already exists
    columns = [col['name'] for col in inspector.get_columns('curated_looks')]

    if 'budget_tier' not in columns:
        # Add the column using the enum
        budgettier_enum = sa.Enum("pocket_friendly", "mid_tier", "premium", "luxury", name="budgettier", create_type=False)
        op.add_column("curated_looks", sa.Column("budget_tier", budgettier_enum, nullable=True))

        # Create index if it doesn't exist
        try:
            op.create_index(op.f("ix_curated_looks_budget_tier"), "curated_looks", ["budget_tier"], unique=False)
        except Exception:
            pass  # Index might already exist


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)

    columns = [col['name'] for col in inspector.get_columns('curated_looks')]

    if 'budget_tier' in columns:
        op.drop_index(op.f("ix_curated_looks_budget_tier"), table_name="curated_looks")
        op.drop_column("curated_looks", "budget_tier")

    # Drop the enum type
    budgettier_enum = sa.Enum("pocket_friendly", "mid_tier", "premium", "luxury", name="budgettier")
    budgettier_enum.drop(op.get_bind(), checkfirst=True)
