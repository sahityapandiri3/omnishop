"""
Fetch alignment data for Wooden Street sectional sofas from their website.

This script:
1. Finds Wooden Street L-shaped/sectional sofas without alignment
2. Fetches the product page to get the "Aligned" specification
3. Updates the ProductAttribute table

Usage:
    DATABASE_URL=... python -m scripts.fetch_woodenstreet_alignment [--dry-run]
"""
import argparse
import asyncio
import logging
import re
import sys
from typing import Optional

import aiohttp

sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from sqlalchemy import and_, or_, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from core.config import settings  # noqa: E402
from database.models import Product, ProductAttribute  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def fetch_alignment_from_page(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Fetch product page and extract alignment from JSON data."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with session.get(url, headers=headers, timeout=30) as response:
            if response.status != 200:
                logger.warning(f"Failed to fetch {url}: {response.status}")
                return None

            html = await response.text()

            # Look for alignment in JSON data
            # Pattern: {"dimensionlabel":"Aligned","dimensiondata":"Right"}
            match = re.search(r'"dimensionlabel"\s*:\s*"[Aa]ligned"\s*,\s*"dimensiondata"\s*:\s*"([^"]+)"', html)
            if match:
                alignment = match.group(1).strip().lower()
                if alignment in ["left", "right", "reversible"]:
                    return alignment

            return None
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None


async def fetch_woodenstreet_alignments(dry_run: bool = False):
    """Fetch alignment data for Wooden Street products."""
    import os

    database_url = os.environ.get("DATABASE_URL") or settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {
        "total_products": 0,
        "fetched": 0,
        "alignments_found": 0,
        "left": 0,
        "right": 0,
        "already_has_alignment": 0,
        "created": 0,
        "failed": 0,
    }

    async with async_session() as db_session:
        # Find Wooden Street L-shaped/sectional sofas without alignment
        query = select(Product).where(
            and_(
                Product.is_available.is_(True),
                Product.source_website == "woodenstreet",
                or_(
                    Product.name.ilike("%l%shape%"),
                    Product.name.ilike("%sectional%"),
                    Product.name.ilike("%corner%sofa%"),
                ),
                Product.name.ilike("%sofa%"),
            )
        )

        result = await db_session.execute(query)
        products = result.scalars().all()

        # Filter out products that already have alignment
        products_to_check = []
        for product in products:
            existing_query = select(ProductAttribute).where(
                and_(ProductAttribute.product_id == product.id, ProductAttribute.attribute_name == "sofa_alignment")
            )
            existing_result = await db_session.execute(existing_query)
            existing_attr = existing_result.scalar_one_or_none()

            if existing_attr:
                stats["already_has_alignment"] += 1
            else:
                products_to_check.append(product)

        stats["total_products"] = len(products_to_check)
        logger.info(f"Found {len(products_to_check)} Wooden Street sofas without alignment")
        logger.info(f"({stats['already_has_alignment']} already have alignment)")

        if not products_to_check:
            print("No products to check!")
            return stats

        # Fetch alignment from website
        async with aiohttp.ClientSession() as http_session:
            for product in products_to_check:
                stats["fetched"] += 1
                logger.info(f"[{stats['fetched']}/{len(products_to_check)}] Checking: {product.name[:50]}...")

                alignment = await fetch_alignment_from_page(http_session, product.source_url)

                if alignment:
                    stats["alignments_found"] += 1
                    stats[alignment] += 1

                    if not dry_run:
                        # Create new attribute
                        new_attr = ProductAttribute(
                            product_id=product.id,
                            attribute_name="sofa_alignment",
                            attribute_value=alignment,
                            attribute_type="text",
                            extraction_method="woodenstreet_fetch",
                            confidence_score=0.95,
                        )
                        db_session.add(new_attr)

                    stats["created"] += 1
                    logger.info(f"  -> Found alignment: {alignment}")
                else:
                    stats["failed"] += 1
                    logger.info("  -> No alignment found")

                # Small delay to be nice to the server
                await asyncio.sleep(1)

        if not dry_run:
            await db_session.commit()
            logger.info("Committed changes to database")

    # Print summary
    print("\n" + "=" * 60)
    print("WOODEN STREET ALIGNMENT FETCH SUMMARY")
    print("=" * 60)
    print(f"Products checked:           {stats['total_products']}")
    print(f"Already had alignment:      {stats['already_has_alignment']}")
    print(f"Alignments found:           {stats['alignments_found']}")
    print(f"  - Left aligned:           {stats['left']}")
    print(f"  - Right aligned:          {stats['right']}")
    print(f"New alignments created:     {stats['created']}")
    print(f"No alignment found:         {stats['failed']}")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN] No changes were made to the database.")

    await engine.dispose()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Wooden Street alignment data")
    parser.add_argument("--dry-run", action="store_true", help="Run without making changes")

    args = parser.parse_args()

    if args.dry_run:
        print("Running in DRY RUN mode - no changes will be made\n")

    asyncio.run(fetch_woodenstreet_alignments(dry_run=args.dry_run))
