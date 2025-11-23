"""fix_phantomhands_availability

Revision ID: f08c0e782d7e
Revises: 9b75ba13d6f1
Create Date: 2025-11-23 14:39:23.597304

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f08c0e782d7e'
down_revision: Union[str, Sequence[str], None] = '9b75ba13d6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fix phantomhands products marked as unavailable when they should be available
    # These products were incorrectly scraped with is_available=False due to Shopify API availability field
    op.execute(
        """
        UPDATE products
        SET is_available = TRUE, stock_status = 'in_stock'
        WHERE source_website = 'phantomhands' AND is_available = FALSE
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert phantomhands products back to unavailable
    op.execute(
        """
        UPDATE products
        SET is_available = FALSE, stock_status = 'out_of_stock'
        WHERE source_website = 'phantomhands'
        """
    )
