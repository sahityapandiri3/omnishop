#!/usr/bin/env python3
"""
Backfill product attributes from existing product descriptions.
Extracts dimensions, material, color, weight, warranty, seating capacity, etc.
"""
import re
import sys
import os
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.connection import db_manager
from database.models import Product, ProductAttribute

# Common materials in furniture
MATERIALS = [
    'teak', 'oak', 'walnut', 'mahogany', 'sheesham', 'mango wood', 'acacia',
    'pine', 'rubber wood', 'engineered wood', 'plywood', 'mdf', 'particle board',
    'solid wood', 'hardwood', 'softwood', 'bamboo', 'rattan', 'cane', 'wicker',
    'metal', 'iron', 'steel', 'stainless steel', 'brass', 'copper', 'aluminum',
    'glass', 'tempered glass', 'mirror',
    'leather', 'faux leather', 'leatherette', 'pu leather', 'genuine leather',
    'fabric', 'cotton', 'linen', 'velvet', 'polyester', 'jute', 'silk',
    'marble', 'granite', 'stone', 'ceramic', 'porcelain',
    'plastic', 'acrylic', 'resin', 'fiberglass'
]

# Common colors
COLORS = [
    'white', 'black', 'brown', 'beige', 'grey', 'gray', 'cream', 'ivory',
    'natural', 'walnut', 'oak', 'teak', 'mahogany', 'honey', 'espresso',
    'red', 'blue', 'green', 'yellow', 'orange', 'pink', 'purple', 'navy',
    'gold', 'silver', 'bronze', 'copper', 'rose gold',
    'multi', 'multicolor', 'multicolour', 'assorted'
]


def extract_dimensions(text: str) -> dict:
    """Extract dimensions from text"""
    attrs = {}

    # Pattern: L x W x H or similar variations
    patterns = [
        r'(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:cm|mm|inch|in|")?',
        r'(?:dimensions?|size)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:cm|mm|inch|in|")?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:cm|mm|inch|in|")?\s*[xX×]\s*(\d+(?:\.\d+)?)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            attrs['dimensions'] = f"{match.group(1)} x {match.group(2)} x {match.group(3)}"
            break

    # Individual dimensions
    height_match = re.search(r'(?:height|h)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cm|mm|inch|in|")?', text, re.IGNORECASE)
    if height_match:
        attrs['height'] = height_match.group(1)

    width_match = re.search(r'(?:width|w)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cm|mm|inch|in|")?', text, re.IGNORECASE)
    if width_match:
        attrs['width'] = width_match.group(1)

    depth_match = re.search(r'(?:depth|d|length|l)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cm|mm|inch|in|")?', text, re.IGNORECASE)
    if depth_match:
        attrs['depth'] = depth_match.group(1)

    return attrs


def extract_material(text: str) -> str:
    """Extract material from text"""
    text_lower = text.lower()

    # Check for materials in order of specificity
    for material in MATERIALS:
        if material in text_lower:
            return material.title()

    return None


def extract_color(text: str) -> str:
    """Extract color from text"""
    text_lower = text.lower()

    # Look for color mentions
    for color in COLORS:
        # Match as whole word
        if re.search(rf'\b{color}\b', text_lower):
            return color.title()

    # Check for finish colors
    finish_match = re.search(r'(?:finish|color|colour)\s*[:\-]?\s*(\w+)', text_lower)
    if finish_match:
        return finish_match.group(1).title()

    return None


def extract_weight(text: str) -> str:
    """Extract weight from text"""
    patterns = [
        r'(?:weight|wt)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilogram)',
        r'(\d+(?:\.\d+)?)\s*(?:kg|kgs)\b',
        r'(?:weight|wt)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds?)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} kg"

    return None


def extract_seating_capacity(text: str) -> str:
    """Extract seating capacity"""
    patterns = [
        r'(\d+)\s*seater',
        r'seats?\s*(\d+)',
        r'seating\s*(?:capacity)?\s*[:\-]?\s*(\d+)',
        r'(\d+)\s*person',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_warranty(text: str) -> str:
    """Extract warranty information"""
    patterns = [
        r'(\d+)\s*(?:year|yr)s?\s*warranty',
        r'warranty\s*[:\-]?\s*(\d+)\s*(?:year|yr|month)s?',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} years"

    return None


def extract_all_attributes(product) -> dict:
    """Extract all attributes from a product"""
    # Combine all text fields
    text_parts = []
    if product.name:
        text_parts.append(product.name)
    if product.description:
        text_parts.append(product.description)

    text = ' '.join(text_parts)

    attrs = {}

    # Extract dimensions
    dim_attrs = extract_dimensions(text)
    attrs.update(dim_attrs)

    # Extract material
    material = extract_material(text)
    if material:
        attrs['material'] = material

    # Extract color
    color = extract_color(text)
    if color:
        attrs['color'] = color

    # Extract weight
    weight = extract_weight(text)
    if weight:
        attrs['weight'] = weight

    # Extract seating capacity
    seating = extract_seating_capacity(text)
    if seating:
        attrs['seating_capacity'] = seating

    # Extract warranty
    warranty = extract_warranty(text)
    if warranty:
        attrs['warranty'] = warranty

    return attrs


def backfill_attributes(stores: list = None, batch_size: int = 100, limit: int = None):
    """Backfill attributes for products"""

    with db_manager.get_session() as session:
        # Build query
        query = session.query(Product).filter(Product.is_available == True)

        if stores:
            query = query.filter(Product.source_website.in_(stores))

        if limit:
            query = query.limit(limit)

        products = query.all()
        total = len(products)

        print(f"Processing {total} products...")

        processed = 0
        attrs_added = 0
        products_updated = 0

        for product in products:
            # Get existing attributes for this product
            existing_attrs = session.query(ProductAttribute).filter(
                ProductAttribute.product_id == product.id
            ).all()
            existing_names = {a.attribute_name for a in existing_attrs}

            # Extract attributes
            new_attrs = extract_all_attributes(product)

            # Add new attributes
            added_for_product = 0
            for name, value in new_attrs.items():
                if name not in existing_names and value:
                    attr = ProductAttribute(
                        product_id=product.id,
                        attribute_name=name,
                        attribute_value=str(value),
                        extraction_method='backfill_script',
                        created_at=datetime.utcnow()
                    )
                    session.add(attr)
                    attrs_added += 1
                    added_for_product += 1

            if added_for_product > 0:
                products_updated += 1

            processed += 1

            # Commit in batches
            if processed % batch_size == 0:
                session.commit()
                print(f"  Processed {processed}/{total} products, {attrs_added} attributes added")

        # Final commit
        session.commit()

        print(f"\nBackfill complete!")
        print(f"  Products processed: {processed}")
        print(f"  Products updated: {products_updated}")
        print(f"  Attributes added: {attrs_added}")

        return {
            'processed': processed,
            'products_updated': products_updated,
            'attrs_added': attrs_added
        }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Backfill product attributes')
    parser.add_argument('--stores', nargs='+', help='Specific stores to process')
    parser.add_argument('--limit', type=int, help='Limit number of products')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for commits')

    args = parser.parse_args()

    stores = args.stores or ['woodenstreet', 'urbanladder', 'durian', 'homecentre']

    print(f"Backfilling attributes for stores: {stores}")
    backfill_attributes(stores=stores, batch_size=args.batch_size, limit=args.limit)
