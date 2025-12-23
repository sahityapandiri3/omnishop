"""Add vector embedding and style columns to products table

Revision ID: 540e4f4fca35
Revises: f1d5721eef65
Create Date: 2025-12-23

This migration adds:
1. pgvector extension for vector similarity search
2. embedding column (768 dimensions for Google text-embedding-004)
3. Style classification columns (primary_style, secondary_style)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "540e4f4fca35"
down_revision: Union[str, Sequence[str], None] = "f1d5721eef65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add vector embedding and style columns to products table."""

    # Note: pgvector extension should be enabled manually on Railway if needed:
    # CREATE EXTENSION IF NOT EXISTS vector;
    # For now, we use TEXT storage for embeddings (JSON array of floats)
    # which works on all PostgreSQL instances.

    # Step 1: Add embedding columns
    # Using TEXT to store JSON array of floats - will be converted to vector type after data migration
    # This avoids issues with pgvector not being available on some hosts
    op.add_column(
        "products",
        sa.Column("embedding", sa.Text(), nullable=True, comment="JSON array of 768 floats for semantic search")
    )
    op.add_column(
        "products",
        sa.Column("embedding_text", sa.Text(), nullable=True, comment="Text that was embedded")
    )
    op.add_column(
        "products",
        sa.Column("embedding_updated_at", sa.DateTime(), nullable=True, comment="When embedding was last generated")
    )

    # Step 3: Add style classification columns
    op.add_column(
        "products",
        sa.Column("primary_style", sa.String(50), nullable=True, comment="Primary design style (e.g., modern, minimalist)")
    )
    op.add_column(
        "products",
        sa.Column("secondary_style", sa.String(50), nullable=True, comment="Secondary design style")
    )
    op.add_column(
        "products",
        sa.Column("style_confidence", sa.Float(), nullable=True, comment="Confidence score 0-1 for style classification")
    )
    op.add_column(
        "products",
        sa.Column("style_extraction_method", sa.String(50), nullable=True, comment="Method used: gemini_vision, text_nlp, manual")
    )

    # Step 4: Create indexes for style-based filtering
    op.create_index("idx_product_primary_style", "products", ["primary_style"])
    op.create_index("idx_product_styles", "products", ["primary_style", "secondary_style"])


def downgrade() -> None:
    """Remove vector embedding and style columns from products table."""

    # Drop indexes
    op.drop_index("idx_product_styles", table_name="products")
    op.drop_index("idx_product_primary_style", table_name="products")

    # Drop columns
    op.drop_column("products", "style_extraction_method")
    op.drop_column("products", "style_confidence")
    op.drop_column("products", "secondary_style")
    op.drop_column("products", "primary_style")
    op.drop_column("products", "embedding_updated_at")
    op.drop_column("products", "embedding_text")
    op.drop_column("products", "embedding")

    # Note: Not dropping pgvector extension as it may be used by other tables
