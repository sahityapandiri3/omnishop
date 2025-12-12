"""Re-categorize products from Rugs and Textiles to correct categories

Revision ID: 82605825665c
Revises: d5bceada1deb
Create Date: 2025-12-12 17:55:05.113757

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82605825665c"
down_revision: Union[str, Sequence[str], None] = "d5bceada1deb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Product ID to new category ID mappings
# Products from "Rugs & Textiles" (168) and "Rugs & Floor Runners" (62)
PRODUCT_CATEGORY_UPDATES = {
    # Bath items -> Decor & Accessories (167) - no bathroom category exists
    8603: 167,  # Checkmate Bath Set
    8602: 167,  # Checkmate Bath Towel
    8601: 167,  # Checkmate Bathrobe
    7219: 167,  # Cloud Bathmat
    # Candles/Votives -> Candles (97)
    8690: 97,  # Matt Black Votives - Set of 8
    4985: 97,  # Soul Mate
    5753: 97,  # Soulmate
    # Bowls -> Decorative Bowls (69)
    3557: 69,  # Hotn Cool Match Bowls (Set of 6)
    # Tumblers -> Tumblers (174)
    3558: 174,  # Hotn Cool Match Tumbler (Set of 6)
    # Jugs -> Water Jugs (132)
    4260: 132,  # Matka Jug
    # Tiffin/Storage -> Kitchen Organisers (90)
    4265: 90,  # Matka Tiffin
    5061: 90,  # Matka Tiffin Gift Box
    3688: 90,  # Enamel Matka Gift Set
    # Cutlery -> Decor & Accessories (167)
    4158: 167,  # Amsterdam All Mat Geltex (Set of 24) - cutlery set
    # Floor Runner -> Rug (36)
    1093: 36,  # Faux Fur Floor Runner - Pink
    # Christmas item -> Festive Decor (111)
    6846: 111,  # Christmas Checkmate
    # Table mats -> Decor & Accessories (167)
    4546: 167,  # Oak Mats - Set of 2
    10089: 167,  # Pomo Rust Place Mats
    5411: 167,  # Sara Mats- Set of 2
    # Decorative items -> Decor & Accessories (167)
    4172: 167,  # Matilda
    5862: 167,  # Matrix
    7070: 167,  # Sakya 2
    4732: 167,  # Serenity Matte
    4094: 167,  # The Matsya Weight
}

# Reverse mapping for downgrade (original categories)
ORIGINAL_CATEGORIES = {
    # From Rugs & Textiles (168)
    8603: 168,
    8602: 168,
    8601: 168,
    7219: 168,
    8690: 168,
    4985: 168,
    5753: 168,
    3557: 168,
    3558: 168,
    4260: 168,
    4265: 168,
    5061: 168,
    3688: 168,
    4158: 168,
    6846: 168,
    4546: 168,
    10089: 168,
    5411: 168,
    4172: 168,
    5862: 168,
    7070: 168,
    4732: 168,
    4094: 168,
    # From Rugs & Floor Runners (62)
    1093: 62,
}


def upgrade() -> None:
    """Re-categorize all products from Rugs & Textiles and Rugs & Floor Runners."""
    conn = op.get_bind()

    for product_id, new_category_id in PRODUCT_CATEGORY_UPDATES.items():
        conn.execute(
            sa.text("UPDATE products SET category_id = :new_cat WHERE id = :pid"),
            {"new_cat": new_category_id, "pid": product_id},
        )

    print(f"Updated {len(PRODUCT_CATEGORY_UPDATES)} products to correct categories")


def downgrade() -> None:
    """Revert products back to original categories."""
    conn = op.get_bind()

    for product_id, original_category_id in ORIGINAL_CATEGORIES.items():
        conn.execute(
            sa.text("UPDATE products SET category_id = :orig_cat WHERE id = :pid"),
            {"orig_cat": original_category_id, "pid": product_id},
        )

    print(f"Reverted {len(ORIGINAL_CATEGORIES)} products to original categories")
