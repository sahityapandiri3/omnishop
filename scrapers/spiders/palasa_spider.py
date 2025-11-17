"""
Palasa spider for planters and home decor
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class PalasaSpider(BaseProductSpider):
    """Spider for scraping Palasa planters and home decor"""

    name = 'palasa'
    allowed_domains = ['palasa.co.in', 'www.palasa.co.in']

    # Main category URLs to scrape
    start_urls = [
        # Main collection
        'https://www.palasa.co.in/collections/all',

        # Product categories
        'https://www.palasa.co.in/collections/floor-planters-online-india',
        'https://www.palasa.co.in/collections/desk-planters',
        'https://www.palasa.co.in/collections/decor-accents',
        'https://www.palasa.co.in/collections/planters-with-stands',
        'https://www.palasa.co.in/collections/faux-plants',

        # By placement
        'https://www.palasa.co.in/collections/outdoor-planters',
        'https://www.palasa.co.in/collections/indoor-planters',
        'https://www.palasa.co.in/collections/living-room-decor',
        'https://www.palasa.co.in/collections/bedroom-decor',
        'https://www.palasa.co.in/collections/balcony-planters',

        # By price
        'https://www.palasa.co.in/collections/under-10k',

        # Special collections
        'https://www.palasa.co.in/collections/new-arrivals',
        'https://www.palasa.co.in/collections/best-sellers',
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
                attributes['tags'] = tags

            # Extract vendor as brand
            brand = product.get('vendor', 'Studio Palasa')

            # Extract product options (size, color, material)
            options = product.get('options', [])
            for option in options:
                if isinstance(option, dict):
                    option_name = option.get('name', '').lower()
                    option_values = option.get('values', [])
                    if option_values:
                        attributes[option_name] = ', '.join(str(v) for v in option_values)

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
            # From: https://www.palasa.co.in/products/product-handle.json
            # To: https://www.palasa.co.in/products/product-handle
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
            # Extract category from URL like /collections/floor-planters-online-india
            match = re.search(r'/collections/([^/?]+)', url)
            if match:
                category = match.group(1).replace('-online-india', '').replace('-', ' ').title()
                return category
        except Exception:
            pass

        return "Home Decor"
