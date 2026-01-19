"""
Script to identify and remove duplicate curated looks in the database.
Duplicates are identified by matching titles.
Keeps the look with more products, or the most recently updated one if equal.
"""
import asyncio
import os
import sys
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from core.database import AsyncSessionLocal
from database.models import CuratedLook, CuratedLookProduct


async def find_duplicates():
    """Find duplicate curated looks by title."""
    async with AsyncSessionLocal() as db:
        # Get all looks with their product counts
        query = (
            select(CuratedLook)
            .options(selectinload(CuratedLook.products))
            .order_by(CuratedLook.title)
        )
        result = await db.execute(query)
        looks = result.scalars().all()

        # Group by title
        by_title = defaultdict(list)
        for look in looks:
            by_title[look.title].append(look)

        # Find duplicates
        duplicates = {title: looks for title, looks in by_title.items() if len(looks) > 1}

        print(f"\n{'='*60}")
        print(f"DUPLICATE CURATED LOOKS REPORT")
        print(f"{'='*60}\n")

        if not duplicates:
            print("No duplicates found!")
            return []

        print(f"Found {len(duplicates)} titles with duplicates:\n")

        to_delete = []

        for title, looks in duplicates.items():
            print(f"\n📦 '{title}' - {len(looks)} copies")
            print("-" * 50)

            # Sort by product count (desc), then by updated_at (desc)
            looks_sorted = sorted(
                looks,
                key=lambda x: (len(x.products), x.updated_at),
                reverse=True
            )

            # Keep the first one (most products / most recent)
            keep = looks_sorted[0]
            delete_these = looks_sorted[1:]

            for look in looks_sorted:
                is_keep = look.id == keep.id
                status = "✅ KEEP" if is_keep else "❌ DELETE"
                print(f"  {status} ID: {look.id}")
                print(f"       Products: {len(look.products)}")
                print(f"       Style: {look.style_theme}")
                print(f"       Budget: {look.budget_tier}")
                print(f"       Published: {look.is_published}")
                print(f"       Updated: {look.updated_at}")
                print()

            to_delete.extend(delete_these)

        print(f"\n{'='*60}")
        print(f"SUMMARY: {len(to_delete)} looks to delete")
        print(f"{'='*60}\n")

        return to_delete


async def delete_duplicates(looks_to_delete: list, dry_run: bool = True):
    """Delete duplicate looks."""
    if not looks_to_delete:
        print("Nothing to delete.")
        return

    if dry_run:
        print("🔍 DRY RUN - No changes will be made")
        print(f"Would delete {len(looks_to_delete)} looks:")
        for look in looks_to_delete:
            print(f"  - ID {look.id}: {look.title}")
        return

    async with AsyncSessionLocal() as db:
        for look in looks_to_delete:
            # Delete associated products first
            await db.execute(
                delete(CuratedLookProduct).where(CuratedLookProduct.curated_look_id == look.id)
            )
            # Delete the look
            await db.execute(
                delete(CuratedLook).where(CuratedLook.id == look.id)
            )
            print(f"  Deleted: ID {look.id} - {look.title}")

        await db.commit()
        print(f"\n✅ Successfully deleted {len(looks_to_delete)} duplicate looks")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Remove duplicate curated looks")
    parser.add_argument("--delete", action="store_true", help="Actually delete duplicates (default is dry run)")
    args = parser.parse_args()

    to_delete = await find_duplicates()

    if to_delete:
        print("\n" + "="*60)
        if args.delete:
            confirm = input("⚠️  Are you sure you want to delete these looks? (yes/no): ")
            if confirm.lower() == "yes":
                await delete_duplicates(to_delete, dry_run=False)
            else:
                print("Aborted.")
        else:
            print("To actually delete duplicates, run with --delete flag")
            await delete_duplicates(to_delete, dry_run=True)


if __name__ == "__main__":
    asyncio.run(main())
