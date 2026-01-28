#!/usr/bin/env python3
"""
Update luxury curated look titles to elegant marketing names.

Usage:
    # Preview new titles (dry run)
    python scripts/update_luxury_titles.py --dry-run

    # Actually update titles
    python scripts/update_luxury_titles.py
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_session
from database.models import CuratedLook


# Elegant marketing titles for the 18 luxury looks
LUXURY_TITLES = {
    # Modern Luxury (171-176)
    171: "Opulent Modern Retreat",
    172: "Gilded Contemporary Haven",
    173: "Sophisticated Urban Oasis",
    174: "Refined Elegance Studio",
    175: "Prestigious Modern Suite",
    176: "Grand Living Experience",

    # Modern (177-182)
    177: "Sleek Serenity Lounge",
    178: "Contemporary Comfort Zone",
    179: "Modern Artisan Retreat",
    180: "Chic Urban Sanctuary",
    181: "Minimalist Luxe Haven",
    182: "Curated Modern Living",

    # Indian Contemporary (183-188)
    183: "Heritage Fusion Suite",
    184: "Royal Indian Modern",
    185: "Artisan Heritage Lounge",
    186: "Indo-Modern Elegance",
    187: "Contemporary Desi Retreat",
    188: "Luxe Indian Living",
}


def update_titles(dry_run: bool = False):
    """Update titles for luxury looks."""
    look_ids = list(range(171, 189))  # IDs 171-188

    print(f"{'[DRY RUN] ' if dry_run else ''}Updating titles for {len(look_ids)} luxury looks\n")

    with get_db_session() as db:
        updates = []

        for look_id in look_ids:
            look = db.query(CuratedLook).filter(CuratedLook.id == look_id).first()
            if not look:
                continue

            new_title = LUXURY_TITLES.get(look_id, look.title)

            updates.append({
                'id': look_id,
                'old_title': look.title,
                'new_title': new_title,
                'style': look.style_theme,
                'look': look,
            })

        # Print updates
        print(f"{'ID':<5} {'Style':<20} {'New Title':<40}")
        print("-" * 70)

        for update in updates:
            print(f"{update['id']:<5} {update['style']:<20} {update['new_title']:<40}")

            if not dry_run:
                update['look'].title = update['new_title']

        if not dry_run:
            db.commit()
            print(f"\n✓ Updated {len(updates)} titles")
        else:
            print(f"\n[DRY RUN] Would update {len(updates)} titles")


def main():
    parser = argparse.ArgumentParser(description="Update luxury look titles")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")

    args = parser.parse_args()
    update_titles(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
