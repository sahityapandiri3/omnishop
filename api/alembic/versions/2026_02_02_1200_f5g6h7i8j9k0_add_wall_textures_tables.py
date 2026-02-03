"""add_wall_textures_tables

Revision ID: f5g6h7i8j9k0
Revises: e4f5g6h7i8j9
Create Date: 2026-02-02 12:00:00.000000

Adds wall_textures and wall_texture_variants tables for storing textured wall
finishes from Asian Paints and other vendors. Textures have multiple color
variants, each with image data stored as base64 for passing to Gemini.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "f5g6h7i8j9k0"
down_revision: Union[str, Sequence[str], None] = "e4f5g6h7i8j9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_exists(conn, enum_name: str) -> bool:
    """Check if an enum type exists in PostgreSQL."""
    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = :name"), {"name": enum_name})
    return result.fetchone() is not None


def upgrade() -> None:
    """Create wall_textures and wall_texture_variants tables with texturetype enum."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create texturetype enum if it doesn't exist
    enum_exists = _enum_exists(conn, "texturetype")
    if not enum_exists:
        conn.execute(
            sa.text(
                """
            CREATE TYPE texturetype AS ENUM (
                'marble',
                'velvet',
                'stone',
                'concrete',
                '3d',
                'wall_tile',
                'stucco',
                'rust',
                'other'
            )
        """
            )
        )

    # Create wall_textures table if it doesn't exist
    if "wall_textures" not in existing_tables:
        conn.execute(
            sa.text(
                """
            CREATE TABLE wall_textures (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                collection VARCHAR(100),
                texture_type texturetype,
                brand VARCHAR(100) NOT NULL DEFAULT 'Asian Paints',
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                display_order INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT now()
            )
        """
            )
        )

        # Create indexes for wall_textures
        conn.execute(sa.text("CREATE INDEX ix_wall_textures_id ON wall_textures (id)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_textures_name ON wall_textures (name)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_textures_collection ON wall_textures (collection)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_textures_texture_type ON wall_textures (texture_type)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_textures_brand ON wall_textures (brand)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_textures_is_active ON wall_textures (is_active)"))
        conn.execute(sa.text("CREATE INDEX idx_wall_texture_brand_type ON wall_textures (brand, texture_type)"))
        conn.execute(sa.text("CREATE INDEX idx_wall_texture_collection ON wall_textures (collection, display_order)"))

    # Create wall_texture_variants table if it doesn't exist
    if "wall_texture_variants" not in existing_tables:
        # Note: wallcolorfamily enum already exists from wall_colors migration
        conn.execute(
            sa.text(
                """
            CREATE TABLE wall_texture_variants (
                id SERIAL PRIMARY KEY,
                texture_id INTEGER NOT NULL REFERENCES wall_textures(id) ON DELETE CASCADE,
                code VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(255),
                image_data TEXT NOT NULL,
                image_url VARCHAR(500),
                color_family wallcolorfamily,
                is_active BOOLEAN DEFAULT true,
                display_order INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT now()
            )
        """
            )
        )

        # Create indexes for wall_texture_variants
        conn.execute(sa.text("CREATE INDEX ix_wall_texture_variants_id ON wall_texture_variants (id)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_texture_variants_texture_id ON wall_texture_variants (texture_id)"))
        conn.execute(sa.text("CREATE UNIQUE INDEX ix_wall_texture_variants_code ON wall_texture_variants (code)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_texture_variants_color_family ON wall_texture_variants (color_family)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_texture_variants_is_active ON wall_texture_variants (is_active)"))
        conn.execute(
            sa.text("CREATE INDEX idx_wall_texture_variant_texture ON wall_texture_variants (texture_id, display_order)")
        )
        conn.execute(sa.text("CREATE INDEX idx_wall_texture_variant_color ON wall_texture_variants (color_family, is_active)"))


def downgrade() -> None:
    """Drop wall_texture_variants, wall_textures tables and texturetype enum."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Drop wall_texture_variants first (foreign key dependency)
    if "wall_texture_variants" in existing_tables:
        op.drop_index("idx_wall_texture_variant_color", table_name="wall_texture_variants")
        op.drop_index("idx_wall_texture_variant_texture", table_name="wall_texture_variants")
        op.drop_index(op.f("ix_wall_texture_variants_is_active"), table_name="wall_texture_variants")
        op.drop_index(op.f("ix_wall_texture_variants_color_family"), table_name="wall_texture_variants")
        op.drop_index(op.f("ix_wall_texture_variants_code"), table_name="wall_texture_variants")
        op.drop_index(op.f("ix_wall_texture_variants_texture_id"), table_name="wall_texture_variants")
        op.drop_index(op.f("ix_wall_texture_variants_id"), table_name="wall_texture_variants")
        op.drop_table("wall_texture_variants")

    # Drop wall_textures
    if "wall_textures" in existing_tables:
        op.drop_index("idx_wall_texture_collection", table_name="wall_textures")
        op.drop_index("idx_wall_texture_brand_type", table_name="wall_textures")
        op.drop_index(op.f("ix_wall_textures_is_active"), table_name="wall_textures")
        op.drop_index(op.f("ix_wall_textures_brand"), table_name="wall_textures")
        op.drop_index(op.f("ix_wall_textures_texture_type"), table_name="wall_textures")
        op.drop_index(op.f("ix_wall_textures_collection"), table_name="wall_textures")
        op.drop_index(op.f("ix_wall_textures_name"), table_name="wall_textures")
        op.drop_index(op.f("ix_wall_textures_id"), table_name="wall_textures")
        op.drop_table("wall_textures")

    # Drop texturetype enum (only works if no columns reference it)
    if _enum_exists(conn, "texturetype"):
        conn.execute(sa.text("DROP TYPE IF EXISTS texturetype"))
