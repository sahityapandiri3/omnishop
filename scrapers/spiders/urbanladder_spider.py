"""
Urban Ladder spider for furniture and home decor products
Website: https://www.urbanladder.com
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class UrbanLadderSpider(BaseProductSpider):
    """Spider for scraping Urban Ladder furniture and home decor products"""

    name = 'urbanladder'
    allowed_domains = ['urbanladder.com', 'www.urbanladder.com']

    # Category URLs using correct query parameter format
    start_urls = [
        # Main category pages - using l1_category format
        'https://www.urbanladder.com/products/?l1_category=sofas-recliners&department=urban-ladder-furniture',
        'https://www.urbanladder.com/products/?l1_category=living-room&department=urban-ladder-furniture',
        'https://www.urbanladder.com/products/?l1_category=bedroom-mattresses&department=urban-ladder-furniture',
        'https://www.urbanladder.com/products/?l1_category=dining-room&department=urban-ladder-furniture',
        'https://www.urbanladder.com/products/?l1_category=storage-furniture&department=urban-ladder-furniture',
        'https://www.urbanladder.com/products/?l1_category=study&department=urban-ladder-furniture',
        'https://www.urbanladder.com/products/?l1_category=lighting--decor&department=urban-ladder-furniture',
        'https://www.urbanladder.com/products/?l1_category=outdoor-furniture&department=urban-ladder-furniture',
        'https://www.urbanladder.com/products/?l1_category=home-office-study&department=furniture',
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

        # Urban Ladder product link selectors
        product_selectors = [
            'a.product-card__link::attr(href)',
            '.product-card a::attr(href)',
            'a[href*="/products/"]::attr(href)',
            '.product-tile a::attr(href)',
            '.product-list a::attr(href)',
            '.plp-card a::attr(href)',
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Remove duplicates and filter valid product links
        product_links = list(set([
            link for link in product_links
            if link and '/products/' in link
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
            '.pagination__next::attr(href)',
            'a:contains("Next")::attr(href)',
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

            # Try to find embedded product JSON data
            script_data = response.css('script:contains("__INITIAL_STATE__")::text').get()
            initial_state = None
            if script_data:
                match = re.search(r'__INITIAL_STATE__\s*=\s*({.*?});', script_data, re.DOTALL)
                if match:
                    try:
                        initial_state = json.loads(match.group(1))
                    except json.JSONDecodeError:
                        pass

            # Extract name
            name = None
            if product_data:
                name = product_data.get('name')
            if not name:
                name = self.extract_text_from_selectors(response, [
                    'h1.product-title::text',
                    'h1.pdp-title::text',
                    'h1::text',
                    '.product-name::text',
                    '[data-testid="product-title"]::text',
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
                    '.product-price::text',
                    '.pdp-price::text',
                    '.selling-price::text',
                    'span[itemprop="price"]::text',
                    '.price-value::text',
                    '[data-testid="product-price"]::text',
                ])
                price = self.extract_price(price_text) if price_text else None

            if not price:
                self.logger.warning(f"No price found for: {name}")
                return

            # Extract original price
            original_price = None
            original_price_text = self.extract_text_from_selectors(response, [
                '.mrp::text',
                '.original-price::text',
                '.striked-price::text',
                '.was-price::text',
            ])
            if original_price_text:
                original_price = self.extract_price(original_price_text)

            # Extract description
            description = self.extract_text_from_selectors(response, [
                '.product-description::text',
                '.pdp-description::text',
                'div[itemprop="description"]::text',
                '.description-content p::text',
            ])

            if not description:
                description = response.css('meta[name="description"]::attr(content)').get()

            # Extract external ID from URL
            external_id = None
            sku_match = re.search(r'/products/([^/?]+)', response.url)
            if sku_match:
                external_id = sku_match.group(1)
            else:
                external_id = self._generate_external_id(response.url)

            # Extract brand
            brand = None
            if product_data:
                brand_data = product_data.get('brand')
                if isinstance(brand_data, dict):
                    brand = brand_data.get('name')
                else:
                    brand = brand_data
            if not brand:
                brand = self.extract_text_from_selectors(response, [
                    '.brand-name::text',
                    'span[itemprop="brand"]::text',
                    '.product-brand::text',
                ])
            brand = brand or 'Urban Ladder'

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
                    '.product-gallery img::attr(src)',
                    '.pdp-gallery img::attr(src)',
                    '.product-images img::attr(data-src)',
                    '.product-images img::attr(src)',
                    '.slick-slide img::attr(src)',
                    'img[itemprop="image"]::attr(src)',
                    '.carousel img::attr(src)',
                ]
                for selector in image_selectors:
                    imgs = response.css(selector).getall()
                    if imgs:
                        image_urls.extend(imgs)
                        break

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

        # Extract specifications from table
        spec_rows = response.css('.specifications tr, .spec-table tr, .product-specs tr')
        for row in spec_rows:
            key = row.css('td:first-child::text, th::text').get()
            value = row.css('td:last-child::text, td:nth-child(2)::text').get()
            if key and value:
                key = key.strip().lower().replace(' ', '_').replace(':', '')
                value = value.strip()
                if key and value and len(value) < 200:
                    attributes[key] = value

        # Extract from spec lists
        spec_items = response.css('.spec-item, .product-spec li')
        for item in spec_items:
            text = item.css('::text').get()
            if text and ':' in text:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower().replace(' ', '_')
                    value = parts[1].strip()
                    if key and value and len(value) < 200:
                        attributes[key] = value

        # Extract dimensions
        if description:
            dim_patterns = [
                r'(?:dimensions?|size):?\s*(?:L\s*x\s*W\s*x\s*H\s*:?\s*)?(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|inches?|in|")',
                r'(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|inches?|in|")',
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

        # Extract color
        if 'color' not in attributes:
            color = self.extract_text_from_selectors(response, [
                '.color-name::text',
                '.selected-color::text',
                '[data-testid="color"]::text',
            ])
            if color:
                attributes['color'] = color.strip()
            elif description:
                color_match = re.search(r'(?:colou?r):?\s*([A-Za-z\s]+?)(?:\.|,|\n|$)', description, re.IGNORECASE)
                if color_match:
                    col = color_match.group(1).strip()
                    if col and len(col) < 50:
                        attributes['color'] = col

        # Extract weight
        if 'weight' not in attributes and description:
            weight_match = re.search(r'(?:weight):?\s*(\d+\.?\d*)\s*(?:kg|kgs?|gm|gms?|g)', description, re.IGNORECASE)
            if weight_match:
                attributes['weight'] = weight_match.group(0)

        # Extract seating capacity
        if description:
            seating_match = re.search(r'(\d+)\s*(?:seater|seating)', description, re.IGNORECASE)
            if seating_match:
                attributes['seating_capacity'] = seating_match.group(1)

        # Extract warranty
        warranty = self.extract_text_from_selectors(response, [
            '.warranty::text',
            '[data-testid="warranty"]::text',
        ])
        if warranty:
            attributes['warranty'] = warranty

        return attributes

    def extract_category_from_url(self, url: str) -> str:
        """Extract category name from URL"""
        try:
            category_map = {
                'sofas': 'Sofa',
                'coffee-tables': 'Coffee Table',
                'tv-units': 'TV Unit',
                'console-tables': 'Console Table',
                'side-and-end-tables': 'Side Table',
                'cabinets-and-sideboards': 'Cabinet',
                'shoe-racks': 'Storage',
                'display-units': 'Shelves',
                'beds': 'Bed',
                'bedside-tables': 'Nightstand',
                'wardrobes': 'Wardrobe',
                'chest-of-drawers': 'Chest of Drawers',
                'dressing-tables': 'Dresser',
                'dining-tables': 'Dining Table',
                'dining-chairs': 'Dining Chair',
                'dining-sets': 'Dining Table',
                'bar-cabinets': 'Cabinet',
                'bar-stools': 'Stool',
                'accent-chairs': 'Accent Chair',
                'recliners': 'Recliner',
                'ottomans-and-stools': 'Ottoman',
                'benches': 'Bench',
                'lounge-chairs': 'Lounge Chair',
                'study-tables': 'Study Table',
                'office-chairs': 'Office Chair',
                'bookshelves': 'Bookshelf',
                'floor-lamps': 'Floor Lamp',
                'table-lamps': 'Table Lamp',
                'ceiling-lights': 'Ceiling Light',
                'wall-lights': 'Wall Lamp',
                'chandeliers': 'Chandelier',
                'mirrors': 'Mirror',
                'vases-and-planters': 'Vase',
                'vases': 'Vase',
                'wall-decor': 'Decor & Accessories',
                'clocks': 'Clock',
                'showpieces-and-sculptures': 'Sculpture',
                'photo-frames': 'Photo Frame',
                'candle-holders': 'Decor & Accessories',
                'decorative-bowls': 'Decor & Accessories',
                'trays': 'Decor & Accessories',
                # Wall Art
                'wall-art': 'Wall Art',
                'canvas-art': 'Wall Art',
                'wall-paintings': 'Wall Art',
                'metal-wall-art': 'Wall Art',
                'wall-hangings': 'Wall Art',
                # Planters
                'planters': 'Planter',
                'plant-stands': 'Planter',
                'hanging-planters': 'Planter',
                'pots': 'Planter',
                # Rugs & Furnishings
                'rugs-and-carpets': 'Rugs',
                'rugs': 'Rugs',
                'runners': 'Rugs',
                'dhurries': 'Rugs',
                'curtains': 'Curtain',
                'cushion-covers': 'Cushion',
                'throws-and-blankets': 'Throw',
                'throws': 'Throw',
            }

            url_lower = url.lower()
            for key, value in category_map.items():
                if key in url_lower:
                    return value

        except Exception:
            pass

        return 'Furniture'
