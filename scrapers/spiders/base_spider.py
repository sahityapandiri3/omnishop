"""
Base spider class with common functionality
"""
import scrapy
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
import logging
import time

from ..items import ProductItem, CategoryItem, ImageItem
from config.settings import settings

logger = logging.getLogger(__name__)


class BaseProductSpider(scrapy.Spider):
    """Base spider class for product scraping"""

    custom_settings = {
        'DOWNLOAD_DELAY': settings.scraping.download_delay,
        'RANDOMIZE_DOWNLOAD_DELAY': settings.scraping.randomize_download_delay,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'ITEM_PIPELINES': {
            'scrapers.pipelines.ValidationPipeline': 200,
            'scrapers.pipelines.DuplicatesPipeline': 250,
            # Disabled CustomImagesPipeline due to Scrapy compatibility issues
            # Images will be saved as direct URLs instead
            # 'scrapers.pipelines.CustomImagesPipeline': 300,
            'scrapers.pipelines.CategoryPipeline': 350,
            'scrapers.pipelines.DatabasePipeline': 400,
            'scrapers.pipelines.StatsPipeline': 500,
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = datetime.utcnow()
        self.products_scraped = 0
        self.errors_count = 0

    def start_requests(self):
        """Generate initial requests"""
        start_urls = getattr(self, 'start_urls', [])
        for url in start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={'dont_cache': True}
            )

    def parse(self, response):
        """Default parse method - to be overridden"""
        raise NotImplementedError("Subclasses must implement parse method")

    def extract_text(self, selector, default: str = None) -> Optional[str]:
        """Extract and clean text from selector"""
        try:
            text = selector.get()
            if text:
                return text.strip()
            return default
        except Exception:
            return default

    def extract_text_list(self, selector) -> List[str]:
        """Extract list of text values from selector"""
        try:
            texts = selector.getall()
            return [text.strip() for text in texts if text.strip()]
        except Exception:
            return []

    def extract_price(self, price_text: str) -> Optional[float]:
        """Extract numeric price from text"""
        if not price_text:
            return None

        try:
            import re
            # Remove currency symbols and extract number
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if price_match:
                return float(price_match.group())
        except (ValueError, AttributeError):
            pass

        return None

    def create_product_item(
        self,
        response,
        name: str,
        price: float,
        external_id: str = None,
        description: str = None,
        brand: str = None,
        category: str = None,
        image_urls: List[str] = None,
        attributes: Dict[str, str] = None,
        **kwargs
    ) -> ProductItem:
        """Create a standardized product item"""

        item = ProductItem()

        # Basic information
        item['name'] = name
        item['price'] = price
        item['external_id'] = external_id or self._generate_external_id(response.url)
        item['description'] = description
        item['brand'] = brand
        item['category'] = category

        # Source information
        item['source_website'] = self.name
        item['source_url'] = response.url
        item['scraped_at'] = datetime.utcnow().isoformat()

        # Images
        item['image_urls'] = image_urls or []

        # Additional attributes
        item['attributes'] = attributes or {}

        # Availability (default to available)
        item['is_available'] = kwargs.get('is_available', True)
        item['is_on_sale'] = kwargs.get('is_on_sale', False)
        item['stock_status'] = kwargs.get('stock_status', 'in_stock')

        # Pricing
        item['currency'] = kwargs.get('currency', 'INR')  # Changed from USD to INR
        item['original_price'] = kwargs.get('original_price')

        # Product details
        item['model'] = kwargs.get('model')
        item['sku'] = kwargs.get('sku')

        self.products_scraped += 1
        return item

    def _generate_external_id(self, url: str) -> str:
        """Generate external ID from URL if not provided"""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def handle_error(self, failure):
        """Handle request errors"""
        self.errors_count += 1
        logger.error(f"Request failed: {failure.request.url}, Error: {failure.value}")

    def closed(self, reason):
        """Spider closed callback"""
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()

        logger.info(f"Spider {self.name} finished. Reason: {reason}")
        logger.info(f"Products scraped: {self.products_scraped}")
        logger.info(f"Errors: {self.errors_count}")
        logger.info(f"Duration: {duration:.2f} seconds")

    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""

        import re
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        # Remove special characters that might cause issues
        text = re.sub(r'[^\w\s\-.,()/$%&]', '', text)
        return text

    def normalize_category(self, category: str) -> str:
        """Normalize category names"""
        if not category:
            return "Uncategorized"

        # Convert to title case and clean
        category = self.clean_text(category)
        category = category.title()

        # Map common variations
        category_mapping = {
            'Living Room': 'Living Room',
            'Bedroom': 'Bedroom',
            'Dining Room': 'Dining Room',
            'Office': 'Office',
            'Outdoor': 'Outdoor',
            'Storage': 'Storage',
            'Lighting': 'Lighting',
            'Rugs': 'Rugs & Textiles',
            'Decor': 'Decor & Accessories',
            'Furniture': 'Furniture'
        }

        return category_mapping.get(category, category)

    def extract_dimensions(self, text: str) -> Dict[str, str]:
        """Extract product dimensions from text"""
        dimensions = {}
        if not text:
            return dimensions

        import re

        # Common dimension patterns
        patterns = [
            r'(\d+(?:\.\d+)?)\s*["\']?\s*[wW]\s*x\s*(\d+(?:\.\d+)?)\s*["\']?\s*[dD]\s*x\s*(\d+(?:\.\d+)?)\s*["\']?\s*[hH]',
            r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)',
            r'[wW]idth[:\s]*(\d+(?:\.\d+)?)',
            r'[dD]epth[:\s]*(\d+(?:\.\d+)?)',
            r'[hH]eight[:\s]*(\d+(?:\.\d+)?)'
        ]

        # Try full dimensions first
        for pattern in patterns[:2]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                dimensions.update({
                    'width': match.group(1),
                    'depth': match.group(2),
                    'height': match.group(3)
                })
                break

        # Try individual dimensions
        if not dimensions:
            for pattern in patterns[2:]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if 'width' in pattern.lower():
                        dimensions['width'] = match.group(1)
                    elif 'depth' in pattern.lower():
                        dimensions['depth'] = match.group(1)
                    elif 'height' in pattern.lower():
                        dimensions['height'] = match.group(1)

        return dimensions