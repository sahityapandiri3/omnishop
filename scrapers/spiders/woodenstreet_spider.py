"""
Wooden Street spider for furniture and home decor products
Website: https://www.woodenstreet.com
"""
import scrapy
from urllib.parse import urljoin
import json
import re
from typing import List, Dict, Optional

from .base_spider import BaseProductSpider
from ..items import ProductItem


class WoodenStreetSpider(BaseProductSpider):
    """Spider for scraping Wooden Street furniture and home decor products"""

    name = 'woodenstreet'
    allowed_domains = ['woodenstreet.com', 'www.woodenstreet.com']

    # Category URLs from sitemap - using verified category patterns
    start_urls = [
        # Living Room - Sofas
        'https://www.woodenstreet.com/3-seater-sofa-designs',
        'https://www.woodenstreet.com/2-seater-sofa-designs',
        'https://www.woodenstreet.com/7-seater-sofa-set',
        'https://www.woodenstreet.com/l-shaped-sofa-designs',
        'https://www.woodenstreet.com/sofa-cum-bed-designs',
        'https://www.woodenstreet.com/recliners',

        # Living Room - Tables
        'https://www.woodenstreet.com/coffee-table-designs',
        'https://www.woodenstreet.com/centre-table-designs',
        'https://www.woodenstreet.com/console-table-designs',
        'https://www.woodenstreet.com/side-table-designs',

        # Living Room - Storage
        'https://www.woodenstreet.com/tv-unit-designs',
        'https://www.woodenstreet.com/shoe-rack-designs',
        'https://www.woodenstreet.com/cabinet-designs',
        'https://www.woodenstreet.com/display-unit-designs',

        # Bedroom
        'https://www.woodenstreet.com/king-size-bed-designs',
        'https://www.woodenstreet.com/queen-size-bed-designs',
        'https://www.woodenstreet.com/single-bed-designs',
        'https://www.woodenstreet.com/bed-with-storage-designs',
        'https://www.woodenstreet.com/wardrobe-designs',
        'https://www.woodenstreet.com/bedside-table-designs',
        'https://www.woodenstreet.com/chest-of-drawers-designs',
        'https://www.woodenstreet.com/dressing-table-designs',

        # Dining
        'https://www.woodenstreet.com/6-seater-dining-table-set-designs',
        'https://www.woodenstreet.com/4-seater-dining-table-set-designs',
        'https://www.woodenstreet.com/8-seater-dining-table-set-designs',
        'https://www.woodenstreet.com/dining-table-designs',
        'https://www.woodenstreet.com/dining-chair-designs',
        'https://www.woodenstreet.com/bar-cabinet-designs',
        'https://www.woodenstreet.com/bar-stool-designs',

        # Seating
        'https://www.woodenstreet.com/chair-designs',
        'https://www.woodenstreet.com/accent-chair-designs',
        'https://www.woodenstreet.com/ottoman-designs',
        'https://www.woodenstreet.com/bench-designs',
        'https://www.woodenstreet.com/stool-designs',

        # Study & Office
        'https://www.woodenstreet.com/study-table-designs',
        'https://www.woodenstreet.com/office-table-designs',
        'https://www.woodenstreet.com/office-chair-designs',
        'https://www.woodenstreet.com/bookshelf-designs',

        # Storage
        'https://www.woodenstreet.com/wall-shelf-designs',

        # Lighting
        'https://www.woodenstreet.com/floor-lamp-designs',
        'https://www.woodenstreet.com/table-lamp-designs',
        'https://www.woodenstreet.com/ceiling-light-designs',
        'https://www.woodenstreet.com/wall-lamp-designs',
        'https://www.woodenstreet.com/chandelier-designs',
        'https://www.woodenstreet.com/pendant-light-designs',

        # Decor
        'https://www.woodenstreet.com/mirror-designs',
        'https://www.woodenstreet.com/vase-designs',
        'https://www.woodenstreet.com/wall-clock-designs',
        'https://www.woodenstreet.com/planter-designs',
        'https://www.woodenstreet.com/showpiece-designs',
        'https://www.woodenstreet.com/photo-frame-designs',

        # Wall Art
        'https://www.woodenstreet.com/wall-paintings',
        'https://www.woodenstreet.com/wall-art-designs',
        'https://www.woodenstreet.com/metal-wall-art-designs',

        # Furnishings
        'https://www.woodenstreet.com/rugs',
        'https://www.woodenstreet.com/carpets',
        'https://www.woodenstreet.com/curtains',
        'https://www.woodenstreet.com/cushion-cover-designs',
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

        # Wooden Street product link selectors - products use /product/ URL pattern
        product_selectors = [
            'a[href*="/product/"]::attr(href)',
            '.product-card a::attr(href)',
            '.product-item a::attr(href)',
            '.plp-product a::attr(href)',
            '.ws-product-card a::attr(href)',
        ]

        product_links = []
        for selector in product_selectors:
            links = response.css(selector).getall()
            product_links.extend(links)

        # Also try XPath for product links
        xpath_links = response.xpath('//a[contains(@href, "/product/")]/@href').getall()
        product_links.extend(xpath_links)

        # Remove duplicates and filter valid product links
        product_links = list(set([
            link for link in product_links
            if link and '/product/' in link
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
            'a:contains("Next")::attr(href)',
            'link[rel="next"]::attr(href)',
            '.page-link[aria-label="Next"]::attr(href)',
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
                    'h1.product-title::text',
                    'h1.pdp-title::text',
                    'h1::text',
                    '.product-name h1::text',
                    '.ws-pdp-title::text',
                    '[itemprop="name"]::text',
                ])

            if not name:
                self.logger.warning(f"No product name found: {response.url}")
                return

            # Extract price
            price = None
            if product_data and 'offers' in product_data:
                offers = product_data['offers']
                if isinstance(offers, dict):
                    # Check for direct price first
                    if offers.get('price'):
                        price = self.extract_price(str(offers.get('price', '')))
                    # Then check priceSpecification (Wooden Street uses this)
                    elif offers.get('priceSpecification'):
                        price_spec = offers['priceSpecification']
                        if isinstance(price_spec, list) and price_spec:
                            # First item is usually the sale price
                            price = self.extract_price(str(price_spec[0].get('price', '')))
                        elif isinstance(price_spec, dict):
                            price = self.extract_price(str(price_spec.get('price', '')))
                elif isinstance(offers, list) and offers:
                    price = self.extract_price(str(offers[0].get('price', '')))

            if not price:
                price_text = self.extract_text_from_selectors(response, [
                    '.product-price::text',
                    '.ws-price::text',
                    '.selling-price::text',
                    'span[itemprop="price"]::text',
                    '.price-value::text',
                    '#product-price::text',
                    '.pdp-price::text',
                ])
                price = self.extract_price(price_text) if price_text else None

            if not price:
                self.logger.warning(f"No price found for: {name}")
                return

            # Extract original price
            original_price = None
            # Try to get original price from priceSpecification (ListPrice type)
            if product_data and 'offers' in product_data:
                offers = product_data['offers']
                if isinstance(offers, dict) and offers.get('priceSpecification'):
                    price_spec = offers['priceSpecification']
                    if isinstance(price_spec, list):
                        for spec in price_spec:
                            if spec.get('priceType') and 'ListPrice' in str(spec.get('priceType', '')):
                                original_price = self.extract_price(str(spec.get('price', '')))
                                break

            if not original_price:
                original_price_text = self.extract_text_from_selectors(response, [
                    '.mrp::text',
                    '.original-price::text',
                    '.ws-mrp::text',
                    '.striked-price::text',
                ])
                if original_price_text:
                    original_price = self.extract_price(original_price_text)

            # Extract description
            description = self.extract_text_from_selectors(response, [
                '.product-description::text',
                '.ws-description::text',
                'div[itemprop="description"]::text',
                '.pdp-description p::text',
                '#product-description::text',
            ])

            if not description:
                description = response.css('meta[name="description"]::attr(content)').get()

            # Extract external ID from URL
            external_id = None
            # Wooden Street URLs are like: /product-name-online
            sku_match = re.search(r'/([^/]+)-online$', response.url)
            if sku_match:
                external_id = sku_match.group(1)
            else:
                external_id = self._generate_external_id(response.url)

            # Extract brand (Wooden Street is the brand)
            brand = 'Wooden Street'

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
                    '.ws-gallery img::attr(src)',
                    '.product-images img::attr(data-src)',
                    '.product-images img::attr(src)',
                    '.slick-slide img::attr(src)',
                    'img[itemprop="image"]::attr(src)',
                    '.pdp-image img::attr(src)',
                    '.carousel img::attr(src)',
                    '.zoom-gallery img::attr(src)',
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

            # Also check for out of stock text
            out_of_stock = response.css('.out-of-stock, .sold-out').get()
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

        # Extract specifications from JSON data (Wooden Street stores specs in JSON)
        # Look for dimensions array with dimensionlabel/dimensiondata structure
        scripts = response.css('script::text').getall()
        for script in scripts:
            # Look for dimensions array in JavaScript
            if 'dimensionlabel' in script and 'dimensiondata' in script:
                try:
                    # Try to find and parse the dimensions array
                    import re
                    # Match array of dimension objects
                    dim_matches = re.findall(
                        r'\{"dimensionlabel"\s*:\s*"([^"]+)"\s*,\s*"dimensiondata"\s*:\s*"([^"]+)"\}',
                        script
                    )
                    for label, data in dim_matches:
                        key = label.strip().lower().replace(' ', '_').replace(':', '')
                        value = data.strip()
                        if key and value and len(value) < 200:
                            attributes[key] = value
                except Exception as e:
                    self.logger.debug(f"Error parsing dimensions JSON: {e}")

        # Also try extracting from page content with different patterns
        page_text = response.text
        if 'dimensionlabel' in page_text:
            try:
                dim_matches = re.findall(
                    r'"dimensionlabel"\s*:\s*"([^"]+)"\s*,\s*"dimensiondata"\s*:\s*"([^"]+)"',
                    page_text
                )
                for label, data in dim_matches:
                    key = label.strip().lower().replace(' ', '_').replace(':', '')
                    value = data.strip()
                    if key and value and len(value) < 200 and key not in attributes:
                        attributes[key] = value
            except Exception as e:
                self.logger.debug(f"Error parsing page dimensions: {e}")

        # Extract specifications from table (fallback)
        spec_rows = response.css('.specifications tr, .spec-table tr, .product-specs tr, .ws-specs tr')
        for row in spec_rows:
            key = row.css('td:first-child::text, th::text').get()
            value = row.css('td:last-child::text, td:nth-child(2)::text').get()
            if key and value:
                key = key.strip().lower().replace(' ', '_').replace(':', '')
                value = value.strip()
                if key and value and len(value) < 200:
                    attributes[key] = value

        # Extract from definition lists
        dt_elements = response.css('.product-details dt, .ws-details dt')
        for dt in dt_elements:
            key = dt.css('::text').get()
            dd = dt.xpath('./following-sibling::dd[1]/text()').get()
            if key and dd:
                key = key.strip().lower().replace(' ', '_').replace(':', '')
                value = dd.strip()
                if key and value and len(value) < 200:
                    attributes[key] = value

        # Wooden Street often lists wood type prominently
        wood_type = self.extract_text_from_selectors(response, [
            '.wood-type::text',
            '.material-type::text',
            '[data-attr="wood"]::text',
        ])
        if wood_type:
            attributes['wood_type'] = wood_type

        # Extract finish
        finish = self.extract_text_from_selectors(response, [
            '.finish-type::text',
            '[data-attr="finish"]::text',
            '.product-finish::text',
        ])
        if finish:
            attributes['finish'] = finish

        # Extract dimensions
        if description:
            dim_patterns = [
                r'(?:dimensions?|size):?\s*(?:L\s*x\s*W\s*x\s*H\s*:?\s*)?(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|inches?|in|")',
                r'(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:x|×)\s*(\d+\.?\d*)\s*(?:cm|inches?|in|")',
                r'(?:L|Length):?\s*(\d+\.?\d*)\s*(?:cm|in)',
            ]
            for pattern in dim_patterns[:2]:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    attributes['dimensions'] = f"{match.group(1)} x {match.group(2)} x {match.group(3)}"
                    break

        # Extract material if not already found
        if 'material' not in attributes and 'wood_type' not in attributes and description:
            material_match = re.search(r'(?:material|made\s+(?:of|from)|wood):?\s*([A-Za-z\s,&]+?)(?:\.|,|\n|$)', description, re.IGNORECASE)
            if material_match:
                mat = material_match.group(1).strip()
                if mat and len(mat) < 100:
                    attributes['material'] = mat

        # Extract color/finish from description
        if 'color' not in attributes and 'finish' not in attributes:
            color = self.extract_text_from_selectors(response, [
                '.color-name::text',
                '.selected-color::text',
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

        # Extract warranty
        warranty = self.extract_text_from_selectors(response, [
            '.warranty::text',
            '.ws-warranty::text',
        ])
        if warranty:
            attributes['warranty'] = warranty

        return attributes

    def extract_category_from_url(self, url: str) -> str:
        """Extract category name from URL"""
        try:
            category_map = {
                'sofas': 'Sofa',
                'l-shaped-sofa': 'Sectional Sofa',
                'sofa-cum-bed': 'Sofa',
                'coffee-tables': 'Coffee Table',
                'tv-units': 'TV Unit',
                'console-tables': 'Console Table',
                'side-tables': 'Side Table',
                'end-tables': 'Side Table',
                'cabinets': 'Cabinet',
                'shoe-racks': 'Storage',
                'beds': 'Bed',
                'king-size-beds': 'King Bed',
                'queen-size-beds': 'Queen Bed',
                'bedside-tables': 'Nightstand',
                'wardrobes': 'Wardrobe',
                'chest-of-drawers': 'Chest of Drawers',
                'dressing-tables': 'Dresser',
                'dining-tables': 'Dining Table',
                'dining-chairs': 'Dining Chair',
                'dining-table-set': 'Dining Table',
                'bar-furniture': 'Cabinet',
                'bar-stools': 'Stool',
                'chairs': 'Chair',
                'accent-chairs': 'Accent Chair',
                'recliners': 'Recliner',
                'ottomans': 'Ottoman',
                'pouffe': 'Ottoman',
                'benches': 'Bench',
                'stools': 'Stool',
                'study-tables': 'Study Table',
                'office-chairs': 'Office Chair',
                'bookshelves': 'Bookshelf',
                'office-furniture': 'Desk',
                'wall-shelves': 'Shelves',
                'display-units': 'Shelves',
                'floor-lamps': 'Floor Lamp',
                'table-lamps': 'Table Lamp',
                'ceiling-lights': 'Ceiling Light',
                'wall-lights': 'Wall Lamp',
                'chandeliers': 'Chandelier',
                'pendant-lights': 'Pendant Lamp',
                'mirrors': 'Mirror',
                'vases': 'Vase',
                'wall-decor': 'Decor & Accessories',
                'clocks': 'Clock',
                'planters': 'Planter',
                'plant-stands': 'Planter',
                'hanging-planters': 'Planter',
                'pots': 'Planter',
                'showpieces': 'Sculpture',
                'figurines': 'Sculpture',
                'sculptures': 'Sculpture',
                'photo-frames': 'Photo Frame',
                'candle-holders': 'Decor & Accessories',
                'decorative-bowls': 'Decor & Accessories',
                'decorative-trays': 'Decor & Accessories',
                # Wall Art
                'wall-art': 'Wall Art',
                'canvas-paintings': 'Wall Art',
                'wall-paintings': 'Wall Art',
                'metal-wall-art': 'Wall Art',
                'wall-hangings': 'Wall Art',
                'wall-plates': 'Wall Art',
                # Rugs & Furnishings
                'rugs-and-carpets': 'Rugs',
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
