"""
Script to copy products from local database to production
Only adds new products, doesn't remove existing ones
Also copies required categories if they don't exist in production
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Category, Product, ProductAttribute, ProductImage

# Local database
LOCAL_DB = "postgresql://sahityapandiri@localhost:5432/omnishop"

# Production database
PROD_DB = os.getenv(
    "TARGET_DATABASE_URL", "postgresql://postgres:iRbvMFKftNziuwsiPBJybbhnboECQeYA@shuttle.proxy.rlwy.net:49640/railway"
)

# Stores to copy - None means copy ALL stores
STORES_TO_COPY = None  # Changed from specific stores to ALL stores


def copy_categories(local_session, prod_session, category_ids):
    """Copy categories from local to production if they don't exist

    Returns a mapping of local category IDs to production category IDs
    """
    if not category_ids:
        return {}

    print(f"\nChecking {len(category_ids)} unique categories...")
    copied_count = 0

    # Get all categories from local that need to be copied
    local_categories = local_session.query(Category).filter(Category.id.in_(category_ids)).all()

    # Create a mapping of local IDs to production IDs
    id_mapping = {}

    for local_cat in local_categories:
        # Check if category already exists in production (by slug)
        existing = prod_session.query(Category).filter(Category.slug == local_cat.slug).first()

        if existing:
            # Map the local ID to the existing production ID
            id_mapping[local_cat.id] = existing.id
            continue

        # Create new category (let database auto-generate ID)
        new_cat = Category(
            name=local_cat.name,
            slug=local_cat.slug,
            parent_id=local_cat.parent_id,
            description=local_cat.description,
            created_at=local_cat.created_at,
            updated_at=local_cat.updated_at,
        )

        prod_session.add(new_cat)
        prod_session.flush()  # Get the auto-generated ID

        # Map the local category ID to the new production ID
        id_mapping[local_cat.id] = new_cat.id
        copied_count += 1

    if copied_count > 0:
        prod_session.commit()
        print(f"✅ Copied {copied_count} new categories")
    else:
        print("✅ All required categories already exist")

    return id_mapping


def copy_products():
    """Copy products from local to production"""
    # Connect to local database
    local_engine = create_engine(LOCAL_DB)
    LocalSession = sessionmaker(bind=local_engine)
    local_session = LocalSession()

    # Connect to production database
    prod_engine = create_engine(PROD_DB)
    ProdSession = sessionmaker(bind=prod_engine)
    prod_session = ProdSession()

    try:
        # Get products from local database for the specified stores
        if STORES_TO_COPY:
            local_products = local_session.query(Product).filter(Product.source_website.in_(STORES_TO_COPY)).all()
            print(f"Found {len(local_products)} products in local database for stores: {STORES_TO_COPY}")
        else:
            local_products = local_session.query(Product).all()
            print(f"Found {len(local_products)} products in local database (ALL stores)")

        # Collect all unique category IDs used by these products
        category_ids = set()
        for product in local_products:
            if product.category_id:
                category_ids.add(product.category_id)

        # Copy categories first and get ID mapping
        category_id_mapping = {}
        if category_ids:
            print("\n📦 Step 1: Copying categories")
            category_id_mapping = copy_categories(local_session, prod_session, category_ids)
            print(f"   Category ID mapping created: {len(category_id_mapping)} mappings")

        print("\n📦 Step 2: Copying products")

        # Track statistics
        added_count = 0
        skipped_count = 0

        for local_product in local_products:
            # Check if product already exists in production (by external_id and source_website)
            existing = (
                prod_session.query(Product)
                .filter(
                    Product.external_id == local_product.external_id, Product.source_website == local_product.source_website
                )
                .first()
            )

            if existing:
                skipped_count += 1
                continue

            # Map the category ID from local to production
            prod_category_id = None
            if local_product.category_id:
                prod_category_id = category_id_mapping.get(local_product.category_id, local_product.category_id)

            # Create new product (detach from local session)
            # Don't specify ID - let database auto-generate it
            new_product = Product(
                external_id=local_product.external_id,
                name=local_product.name,
                description=local_product.description,
                price=local_product.price,
                original_price=local_product.original_price,
                currency=local_product.currency,
                brand=local_product.brand,
                model=local_product.model,
                sku=local_product.sku,
                source_website=local_product.source_website,
                source_url=local_product.source_url,
                scraped_at=local_product.scraped_at,
                last_updated=local_product.last_updated,
                is_available=local_product.is_available,
                is_on_sale=local_product.is_on_sale,
                stock_status=local_product.stock_status,
                category_id=prod_category_id,  # Use mapped category ID
            )

            prod_session.add(new_product)
            prod_session.flush()  # Get the ID

            # Copy product images
            local_images = local_session.query(ProductImage).filter(ProductImage.product_id == local_product.id).all()

            for local_image in local_images:
                new_image = ProductImage(
                    product_id=new_product.id,
                    original_url=local_image.original_url,
                    thumbnail_url=local_image.thumbnail_url,
                    medium_url=local_image.medium_url,
                    large_url=local_image.large_url,
                    alt_text=local_image.alt_text,
                    width=local_image.width,
                    height=local_image.height,
                    file_size=local_image.file_size,
                    file_format=local_image.file_format,
                    display_order=local_image.display_order,
                    is_primary=local_image.is_primary,
                    created_at=local_image.created_at,
                )
                prod_session.add(new_image)

            # Copy product attributes
            local_attributes = (
                local_session.query(ProductAttribute).filter(ProductAttribute.product_id == local_product.id).all()
            )

            for local_attr in local_attributes:
                new_attr = ProductAttribute(
                    product_id=new_product.id,
                    attribute_name=local_attr.attribute_name,
                    attribute_value=local_attr.attribute_value,
                    attribute_type=local_attr.attribute_type,
                    confidence_score=local_attr.confidence_score,
                    extraction_method=local_attr.extraction_method,
                    created_at=local_attr.created_at,
                    updated_at=local_attr.updated_at,
                )
                prod_session.add(new_attr)

            added_count += 1

            if added_count % 100 == 0:
                print(f"Processed {added_count} products...")
                prod_session.commit()

        # Final commit
        prod_session.commit()

        print("\n✅ Migration complete!")
        print(f"   Added: {added_count} products")
        print(f"   Skipped (already exist): {skipped_count} products")

    except Exception as e:
        prod_session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        local_session.close()
        prod_session.close()


if __name__ == "__main__":
    copy_products()
