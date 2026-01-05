"""add_budget_tier_to_curated_looks

Revision ID: a75e7a12d020
Revises: 72c81130317d
Create Date: 2026-01-05 13:10:12.941764

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a75e7a12d020"
down_revision: Union[str, Sequence[str], None] = "72c81130317d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type first
    budgettier_enum = sa.Enum("essential", "value", "mid", "premium", "ultra_luxury", name="budgettier")
    budgettier_enum.create(op.get_bind(), checkfirst=True)

    # Add the column
    op.add_column("curated_looks", sa.Column("budget_tier", budgettier_enum, nullable=True))
    op.create_index(op.f("ix_curated_looks_budget_tier"), "curated_looks", ["budget_tier"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_curated_looks_budget_tier"), table_name="curated_looks")
    op.drop_column("curated_looks", "budget_tier")

    # Drop the enum type
    budgettier_enum = sa.Enum("essential", "value", "mid", "premium", "ultra_luxury", name="budgettier")
    budgettier_enum.drop(op.get_bind(), checkfirst=True)
