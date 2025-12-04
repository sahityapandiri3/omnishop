"""add_visualization_history_to_projects

Revision ID: 5621174fa00b
Revises: fa9d60b01645
Create Date: 2025-12-04 22:38:20.160899

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5621174fa00b"
down_revision: Union[str, Sequence[str], None] = "fa9d60b01645"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("projects", sa.Column("visualization_history", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projects", "visualization_history")
