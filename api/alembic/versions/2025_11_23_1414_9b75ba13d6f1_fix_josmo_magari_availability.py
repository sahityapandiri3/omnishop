"""fix_josmo_magari_availability

Revision ID: 9b75ba13d6f1
Revises: 185600cfb697
Create Date: 2025-11-23 14:14:07.489076

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b75ba13d6f1"
down_revision: Union[str, Sequence[str], None] = "185600cfb697"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fix josmo and magari products marked as unavailable when they should be available
    # These products were incorrectly scraped with is_available=False due to Shopify API availability field
    op.execute(
        """
        UPDATE products
        SET is_available = TRUE, stock_status = 'in_stock'
        WHERE source_website IN ('josmo', 'magari') AND is_available = FALSE
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert josmo and magari products back to unavailable
    op.execute(
        """
        UPDATE products
        SET is_available = FALSE, stock_status = 'out_of_stock'
        WHERE source_website IN ('josmo', 'magari')
        """
    )
