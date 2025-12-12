"""Rename Rug category to Rugs

Revision ID: 9a0d2954ab5d
Revises: 82605825665c
Create Date: 2025-12-12 17:58:30.708248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a0d2954ab5d'
down_revision: Union[str, Sequence[str], None] = '82605825665c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename 'Rug' category to 'Rugs' (plural)."""
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE categories SET name = 'Rugs' WHERE id = 36"))


def downgrade() -> None:
    """Revert 'Rugs' back to 'Rug'."""
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE categories SET name = 'Rug' WHERE id = 36"))
