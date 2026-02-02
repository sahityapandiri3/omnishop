"""add_wall_colors_table

Revision ID: e4f5g6h7i8j9
Revises: d3e4f5g6h7i8
Create Date: 2026-02-02 10:00:00.000000

Adds wall_colors table for storing Asian Paints wall color catalog.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "e4f5g6h7i8j9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5g6h7i8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_exists(conn, enum_name: str) -> bool:
    """Check if an enum type exists in PostgreSQL."""
    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = :name"), {"name": enum_name})
    return result.fetchone() is not None


def upgrade() -> None:
    """Create wall_colors table and wallcolorfamily enum."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create wallcolorfamily enum if it doesn't exist
    enum_exists = _enum_exists(conn, "wallcolorfamily")
    if not enum_exists:
        # Create enum using raw SQL to avoid SQLAlchemy auto-creation issues
        conn.execute(
            sa.text(
                """
            CREATE TYPE wallcolorfamily AS ENUM (
                'whites_offwhites',
                'greys',
                'blues',
                'browns',
                'yellows_greens',
                'reds_oranges',
                'purples_pinks'
            )
        """
            )
        )

    # Create wall_colors table if it doesn't exist
    if "wall_colors" not in existing_tables:
        # Use raw SQL for table creation to avoid SQLAlchemy Enum auto-creation
        conn.execute(
            sa.text(
                """
            CREATE TABLE wall_colors (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                hex_value VARCHAR(7) NOT NULL,
                family wallcolorfamily NOT NULL,
                brand VARCHAR(100) NOT NULL DEFAULT 'Asian Paints',
                is_active BOOLEAN DEFAULT true,
                display_order INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT now()
            )
        """
            )
        )

        # Create indexes
        conn.execute(sa.text("CREATE INDEX ix_wall_colors_id ON wall_colors (id)"))
        conn.execute(sa.text("CREATE UNIQUE INDEX ix_wall_colors_code ON wall_colors (code)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_colors_name ON wall_colors (name)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_colors_family ON wall_colors (family)"))
        conn.execute(sa.text("CREATE INDEX ix_wall_colors_is_active ON wall_colors (is_active)"))
        conn.execute(sa.text("CREATE INDEX idx_wall_color_family_order ON wall_colors (family, display_order)"))
        conn.execute(sa.text("CREATE INDEX idx_wall_color_brand_family ON wall_colors (brand, family)"))


def downgrade() -> None:
    """Drop wall_colors table and wallcolorfamily enum."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "wall_colors" in existing_tables:
        op.drop_index("idx_wall_color_brand_family", table_name="wall_colors")
        op.drop_index("idx_wall_color_family_order", table_name="wall_colors")
        op.drop_index(op.f("ix_wall_colors_is_active"), table_name="wall_colors")
        op.drop_index(op.f("ix_wall_colors_family"), table_name="wall_colors")
        op.drop_index(op.f("ix_wall_colors_name"), table_name="wall_colors")
        op.drop_index(op.f("ix_wall_colors_code"), table_name="wall_colors")
        op.drop_index(op.f("ix_wall_colors_id"), table_name="wall_colors")
        op.drop_table("wall_colors")

    # Drop enum (note: only works if no columns reference it)
    if _enum_exists(conn, "wallcolorfamily"):
        conn.execute(sa.text("DROP TYPE IF EXISTS wallcolorfamily"))
