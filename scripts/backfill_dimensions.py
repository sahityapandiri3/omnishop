#!/usr/bin/env python3
"""
Backfill product dimensions from descriptions and product pages.

This script extracts height, width, depth, and diameter dimensions from:
1. Product descriptions stored in the database
2. Product pages (by re-fetching if needed)

All dimensions are standardized to INCHES.

Usage:
    python scripts/backfill_dimensions.py [--store STORE_NAME] [--dry-run] [--fetch-pages] [--limit N] [--from-scratch]

Examples:
    # Dry run - show what would be updated
    python scripts/backfill_dimensions.py --dry-run

    # Backfill from descriptions only (no web fetching)
    python scripts/backfill_dimensions.py

    # Re-extract all dimensions from scratch (ignore existing attributes)
    python scripts/backfill_dimensions.py --from-scratch

    # Backfill for a specific store
    python scripts/backfill_dimensions.py --store "The House of Things"

    # Fetch product pages to get dimensions (slower but more accurate)
    python scripts/backfill_dimensions.py --fetch-pages --limit 100
"""

import re
import sys
import asyncio
import argparse
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.insert(0, '/Users/sahityapandiri/Omnishop')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = "postgresql://sahityapandiri@localhost:5432/omnishop"

@dataclass
class ProductDimensions:
    """Extracted product dimensions - all standardized to inches"""
    height: Optional[float] = None
    width: Optional[float] = None
    depth: Optional[float] = None
    diameter: Optional[float] = None  # For planters, round tables, etc.
    unit: str = "cm"  # Original unit detected (cm, inch, mm, ft, m)
    raw_text: Optional[str] = None  # Original text where dimensions were found


