#!/usr/bin/env python3
"""
Migrate curated looks from local database to production.

This script exports curated looks and their products from the local database,
then imports them into the production database.

Usage:
    # Export from local to JSON file
    python scripts/migrate_curated_looks_to_prod.py --export

    # Import to production from JSON file
    python scripts/migrate_curated_looks_to_prod.py --import --prod-url "postgresql://..."

    # Or do both with direct connection
    python scripts/migrate_curated_looks_to_prod.py --prod-url "postgresql://..."
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

EXPORT_FILE = "curated_looks_export.json"


def get_local_engine():
    """Get engine for local database."""
    db_url = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
    if not db_url:
        raise ValueError("DATABASE_URL not set")
    return create_engine(db_url)


def get_prod_engine(prod_url: str):
    """Get engine for production database."""
    # Handle asyncpg URL format
    prod_url = prod_url.replace("+asyncpg", "")
    return create_engine(prod_url)


def export_curated_looks(engine) -> dict:
    """Export all curated looks and their products from the database."""
    data = {"looks": [], "products": []}

    with engine.connect() as conn:
        # Export curated_looks
        result = conn.execute(text("""
            SELECT id, title, style_theme, style_description, style_labels,
                   room_type, room_image, visualization_image, room_analysis,
                   total_price, budget_tier, is_published, display_order,
                   created_at, updated_at
            FROM curated_looks
            ORDER BY id
        """))

        for row in result:
            look = {
                "id": row[0],
                "title": row[1],
                "style_theme": row[2],
                "style_description": row[3],
                "style_labels": row[4] if row[4] else [],
                "room_type": row[5],
                "room_image": row[6],
                "visualization_image": row[7],
                "room_analysis": row[8],
                "total_price": float(row[9]) if row[9] else 0,
                "budget_tier": row[10],
                "is_published": row[11],
                "display_order": row[12],
                "created_at": row[13].isoformat() if row[13] else None,
                "updated_at": row[14].isoformat() if row[14] else None,
            }
            data["looks"].append(look)

        print(f"Exported {len(data['looks'])} curated looks")

        # Export curated_look_products
        result = conn.execute(text("""
            SELECT id, curated_look_id, product_id, product_type, quantity, display_order
            FROM curated_look_products
            ORDER BY id
        """))

        for row in result:
            product = {
                "id": row[0],
                "curated_look_id": row[1],
                "product_id": row[2],
                "product_type": row[3],
                "quantity": row[4] or 1,
                "display_order": row[5] or 0,
            }
            data["products"].append(product)

        print(f"Exported {len(data['products'])} curated look products")

    return data


def save_to_file(data: dict, filename: str):
    """Save exported data to JSON file."""
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Saved to {filename}")


def load_from_file(filename: str) -> dict:
    """Load exported data from JSON file."""
    with open(filename, "r") as f:
        return json.load(f)


def import_curated_looks(engine, data: dict, force: bool = False):
    """Import curated looks and their products into the database."""
    with engine.connect() as conn:
        # Check existing looks in production
        result = conn.execute(text("SELECT id FROM curated_looks ORDER BY id"))
        existing_ids = {row[0] for row in result}
        print(f"Production has {len(existing_ids)} existing looks: {sorted(existing_ids)[:10]}...")

        # Filter to only new looks
        new_looks = [look for look in data["looks"] if look["id"] not in existing_ids]

        if not new_looks:
            print("No new looks to import!")
            return

        print(f"Will import {len(new_looks)} new looks")

        if not force:
            response = input("Continue? [y/N]: ")
            if response.lower() != "y":
                print("Aborted")
                return

        # Import looks
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
                "id": look["id"],
                "title": look["title"],
                "style_theme": look["style_theme"],
                "style_description": look["style_description"],
                "style_labels": json.dumps(look["style_labels"]) if look["style_labels"] else "[]",
                "room_type": look["room_type"],
                "room_image": look["room_image"],
                "visualization_image": look["visualization_image"],
                "room_analysis": json.dumps(look["room_analysis"]) if look["room_analysis"] else None,
                "total_price": look["total_price"],
                "budget_tier": look["budget_tier"],
                "is_published": look["is_published"],
                "display_order": look["display_order"],
                "created_at": look["created_at"],
                "updated_at": look["updated_at"],
            })

        print(f"Imported {len(new_looks)} looks")

        # Import products for new looks
        new_look_ids = {look["id"] for look in new_looks}
        new_products = [p for p in data["products"] if p["curated_look_id"] in new_look_ids]

        from datetime import datetime
        now = datetime.utcnow().isoformat()

        for product in new_products:
            conn.execute(text("""
                INSERT INTO curated_look_products
                (id, curated_look_id, product_id, product_type, quantity, display_order, created_at)
                VALUES
                (:id, :curated_look_id, :product_id, :product_type, :quantity, :display_order, CAST(:created_at AS timestamp))
                ON CONFLICT (id) DO NOTHING
            """), {**product, "created_at": now})

        print(f"Imported {len(new_products)} products")

        # Update sequence to avoid ID conflicts
        conn.execute(text("""
            SELECT setval('curated_looks_id_seq', (SELECT MAX(id) FROM curated_looks), true)
        """))
        conn.execute(text("""
            SELECT setval('curated_look_products_id_seq', (SELECT MAX(id) FROM curated_look_products), true)
        """))

        conn.commit()
        print("Done!")


def main():
    parser = argparse.ArgumentParser(description="Migrate curated looks to production")
    parser.add_argument("--export", action="store_true", help="Export from local DB to JSON file")
    parser.add_argument("--import-only", action="store_true", help="Import from JSON file to production")
    parser.add_argument("--prod-url", help="Production database URL")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--file", default=EXPORT_FILE, help=f"Export/import file (default: {EXPORT_FILE})")

    args = parser.parse_args()

    if args.export or not args.import_only:
        # Export from local
        print("=== Exporting from local database ===")
        local_engine = get_local_engine()
        data = export_curated_looks(local_engine)
        save_to_file(data, args.file)

    if args.import_only or args.prod_url:
        # Import to production
        if not args.prod_url:
            print("\nError: --prod-url required for import")
            print("Example: python scripts/migrate_curated_looks_to_prod.py --import-only --prod-url 'postgresql://user:pass@host:5432/db'")
            sys.exit(1)

        print("\n=== Importing to production database ===")
        data = load_from_file(args.file)
        prod_engine = get_prod_engine(args.prod_url)
        import_curated_looks(prod_engine, data, force=args.force)


if __name__ == "__main__":
    main()
