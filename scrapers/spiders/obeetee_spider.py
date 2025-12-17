"""
Obeetee spider for premium rugs and carpets
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class ObeeteeSpider(BaseProductSpider):
    """Spider for scraping Obeetee premium rugs and carpets"""

    name = 'obeetee'
    allowed_domains = ['obeetee.in', 'www.obeetee.in']

    # Main category URLs to scrape (all rug collections)
    start_urls = [
        # All rugs - main collection
        'https://obeetee.in/collections/all-rugs',
        # Style-based collections
        'https://obeetee.in/collections/traditional-living',
        'https://obeetee.in/collections/geometric',
        'https://obeetee.in/collections/abstract',
        'https://obeetee.in/collections/contemporary-living',
    ]

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

    def feet_to_inches(self, feet_value: str) -> str:
        """Convert feet to inches (1 foot = 12 inches)."""
        try:
            feet = float(feet_value)
            inches = round(feet * 12, 1)
            return str(inches)
        except (ValueError, TypeError):
            return feet_value

    def extract_rug_dimensions(self, text: str) -> Dict[str, str]:
        """
        Extract rug dimensions from description text.
        Rugs typically have length x width format.
        Convert to inches for consistency.
        """
        if not text:
            return {}

        dimensions = {}

        # Pattern 1: "8 x 10 ft" or "8' x 10'" (feet format - common for rugs)
        match = re.search(
            r"(\d+\.?\d*)\s*[''′]?\s*[x×]\s*(\d+\.?\d*)\s*[''′]?\s*(?:ft|feet)?",
            text, re.IGNORECASE
        )
        if match:
            # Assume feet, convert to inches
            dimensions['width'] = self.feet_to_inches(match.group(1))
            dimensions['height'] = self.feet_to_inches(match.group(2))  # length for rugs
            return dimensions

        # Pattern 2: "240 x 300 cm" (cm format)
        match = re.search(
            r'(\d+\.?\d*)\s*(?:cm)?\s*[x×]\s*(\d+\.?\d*)\s*(?:cm)?',
            text, re.IGNORECASE
        )
        if match:
            dimensions['width'] = self.cm_to_inches(match.group(1))
            dimensions['height'] = self.cm_to_inches(match.group(2))
            return dimensions

        # Pattern 3: Individual dimensions
        width_match = re.search(r'(?:width|w)[:\s]*(\d+\.?\d*)\s*(?:cm|ft|inch)?', text, re.IGNORECASE)
        if width_match:
            dimensions['width'] = self.cm_to_inches(width_match.group(1))

        length_match = re.search(r'(?:length|l|height|h)[:\s]*(\d+\.?\d*)\s*(?:cm|ft|inch)?', text, re.IGNORECASE)
        if length_match:
            dimensions['height'] = self.cm_to_inches(length_match.group(1))

        return dimensions

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Shopify product link selectors
        product_selectors = [
            'a[href*="/products/"]:not(.logo-bar__link):not(.site-nav__link)::attr(href)',
            '.product-card a::attr(href)',
            '.grid-product a::attr(href)',
            '.product-item a::attr(href)',
            'a.product-link::attr(href)',
            '.collection-product a::attr(href)',
            '.product-grid-item a::attr(href)',
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
                    meta={'category': 'Rugs'}  # All Obeetee products are rugs
                )

        # Follow pagination
        next_page_selectors = [
            'a[rel="next"]::attr(href)',
            '.pagination__next a::attr(href)',
            'a.pagination-next::attr(href)',
            'link[rel="next"]::attr(href)',
        ]

        for selector in next_page_selectors:
            next_page = response.css(selector).get()
            if next_page:
                next_page_url = urljoin(response.url, next_page)
                self.logger.info(f"Following pagination: {next_page_url}")
                yield scrapy.Request(
                    url=next_page_url,
                    callback=self.parse,
                    meta={'category': 'Rugs'}
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

            # Category - always Rugs for Obeetee
            category = 'Rugs'

            # Extract images
            image_urls = []
            images = product.get('images', [])
            for img in images[:10]:
                if isinstance(img, dict) and 'src' in img:
                    image_urls.append(img['src'])

            # Extract attributes
            attributes = {}

            # Extract tags (may include style info like "traditional", "geometric")
            tags = product.get('tags', '')
            if tags:
                tag_list = tags if isinstance(tags, list) else [t.strip() for t in tags.split(',')]
                attributes['tags'] = ', '.join(tag_list)

                # Extract style from tags
                style_keywords = ['traditional', 'modern', 'contemporary', 'geometric', 'abstract', 'floral', 'tribal']
                found_styles = [style for style in style_keywords if any(style in t.lower() for t in tag_list)]
                if found_styles:
                    attributes['style'] = ', '.join(found_styles)

            # Extract vendor/brand - may include designer name
            vendor = product.get('vendor', 'Obeetee')
            brand = f"Obeetee ({vendor})" if vendor and vendor.lower() != 'obeetee' else 'Obeetee'

            # Extract product options (size is crucial for rugs)
            options = product.get('options', [])
            for option in options:
                if isinstance(option, dict):
                    option_name = option.get('name', '').lower()
                    option_values = option.get('values', [])
                    if option_values:
                        attributes[option_name] = ', '.join(str(v) for v in option_values)

            # Extract dimensions from variant title or description
            # Rug sizes often in variant title like "8 x 10 ft"
            variant_title = variant.get('title', '')
            dims = self.extract_rug_dimensions(variant_title)
            if not dims and description:
                dims = self.extract_rug_dimensions(description)
            if not dims and name:
                dims = self.extract_rug_dimensions(name)

            if dims.get('width'):
                attributes['width'] = dims['width']
            if dims.get('height'):
                attributes['height'] = dims['height']

            # Extract materials (common rug materials)
            if description:
                material_keywords = ['wool', 'silk', 'bamboo silk', 'viscose', 'jute', 'cotton',
                                   'hand-knotted', 'hand-woven', 'hand-tufted', 'flat-weave',
                                   'persian', 'oriental']
                found_materials = [mat for mat in material_keywords if mat in description.lower()]
                if found_materials:
                    attributes['materials'] = ', '.join(found_materials)

                # Extract weave type
                weave_keywords = ['hand-knotted', 'hand-woven', 'hand-tufted', 'flat-weave', 'machine-made']
                found_weaves = [w for w in weave_keywords if w in description.lower()]
                if found_weaves:
                    attributes['weave_type'] = ', '.join(found_weaves)

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
