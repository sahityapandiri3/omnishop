"""
TheHouseOfThings spider for furniture, lighting, decor, rugs, and planters
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class TheHouseOfThingsSpider(BaseProductSpider):
    """Spider for scraping The House of Things premium furniture and decor"""

    name = 'thehouseofthings'
    allowed_domains = ['thehouseofthings.com', 'www.thehouseofthings.com']

    # Main category URLs to scrape (all requested categories)
    start_urls = [
        # Furniture
        'https://thehouseofthings.com/furniture.html',
        'https://thehouseofthings.com/furniture/seating.html',
        'https://thehouseofthings.com/furniture/tables.html',
        'https://thehouseofthings.com/furniture/storage.html',
        'https://thehouseofthings.com/furniture/bedroom.html',
        'https://thehouseofthings.com/furniture/outdoor.html',

        # Lighting
        'https://thehouseofthings.com/lighting.html',
        'https://thehouseofthings.com/lighting/table-lamps.html',
        'https://thehouseofthings.com/lighting/floor-lamps.html',
        'https://thehouseofthings.com/lighting/chandeliers.html',
        'https://thehouseofthings.com/lighting/wall-lamps.html',

        # Decor
        'https://thehouseofthings.com/decor.html',
        'https://thehouseofthings.com/decor/wall-art.html',
        'https://thehouseofthings.com/decor/mirrors.html',
        'https://thehouseofthings.com/decor/sculptures.html',
        'https://thehouseofthings.com/decor/cushions.html',

        # Rugs
        'https://thehouseofthings.com/rugs.html',

        # Planters
        'https://thehouseofthings.com/planters.html',
        'https://thehouseofthings.com/vases.html',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 1.5,  # Optimized for sitemap-based scraping
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,  # Increased concurrency
        'RETRY_TIMES': 3,  # Reduced retries since we're fetching static pages
    }

    def start_requests(self):
        """Override start_requests to use sitemap-based scraping (AJAX site)"""
        # The site uses AJAX to load products, so we parse sitemaps instead
        self.logger.info("Starting sitemap-based scraping for thehouseofthings")
        yield scrapy.Request(
            url='https://thehouseofthings.com/sitemap.xml',
            callback=self.parse_sitemap_index
        )

    def parse_sitemap_index(self, response):
        """Parse sitemap index and fetch all sub-sitemaps"""
        sitemap_urls = response.xpath(
            '//ns:loc/text()',
            namespaces={'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        ).getall()

        self.logger.info(f"Found {len(sitemap_urls)} sitemaps in index")

        for sitemap_url in sitemap_urls:
            yield scrapy.Request(url=sitemap_url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        """Parse individual sitemap and extract product URLs"""
        urls = response.xpath(
            '//ns:loc/text()',
            namespaces={'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        ).getall()

        product_count = 0
        for url in urls:
            if url.endswith('.html'):
                # Check if it's a product page (root level, not a category)
                path = url.split('.com/')[-1]
                # Products are like "product-name.html", categories are like "furniture/seating.html"
                if '/' not in path.replace('.html', ''):
                    product_count += 1
                    # Determine category from keywords in URL
                    category = self.infer_category_from_url(url)
                    yield scrapy.Request(
                        url=url,
                        callback=self.parse_product,
                        meta={'category': category}
                    )

        self.logger.info(f"Found {product_count} product URLs in {response.url}")

    def infer_category_from_url(self, url: str) -> str:
        """Infer category from product URL keywords"""
        url_lower = url.lower()

        # Furniture keywords
        if any(kw in url_lower for kw in ['chair', 'sofa', 'table', 'desk', 'cabinet', 'shelf', 'bed', 'bench']):
            return 'Furniture'
        # Lighting keywords
        elif any(kw in url_lower for kw in ['lamp', 'light', 'chandelier', 'sconce', 'lantern']):
            return 'Lighting'
        # Rug keywords
        elif any(kw in url_lower for kw in ['rug', 'carpet', 'mat']):
            return 'Rugs'
        # Planter keywords
        elif any(kw in url_lower for kw in ['planter', 'pot', 'vase']):
            return 'Plants & Planters'
        # Decor keywords (default)
        else:
            return 'Decor & Accessories'

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract category name from URL or breadcrumbs
        category = self.extract_category_from_page(response)

        # Magento product link selectors
        product_selectors = [
            '.product-item-link::attr(href)',
            '.product-item-info a.product-item-photo::attr(href)',
            'a.product-item-link::attr(href)',
            '.product-item a[href*="/products/"]::attr(href)',
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Remove duplicates
        product_links = list(set(product_links))

        self.logger.info(f"Found {len(product_links)} product links on {response.url}")

        for link in product_links:
            product_url = urljoin(response.url, link)
            yield scrapy.Request(
                url=product_url,
                callback=self.parse_product,
                meta={'category': category}
            )

        # Follow pagination (Magento pagination)
        pagination_selectors = [
            '.pages a.next::attr(href)',
            'a[title="Next"]::attr(href)',
            '.pager a.next::attr(href)',
            'link[rel="next"]::attr(href)',
        ]

        for selector in pagination_selectors:
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
        """Parse product detail page"""
        try:
            self.logger.info(f"Parsing product: {response.url}")

            # Extract product name
            name_selectors = [
                'h1.page-title span::text',
                '.product-info-main h1::text',
                '.product-name::text',
                'h1::text',
            ]
            name = None
            for selector in name_selectors:
                name = self.extract_text(response.css(selector))
                if name:
                    break

            if not name:
                self.logger.warning(f"No product name found for {response.url}")
                return

            # Extract price (Magento price structure)
            price_selectors = [
                '.price-box .price::text',
                '.product-info-price .price::text',
                'span.price::text',
                '[data-price-type="finalPrice"] .price::text',
            ]
            price_text = None
            for selector in price_selectors:
                price_text = self.extract_text(response.css(selector))
                if price_text:
                    break

            price = self.extract_price(price_text) if price_text else None

            if not price:
                self.logger.warning(f"No price found for product: {name}")
                return

            # Extract original price (if on sale)
            original_price = None
            old_price_selectors = [
                '.old-price .price::text',
                '.price-box .old-price .price::text',
                '[data-price-type="oldPrice"] .price::text',
            ]
            for selector in old_price_selectors:
                old_price_text = self.extract_text(response.css(selector))
                if old_price_text:
                    original_price = self.extract_price(old_price_text)
                    break

            # Extract description
            description_selectors = [
                '.product.attribute.description .value::text',
                '.product.description .value::text',
                '[itemprop="description"]::text',
                '.product-info-main .description::text',
            ]
            description = None
            for selector in description_selectors:
                description = self.extract_text(response.css(selector))
                if description:
                    break

            # If no description found, try extracting from multiple paragraphs
            if not description:
                desc_parts = response.css('.product.attribute.description p::text').getall()
                if desc_parts:
                    description = ' '.join(part.strip() for part in desc_parts if part.strip())

            # Extract SKU
            sku_selectors = [
                '[itemprop="sku"]::text',
                '.product.attribute.sku .value::text',
                '.sku .value::text',
            ]
            external_id = None
            for selector in sku_selectors:
                external_id = self.extract_text(response.css(selector))
                if external_id:
                    break

            # Fallback: extract ID from URL
            if not external_id:
                id_match = re.search(r'/([^/]+)\.html$', response.url)
                if id_match:
                    external_id = id_match.group(1)

            # Extract category from breadcrumbs or meta
            category = response.meta.get('category', 'Home Decor')
            breadcrumbs = response.css('.breadcrumbs a span::text').getall()
            if breadcrumbs and len(breadcrumbs) > 1:
                category = breadcrumbs[-1]  # Last breadcrumb is usually the category

            # Extract images
            image_urls = []
            image_selectors = [
                '.gallery-placeholder img::attr(src)',
                '.product.media img::attr(src)',
                '[data-gallery-role="gallery-placeholder"] img::attr(src)',
                '.product-image-photo::attr(src)',
            ]
            for selector in image_selectors:
                images = response.css(selector).getall()
                image_urls.extend(images)

            # Remove duplicates and filter valid images
            image_urls = list(set([img for img in image_urls if img and 'placeholder' not in img.lower()]))[:10]

            # Extract attributes
            attributes = {}

            # Try to extract structured attributes from product details
            attribute_rows = response.css('.product.attribute')
            for row in attribute_rows:
                attr_label = self.extract_text(row.css('.label::text'))
                attr_value = self.extract_text(row.css('.value::text'))
                if attr_label and attr_value:
                    attr_key = attr_label.lower().replace(':', '').strip()
                    attributes[attr_key] = attr_value

            # Extract dimensions from description if available
            if description:
                # Common dimension patterns
                dim_patterns = [
                    r'(?:dimensions?|size):?\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|inch|")',
                    r'(?:L|length)\s*:\s*(\d+\.?\d*).*?(?:W|width)\s*:\s*(\d+\.?\d*).*?(?:H|height)\s*:\s*(\d+\.?\d*)',
                ]
                for pattern in dim_patterns:
                    dim_match = re.search(pattern, description, re.IGNORECASE)
                    if dim_match:
                        attributes['dimensions'] = f"{dim_match.group(1)} x {dim_match.group(2)} x {dim_match.group(3)}"
                        break

                # Extract materials
                material_keywords = ['wood', 'metal', 'brass', 'iron', 'steel', 'glass', 'ceramic', 'marble', 'stone', 'fabric', 'leather', 'cotton', 'linen', 'velvet']
                found_materials = [mat for mat in material_keywords if mat in description.lower()]
                if found_materials:
                    attributes['materials'] = ', '.join(set(found_materials))

            # Extract color swatches if available
            colors = response.css('.swatch-option.color::attr(option-label)').getall()
            if colors:
                attributes['colors'] = ', '.join(colors)

            # Brand (The House of Things)
            brand = 'The House of Things'

            # Check availability
            is_available = True
            stock_status = response.css('.stock.available span::text').get()
            if stock_status and 'out of stock' in stock_status.lower():
                is_available = False

            # Check if on sale
            is_on_sale = original_price and original_price > price if original_price else False

            # Create product item
            item = self.create_product_item(
                response=response,
                name=self.clean_text(name),
                price=price,
                external_id=external_id or f"thot-{hash(response.url)}",
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

            yield item

        except Exception as e:
            self.logger.error(f"Error parsing product {response.url}: {str(e)}")
            self.errors_count += 1

    def extract_category_from_page(self, response) -> str:
        """Extract category from breadcrumbs or URL"""
        try:
            # Try breadcrumbs first
            breadcrumbs = response.css('.breadcrumbs a span::text').getall()
            if breadcrumbs and len(breadcrumbs) > 1:
                category = breadcrumbs[-1].strip()
                return category

            # Fallback: extract from URL
            match = re.search(r'thehouseofthings\.com/([^/\.]+)', response.url)
            if match:
                category = match.group(1).replace('-', ' ').title()

                # Map to standard categories
                category_lower = category.lower()
                if 'furniture' in category_lower or any(keyword in category_lower for keyword in ['seating', 'table', 'storage', 'bedroom']):
                    return 'Furniture'
                elif 'light' in category_lower or any(keyword in category_lower for keyword in ['lamp', 'chandelier']):
                    return 'Lighting'
                elif 'rug' in category_lower or 'carpet' in category_lower:
                    return 'Rugs'
                elif 'planter' in category_lower or 'vase' in category_lower:
                    return 'Plants & Planters'
                elif 'decor' in category_lower or any(keyword in category_lower for keyword in ['wall art', 'mirror', 'sculpture', 'cushion']):
                    return 'Decor & Accessories'

                return category
        except Exception:
            pass

        return "Home Decor"
