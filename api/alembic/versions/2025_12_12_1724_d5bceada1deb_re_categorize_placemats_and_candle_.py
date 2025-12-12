"""Re-categorize placemats and candle holders from Rugs to correct categories

Revision ID: d5bceada1deb
Revises: d249967ad91f
Create Date: 2025-12-12 17:24:18.953070

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5bceada1deb"
down_revision: Union[str, Sequence[str], None] = "d249967ad91f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Re-categorize miscategorized products:
    - Move placemats from 'Rugs & Textiles' to 'Decor & Accessories'
    - Move candle holders from 'Rugs & Textiles' to 'Candle Holders'
    - Move brass bowls with 'Matt' in name from 'Rugs & Textiles' to 'Decor & Accessories'
    """
    # Get connection for raw SQL execution
    conn = op.get_bind()

    # First, get the category IDs (they may vary between environments)
    result = conn.execute(
        sa.text("SELECT id, name FROM categories WHERE name IN ('Candle Holders', 'Decor & Accessories', 'Rugs & Textiles')")
    )
    categories = {row[1]: row[0] for row in result}

    candle_holders_id = categories.get("Candle Holders")
    decor_accessories_id = categories.get("Decor & Accessories")
    rugs_textiles_id = categories.get("Rugs & Textiles")

    if not all([candle_holders_id, decor_accessories_id, rugs_textiles_id]):
        print("Warning: Not all required categories found, skipping data migration")
        return

    # Move candle holders from Rugs & Textiles to Candle Holders
    conn.execute(
        sa.text(
            """
        UPDATE products
        SET category_id = :candle_holders_id
        WHERE category_id = :rugs_textiles_id
        AND LOWER(name) LIKE '%candle holder%'
    """
        ),
        {"candle_holders_id": candle_holders_id, "rugs_textiles_id": rugs_textiles_id},
    )

    # Move placemats from Rugs & Textiles to Decor & Accessories
    conn.execute(
        sa.text(
            """
        UPDATE products
        SET category_id = :decor_accessories_id
        WHERE category_id = :rugs_textiles_id
        AND LOWER(name) LIKE '%placemat%'
    """
        ),
        {"decor_accessories_id": decor_accessories_id, "rugs_textiles_id": rugs_textiles_id},
    )

    # Move "Matt Brass Bowl" products from Rugs & Textiles to Decor & Accessories
    conn.execute(
        sa.text(
            """
        UPDATE products
        SET category_id = :decor_accessories_id
        WHERE category_id = :rugs_textiles_id
        AND LOWER(name) LIKE '%matt brass bowl%'
    """
        ),
        {"decor_accessories_id": decor_accessories_id, "rugs_textiles_id": rugs_textiles_id},
    )

    # Move "Matt Candle" products from Rugs & Textiles to Candle Holders
    conn.execute(
        sa.text(
            """
        UPDATE products
        SET category_id = :candle_holders_id
        WHERE category_id = :rugs_textiles_id
        AND LOWER(name) LIKE '%matt candle%'
    """
        ),
        {"candle_holders_id": candle_holders_id, "rugs_textiles_id": rugs_textiles_id},
    )


def downgrade() -> None:
    """
    Revert the re-categorization.
    Note: This is a best-effort downgrade - exact original categories may not be restored.
    """
    # Get connection for raw SQL execution
    conn = op.get_bind()

    # Get category IDs
    result = conn.execute(
        sa.text("SELECT id, name FROM categories WHERE name IN ('Candle Holders', 'Decor & Accessories', 'Rugs & Textiles')")
    )
    categories = {row[1]: row[0] for row in result}

    candle_holders_id = categories.get("Candle Holders")
    decor_accessories_id = categories.get("Decor & Accessories")
    rugs_textiles_id = categories.get("Rugs & Textiles")

    if not all([candle_holders_id, decor_accessories_id, rugs_textiles_id]):
        print("Warning: Not all required categories found, skipping downgrade")
        return

    # Move placemats back to Rugs & Textiles
    conn.execute(
        sa.text(
            """
        UPDATE products
        SET category_id = :rugs_textiles_id
        WHERE category_id = :decor_accessories_id
        AND LOWER(name) LIKE '%placemat%'
    """
        ),
        {"rugs_textiles_id": rugs_textiles_id, "decor_accessories_id": decor_accessories_id},
    )
