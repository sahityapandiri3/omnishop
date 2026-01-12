"""
Sync embeddings from production database to local database.
This copies embedding data for products that exist in both databases.
"""
import asyncio
import os
import sys
from typing import Dict, List, Tuple

import asyncpg

# Database URLs
PROD_DB_URL = "postgresql://postgres:iRbvMFKftNziuwsiPBJybbhnboECQeYA@shuttle.proxy.rlwy.net:49640/railway"
LOCAL_DB_URL = os.environ.get("LOCAL_DATABASE_URL", "postgresql://sahityapandiri@localhost:5432/omnishop")

BATCH_SIZE = 500


async def get_prod_embeddings(prod_conn: asyncpg.Connection, external_ids: List[str]) -> Dict[str, Tuple[str, str]]:
    """Fetch embeddings from production for given external_ids."""
    if not external_ids:
        return {}

    rows = await prod_conn.fetch(
        """
        SELECT external_id, embedding, embedding_text
        FROM products
        WHERE external_id = ANY($1) AND embedding IS NOT NULL
        """,
        external_ids,
    )
    return {row["external_id"]: (row["embedding"], row["embedding_text"]) for row in rows}


async def sync_embeddings():
    """Main sync function."""
    print(f"Connecting to production database...")
    prod_conn = await asyncpg.connect(PROD_DB_URL)

    print(f"Connecting to local database...")
    local_conn = await asyncpg.connect(LOCAL_DB_URL)

    try:
        # Get all products without embeddings from local DB
        print("Finding local products without embeddings...")
        local_products = await local_conn.fetch(
            """
            SELECT id, external_id, source_website
            FROM products
            WHERE embedding IS NULL AND external_id IS NOT NULL
            ORDER BY source_website, id
            """
        )
        print(f"Found {len(local_products)} local products without embeddings")

        if not local_products:
            print("All local products already have embeddings!")
            return

        # Process in batches
        updated_count = 0
        total_batches = (len(local_products) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_idx in range(0, len(local_products), BATCH_SIZE):
            batch = local_products[batch_idx : batch_idx + BATCH_SIZE]
            batch_num = batch_idx // BATCH_SIZE + 1

            external_ids = [p["external_id"] for p in batch]

            # Get embeddings from production
            prod_embeddings = await get_prod_embeddings(prod_conn, external_ids)

            if not prod_embeddings:
                print(f"Batch {batch_num}/{total_batches}: No embeddings found in production")
                continue

            # Update local database
            for product in batch:
                ext_id = product["external_id"]
                if ext_id in prod_embeddings:
                    embedding, embedding_text = prod_embeddings[ext_id]
                    await local_conn.execute(
                        """
                        UPDATE products
                        SET embedding = $1, embedding_text = $2, embedding_updated_at = NOW()
                        WHERE id = $3
                        """,
                        embedding,
                        embedding_text,
                        product["id"],
                    )
                    updated_count += 1

            print(f"Batch {batch_num}/{total_batches}: Updated {len(prod_embeddings)} products (total: {updated_count})")

        print(f"\nSync complete! Updated {updated_count} products with embeddings.")

        # Show summary by store
        print("\nEmbedding status by store:")
        summary = await local_conn.fetch(
            """
            SELECT source_website,
                   COUNT(*) as total,
                   COUNT(embedding) as with_embeddings
            FROM products
            WHERE is_available = true
            GROUP BY source_website
            ORDER BY source_website
            """
        )
        for row in summary:
            pct = (row["with_embeddings"] / row["total"] * 100) if row["total"] > 0 else 0
            print(f"  {row['source_website']}: {row['with_embeddings']}/{row['total']} ({pct:.1f}%)")

    finally:
        await prod_conn.close()
        await local_conn.close()


if __name__ == "__main__":
    asyncio.run(sync_embeddings())
