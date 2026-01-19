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
down_revision: Union[str, Sequence[str], None] = "30c8f8403d7c"  # add_budget_tier_to_homestyling_sessions
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Store data with budget tiers
# Budget tiers: pocket_friendly (<2L), mid_tier (2-8L), premium (8-15L), luxury (15L+)
STORES = [
    # Pocket-friendly stores (for <₹2L looks)
    {"name": "woodenstreet", "display_name": "Wooden Street", "budget_tier": "pocket_friendly"},
    {"name": "urbanladder", "display_name": "Urban Ladder", "budget_tier": "pocket_friendly"},
    {"name": "durian", "display_name": "Durian", "budget_tier": "pocket_friendly"},
    {"name": "homecentre", "display_name": "Home Centre", "budget_tier": "pocket_friendly"},
    {"name": "pepperfry", "display_name": "Pepperfry", "budget_tier": "pocket_friendly"},
    # Mid-tier stores (for ₹2L – ₹8L looks)
    {"name": "modernquests", "display_name": "Modern Quests", "budget_tier": "mid_tier"},
    {"name": "masonhome", "display_name": "Mason Home", "budget_tier": "mid_tier"},
    {"name": "fleck", "display_name": "Fleck", "budget_tier": "mid_tier"},
    {"name": "nicobar", "display_name": "Nicobar", "budget_tier": "mid_tier"},
    {"name": "palasa", "display_name": "Palasa", "budget_tier": "mid_tier"},
    {"name": "ellementry", "display_name": "Ellementry", "budget_tier": "mid_tier"},
    {"name": "objectry", "display_name": "Objectry", "budget_tier": "mid_tier"},
    {"name": "pelicanessentials", "display_name": "Pelican Essentials", "budget_tier": "mid_tier"},
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
    from sqlalchemy import inspect
    from datetime import datetime

    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # Create stores table if it doesn't exist
    if "stores" not in tables:
        op.create_table(
            "stores",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("display_name", sa.String(100), nullable=True),
            sa.Column(
                "budget_tier",
                sa.String(50),
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

    # Insert store data (use upsert logic - insert if not exists)
    now = datetime.utcnow()

    for store in STORES:
        # Check if store already exists
        result = conn.execute(
            sa.text("SELECT id FROM stores WHERE name = :name"),
            {"name": store["name"]}
        )
        exists = result.fetchone()

        if not exists:
            conn.execute(
                sa.text("""
                    INSERT INTO stores (name, display_name, budget_tier, is_active, created_at, updated_at)
                    VALUES (:name, :display_name, :budget_tier, :is_active, :created_at, :updated_at)
                """),
                {
                    "name": store["name"],
                    "display_name": store["display_name"],
                    "budget_tier": store["budget_tier"],
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )


def downgrade() -> None:
    """Downgrade schema."""
    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if "stores" in tables:
        op.drop_index(op.f("ix_stores_is_active"), table_name="stores")
        op.drop_index(op.f("ix_stores_budget_tier"), table_name="stores")
        op.drop_index(op.f("ix_stores_name"), table_name="stores")
        op.drop_table("stores")
