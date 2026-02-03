"""add swatch_data and swatch_url to wall_texture_variants

Revision ID: a1b2c3swatch
Revises: f5g6h7i8j9k0
Create Date: 2026-02-03 12:00:00.000000

Adds swatch_data (Text) and swatch_url (String) columns to wall_texture_variants
so the AI visualization can use the actual texture swatch pattern instead of
room showcase photos.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3swatch"
down_revision: Union[str, Sequence[str], None] = "f5g6h7i8j9k0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add swatch_data and swatch_url columns to wall_texture_variants."""
    op.add_column("wall_texture_variants", sa.Column("swatch_data", sa.Text(), nullable=True))
    op.add_column("wall_texture_variants", sa.Column("swatch_url", sa.String(500), nullable=True))


def downgrade() -> None:
    """Remove swatch_data and swatch_url columns from wall_texture_variants."""
    op.drop_column("wall_texture_variants", "swatch_url")
    op.drop_column("wall_texture_variants", "swatch_data")