class DimensionExtractor:
    """Extract dimensions from text using various patterns"""

    # Patterns for extracting dimensions (order matters - more specific first)
    DIMENSION_PATTERNS = [
        # Pattern: "15 cm (6.2") L x 15 cm (6.2") W x 76.2 cm (30") H"
        r'(\d+(?:\.\d+)?)\s*(?:cm|CM)\s*(?:\([^)]+\))?\s*[Ll]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:cm|CM)\s*(?:\([^)]+\))?\s*[Ww]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:cm|CM)\s*(?:\([^)]+\))?\s*[Hh]',

        # Pattern: "L x W x H: 100 x 50 x 75 cm"
        r'[Ll]\s*[xX×]\s*[Ww]\s*[xX×]\s*[Hh]\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:cm|CM|inches?|in|")',

        # Pattern: "Dimensions: 100 x 50 x 75 cm" or "Size: 100 x 50 x 75"
        r'(?:Dimensions?|Size)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:cm|CM|inches?|in|")?',

        # Pattern: "100cm x 50cm x 75cm" or "100 cm x 50 cm x 75 cm"
        r'(\d+(?:\.\d+)?)\s*(?:cm|CM)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:cm|CM)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:cm|CM)',

        # Pattern: "100" x 50" x 75"" (inches)
        r'(\d+(?:\.\d+)?)\s*["\u201d]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\u201d]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\u201d]',

        # Pattern: "100 x 50 x 75" (generic, assume cm)
        r'(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)',

        # Pattern: "W x D x H" format with labels
        r'[Ww](?:idth)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cm|CM|inches?|in|")?\s*[,;xX×]\s*[Dd](?:epth)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cm|CM|inches?|in|")?\s*[,;xX×]\s*[Hh](?:eight)?\s*[:\-]?\s*(\d+(?:\.\d+)?)',

        # Pattern: "H x W x D" format
        r'[Hh](?:eight)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cm|CM|inches?|in|")?\s*[,;xX×]\s*[Ww](?:idth)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cm|CM|inches?|in|")?\s*[,;xX×]\s*[Dd](?:epth)?\s*[:\-]?\s*(\d+(?:\.\d+)?)',
    ]

    # Patterns for individual dimensions
    # Note: (?:cms?|CMS?) matches both "cm" and "cms" (common variations)
    INDIVIDUAL_PATTERNS = {
        'height': [
            r'[Hh](?:eight|t)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")',
            r'(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")\s*[Hh](?:eight|igh)?',
            r'[Hh](?:eight)?\s*[:\-]?\s*(\d+(?:\.\d+)?)',
        ],
        'width': [
            r'[Ww](?:idth|d)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")',
            r'(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")\s*[Ww](?:idth|ide)?',
            r'[Ww](?:idth)?\s*[:\-]?\s*(\d+(?:\.\d+)?)',
        ],
        'depth': [
            r'[Dd](?:epth|p)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")',
            r'(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")\s*[Dd](?:epth|eep)?',
            r'[Ll](?:ength)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")',  # Length as depth
            r'[Dd](?:epth)?\s*[:\-]?\s*(\d+(?:\.\d+)?)',
        ],
        'diameter': [
            r'[Dd](?:ia(?:meter)?|iam)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")',
            r'(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")\s*[Dd](?:ia(?:meter)?)?',
            r'[Øø]\s*(\d+(?:\.\d+)?)\s*(?:cms?|CMS?|inches?|in|")?',  # Diameter symbol
            r'(?:diameter|Diameter)\s*[:\-]?\s*(\d+(?:\.\d+)?)',
        ],
    }

    # Unit detection patterns - ORDER MATTERS! More specific patterns first.
    # We check cm/cms BEFORE inch to avoid false positives like "in India"
    UNIT_PATTERNS = [
        (r'(?:cm|cms|CM|CMS|centimeter|centimeters)\b', 'cm'),  # Check cm/cms first
        (r'(?:mm|MM|millimeter|millimeters)\b', 'mm'),
        (r'(?:ft|feet|foot)\b', 'ft'),
        (r'\binches?\b|\bin\b(?=\s*\d)|"\b|\u201d\b', 'inch'),  # "in" only when followed by digit
        (r'\bm\b|\bmeters?\b', 'm'),
    ]

    def extract_from_text(self, text: str) -> Optional[ProductDimensions]:
        """Extract dimensions from text"""
        if not text:
            return None

        # Normalize text
        text = text.replace('\n', ' ').replace('\r', ' ')

        # Try combined patterns first (L x W x H)
        for pattern in self.DIMENSION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    # Extract values first
                    extracted = {
                        'width': float(groups[0]),
                        'depth': float(groups[1]),
                        'height': float(groups[2]),
                    }
                    # Detect unit with sanity checking based on extracted values
                    unit = self._detect_unit(text, extracted)

                    dims = ProductDimensions(
                        width=extracted['width'],
                        depth=extracted['depth'],
                        height=extracted['height'],
                        unit=unit,
                        raw_text=match.group(0)
                    )
                    return dims

        # Try individual patterns - extract all values first, then detect unit
        extracted = {}
        raw_texts = []

        for dim_name, patterns in self.INDIVIDUAL_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    extracted[dim_name] = float(match.group(1))
                    raw_texts.append(match.group(0))
                    break

        if not extracted:
            return None

        # Detect unit with sanity checking based on ALL extracted values
        unit = self._detect_unit(text, extracted)

        dims = ProductDimensions(
            height=extracted.get('height'),
            width=extracted.get('width'),
            depth=extracted.get('depth'),
            diameter=extracted.get('diameter'),
            unit=unit,
            raw_text='; '.join(raw_texts)
        )

        return dims

    def _detect_unit(self, text: str, extracted_values: dict = None) -> str:
        """Detect the measurement unit used in text.

        Uses multiple strategies:
        1. Look for units near dimension keywords (Height: X cm)
        2. Apply sanity checks based on extracted values
        3. Default to cm for ambiguous cases
        """
        # Strategy 1: Look for units specifically near dimension values
        # Pattern: dimension keyword followed by number and unit
        dimension_with_unit_patterns = [
            r'(?:height|width|depth|length|diameter|H|W|D|L)\s*[:\-]?\s*\d+(?:\.\d+)?\s*(cms?|inches?|in|mm|ft|feet|m)\b',
            r'\d+(?:\.\d+)?\s*(cms?|inches?|in|mm|ft|feet|m)\s*(?:height|width|depth|length|H|W|D|L)',
            r'\d+(?:\.\d+)?\s*[xX×]\s*\d+(?:\.\d+)?\s*[xX×]\s*\d+(?:\.\d+)?\s*(cms?|inches?|in|mm|ft|feet|m)',
        ]

        for pattern in dimension_with_unit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                unit_str = match.group(1).lower()
                if unit_str in ('cm', 'cms'):
                    return 'cm'
                elif unit_str in ('inch', 'inches', 'in'):
                    return 'inch'
                elif unit_str == 'mm':
                    return 'mm'
                elif unit_str in ('ft', 'feet'):
                    return 'ft'
                elif unit_str == 'm':
                    return 'm'

        # Strategy 2: Sanity check based on extracted values
        # Furniture dimensions have reasonable ranges
        if extracted_values:
            values = [v for v in extracted_values.values() if v is not None]
            if values:
                max_val = max(values)
                min_val = min(values)

                # If values are reasonable for inches (1-120), assume inches
                if 1 <= max_val <= 120 and min_val >= 1:
                    return 'inch'
                # If values are reasonable for cm (2-300), assume cm
                elif 2 <= max_val <= 300:
                    return 'cm'
                # Very small values might be meters
                elif max_val <= 3:
                    return 'm'

        # Strategy 3: Fall back to checking entire text, but prefer cm/inch over feet
        # (feet is often in product names like "5 feet sofa" but actual dims are in cm/inch)
        for pattern, unit in self.UNIT_PATTERNS:
            if unit == 'ft':  # Skip feet in general text search - too many false positives
                continue
            if re.search(pattern, text, re.IGNORECASE):
                return unit

        return 'cm'  # Default to cm

    def convert_to_inches(self, dims: ProductDimensions) -> ProductDimensions:
        """Convert dimensions to inches (standardized unit)"""
        if dims.unit == 'inch':
            return ProductDimensions(
                height=dims.height,
                width=dims.width,
                depth=dims.depth,
                diameter=dims.diameter,
                unit='inch',
                raw_text=dims.raw_text
            )

        # Conversion factors TO inches
        conversion = {
            'cm': 0.393701,     # 1 cm = 0.393701 inches
            'mm': 0.0393701,   # 1 mm = 0.0393701 inches
            'ft': 12,          # 1 foot = 12 inches
            'm': 39.3701,      # 1 meter = 39.3701 inches
        }

        factor = conversion.get(dims.unit, 0.393701)  # Default to cm conversion

        def convert(val):
            if val is None:
                return None
            result = round(val * factor, 2)  # Round to 2 decimal places
            return result

        return ProductDimensions(
            height=convert(dims.height),
            width=convert(dims.width),
            depth=convert(dims.depth),
            diameter=convert(dims.diameter),
            unit='inch',
            raw_text=dims.raw_text
        )


