"""
Josmo Studio spider for furniture and decor
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class JosmoSpider(BaseProductSpider):
    """Spider for scraping Josmo Studio furniture"""

    name = 'josmo'
    allowed_domains = ['josmostudio.com', 'www.josmostudio.com']

    # Category URLs to scrape (based on user's requested categories)
    start_urls = [
        # Sofas
        'https://www.josmostudio.com/collections/sofas-1',
        'https://www.josmostudio.com/collections/sofas-3-seater',
        'https://www.josmostudio.com/collections/sofas-2-seater',

        # Benches & Stools
        'https://www.josmostudio.com/collections/bar-stools',
        'https://www.josmostudio.com/collections/ottomans',

        # Tables
        'https://www.josmostudio.com/collections/coffee-tables',
        'https://www.josmostudio.com/collections/side-tables',
        'https://www.josmostudio.com/collections/dining-tables',
        'https://www.josmostudio.com/collections/study-tables',
        'https://www.josmostudio.com/collections/consoles',

        # Live Edge Tables
        'https://www.josmostudio.com/collections/live-edge-coffee-tables',
        'https://www.josmostudio.com/collections/live-edge-side-tables',
        'https://www.josmostudio.com/collections/live-edge-dining-tables',
        'https://www.josmostudio.com/collections/live-edge-consoles',

        # Beds
        'https://www.josmostudio.com/collections/beds',

        # Carpets
        'https://www.josmostudio.com/collections/carpets',

        # Lighting (if available)
        'https://www.josmostudio.com/collections/lighting',

        # Wall Art/Decor
        'https://www.josmostudio.com/collections/mirrors',
        'https://www.josmostudio.com/collections/wall-art',

        # Additional categories
        'https://www.josmostudio.com/collections/lounge-chairs',
        'https://www.josmostudio.com/collections/dining-chairs',
        'https://www.josmostudio.com/collections/study-chairs',
        'https://www.josmostudio.com/collections/bookshelves',
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
            '.pagination a[aria-label="Next"]::attr(href)',
        ]

        for selector in next_page_selectors:
            next_page = response.css(selector).get()
            if next_page:
                yield response.follow(next_page, callback=self.parse)
                break

    def parse_product(self, response):
        """Parse product JSON and extract product information"""
        try:
            data = json.loads(response.text)
            product = data.get('product', {})

            if not product:
                self.logger.warning(f"No product data found for {response.url}")
                return

            # Extract basic product information
            title = product.get('title', '')
            description = product.get('body_html', '') or product.get('description', '')
            vendor = product.get('vendor', 'Josmo Studio')
            product_type = product.get('product_type', '')
            tags = product.get('tags', [])

            # Get category from meta or product_type
            category = response.meta.get('category') or product_type or 'Furniture'

            # Extract variants and pricing
            variants = product.get('variants', [])
            if not variants:
                self.logger.warning(f"No variants found for {title}")
                return

            # Use first variant for primary product info
            first_variant = variants[0]
            price = float(first_variant.get('price', 0))
            compare_price = first_variant.get('compare_at_price')
            original_price = float(compare_price) if compare_price else None
            sku = first_variant.get('sku', '')

            # Check availability
            available = first_variant.get('available', False)
            stock_status = 'in_stock' if available else 'out_of_stock'

            # Extract images
            images = product.get('images', [])
            image_urls = [img.get('src') for img in images if img.get('src')]

            # Make sure image URLs are absolute and use HTTPS
            image_urls = [url if url.startswith('http') else f"https:{url}" for url in image_urls]

            # Extract product options and attributes
            options = product.get('options', [])
            attributes = {
                'vendor': vendor,
                'product_type': product_type,
                'tags': tags if isinstance(tags, list) else tags.split(',') if tags else [],
            }

            # Add options as attributes
            for option in options:
                option_name = option.get('name', '').lower()
                option_values = option.get('values', [])
                if option_values:
                    attributes[option_name] = option_values

            # Check if on sale
            is_on_sale = bool(original_price and original_price > price)

            # Create product item
            yield self.create_product_item(
                response=response,
                name=title,
                price=price,
                external_id=str(product.get('id')),
                description=self.clean_html(description),
                brand=vendor,
                category=self.normalize_category(category),
                image_urls=image_urls,
                attributes=attributes,
                sku=sku,
                original_price=original_price,
                is_available=available,
                stock_status=stock_status,
                is_on_sale=is_on_sale,
                currency='INR'
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON for {response.url}: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing product {response.url}: {e}")

    def extract_category_from_url(self, url: str) -> str:
        """Extract category name from URL"""
        if '/collections/' in url:
            category = url.split('/collections/')[-1].split('?')[0].split('/')[0]
            # Clean up category name
            category = category.replace('-', ' ').replace('_', ' ').title()
            return category
        return 'Furniture'

    def clean_html(self, html_text: str) -> str:
        """Clean HTML tags from text"""
        if not html_text:
            return ""

        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        # Remove extra whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text
