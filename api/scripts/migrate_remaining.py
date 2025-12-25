"""
Migrate remaining products that don't have embeddings/styles on production.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

LOCAL_DB_URL = os.environ.get("LOCAL_DB_URL", "postgresql://sahityapandiri@localhost:5432/omnishop")
PROD_DB_URL = os.environ.get("PROD_DB_URL") or os.environ.get("DATABASE_URL")

BATCH_SIZE = 50


def migrate_remaining():
    """Migrate only products that don't have styles on production."""

    if not PROD_DB_URL:
        print("ERROR: Production database URL not found.")
        return

    print(f"Source DB: {LOCAL_DB_URL[:50]}...")
    print(f"Target DB: {PROD_DB_URL[:50]}...")
    print()

    local_engine = create_engine(LOCAL_DB_URL, pool_pre_ping=True)
    prod_engine = create_engine(PROD_DB_URL, pool_pre_ping=True)

    # Get list of product IDs that don't have styles on production
    print("Finding products without styles on production...")
    with prod_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id FROM products WHERE primary_style IS NULL ORDER BY id
        """))
        missing_ids = [row.id for row in result.fetchall()]

    print(f"Found {len(missing_ids)} products without styles")

    if not missing_ids:
        print("All products already have styles!")
        return

    # Get data from local for those IDs
    print("Fetching data from local database...")
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
        WHERE id = ANY(:ids)
        AND primary_style IS NOT NULL
        ORDER BY id
    """)

    with local_engine.connect() as conn:
        result = conn.execute(select_query, {"ids": missing_ids})
        rows = result.fetchall()

    print(f"Found {len(rows)} products with data in local DB")

    if not rows:
        print("No matching products with data in local DB")
        return

    # Migrate in small batches with individual commits
    update_sql = text("""
        UPDATE products SET
            embedding = :embedding,
            embedding_text = :embedding_text,
            embedding_updated_at = :embedding_updated_at,
            primary_style = :primary_style,
            secondary_style = :secondary_style,
            style_confidence = :style_confidence,
            style_extraction_method = :style_extraction_method
        WHERE id = :id
    """)

    updated = 0
    skipped = 0
    errors = 0
    total = len(rows)

    print(f"\nMigrating {total} products...")

    with prod_engine.connect() as conn:
        for i, row in enumerate(rows):
            try:
                result = conn.execute(update_sql, {
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
                    conn.commit()
                    pct = (i + 1) / total * 100
                    print(f"Progress: {i + 1}/{total} ({pct:.1f}%) | Updated: {updated} | Skipped: {skipped}")

            except Exception as e:
                errors += 1
                try:
                    conn.rollback()
                except Exception:
                    pass
                if errors <= 3:
                    print(f"Error on product {row.id}: {str(e)[:100]}")
                # Try to reconnect
                try:
                    conn.close()
                    conn = prod_engine.connect()
                except Exception:
                    pass

        # Final commit
        try:
            conn.commit()
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Total attempted: {total}")
    print(f"Updated:         {updated}")
    print(f"Skipped:         {skipped}")
    print(f"Errors:          {errors}")
    print("=" * 60)


if __name__ == "__main__":
    migrate_remaining()
