"""Add curated_looks and curated_look_products tables

Revision ID: a1b2c3d4e5f6
Revises: f08c0e782d7e
Create Date: 2025-12-02 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f08c0e782d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated_looks and curated_look_products tables."""
    # Create curated_looks table
    op.create_table(
        "curated_looks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("style_theme", sa.String(length=100), nullable=False),
        sa.Column("style_description", sa.Text(), nullable=True),
        sa.Column("room_type", sa.String(length=50), nullable=False),
        sa.Column("room_image", sa.Text(), nullable=True),
        sa.Column("visualization_image", sa.Text(), nullable=True),
        sa.Column("total_price", sa.Float(), nullable=True, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("display_order", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_curated_looks_id"), "curated_looks", ["id"], unique=False)
    op.create_index(op.f("ix_curated_looks_room_type"), "curated_looks", ["room_type"], unique=False)
    op.create_index(op.f("ix_curated_looks_is_published"), "curated_looks", ["is_published"], unique=False)

    # Create curated_look_products table
    op.create_table(
        "curated_look_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("curated_look_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_type", sa.String(length=50), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["curated_look_id"],
            ["curated_looks.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_curated_look_products_id"), "curated_look_products", ["id"], unique=False)
    op.create_index(
        op.f("ix_curated_look_products_curated_look_id"), "curated_look_products", ["curated_look_id"], unique=False
    )
    op.create_index(op.f("ix_curated_look_products_product_id"), "curated_look_products", ["product_id"], unique=False)
    op.create_index("idx_curated_look_product", "curated_look_products", ["curated_look_id", "product_id"], unique=True)


def downgrade() -> None:
    """Drop curated_looks and curated_look_products tables."""
    # Drop curated_look_products first (has foreign key to curated_looks)
    op.drop_index("idx_curated_look_product", table_name="curated_look_products")
    op.drop_index(op.f("ix_curated_look_products_product_id"), table_name="curated_look_products")
    op.drop_index(op.f("ix_curated_look_products_curated_look_id"), table_name="curated_look_products")
    op.drop_index(op.f("ix_curated_look_products_id"), table_name="curated_look_products")
    op.drop_table("curated_look_products")

    # Drop curated_looks
    op.drop_index(op.f("ix_curated_looks_is_published"), table_name="curated_looks")
    op.drop_index(op.f("ix_curated_looks_room_type"), table_name="curated_looks")
    op.drop_index(op.f("ix_curated_looks_id"), table_name="curated_looks")
    op.drop_table("curated_looks")
