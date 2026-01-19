"""add_homestyling_and_analytics_tables

Revision ID: cda9e2c70800
Revises: c8cc8852497c
Create Date: 2025-12-28 17:48:19.001211

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "cda9e2c70800"
down_revision: Union[str, Sequence[str], None] = "c8cc8852497c"
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

    # Create analytics_events table if it doesn't exist
    if "analytics_events" not in existing_tables:
        op.create_table(
            "analytics_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=True),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("step_name", sa.String(length=50), nullable=True),
            sa.Column("event_data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_analytics_event_type_created", "analytics_events", ["event_type", "created_at"], unique=False)
        op.create_index("idx_analytics_session_created", "analytics_events", ["session_id", "created_at"], unique=False)
        op.create_index("idx_analytics_user_created", "analytics_events", ["user_id", "created_at"], unique=False)
        op.create_index(op.f("ix_analytics_events_created_at"), "analytics_events", ["created_at"], unique=False)
        op.create_index(op.f("ix_analytics_events_event_type"), "analytics_events", ["event_type"], unique=False)
        op.create_index(op.f("ix_analytics_events_id"), "analytics_events", ["id"], unique=False)
        op.create_index(op.f("ix_analytics_events_session_id"), "analytics_events", ["session_id"], unique=False)
        op.create_index(op.f("ix_analytics_events_user_id"), "analytics_events", ["user_id"], unique=False)

    # Create enums if they don't exist
    if not _enum_exists(conn, "homestylingtier"):
        homestylingtier = sa.Enum("free", "basic", "premium", name="homestylingtier")
        homestylingtier.create(conn, checkfirst=True)

    if not _enum_exists(conn, "homestylingsessionstatus"):
        homestylingsessionstatus = sa.Enum(
            "preferences", "upload", "tier_selection", "generating", "completed", "failed",
            name="homestylingsessionstatus"
        )
        homestylingsessionstatus.create(conn, checkfirst=True)

    # Create homestyling_sessions table if it doesn't exist
    if "homestyling_sessions" not in existing_tables:
        op.create_table(
            "homestyling_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("room_type", sa.String(length=50), nullable=True),
            sa.Column("style", sa.String(length=50), nullable=True),
            sa.Column("color_palette", sa.JSON(), nullable=True),
            sa.Column("original_room_image", sa.Text(), nullable=True),
            sa.Column("clean_room_image", sa.Text(), nullable=True),
            sa.Column("selected_tier", sa.Enum("free", "basic", "premium", name="homestylingtier", create_type=False), nullable=True),
            sa.Column("views_count", sa.Integer(), nullable=True),
            sa.Column(
                "status",
                sa.Enum(
                    "preferences", "upload", "tier_selection", "generating", "completed", "failed",
                    name="homestylingsessionstatus", create_type=False
                ),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_homestyling_session_status", "homestyling_sessions", ["status", "created_at"], unique=False)
        op.create_index("idx_homestyling_session_user", "homestyling_sessions", ["user_id", "created_at"], unique=False)
        op.create_index(op.f("ix_homestyling_sessions_status"), "homestyling_sessions", ["status"], unique=False)
        op.create_index(op.f("ix_homestyling_sessions_user_id"), "homestyling_sessions", ["user_id"], unique=False)

    # Create homestyling_views table if it doesn't exist
    if "homestyling_views" not in existing_tables:
        op.create_table(
            "homestyling_views",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("curated_look_id", sa.Integer(), nullable=True),
            sa.Column("visualization_image", sa.Text(), nullable=True),
            sa.Column("view_number", sa.Integer(), nullable=False),
            sa.Column("generation_status", sa.String(length=20), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["curated_look_id"], ["curated_looks.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["homestyling_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_homestyling_view_session", "homestyling_views", ["session_id", "view_number"], unique=False)
        op.create_index(op.f("ix_homestyling_views_curated_look_id"), "homestyling_views", ["curated_look_id"], unique=False)
        op.create_index(op.f("ix_homestyling_views_id"), "homestyling_views", ["id"], unique=False)
        op.create_index(op.f("ix_homestyling_views_session_id"), "homestyling_views", ["session_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "homestyling_views" in existing_tables:
        op.drop_index(op.f("ix_homestyling_views_session_id"), table_name="homestyling_views")
        op.drop_index(op.f("ix_homestyling_views_id"), table_name="homestyling_views")
        op.drop_index(op.f("ix_homestyling_views_curated_look_id"), table_name="homestyling_views")
        op.drop_index("idx_homestyling_view_session", table_name="homestyling_views")
        op.drop_table("homestyling_views")

    if "homestyling_sessions" in existing_tables:
        op.drop_index(op.f("ix_homestyling_sessions_user_id"), table_name="homestyling_sessions")
        op.drop_index(op.f("ix_homestyling_sessions_status"), table_name="homestyling_sessions")
        op.drop_index("idx_homestyling_session_user", table_name="homestyling_sessions")
        op.drop_index("idx_homestyling_session_status", table_name="homestyling_sessions")
        op.drop_table("homestyling_sessions")

    if "analytics_events" in existing_tables:
        op.drop_index(op.f("ix_analytics_events_user_id"), table_name="analytics_events")
        op.drop_index(op.f("ix_analytics_events_session_id"), table_name="analytics_events")
        op.drop_index(op.f("ix_analytics_events_id"), table_name="analytics_events")
        op.drop_index(op.f("ix_analytics_events_event_type"), table_name="analytics_events")
        op.drop_index(op.f("ix_analytics_events_created_at"), table_name="analytics_events")
        op.drop_index("idx_analytics_user_created", table_name="analytics_events")
        op.drop_index("idx_analytics_session_created", table_name="analytics_events")
        op.drop_index("idx_analytics_event_type_created", table_name="analytics_events")
        op.drop_table("analytics_events")
