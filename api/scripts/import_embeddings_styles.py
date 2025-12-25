"""
Import embeddings and styles from CSV dump to production database.

Usage:
    # Local
    python scripts/import_embeddings_styles.py

    # Production (Railway)
    railway run python scripts/import_embeddings_styles.py
"""
import csv
import gzip
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

from core.config import settings  # noqa: E402

# Path to the compressed CSV file
CSV_FILE = Path(__file__).parent / "products_embeddings_styles.csv.gz"


def import_data():
    """Import embeddings and styles from CSV to database."""

    database_url = settings.database_url
    print(f"Database: {database_url[:50]}...")

    engine = create_engine(database_url, pool_pre_ping=True)

    if not CSV_FILE.exists():
        print(f"ERROR: CSV file not found: {CSV_FILE}")
        print("Make sure products_embeddings_styles.csv.gz is in the scripts folder")
        return

    print(f"Reading from: {CSV_FILE}")
    print(f"File size: {CSV_FILE.stat().st_size / 1024 / 1024:.1f} MB")

    # Read and import data
    updated = 0
    skipped = 0
    errors = 0

    with gzip.open(CSV_FILE, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        with engine.connect() as conn:
            for i, row in enumerate(reader):
                try:
                    product_id = int(row["id"])

                    # Build update query
                    update_sql = text(
                        """
                        UPDATE products SET
                            embedding = :embedding,
                            embedding_text = :embedding_text,
                            embedding_updated_at = :embedding_updated_at,
                            primary_style = :primary_style,
                            secondary_style = :secondary_style,
                            style_confidence = :style_confidence,
                            style_extraction_method = :style_extraction_method
                        WHERE id = :id
                    """
                    )

                    result = conn.execute(
                        update_sql,
                        {
                            "id": product_id,
                            "embedding": row["embedding"] if row["embedding"] else None,
                            "embedding_text": row["embedding_text"] if row["embedding_text"] else None,
                            "embedding_updated_at": row["embedding_updated_at"] if row["embedding_updated_at"] else None,
                            "primary_style": row["primary_style"] if row["primary_style"] else None,
                            "secondary_style": row["secondary_style"] if row["secondary_style"] else None,
                            "style_confidence": float(row["style_confidence"]) if row["style_confidence"] else None,
                            "style_extraction_method": row["style_extraction_method"]
                            if row["style_extraction_method"]
                            else None,
                        },
                    )

                    if result.rowcount > 0:
                        updated += 1
                    else:
                        skipped += 1

                    # Commit every 500 records
                    if (i + 1) % 500 == 0:
                        conn.commit()
                        print(f"Progress: {i + 1} processed, {updated} updated, {skipped} skipped")

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"Error on row {i + 1}: {e}")

            # Final commit
            conn.commit()

    print("\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    print(f"Total processed: {updated + skipped + errors}")
    print(f"Updated:         {updated}")
    print(f"Skipped:         {skipped} (product not found in target DB)")
    print(f"Errors:          {errors}")
    print("=" * 60)


if __name__ == "__main__":
    import_data()
