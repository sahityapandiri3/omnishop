"""add floor_tiles table

Revision ID: 28add4542bdc
Revises: a1b2c3swatch
Create Date: 2026-02-03
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "28add4542bdc"
down_revision = "a1b2c3swatch"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "floor_tiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=False),
        sa.Column("size_width_mm", sa.Integer(), nullable=True),
        sa.Column("size_height_mm", sa.Integer(), nullable=True),
        sa.Column("finish", sa.String(length=50), nullable=True),
        sa.Column("look", sa.String(length=100), nullable=True),
        sa.Column("color", sa.String(length=50), nullable=True),
        sa.Column("material", sa.String(length=100), nullable=True),
        sa.Column("vendor", sa.String(length=100), nullable=False, server_default="Nitco"),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("swatch_data", sa.Text(), nullable=True),
        sa.Column("swatch_url", sa.String(length=500), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("image_data", sa.Text(), nullable=True),
        sa.Column("additional_images", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("display_order", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_floor_tiles_id"), "floor_tiles", ["id"], unique=False)
    op.create_index(op.f("ix_floor_tiles_product_code"), "floor_tiles", ["product_code"], unique=True)
    op.create_index(op.f("ix_floor_tiles_name"), "floor_tiles", ["name"], unique=False)
    op.create_index(op.f("ix_floor_tiles_size"), "floor_tiles", ["size"], unique=False)
    op.create_index(op.f("ix_floor_tiles_finish"), "floor_tiles", ["finish"], unique=False)
    op.create_index(op.f("ix_floor_tiles_look"), "floor_tiles", ["look"], unique=False)
    op.create_index(op.f("ix_floor_tiles_color"), "floor_tiles", ["color"], unique=False)
    op.create_index(op.f("ix_floor_tiles_vendor"), "floor_tiles", ["vendor"], unique=False)
    op.create_index(op.f("ix_floor_tiles_is_active"), "floor_tiles", ["is_active"], unique=False)
    op.create_index("idx_floor_tile_vendor_finish", "floor_tiles", ["vendor", "finish"], unique=False)
    op.create_index("idx_floor_tile_look_color", "floor_tiles", ["look", "color"], unique=False)
    op.create_index("idx_floor_tile_size_finish", "floor_tiles", ["size", "finish"], unique=False)


def downgrade():
    op.drop_index("idx_floor_tile_size_finish", table_name="floor_tiles")
    op.drop_index("idx_floor_tile_look_color", table_name="floor_tiles")
    op.drop_index("idx_floor_tile_vendor_finish", table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_is_active"), table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_vendor"), table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_color"), table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_look"), table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_finish"), table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_size"), table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_name"), table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_product_code"), table_name="floor_tiles")
    op.drop_index(op.f("ix_floor_tiles_id"), table_name="floor_tiles")
    op.drop_table("floor_tiles")
