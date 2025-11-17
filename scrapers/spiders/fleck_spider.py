"""
Fleck spider for furniture, lighting, decor, and planters
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class FleckSpider(BaseProductSpider):
    """Spider for scraping Fleck contemporary furniture and decor"""

    name = 'fleck'
    allowed_domains = ['fleck.co.in', 'www.fleck.co.in', 'ammilstudio.myshopify.com']

    # Main category URLs to scrape (covering requested categories)
    start_urls = [
        # Furniture
        'https://fleck.co.in/collections/accent-furniture-lighting',
        'https://fleck.co.in/collections/tables',
        'https://fleck.co.in/collections/coffee-tables',
        'https://fleck.co.in/collections/side-nesting-tables',

        # Lighting
        'https://fleck.co.in/collections/lighting',
        'https://fleck.co.in/collections/hanging-lamps',
        'https://fleck.co.in/collections/hanging-and-pendant-lamps',
        'https://fleck.co.in/collections/table-floor-lamps',
        'https://fleck.co.in/collections/lanterns-candle-holders',

        # Decor & Accessories
        'https://fleck.co.in/collections/decor',
        'https://fleck.co.in/collections/decorative-objects',
        'https://fleck.co.in/collections/centrepieces-decorative-bowls',
        'https://fleck.co.in/collections/candle-holders',
        'https://fleck.co.in/collections/vases',

        # Planters
        'https://fleck.co.in/collections/planters',
        'https://fleck.co.in/collections/dried-flower-bunches',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 2,  # Be respectful (JavaScript-heavy site)
        'RANDOMIZE_DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 3,  # Lower concurrency for JS-heavy site
    }

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract category name from URL
        category = self.extract_category_from_url(response.url)

        # Shopify product link selectors (Be Yours theme)
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
                # Extract the product handle
                product_handle = link.split('/products/')[-1].split('?')[0]
                # Build JSON API URL
                json_url = urljoin(response.url, f'/products/{product_handle}.json')
                yield scrapy.Request(
                    url=json_url,
                    callback=self.parse_product,
                    meta={'category': category}
                )

        # Follow pagination
        next_page_selectors = [
            'a[rel="next"]::attr(href)',
            '.pagination__next a::attr(href)',
            'a.pagination-next::attr(href)',
            'a:contains("Next")::attr(href)',
            'link[rel="next"]::attr(href)'
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
            # The response is JSON from Shopify's API
            data = json.loads(response.text)
            product = data.get('product', {})

            if not product:
                self.logger.warning(f"No product data in response: {response.url}")
                return

            self.logger.info(f"Parsing product: {product.get('title')}")

            # Extract basic information
            name = product.get('title', 'Unknown Product')
            description = product.get('body_html', '')

            # Remove HTML tags from description
            if description:
                description = re.sub(r'<[^>]+>', '', description).strip()

            # Get first variant for price
            variants = product.get('variants', [])
            if not variants:
                self.logger.warning(f"No variants found for product: {name}")
                return

            variant = variants[0]
            price = self.extract_price(str(variant.get('price', '')))

            if not price:
                self.logger.warning(f"No price found for product: {name}")
                return

            # Extract original price (compare_at_price)
            original_price = None
            compare_at_price = variant.get('compare_at_price')
            if compare_at_price:
                original_price = self.extract_price(str(compare_at_price))

            # Extract SKU or use product ID as external_id
            external_id = variant.get('sku') or str(product.get('id', ''))

            # Extract category from product_type or tags or meta category
            category = response.meta.get('category', 'Home Decor')
            if product.get('product_type'):
                category = product.get('product_type')

            # Extract images
            image_urls = []
            images = product.get('images', [])
            for img in images[:10]:  # Limit to 10 images
                if isinstance(img, dict) and 'src' in img:
                    image_urls.append(img['src'])

            # Extract attributes
            attributes = {}

            # Extract tags
            tags = product.get('tags', '')
            if tags:
                attributes['tags'] = tags if isinstance(tags, str) else ', '.join(tags)

            # Extract vendor/brand - Fleck features different designers
            vendor = product.get('vendor', 'Fleck')
            brand = f"Fleck ({vendor})" if vendor and vendor != 'Fleck' else 'Fleck'

            # Extract product options (size, color, material, finish)
            options = product.get('options', [])
            for option in options:
                if isinstance(option, dict):
                    option_name = option.get('name', '').lower()
                    option_values = option.get('values', [])
                    if option_values:
                        attributes[option_name] = ', '.join(str(v) for v in option_values)

            # Extract dimensions from description or metafields
            if description:
                # Try to extract dimensions (common formats: LxWxH, L x W x H)
                dim_match = re.search(r'(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|inch|")', description, re.IGNORECASE)
                if dim_match:
                    attributes['dimensions'] = f"{dim_match.group(1)} x {dim_match.group(2)} x {dim_match.group(3)}"

                # Try to extract materials
                material_keywords = ['wood', 'metal', 'brass', 'copper', 'glass', 'ceramic', 'marble', 'stone', 'fabric', 'leather']
                found_materials = [mat for mat in material_keywords if mat in description.lower()]
                if found_materials:
                    attributes['materials'] = ', '.join(found_materials)

            # Check availability
            is_available = variant.get('available', True)

            # Check if on sale
            is_on_sale = original_price and original_price > price if original_price else False

            # Create product item
            item = self.create_product_item(
                response=response,
                name=self.clean_text(name),
                price=price,
                external_id=external_id,
                description=self.clean_text(description),
                brand=brand,
                category=self.normalize_category(category),
                image_urls=image_urls,
                attributes=attributes,
                is_available=is_available,
                is_on_sale=is_on_sale,
                original_price=original_price,
                currency='INR'
            )

            # Fix source_url: Convert JSON API URL to HTML product page URL
            if item['source_url'].endswith('.json'):
                item['source_url'] = item['source_url'].replace('.json', '')
                self.logger.info(f"Fixed product URL: {item['source_url']}")

            yield item

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for {response.url}: {str(e)}")
            self.errors_count += 1
        except Exception as e:
            self.logger.error(f"Error parsing product {response.url}: {str(e)}")
            self.errors_count += 1

    def extract_category_from_url(self, url: str) -> str:
        """Extract category name from collection URL"""
        try:
            # Extract category from URL like /collections/hanging-and-pendant-lamps
            match = re.search(r'/collections/([^/?]+)', url)
            if match:
                category = match.group(1).replace('-', ' ').title()

                # Map specific collections to standard categories
                category_lower = category.lower()
                if any(keyword in category_lower for keyword in ['table', 'coffee', 'side', 'nesting', 'accent furniture']):
                    return 'Furniture'
                elif any(keyword in category_lower for keyword in ['lamp', 'light', 'lantern', 'hanging', 'pendant']):
                    return 'Lighting'
                elif any(keyword in category_lower for keyword in ['planter', 'flower bunch', 'dried flower']):
                    return 'Plants & Planters'
                elif any(keyword in category_lower for keyword in ['decor', 'decorative', 'centrepiece', 'bowl', 'candle', 'vase']):
                    return 'Decor & Accessories'

                return category
        except Exception:
            pass

        return "Home Decor"
