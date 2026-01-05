"""add_curated_look_id_to_precomputed_masks

Revision ID: 72c81130317d
Revises: 369950a2002b
Create Date: 2025-12-31 01:45:32.914883

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72c81130317d"
down_revision: Union[str, Sequence[str], None] = "369950a2002b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Adds support for curated looks in precomputed_masks table:
    - Makes session_id nullable (was required before)
    - Adds curated_look_id column with FK to curated_looks
    - Adds index for curated look lookups
    """
    # Make session_id nullable to support curated looks (which don't have sessions)
    op.alter_column("precomputed_masks", "session_id", existing_type=sa.String(length=36), nullable=True)

    # Add curated_look_id column
    op.add_column("precomputed_masks", sa.Column("curated_look_id", sa.Integer(), nullable=True))

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_precomputed_masks_curated_look_id", "precomputed_masks", "curated_looks", ["curated_look_id"], ["id"]
    )

    # Add index for curated look lookups
    op.create_index(
        "idx_precomputed_mask_curated_viz", "precomputed_masks", ["curated_look_id", "visualization_hash"], unique=False
    )

    # Add individual index on curated_look_id
    op.create_index("ix_precomputed_masks_curated_look_id", "precomputed_masks", ["curated_look_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index("ix_precomputed_masks_curated_look_id", table_name="precomputed_masks")
    op.drop_index("idx_precomputed_mask_curated_viz", table_name="precomputed_masks")

    # Drop foreign key
    op.drop_constraint("fk_precomputed_masks_curated_look_id", "precomputed_masks", type_="foreignkey")

    # Drop column
    op.drop_column("precomputed_masks", "curated_look_id")

    # Make session_id required again
    op.alter_column("precomputed_masks", "session_id", existing_type=sa.String(length=36), nullable=False)
