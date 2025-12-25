"""
Migrate only style classifications (not embeddings) to production.

Use this when pgvector is not available on production or disk space is limited.

Usage:
    PROD_DB_URL="postgresql://..." python scripts/migrate_styles_only.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

LOCAL_DB_URL = os.environ.get("LOCAL_DB_URL", "postgresql://sahityapandiri@localhost:5432/omnishop")
PROD_DB_URL = os.environ.get("PROD_DB_URL") or os.environ.get("DATABASE_URL")

BATCH_SIZE = 500


def migrate_styles():
    """Migrate only style classifications from local to production."""

    if not PROD_DB_URL:
        print("ERROR: Production database URL not found.")
        return

    print(f"Source DB: {LOCAL_DB_URL[:50]}...")
    print(f"Target DB: {PROD_DB_URL[:50]}...")
    print("Migrating: primary_style, secondary_style, style_confidence, style_extraction_method")
    print()

    local_engine = create_engine(LOCAL_DB_URL, pool_pre_ping=True)
    prod_engine = create_engine(PROD_DB_URL, pool_pre_ping=True)

    # Query only style columns from local
    select_query = text("""
        SELECT id, primary_style, secondary_style, style_confidence, style_extraction_method
        FROM products
        WHERE primary_style IS NOT NULL
        ORDER BY id
    """)

    print("Reading from local database...")
    with local_engine.connect() as local_conn:
        result = local_conn.execute(select_query)
        rows = result.fetchall()

    total = len(rows)
    print(f"Found {total} products with style classifications")

    if total == 0:
        print("Nothing to migrate.")
        return

    # Update query for styles only
    update_sql = text("""
        UPDATE products SET
            primary_style = :primary_style,
            secondary_style = :secondary_style,
            style_confidence = :style_confidence,
            style_extraction_method = :style_extraction_method
        WHERE id = :id
    """)

    updated = 0
    skipped = 0
    errors = 0

    print("\nMigrating styles to production...")

    with prod_engine.connect() as prod_conn:
        for i, row in enumerate(rows):
            try:
                result = prod_conn.execute(update_sql, {
                    "id": row.id,
                    "primary_style": row.primary_style,
                    "secondary_style": row.secondary_style,
                    "style_confidence": float(row.style_confidence) if row.style_confidence else None,
                    "style_extraction_method": row.style_extraction_method,
                })

                if result.rowcount > 0:
                    updated += 1
                else:
                    skipped += 1

                if (i + 1) % BATCH_SIZE == 0:
                    prod_conn.commit()
                    pct = (i + 1) / total * 100
                    print(f"Progress: {i + 1}/{total} ({pct:.1f}%) | Updated: {updated} | Skipped: {skipped}")

            except Exception as e:
                errors += 1
                prod_conn.rollback()
                if errors <= 5:
                    print(f"Error on product {row.id}: {e}")

        prod_conn.commit()

    print("\n" + "=" * 60)
    print("STYLE MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Total processed: {total}")
    print(f"Updated:         {updated}")
    print(f"Skipped:         {skipped}")
    print(f"Errors:          {errors}")
    print("=" * 60)


if __name__ == "__main__":
    migrate_styles()
