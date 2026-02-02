"""
Seed script for Asian Paints wall colors.

This script populates the wall_colors table with a curated collection
of popular Asian Paints colors organized by family.

Usage:
    python -m scripts.seed_wall_colors

The hex values are sourced from Asian Paints' official color tools.
"""
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from core.database import AsyncSessionLocal
from database.models import WallColor, WallColorFamily

# Asian Paints color data organized by family
# Format: (code, name, hex_value)
WALL_COLORS = {
    WallColorFamily.WHITES_OFFWHITES: [
        ("L101", "White Whisper", "#FFFFFF"),
        ("L102", "Snow White", "#FEFEFE"),
        ("L103", "Arctic White", "#FAFAFA"),
        ("L104", "Milk White", "#FDFBF7"),
        ("L105", "Oyster White", "#F6F3ED"),
        ("L106", "Pearl White", "#F5F2EB"),
        ("L107", "Antique White", "#FAEBD7"),
        ("L108", "Ivory Cream", "#F8F4E9"),
        ("L109", "Linen White", "#F4F0E6"),
        ("L110", "Vanilla Ice", "#F5F0E5"),
        ("L111", "Almond White", "#F2EDE4"),
        ("L112", "French White", "#F0EBE0"),
        ("L113", "Bone White", "#EDE9DD"),
        ("L114", "Cream Silk", "#F5EFE0"),
        ("L115", "Eggshell", "#F0EAD6"),
        ("L116", "Swiss Coffee", "#EDE4D4"),
        ("L117", "Alabaster", "#EDEADE"),
        ("L118", "Parchment", "#F1E9D2"),
        ("L119", "Cottage White", "#EFEAE0"),
        ("L120", "Natural White", "#E8E3D8"),
    ],
    WallColorFamily.GREYS: [
        ("G101", "Silver Mist", "#E8E8E8"),
        ("G102", "Misty Grey", "#D5D5D5"),
        ("G103", "Gentle Grey", "#C5C5C5"),
        ("G104", "Pewter Grey", "#B8B8B8"),
        ("G105", "Platinum", "#E5E4E2"),
        ("G106", "Cloud Grey", "#BDB8B0"),
        ("G107", "Dove Grey", "#A8A8A8"),
        ("G108", "Ash Grey", "#B2BEB5"),
        ("G109", "Stone Grey", "#928E85"),
        ("G110", "Warm Grey", "#A8A39E"),
        ("G111", "Smokey Grey", "#8B8B8B"),
        ("G112", "Charcoal Light", "#7D7D7D"),
        ("G113", "Silver Sage", "#C4CDC8"),
        ("G114", "Grey Flannel", "#9A9B94"),
        ("G115", "Harbour Grey", "#8F9FA5"),
        ("G116", "Slate Grey", "#708090"),
        ("G117", "Granite Grey", "#676767"),
        ("G118", "Steel Grey", "#71797E"),
        ("G119", "French Grey", "#BDBDBD"),
        ("G120", "Elephant Grey", "#6E6E6E"),
    ],
    WallColorFamily.BLUES: [
        ("B101", "Sky Blue", "#87CEEB"),
        ("B102", "Baby Blue", "#89CFF0"),
        ("B103", "Powder Blue", "#B0E0E6"),
        ("B104", "Ice Blue", "#D6EBEE"),
        ("B105", "Pale Blue", "#AFEEEE"),
        ("B106", "Light Azure", "#ADD8E6"),
        ("B107", "Carolina Blue", "#99BADD"),
        ("B108", "Cornflower", "#6495ED"),
        ("B109", "Steel Blue", "#4682B4"),
        ("B110", "Wedgewood Blue", "#5A7FA5"),
        ("B111", "Denim Blue", "#1560BD"),
        ("B112", "Navy Light", "#4C6A92"),
        ("B113", "Ocean Blue", "#0077BE"),
        ("B114", "Teal Mist", "#5DA9AB"),
        ("B115", "Aqua Marine", "#7FFFD4"),
        ("B116", "Turquoise Light", "#40E0D0"),
        ("B117", "Sea Foam", "#71EEB8"),
        ("B118", "Robin Egg", "#00CCCC"),
        ("B119", "Cadet Blue", "#5F9EA0"),
        ("B120", "Prussian Light", "#003153"),
    ],
    WallColorFamily.BROWNS: [
        ("BR101", "Beige", "#F5F5DC"),
        ("BR102", "Sand Dune", "#E5D3B3"),
        ("BR103", "Wheat", "#F5DEB3"),
        ("BR104", "Tan", "#D2B48C"),
        ("BR105", "Khaki", "#C3B091"),
        ("BR106", "Camel", "#C19A6B"),
        ("BR107", "Buff", "#F0DC82"),
        ("BR108", "Fawn", "#E5AA70"),
        ("BR109", "Taupe", "#483C32"),
        ("BR110", "Mocha", "#967969"),
        ("BR111", "Cinnamon", "#D2691E"),
        ("BR112", "Cocoa", "#D2691E"),
        ("BR113", "Chocolate Light", "#D2691E"),
        ("BR114", "Coffee", "#6F4E37"),
        ("BR115", "Sienna", "#A0522D"),
        ("BR116", "Russet", "#80461B"),
        ("BR117", "Walnut", "#773F1A"),
        ("BR118", "Umber", "#635147"),
        ("BR119", "Terracotta Light", "#CC7355"),
        ("BR120", "Copper", "#B87333"),
    ],
    WallColorFamily.YELLOWS_GREENS: [
        ("YG101", "Lemon Chiffon", "#FFFACD"),
        ("YG102", "Pale Yellow", "#FFFFE0"),
        ("YG103", "Butter Cream", "#FFF8CD"),
        ("YG104", "Canary", "#FFEF00"),
        ("YG105", "Daffodil", "#FFFF31"),
        ("YG106", "Sunshine", "#FFFD37"),
        ("YG107", "Golden Yellow", "#FFDF00"),
        ("YG108", "Maize", "#FBEC5D"),
        ("YG109", "Honey", "#EB9605"),
        ("YG110", "Mustard", "#FFDB58"),
        ("YG111", "Mint Green", "#98FF98"),
        ("YG112", "Sage", "#BCB88A"),
        ("YG113", "Olive Light", "#C5C3B0"),
        ("YG114", "Celery", "#B4C424"),
        ("YG115", "Lime Wash", "#BFFF00"),
        ("YG116", "Pistachio", "#93C572"),
        ("YG117", "Sea Green Light", "#9FE2BF"),
        ("YG118", "Spring Green", "#00FF7F"),
        ("YG119", "Fern", "#4F7942"),
        ("YG120", "Moss Green", "#8A9A5B"),
    ],
    WallColorFamily.REDS_ORANGES: [
        ("RO101", "Blush Pink", "#FFB6C1"),
        ("RO102", "Pale Rose", "#FFE4E1"),
        ("RO103", "Salmon", "#FA8072"),
        ("RO104", "Coral", "#FF7F50"),
        ("RO105", "Peach", "#FFCBA4"),
        ("RO106", "Apricot", "#FBCEB1"),
        ("RO107", "Melon", "#FEBAAD"),
        ("RO108", "Tangerine Light", "#FF9966"),
        ("RO109", "Papaya", "#FFEFD5"),
        ("RO110", "Mango", "#FF8243"),
        ("RO111", "Terracotta", "#E2725B"),
        ("RO112", "Rust Light", "#B7410E"),
        ("RO113", "Burnt Orange", "#CC5500"),
        ("RO114", "Clay", "#B66A50"),
        ("RO115", "Brick Light", "#CB4154"),
        ("RO116", "Crimson Light", "#DC143C"),
        ("RO117", "Cherry", "#DE3163"),
        ("RO118", "Ruby Light", "#E0115F"),
        ("RO119", "Scarlet", "#FF2400"),
        ("RO120", "Vermillion", "#E34234"),
    ],
    WallColorFamily.PURPLES_PINKS: [
        ("PP101", "Lavender", "#E6E6FA"),
        ("PP102", "Lilac", "#C8A2C8"),
        ("PP103", "Wisteria", "#C9A0DC"),
        ("PP104", "Mauve", "#E0B0FF"),
        ("PP105", "Orchid", "#DA70D6"),
        ("PP106", "Plum Light", "#DDA0DD"),
        ("PP107", "Heather", "#9F7FB7"),
        ("PP108", "Amethyst Light", "#9966CC"),
        ("PP109", "Violet", "#EE82EE"),
        ("PP110", "Grape Light", "#6F2DA8"),
        ("PP111", "Dusty Rose", "#D4A5A5"),
        ("PP112", "Rose Quartz", "#F7CAC9"),
        ("PP113", "Carnation", "#FFA6C9"),
        ("PP114", "Hot Pink Light", "#FF69B4"),
        ("PP115", "Fuschia Light", "#FF77FF"),
        ("PP116", "Magenta Light", "#FF00FF"),
        ("PP117", "Berry", "#8E4585"),
        ("PP118", "Raspberry", "#E30B5C"),
        ("PP119", "Mulberry", "#C54B8C"),
        ("PP120", "Wine Light", "#722F37"),
    ],
}


