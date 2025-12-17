"""add_quantity_to_curated_look_products

Revision ID: 57ad804efc7c
Revises: 458840706a59
Create Date: 2025-12-16 10:55:11.984774

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "57ad804efc7c"
down_revision: Union[str, Sequence[str], None] = "458840706a59"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add quantity column with default value of 1
    op.add_column("curated_look_products", sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("curated_look_products", "quantity")