class PageFetcher:
    """Fetch product pages to extract dimensions"""

    # Store-specific dimension selectors
    STORE_SELECTORS = {
        'thehouseofthings': {
            'spec_table': '.product-info-main .product.attribute',
            'description': '.product.attribute.description .value',
        },
        'nicobar': {
            'spec_table': '.product-details table',
            'description': '.product-description',
        },
        'urbanladder': {
            'spec_table': '.specification-list',
            'description': '.product-description',
        },
        'pepperfry': {
            'spec_table': '.pf-spec-table',
            'description': '.product-desc',
        },
        'default': {
            'spec_table': 'table',
            'description': '.description, .product-description, [class*="desc"]',
        }
    }

    def __init__(self):
        self.extractor = DimensionExtractor()

    async def fetch_dimensions(self, url: str, store: str) -> Optional[ProductDimensions]:
        """Fetch product page and extract dimensions"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, follow_redirects=True)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch {url}: {response.status_code}")
                    return None

                soup = BeautifulSoup(response.text, 'html.parser')

                # Get store-specific selectors
                store_key = store.lower().replace(' ', '').replace('_', '')
                selectors = self.STORE_SELECTORS.get(store_key, self.STORE_SELECTORS['default'])

                # Try to find dimensions in specification table
                spec_elements = soup.select(selectors['spec_table'])
                for elem in spec_elements:
                    text = elem.get_text(separator=' ', strip=True)
                    dims = self.extractor.extract_from_text(text)
                    if dims and (dims.height or dims.width or dims.depth):
                        return dims

                # Try description
                desc_elements = soup.select(selectors['description'])
                for elem in desc_elements:
                    text = elem.get_text(separator=' ', strip=True)
                    dims = self.extractor.extract_from_text(text)
                    if dims and (dims.height or dims.width or dims.depth):
                        return dims

                # Try entire page body as fallback
                body_text = soup.get_text(separator=' ', strip=True)
                dims = self.extractor.extract_from_text(body_text)
                if dims and (dims.height or dims.width or dims.depth):
                    return dims

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")

        return None


class DimensionBackfiller:
    """Main backfill logic"""

    def __init__(self, dry_run: bool = False, fetch_pages: bool = False, from_scratch: bool = False):
        self.dry_run = dry_run
        self.fetch_pages = fetch_pages
        self.from_scratch = from_scratch  # If True, process ALL products regardless of existing dimensions
        self.extractor = DimensionExtractor()
        self.fetcher = PageFetcher() if fetch_pages else None

        # Database setup
        self.engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def get_products_without_dimensions(self, store: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get products that don't have dimension attributes"""
        query = """
            SELECT p.id, p.name, p.description, p.source_url, p.source_website
            FROM products p
            WHERE NOT EXISTS (
                SELECT 1 FROM product_attributes pa
                WHERE pa.product_id = p.id
                AND pa.attribute_name IN ('height', 'width', 'depth')
            )
        """

        if store:
            query += f" AND p.source_website = '{store}'"

        query += " ORDER BY p.id"

        if limit:
            query += f" LIMIT {limit}"

        result = self.session.execute(text(query))
        return [dict(row._mapping) for row in result]

    def get_products_with_descriptions(self, store: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get all products with descriptions (for re-extraction)"""
        query = """
            SELECT p.id, p.name, p.description, p.source_url, p.source_website
            FROM products p
            WHERE p.description IS NOT NULL AND p.description != ''
        """

        if store:
            query += f" AND p.source_website = '{store}'"

        query += " ORDER BY p.id"

        if limit:
            query += f" LIMIT {limit}"

        result = self.session.execute(text(query))
        return [dict(row._mapping) for row in result]

    def get_all_products_for_dimension_extraction(self, store: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get all products with their raw Dimensions attribute for re-extraction from scratch"""
        query = """
            SELECT
                p.id,
                p.name,
                p.description,
                p.source_url,
                p.source_website,
                MAX(CASE WHEN pa.attribute_name IN ('Dimensions', 'dimensions') THEN pa.attribute_value END) as raw_dimensions
            FROM products p
            LEFT JOIN product_attributes pa ON p.id = pa.product_id AND pa.attribute_name IN ('Dimensions', 'dimensions')
            WHERE 1=1
        """

        if store:
            query += f" AND p.source_website = '{store}'"

        query += " GROUP BY p.id, p.name, p.description, p.source_url, p.source_website ORDER BY p.id"

        if limit:
            query += f" LIMIT {limit}"

        result = self.session.execute(text(query))
        return [dict(row._mapping) for row in result]

    def delete_existing_dimensions(self, product_id: int) -> None:
        """Delete existing dimension attributes for a product"""
        if self.dry_run:
            return

        try:
            delete_query = text("""
                DELETE FROM product_attributes
                WHERE product_id = :pid
                AND attribute_name IN ('height', 'width', 'depth', 'diameter', 'dimension_unit')
            """)
            self.session.execute(delete_query, {'pid': product_id})
            self.session.commit()
        except Exception as e:
            logger.error(f"Error deleting dimensions for product {product_id}: {e}")
            self.session.rollback()

    def save_dimensions(self, product_id: int, dims: ProductDimensions) -> bool:
        """Save dimensions to product_attributes table (standardized to inches)"""
        if self.dry_run:
            return True

        try:
            # Convert to INCHES for consistency
            dims_inches = self.extractor.convert_to_inches(dims)

            # If from_scratch mode, delete existing dimensions first
            if self.from_scratch:
                self.delete_existing_dimensions(product_id)

            # Insert or update each dimension (including diameter)
            for attr_name in ['height', 'width', 'depth', 'diameter']:
                value = getattr(dims_inches, attr_name)
                if value is not None:
                    # Check if attribute exists
                    check_query = text("""
                        SELECT id FROM product_attributes
                        WHERE product_id = :pid AND attribute_name = :name
                    """)
                    existing = self.session.execute(check_query, {'pid': product_id, 'name': attr_name}).fetchone()

                    if existing:
                        # Update
                        update_query = text("""
                            UPDATE product_attributes
                            SET attribute_value = :value
                            WHERE product_id = :pid AND attribute_name = :name
                        """)
                        self.session.execute(update_query, {'pid': product_id, 'name': attr_name, 'value': str(value)})
                    else:
                        # Insert
                        insert_query = text("""
                            INSERT INTO product_attributes (product_id, attribute_name, attribute_value)
                            VALUES (:pid, :name, :value)
                        """)
                        self.session.execute(insert_query, {'pid': product_id, 'name': attr_name, 'value': str(value)})

            # Save unit as 'inches'
            unit_check = text("""
                SELECT id FROM product_attributes
                WHERE product_id = :pid AND attribute_name = 'dimension_unit'
            """)
            existing_unit = self.session.execute(unit_check, {'pid': product_id}).fetchone()

            if existing_unit:
                unit_update = text("""
                    UPDATE product_attributes
                    SET attribute_value = 'inches'
                    WHERE product_id = :pid AND attribute_name = 'dimension_unit'
                """)
                self.session.execute(unit_update, {'pid': product_id})
            else:
                unit_insert = text("""
                    INSERT INTO product_attributes (product_id, attribute_name, attribute_value)
                    VALUES (:pid, 'dimension_unit', 'inches')
                """)
                self.session.execute(unit_insert, {'pid': product_id})

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error saving dimensions for product {product_id}: {e}")
            self.session.rollback()
            return False

    async def backfill(self, store: Optional[str] = None, limit: Optional[int] = None):
        """Run the backfill process"""
        logger.info(f"Starting dimension backfill (dry_run={self.dry_run}, fetch_pages={self.fetch_pages}, from_scratch={self.from_scratch})")

        # Get products based on mode
        if self.from_scratch:
            # Process ALL products - re-extract dimensions from raw Dimensions attribute
            products = self.get_all_products_for_dimension_extraction(store, limit)
            logger.info(f"FROM SCRATCH MODE: Found {len(products)} products to process")
        else:
            # Only process products without existing dimensions
            products = self.get_products_without_dimensions(store, limit)
            logger.info(f"Found {len(products)} products without dimensions")

        stats = {
            'total': len(products),
            'extracted_from_raw_dimensions': 0,
            'extracted_from_description': 0,
            'extracted_from_page': 0,
            'no_dimensions_found': 0,
            'errors': 0,
        }

        for i, product in enumerate(products):
            product_id = product['id']
            name = product['name']
            description = product.get('description')
            source_url = product['source_url']
            source_website = product['source_website']
            raw_dimensions = product.get('raw_dimensions')  # From Dimensions/dimensions attribute

            logger.info(f"[{i+1}/{len(products)}] Processing: {name} ({source_website})")

            dims = None

            # Priority 1: Try extracting from raw Dimensions attribute
            if raw_dimensions:
                dims = self.extractor.extract_from_text(raw_dimensions)
                if dims and (dims.height or dims.width or dims.depth or dims.diameter):
                    logger.info(f"  Found in raw dimensions: H={dims.height}, W={dims.width}, D={dims.depth}, Dia={dims.diameter} {dims.unit}")
                    stats['extracted_from_raw_dimensions'] += 1

            # Priority 2: Try extracting from description
            if not dims and description:
                dims = self.extractor.extract_from_text(description)
                if dims and (dims.height or dims.width or dims.depth or dims.diameter):
                    logger.info(f"  Found in description: H={dims.height}, W={dims.width}, D={dims.depth}, Dia={dims.diameter} {dims.unit}")
                    stats['extracted_from_description'] += 1

            # Priority 3: If not found and fetch_pages is enabled, try fetching the page
            if not dims and self.fetch_pages and source_url:
                logger.info(f"  Fetching page: {source_url}")
                dims = await self.fetcher.fetch_dimensions(source_url, source_website)
                if dims and (dims.height or dims.width or dims.depth or dims.diameter):
                    logger.info(f"  Found on page: H={dims.height}, W={dims.width}, D={dims.depth}, Dia={dims.diameter} {dims.unit}")
                    stats['extracted_from_page'] += 1

            # Save dimensions if found
            if dims and (dims.height or dims.width or dims.depth or dims.diameter):
                # Convert to inches before saving
                dims_inches = self.extractor.convert_to_inches(dims)
                if self.dry_run:
                    logger.info(f"  [DRY RUN] Would save (in inches): H={dims_inches.height}, W={dims_inches.width}, D={dims_inches.depth}, Dia={dims_inches.diameter}")
                else:
                    if self.save_dimensions(product_id, dims):
                        logger.info(f"  Saved dimensions (in inches): H={dims_inches.height}, W={dims_inches.width}, D={dims_inches.depth}, Dia={dims_inches.diameter}")
                    else:
                        stats['errors'] += 1
            else:
                logger.debug(f"  No dimensions found")
                stats['no_dimensions_found'] += 1

        # Print summary
        logger.info("\n" + "="*60)
        logger.info("BACKFILL SUMMARY (ALL DIMENSIONS IN INCHES)")
        logger.info("="*60)
        logger.info(f"Total products processed: {stats['total']}")
        logger.info(f"Extracted from raw Dimensions attribute: {stats['extracted_from_raw_dimensions']}")
        logger.info(f"Extracted from description: {stats['extracted_from_description']}")
        logger.info(f"Extracted from page fetch: {stats['extracted_from_page']}")
        logger.info(f"No dimensions found: {stats['no_dimensions_found']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"Success rate: {100 * (stats['total'] - stats['no_dimensions_found'] - stats['errors']) / max(stats['total'], 1):.1f}%")

        if self.dry_run:
            logger.info("\n[DRY RUN] No changes were made to the database")

    def close(self):
        """Close database connection"""
        self.session.close()


async def main():
    parser = argparse.ArgumentParser(description='Backfill product dimensions (standardized to INCHES)')
    parser.add_argument('--store', type=str, help='Filter by store name')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--fetch-pages', action='store_true', help='Fetch product pages to extract dimensions')
    parser.add_argument('--limit', type=int, help='Limit number of products to process')
    parser.add_argument('--from-scratch', action='store_true',
                        help='Re-extract dimensions for ALL products (ignores existing dimension attributes)')

    args = parser.parse_args()

    backfiller = DimensionBackfiller(
        dry_run=args.dry_run,
        fetch_pages=args.fetch_pages,
        from_scratch=args.from_scratch
    )

    try:
        await backfiller.backfill(store=args.store, limit=args.limit)
    finally:
        backfiller.close()


if __name__ == '__main__':
    asyncio.run(main())
