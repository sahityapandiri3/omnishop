"""
Import scraped Asian Paints colors into the database.

Usage:
    python -m scripts.import_asian_paints_colors
"""

import asyncio
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select

from core.database import AsyncSessionLocal
from database.models import WallColor, WallColorFamily

# Map our family names to the enum values
FAMILY_TO_ENUM = {
    "whites_offwhites": WallColorFamily.WHITES_OFFWHITES,
    "greys": WallColorFamily.GREYS,
    "blues": WallColorFamily.BLUES,
    "browns": WallColorFamily.BROWNS,
    "reds_oranges": WallColorFamily.REDS_ORANGES,
    "yellows_greens": WallColorFamily.YELLOWS_GREENS,
    "purples_pinks": WallColorFamily.PURPLES_PINKS,
}


async def import_colors():
    """Import colors from JSON file to database."""

    # Load scraped colors
    json_file = "/Users/sahityapandiri/Omnishop/api/scripts/asian_paints_colors.json"
    with open(json_file, "r") as f:
        colors = json.load(f)

    print(f"Loaded {len(colors)} colors from {json_file}")

    async with AsyncSessionLocal() as session:
        # First, delete all existing colors
        print("\nDeleting existing wall colors...")
        result = await session.execute(delete(WallColor))
        print(f"Deleted {result.rowcount} existing colors")

        # Insert new colors
        print("\nInserting new colors...")

        # Group by family for display_order
        colors_by_family = {}
        for c in colors:
            family = c["family"]
            if family not in colors_by_family:
                colors_by_family[family] = []
            colors_by_family[family].append(c)

        total_inserted = 0
        for family_name, family_colors in colors_by_family.items():
            family_enum = FAMILY_TO_ENUM.get(family_name)
            if not family_enum:
                print(f"  Warning: Unknown family '{family_name}', skipping {len(family_colors)} colors")
                continue

            print(f"  Inserting {len(family_colors)} {family_name} colors...")

            for display_order, color_data in enumerate(family_colors):
                color = WallColor(
                    code=color_data["code"],
                    name=color_data["name"],
                    hex_value=color_data["hex_value"],
                    family=family_enum,
                    brand="Asian Paints",
                    is_active=True,
                    display_order=display_order,
                )
                session.add(color)
                total_inserted += 1

        await session.commit()
        print(f"\n{'='*50}")
        print(f"Successfully imported {total_inserted} Asian Paints colors!")
        print(f"{'='*50}")

        # Verify
        print("\nVerification:")
        for family_name, family_enum in FAMILY_TO_ENUM.items():
            result = await session.execute(select(WallColor).where(WallColor.family == family_enum))
            count = len(result.scalars().all())
            print(f"  {family_name}: {count} colors")


async def main():
    print("=" * 60)
    print("Asian Paints Color Importer")
    print("=" * 60)
    await import_colors()


if __name__ == "__main__":
    asyncio.run(main())
