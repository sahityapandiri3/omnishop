"""add room_analysis column to curated_looks and projects

Revision ID: c9d5e6f7a8b0
Revises: b8c31a3ae707
Create Date: 2026-01-08 14:03:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "c9d5e6f7a8b0"
down_revision: Union[str, Sequence[str], None] = "b8c31a3ae707"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add room_analysis JSONB column to curated_looks and projects tables - idempotent.

    This column stores cached room analysis data from the upload step,
    eliminating redundant Gemini API calls during visualization.
    Saves 4-13 seconds per visualization by avoiding repeated room analysis.

    Structure stored:
    {
        "room_type": "living_room",
        "dimensions": {...},
        "lighting_conditions": "natural",
        "color_palette": [...],
        "existing_furniture": [...],  # Detailed furniture detection
        "architectural_features": [...],
        "style_assessment": "modern",
        "confidence_score": 0.85,
        "scale_references": {...},
        "camera_view_analysis": {...}
    }
    """
    conn = op.get_bind()
    inspector = inspect(conn)

    # Add room_analysis to curated_looks table (admin curation flow)
    if "curated_looks" in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('curated_looks')]
        if 'room_analysis' not in columns:
            op.add_column("curated_looks", sa.Column("room_analysis", JSONB, nullable=True))

    # Add room_analysis to projects table (design page flow)
    if "projects" in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'room_analysis' not in columns:
            op.add_column("projects", sa.Column("room_analysis", JSONB, nullable=True))


def downgrade() -> None:
    """Remove room_analysis columns."""
    conn = op.get_bind()
    inspector = inspect(conn)

    if "projects" in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('projects')]
        if 'room_analysis' in columns:
            op.drop_column("projects", "room_analysis")

    if "curated_looks" in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('curated_looks')]
        if 'room_analysis' in columns:
            op.drop_column("curated_looks", "room_analysis")
