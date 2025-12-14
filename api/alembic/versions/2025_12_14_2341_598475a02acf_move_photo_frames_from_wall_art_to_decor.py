"""move_photo_frames_from_wall_art_to_decor

Revision ID: 598475a02acf
Revises: 6e6eea19bf42
Create Date: 2025-12-14 23:41:57.214452

Move products with 'frame' in name from Wall Art category to Decor Accents.
Photo frames, picture frames should be in Decor, not Wall Art.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '598475a02acf'
down_revision: Union[str, Sequence[str], None] = '6e6eea19bf42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Move photo frames from Wall Art to Decor Accents."""
    conn = op.get_bind()

    # Get category IDs
    wall_art_result = conn.execute(
        sa.text("SELECT id FROM categories WHERE name = 'Wall Art'")
    ).fetchone()
    decor_result = conn.execute(
        sa.text("SELECT id FROM categories WHERE name = 'Decor Accents'")
    ).fetchone()

    if not wall_art_result or not decor_result:
        print("Warning: Could not find Wall Art or Decor Accents category")
        return

    wall_art_id = wall_art_result[0]
    decor_id = decor_result[0]

    # Find products with 'frame' in name in Wall Art category
    products_to_move = conn.execute(
        sa.text("""
            SELECT id, name FROM products
            WHERE category_id = :wall_art_id
            AND (name ILIKE '%frame%' OR name ILIKE '%photo frame%' OR name ILIKE '%picture frame%')
        """),
        {"wall_art_id": wall_art_id}
    ).fetchall()

    print(f"Found {len(products_to_move)} frame products to move from Wall Art to Decor Accents:")
    for product in products_to_move:
        print(f"  - {product[1]} (id: {product[0]})")

    # Move products to Decor Accents
    if products_to_move:
        product_ids = [p[0] for p in products_to_move]
        conn.execute(
            sa.text("""
                UPDATE products
                SET category_id = :decor_id
                WHERE id = ANY(:product_ids)
            """),
            {"decor_id": decor_id, "product_ids": product_ids}
        )
        print(f"Moved {len(products_to_move)} products to Decor Accents")


def downgrade() -> None:
    """Move photo frames back from Decor Accents to Wall Art."""
    conn = op.get_bind()

    # Get category IDs
    wall_art_result = conn.execute(
        sa.text("SELECT id FROM categories WHERE name = 'Wall Art'")
    ).fetchone()
    decor_result = conn.execute(
        sa.text("SELECT id FROM categories WHERE name = 'Decor Accents'")
    ).fetchone()

    if not wall_art_result or not decor_result:
        return

    wall_art_id = wall_art_result[0]
    decor_id = decor_result[0]

    # Move frame products back to Wall Art
    conn.execute(
        sa.text("""
            UPDATE products
            SET category_id = :wall_art_id
            WHERE category_id = :decor_id
            AND (name ILIKE '%frame%' OR name ILIKE '%photo frame%' OR name ILIKE '%picture frame%')
        """),
        {"wall_art_id": wall_art_id, "decor_id": decor_id}
    )
