"""add_curated_look_id_to_precomputed_masks

Revision ID: 72c81130317d
Revises: 369950a2002b
Create Date: 2025-12-31 01:45:32.914883

NOTE: This migration is skipped - precomputed_masks table is not used (SAM disabled).
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "72c81130317d"
down_revision: Union[str, Sequence[str], None] = "369950a2002b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Skip - precomputed_masks table not needed (SAM disabled)."""
    pass


def downgrade() -> None:
    """Skip - precomputed_masks table not needed (SAM disabled)."""
    pass
