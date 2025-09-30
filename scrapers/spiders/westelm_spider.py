"""
West Elm spider for furniture, lighting, and rugs
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class WestElmSpider(BaseProductSpider):
    """Spider for scraping West Elm products"""

    name = 'westelm'
    allowed_domains = ['westelm.com']

    # Main category URLs to scrape
    start_urls = [
        # Furniture categories
        'https://www.westelm.com/shop/furniture/sofas-sectionals/',
        'https://www.westelm.com/shop/furniture/chairs/',
        'https://www.westelm.com/shop/furniture/tables/',
        'https://www.westelm.com/shop/furniture/storage/',
        'https://www.westelm.com/shop/furniture/bedroom/',
        'https://www.westelm.com/shop/furniture/office/',

        # Lighting categories
        'https://www.westelm.com/shop/lighting/table-lamps/',
        'https://www.westelm.com/shop/lighting/floor-lamps/',
        'https://www.westelm.com/shop/lighting/ceiling-lighting/',
        'https://www.westelm.com/shop/lighting/outdoor-lighting/',

        # Rugs and textiles
        'https://www.westelm.com/shop/rugs/',
        'https://www.westelm.com/shop/bedding/',
        'https://www.westelm.com/shop/pillows-throws/',
        'https://www.westelm.com/shop/window-treatments/',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 2,  # Be respectful to West Elm
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
    }

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract product links from category page
        product_links = response.css('a.product-tile-link::attr(href)').getall()

        for link in product_links:
            product_url = urljoin(response.url, link)
            yield scrapy.Request(
                url=product_url,
                callback=self.parse_product,
                meta={'category_url': response.url}
            )

        # Follow pagination
        next_page = response.css('a.next-page::attr(href)').get()
        if next_page:
            next_url = urljoin(response.url, next_page)
            yield scrapy.Request(
                url=next_url,
                callback=self.parse,
                meta={'category_url': response.meta.get('category_url', response.url)}
            )

        # Alternative pagination selector
        load_more = response.css('button[data-load-more]::attr(data-load-more)').get()
        if load_more:
            yield scrapy.Request(
                url=load_more,
                callback=self.parse,
                meta={'category_url': response.meta.get('category_url', response.url)}
            )

    def parse_product(self, response):
        """Parse individual product pages"""
        self.logger.info(f"Parsing product: {response.url}")

        try:
            # Extract basic product information
            name = self.extract_product_name(response)
            if not name:
                self.logger.warning(f"No product name found for {response.url}")
                return

            price = self.extract_product_price(response)
            if not price:
                self.logger.warning(f"No price found for {response.url}")
                return

            # Extract additional product details
            description = self.extract_product_description(response)
            brand = self.extract_product_brand(response)
            category = self.extract_product_category(response)
            external_id = self.extract_product_id(response)
            sku = self.extract_product_sku(response)
            image_urls = self.extract_product_images(response)
            attributes = self.extract_product_attributes(response)

            # Check availability
            is_available = self.extract_availability(response)
            is_on_sale = self.extract_sale_status(response)
            original_price = self.extract_original_price(response)

            # Create product item
            item = self.create_product_item(
                response=response,
                name=name,
                price=price,
                external_id=external_id,
                description=description,
                brand=brand,
                category=category,
                image_urls=image_urls,
                attributes=attributes,
                is_available=is_available,
                is_on_sale=is_on_sale,
                original_price=original_price,
                sku=sku
            )

            yield item

        except Exception as e:
            self.logger.error(f"Error parsing product {response.url}: {e}")
            self.errors_count += 1

    def extract_product_name(self, response) -> Optional[str]:
        """Extract product name"""
        # Try multiple selectors
        selectors = [
            'h1.product-title::text',
            'h1[data-test-id="product-title"]::text',
            '.product-details h1::text',
            '.product-info h1::text'
        ]

        for selector in selectors:
            name = self.extract_text(response.css(selector))
            if name:
                return self.clean_text(name)

        return None

    def extract_product_price(self, response) -> Optional[float]:
        """Extract product price"""
        # Try multiple price selectors
        selectors = [
            '.price-current .price-amount::text',
            '.product-price .price-amount::text',
            '[data-test-id="price-current"] .price-amount::text',
            '.price-display .price-amount::text',
            '.price .price-amount::text'
        ]

        for selector in selectors:
            price_text = self.extract_text(response.css(selector))
            if price_text:
                price = self.extract_price(price_text)
                if price:
                    return price

        # Try JSON-LD structured data
        price = self.extract_price_from_json_ld(response)
        if price:
            return price

        return None

    def extract_product_description(self, response) -> Optional[str]:
        """Extract product description"""
        # Try multiple description selectors
        selectors = [
            '.product-description .description-text::text',
            '.product-details .description::text',
            '[data-test-id="product-description"]::text',
            '.product-info .description::text'
        ]

        descriptions = []
        for selector in selectors:
            desc_parts = self.extract_text_list(response.css(selector))
            descriptions.extend(desc_parts)

        if descriptions:
            return self.clean_text(' '.join(descriptions))

        return None

    def extract_product_brand(self, response) -> str:
        """Extract product brand - always West Elm"""
        return "West Elm"

    def extract_product_category(self, response) -> Optional[str]:
        """Extract product category from breadcrumbs or URL"""
        # Try breadcrumbs first
        breadcrumbs = response.css('.breadcrumb a::text').getall()
        if breadcrumbs and len(breadcrumbs) > 1:
            # Take the last meaningful breadcrumb (skip "Home")
            category = breadcrumbs[-1] if breadcrumbs[-1].lower() != 'home' else breadcrumbs[-2]
            return self.normalize_category(category)

        # Try extracting from URL
        url_parts = response.url.split('/')
        for part in url_parts:
            if part in ['furniture', 'lighting', 'rugs', 'bedding']:
                return self.normalize_category(part)

        return "Furniture"  # Default category

    def extract_product_id(self, response) -> Optional[str]:
        """Extract product ID"""
        # Try to find product ID in various places
        # From URL
        url_match = re.search(r'/([a-zA-Z0-9-]+)/?$', response.url)
        if url_match:
            return url_match.group(1)

        # From data attributes
        product_id = response.css('[data-product-id]::attr(data-product-id)').get()
        if product_id:
            return product_id

        # From SKU if available
        sku = response.css('[data-sku]::attr(data-sku)').get()
        if sku:
            return sku

        return None

    def extract_product_sku(self, response) -> Optional[str]:
        """Extract product SKU"""
        # Try multiple SKU selectors
        selectors = [
            '[data-sku]::attr(data-sku)',
            '.product-sku::text',
            '.sku-number::text'
        ]

        for selector in selectors:
            sku = self.extract_text(response.css(selector))
            if sku:
                return sku.replace('SKU:', '').strip()

        return None

    def extract_product_images(self, response) -> List[str]:
        """Extract product image URLs"""
        image_urls = []

        # Try multiple image selectors
        selectors = [
            '.product-images img::attr(src)',
            '.product-gallery img::attr(src)',
            '.image-gallery img::attr(src)',
            '[data-test-id="product-image"] img::attr(src)'
        ]

        for selector in selectors:
            urls = response.css(selector).getall()
            for url in urls:
                if url and url not in image_urls:
                    # Convert relative URLs to absolute
                    full_url = urljoin(response.url, url)
                    # Get high-resolution version if possible
                    full_url = self.get_high_res_image_url(full_url)
                    image_urls.append(full_url)

        # Also check for data-src (lazy loaded images)
        lazy_images = response.css('.product-images img::attr(data-src)').getall()
        for url in lazy_images:
            if url and url not in image_urls:
                full_url = urljoin(response.url, url)
                full_url = self.get_high_res_image_url(full_url)
                image_urls.append(full_url)

        return image_urls[:10]  # Limit to first 10 images

    def extract_product_attributes(self, response) -> Dict[str, str]:
        """Extract product attributes (dimensions, materials, etc.)"""
        attributes = {}

        # Extract from product details section
        detail_rows = response.css('.product-details .detail-row')
        for row in detail_rows:
            key = self.extract_text(row.css('.detail-key::text'))
            value = self.extract_text(row.css('.detail-value::text'))
            if key and value:
                attributes[key] = value

        # Extract dimensions if available
        dimensions_text = response.css('.dimensions::text').get()
        if dimensions_text:
            dimensions = self.extract_dimensions(dimensions_text)
            attributes.update(dimensions)

        # Extract materials
        materials = response.css('.materials::text').get()
        if materials:
            attributes['materials'] = self.clean_text(materials)

        # Extract care instructions
        care = response.css('.care-instructions::text').get()
        if care:
            attributes['care_instructions'] = self.clean_text(care)

        return attributes

    def extract_availability(self, response) -> bool:
        """Check if product is available"""
        # Check for out of stock indicators
        out_of_stock_indicators = [
            '.out-of-stock',
            '.unavailable',
            '[data-availability="out-of-stock"]'
        ]

        for indicator in out_of_stock_indicators:
            if response.css(indicator):
                return False

        # Check button text
        add_to_cart = response.css('.add-to-cart button::text').get()
        if add_to_cart and 'out of stock' in add_to_cart.lower():
            return False

        return True  # Default to available

    def extract_sale_status(self, response) -> bool:
        """Check if product is on sale"""
        sale_indicators = [
            '.sale-price',
            '.price-sale',
            '[data-sale="true"]',
            '.on-sale'
        ]

        for indicator in sale_indicators:
            if response.css(indicator):
                return True

        return False

    def extract_original_price(self, response) -> Optional[float]:
        """Extract original price if item is on sale"""
        if not self.extract_sale_status(response):
            return None

        selectors = [
            '.price-original .price-amount::text',
            '.price-was .price-amount::text',
            '.original-price .price-amount::text'
        ]

        for selector in selectors:
            price_text = self.extract_text(response.css(selector))
            if price_text:
                price = self.extract_price(price_text)
                if price:
                    return price

        return None

    def extract_price_from_json_ld(self, response) -> Optional[float]:
        """Extract price from JSON-LD structured data"""
        try:
            scripts = response.css('script[type="application/ld+json"]::text').getall()
            for script in scripts:
                data = json.loads(script)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = offers.get('price')
                    if price:
                        return float(price)
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        return None

    def get_high_res_image_url(self, url: str) -> str:
        """Convert image URL to high resolution version"""
        # West Elm image URL patterns - try to get larger sizes
        if 'westelm.com' in url:
            # Replace size parameters with larger ones
            url = re.sub(r'[?&]wid=\d+', '?wid=800', url)
            url = re.sub(r'[?&]hei=\d+', '&hei=800', url)

        return url