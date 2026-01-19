"""change budget_tier from enum to varchar

Revision ID: b8c31a3ae707
Revises: b8d4e5f6a7c9
Create Date: 2026-01-07 19:35:42.728103

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "b8c31a3ae707"
down_revision: Union[str, Sequence[str], None] = "b8d4e5f6a7c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_is_varchar(conn, table_name: str, column_name: str) -> bool:
    """Check if a column is already VARCHAR type."""
    result = conn.execute(
        sa.text("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
        """),
        {"table": table_name, "column": column_name}
    )
    row = result.fetchone()
    if row:
        return row[0] in ('character varying', 'varchar')
    return False


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Upgrade schema - idempotent.

    Change budget_tier column from native PostgreSQL enum to VARCHAR(20).
    This fixes asyncpg compatibility issues with enum types.
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Change the column type from enum to varchar in curated_looks, if needed
    if "curated_looks" in existing_tables:
        if _column_exists(inspector, "curated_looks", "budget_tier"):
            if not _column_is_varchar(conn, "curated_looks", "budget_tier"):
                op.execute(
                    """
                    ALTER TABLE curated_looks
                    ALTER COLUMN budget_tier TYPE VARCHAR(20)
                    USING budget_tier::text
                """
                )

    # Also change it in stores table if column exists and is not already varchar
    if "stores" in existing_tables:
        if _column_exists(inspector, "stores", "budget_tier"):
            if not _column_is_varchar(conn, "stores", "budget_tier"):
                op.execute(
                    """
                    ALTER TABLE stores
                    ALTER COLUMN budget_tier TYPE VARCHAR(20)
                    USING budget_tier::text
                """
                )

    # Drop the enum type since we're no longer using it (if it exists)
    op.execute("DROP TYPE IF EXISTS budgettier")


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Recreate the enum type if it doesn't exist
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE budgettier AS ENUM ('pocket_friendly', 'mid_tier', 'premium', 'luxury');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """
    )

    # Change column back to enum in curated_looks
    if "curated_looks" in existing_tables:
        if _column_exists(inspector, "curated_looks", "budget_tier"):
            op.execute(
                """
                ALTER TABLE curated_looks
                ALTER COLUMN budget_tier TYPE budgettier
                USING budget_tier::budgettier
            """
            )

    # Change column back to enum in stores
    if "stores" in existing_tables:
        if _column_exists(inspector, "stores", "budget_tier"):
            op.execute(
                """
                ALTER TABLE stores
                ALTER COLUMN budget_tier TYPE budgettier
                USING budget_tier::budgettier
            """
            )
