"""add_new_midtier_stores

Revision ID: d1e2f3g4h5i6
Revises: c9f8e7d6b5a4
Create Date: 2026-01-05 17:00:00.000000

Adds new mid-tier stores: Pepperfry, Urban Ladder, Wooden Street, Durian
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3g4h5i6"
down_revision: Union[str, Sequence[str], None] = "c9f8e7d6b5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New mid-tier stores to add
NEW_STORES = [
    {"name": "pepperfry", "display_name": "Pepperfry", "budget_tier": "mid_tier", "website_url": "https://www.pepperfry.com"},
    {
        "name": "urbanladder",
        "display_name": "Urban Ladder",
        "budget_tier": "mid_tier",
        "website_url": "https://www.urbanladder.com",
    },
    {
        "name": "woodenstreet",
        "display_name": "Wooden Street",
        "budget_tier": "mid_tier",
        "website_url": "https://www.woodenstreet.com",
    },
    {"name": "durian", "display_name": "Durian", "budget_tier": "mid_tier", "website_url": "https://www.durian.in"},
]


def upgrade() -> None:
    """Add new mid-tier stores."""
    from datetime import datetime

    stores_table = sa.table(
        "stores",
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("budget_tier", sa.String),
        sa.column("website_url", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    now = datetime.utcnow()

    op.bulk_insert(
        stores_table,
        [
            {
                "name": store["name"],
                "display_name": store["display_name"],
                "budget_tier": store["budget_tier"],
                "website_url": store["website_url"],
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for store in NEW_STORES
        ],
    )


def downgrade() -> None:
    """Remove the new stores."""
    op.execute("DELETE FROM stores WHERE name IN ('pepperfry', 'urbanladder', 'woodenstreet', 'durian')")
