"""add system_settings table for global app settings

Revision ID: 3c4d5e6f7g8h
Revises: 28add4542bdc
Create Date: 2026-02-04
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "3c4d5e6f7g8h"
down_revision = "28add4542bdc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade():
    op.drop_table("system_settings")
