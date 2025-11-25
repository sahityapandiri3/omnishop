"""
Script to backfill product_attributes from local database to production
for products that already exist in production but are missing their attributes
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Product, ProductAttribute

# Local database
LOCAL_DB = "postgresql://sahityapandiri@localhost:5432/omnishop"

# Production database
PROD_DB = os.getenv(
    "TARGET_DATABASE_URL", "postgresql://postgres:iRbvMFKftNziuwsiPBJybbhnboECQeYA@shuttle.proxy.rlwy.net:49640/railway"
)

# Stores to process
STORES_TO_PROCESS = ["josmo", "magari", "phantomhands"]


def backfill_attributes():
    """Backfill product_attributes for existing products"""
    # Connect to local database
    local_engine = create_engine(LOCAL_DB)
    LocalSession = sessionmaker(bind=local_engine)
    local_session = LocalSession()

    # Connect to production database
    prod_engine = create_engine(PROD_DB)
    ProdSession = sessionmaker(bind=prod_engine)
    prod_session = ProdSession()

    try:
        # Get all products from local database for the specified stores
        local_products = local_session.query(Product).filter(Product.source_website.in_(STORES_TO_PROCESS)).all()

        print(f"Found {len(local_products)} products in local database for stores: {STORES_TO_PROCESS}")

        # Track statistics
        total_attributes = 0
        products_processed = 0
        products_skipped = 0

        for local_product in local_products:
            # Find the corresponding product in production by external_id and source_website
            prod_product = (
                prod_session.query(Product)
                .filter(
                    Product.external_id == local_product.external_id, Product.source_website == local_product.source_website
                )
                .first()
            )

            if not prod_product:
                print(f"⚠️  Product not found in production: {local_product.external_id} ({local_product.source_website})")
                products_skipped += 1
                continue

            # Check if attributes already exist in production for this product
            existing_attrs = (
                prod_session.query(ProductAttribute).filter(ProductAttribute.product_id == prod_product.id).count()
            )

            if existing_attrs > 0:
                # Skip products that already have attributes
                products_skipped += 1
                continue

            # Get attributes from local database
            local_attributes = (
                local_session.query(ProductAttribute).filter(ProductAttribute.product_id == local_product.id).all()
            )

            if not local_attributes:
                # No attributes to copy
                products_skipped += 1
                continue

            # Copy attributes to production using the production product ID
            for local_attr in local_attributes:
                new_attr = ProductAttribute(
                    product_id=prod_product.id,  # Use production product ID
                    attribute_name=local_attr.attribute_name,
                    attribute_value=local_attr.attribute_value,
                    attribute_type=local_attr.attribute_type,
                    confidence_score=local_attr.confidence_score,
                    extraction_method=local_attr.extraction_method,
                    created_at=local_attr.created_at,
                    updated_at=local_attr.updated_at,
                )
                prod_session.add(new_attr)
                total_attributes += 1

            products_processed += 1

            # Commit every 50 products
            if products_processed % 50 == 0:
                print(f"Processed {products_processed} products, copied {total_attributes} attributes...")
                prod_session.commit()

        # Final commit
        prod_session.commit()

        print("\n✅ Backfill complete!")
        print(f"   Products processed: {products_processed}")
        print(f"   Products skipped: {products_skipped}")
        print(f"   Total attributes copied: {total_attributes}")

    except Exception as e:
        prod_session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        local_session.close()
        prod_session.close()


if __name__ == "__main__":
    backfill_attributes()
