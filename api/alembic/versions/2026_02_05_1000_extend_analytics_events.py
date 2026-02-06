"""extend analytics_events: widen columns, add page_url, add composite index

Revision ID: 4e5f6a7b8c9d
Revises: 3c4d5e6f7g8h
Create Date: 2026-02-05
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "4e5f6a7b8c9d"
down_revision = "3c4d5e6f7g8h"
branch_labels = None
depends_on = None


def upgrade():
    # Widen event_type from VARCHAR(50) to VARCHAR(100)
    op.alter_column(
        "analytics_events",
        "event_type",
        existing_type=sa.String(50),
        type_=sa.String(100),
        existing_nullable=False,
    )

    # Widen step_name from VARCHAR(50) to VARCHAR(100)
    op.alter_column(
        "analytics_events",
        "step_name",
        existing_type=sa.String(50),
        type_=sa.String(100),
        existing_nullable=True,
    )

    # Add page_url column
    op.add_column(
        "analytics_events",
        sa.Column("page_url", sa.String(500), nullable=True),
    )

    # Add composite index for funnel queries
    op.create_index(
        "idx_analytics_user_event_type",
        "analytics_events",
        ["user_id", "event_type", "created_at"],
    )


def downgrade():
    op.drop_index("idx_analytics_user_event_type", table_name="analytics_events")
    op.drop_column("analytics_events", "page_url")
    op.alter_column(
        "analytics_events",
        "step_name",
        existing_type=sa.String(100),
        type_=sa.String(50),
        existing_nullable=True,
    )
    op.alter_column(
        "analytics_events",
        "event_type",
        existing_type=sa.String(100),
        type_=sa.String(50),
        existing_nullable=False,
    )
