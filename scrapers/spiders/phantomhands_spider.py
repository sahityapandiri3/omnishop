"""
Phantom Hands spider for furniture and decor
"""
import scrapy
from urllib.parse import urljoin
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class PhantomHandsSpider(BaseProductSpider):
    """Spider for scraping Phantom Hands furniture"""

    name = 'phantomhands'
    allowed_domains = ['phantomhands.in', 'www.phantomhands.in']

    # Category URLs to scrape (based on user's requested categories)
    start_urls = [
        'https://phantomhands.in/products/type/chair',
        'https://phantomhands.in/products/type/tables',
        'https://phantomhands.in/products/type/lamps',
        'https://phantomhands.in/products/type/storage-and-shelves',
        'https://phantomhands.in/products/type/dividers',
        'https://phantomhands.in/products/type/benches',
        'https://phantomhands.in/products/type/stools',
        'https://phantomhands.in/products/type/sofas',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 3,
    }

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract category name from URL
        category = self.extract_category_from_url(response.url)

        # Phantom Hands uses a specific structure: div.item > a with href to products
        # The correct selector is to find all divs with class "item" and extract links within them
        product_links = response.css('div.item a::attr(href)').getall()

        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in product_links:
            if link and link not in seen:
                seen.add(link)
                unique_links.append(link)

        self.logger.info(f"Found {len(unique_links)} product links on {response.url}")

        for link in unique_links:
            # Only follow links that look like product pages
            # Product pages have pattern: /products/{product-slug} (not /products/type/ or /products/collection/)
            if '/products/' in link and '/type/' not in link and '/collection/' not in link and '/designer/' not in link:
                yield response.follow(link, callback=self.parse_product, meta={'category': category})

        # Follow pagination - check if there's a next page button
        # Note: This site appears to use dynamic loading (HTMX/Sprig), so pagination may not be present
        next_page_selectors = [
            'a.next::attr(href)',
            'a[rel="next"]::attr(href)',
            '.pagination .next a::attr(href)',
            'a.pagination-next::attr(href)',
        ]

        for selector in next_page_selectors:
            next_page = response.css(selector).get()
            if next_page:
                yield response.follow(next_page, callback=self.parse)
                break

    def parse_product(self, response):
        """Parse product pages and extract product information"""
        try:
            # Extract product title
            # Phantom Hands uses: <h1 class="mv0 f6 f5-m fw4">Product Name</h1>
            title_selectors = [
                'h1::text',
                'meta[property="og:title"]::attr(content)',
                'h1.product-title::text',
                '.product-name::text',
                '.product-title::text',
            ]
            title = self.extract_text_from_selectors(response, title_selectors)

            if not title:
                self.logger.warning(f"No title found for {response.url}")
                return

            # Extract description
            description_selectors = [
                '.product-description::text',
                '.description::text',
                'meta[property="og:description"]::attr(content)',
                '.product-details p::text',
                'meta[name="description"]::attr(content)',
            ]
            description = self.extract_text_from_selectors(response, description_selectors)

            # Extract price
            # NOTE: Phantom Hands does NOT display prices on their website
            # They use an "Enquire" button instead (mailto:info@phantomhands.in)
            # We still check for prices in case this changes, but expect None
            price_selectors = [
                '.price::text',
                '.product-price::text',
                'span[class*="price"]::text',
                '.amount::text',
                'meta[property="og:price:amount"]::attr(content)',
            ]
            price_text = self.extract_text_from_selectors(response, price_selectors)
            price = self.extract_price(price_text) if price_text else None

            if not price:
                self.logger.info(f"No price found for {title} at {response.url} (expected - site uses enquiry-based pricing)")
                # Phantom Hands uses enquiry-based pricing, so we'll set price to 0

            # Extract original price (for sale items)
            original_price_selectors = [
                '.original-price::text',
                '.regular-price::text',
                'del.price::text',
                's.price::text',
            ]
            original_price_text = self.extract_text_from_selectors(response, original_price_selectors)
            original_price = self.extract_price(original_price_text) if original_price_text else None

            # Extract images
            image_selectors = [
                '.product-image img::attr(src)',
                '.product-gallery img::attr(src)',
                'img.product-img::attr(src)',
                '.gallery-image img::attr(src)',
                'meta[property="og:image"]::attr(content)',
            ]

            image_urls = []
            for selector in image_selectors:
                imgs = response.css(selector).getall()
                image_urls.extend(imgs)

            # Clean and make URLs absolute
            image_urls = [urljoin(response.url, url) for url in image_urls if url]
            # Remove duplicates while preserving order
            image_urls = list(dict.fromkeys(image_urls))

            # Extract brand/vendor
            brand_selectors = [
                '.brand::text',
                '.vendor::text',
                'meta[property="og:brand"]::attr(content)',
            ]
            brand = self.extract_text_from_selectors(response, brand_selectors) or 'Phantom Hands'

            # Extract SKU
            sku_selectors = [
                '.sku::text',
                'meta[property="product:sku"]::attr(content)',
                '[itemprop="sku"]::text',
            ]
            sku = self.extract_text_from_selectors(response, sku_selectors) or ''

            # Get category from meta (URL-based) as fallback
            # Smart categorization is automatically applied in create_product_item()
            category = response.meta.get('category', 'Furniture')

            # Extract availability
            availability_selectors = [
                '.availability::text',
                '.stock-status::text',
                'link[itemprop="availability"]::attr(href)',
                '.in-stock::text',
            ]
            availability_text = self.extract_text_from_selectors(response, availability_selectors)
            is_available = True  # Default to available
            stock_status = 'in_stock'

            if availability_text:
                availability_lower = availability_text.lower()
                if 'out' in availability_lower or 'sold' in availability_lower:
                    is_available = False
                    stock_status = 'out_of_stock'

            # Extract attributes
            attributes = {
                'brand': brand,
            }

            # Try to extract material, dimensions, or other specs
            specs_selectors = [
                '.product-specs dt::text',
                '.specifications dt::text',
                '.details dt::text',
            ]
            spec_names = response.css(','.join(specs_selectors)).getall()

            if spec_names:
                spec_values_selectors = [
                    '.product-specs dd::text',
                    '.specifications dd::text',
                    '.details dd::text',
                ]
                spec_values = response.css(','.join(spec_values_selectors)).getall()

                for name, value in zip(spec_names, spec_values):
                    if name and value:
                        attributes[name.strip().lower()] = value.strip()

            # Determine if on sale
            is_on_sale = bool(original_price and original_price > price) if price else False

            # Create unique external ID from URL
            external_id = response.url.split('/')[-1] or str(hash(response.url))

            # Create product item
            yield self.create_product_item(
                response=response,
                name=title,
                price=price,  # None is OK for enquiry-based pricing
                external_id=external_id,
                description=description or '',
                brand=brand,
                category=self.normalize_category(category),
                image_urls=image_urls,
                attributes=attributes,
                sku=sku,
                original_price=original_price,
                is_available=is_available,
                stock_status=stock_status,
                is_on_sale=is_on_sale,
                currency='INR'
            )

        except Exception as e:
            self.logger.error(f"Error parsing product {response.url}: {e}")

    def extract_category_from_url(self, url: str) -> str:
        """Extract category name from URL"""
        if '/products/type/' in url:
            category = url.split('/products/type/')[-1].split('?')[0].split('/')[0]
            # Clean up category name
            category = category.replace('-', ' ').replace('_', ' ').title()
            return category
        return 'Furniture'

    # Note: determine_category_from_name is inherited from BaseProductSpider
    # Smart categorization is now automatically applied in create_product_item()

    def looks_like_product_url(self, url: str) -> bool:
        """Check if URL looks like a product page"""
        # Phantom Hands product URLs typically contain /products/
        if '/products/' in url:
            # Exclude category pages
            if '/type/' not in url and '/category/' not in url:
                return True
        return False
