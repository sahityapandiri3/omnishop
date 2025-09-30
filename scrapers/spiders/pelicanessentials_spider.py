"""
Pelican Essentials spider for luxury decor and furniture
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class PelicanEssentialsSpider(BaseProductSpider):
    """Spider for scraping Pelican Essentials luxury decor and furniture"""

    name = 'pelicanessentials'
    allowed_domains = ['pelicanessentials.com']

    # Main category URLs to scrape
    start_urls = [
        # Luxury furniture
        'https://www.pelicanessentials.com/furniture/',
        'https://www.pelicanessentials.com/seating/',
        'https://www.pelicanessentials.com/tables/',
        'https://www.pelicanessentials.com/storage-furniture/',
        'https://www.pelicanessentials.com/bedroom-furniture/',

        # Luxury decor
        'https://www.pelicanessentials.com/decor/',
        'https://www.pelicanessentials.com/wall-art/',
        'https://www.pelicanessentials.com/sculptures/',
        'https://www.pelicanessentials.com/vases-vessels/',
        'https://www.pelicanessentials.com/decorative-objects/',

        # Lighting
        'https://www.pelicanessentials.com/lighting/',
        'https://www.pelicanessentials.com/table-lamps/',
        'https://www.pelicanessentials.com/floor-lamps/',
        'https://www.pelicanessentials.com/chandeliers/',

        # Textiles and rugs
        'https://www.pelicanessentials.com/textiles/',
        'https://www.pelicanessentials.com/rugs/',
        'https://www.pelicanessentials.com/pillows/',
        'https://www.pelicanessentials.com/throws/',

        # Collections and designer pieces
        'https://www.pelicanessentials.com/collections/',
        'https://www.pelicanessentials.com/designer-pieces/',
        'https://www.pelicanessentials.com/limited-edition/',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 2,  # Be more respectful for luxury site
        'RANDOMIZE_DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,  # Lower concurrency
    }

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Multiple selectors for product links
        product_selectors = [
            'a.product-item-link::attr(href)',
            'a.product-link::attr(href)',
            '.product-grid a::attr(href)',
            '.product-card a::attr(href)',
            'a[href*="/products/"]::attr(href)',
            '.collection-item a::attr(href)'
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Remove duplicates and filter valid links
        product_links = list(set([link for link in product_links if link and '/products/' in link]))

        for link in product_links:
            product_url = urljoin(response.url, link)
            yield scrapy.Request(
                url=product_url,
                callback=self.parse_product,
                meta={'category_url': response.url}
            )

        # Follow pagination with multiple selectors
        pagination_selectors = [
            'a.next::attr(href)',
            'a[rel="next"]::attr(href)',
            '.pagination-next a::attr(href)',
            '.load-more::attr(href)',
            'a.page-next::attr(href)'
        ]

        for selector in pagination_selectors:
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
            'h1[data-product-title]::text',
            '.product-details h1::text'
        ]

        for selector in selectors:
            name = self.extract_text(response.css(selector))
            if name:
                return self.clean_text(name)

        return None

    def extract_product_price(self, response) -> Optional[float]:
        """Extract product price"""
        selectors = [
            '.price-current .amount::text',
            '.product-price .price::text',
            '.price-display .price-amount::text',
            '.current-price::text',
            '[data-price]::attr(data-price)',
            '.money::text'
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

        # Try extracting from script tags (Shopify pattern)
        price = self.extract_price_from_script(response)
        if price:
            return price

        return None

    def extract_product_description(self, response) -> Optional[str]:
        """Extract product description"""
        selectors = [
            '.product-description p::text',
            '.product-details .description::text',
            '.product-content .description::text',
            '.product-summary::text',
            '.rte p::text',
            '.product-description div::text'
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
        # Check for explicit brand/designer mention
        brand_selectors = [
            '.product-brand::text',
            '.brand-name::text',
            '.designer-name::text',
            '[data-brand]::attr(data-brand)',
            '.product-vendor::text'
        ]

        for selector in brand_selectors:
            brand = self.extract_text(response.css(selector))
            if brand:
                return self.clean_text(brand)

        # Check in product description for designer names
        description = self.extract_product_description(response)
        if description:
            # Look for common designer name patterns
            designer_patterns = [
                r'by ([A-Z][a-z]+ [A-Z][a-z]+)',
                r'designed by ([A-Z][a-z]+ [A-Z][a-z]+)',
                r'([A-Z][a-z]+ [A-Z][a-z]+) design'
            ]
            for pattern in designer_patterns:
                match = re.search(pattern, description)
                if match:
                    return match.group(1)

        # Default to Pelican Essentials
        return "Pelican Essentials"

    def extract_product_category(self, response) -> Optional[str]:
        """Extract product category"""
        # Try breadcrumbs first
        breadcrumbs = response.css('.breadcrumb a::text, .breadcrumbs a::text').getall()
        if breadcrumbs and len(breadcrumbs) > 1:
            # Filter out "Home" and get specific category
            meaningful_crumbs = [crumb.strip() for crumb in breadcrumbs if crumb.strip().lower() not in ['home', 'products', 'all']]
            if meaningful_crumbs:
                category = meaningful_crumbs[-1]
                return self.normalize_luxury_category(category)

        # Try category from URL
        url_parts = response.url.split('/')
        for part in url_parts:
            if part in ['furniture', 'decor', 'lighting', 'textiles', 'collections']:
                return self.normalize_luxury_category(part)

        # Try product type from meta or data attributes
        product_type = response.css('[data-product-type]::attr(data-product-type)').get()
        if product_type:
            return self.normalize_luxury_category(product_type)

        return "Luxury Decor"

    def normalize_luxury_category(self, category: str) -> str:
        """Normalize category names for luxury items"""
        if not category:
            return "Luxury Decor"

        category = self.clean_text(category).title()

        # Luxury-specific category mapping
        luxury_mapping = {
            'Seating': 'Luxury Seating',
            'Tables': 'Luxury Tables',
            'Storage Furniture': 'Luxury Storage',
            'Bedroom Furniture': 'Luxury Bedroom',
            'Wall Art': 'Art & Wall Decor',
            'Sculptures': 'Sculptures & Art Objects',
            'Vases Vessels': 'Vases & Vessels',
            'Decorative Objects': 'Luxury Accessories',
            'Table Lamps': 'Designer Lighting',
            'Floor Lamps': 'Designer Lighting',
            'Chandeliers': 'Designer Lighting',
            'Rugs': 'Luxury Rugs',
            'Pillows': 'Luxury Textiles',
            'Throws': 'Luxury Textiles',
            'Collections': 'Designer Collections',
            'Designer Pieces': 'Designer Collections',
            'Limited Edition': 'Limited Edition'
        }

        return luxury_mapping.get(category, category)

    def extract_product_id(self, response) -> Optional[str]:
        """Extract product ID"""
        # Try data attributes
        selectors = [
            '[data-product-id]::attr(data-product-id)',
            '[data-variant-id]::attr(data-variant-id)',
            '[data-product-handle]::attr(data-product-handle)'
        ]

        for selector in selectors:
            product_id = response.css(selector).get()
            if product_id:
                return product_id

        # From URL (Shopify pattern)
        url_match = re.search(r'/products/([^/?]+)', response.url)
        if url_match:
            return url_match.group(1)

        return None

    def extract_product_sku(self, response) -> Optional[str]:
        """Extract product SKU"""
        selectors = [
            '.product-sku::text',
            '.sku-number::text',
            '[data-sku]::attr(data-sku)',
            '.variant-sku::text'
        ]

        for selector in selectors:
            sku = self.extract_text(response.css(selector))
            if sku:
                return sku.replace('SKU:', '').replace('Item #:', '').strip()

        return None

    def extract_product_images(self, response) -> List[str]:
        """Extract product image URLs"""
        image_urls = []

        # Try multiple image selectors
        selectors = [
            '.product-images img::attr(src)',
            '.product-gallery img::attr(src)',
            '.product-photos img::attr(src)',
            '.image-gallery img::attr(src)',
            '.product-media img::attr(src)'
        ]

        for selector in selectors:
            urls = response.css(selector).getall()
            for url in urls:
                if url and self.is_valid_image_url(url) and url not in image_urls:
                    full_url = urljoin(response.url, url)
                    # Get high-resolution version
                    full_url = self.get_high_res_image_url(full_url)
                    image_urls.append(full_url)

        # Check for lazy loaded images
        lazy_selectors = [
            '.product-images img::attr(data-src)',
            '.product-gallery img::attr(data-original)',
            '.product-photos img::attr(data-lazy)',
            '.product-media img::attr(data-zoom)'
        ]

        for selector in lazy_selectors:
            urls = response.css(selector).getall()
            for url in urls:
                if url and self.is_valid_image_url(url) and url not in image_urls:
                    full_url = urljoin(response.url, url)
                    full_url = self.get_high_res_image_url(full_url)
                    image_urls.append(full_url)

        return image_urls[:12]  # Allow more images for luxury items

    def is_valid_image_url(self, url: str) -> bool:
        """Check if URL is a valid product image"""
        if not url:
            return False

        # Filter out placeholder and icon images
        invalid_patterns = [
            'placeholder',
            'loading',
            'icon',
            'logo',
            'badge',
            'no-image'
        ]

        url_lower = url.lower()
        return not any(pattern in url_lower for pattern in invalid_patterns)

    def extract_product_attributes(self, response) -> Dict[str, str]:
        """Extract product attributes for luxury items"""
        attributes = {}

        # Extract from specification/details table
        spec_rows = response.css('.product-specs tr, .specifications tr, .product-details-table tr')
        for row in spec_rows:
            key = self.extract_text(row.css('td:first-child::text, th::text'))
            value = self.extract_text(row.css('td:last-child::text'))
            if key and value:
                attributes[self.clean_text(key)] = self.clean_text(value)

        # Extract from product details list
        detail_items = response.css('.product-details li, .product-info li')
        for item in detail_items:
            text = self.extract_text(item.css('::text'))
            if text and ':' in text:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    key, value = parts
                    attributes[self.clean_text(key)] = self.clean_text(value)

        # Extract dimensions
        dimensions_text = ' '.join(response.css('.dimensions::text, .size-info::text, .measurements::text').getall())
        if dimensions_text:
            dimensions = self.extract_dimensions(dimensions_text)
            attributes.update(dimensions)

        # Extract materials (important for luxury items)
        materials = response.css('.materials::text, .material-info::text, .composition::text').get()
        if materials:
            attributes['materials'] = self.clean_text(materials)

        # Extract finish/color
        finish = response.css('.finish::text, .color::text, .finish-info::text').get()
        if finish:
            attributes['finish'] = self.clean_text(finish)

        # Extract designer/collection
        designer = response.css('.designer::text, .collection::text').get()
        if designer:
            attributes['designer'] = self.clean_text(designer)

        # Extract care instructions (important for luxury textiles)
        care = response.css('.care-instructions::text, .care-info::text').get()
        if care:
            attributes['care_instructions'] = self.clean_text(care)

        return attributes

    def extract_availability(self, response) -> bool:
        """Check product availability"""
        # Check for out of stock indicators
        out_of_stock_selectors = [
            '.out-of-stock',
            '.sold-out',
            '.unavailable',
            '.backorder',
            '[data-available="false"]'
        ]

        for selector in out_of_stock_selectors:
            if response.css(selector):
                return False

        # Check inventory status
        inventory_text = response.css('.inventory-status::text, .stock-status::text').get()
        if inventory_text and any(phrase in inventory_text.lower() for phrase in ['out of stock', 'sold out', 'unavailable']):
            return False

        # Check add to cart button
        add_to_cart_text = response.css('.add-to-cart::text, .btn-add-cart::text').get()
        if add_to_cart_text and any(phrase in add_to_cart_text.lower() for phrase in ['out of stock', 'sold out', 'contact us']):
            return False

        return True

    def extract_sale_status(self, response) -> bool:
        """Check if product is on sale"""
        sale_indicators = [
            '.sale-badge',
            '.on-sale',
            '.price-sale',
            '.discount-badge',
            '[data-sale="true"]'
        ]

        for indicator in sale_indicators:
            if response.css(indicator):
                return True

        # Check for compare at price
        compare_price = response.css('.compare-at-price::text, .was-price::text').get()
        if compare_price:
            return True

        return False

    def extract_original_price(self, response) -> Optional[float]:
        """Extract original price if on sale"""
        if not self.extract_sale_status(response):
            return None

        selectors = [
            '.compare-at-price .money::text',
            '.was-price .money::text',
            '.price-original::text',
            '.original-price::text'
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

    def extract_price_from_script(self, response) -> Optional[float]:
        """Extract price from JavaScript variables (Shopify pattern)"""
        try:
            scripts = response.css('script:not([src])::text').getall()
            for script in scripts:
                # Look for product price in various JS patterns
                price_patterns = [
                    r'"price":\s*(\d+)',
                    r'price:\s*(\d+)',
                    r'"compare_at_price":\s*(\d+)',
                ]

                for pattern in price_patterns:
                    match = re.search(pattern, script)
                    if match:
                        # Shopify prices are usually in cents
                        price_cents = int(match.group(1))
                        return price_cents / 100

        except (ValueError, AttributeError):
            pass

        return None

    def get_high_res_image_url(self, url: str) -> str:
        """Convert to high resolution image URL"""
        # Pelican Essentials / Shopify specific image optimization
        if 'cdn.shopify.com' in url or 'shopifycdn.com' in url:
            # Replace size parameters with larger ones
            url = re.sub(r'_\d+x\d+\.(jpg|jpeg|png|webp)', r'_1200x1200.\1', url)
            url = re.sub(r'\?.*', '', url)  # Remove query parameters

        return url