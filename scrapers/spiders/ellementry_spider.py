"""
Ellementry spider for home decor, furniture, lighting, and textiles
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class EllementrySpider(BaseProductSpider):
    """Spider for scraping Ellementry home decor, furniture, and lighting"""

    name = 'ellementry'
    allowed_domains = ['ellementry.com', 'www.ellementry.com']

    # Main category URLs to scrape (18 categories)
    start_urls = [
        # Home accents
        'https://www.ellementry.com/collections/home-accents',
        # Vases
        'https://www.ellementry.com/collections/table-decor-vase',
        # Planters
        'https://www.ellementry.com/collections/planter',
        # Cushion covers
        'https://www.ellementry.com/collections/cushion-cover',
        # Wall decor
        'https://www.ellementry.com/collections/wall-decor',
        # Dining tables
        'https://www.ellementry.com/collections/dining-table',
        # Dining chairs
        'https://www.ellementry.com/collections/dining-room-chair',
        # Pendant lamps
        'https://www.ellementry.com/collections/pendant-lamp',
        # Table lamps
        'https://www.ellementry.com/collections/table-lamp',
        # Floor lamps
        'https://www.ellementry.com/collections/floor-lamp',
        # Sculptures
        'https://www.ellementry.com/collections/sculpture',
        # Coffee tables
        'https://www.ellementry.com/collections/coffee-table',
        # Side tables
        'https://www.ellementry.com/collections/living-room-side-table',
        # Cabinets
        'https://www.ellementry.com/collections/cabinet',
        # Benches
        'https://www.ellementry.com/collections/living-room-bench',
        # Accent chairs
        'https://www.ellementry.com/collections/living-chair',
        # Ottomans
        'https://www.ellementry.com/collections/ottoman',
        # Rugs
        'https://www.ellementry.com/collections/rugs',
    ]

    # Category mapping from URL to Omnishop category
    CATEGORY_MAP = {
        'home-accents': 'Decor & Accessories',
        'table-decor-vase': 'Vases',
        'planter': 'Planters',
        'cushion-cover': 'Cushion Cover',
        'wall-decor': 'Wall Art',
        'dining-table': 'Dining Table',
        'dining-room-chair': 'Dining Chair',
        'pendant-lamp': 'Pendant Lamps',
        'table-lamp': 'Table Lamps',
        'floor-lamp': 'Floor Lamp',
        'sculpture': 'Sculptures',
        'coffee-table': 'Coffee Table',
        'living-room-side-table': 'Side Table',
        'cabinet': 'Cabinet',
        'living-room-bench': 'Bench',
        'living-chair': 'Accent Chair',
        'ottoman': 'Ottoman',
        'rugs': 'Rugs',
    }

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 3,
    }

    def cm_to_inches(self, cm_value: str) -> str:
        """Convert cm to inches (1 inch = 2.54 cm)."""
        try:
            cm = float(cm_value)
            inches = round(cm / 2.54, 1)
            return str(inches)
        except (ValueError, TypeError):
            return cm_value

    def extract_dimensions_from_text(self, text: str) -> Dict[str, str]:
        """Extract width, height, depth from description text and convert to inches."""
        if not text:
            return {}

        dimensions = {}

        # Pattern 1: "L x W x H cm" or "19cm x 19cm x 23cm" (three dimensions)
        match = re.search(
            r'(\d+\.?\d*)\s*(?:cm)?\s*[x×]\s*(\d+\.?\d*)\s*(?:cm)?\s*[x×]\s*(\d+\.?\d*)\s*(?:cm)?',
            text, re.IGNORECASE
        )
        if match:
            dimensions['width'] = self.cm_to_inches(match.group(1))
            dimensions['depth'] = self.cm_to_inches(match.group(2))
            dimensions['height'] = self.cm_to_inches(match.group(3))
            return dimensions

        # Pattern 2: "W x H cm" (two dimensions - for cushion covers, wall art, rugs)
        match = re.search(
            r'(\d+\.?\d*)\s*(?:cm)?\s*[x×]\s*(\d+\.?\d*)\s*(?:cm)?',
            text, re.IGNORECASE
        )
        if match:
            dimensions['width'] = self.cm_to_inches(match.group(1))
            dimensions['height'] = self.cm_to_inches(match.group(2))
            return dimensions

        # Pattern 3: Individual dimensions with labels like "L: 19cm W: 19cm H: 23cm"
        # or "(L) x (W) x (H)" format common in Ellementry
        length_match = re.search(r'(?:length|l)\s*[:\(]?\s*(\d+\.?\d*)\s*(?:cm)?', text, re.IGNORECASE)
        if length_match:
            dimensions['depth'] = self.cm_to_inches(length_match.group(1))

        width_match = re.search(r'(?:width|w)\s*[:\(]?\s*(\d+\.?\d*)\s*(?:cm)?', text, re.IGNORECASE)
        if width_match:
            dimensions['width'] = self.cm_to_inches(width_match.group(1))

        height_match = re.search(r'(?:height|h)\s*[:\(]?\s*(\d+\.?\d*)\s*(?:cm)?', text, re.IGNORECASE)
        if height_match:
            dimensions['height'] = self.cm_to_inches(height_match.group(1))

        return dimensions

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract category name from URL
        category = self.extract_category_from_url(response.url)

        # Shopify product link selectors
        product_selectors = [
            'a[href*="/products/"]:not(.logo-bar__link):not(.site-nav__link)::attr(href)',
            '.product-card a::attr(href)',
            '.grid-product a::attr(href)',
            '.product-item a::attr(href)',
            'a.product-link::attr(href)',
            '.collection-product a::attr(href)',
            '.product-grid-item a::attr(href)',
            '.card-information__wrapper a::attr(href)',
            '.products-flex .product a::attr(href)',
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Remove duplicates and filter valid product links
        product_links = list(set([link for link in product_links if link and '/products/' in link]))

        self.logger.info(f"Found {len(product_links)} product links on {response.url}")

        for link in product_links:
            # Convert product link to JSON API endpoint
            if '/products/' in link:
                product_handle = link.split('/products/')[-1].split('?')[0]
                json_url = urljoin(response.url, f'/products/{product_handle}.json')
                yield scrapy.Request(
                    url=json_url,
                    callback=self.parse_product,
                    meta={'category': category}
                )

        # Follow pagination (Ellementry may use "Load More" but also has next links)
        next_page_selectors = [
            'a[rel="next"]::attr(href)',
            '.pagination__next a::attr(href)',
            'a.pagination-next::attr(href)',
            'link[rel="next"]::attr(href)',
            '.pagination a:contains("Next")::attr(href)',
        ]

        for selector in next_page_selectors:
            next_page = response.css(selector).get()
            if next_page:
                next_page_url = urljoin(response.url, next_page)
                self.logger.info(f"Following pagination: {next_page_url}")
                yield scrapy.Request(
                    url=next_page_url,
                    callback=self.parse,
                    meta={'category': category}
                )
                break

    def parse_product(self, response):
        """Parse product JSON data from Shopify API"""
        try:
            data = json.loads(response.text)
            product = data.get('product', {})

            if not product:
                self.logger.warning(f"No product data in response: {response.url}")
                return

            name = product.get('title', 'Unknown Product')
            self.logger.info(f"Parsing product: {name}")

            # Get description and remove HTML tags
            description = product.get('body_html', '')
            if description:
                description = re.sub(r'<[^>]+>', ' ', description).strip()
                description = re.sub(r'\s+', ' ', description)

            # Get variants
            variants = product.get('variants', [])
            if not variants:
                self.logger.warning(f"No variants found for product: {name}")
                return

            # Use first variant (Shopify public JSON API doesn't include 'available' field)
            # The availability status is only in storefront JS, not in /products/{handle}.json
            variant = variants[0]
            price = self.extract_price(str(variant.get('price', '')))

            if not price:
                self.logger.warning(f"No price found for product: {name}")
                return

            # Extract original price
            original_price = None
            compare_at_price = variant.get('compare_at_price')
            if compare_at_price:
                original_price = self.extract_price(str(compare_at_price))

            # External ID
            external_id = variant.get('sku') or str(product.get('id', ''))

            # Category
            category = response.meta.get('category', 'Decor & Accessories')

            # Extract images
            image_urls = []
            images = product.get('images', [])
            for img in images[:10]:
                if isinstance(img, dict) and 'src' in img:
                    image_urls.append(img['src'])

            # Extract attributes
            attributes = {}

            # Extract tags
            tags = product.get('tags', '')
            if tags:
                attributes['tags'] = tags if isinstance(tags, str) else ', '.join(tags)

            # Extract vendor/brand
            vendor = product.get('vendor', 'Ellementry')
            brand = vendor if vendor else 'Ellementry'

            # Extract product options (size, color, material)
            options = product.get('options', [])
            for option in options:
                if isinstance(option, dict):
                    option_name = option.get('name', '').lower()
                    option_values = option.get('values', [])
                    if option_values:
                        attributes[option_name] = ', '.join(str(v) for v in option_values)

            # Extract dimensions from description
            if description:
                dims = self.extract_dimensions_from_text(description)
                if dims.get('width'):
                    attributes['width'] = dims['width']
                if dims.get('height'):
                    attributes['height'] = dims['height']
                if dims.get('depth'):
                    attributes['depth'] = dims['depth']

                # Extract materials (Ellementry uses ceramic, wood, etc.)
                material_keywords = ['ceramic', 'stoneware', 'porcelain', 'terracotta',
                                   'mango wood', 'sheesham', 'teak', 'wood', 'wooden',
                                   'metal', 'brass', 'iron', 'copper', 'glass',
                                   'cotton', 'jute', 'wool', 'fabric', 'rattan', 'cane']
                found_materials = [mat for mat in material_keywords if mat in description.lower()]
                if found_materials:
                    attributes['materials'] = ', '.join(found_materials)

            # Availability
            is_available = True

            # Check if on sale
            is_on_sale = original_price and original_price > price if original_price else False

            # Create product item
            item = self.create_product_item(
                response=response,
                name=self.clean_text(name),
                price=price,
                external_id=external_id,
                description=self.clean_text(description) if description else '',
                brand=brand,
                category=self.normalize_category(category),
                image_urls=image_urls,
                attributes=attributes,
                is_available=is_available,
                is_on_sale=is_on_sale,
                original_price=original_price,
                currency='INR'
            )

            # Fix source_url
            if item['source_url'].endswith('.json'):
                item['source_url'] = item['source_url'].replace('.json', '')

            yield item

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for {response.url}: {str(e)}")
            self.errors_count += 1
        except Exception as e:
            self.logger.error(f"Error parsing product {response.url}: {str(e)}")
            self.errors_count += 1

    def extract_category_from_url(self, url: str) -> str:
        """Extract category name from collection URL and map to Omnishop category"""
        try:
            match = re.search(r'/collections/([^/?]+)', url)
            if match:
                collection_slug = match.group(1).lower()
                # Use our category mapping
                if collection_slug in self.CATEGORY_MAP:
                    return self.CATEGORY_MAP[collection_slug]
                # Fallback to cleaned slug
                return collection_slug.replace('-', ' ').title()
        except Exception:
            pass
        return "Decor & Accessories"
