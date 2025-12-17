"""
Migrate only NEW products from nicobar, ellementry, obeetee scrapers to Railway production
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# New scrapers to migrate
NEW_SOURCES = ('nicobar', 'ellementry', 'obeetee')

def migrate_new_products(source_url: str, target_url: str):
    """Migrate only products from new scrapers"""
    logger.info("Starting targeted migration for new scrapers...")
    logger.info(f"Sources to migrate: {NEW_SOURCES}")

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)

    source_session = SourceSession()
    target_session = TargetSession()

    try:
        # Get product IDs for new sources
        product_ids_result = source_session.execute(text("""
            SELECT id FROM products WHERE source_website IN :sources
        """), {"sources": NEW_SOURCES})
        product_ids = [row[0] for row in product_ids_result]

        logger.info(f"Found {len(product_ids)} products to migrate")

        # Check what's already in production
        existing_result = target_session.execute(text("""
            SELECT id FROM products WHERE source_website IN :sources
        """), {"sources": NEW_SOURCES})
        existing_ids = set(row[0] for row in existing_result)

        new_product_ids = [pid for pid in product_ids if pid not in existing_ids]
        logger.info(f"  Already in production: {len(existing_ids)}")
        logger.info(f"  New to migrate: {len(new_product_ids)}")

        if not new_product_ids:
            logger.info("No new products to migrate!")
            return

        # Migrate products
        logger.info("\n=== Migrating Products ===")
        migrate_products(source_session, target_session, new_product_ids)

        # Migrate product images
        logger.info("\n=== Migrating Product Images ===")
        migrate_product_images(source_session, target_session, new_product_ids)

        # Migrate product attributes
        logger.info("\n=== Migrating Product Attributes ===")
        migrate_product_attributes(source_session, target_session, new_product_ids)

        # Migrate product search view
        logger.info("\n=== Migrating Product Search View ===")
        migrate_product_search_view(source_session, target_session, new_product_ids)

        # Update sequences
        logger.info("\n=== Updating Sequences ===")
        for table in ['products', 'product_images', 'product_attributes', 'product_search_view']:
            max_id = target_session.execute(text(f"SELECT MAX(id) FROM {table}")).scalar()
            if max_id:
                target_session.execute(text(f"SELECT setval('{table}_id_seq', :max_id)"), {"max_id": max_id})
                logger.info(f"Updated {table}_id_seq to {max_id}")

        target_session.commit()
        logger.info("\n=== Migration Complete! ===")

        # Final counts
        for source in NEW_SOURCES:
            count = target_session.execute(text(
                "SELECT COUNT(*) FROM products WHERE source_website = :source"
            ), {"source": source}).scalar()
            logger.info(f"  {source}: {count} products in production")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        target_session.rollback()
        raise
    finally:
        source_session.close()
        target_session.close()


def migrate_products(source_session, target_session, product_ids, batch_size=100):
    """Migrate products by IDs"""
    columns = ['id', 'name', 'description', 'price', 'source_website', 'source_url',
               'category_id', 'is_available', 'scraped_at', 'last_updated', 'external_id',
               'original_price', 'brand', 'currency', 'sku']
    columns_str = ', '.join(columns)

    with tqdm(total=len(product_ids), desc="Migrating products") as pbar:
        for i in range(0, len(product_ids), batch_size):
            batch_ids = product_ids[i:i+batch_size]

            rows = source_session.execute(text(f"""
                SELECT {columns_str} FROM products WHERE id IN :ids
            """), {"ids": tuple(batch_ids)}).fetchall()

            for row in rows:
                row_dict = dict(zip(columns, row))
                placeholders = ', '.join([f':{col}' for col in columns])

                target_session.execute(text(f"""
                    INSERT INTO products ({columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO UPDATE SET
                    {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != 'id'])}
                """), row_dict)

            target_session.commit()
            pbar.update(len(rows))


def migrate_product_images(source_session, target_session, product_ids, batch_size=500):
    """Migrate product images for given product IDs"""
    columns = ['id', 'product_id', 'original_url', 'thumbnail_url', 'medium_url', 'large_url',
               'alt_text', 'width', 'height', 'file_size', 'file_format', 'display_order',
               'is_primary', 'created_at']
    columns_str = ', '.join(columns)

    # Get total count
    total = source_session.execute(text(
        "SELECT COUNT(*) FROM product_images WHERE product_id IN :ids"
    ), {"ids": tuple(product_ids)}).scalar()

    with tqdm(total=total, desc="Migrating images") as pbar:
        offset = 0
        while True:
            rows = source_session.execute(text(f"""
                SELECT {columns_str} FROM product_images
                WHERE product_id IN :ids
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """), {"ids": tuple(product_ids), "limit": batch_size, "offset": offset}).fetchall()

            if not rows:
                break

            for row in rows:
                row_dict = dict(zip(columns, row))
                placeholders = ', '.join([f':{col}' for col in columns])

                target_session.execute(text(f"""
                    INSERT INTO product_images ({columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO NOTHING
                """), row_dict)

            target_session.commit()
            offset += len(rows)
            pbar.update(len(rows))


def migrate_product_attributes(source_session, target_session, product_ids, batch_size=500):
    """Migrate product attributes for given product IDs"""
    columns = ['id', 'product_id', 'attribute_name', 'attribute_value', 'attribute_type',
               'created_at', 'confidence_score', 'extraction_method', 'updated_at']
    columns_str = ', '.join(columns)

    # Get total count
    total = source_session.execute(text(
        "SELECT COUNT(*) FROM product_attributes WHERE product_id IN :ids"
    ), {"ids": tuple(product_ids)}).scalar()

    with tqdm(total=total, desc="Migrating attributes") as pbar:
        offset = 0
        while True:
            rows = source_session.execute(text(f"""
                SELECT {columns_str} FROM product_attributes
                WHERE product_id IN :ids
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """), {"ids": tuple(product_ids), "limit": batch_size, "offset": offset}).fetchall()

            if not rows:
                break

            for row in rows:
                row_dict = dict(zip(columns, row))
                placeholders = ', '.join([f':{col}' for col in columns])

                target_session.execute(text(f"""
                    INSERT INTO product_attributes ({columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO NOTHING
                """), row_dict)

            target_session.commit()
            offset += len(rows)
            pbar.update(len(rows))


def migrate_product_search_view(source_session, target_session, product_ids, batch_size=500):
    """Migrate product search view for given product IDs"""
    columns = ['id', 'product_id', 'name', 'description_text', 'price', 'brand',
               'category_name', 'category_path', 'source_website', 'is_available',
               'primary_image_url', 'search_vector', 'last_updated']
    columns_str = ', '.join(columns)

    # Get total count
    total = source_session.execute(text(
        "SELECT COUNT(*) FROM product_search_view WHERE product_id IN :ids"
    ), {"ids": tuple(product_ids)}).scalar()

    logger.info(f"Found {total} search view entries to migrate")

    with tqdm(total=total, desc="Migrating search view") as pbar:
        offset = 0
        while True:
            rows = source_session.execute(text(f"""
                SELECT {columns_str} FROM product_search_view
                WHERE product_id IN :ids
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """), {"ids": tuple(product_ids), "limit": batch_size, "offset": offset}).fetchall()

            if not rows:
                break

            for row in rows:
                row_dict = dict(zip(columns, row))
                placeholders = ', '.join([f':{col}' for col in columns])

                target_session.execute(text(f"""
                    INSERT INTO product_search_view ({columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO NOTHING
                """), row_dict)

            target_session.commit()
            offset += len(rows)
            pbar.update(len(rows))


if __name__ == '__main__':
    source_url = os.environ.get(
        'SOURCE_DATABASE_URL',
        'postgresql://sahityapandiri@localhost:5432/omnishop'
    )
    target_url = os.environ.get('TARGET_DATABASE_URL')

    if not target_url:
        print("Error: TARGET_DATABASE_URL not set")
        print("Usage: export TARGET_DATABASE_URL='...' && python scripts/migrate_new_scrapers.py")
        sys.exit(1)

    migrate_new_products(source_url, target_url)
