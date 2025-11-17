"""
Objectry spider for furniture and home decor
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class ObjectrySpider(BaseProductSpider):
    """Spider for scraping Objectry furniture and home decor"""

    name = 'objectry'
    allowed_domains = ['objectry.com']

    # Main category URLs to scrape
    start_urls = [
        # Main collections
        'https://objectry.com/collections/all',

        # Seating
        'https://objectry.com/collections/seating',
        'https://objectry.com/collections/sofas',
        'https://objectry.com/collections/chairs',
        'https://objectry.com/collections/stools-benches',

        # Tables
        'https://objectry.com/collections/tables',
        'https://objectry.com/collections/coffee-tables',
        'https://objectry.com/collections/side-tables',
        'https://objectry.com/collections/dining-tables',
        'https://objectry.com/collections/console-tables',

        # Storage
        'https://objectry.com/collections/storage',
        'https://objectry.com/collections/shelving',
        'https://objectry.com/collections/cabinets',
        'https://objectry.com/collections/sideboards',

        # Bedroom
        'https://objectry.com/collections/beds',
        'https://objectry.com/collections/bedroom',

        # Lighting
        'https://objectry.com/collections/lighting',
        'https://objectry.com/collections/table-lamps',
        'https://objectry.com/collections/floor-lamps',
        'https://objectry.com/collections/ceiling-lights',
        'https://objectry.com/collections/wall-lights',

        # Decor
        'https://objectry.com/collections/decor',
        'https://objectry.com/collections/mirrors',
        'https://objectry.com/collections/rugs',

        # Office
        'https://objectry.com/collections/desks',
        'https://objectry.com/collections/office',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
    }

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract category name from URL
        category = self.extract_category_from_url(response.url)

        # Shopify product link selectors
        product_selectors = [
            'a[href*="/products/"]::attr(href)',
            '.product-card a::attr(href)',
            '.grid-product a::attr(href)',
            '.product-item a::attr(href)',
            'a.product-link::attr(href)',
            '.collection-product a::attr(href)'
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
            # From: /collections/all/products/product-name
            # To: /products/product-name.json
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

            # Extract SKU
            external_id = variant.get('sku') or None

            # Extract category from product_type or tags
            category = response.meta.get('category', 'Furniture')
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
                attributes['tags'] = tags

            # Extract vendor as brand
            brand = product.get('vendor', 'Objectry')

            # Check availability
            is_available = variant.get('available', True)

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
                currency='INR'
            )

            # Fix source_url: Convert JSON API URL to HTML product page URL
            # From: https://objectry.com/products/product-handle.json
            # To: https://objectry.com/products/product-handle
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
            # Extract category from URL like /collections/sofas
            match = re.search(r'/collections/([^/?]+)', url)
            if match:
                category = match.group(1).replace('-', ' ').title()
                return category
        except Exception:
            pass

        return "Furniture"
