"""fix_kalvi_kalai_product_categories

Revision ID: 6e6eea19bf42
Revises: 61749b6b1dfa
Create Date: 2025-12-14 13:10:00.588906

Fix product categorization:
- Kalvi with Arms (id 10394): Sofas Sectionals (178) -> Accent Chair (264)
- Kalai (id 10380): Sofas Sectionals (178) -> Console Table (142)
- Kalvi (id 10408): Sofas Sectionals (178) -> Accent Chair (264)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6e6eea19bf42"
down_revision: Union[str, Sequence[str], None] = "61749b6b1dfa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix Magari product categories."""
    # Kalvi with Arms -> Accent Chair (264)
    op.execute(
        """
        UPDATE products
        SET category_id = 264
        WHERE name = 'Kalvi with Arms' AND source_website = 'magari'
    """
    )

    # Kalai -> Console Table (142)
    op.execute(
        """
        UPDATE products
        SET category_id = 142
        WHERE name = 'Kalai' AND source_website = 'magari'
    """
    )

    # Kalvi (base) -> Accent Chair (264)
    op.execute(
        """
        UPDATE products
        SET category_id = 264
        WHERE name = 'Kalvi' AND source_website = 'magari'
    """
    )


def downgrade() -> None:
    """Revert to original Sofas Sectionals category."""
    # Revert all three products back to Sofas Sectionals (178)
    op.execute(
        """
        UPDATE products
        SET category_id = 178
        WHERE name IN ('Kalvi with Arms', 'Kalai', 'Kalvi')
        AND source_website = 'magari'
    """
    )
