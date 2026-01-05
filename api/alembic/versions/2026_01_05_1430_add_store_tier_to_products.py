"""add_stores_table

Revision ID: b8d4e5f6a7c9
Revises: 30c8f8403d7c
Create Date: 2026-01-05 14:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4e5f6a7c9"
down_revision: Union[str, Sequence[str], None] = "30c8f8403d7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Store data with budget tiers
# Budget tiers: essential (<2L), value (2-4L), mid (4-8L), premium (8-15L), ultra_luxury (15L+)
STORES = [
    # Mid-range stores (for ₹4L – ₹8L looks)
    {"name": "modernquests", "display_name": "Modern Quests", "budget_tier": "mid"},
    {"name": "masonhome", "display_name": "Mason Home", "budget_tier": "mid"},
    {"name": "fleck", "display_name": "Fleck", "budget_tier": "mid"},
    {"name": "nicobar", "display_name": "Nicobar", "budget_tier": "mid"},
    {"name": "palasa", "display_name": "Palasa", "budget_tier": "mid"},
    {"name": "ellementry", "display_name": "Ellementry", "budget_tier": "mid"},
    {"name": "objectry", "display_name": "Objectry", "budget_tier": "mid"},
    {"name": "pelicanessentials", "display_name": "Pelican Essentials", "budget_tier": "mid"},
    # Premium stores (for ₹8L – ₹15L looks)
    {"name": "thehouseofthings", "display_name": "The House of Things", "budget_tier": "premium"},
    {"name": "phantomhands", "display_name": "Phantom Hands", "budget_tier": "premium"},
    {"name": "magari", "display_name": "Magari", "budget_tier": "premium"},
    {"name": "obeetee", "display_name": "Obeetee", "budget_tier": "premium"},
    {"name": "sageliving", "display_name": "Sage Living", "budget_tier": "premium"},
    {"name": "josmo", "display_name": "Josmo", "budget_tier": "premium"},
]


def upgrade() -> None:
    """Upgrade schema."""
    # Create stores table (budgettier enum already exists from curated_looks migration)
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column(
            "budget_tier",
            sa.Enum("essential", "value", "mid", "premium", "ultra_luxury", name="budgettier", create_type=False),
            nullable=True,
        ),
        sa.Column("website_url", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stores_name"), "stores", ["name"], unique=True)
    op.create_index(op.f("ix_stores_budget_tier"), "stores", ["budget_tier"], unique=False)
    op.create_index(op.f("ix_stores_is_active"), "stores", ["is_active"], unique=False)

    # Insert store data
    stores_table = sa.table(
        "stores",
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("budget_tier", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    from datetime import datetime

    now = datetime.utcnow()

    op.bulk_insert(
        stores_table,
        [
            {
                "name": store["name"],
                "display_name": store["display_name"],
                "budget_tier": store["budget_tier"],
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for store in STORES
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_stores_is_active"), table_name="stores")
    op.drop_index(op.f("ix_stores_budget_tier"), table_name="stores")
    op.drop_index(op.f("ix_stores_name"), table_name="stores")
    op.drop_table("stores")
