"""Add status field to projects table for draft mode

Revision ID: 458840706a59
Revises: 598475a02acf
Create Date: 2025-12-16 09:50:01.647208

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "458840706a59"
down_revision: Union[str, Sequence[str], None] = "598475a02acf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type first
    projectstatus = sa.Enum("DRAFT", "PUBLISHED", name="projectstatus")
    projectstatus.create(op.get_bind(), checkfirst=True)

    # Add column with default value for existing rows
    op.add_column("projects", sa.Column("status", projectstatus, nullable=False, server_default="DRAFT"))
    op.create_index(op.f("ix_projects_status"), "projects", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_projects_status"), table_name="projects")
    op.drop_column("projects", "status")
    # Drop the enum type
    sa.Enum(name="projectstatus").drop(op.get_bind(), checkfirst=True)
