"""
Export embeddings and styles from local database to CSV.

This script properly handles the embedding JSON array that contains commas.

Usage:
    python scripts/export_embeddings_styles.py
"""
import csv
import gzip
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

from core.config import settings  # noqa: E402

# Output file
OUTPUT_FILE = Path(__file__).parent / "products_embeddings_styles.csv.gz"


def export_data():
    """Export embeddings and styles to CSV."""

    database_url = settings.database_url
    print(f"Database: {database_url[:50]}...")

    engine = create_engine(database_url, pool_pre_ping=True)

    # Query all products with embeddings or styles
    query = text(
        """
        SELECT
            id,
            embedding::text as embedding,
            embedding_text,
            embedding_updated_at::text as embedding_updated_at,
            primary_style,
            secondary_style,
            style_confidence,
            style_extraction_method
        FROM products
        WHERE embedding IS NOT NULL
           OR primary_style IS NOT NULL
        ORDER BY id
    """
    )

    print("Querying database...")

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

    print(f"Found {len(rows)} products to export")

    # Write to gzipped CSV
    print(f"Writing to {OUTPUT_FILE}...")

    with gzip.open(OUTPUT_FILE, "wt", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)

        # Write header
        writer.writerow(
            [
                "id",
                "embedding",
                "embedding_text",
                "embedding_updated_at",
                "primary_style",
                "secondary_style",
                "style_confidence",
                "style_extraction_method",
            ]
        )

        # Write data rows
        for row in rows:
            writer.writerow(
                [
                    row.id,
                    row.embedding,
                    row.embedding_text,
                    row.embedding_updated_at,
                    row.primary_style,
                    row.secondary_style,
                    row.style_confidence,
                    row.style_extraction_method,
                ]
            )

    file_size = OUTPUT_FILE.stat().st_size / 1024 / 1024
    print("\nExport complete!")
    print(f"File: {OUTPUT_FILE}")
    print(f"Size: {file_size:.1f} MB")
    print(f"Records: {len(rows)}")

    # Verify by reading first few rows
    print("\nVerifying export (first 2 rows):")
    with gzip.open(OUTPUT_FILE, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 2:
                break
            print(f"\n  Row {i+1}:")
            print(f"    id: {row['id']}")
            print(f"    primary_style: {row['primary_style']}")
            print(f"    secondary_style: {row['secondary_style']}")
            print(f"    style_confidence: {row['style_confidence']}")
            print(f"    embedding preview: {row['embedding'][:50]}...")


if __name__ == "__main__":
    export_data()