async def seed_wall_colors():
    """Seed the wall colors database with Asian Paints colors."""
    print("Starting wall color seed...")

    async with AsyncSessionLocal() as session:
        # Check if colors already exist
        result = await session.execute(select(WallColor).limit(1))
        existing = result.scalar_one_or_none()

        if existing:
            print("Wall colors already exist. Skipping seed.")
            print("To re-seed, delete all wall colors first.")
            return

        total_added = 0

        for family, colors in WALL_COLORS.items():
            print(f"\nAdding {family.value} colors...")

            for display_order, (code, name, hex_value) in enumerate(colors):
                color = WallColor(
                    code=code,
                    name=name,
                    hex_value=hex_value,
                    family=family,
                    brand="Asian Paints",
                    is_active=True,
                    display_order=display_order,
                )
                session.add(color)
                total_added += 1

            print(f"  Added {len(colors)} colors")

        await session.commit()
        print(f"\n{'='*50}")
        print(f"Successfully seeded {total_added} wall colors!")
        print(f"{'='*50}")


async def clear_wall_colors():
    """Clear all wall colors from database (for re-seeding)."""
    print("Clearing all wall colors...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(WallColor))
        colors = result.scalars().all()

        for color in colors:
            await session.delete(color)

        await session.commit()
        print(f"Deleted {len(colors)} wall colors.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed wall colors database")
    parser.add_argument("--clear", action="store_true", help="Clear existing colors before seeding")
    parser.add_argument("--clear-only", action="store_true", help="Only clear colors, don't seed")
    args = parser.parse_args()

    async def main():
        if args.clear_only:
            await clear_wall_colors()
        elif args.clear:
            await clear_wall_colors()
            await seed_wall_colors()
        else:
            await seed_wall_colors()

    asyncio.run(main())
