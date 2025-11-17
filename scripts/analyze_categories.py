#!/usr/bin/env python3
"""
Analyze category names from scraped products and create missing categories
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.connection import get_db_session
from database.models import Product, Category, ProductAttribute
from collections import Counter

def analyze_product_categories():
    """Analyze what categories products are trying to use"""
    with get_db_session() as session:
        # Get all products from Objectry
        products = session.query(Product).filter(
            Product.source_website == 'objectry'
        ).all()

        print(f"\nAnalyzing {len(products)} Objectry products...")

        # Check product_attributes table for category info
        category_info = []
        for product in products[:10]:  # Sample first 10
            attrs = session.query(ProductAttribute).filter(
                ProductAttribute.product_id == product.id
            ).all()

            print(f"\nProduct: {product.name}")
            print(f"  Brand: {product.brand}")
            if attrs:
                print(f"  Attributes:")
                for attr in attrs:
                    print(f"    {attr.attribute_name}: {attr.attribute_value}")
            else:
                print(f"  No attributes found")

if __name__ == '__main__':
    analyze_product_categories()
