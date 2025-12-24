"""delete_node_sofa_extension_modules_product

Revision ID: d8178f88dff1
Revises: 540e4f4fca35
Create Date: 2025-12-24 21:53:05.758659

Deletes the product "Node 2.0 Sofa - Extension Modules - Arms (1 unit)"
which is not a real sofa (it's just a sofa arm extension module).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8178f88dff1"
down_revision: Union[str, Sequence[str], None] = "540e4f4fca35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Product details for reference
PRODUCT_NAME = "Node 2.0 Sofa - Extension Modules - Arms (1 unit)"
PRODUCT_SOURCE = "pelicanessentials"


def upgrade() -> None:
    """Delete the product and its related records."""
    conn = op.get_bind()

    # Find the product ID by name (in case ID differs between environments)
    result = conn.execute(
        sa.text("SELECT id FROM products WHERE name = :name AND source_website = :source"),
        {"name": PRODUCT_NAME, "source": PRODUCT_SOURCE},
    )
    row = result.fetchone()

    if row:
        product_id = row[0]

        # Delete related product images
        conn.execute(sa.text("DELETE FROM product_images WHERE product_id = :id"), {"id": product_id})

        # Delete related product attributes
        conn.execute(sa.text("DELETE FROM product_attributes WHERE product_id = :id"), {"id": product_id})

        # Delete the product
        conn.execute(sa.text("DELETE FROM products WHERE id = :id"), {"id": product_id})

        print(f"Deleted product '{PRODUCT_NAME}' (ID: {product_id})")
    else:
        print(f"Product '{PRODUCT_NAME}' not found - may have already been deleted")


def downgrade() -> None:
    """
    Cannot restore deleted product data.
    If needed, re-scrape from source website.
    """
    print("Cannot restore deleted product - re-scrape from pelicanessentials.com if needed")
