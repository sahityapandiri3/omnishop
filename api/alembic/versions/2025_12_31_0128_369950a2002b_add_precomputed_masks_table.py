"""add_precomputed_masks_table

Revision ID: 369950a2002b
Revises: cda9e2c70800
Create Date: 2025-12-31 01:28:03.387525

NOTE: This migration is skipped - precomputed_masks table is not used (SAM disabled).
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '369950a2002b'
down_revision: Union[str, Sequence[str], None] = 'cda9e2c70800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Skip - precomputed_masks table not needed (SAM disabled)."""
    pass


def downgrade() -> None:
    """Skip - precomputed_masks table not needed (SAM disabled)."""
    pass
