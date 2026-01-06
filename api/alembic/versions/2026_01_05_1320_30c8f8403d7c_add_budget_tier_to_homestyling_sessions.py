"""add_budget_tier_to_homestyling_sessions

Revision ID: 30c8f8403d7c
Revises: a75e7a12d020
Create Date: 2026-01-05 13:20:32.184838

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "30c8f8403d7c"
down_revision: Union[str, Sequence[str], None] = "a75e7a12d020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - idempotent (safe to run multiple times)."""
    conn = op.get_bind()
    inspector = inspect(conn)

    # Check if column already exists
    columns = [col['name'] for col in inspector.get_columns('homestyling_sessions')]

    if 'budget_tier' not in columns:
        # Use existing budgettier enum (created in previous migration)
        budgettier_enum = sa.Enum("pocket_friendly", "mid_tier", "premium", "luxury", name="budgettier", create_type=False)
        op.add_column("homestyling_sessions", sa.Column("budget_tier", budgettier_enum, nullable=True))

        # Create index if it doesn't exist
        try:
            op.create_index(op.f("ix_homestyling_sessions_budget_tier"), "homestyling_sessions", ["budget_tier"], unique=False)
        except Exception:
            pass  # Index might already exist


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)

    columns = [col['name'] for col in inspector.get_columns('homestyling_sessions')]

    if 'budget_tier' in columns:
        op.drop_index(op.f("ix_homestyling_sessions_budget_tier"), table_name="homestyling_sessions")
        op.drop_column("homestyling_sessions", "budget_tier")
