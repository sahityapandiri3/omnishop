"""add_curated_look_id_to_precomputed_masks

Revision ID: 72c81130317d
Revises: 369950a2002b
Create Date: 2025-12-31 01:45:32.914883

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "72c81130317d"
down_revision: Union[str, Sequence[str], None] = "369950a2002b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(conn, index_name: str) -> bool:
    """Check if an index exists."""
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": index_name}
    )
    return result.fetchone() is not None


def _constraint_exists(conn, constraint_name: str) -> bool:
    """Check if a constraint exists."""
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
        {"name": constraint_name}
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Upgrade schema - idempotent (safe to run multiple times).

    Adds support for curated looks in precomputed_masks table:
    - Makes session_id nullable (was required before)
    - Adds curated_look_id column with FK to curated_looks
    - Adds index for curated look lookups
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Skip if precomputed_masks table doesn't exist
    if "precomputed_masks" not in existing_tables:
        return

    columns = [col['name'] for col in inspector.get_columns('precomputed_masks')]

    # Make session_id nullable to support curated looks (which don't have sessions)
    op.alter_column("precomputed_masks", "session_id", existing_type=sa.String(length=36), nullable=True)

    # Add curated_look_id column if it doesn't exist
    if "curated_look_id" not in columns:
        op.add_column("precomputed_masks", sa.Column("curated_look_id", sa.Integer(), nullable=True))

        # Add foreign key constraint if it doesn't exist
        if not _constraint_exists(conn, "fk_precomputed_masks_curated_look_id"):
            op.create_foreign_key(
                "fk_precomputed_masks_curated_look_id", "precomputed_masks", "curated_looks", ["curated_look_id"], ["id"]
            )

        # Add index for curated look lookups
        if not _index_exists(conn, "idx_precomputed_mask_curated_viz"):
            op.create_index(
                "idx_precomputed_mask_curated_viz", "precomputed_masks", ["curated_look_id", "visualization_hash"], unique=False
            )

        # Add individual index on curated_look_id
        if not _index_exists(conn, "ix_precomputed_masks_curated_look_id"):
            op.create_index("ix_precomputed_masks_curated_look_id", "precomputed_masks", ["curated_look_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Skip if precomputed_masks table doesn't exist
    if "precomputed_masks" not in existing_tables:
        return

    columns = [col['name'] for col in inspector.get_columns('precomputed_masks')]

    if "curated_look_id" in columns:
        # Drop indexes
        if _index_exists(conn, "ix_precomputed_masks_curated_look_id"):
            op.drop_index("ix_precomputed_masks_curated_look_id", table_name="precomputed_masks")
        if _index_exists(conn, "idx_precomputed_mask_curated_viz"):
            op.drop_index("idx_precomputed_mask_curated_viz", table_name="precomputed_masks")

        # Drop foreign key
        if _constraint_exists(conn, "fk_precomputed_masks_curated_look_id"):
            op.drop_constraint("fk_precomputed_masks_curated_look_id", "precomputed_masks", type_="foreignkey")

        # Drop column
        op.drop_column("precomputed_masks", "curated_look_id")

    # Make session_id required again
    op.alter_column("precomputed_masks", "session_id", existing_type=sa.String(length=36), nullable=False)
