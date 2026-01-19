"""add_precomputed_masks_table

Revision ID: 369950a2002b
Revises: cda9e2c70800
Create Date: 2025-12-31 01:28:03.387525

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '369950a2002b'
down_revision: Union[str, Sequence[str], None] = 'cda9e2c70800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_exists(conn, enum_name: str) -> bool:
    """Check if an enum type exists in PostgreSQL."""
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": enum_name}
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Upgrade schema - idempotent (safe to run multiple times)."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Skip if table already exists
    if "precomputed_masks" in existing_tables:
        return

    # Create enum if it doesn't exist
    if not _enum_exists(conn, "precomputedmaskstatus"):
        precomputedmaskstatus = sa.Enum('pending', 'processing', 'completed', 'failed', name='precomputedmaskstatus')
        precomputedmaskstatus.create(conn, checkfirst=True)

    op.create_table('precomputed_masks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('visualization_hash', sa.String(length=64), nullable=False),
        sa.Column('product_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='precomputedmaskstatus', create_type=False), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('clean_background', sa.Text(), nullable=True),
        sa.Column('layers_data', sa.JSON(), nullable=True),
        sa.Column('extraction_method', sa.String(length=50), nullable=True),
        sa.Column('image_dimensions', sa.JSON(), nullable=True),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_precomputed_mask_lookup', 'precomputed_masks', ['session_id', 'visualization_hash', 'product_hash'], unique=False)
    op.create_index('idx_precomputed_mask_session_viz', 'precomputed_masks', ['session_id', 'visualization_hash'], unique=False)
    op.create_index('idx_precomputed_mask_status', 'precomputed_masks', ['status', 'created_at'], unique=False)
    op.create_index(op.f('ix_precomputed_masks_id'), 'precomputed_masks', ['id'], unique=False)
    op.create_index(op.f('ix_precomputed_masks_product_hash'), 'precomputed_masks', ['product_hash'], unique=False)
    op.create_index(op.f('ix_precomputed_masks_session_id'), 'precomputed_masks', ['session_id'], unique=False)
    op.create_index(op.f('ix_precomputed_masks_status'), 'precomputed_masks', ['status'], unique=False)
    op.create_index(op.f('ix_precomputed_masks_visualization_hash'), 'precomputed_masks', ['visualization_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "precomputed_masks" in existing_tables:
        op.drop_index(op.f('ix_precomputed_masks_visualization_hash'), table_name='precomputed_masks')
        op.drop_index(op.f('ix_precomputed_masks_status'), table_name='precomputed_masks')
        op.drop_index(op.f('ix_precomputed_masks_session_id'), table_name='precomputed_masks')
        op.drop_index(op.f('ix_precomputed_masks_product_hash'), table_name='precomputed_masks')
        op.drop_index(op.f('ix_precomputed_masks_id'), table_name='precomputed_masks')
        op.drop_index('idx_precomputed_mask_status', table_name='precomputed_masks')
        op.drop_index('idx_precomputed_mask_session_viz', table_name='precomputed_masks')
        op.drop_index('idx_precomputed_mask_lookup', table_name='precomputed_masks')
        op.drop_table('precomputed_masks')
