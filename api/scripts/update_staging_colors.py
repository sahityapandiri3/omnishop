"""
Update wall colors on any database (local or staging).

Usage:
    # For local database:
    python -m scripts.update_staging_colors

    # For staging database (provide DATABASE_URL):
    DATABASE_URL="postgresql://user:pass@host:5432/db" python -m scripts.update_staging_colors

    # Or use Railway CLI:
    railway run python -m scripts.update_staging_colors
"""

import asyncio
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Color family mapping
FAMILY_MAPPING = {
    "whites_offwhites": "whites_offwhites",
    "greys": "greys",
    "blues": "blues",
    "browns": "browns",
    "reds_oranges": "reds_oranges",
    "yellows_greens": "yellows_greens",
    "purples_pinks": "purples_pinks",
}


async def update_colors(database_url: str):
    """Update wall colors in the specified database."""

    # Convert to async URL if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"Connecting to database...")
    print(f"  URL: {database_url[:50]}...")

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Load scraped colors
    json_file = os.path.join(os.path.dirname(__file__), "asian_paints_colors.json")
    with open(json_file, "r") as f:
        colors = json.load(f)

    print(f"Loaded {len(colors)} colors from {json_file}")

    async with async_session() as session:
        # Check current count
        result = await session.execute(text("SELECT COUNT(*) FROM wall_colors"))
        current_count = result.scalar()
        print(f"\nCurrent wall_colors count: {current_count}")

        # Delete all existing colors
        print("Deleting existing wall colors...")
        result = await session.execute(text("DELETE FROM wall_colors"))
        print(f"Deleted {result.rowcount} colors")

        # Insert new colors
        print("\nInserting new Asian Paints colors...")

        # Group by family
        colors_by_family = {}
        for c in colors:
            family = c["family"]
            if family not in colors_by_family:
                colors_by_family[family] = []
            colors_by_family[family].append(c)

        total_inserted = 0
        for family_name, family_colors in colors_by_family.items():
            print(f"  Inserting {len(family_colors)} {family_name} colors...")

            for display_order, color_data in enumerate(family_colors):
                await session.execute(
                    text(
                        """
                        INSERT INTO wall_colors (code, name, hex_value, family, brand, is_active, display_order, created_at)
                        VALUES (:code, :name, :hex_value, :family, :brand, :is_active, :display_order, NOW())
                    """
                    ),
                    {
                        "code": color_data["code"],
                        "name": color_data["name"],
                        "hex_value": color_data["hex_value"],
                        "family": family_name,
                        "brand": "Asian Paints",
                        "is_active": True,
                        "display_order": display_order,
                    },
                )
                total_inserted += 1

        await session.commit()

        # Verify
        result = await session.execute(text("SELECT COUNT(*) FROM wall_colors"))
        final_count = result.scalar()

        print(f"\n{'='*50}")
        print(f"Successfully imported {total_inserted} colors!")
        print(f"Final wall_colors count: {final_count}")
        print(f"{'='*50}")

        # Show breakdown
        result = await session.execute(
            text(
                """
            SELECT family, COUNT(*) as count
            FROM wall_colors
            GROUP BY family
            ORDER BY family
        """
            )
        )
        print("\nColors by family:")
        for row in result:
            print(f"  {row[0]}: {row[1]} colors")

    await engine.dispose()


async def main():
    # Get database URL from environment or use default
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        # Try to load from .env file
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        database_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not database_url:
        print("ERROR: No DATABASE_URL found!")
        print("\nUsage:")
        print('  DATABASE_URL="postgresql://..." python -m scripts.update_staging_colors')
        print("  or: railway run python -m scripts.update_staging_colors")
        sys.exit(1)

    print("=" * 60)
    print("Asian Paints Color Updater")
    print("=" * 60)

    await update_colors(database_url)


if __name__ == "__main__":
    asyncio.run(main())
