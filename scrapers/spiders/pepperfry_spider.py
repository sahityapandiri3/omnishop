"""
Pepperfry spider for furniture and home decor products
Website: https://www.pepperfry.com
"""
import scrapy
from urllib.parse import urljoin, urlencode
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class PepperfrySpider(BaseProductSpider):
    """Spider for scraping Pepperfry furniture and home decor products"""

    name = 'pepperfry'
    allowed_domains = ['pepperfry.com', 'www.pepperfry.com']

    # Category URLs using /category/ pattern that works
    start_urls = [
        # Furniture
        'https://www.pepperfry.com/category/sofas.html',
        'https://www.pepperfry.com/category/beds.html',
        'https://www.pepperfry.com/category/wardrobes.html',
        'https://www.pepperfry.com/category/dining-sets.html',
        'https://www.pepperfry.com/category/study-tables.html',
        'https://www.pepperfry.com/category/centre-tables.html',
        'https://www.pepperfry.com/category/recliners.html',
        'https://www.pepperfry.com/category/office-furniture.html',
        'https://www.pepperfry.com/category/shoe-racks.html',
        'https://www.pepperfry.com/category/tv-units.html',
        'https://www.pepperfry.com/category/cabinets.html',
        'https://www.pepperfry.com/category/coffee-tables.html',
        'https://www.pepperfry.com/category/bedside-tables.html',
        'https://www.pepperfry.com/category/dressing-tables.html',
        'https://www.pepperfry.com/category/chest-of-drawers.html',
        'https://www.pepperfry.com/category/dining-tables.html',
        'https://www.pepperfry.com/category/dining-chairs.html',
        'https://www.pepperfry.com/category/accent-chairs.html',
        'https://www.pepperfry.com/category/ottomans-poufs.html',
        'https://www.pepperfry.com/category/benches.html',
        'https://www.pepperfry.com/category/stools.html',
        'https://www.pepperfry.com/category/office-chairs.html',
        'https://www.pepperfry.com/category/bookshelves.html',
        'https://www.pepperfry.com/category/display-units.html',
        'https://www.pepperfry.com/category/wall-shelves.html',

        # Lighting
        'https://www.pepperfry.com/category/floor-lamps.html',
        'https://www.pepperfry.com/category/table-lamps.html',
        'https://www.pepperfry.com/category/ceiling-lights.html',
        'https://www.pepperfry.com/category/wall-lights.html',
        'https://www.pepperfry.com/category/chandeliers.html',
        'https://www.pepperfry.com/category/pendant-lights.html',

        # Home Decor
        'https://www.pepperfry.com/category/mirrors.html',
        'https://www.pepperfry.com/category/vases.html',
        'https://www.pepperfry.com/category/wall-decor.html',
        'https://www.pepperfry.com/category/clocks.html',
        'https://www.pepperfry.com/category/photo-frames.html',
        'https://www.pepperfry.com/category/planters.html',
        'https://www.pepperfry.com/category/showpieces.html',
        'https://www.pepperfry.com/category/sculptures.html',
        'https://www.pepperfry.com/category/figurines.html',
        'https://www.pepperfry.com/category/candle-holders.html',
        'https://www.pepperfry.com/category/decorative-bowls.html',
        'https://www.pepperfry.com/category/trays.html',

        # Wall Art
        'https://www.pepperfry.com/category/wall-art.html',
        'https://www.pepperfry.com/category/canvas-paintings.html',
        'https://www.pepperfry.com/category/metal-wall-art.html',
        'https://www.pepperfry.com/category/wall-hangings.html',

        # Furnishings
        'https://www.pepperfry.com/category/rugs.html',
        'https://www.pepperfry.com/category/carpets.html',
        'https://www.pepperfry.com/category/curtains.html',
        'https://www.pepperfry.com/category/cushion-covers.html',
        'https://www.pepperfry.com/category/throws.html',
    ]

    custom_settings = {
        **BaseProductSpider.custom_settings,
        'DOWNLOAD_DELAY': 3.0,
        'RANDOMIZE_DOWNLOAD_DELAY': 2.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
    }

    def parse(self, response):
        """Parse category pages and extract product links"""
        self.logger.info(f"Parsing category page: {response.url}")

        # Extract category from URL
        category = self.extract_category_from_url(response.url)

        # Pepperfry uses different product card selectors
        product_selectors = [
            'a.clipCardLink::attr(href)',
            '.pf-card a::attr(href)',
            '.product-card a::attr(href)',
            'a[href*="/buy-"]::attr(href)',
            '.product-listing a::attr(href)',
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Remove duplicates and filter valid product links
        product_links = list(set([
            link for link in product_links
            if link and ('/buy-' in link or '/product/' in link) and '.html' in link
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
            '.pagination a.next::attr(href)',
            'link[rel="next"]::attr(href)',
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

            # Try to extract JSON-LD structured data first
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
                    'h1.pf-title::text',
                    'h1.product-title::text',
                    'h1::text',
                    '[data-testid="product-title"]::text',
                    '.product-name h1::text',
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
                    '.pf-price-value::text',
                    '[data-testid="product-price"]::text',
                    '.product-price .price::text',
                    '.selling-price::text',
                    'span[itemprop="price"]::text',
                    '.price::text',
                ])
                price = self.extract_price(price_text) if price_text else None

            if not price:
                self.logger.warning(f"No price found for: {name}")
                return

            # Extract original price (for sale items)
            original_price = None
            original_price_text = self.extract_text_from_selectors(response, [
                '.pf-mrp-value::text',
                '.original-price::text',
                '.mrp::text',
                'span.strike::text',
            ])
            if original_price_text:
                original_price = self.extract_price(original_price_text)

            # Extract description
            description = self.extract_text_from_selectors(response, [
                '.pf-description::text',
                '[data-testid="product-description"]::text',
                '.product-description p::text',
                '.description-content::text',
                'div[itemprop="description"]::text',
            ])

            # Also try to get description from meta tag
            if not description:
                description = response.css('meta[name="description"]::attr(content)').get()

            # Extract external ID from URL or SKU
            external_id = None
            sku_match = re.search(r'-(\d+)\.html', response.url)
            if sku_match:
                external_id = sku_match.group(1)
            else:
                external_id = self._generate_external_id(response.url)

            # Extract brand
            brand = None
            if product_data:
                brand = product_data.get('brand', {}).get('name') if isinstance(product_data.get('brand'), dict) else product_data.get('brand')
            if not brand:
                brand = self.extract_text_from_selectors(response, [
                    '.pf-brand::text',
                    '[data-testid="brand-name"]::text',
                    '.brand-name::text',
                    'span[itemprop="brand"]::text',
                ])
            brand = brand or 'Pepperfry'

            # Extract images
            image_urls = []
            if product_data and 'image' in product_data:
                images = product_data['image']
                if isinstance(images, str):
                    image_urls.append(images)
                elif isinstance(images, list):
                    image_urls.extend(images[:10])

            if not image_urls:
                # Try various image selectors
                image_selectors = [
                    '.pf-gallery img::attr(src)',
                    '.product-gallery img::attr(src)',
                    '.product-images img::attr(data-src)',
                    '.product-images img::attr(src)',
                    'img[itemprop="image"]::attr(src)',
                    '.slick-slide img::attr(src)',
                ]
                for selector in image_selectors:
                    imgs = response.css(selector).getall()
                    if imgs:
                        image_urls.extend(imgs)
                        break

            # Clean and deduplicate image URLs
            image_urls = list(set([
                img for img in image_urls
                if img and not img.endswith('.svg') and 'placeholder' not in img.lower()
            ]))[:10]

            # Extract category from response or use meta
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

        # Extract specifications from table or list
        spec_selectors = [
            ('.pf-specs tr', 'td:first-child::text', 'td:last-child::text'),
            ('.specifications tr', 'td:first-child::text', 'td:last-child::text'),
            ('.product-specs li', 'span:first-child::text', 'span:last-child::text'),
            ('.spec-table tr', 'th::text', 'td::text'),
        ]

        for container_sel, key_sel, val_sel in spec_selectors:
            rows = response.css(container_sel)
            if rows:
                for row in rows:
                    key = row.css(key_sel).get()
                    value = row.css(val_sel).get()
                    if key and value:
                        key = key.strip().lower().replace(' ', '_').replace(':', '')
                        value = value.strip()
                        if key and value and len(value) < 200:
                            attributes[key] = value
                break

        # Extract dimensions from description or specs
        if description:
            # Look for dimension patterns
            dim_patterns = [
                r'(?:dimensions?|size):?\s*(?:L\s*x\s*W\s*x\s*H\s*:?\s*)?(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|inches?|in|")',
                r'(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|inches?|in|")',
                r'(?:L|Length):?\s*(\d+\.?\d*)\s*(?:cm|in)',
                r'(?:W|Width):?\s*(\d+\.?\d*)\s*(?:cm|in)',
                r'(?:H|Height):?\s*(\d+\.?\d*)\s*(?:cm|in)',
            ]

            for pattern in dim_patterns[:2]:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    attributes['dimensions'] = f"{match.group(1)} x {match.group(2)} x {match.group(3)}"
                    break

        # Extract material
        material_selectors = [
            '[data-testid="material"]::text',
            '.material-value::text',
            '.pf-material::text',
        ]
        material = self.extract_text_from_selectors(response, material_selectors)
        if material:
            attributes['material'] = material
        elif description:
            material_match = re.search(r'(?:material|made\s+(?:of|from)):?\s*([A-Za-z\s,&]+?)(?:\.|,|\n|$)', description, re.IGNORECASE)
            if material_match:
                mat = material_match.group(1).strip()
                if mat and len(mat) < 100:
                    attributes['material'] = mat

        # Extract color
        color_selectors = [
            '[data-testid="color"]::text',
            '.color-value::text',
            '.pf-color::text',
        ]
        color = self.extract_text_from_selectors(response, color_selectors)
        if color:
            attributes['color'] = color
        elif description:
            color_match = re.search(r'(?:colou?r):?\s*([A-Za-z\s]+?)(?:\.|,|\n|$)', description, re.IGNORECASE)
            if color_match:
                col = color_match.group(1).strip()
                if col and len(col) < 50:
                    attributes['color'] = col

        # Extract weight
        if description:
            weight_match = re.search(r'(?:weight):?\s*(\d+\.?\d*)\s*(?:kg|kgs?|gm|gms?|g)', description, re.IGNORECASE)
            if weight_match:
                attributes['weight'] = weight_match.group(0)

        # Extract seating capacity
        if description:
            seating_match = re.search(r'(\d+)\s*(?:seater|seating)', description, re.IGNORECASE)
            if seating_match:
                attributes['seating_capacity'] = seating_match.group(1)

        return attributes

    def extract_category_from_url(self, url: str) -> str:
        """Extract category name from URL"""
        try:
            # Map URL patterns to categories
            category_map = {
                'sofas': 'Sofa',
                'sofa-sets': 'Sofa',
                'coffee-tables': 'Coffee Table',
                'tv-units': 'TV Unit',
                'cabinets': 'Cabinet',
                'sideboards': 'Sideboard',
                'shoe-racks': 'Storage',
                'beds': 'Bed',
                'wardrobes': 'Wardrobe',
                'bedside-tables': 'Nightstand',
                'dressing-tables': 'Dresser',
                'chest-of-drawers': 'Chest of Drawers',
                'dining-tables': 'Dining Table',
                'dining-chairs': 'Dining Chair',
                'dining-sets': 'Dining Table',
                'accent-chairs': 'Accent Chair',
                'recliners': 'Recliner',
                'ottomans': 'Ottoman',
                'poufs': 'Ottoman',
                'benches': 'Bench',
                'stools': 'Stool',
                'study-tables': 'Study Table',
                'office-chairs': 'Office Chair',
                'book-shelves': 'Bookshelf',
                'display-units': 'Shelves',
                'wall-shelves': 'Shelves',
                'floor-lamps': 'Floor Lamp',
                'table-lamps': 'Table Lamp',
                'ceiling-lights': 'Ceiling Light',
                'wall-lights': 'Wall Lamp',
                'chandeliers': 'Chandelier',
                'mirrors': 'Mirror',
                'vases': 'Vase',
                'wall-decor': 'Decor & Accessories',
                'clocks': 'Clock',
                'photo-frames': 'Decor & Accessories',
                'planters': 'Planter',
                'planters-pots': 'Planter',
                'plant-stands': 'Planter',
                'hanging-planters': 'Planter',
                'sculptures': 'Decor & Accessories',
                'figurines': 'Decor & Accessories',
                'showpieces': 'Decor & Accessories',
                'candle-holders': 'Decor & Accessories',
                'decorative-bowls': 'Decor & Accessories',
                'decorative-trays': 'Decor & Accessories',
                'table-decor': 'Decor & Accessories',
                'bookends': 'Decor & Accessories',
                # Wall Art
                'wall-art': 'Wall Art',
                'canvas-art': 'Wall Art',
                'wall-paintings': 'Wall Art',
                'metal-wall-art': 'Wall Art',
                'wall-hangings': 'Wall Art',
                'wall-plates': 'Wall Art',
                # Rugs & Furnishings
                'rugs': 'Rugs',
                'carpets': 'Rugs',
                'runners': 'Rugs',
                'dhurries': 'Rugs',
                'curtains': 'Curtain',
                'cushion-covers': 'Cushion',
                'throws': 'Throw',
                'blankets': 'Throw',
            }

            url_lower = url.lower()
            for key, value in category_map.items():
                if key in url_lower:
                    return value

        except Exception:
            pass

        return 'Furniture'
