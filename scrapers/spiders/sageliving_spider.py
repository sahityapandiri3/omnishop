"""
Sage Living spider for contemporary Indian furniture and home decor
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class SageLivingSpider(BaseProductSpider):
    """Spider for scraping Sage Living contemporary furniture"""

    name = 'sageliving'
    allowed_domains = ['sageliving.in']

    # Limit products per category
    PRODUCTS_PER_CATEGORY = 100

    # Main category URLs to scrape (WooCommerce)
    start_urls = [
        # Main shop page
        'https://www.sageliving.in/shop/',

        # Furniture categories
        'https://www.sageliving.in/product-category/sofas/',
        'https://www.sageliving.in/product-category/coffee-tables/',
        'https://www.sageliving.in/product-category/side-tables/',
        'https://www.sageliving.in/product-category/consoles/',
        'https://www.sageliving.in/product-category/beds/',
        'https://www.sageliving.in/product-category/dining-tables/',
        'https://www.sageliving.in/product-category/mirrors/',
        'https://www.sageliving.in/product-category/accent-chairs/',
        'https://www.sageliving.in/product-category/shelves/',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 1.5,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 6,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_product_count = {}

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Get the category URL from meta or use current URL
        category_url = response.meta.get('category_url', response.url)

        # Initialize category counter if not exists
        if category_url not in self.category_product_count:
            self.category_product_count[category_url] = 0

        # Check if we've reached the limit for this category
        if self.category_product_count[category_url] >= self.PRODUCTS_PER_CATEGORY:
            self.logger.info(f"Reached limit of {self.PRODUCTS_PER_CATEGORY} products for category: {category_url}")
            return

        # WooCommerce product link selectors
        product_selectors = [
            'a.woocommerce-LoopProduct-link::attr(href)',
            'a.woocommerce-loop-product__link::attr(href)',
            '.products a[href*="/product/"]::attr(href)',
            'a[href*="/product/"]::attr(href)',
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Remove duplicates and filter valid product links (not category links)
        product_links = list(set([link for link in product_links if link and '/product/' in link and '/product-category/' not in link]))

        for link in product_links:
            # Check if we've reached the limit
            if self.category_product_count[category_url] >= self.PRODUCTS_PER_CATEGORY:
                break

            product_url = urljoin(response.url, link)
            self.category_product_count[category_url] += 1
            yield scrapy.Request(
                url=product_url,
                callback=self.parse_product,
                meta={'category_url': category_url}
            )

        # Follow pagination only if we haven't reached the limit
        if self.category_product_count[category_url] < self.PRODUCTS_PER_CATEGORY:
            pagination_selectors = [
                'a.next::attr(href)',
                'a[rel="next"]::attr(href)',
                '.woocommerce-pagination a.next::attr(href)',
                '.nav-links a.next::attr(href)',
                'a.page-numbers.next::attr(href)'
            ]

            for selector in pagination_selectors:
                next_page = response.css(selector).get()
                if next_page:
                    next_url = urljoin(response.url, next_page)
                    yield scrapy.Request(
                        url=next_url,
                        callback=self.parse,
                        meta={'category_url': category_url}
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
        """Extract product name (WooCommerce format)"""
        selectors = [
            'h1.product_title::text',
            'h1.product-title::text',
            '.product_title::text',
            'h1[itemprop="name"]::text',
            '.summary h1::text'
        ]

        for selector in selectors:
            name = self.extract_text(response.css(selector))
            if name:
                return self.clean_text(name)

        return None

    def extract_product_price(self, response) -> Optional[float]:
        """Extract product price (INR - WooCommerce)"""
        selectors = [
            '.woocommerce-Price-amount bdi::text',
            'p.price .woocommerce-Price-amount::text',
            'span.woocommerce-Price-amount::text',
            '.price bdi::text',
            'span[itemprop="price"]::attr(content)',
            '.summary .price::text'
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
        """Extract product description (WooCommerce)"""
        selectors = [
            '.woocommerce-product-details__short-description p::text',
            '#tab-description p::text',
            '.woocommerce-Tabs-panel--description p::text',
            '[itemprop="description"] p::text',
            '.product-description p::text'
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
            '[itemprop="brand"]::text',
            '.product-brand::text',
            '.vendor::text'
        ]

        for selector in brand_selectors:
            brand = self.extract_text(response.css(selector))
            if brand:
                return self.clean_text(brand)

        # Default to Sage Living
        return "Sage Living"

    def extract_product_category(self, response) -> Optional[str]:
        """Extract product category (WooCommerce)"""
        # Try breadcrumbs first
        breadcrumbs = response.css('.woocommerce-breadcrumb a::text').getall()
        if breadcrumbs and len(breadcrumbs) > 1:
            # Filter out "Home" and get the most specific category
            meaningful_crumbs = [crumb for crumb in breadcrumbs if crumb.strip().lower() not in ['home', '', 'shop']]
            if meaningful_crumbs:
                category = meaningful_crumbs[-1]
                return self.normalize_category(category)

        # Try from posted_in links
        category_links = response.css('.posted_in a::text').getall()
        if category_links:
            return self.normalize_category(category_links[0])

        # Try category from referrer URL
        if 'category_url' in response.meta:
            url_match = re.search(r'/product-category/([^/?]+)', response.meta['category_url'])
            if url_match:
                category_slug = url_match.group(1)
                return self.normalize_category(category_slug.replace('-', ' '))

        return "Furniture"

    def extract_product_id(self, response) -> Optional[str]:
        """Extract product ID (WooCommerce)"""
        # Try data attributes
        product_id = response.css('[data-product_id]::attr(data-product_id)').get()
        if product_id:
            return product_id

        # From URL pattern
        url_match = re.search(r'/product/([^/?]+)', response.url)
        if url_match:
            return url_match.group(1)

        return None

    def extract_product_sku(self, response) -> Optional[str]:
        """Extract product SKU"""
        selectors = [
            '[itemprop="sku"]::text',
            '.product-sku::text',
            '.variant-sku::text',
            '[data-sku]::attr(data-sku)'
        ]

        for selector in selectors:
            sku = self.extract_text(response.css(selector))
            if sku:
                return sku.replace('SKU:', '').strip()

        return None

    def extract_product_images(self, response) -> List[str]:
        """Extract product image URLs (WooCommerce)"""
        image_urls = []

        # Try multiple image selectors
        selectors = [
            '.woocommerce-product-gallery img::attr(src)',
            '.woocommerce-product-gallery__image img::attr(src)',
            '.product-images img::attr(src)',
            '.images img::attr(src)',
            '[data-large_image]::attr(data-large_image)'
        ]

        for selector in selectors:
            urls = response.css(selector).getall()
            for url in urls:
                if url and url not in image_urls:
                    # Clean Shopify image URL (remove size parameters for high-res)
                    full_url = urljoin(response.url, url)
                    full_url = self.get_high_res_image_url(full_url)
                    image_urls.append(full_url)

        # Check for lazy loaded images and large versions
        lazy_selectors = [
            '.woocommerce-product-gallery img::attr(data-src)',
            '.woocommerce-product-gallery img::attr(data-large_image)',
            'img::attr(data-zoom-image)'
        ]

        for selector in lazy_selectors:
            urls = response.css(selector).getall()
            for url in urls:
                if url and url not in image_urls:
                    full_url = urljoin(response.url, url)
                    full_url = self.get_high_res_image_url(full_url)
                    image_urls.append(full_url)

        return image_urls[:10]  # Limit to first 10 images

    def extract_product_attributes(self, response) -> Dict[str, str]:
        """Extract product attributes"""
        attributes = {}

        # Extract from product meta/details
        detail_items = response.css('.product-meta__item, .product-details li')
        for item in detail_items:
            text = self.extract_text(item.css('::text'))
            if text and ':' in text:
                key, value = text.split(':', 1)
                attributes[self.clean_text(key)] = self.clean_text(value)

        # Extract dimensions
        dimensions_text = ' '.join(response.css('.product-dimensions::text, [data-dimensions]::text').getall())
        if dimensions_text:
            dimensions = self.extract_dimensions(dimensions_text)
            attributes.update(dimensions)

        # Extract materials
        materials = response.css('.product-materials::text, [data-material]::text').get()
        if materials:
            attributes['materials'] = self.clean_text(materials)

        # Extract features from description
        features = response.css('.product-features li::text').getall()
        if features:
            attributes['features'] = '; '.join([self.clean_text(f) for f in features])

        return attributes

    def extract_availability(self, response) -> bool:
        """Check product availability (WooCommerce)"""
        # Check for out of stock indicators
        out_of_stock_selectors = [
            '.out-of-stock',
            '.stock.out-of-stock',
            'p.stock.out-of-stock'
        ]

        for selector in out_of_stock_selectors:
            if response.css(selector):
                return False

        # Check button text
        add_to_cart = response.css('.single_add_to_cart_button::text').get()
        if add_to_cart and any(phrase in add_to_cart.lower() for phrase in ['sold out', 'unavailable', 'out of stock']):
            return False

        # Check stock status
        stock_status = response.css('.stock::text').get()
        if stock_status and 'out of stock' in stock_status.lower():
            return False

        return True

    def extract_sale_status(self, response) -> bool:
        """Check if product is on sale (WooCommerce)"""
        sale_indicators = [
            '.onsale',
            'span.onsale',
            '.price del',  # Deleted/strikethrough price indicates sale
        ]

        for indicator in sale_indicators:
            if response.css(indicator):
                return True

        # Check for deleted price (original price shown as strikethrough)
        del_price = response.css('.price del').get()
        if del_price:
            return True

        return False

    def extract_original_price(self, response) -> Optional[float]:
        """Extract original price if on sale (WooCommerce)"""
        if not self.extract_sale_status(response):
            return None

        selectors = [
            '.price del bdi::text',
            '.price del .woocommerce-Price-amount::text',
            'del .woocommerce-Price-amount bdi::text',
            'del span.woocommerce-Price-amount::text'
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
        # WordPress/WooCommerce image URL pattern
        if 'sageliving.in' in url:
            # Remove size suffixes like -150x150, -300x300, etc.
            url = re.sub(r'-\d+x\d+(\.(jpg|jpeg|png|gif|webp))', r'.\1', url)
            # Remove width/height query params
            url = re.sub(r'[?&](w|h|width|height)=\d+', '', url)

        return url
