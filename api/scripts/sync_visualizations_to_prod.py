#!/usr/bin/env python3
"""
Sync visualization images and titles from local database to production.

This script updates the visualization_image and title fields for curated looks
that exist in both databases.

Usage:
    # Preview what would be updated (dry run)
    python scripts/sync_visualizations_to_prod.py --prod-url "postgresql://..." --dry-run

    # Actually sync visualizations and titles
    python scripts/sync_visualizations_to_prod.py --prod-url "postgresql://..."

    # Sync specific look IDs
    python scripts/sync_visualizations_to_prod.py --prod-url "postgresql://..." --ids 171,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def get_engine(db_url: str):
    """Create engine from URL."""
    return create_engine(db_url.replace("+asyncpg", ""), isolation_level="AUTOCOMMIT")


def get_looks_needing_sync(local_engine, prod_engine, specific_ids: list = None):
    """Find looks that need syncing (visualization or title differences)."""
    needs_sync = []

    with local_engine.connect() as local_conn, prod_engine.connect() as prod_conn:
        # Get looks from local
        if specific_ids:
            id_list = ",".join(str(id) for id in specific_ids)
            query = f"""
                SELECT id, title, visualization_image
                FROM curated_looks
                WHERE id IN ({id_list})
                ORDER BY id
            """
        else:
            query = """
                SELECT id, title, visualization_image
                FROM curated_looks
                WHERE visualization_image IS NOT NULL
                ORDER BY id
            """

        local_looks = {}
        result = local_conn.execute(text(query))
        for row in result:
            local_looks[row[0]] = {"title": row[1], "visualization_image": row[2]}

        print(f"Local DB: {len(local_looks)} looks to check")

        # Check which ones need updating in production
        if not local_looks:
            return []

        id_list = ",".join(str(id) for id in local_looks.keys())
        result = prod_conn.execute(text(f"""
            SELECT id, title, visualization_image IS NOT NULL as has_viz
            FROM curated_looks
            WHERE id IN ({id_list})
            ORDER BY id
        """))

        for row in result:
            look_id = row[0]
            prod_title = row[1]
            has_viz = row[2]

            local_data = local_looks[look_id]
            local_title = local_data["title"]
            local_viz = local_data["visualization_image"]

            # Check if title or visualization needs updating
            title_changed = prod_title != local_title
            viz_missing = not has_viz and local_viz

            if title_changed or viz_missing:
                needs_sync.append({
                    "id": look_id,
                    "old_title": prod_title,
                    "new_title": local_title,
                    "title_changed": title_changed,
                    "viz_missing": viz_missing,
                    "viz_size": len(local_viz) if local_viz else 0,
                    "visualization_image": local_viz,
                })

    return needs_sync


def sync_looks(prod_engine, looks_to_sync: list, dry_run: bool = False):
    """Sync visualization images and titles to production."""
    if not looks_to_sync:
        print("Nothing to sync!")
        return

    print(f"\nWill sync {len(looks_to_sync)} look(s):\n")
    print(f"{'ID':<5} {'Change':<15} {'Details':<60}")
    print("-" * 85)

    for look in looks_to_sync:
        changes = []
        if look['title_changed']:
            changes.append('title')
        if look['viz_missing']:
            changes.append(f"viz ({look['viz_size']:,} bytes)")
        change_str = ' + '.join(changes)

        if look['title_changed']:
            detail = f"{look['old_title'][:28]} → {look['new_title'][:28]}"
        else:
            detail = look['new_title'][:58]

        print(f"{look['id']:<5} {change_str:<15} {detail:<60}")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        return

    print("\nSyncing...")
    with prod_engine.connect() as conn:
        for look in looks_to_sync:
            # Build update query based on what needs updating
            updates = ["updated_at = NOW()"]
            params = {"id": look["id"]}

            if look['title_changed']:
                updates.append("title = :title")
                params["title"] = look["new_title"]

            if look['viz_missing']:
                updates.append("visualization_image = :viz")
                params["viz"] = look["visualization_image"]

            query = f"UPDATE curated_looks SET {', '.join(updates)} WHERE id = :id"
            conn.execute(text(query), params)

            changes = []
            if look['title_changed']:
                changes.append('title')
            if look['viz_missing']:
                changes.append('viz')
            print(f"  Updated ID {look['id']}: {' + '.join(changes)}")

    print("\nSync complete!")


def main():
    parser = argparse.ArgumentParser(description="Sync visualization images and titles to production")
    parser.add_argument("--prod-url", required=True, help="Production database URL")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--ids", help="Comma-separated list of specific look IDs to sync")

    args = parser.parse_args()

    local_url = os.getenv("DATABASE_URL", "")
    if not local_url:
        print("Error: DATABASE_URL not set in environment")
        sys.exit(1)

    specific_ids = None
    if args.ids:
        specific_ids = [int(id.strip()) for id in args.ids.split(",")]
        print(f"Targeting specific IDs: {specific_ids}")

    local_engine = get_engine(local_url)
    prod_engine = get_engine(args.prod_url)

    print("=== Syncing Curated Looks: Local → Production ===\n")

    looks_to_sync = get_looks_needing_sync(local_engine, prod_engine, specific_ids)
    sync_looks(prod_engine, looks_to_sync, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
