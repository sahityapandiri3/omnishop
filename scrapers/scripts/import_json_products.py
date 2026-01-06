"""
Import products from JSON files into the database
Handles Playwright scraper output for Durian and Wooden Street
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
import logging

# Add parent directories to path for imports
api_path = str(Path(__file__).parent.parent.parent / "api")
scrapers_path = str(Path(__file__).parent.parent)
sys.path.insert(0, api_path)
sys.path.insert(0, scrapers_path)

from database.connection import get_db_session
from database.models import Product, ProductImage, ProductAttribute, Category

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_or_create_category(session, category_name: str):
    """Get or create a category by name"""
    if not category_name:
        return None

    category = session.query(Category).filter_by(name=category_name).first()
    if not category:
        # Create slug from name
        slug = re.sub(r'[^\w\s-]', '', category_name.lower())
        slug = re.sub(r'[-\s]+', '-', slug).strip('-')

        category = Category(
            name=category_name,
            slug=slug
        )
        session.add(category)
        session.flush()
        logger.info(f"Created category: {category_name}")

    return category


def import_product(session, product_data: dict, source_website: str):
    """Import a single product into the database"""
    external_id = product_data.get('external_id')

    # Check if product already exists
    existing = session.query(Product).filter_by(
        source_website=source_website,
        external_id=external_id
    ).first()

    if existing:
        # Update existing product
        product = existing
        product.last_updated = datetime.utcnow()
    else:
        # Create new product
        product = Product()
        product.scraped_at = datetime.utcnow()

    # Set product fields
    product.external_id = external_id
    product.name = product_data.get('name')
    product.description = product_data.get('description')
    product.price = product_data.get('price')
    product.original_price = product_data.get('original_price')
    product.currency = product_data.get('currency', 'INR')
    product.brand = product_data.get('brand')
    product.model = product_data.get('model')
    product.sku = product_data.get('sku')
    product.source_website = source_website
    product.source_url = product_data.get('source_url')
    product.is_available = product_data.get('is_available', True)
    product.is_on_sale = product_data.get('is_on_sale', False)
    product.stock_status = product_data.get('stock_status', 'in_stock')

    # Handle category
    category_name = product_data.get('category')
    if category_name:
        category = get_or_create_category(session, category_name)
        if category:
            product.category_id = category.id

    # Add product to session
    if not existing:
        session.add(product)
        session.flush()

    # Handle images
    image_urls = product_data.get('image_urls', [])
    for i, url in enumerate(image_urls):
        # Check if image exists
        existing_img = session.query(ProductImage).filter_by(
            product_id=product.id,
            original_url=url
        ).first()

        if not existing_img:
            image = ProductImage(
                product_id=product.id,
                original_url=url,
                display_order=i,
                is_primary=(i == 0)
            )
            session.add(image)

    # Handle attributes
    attributes = product_data.get('attributes', {})
    for attr_name, attr_value in attributes.items():
        if attr_value:
            existing_attr = session.query(ProductAttribute).filter_by(
                product_id=product.id,
                attribute_name=attr_name
            ).first()

            if not existing_attr:
                attr = ProductAttribute(
                    product_id=product.id,
                    attribute_name=attr_name,
                    attribute_value=str(attr_value)
                )
                session.add(attr)
            else:
                existing_attr.attribute_value = str(attr_value)

    return product, existing is not None


def import_json_file(json_path: str, source_website: str, display_name: str):
    """Import all products from a JSON file"""
    logger.info(f"Loading products from {json_path}")

    with open(json_path, 'r') as f:
        products = json.load(f)

    logger.info(f"Found {len(products)} products to import for {display_name}")

    new_count = 0
    updated_count = 0
    error_count = 0

    with get_db_session() as session:

        for i, product_data in enumerate(products):
            try:
                product, was_existing = import_product(session, product_data, source_website)

                if was_existing:
                    updated_count += 1
                else:
                    new_count += 1

                if (i + 1) % 50 == 0:
                    logger.info(f"Processed {i + 1}/{len(products)} products")
                    session.commit()  # Commit in batches

            except Exception as e:
                error_count += 1
                logger.error(f"Error importing product {i + 1}: {e}")
                continue

        session.commit()

    logger.info(f"\n{'='*60}")
    logger.info(f"Import complete for {display_name}")
    logger.info(f"New products: {new_count}")
    logger.info(f"Updated products: {updated_count}")
    logger.info(f"Errors: {error_count}")
    logger.info(f"{'='*60}")

    return new_count, updated_count, error_count


def main():
    """Main import function"""
    import_files = [
        {
            'path': '/tmp/durian_products_full.json',
            'source_website': 'durian',
            'display_name': 'Durian'
        },
        {
            'path': '/tmp/woodenstreet_products_full.json',
            'source_website': 'woodenstreet',
            'display_name': 'Wooden Street'
        }
    ]

    total_new = 0
    total_updated = 0
    total_errors = 0

    for file_config in import_files:
        if Path(file_config['path']).exists():
            new, updated, errors = import_json_file(
                file_config['path'],
                file_config['source_website'],
                file_config['display_name']
            )
            total_new += new
            total_updated += updated
            total_errors += errors
        else:
            logger.warning(f"File not found: {file_config['path']}")

    logger.info(f"\n{'='*60}")
    logger.info("FINAL SUMMARY")
    logger.info(f"Total new products: {total_new}")
    logger.info(f"Total updated products: {total_updated}")
    logger.info(f"Total errors: {total_errors}")
    logger.info(f"{'='*60}")


if __name__ == '__main__':
    main()
