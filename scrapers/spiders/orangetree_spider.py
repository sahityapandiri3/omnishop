"""
Orange Tree spider for contemporary furniture
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class OrangeTreeSpider(BaseProductSpider):
    """Spider for scraping Orange Tree contemporary furniture"""

    name = 'orangetree'
    allowed_domains = ['orangetree.com']

    # Main category URLs to scrape
    start_urls = [
        # Living room furniture
        'https://www.orangetree.com/living-room/',
        'https://www.orangetree.com/sofas/',
        'https://www.orangetree.com/chairs/',
        'https://www.orangetree.com/coffee-tables/',
        'https://www.orangetree.com/side-tables/',

        # Dining room furniture
        'https://www.orangetree.com/dining/',
        'https://www.orangetree.com/dining-tables/',
        'https://www.orangetree.com/dining-chairs/',
        'https://www.orangetree.com/bar-stools/',

        # Bedroom furniture
        'https://www.orangetree.com/bedroom/',
        'https://www.orangetree.com/beds/',
        'https://www.orangetree.com/dressers/',
        'https://www.orangetree.com/nightstands/',

        # Office furniture
        'https://www.orangetree.com/office/',
        'https://www.orangetree.com/desks/',
        'https://www.orangetree.com/office-chairs/',
        'https://www.orangetree.com/bookcases/',

        # Storage
        'https://www.orangetree.com/storage/',
        'https://www.orangetree.com/cabinets/',
        'https://www.orangetree.com/shelving/',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 1.5,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
    }

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract product links - try multiple selectors
        product_selectors = [
            'a.product-link::attr(href)',
            'a.product-item-link::attr(href)',
            '.product-grid a::attr(href)',
            '.product-tile a::attr(href)',
            'a[href*="/products/"]::attr(href)'
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Remove duplicates
        product_links = list(set(product_links))

        for link in product_links:
            if link:
                product_url = urljoin(response.url, link)
                yield scrapy.Request(
                    url=product_url,
                    callback=self.parse_product,
                    meta={'category_url': response.url}
                )

        # Follow pagination
        next_selectors = [
            'a.next-page::attr(href)',
            'a[rel="next"]::attr(href)',
            '.pagination-next a::attr(href)',
            '.page-next::attr(href)'
        ]

        for selector in next_selectors:
            next_page = response.css(selector).get()
            if next_page:
                next_url = urljoin(response.url, next_page)
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse,
                    meta={'category_url': response.meta.get('category_url', response.url)}
                )
                break

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

            # Check availability and pricing
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
        selectors = [
            'h1.product-title::text',
            'h1.product-name::text',
            '.product-header h1::text',
            '.product-info h1::text',
            'h1[data-product-title]::text'
        ]

        for selector in selectors:
            name = self.extract_text(response.css(selector))
            if name:
                return self.clean_text(name)

        return None

    def extract_product_price(self, response) -> Optional[float]:
        """Extract product price"""
        selectors = [
            '.price-current::text',
            '.product-price .price::text',
            '.price-display .amount::text',
            '.price-value::text',
            '[data-price]::attr(data-price)'
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
        selectors = [
            '.product-description p::text',
            '.product-details .description::text',
            '.product-content .description::text',
            '.product-summary::text'
        ]

        descriptions = []
        for selector in selectors:
            desc_parts = self.extract_text_list(response.css(selector))
            descriptions.extend(desc_parts)

        if descriptions:
            return self.clean_text(' '.join(descriptions))

        return None

    def extract_product_brand(self, response) -> str:
        """Extract product brand"""
        # Check for explicit brand mention
        brand_selectors = [
            '.product-brand::text',
            '.brand-name::text',
            '[data-brand]::attr(data-brand)'
        ]

        for selector in brand_selectors:
            brand = self.extract_text(response.css(selector))
            if brand:
                return self.clean_text(brand)

        # Default to Orange Tree
        return "Orange Tree"

    def extract_product_category(self, response) -> Optional[str]:
        """Extract product category"""
        # Try breadcrumbs first
        breadcrumbs = response.css('.breadcrumb a span::text, .breadcrumb a::text').getall()
        if breadcrumbs and len(breadcrumbs) > 1:
            # Filter out "Home" and get the most specific category
            meaningful_crumbs = [crumb for crumb in breadcrumbs if crumb.lower() not in ['home', 'products']]
            if meaningful_crumbs:
                category = meaningful_crumbs[-1]
                return self.normalize_category(category)

        # Try category from URL
        url_parts = response.url.split('/')
        for part in url_parts:
            if part in ['living-room', 'dining', 'bedroom', 'office', 'storage']:
                return self.normalize_category(part.replace('-', ' '))

        return "Furniture"

    def extract_product_id(self, response) -> Optional[str]:
        """Extract product ID"""
        # Try data attributes
        product_id = response.css('[data-product-id]::attr(data-product-id)').get()
        if product_id:
            return product_id

        # From URL pattern
        url_match = re.search(r'/products/([^/?]+)', response.url)
        if url_match:
            return url_match.group(1)

        # From handle or slug
        handle_match = re.search(r'/([a-zA-Z0-9-]+)/?$', response.url)
        if handle_match:
            return handle_match.group(1)

        return None

    def extract_product_sku(self, response) -> Optional[str]:
        """Extract product SKU"""
        selectors = [
            '.product-sku::text',
            '.sku-number::text',
            '[data-sku]::attr(data-sku)'
        ]

        for selector in selectors:
            sku = self.extract_text(response.css(selector))
            if sku:
                return sku.replace('SKU:', '').replace('Item:', '').strip()

        return None

    def extract_product_images(self, response) -> List[str]:
        """Extract product image URLs"""
        image_urls = []

        # Try multiple image selectors
        selectors = [
            '.product-images img::attr(src)',
            '.product-gallery img::attr(src)',
            '.product-photos img::attr(src)',
            '.image-gallery img::attr(src)'
        ]

        for selector in selectors:
            urls = response.css(selector).getall()
            for url in urls:
                if url and url not in image_urls:
                    full_url = urljoin(response.url, url)
                    # Get high-resolution version
                    full_url = self.get_high_res_image_url(full_url)
                    image_urls.append(full_url)

        # Check for lazy loaded images
        lazy_selectors = [
            '.product-images img::attr(data-src)',
            '.product-gallery img::attr(data-original)',
            '.product-photos img::attr(data-lazy)'
        ]

        for selector in lazy_selectors:
            urls = response.css(selector).getall()
            for url in urls:
                if url and url not in image_urls:
                    full_url = urljoin(response.url, url)
                    full_url = self.get_high_res_image_url(full_url)
                    image_urls.append(full_url)

        return image_urls[:8]  # Limit to first 8 images

    def extract_product_attributes(self, response) -> Dict[str, str]:
        """Extract product attributes"""
        attributes = {}

        # Extract from specification table
        spec_rows = response.css('.product-specs tr, .specifications tr')
        for row in spec_rows:
            key = self.extract_text(row.css('td:first-child::text, th::text'))
            value = self.extract_text(row.css('td:last-child::text'))
            if key and value:
                attributes[self.clean_text(key)] = self.clean_text(value)

        # Extract from product features
        features = response.css('.product-features li::text').getall()
        if features:
            attributes['features'] = '; '.join([self.clean_text(f) for f in features])

        # Extract dimensions
        dimensions_text = ' '.join(response.css('.dimensions::text, .size-info::text').getall())
        if dimensions_text:
            dimensions = self.extract_dimensions(dimensions_text)
            attributes.update(dimensions)

        # Extract materials
        materials = response.css('.materials::text, .material-info::text').get()
        if materials:
            attributes['materials'] = self.clean_text(materials)

        # Extract finish
        finish = response.css('.finish::text, .finish-info::text').get()
        if finish:
            attributes['finish'] = self.clean_text(finish)

        return attributes

    def extract_availability(self, response) -> bool:
        """Check product availability"""
        # Check for out of stock indicators
        out_of_stock_selectors = [
            '.out-of-stock',
            '.sold-out',
            '.unavailable',
            '[data-available="false"]'
        ]

        for selector in out_of_stock_selectors:
            if response.css(selector):
                return False

        # Check add to cart button
        add_to_cart_text = response.css('.add-to-cart::text, .btn-add-cart::text').get()
        if add_to_cart_text and any(phrase in add_to_cart_text.lower() for phrase in ['out of stock', 'sold out', 'unavailable']):
            return False

        return True

    def extract_sale_status(self, response) -> bool:
        """Check if product is on sale"""
        sale_indicators = [
            '.sale-badge',
            '.on-sale',
            '.price-sale',
            '[data-sale="true"]'
        ]

        for indicator in sale_indicators:
            if response.css(indicator):
                return True

        # Check for multiple prices (original and sale)
        prices = response.css('.price::text, .price-amount::text').getall()
        if len(prices) >= 2:
            return True

        return False

    def extract_original_price(self, response) -> Optional[float]:
        """Extract original price if on sale"""
        if not self.extract_sale_status(response):
            return None

        selectors = [
            '.price-original::text',
            '.price-was::text',
            '.original-price::text',
            '.price-compare::text'
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
        """Convert to high resolution image URL"""
        # Orange Tree specific image optimization
        if 'orangetree.com' in url:
            # Try to get larger image sizes
            url = re.sub(r'_\d+x\d+\.(jpg|jpeg|png)', r'_800x800.\1', url)
            url = re.sub(r'\?.*', '', url)  # Remove query parameters

        return url