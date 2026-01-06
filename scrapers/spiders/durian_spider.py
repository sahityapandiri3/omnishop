"""
Durian spider for furniture products
Website: https://www.durian.in
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class DurianSpider(BaseProductSpider):
    """Spider for scraping Durian furniture products"""

    name = 'durian'
    allowed_domains = ['durian.in', 'www.durian.in']

    # Category URLs using /buy-furniture/ pattern from sitemap
    start_urls = [
        # Sofas & Living Room
        'https://www.durian.in/buy-furniture/all-sofas',
        'https://www.durian.in/buy-furniture/sectional-sofas',
        'https://www.durian.in/buy-furniture/premium-sofas',
        'https://www.durian.in/buy-furniture/reclining-sofas',
        'https://www.durian.in/buy-furniture/all-living-chairs',
        'https://www.durian.in/buy-furniture/all-living-storage',
        'https://www.durian.in/buy-furniture/all-coffee-tables',

        # Bedroom
        'https://www.durian.in/buy-furniture/all-beds',
        'https://www.durian.in/buy-furniture/designer-beds',
        'https://www.durian.in/buy-furniture/solid-wood-beds',
        'https://www.durian.in/buy-furniture/king-size-beds',
        'https://www.durian.in/buy-furniture/queen-size-beds',
        'https://www.durian.in/buy-furniture/hydraulic-beds',
        'https://www.durian.in/buy-furniture/upholstered-beds',
        'https://www.durian.in/buy-furniture/all-wardrobes',
        'https://www.durian.in/buy-furniture/2-door-wardrobe',
        'https://www.durian.in/buy-furniture/3-door-wardrobe',
        'https://www.durian.in/buy-furniture/4-door-wardrobe',
        'https://www.durian.in/buy-furniture/all-chest-of-drawers',
        'https://www.durian.in/buy-furniture/all-bedroom-storage',
        'https://www.durian.in/buy-furniture/all-bedroom-chairs',

        # Dining
        'https://www.durian.in/buy-furniture/all-dining-sets',
        'https://www.durian.in/buy-furniture/4-seater-dining-set',
        'https://www.durian.in/buy-furniture/6-seater-dining-set',
        'https://www.durian.in/buy-furniture/8-seater-dining-set',
        'https://www.durian.in/buy-furniture/wooden-dining-set',
        'https://www.durian.in/buy-furniture/marble-dining-set',
        'https://www.durian.in/buy-furniture/glass-dining-set',
        'https://www.durian.in/buy-furniture/all-dining-seating',
        'https://www.durian.in/buy-furniture/all-dining-storage',

        # Office
        'https://www.durian.in/buy-furniture/office-chairs',
        'https://www.durian.in/buy-furniture/focus-ergonomic-chairs',
        'https://www.durian.in/buy-furniture/adapt-home-office-chairs',
        'https://www.durian.in/buy-furniture/all-office-desk',
        'https://www.durian.in/buy-furniture/conference-desks',
        'https://www.durian.in/buy-furniture/study-tables',

        # Mattresses
        'https://www.durian.in/buy-furniture/all-mattress',
        'https://www.durian.in/buy-furniture/ortho-mattress',
        'https://www.durian.in/buy-furniture/comfort-mattress',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 2.5,
        'RANDOMIZE_DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract category from URL
        category = self.extract_category_from_url(response.url)

        # Durian product link selectors
        product_selectors = [
            'a.product-item-link::attr(href)',
            '.product-card a::attr(href)',
            'a.product-link::attr(href)',
            '.product-item a::attr(href)',
            'a[href*="/product/"]::attr(href)',
            '.product-tile a::attr(href)',
            '.products-grid a.product-item-photo::attr(href)',
            '.product-image-container a::attr(href)',
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Remove duplicates and filter valid product links
        product_links = list(set([
            link for link in product_links
            if link and ('/product/' in link or '.html' in link) and 'category' not in link.lower()
        ]))

        self.logger.info(f"Found {len(product_links)} product links on {response.url}")

        for link in product_links:
            full_url = urljoin(response.url, link)
            yield scrapy.Request(
                url=full_url,
                callback=self.parse_product,
                meta={'category': category}
            )

        # Follow pagination
        next_page_selectors = [
            'a.next::attr(href)',
            'a[rel="next"]::attr(href)',
            '.pages-item-next a::attr(href)',
            'a:contains("Next")::attr(href)',
            'link[rel="next"]::attr(href)',
            '.action.next::attr(href)',
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
        """Parse individual product page"""
        try:
            self.logger.info(f"Parsing product: {response.url}")

            # Try to extract JSON-LD structured data
            json_ld = response.css('script[type="application/ld+json"]::text').getall()
            product_data = None
            for ld in json_ld:
                try:
                    data = json.loads(ld)
                    if isinstance(data, dict) and data.get('@type') == 'Product':
                        product_data = data
                        break
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Product':
                                product_data = item
                                break
                except json.JSONDecodeError:
                    continue

            # Extract name
            name = None
            if product_data:
                name = product_data.get('name')
            if not name:
                name = self.extract_text_from_selectors(response, [
                    'h1.page-title span::text',
                    'h1.product-title::text',
                    'h1::text',
                    '.product-info-main h1::text',
                    '[data-ui-id="page-title-wrapper"]::text',
                    'span[itemprop="name"]::text',
                ])

            if not name:
                self.logger.warning(f"No product name found: {response.url}")
                return

            # Extract price
            price = None
            if product_data and 'offers' in product_data:
                offers = product_data['offers']
                if isinstance(offers, dict):
                    price = self.extract_price(str(offers.get('price', '')))
                elif isinstance(offers, list) and offers:
                    price = self.extract_price(str(offers[0].get('price', '')))

            if not price:
                price_text = self.extract_text_from_selectors(response, [
                    '.price-wrapper .price::text',
                    '.product-info-price .price::text',
                    'span[data-price-type="finalPrice"]::text',
                    'span[itemprop="price"]::text',
                    '.special-price .price::text',
                    '.price-box .price::text',
                ])
                price = self.extract_price(price_text) if price_text else None

            if not price:
                self.logger.warning(f"No price found for: {name}")
                return

            # Extract original price
            original_price = None
            original_price_text = self.extract_text_from_selectors(response, [
                '.old-price .price::text',
                'span[data-price-type="oldPrice"]::text',
                '.regular-price .price::text',
            ])
            if original_price_text:
                original_price = self.extract_price(original_price_text)

            # Extract description
            description = None
            desc_selectors = [
                '.product.attribute.description .value::text',
                '.product-description::text',
                'div[itemprop="description"]::text',
                '.description .value p::text',
                '#description .value::text',
            ]
            for selector in desc_selectors:
                desc_parts = response.css(selector).getall()
                if desc_parts:
                    description = ' '.join([p.strip() for p in desc_parts if p.strip()])
                    break

            if not description:
                description = response.css('meta[name="description"]::attr(content)').get()

            # Extract external ID (SKU)
            external_id = None
            sku = self.extract_text_from_selectors(response, [
                '[itemprop="sku"]::text',
                '.product.attribute.sku .value::text',
                '.sku .value::text',
            ])
            if sku:
                external_id = sku.strip()
            else:
                # Try to get from URL
                sku_match = re.search(r'/([^/]+)\.html', response.url)
                if sku_match:
                    external_id = sku_match.group(1)
                else:
                    external_id = self._generate_external_id(response.url)

            # Brand is Durian
            brand = 'Durian'

            # Extract images
            image_urls = []
            if product_data and 'image' in product_data:
                images = product_data['image']
                if isinstance(images, str):
                    image_urls.append(images)
                elif isinstance(images, list):
                    image_urls.extend(images[:10])

            if not image_urls:
                image_selectors = [
                    '.gallery-placeholder img::attr(src)',
                    '.fotorama__stage img::attr(src)',
                    '.product.media img::attr(src)',
                    '.product-image-gallery img::attr(src)',
                    '.product-image-photo::attr(src)',
                    'img[itemprop="image"]::attr(src)',
                    '.fotorama__img::attr(src)',
                ]
                for selector in image_selectors:
                    imgs = response.css(selector).getall()
                    if imgs:
                        image_urls.extend(imgs)
                        break

                # Also try data-src for lazy loaded images
                if not image_urls:
                    lazy_imgs = response.css('.gallery-placeholder img::attr(data-src), .fotorama__img::attr(data-src)').getall()
                    image_urls.extend(lazy_imgs)

            # Clean image URLs
            image_urls = list(set([
                img for img in image_urls
                if img and not img.endswith('.svg') and 'placeholder' not in img.lower()
            ]))[:10]

            # Extract category
            category = response.meta.get('category', 'Furniture')

            # Extract product attributes
            attributes = self._extract_attributes(response, description)

            # Check availability
            is_available = True
            if product_data and 'offers' in product_data:
                offers = product_data['offers']
                if isinstance(offers, dict):
                    availability = offers.get('availability', '')
                    is_available = 'InStock' in availability
                elif isinstance(offers, list) and offers:
                    availability = offers[0].get('availability', '')
                    is_available = 'InStock' in availability

            # Also check for out of stock indicator
            out_of_stock = response.css('.stock.unavailable, .out-of-stock').get()
            if out_of_stock:
                is_available = False

            # Check if on sale
            is_on_sale = original_price and original_price > price if original_price else False

            # Create product item
            item = self.create_product_item(
                response=response,
                name=self.clean_text(name),
                price=price,
                external_id=external_id,
                description=self.clean_text(description) if description else None,
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

    def _extract_attributes(self, response, description: str) -> Dict[str, str]:
        """Extract product attributes from the page"""
        attributes = {}

        # Durian uses Magento-style additional information tables
        spec_rows = response.css('.additional-attributes tr, .product-attributes tr, #product-attribute-specs-table tr')
        for row in spec_rows:
            key = row.css('th::text, td:first-child::text').get()
            value = row.css('td:last-child::text, td:nth-child(2)::text').get()
            if key and value:
                key = key.strip().lower().replace(' ', '_').replace(':', '')
                value = value.strip()
                if key and value and len(value) < 200:
                    attributes[key] = value

        # Extract from data attributes
        data_attrs = response.css('.product.attribute')
        for attr in data_attrs:
            label = attr.css('.type::text').get()
            value = attr.css('.value::text').get()
            if label and value:
                key = label.strip().lower().replace(' ', '_').replace(':', '')
                value = value.strip()
                if key and value and len(value) < 200:
                    attributes[key] = value

        # Extract dimensions
        if 'dimensions' not in attributes and description:
            dim_patterns = [
                r'(?:dimensions?|size):?\s*(?:L\s*x\s*W\s*x\s*H\s*:?\s*)?(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|mm|inches?|in|")',
                r'(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|mm|inches?|in|")',
            ]
            for pattern in dim_patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    attributes['dimensions'] = f"{match.group(1)} x {match.group(2)} x {match.group(3)}"
                    break

        # Extract material
        if 'material' not in attributes and description:
            material_match = re.search(r'(?:material|made\s+(?:of|from)):?\s*([A-Za-z\s,&]+?)(?:\.|,|\n|$)', description, re.IGNORECASE)
            if material_match:
                mat = material_match.group(1).strip()
                if mat and len(mat) < 100:
                    attributes['material'] = mat

        # Extract color/finish
        if 'color' not in attributes and 'finish' not in attributes:
            color = self.extract_text_from_selectors(response, [
                '.swatch-option.selected::attr(aria-label)',
                '.color-name::text',
            ])
            if color:
                attributes['color'] = color.strip()
            elif description:
                color_match = re.search(r'(?:colou?r|finish):?\s*([A-Za-z\s]+?)(?:\.|,|\n|$)', description, re.IGNORECASE)
                if color_match:
                    col = color_match.group(1).strip()
                    if col and len(col) < 50:
                        attributes['color'] = col

        # Extract weight
        if 'weight' not in attributes and description:
            weight_match = re.search(r'(?:weight):?\s*(\d+\.?\d*)\s*(?:kg|kgs?)', description, re.IGNORECASE)
            if weight_match:
                attributes['weight'] = weight_match.group(0)

        # Extract seating capacity
        if description:
            seating_match = re.search(r'(\d+)\s*(?:seater|seating)', description, re.IGNORECASE)
            if seating_match:
                attributes['seating_capacity'] = seating_match.group(1)

        # Extract warranty from Durian (they often mention it)
        warranty = self.extract_text_from_selectors(response, [
            '.warranty-info::text',
            '[data-attr="warranty"]::text',
        ])
        if warranty:
            attributes['warranty'] = warranty
        elif description:
            warranty_match = re.search(r'(\d+)\s*(?:year|yr)s?\s*warranty', description, re.IGNORECASE)
            if warranty_match:
                attributes['warranty'] = warranty_match.group(0)

        return attributes

    def extract_category_from_url(self, url: str) -> str:
        """Extract category name from URL"""
        try:
            category_map = {
                'sofas': 'Sofa',
                'recliners': 'Recliner',
                'coffee-tables': 'Coffee Table',
                'tv-units': 'TV Unit',
                'console-tables': 'Console Table',
                'shoe-racks': 'Storage',
                'wall-units': 'Shelves',
                'beds': 'Bed',
                'bedside-tables': 'Nightstand',
                'wardrobes': 'Wardrobe',
                'chest-of-drawers': 'Chest of Drawers',
                'dressing-tables': 'Dresser',
                'dining-tables': 'Dining Table',
                'dining-chairs': 'Dining Chair',
                'dining-sets': 'Dining Table',
                'bar-units': 'Cabinet',
                'crockery-units': 'Cabinet',
                'study-tables': 'Study Table',
                'office-chairs': 'Office Chair',
                'book-shelves': 'Bookshelf',
                'office-furniture': 'Desk',
                'accent-chairs': 'Accent Chair',
                'ottomans': 'Ottoman',
                'benches': 'Bench',
                'kids-beds': 'Bed',
                'kids-wardrobes': 'Wardrobe',
                'kids-study-tables': 'Study Table',
                'display-units': 'Shelves',
                'wall-shelves': 'Shelves',
                'cabinets': 'Cabinet',
                # Lighting
                'floor-lamps': 'Floor Lamp',
                'table-lamps': 'Table Lamp',
                'ceiling-lights': 'Ceiling Light',
                'wall-lights': 'Wall Lamp',
                # Decor
                'mirrors': 'Mirror',
                'vases': 'Vase',
                'clocks': 'Clock',
                'planters': 'Planter',
                'showpieces': 'Sculpture',
                'photo-frames': 'Photo Frame',
                'wall-art': 'Wall Art',
                'wall-decor': 'Decor & Accessories',
                # Furnishings
                'rugs': 'Rugs',
                'carpets': 'Rugs',
                'curtains': 'Curtain',
                'cushion-covers': 'Cushion',
                # Outdoor
                'outdoor-furniture': 'Outdoor',
            }

            url_lower = url.lower()
            for key, value in category_map.items():
                if key in url_lower:
                    return value

        except Exception:
            pass

        return 'Furniture'
