#!/usr/bin/env python3
"""
Sync curated looks between local and production databases.

Usage:
    # Push local looks to production
    python scripts/sync_curated_looks.py --push --prod-url "postgresql://..."

    # Pull production looks to local
    python scripts/sync_curated_looks.py --pull --prod-url "postgresql://..."

    # Dry run (show what would be synced)
    python scripts/sync_curated_looks.py --pull --prod-url "postgresql://..." --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def get_engine(db_url: str):
    """Create engine from URL."""
    return create_engine(db_url.replace("+asyncpg", ""), isolation_level="AUTOCOMMIT")


def get_looks_from_db(engine) -> dict:
    """Get all curated looks and products from a database."""
    data = {"looks": [], "products": []}

    with engine.connect() as conn:
        # Get looks
        result = conn.execute(text("""
            SELECT id, title, style_theme, style_description, style_labels,
                   room_type, room_image, visualization_image, room_analysis,
                   total_price, budget_tier, is_published, display_order,
                   created_at, updated_at
            FROM curated_looks ORDER BY id
        """))
        for row in result:
            data["looks"].append({
                "id": row[0], "title": row[1], "style_theme": row[2],
                "style_description": row[3], "style_labels": row[4] or [],
                "room_type": row[5], "room_image": row[6], "visualization_image": row[7],
                "room_analysis": row[8], "total_price": float(row[9]) if row[9] else 0,
                "budget_tier": row[10], "is_published": row[11], "display_order": row[12],
                "created_at": row[13].isoformat() if row[13] else None,
                "updated_at": row[14].isoformat() if row[14] else None,
            })

        # Get products
        result = conn.execute(text("""
            SELECT id, curated_look_id, product_id, product_type, quantity, display_order
            FROM curated_look_products ORDER BY id
        """))
        for row in result:
            data["products"].append({
                "id": row[0], "curated_look_id": row[1], "product_id": row[2],
                "product_type": row[3], "quantity": row[4] or 1, "display_order": row[5] or 0,
            })

    return data


def sync_looks(source_engine, target_engine, dry_run: bool = False):
    """Sync looks from source to target database."""
    source_data = get_looks_from_db(source_engine)
    target_data = get_looks_from_db(target_engine)

    source_look_ids = {l["id"] for l in source_data["looks"]}
    target_look_ids = {l["id"] for l in target_data["looks"]}

    new_look_ids = source_look_ids - target_look_ids
    new_looks = [l for l in source_data["looks"] if l["id"] in new_look_ids]

    print(f"Source has {len(source_data['looks'])} looks, {len(source_data['products'])} products")
    print(f"Target has {len(target_data['looks'])} looks, {len(target_data['products'])} products")
    print(f"New looks to sync: {len(new_looks)} (IDs: {sorted(new_look_ids)})")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        return

    if not new_looks:
        print("Nothing to sync!")
        return

    # Import new looks
    with target_engine.connect() as conn:
        for look in new_looks:
            conn.execute(text("""
                INSERT INTO curated_looks
                (id, title, style_theme, style_description, style_labels,
                 room_type, room_image, visualization_image, room_analysis,
                 total_price, budget_tier, is_published, display_order,
                 created_at, updated_at)
                VALUES
                (:id, :title, :style_theme, :style_description, CAST(:style_labels AS jsonb),
                 :room_type, :room_image, :visualization_image, CAST(:room_analysis AS jsonb),
                 :total_price, :budget_tier, :is_published, :display_order,
                 CAST(:created_at AS timestamp), CAST(:updated_at AS timestamp))
                ON CONFLICT (id) DO NOTHING
            """), {
                **look,
                "style_labels": json.dumps(look["style_labels"]) if look["style_labels"] else "[]",
                "room_analysis": json.dumps(look["room_analysis"]) if look["room_analysis"] else None,
            })
        print(f"Imported {len(new_looks)} looks")

        # Import products for new looks
        target_pairs = set()
        result = conn.execute(text("SELECT curated_look_id, product_id FROM curated_look_products"))
        target_pairs = {(row[0], row[1]) for row in result}

        new_products = [
            p for p in source_data["products"]
            if p["curated_look_id"] in new_look_ids
            and (p["curated_look_id"], p["product_id"]) not in target_pairs
        ]

        now = datetime.utcnow().isoformat()
        for product in new_products:
            conn.execute(text("""
                INSERT INTO curated_look_products
                (curated_look_id, product_id, product_type, quantity, display_order, created_at)
                VALUES (:curated_look_id, :product_id, :product_type, :quantity, :display_order, CAST(:created_at AS timestamp))
            """), {**product, "created_at": now})
        print(f"Imported {len(new_products)} products")

        # Update sequences
        conn.execute(text("SELECT setval(pg_get_serial_sequence('curated_looks', 'id'), (SELECT COALESCE(MAX(id), 1) FROM curated_looks), true)"))
        conn.execute(text("SELECT setval(pg_get_serial_sequence('curated_look_products', 'id'), (SELECT COALESCE(MAX(id), 1) FROM curated_look_products), true)"))

    print("Sync complete!")


def main():
    parser = argparse.ArgumentParser(description="Sync curated looks between databases")
    parser.add_argument("--push", action="store_true", help="Push local → production")
    parser.add_argument("--pull", action="store_true", help="Pull production → local")
    parser.add_argument("--prod-url", required=True, help="Production database URL")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without making changes")

    args = parser.parse_args()

    if not args.push and not args.pull:
        print("Error: Specify --push or --pull")
        sys.exit(1)

    local_url = os.getenv("DATABASE_URL", "")
    if not local_url:
        print("Error: DATABASE_URL not set in environment")
        sys.exit(1)

    local_engine = get_engine(local_url)
    prod_engine = get_engine(args.prod_url)

    if args.push:
        print("=== Pushing Local → Production ===")
        sync_looks(local_engine, prod_engine, dry_run=args.dry_run)
    else:
        print("=== Pulling Production → Local ===")
        sync_looks(prod_engine, local_engine, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
