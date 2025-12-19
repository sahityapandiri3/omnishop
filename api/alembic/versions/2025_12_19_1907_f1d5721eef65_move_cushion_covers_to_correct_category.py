"""move_cushion_covers_to_correct_category

Revision ID: f1d5721eef65
Revises: 57ad804efc7c
Create Date: 2025-12-19 19:07:37.667443

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1d5721eef65"
down_revision: Union[str, Sequence[str], None] = "57ad804efc7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Move cushion cover products from 'Cushion' category (id 249) to 'Cushion Cover' category (id 117).
    Products are identified by having 'cover' or 'sham' in their name.
    """
    # Move products with 'cover' or 'sham' in name from Cushion (249) to Cushion Cover (117)
    op.execute(
        """
        UPDATE products
        SET category_id = 117
        WHERE category_id = 249
        AND (LOWER(name) LIKE '%cover%' OR LOWER(name) LIKE '%sham%')
    """
    )


def downgrade() -> None:
    """
    Revert: Move cushion cover products back from 'Cushion Cover' category to 'Cushion' category.
    """
    # Move products with 'cover' or 'sham' in name back from Cushion Cover (117) to Cushion (249)
    op.execute(
        """
        UPDATE products
        SET category_id = 249
        WHERE category_id = 117
        AND (LOWER(name) LIKE '%cover%' OR LOWER(name) LIKE '%sham%')
    """
    )
