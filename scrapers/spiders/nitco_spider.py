"""
Nitco Floor Tiles Spider

Scrapes floor tiles from nitco.in for the Omnishop floor tile catalog.
This is a standalone spider (does NOT extend BaseProductSpider) since
tiles use a separate data model from furniture products.

Usage:
    cd scrapers
    scrapy crawl nitco_tiles -o ../api/scripts/nitco_tiles_output.jsonl
"""

import json
import logging
import re
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)


class NitcoTilesSpider(scrapy.Spider):
    name = "nitco_tiles"
    allowed_domains = ["nitco.in", "www.nitco.in"]

    # Entry points — living room floor tiles listing
    start_urls = [
        "https://www.nitco.in/living-room-floor-tiles/",
    ]

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "ROBOTSTXT_OBEY": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "FEEDS": {
            "nitco_tiles_output.jsonl": {
                "format": "jsonlines",
                "encoding": "utf-8",
                "overwrite": True,
            }
        },
    }

    def parse(self, response):
        """Parse the tile listing page and follow links to detail pages."""
        # Extract tile links from the grid
        tile_links = response.css("a.product-tile-link::attr(href)").getall()

        # Also try alternative selectors common on Nitco
        if not tile_links:
            tile_links = response.css(".product-card a::attr(href)").getall()
        if not tile_links:
            tile_links = response.css(".tile-item a::attr(href)").getall()
        if not tile_links:
            # Generic: grab all links that look like product detail pages
            tile_links = response.css('a[href*="product-details"]::attr(href)').getall()

        logger.info(f"Found {len(tile_links)} tile links on {response.url}")

        for link in tile_links:
            url = urljoin(response.url, link)
            yield scrapy.Request(url, callback=self.parse_tile_detail)

        # Handle pagination
        next_page = response.css("a.next-page::attr(href)").get()
        if not next_page:
            next_page = response.css('a[rel="next"]::attr(href)').get()
        if not next_page:
            next_page = response.css(".pagination a.active + a::attr(href)").get()

        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_tile_detail(self, response):
        """Parse individual tile detail page and extract structured data."""
        # Product name
        name = response.css("h1.product-name::text").get()
        if not name:
            name = response.css("h1::text").get()
        name = name.strip() if name else None

        if not name:
            logger.warning(f"No product name found at {response.url}")
            return

        # Product code — extract from URL or page content
        product_code = None
        # Try URL pattern: /product-details/living-room-floor-tiles/{name}/{code}
        url_match = re.search(r"/([A-Z0-9\-]+)/?$", response.url)
        if url_match:
            product_code = url_match.group(1)

        # Also try extracting from page
        if not product_code:
            code_el = response.css(".product-code::text").get()
            if code_el:
                product_code = code_el.strip()

        if not product_code:
            product_code = re.sub(r"[^a-zA-Z0-9]", "-", name)[:100]

        # Description
        description = response.css(".product-description::text").get()
        if not description:
            description = response.css('meta[name="description"]::attr(content)').get()
        description = description.strip() if description else None

        # Extract specs from the detail table
        specs = {}
        spec_rows = response.css(".product-specs tr, .product-details-table tr, .spec-row")
        for row in spec_rows:
            label = row.css("td:first-child::text, .spec-label::text").get()
            value = row.css("td:last-child::text, .spec-value::text").get()
            if label and value:
                specs[label.strip().lower()] = value.strip()

        # Also try key-value divs
        if not specs:
            for item in response.css(".product-attribute, .product-info-item"):
                label = item.css(".attr-label::text, .info-label::text").get()
                value = item.css(".attr-value::text, .info-value::text").get()
                if label and value:
                    specs[label.strip().lower()] = value.strip()

        # Size
        size = specs.get("size", specs.get("tile size", specs.get("dimensions", "")))
        size_width_mm, size_height_mm = self._parse_size(size)

        # Other attributes
        finish = specs.get("finish", specs.get("surface finish", ""))
        look = specs.get("look", specs.get("design look", ""))
        color = specs.get("color", specs.get("colour", ""))
        material = specs.get("material", specs.get("tile type", specs.get("body type", "")))

        # Images
        images = []
        # Main product image
        main_img = response.css(".product-main-image img::attr(src)").get()
        if not main_img:
            main_img = response.css(".product-gallery img::attr(src)").get()
        if not main_img:
            main_img = response.css('meta[property="og:image"]::attr(content)').get()

        if main_img:
            images.append(urljoin(response.url, main_img))

        # Additional images
        for img_el in response.css(".product-gallery img, .product-thumbnails img"):
            src = img_el.attrib.get("src") or img_el.attrib.get("data-src")
            if src:
                full_url = urljoin(response.url, src)
                if full_url not in images:
                    images.append(full_url)

        # Swatch image — look for specific swatch or texture close-up
        swatch_url = None
        for img_url in images:
            if "swatch" in img_url.lower() or "texture" in img_url.lower():
                swatch_url = img_url
                break
        # If no explicit swatch, use the first image as swatch
        if not swatch_url and images:
            swatch_url = images[0]

        yield {
            "product_code": product_code,
            "name": name,
            "description": description,
            "size": size or "Unknown",
            "size_width_mm": size_width_mm,
            "size_height_mm": size_height_mm,
            "finish": finish or None,
            "look": look or None,
            "color": color or None,
            "material": material or None,
            "vendor": "Nitco",
            "product_url": response.url,
            "swatch_url": swatch_url,
            "image_url": images[0] if images else None,
            "additional_images": images[1:] if len(images) > 1 else [],
        }

    def _parse_size(self, size_str: str) -> tuple:
        """Parse size string like '1200x1800' or '600 x 600 mm' into (width_mm, height_mm)."""
        if not size_str:
            return (None, None)

        # Remove 'mm' suffix and whitespace
        cleaned = re.sub(r"[mM]{2}", "", size_str).strip()

        # Try pattern like "1200x1800" or "1200 x 1800"
        match = re.search(r"(\d+)\s*[xX×]\s*(\d+)", cleaned)
        if match:
            return (int(match.group(1)), int(match.group(2)))

        return (None, None)
