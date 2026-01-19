"""add_api_usage_table

Revision ID: fb1cd2a025d2
Revises: c9d5e6f7a8b0
Create Date: 2026-01-09 20:20:11.915545

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fb1cd2a025d2"
down_revision: Union[str, Sequence[str], None] = "c9d5e6f7a8b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(conn, index_name: str) -> bool:
    """Check if an index exists."""
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": index_name}
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Upgrade schema - idempotent (safe to run multiple times)."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create api_usage table if it doesn't exist
    if "api_usage" not in existing_tables:
        op.create_table(
            "api_usage",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("session_id", sa.String(length=36), nullable=True),
            sa.Column("provider", sa.String(length=20), nullable=False),
            sa.Column("model", sa.String(length=50), nullable=False),
            sa.Column("operation", sa.String(length=50), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("estimated_cost", sa.Float(), nullable=True),
            sa.Column("request_metadata", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_api_usage_timestamp_provider", "api_usage", ["timestamp", "provider"], unique=False)
        op.create_index("idx_api_usage_user_operation", "api_usage", ["user_id", "operation"], unique=False)
        op.create_index(op.f("ix_api_usage_id"), "api_usage", ["id"], unique=False)
        op.create_index(op.f("ix_api_usage_model"), "api_usage", ["model"], unique=False)
        op.create_index(op.f("ix_api_usage_operation"), "api_usage", ["operation"], unique=False)
        op.create_index(op.f("ix_api_usage_provider"), "api_usage", ["provider"], unique=False)
        op.create_index(op.f("ix_api_usage_session_id"), "api_usage", ["session_id"], unique=False)
        op.create_index(op.f("ix_api_usage_timestamp"), "api_usage", ["timestamp"], unique=False)
        op.create_index(op.f("ix_api_usage_user_id"), "api_usage", ["user_id"], unique=False)

    # Alter curated_looks.room_analysis if table exists (JSONB -> JSON is usually safe)
    # Skip this as it's a no-op in most cases and can cause issues

    # Add budget_tier to homestyling_sessions if table exists and column doesn't
    if "homestyling_sessions" in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('homestyling_sessions')]
        if 'budget_tier' not in columns:
            op.add_column("homestyling_sessions", sa.Column("budget_tier", sa.String(length=20), nullable=True))
            if not _index_exists(conn, "ix_homestyling_sessions_budget_tier"):
                op.create_index(op.f("ix_homestyling_sessions_budget_tier"), "homestyling_sessions", ["budget_tier"], unique=False)

    # Create index on stores if it doesn't exist
    if "stores" in existing_tables:
        if not _index_exists(conn, "ix_stores_id"):
            op.create_index(op.f("ix_stores_id"), "stores", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "stores" in existing_tables:
        if _index_exists(conn, "ix_stores_id"):
            op.drop_index(op.f("ix_stores_id"), table_name="stores")

    if "homestyling_sessions" in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('homestyling_sessions')]
        if 'budget_tier' in columns:
            if _index_exists(conn, "ix_homestyling_sessions_budget_tier"):
                op.drop_index(op.f("ix_homestyling_sessions_budget_tier"), table_name="homestyling_sessions")
            op.drop_column("homestyling_sessions", "budget_tier")

    if "api_usage" in existing_tables:
        op.drop_index(op.f("ix_api_usage_user_id"), table_name="api_usage")
        op.drop_index(op.f("ix_api_usage_timestamp"), table_name="api_usage")
        op.drop_index(op.f("ix_api_usage_session_id"), table_name="api_usage")
        op.drop_index(op.f("ix_api_usage_provider"), table_name="api_usage")
        op.drop_index(op.f("ix_api_usage_operation"), table_name="api_usage")
        op.drop_index(op.f("ix_api_usage_model"), table_name="api_usage")
        op.drop_index(op.f("ix_api_usage_id"), table_name="api_usage")
        op.drop_index("idx_api_usage_user_operation", table_name="api_usage")
        op.drop_index("idx_api_usage_timestamp_provider", table_name="api_usage")
        op.drop_table("api_usage")
