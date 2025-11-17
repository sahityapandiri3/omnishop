"""
Script to investigate product names in database for Issues 12 & 13
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path (same as main.py does)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from api.core.database import get_db
from database.models import Product


async def check_pillow_products():
    """Check for pillow-related products in database"""
    print("\n=== CHECKING PILLOW PRODUCTS ===")

    async for db in get_db():
        # Search for products with pillow-related keywords
        keywords = ['pillow', 'cushion', 'throw', 'accent']

        for keyword in keywords:
            query = select(Product).where(
                func.lower(Product.name).like(f'%{keyword}%')
            ).limit(10)

            result = await db.execute(query)
            products = result.scalars().all()

            if products:
                print(f"\n✅ Found {len(products)} products with '{keyword}':")
                for p in products[:5]:  # Show first 5
                    print(f"  - {p.name} (ID: {p.id})")
            else:
                print(f"\n❌ No products found with '{keyword}'")

        # Get total product count
        count_query = select(func.count(Product.id))
        total = await db.execute(count_query)
        print(f"\n📊 Total products in database: {total.scalar()}")

        break  # Exit after first db session


async def check_wall_art_products():
    """Check for wall art related products in database"""
    print("\n=== CHECKING WALL ART PRODUCTS ===")

    async for db in get_db():
        # Search for products with wall art-related keywords
        keywords = ['art', 'wall', 'canvas', 'print', 'painting', 'frame', 'decor']

        for keyword in keywords:
            query = select(Product).where(
                func.lower(Product.name).like(f'%{keyword}%')
            ).limit(10)

            result = await db.execute(query)
            products = result.scalars().all()

            if products:
                print(f"\n✅ Found {len(products)} products with '{keyword}':")
                for p in products[:5]:  # Show first 5
                    print(f"  - {p.name} (ID: {p.id})")
            else:
                print(f"\n❌ No products found with '{keyword}'")

        break  # Exit after first db session


async def check_all_categories():
    """List all unique product types to understand what's in DB"""
    print("\n=== PRODUCT CATEGORIES ===")

    async for db in get_db():
        # Get sample of product names to understand naming patterns
        query = select(Product.name, Product.product_type).limit(50)
        result = await db.execute(query)
        products = result.all()

        print("\n📦 Sample of products in database:")
        for name, ptype in products[:20]:
            print(f"  - {name} (type: {ptype})")

        break


async def main():
    """Run all checks"""
    await check_pillow_products()
    await check_wall_art_products()
    await check_all_categories()


if __name__ == "__main__":
    asyncio.run(main())
