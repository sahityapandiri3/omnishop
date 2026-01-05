"""update_budget_tier_enum_values

Revision ID: c9f8e7d6b5a4
Revises: b8d4e5f6a7c9
Create Date: 2026-01-05 16:00:00.000000

Updates the budgettier enum from:
  - essential, value, mid, premium, ultra_luxury
To:
  - pocket_friendly, mid_tier, premium, luxury
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f8e7d6b5a4"
down_revision: Union[str, Sequence[str], None] = "b8d4e5f6a7c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade the budgettier enum to use new values.

    PostgreSQL doesn't allow easy enum modification, so we:
    1. Add new enum values
    2. Update existing data to new values
    3. Remove old enum values (by recreating the type)
    """
    # Step 1: Add new enum values to the existing type
    op.execute("ALTER TYPE budgettier ADD VALUE IF NOT EXISTS 'pocket_friendly'")
    op.execute("ALTER TYPE budgettier ADD VALUE IF NOT EXISTS 'mid_tier'")
    op.execute("ALTER TYPE budgettier ADD VALUE IF NOT EXISTS 'luxury'")
    # 'premium' already exists, no need to add

    # Step 2: Update existing data in curated_looks table
    op.execute("UPDATE curated_looks SET budget_tier = 'pocket_friendly' WHERE budget_tier = 'essential'")
    op.execute("UPDATE curated_looks SET budget_tier = 'mid_tier' WHERE budget_tier = 'value'")
    op.execute("UPDATE curated_looks SET budget_tier = 'mid_tier' WHERE budget_tier = 'mid'")
    # 'premium' stays as 'premium'
    op.execute("UPDATE curated_looks SET budget_tier = 'luxury' WHERE budget_tier = 'ultra_luxury'")

    # Step 3: Update existing data in homestyling_sessions table
    op.execute("UPDATE homestyling_sessions SET budget_tier = 'pocket_friendly' WHERE budget_tier = 'essential'")
    op.execute("UPDATE homestyling_sessions SET budget_tier = 'mid_tier' WHERE budget_tier = 'value'")
    op.execute("UPDATE homestyling_sessions SET budget_tier = 'mid_tier' WHERE budget_tier = 'mid'")
    # 'premium' stays as 'premium'
    op.execute("UPDATE homestyling_sessions SET budget_tier = 'luxury' WHERE budget_tier = 'ultra_luxury'")

    # Step 4: Update existing data in stores table (if any old values exist)
    op.execute("UPDATE stores SET budget_tier = 'pocket_friendly' WHERE budget_tier = 'essential'")
    op.execute("UPDATE stores SET budget_tier = 'mid_tier' WHERE budget_tier = 'value'")
    op.execute("UPDATE stores SET budget_tier = 'mid_tier' WHERE budget_tier = 'mid'")
    # 'premium' stays as 'premium'
    op.execute("UPDATE stores SET budget_tier = 'luxury' WHERE budget_tier = 'ultra_luxury'")


def downgrade() -> None:
    """
    Downgrade back to old enum values.
    Note: This is a lossy operation - mid_tier maps back to mid, pocket_friendly to essential, etc.
    """
    # Step 1: Add old enum values back
    op.execute("ALTER TYPE budgettier ADD VALUE IF NOT EXISTS 'essential'")
    op.execute("ALTER TYPE budgettier ADD VALUE IF NOT EXISTS 'value'")
    op.execute("ALTER TYPE budgettier ADD VALUE IF NOT EXISTS 'mid'")
    op.execute("ALTER TYPE budgettier ADD VALUE IF NOT EXISTS 'ultra_luxury'")

    # Step 2: Update data back to old values
    op.execute("UPDATE curated_looks SET budget_tier = 'essential' WHERE budget_tier = 'pocket_friendly'")
    op.execute("UPDATE curated_looks SET budget_tier = 'mid' WHERE budget_tier = 'mid_tier'")
    op.execute("UPDATE curated_looks SET budget_tier = 'ultra_luxury' WHERE budget_tier = 'luxury'")

    op.execute("UPDATE homestyling_sessions SET budget_tier = 'essential' WHERE budget_tier = 'pocket_friendly'")
    op.execute("UPDATE homestyling_sessions SET budget_tier = 'mid' WHERE budget_tier = 'mid_tier'")
    op.execute("UPDATE homestyling_sessions SET budget_tier = 'ultra_luxury' WHERE budget_tier = 'luxury'")

    op.execute("UPDATE stores SET budget_tier = 'essential' WHERE budget_tier = 'pocket_friendly'")
    op.execute("UPDATE stores SET budget_tier = 'mid' WHERE budget_tier = 'mid_tier'")
    op.execute("UPDATE stores SET budget_tier = 'ultra_luxury' WHERE budget_tier = 'luxury'")
