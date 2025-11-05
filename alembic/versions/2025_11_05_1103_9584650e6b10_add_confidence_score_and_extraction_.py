"""Add confidence_score and extraction_method to product_attributes

Revision ID: 9584650e6b10
Revises: 17429ea8cb77
Create Date: 2025-11-05 11:03:04.799850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9584650e6b10'
down_revision: Union[str, Sequence[str], None] = '17429ea8cb77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add confidence_score and extraction_method columns to product_attributes
    op.add_column('product_attributes', sa.Column('confidence_score', sa.Float(), nullable=True))
    op.add_column('product_attributes', sa.Column('extraction_method', sa.String(length=50), nullable=True))
    op.add_column('product_attributes', sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))

    # Create new composite index for efficient queries
    op.create_index('idx_attribute_product_name', 'product_attributes', ['product_id', 'attribute_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the index
    op.drop_index('idx_attribute_product_name', table_name='product_attributes')

    # Drop the columns
    op.drop_column('product_attributes', 'updated_at')
    op.drop_column('product_attributes', 'extraction_method')
    op.drop_column('product_attributes', 'confidence_score')
