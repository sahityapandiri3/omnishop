"""add_layer_data_to_furniture_positions

Revision ID: f0607fc0c831
Revises: ffd0ace4b641
Create Date: 2025-11-22 17:45:36.991217

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0607fc0c831"
down_revision: Union[str, Sequence[str], None] = "ffd0ace4b641"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add layer_image_url and z_index columns to furniture_positions table."""
    # Add layer_image_url column for storing isolated furniture layer images
    op.add_column("furniture_positions", sa.Column("layer_image_url", sa.Text(), nullable=True))

    # Add z_index column for layer stacking order
    op.add_column("furniture_positions", sa.Column("z_index", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    """Remove layer_image_url and z_index columns from furniture_positions table."""
    # Remove z_index column
    op.drop_column("furniture_positions", "z_index")

    # Remove layer_image_url column
    op.drop_column("furniture_positions", "layer_image_url")
