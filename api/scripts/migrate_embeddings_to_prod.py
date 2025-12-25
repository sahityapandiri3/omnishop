"""
Migrate embeddings and styles from local database directly to production.

This script connects to both databases and transfers data without needing
to transfer large CSV files.

Usage:
    # Set your local database URL and run with Railway
    LOCAL_DB_URL="postgresql://user@localhost:5432/omnishop" railway run python scripts/migrate_embeddings_to_prod.py

    # Or specify both URLs explicitly
    LOCAL_DB_URL="postgresql://..." PROD_DB_URL="postgresql://..." python scripts/migrate_embeddings_to_prod.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

# Get database URLs
LOCAL_DB_URL = os.environ.get("LOCAL_DB_URL", "postgresql://sahityapandiri@localhost:5432/omnishop")
PROD_DB_URL = os.environ.get("PROD_DB_URL") or os.environ.get("DATABASE_URL")

BATCH_SIZE = 100


def migrate_data():
    """Migrate embeddings and styles from local to production."""

    if not PROD_DB_URL:
        print("ERROR: Production database URL not found.")
        print("Set PROD_DB_URL or run with 'railway run'")
        return

    print(f"Source DB: {LOCAL_DB_URL[:50]}...")
    print(f"Target DB: {PROD_DB_URL[:50]}...")
    print(f"Batch size: {BATCH_SIZE}")
    print()

    # Connect to both databases
    local_engine = create_engine(LOCAL_DB_URL, pool_pre_ping=True)
    prod_engine = create_engine(PROD_DB_URL, pool_pre_ping=True)

    # Query products with embeddings/styles from local
    select_query = text("""
        SELECT
            id,
            embedding::text as embedding,
            embedding_text,
            embedding_updated_at,
            primary_style,
            secondary_style,
            style_confidence,
            style_extraction_method
        FROM products
        WHERE embedding IS NOT NULL
           OR primary_style IS NOT NULL
        ORDER BY id
    """)

    print("Reading from local database...")
    with local_engine.connect() as local_conn:
        result = local_conn.execute(select_query)
        rows = result.fetchall()

    total = len(rows)
    print(f"Found {total} products to migrate")

    if total == 0:
        print("Nothing to migrate.")
        return

    # Prepare update query
    update_sql = text("""
        UPDATE products SET
            embedding = :embedding::vector,
            embedding_text = :embedding_text,
            embedding_updated_at = :embedding_updated_at,
            primary_style = :primary_style,
            secondary_style = :secondary_style,
            style_confidence = :style_confidence,
            style_extraction_method = :style_extraction_method
        WHERE id = :id
    """)

    # Migrate in batches
    updated = 0
    skipped = 0
    errors = 0

    print("\nMigrating to production...")

    with prod_engine.connect() as prod_conn:
        for i, row in enumerate(rows):
            try:
                result = prod_conn.execute(update_sql, {
                    "id": row.id,
                    "embedding": row.embedding,
                    "embedding_text": row.embedding_text,
                    "embedding_updated_at": row.embedding_updated_at,
                    "primary_style": row.primary_style,
                    "secondary_style": row.secondary_style,
                    "style_confidence": float(row.style_confidence) if row.style_confidence else None,
                    "style_extraction_method": row.style_extraction_method,
                })

                if result.rowcount > 0:
                    updated += 1
                else:
                    skipped += 1

                # Commit every BATCH_SIZE records
                if (i + 1) % BATCH_SIZE == 0:
                    prod_conn.commit()
                    pct = (i + 1) / total * 100
                    print(f"Progress: {i + 1}/{total} ({pct:.1f}%) | Updated: {updated} | Skipped: {skipped}")

            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"Error on product {row.id}: {e}")

        # Final commit
        prod_conn.commit()

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Total processed: {total}")
    print(f"Updated:         {updated}")
    print(f"Skipped:         {skipped} (product not found in prod DB)")
    print(f"Errors:          {errors}")
    print("=" * 60)


if __name__ == "__main__":
    migrate_data()
