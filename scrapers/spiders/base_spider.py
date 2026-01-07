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
            # Generate embeddings and classify styles before saving
            'scrapers.pipelines.EmbeddingAndStylePipeline': 380,
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

    def extract_text_from_selectors(self, response, selectors: List[str], default: str = None) -> Optional[str]:
        """Try multiple CSS selectors in order until one returns a value"""
        for selector_str in selectors:
            try:
                text = response.css(selector_str).get()
                if text:
                    return text.strip()
            except Exception:
                continue
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

        # Smart categorization: determine category from product name
        # Uses the provided category as fallback if no match found in name
        smart_category = self.determine_category_from_name(name, category)

        # Basic information
        item['name'] = name
        item['price'] = price
        item['external_id'] = external_id or self._generate_external_id(response.url)
        item['description'] = description
        item['brand'] = brand
        item['category'] = smart_category

        # Source information
        item['source_website'] = self.name
        item['source_url'] = response.url
        item['scraped_at'] = datetime.utcnow().isoformat()

        # Images
        item['image_urls'] = image_urls or []

        # Additional attributes - enrich with sofa alignment if applicable
        enriched_attributes = self.enrich_attributes_with_alignment(
            attributes or {},
            name,
            description
        )
        item['attributes'] = enriched_attributes

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
            'Rugs': 'Rugs',
            'Rug': 'Rugs',  # Handle singular form
            'Decor': 'Decor & Accessories',
            'Furniture': 'Furniture'
        }

        return category_mapping.get(category, category)

    def determine_category_from_name(self, product_name: str, fallback_category: str = None) -> str:
        """
        Determine the correct category based on product name.
        This provides smart categorization by analyzing the product name for keywords.

        Args:
            product_name: The product's name/title
            fallback_category: Category to use if no match found (e.g., from URL or breadcrumbs)

        Returns:
            The determined category name
        """
        if not product_name:
            return fallback_category or 'Furniture'

        name_lower = product_name.lower()

        # Ottoman detection - must come before sofa check
        if 'ottoman' in name_lower:
            return 'Ottoman'

        # Side table detection - must come before table check
        if 'side table' in name_lower or 'sidetable' in name_lower or 'end table' in name_lower:
            return 'Side Table'

        # Coffee table detection
        if 'coffee table' in name_lower:
            return 'Coffee Table'

        # Console table detection
        if 'console' in name_lower and 'table' in name_lower:
            return 'Console Table'

        # Dining table detection
        if 'dining table' in name_lower or ('dining' in name_lower and 'table' in name_lower):
            return 'Dining Table'

        # Center table detection
        if 'center table' in name_lower or 'centre table' in name_lower:
            return 'Center Table'

        # Nightstand / Bedside table
        if 'nightstand' in name_lower or 'night stand' in name_lower or 'bedside table' in name_lower or 'bedside' in name_lower:
            return 'Nightstand'

        # Sofa seater variations - categorize by seating capacity
        if 'sofa' in name_lower or 'seater' in name_lower or 'couch' in name_lower:
            if 'three seater' in name_lower or '3 seater' in name_lower or 'three-seater' in name_lower or '3-seater' in name_lower:
                return 'Three Seater Sofa'
            elif 'two seater' in name_lower or '2 seater' in name_lower or 'two-seater' in name_lower or '2-seater' in name_lower:
                return 'Two Seater Sofa'
            elif 'single seater' in name_lower or '1 seater' in name_lower or 'one seater' in name_lower or 'single-seater' in name_lower or '1-seater' in name_lower or 'one-seater' in name_lower:
                return 'Single Seater Sofa'
            elif 'sectional' in name_lower:
                return 'Sectional Sofa'
            elif 'sofa' in name_lower or 'couch' in name_lower:
                return 'Sofa'

        # Armchair detection
        if 'armchair' in name_lower or 'arm chair' in name_lower:
            return 'Armchair'

        # Lounge chair detection
        if 'lounge' in name_lower and 'chair' in name_lower:
            return 'Lounge Chair'

        # Accent chair detection
        if 'accent' in name_lower and 'chair' in name_lower:
            return 'Accent Chair'

        # Dining chair detection
        if 'dining' in name_lower and 'chair' in name_lower:
            return 'Dining Chair'

        # Office chair detection
        if 'office' in name_lower and 'chair' in name_lower:
            return 'Office Chair'

        # Study chair detection
        if 'study' in name_lower and 'chair' in name_lower:
            return 'Study Chair'

        # Rocking chair detection
        if 'rocking' in name_lower and 'chair' in name_lower:
            return 'Rocking Chair'

        # Recliner detection
        if 'recliner' in name_lower:
            return 'Recliner'

        # Generic chair
        if 'chair' in name_lower:
            return 'Chair'

        # Bench detection
        if 'bench' in name_lower:
            return 'Bench'

        # Stool detection
        if 'stool' in name_lower:
            return 'Stool'

        # Bed detection
        if 'bed' in name_lower:
            if 'king' in name_lower:
                return 'King Bed'
            elif 'queen' in name_lower:
                return 'Queen Bed'
            elif 'single' in name_lower or 'twin' in name_lower:
                return 'Single Bed'
            elif 'double' in name_lower:
                return 'Double Bed'
            return 'Bed'

        # Wardrobe / Closet detection
        if 'wardrobe' in name_lower or 'closet' in name_lower or 'armoire' in name_lower:
            return 'Wardrobe'

        # Dresser detection
        if 'dresser' in name_lower:
            return 'Dresser'

        # Chest of drawers
        if 'chest' in name_lower and 'drawer' in name_lower:
            return 'Chest of Drawers'

        # Bookshelf / Shelves detection
        if 'bookshelf' in name_lower or 'book shelf' in name_lower or 'bookcase' in name_lower:
            return 'Bookshelf'
        if 'shelf' in name_lower or 'shelves' in name_lower or 'shelving' in name_lower:
            return 'Shelves'

        # TV Unit / Media console
        if 'tv unit' in name_lower or 'tv stand' in name_lower or 'media console' in name_lower or 'entertainment' in name_lower:
            return 'TV Unit'

        # Sideboard / Buffet
        if 'sideboard' in name_lower or 'buffet' in name_lower:
            return 'Sideboard'

        # Storage / Cabinet detection
        if 'cabinet' in name_lower:
            return 'Cabinet'
        if 'storage' in name_lower:
            return 'Storage'

        # Study table detection (before desk to catch "study table" specifically)
        if 'study table' in name_lower or 'study desk' in name_lower:
            return 'Study Table'

        # Desk detection
        if 'desk' in name_lower:
            return 'Desk'

        # Lamp detection
        if 'lamp' in name_lower or 'light' in name_lower:
            if 'floor lamp' in name_lower or 'floor light' in name_lower:
                return 'Floor Lamp'
            elif 'table lamp' in name_lower or 'desk lamp' in name_lower:
                return 'Table Lamp'
            elif 'pendant' in name_lower:
                return 'Pendant Lamp'
            elif 'wall lamp' in name_lower or 'sconce' in name_lower or 'wall light' in name_lower:
                return 'Wall Lamp'
            elif 'chandelier' in name_lower:
                return 'Chandelier'
            elif 'ceiling' in name_lower:
                return 'Ceiling Light'
            elif 'lamp' in name_lower:
                return 'Lamp'

        # Mirror detection
        if 'mirror' in name_lower:
            return 'Mirror'

        # Wall Art detection (before generic decor)
        if any(term in name_lower for term in ['wall art', 'canvas art', 'painting', 'wall painting', 'canvas painting', 'art print', 'wall hanging', 'metal wall', 'wall plate']):
            return 'Wall Art'

        # Sculpture / Showpiece detection
        if any(term in name_lower for term in ['sculpture', 'showpiece', 'figurine', 'statue', 'idol']):
            return 'Sculpture'

        # Rug / Carpet detection
        if 'rug' in name_lower or 'carpet' in name_lower or 'dhurrie' in name_lower or 'runner' in name_lower:
            return 'Rugs'

        # Planter detection
        if 'planter' in name_lower or 'plant pot' in name_lower or 'flower pot' in name_lower or 'plant stand' in name_lower:
            return 'Planter'

        # Vase detection
        if 'vase' in name_lower:
            return 'Vase'

        # Clock detection
        if 'clock' in name_lower:
            return 'Clock'

        # Divider detection
        if 'divider' in name_lower or ('screen' in name_lower and 'room' in name_lower):
            return 'Room Divider'

        # Curtain detection
        if 'curtain' in name_lower or 'drape' in name_lower:
            return 'Curtain'

        # Cushion / Pillow detection
        if 'cushion' in name_lower or 'pillow' in name_lower:
            return 'Cushion'

        # Throw / Blanket detection
        if 'throw' in name_lower or 'blanket' in name_lower:
            return 'Throw'

        # Photo Frame detection
        if 'photo frame' in name_lower or 'picture frame' in name_lower:
            return 'Photo Frame'

        # Candle / Candle Holder detection
        if 'candle' in name_lower:
            return 'Decor & Accessories'

        # Decorative items
        if any(term in name_lower for term in ['decorative', 'decor', 'tray', 'bowl', 'bookend']):
            return 'Decor & Accessories'

        # Table (generic) - after all specific table types
        if 'table' in name_lower:
            return 'Table'

        # Return fallback category if no specific match
        return fallback_category or 'Furniture'

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

    def extract_sofa_alignment(self, product_name: str, description: str = None) -> Optional[str]:
        """
        Extract sofa alignment (left/right) from product name or description.

        This is relevant for sectional sofas, L-shaped sofas, and sofas with chaise.

        Args:
            product_name: The product's name/title
            description: Optional product description

        Returns:
            'left', 'right', 'reversible', or None
        """
        import re

        if not product_name:
            return None

        # Combine name and description for searching
        text = f"{product_name} {description or ''}".lower()

        # Check for reversible first (higher priority)
        reversible_patterns = [
            r'\breversible\b',
            r'\binterchangeable\b',
        ]
        for pattern in reversible_patterns:
            if re.search(pattern, text):
                return 'reversible'

        # Check for right alignment
        right_patterns = [
            r'\bright[\s-]*align',      # "right aligned", "right-aligned"
            r'\bright[\s-]*facing\b',   # "right facing"
            r'\bright[\s-]*arm\b',      # "right arm"
            r'\bright[\s-]*chaise\b',   # "right chaise"
            r'\brhs\b',                 # "RHS"
            r'\bright[\s-]*corner\b',   # "right corner"
            r'\bright[\s-]*hand\b',     # "right hand"
            r'\bright[\s-]*longchair\b',  # "right longchair"
            r'\bright[\s-]*sectional\b',  # "right sectional"
            r'\bright[\s-]*l[\s-]*shape', # "right L-shape"
            r'\bl[\s-]*shape[d]?[\s-]*right\b', # "L-shaped right"
        ]
        for pattern in right_patterns:
            if re.search(pattern, text):
                return 'right'

        # Check for left alignment
        left_patterns = [
            r'\bleft[\s-]*align',       # "left aligned", "left-aligned"
            r'\bleft[\s-]*facing\b',    # "left facing"
            r'\bleft[\s-]*arm\b',       # "left arm"
            r'\bleft[\s-]*chaise\b',    # "left chaise"
            r'\blhs\b',                 # "LHS"
            r'\bleft[\s-]*corner\b',    # "left corner"
            r'\bleft[\s-]*hand\b',      # "left hand"
            r'\bleft[\s-]*longchair\b', # "left longchair"
            r'\bleft[\s-]*sectional\b', # "left sectional"
            r'\bleft[\s-]*l[\s-]*shape', # "left L-shape"
            r'\bl[\s-]*shape[d]?[\s-]*left\b', # "L-shaped left"
        ]
        for pattern in left_patterns:
            if re.search(pattern, text):
                return 'left'

        return None

    def is_sectional_sofa(self, product_name: str, description: str = None) -> bool:
        """
        Check if a product is a sectional/L-shape sofa.

        Args:
            product_name: The product's name/title
            description: Optional product description

        Returns:
            True if the product is a sectional sofa
        """
        import re

        text = f"{product_name} {description or ''}".lower()

        sectional_patterns = [
            r'\bl[\s-]*shape',          # "L-shape", "L shape"
            r'\bsectional\b',           # "sectional"
            r'\bcorner\s+sofa\b',       # "corner sofa"
            r'\bmodular\s+sofa\b',      # "modular sofa"
            r'\bchaise\b',              # has chaise
        ]

        # Must also be a sofa
        is_sofa = bool(re.search(r'\bsofa\b|\bcouch\b|\bsettee\b', text))

        if not is_sofa:
            return False

        for pattern in sectional_patterns:
            if re.search(pattern, text):
                return True

        return False

    def extract_alignment_from_specifications(self, attributes: Dict[str, str]) -> Optional[str]:
        """
        Extract sofa alignment from product specifications/attributes.

        Looks for common specification keys like 'configuration', 'orientation',
        'chaise position', 'arm position', etc.

        Args:
            attributes: Product attributes dict from specifications

        Returns:
            'left', 'right', 'reversible', or None
        """
        import re

        if not attributes:
            return None

        # Keys that might contain alignment info
        alignment_keys = [
            'configuration', 'orientation', 'chaise_position', 'chaise position',
            'arm_position', 'arm position', 'facing', 'direction', 'type',
            'sofa_type', 'sofa type', 'shape', 'layout', 'seating_configuration',
            'seating configuration', 'corner_type', 'corner type', 'aligned'
        ]

        for key in attributes:
            key_lower = key.lower()
            # Check if this key might contain alignment info
            if any(ak in key_lower for ak in alignment_keys) or 'align' in key_lower or 'facing' in key_lower:
                value = attributes[key].lower()

                # Check for reversible
                if 'reversible' in value or 'interchangeable' in value:
                    return 'reversible'

                # Check for right
                if re.search(r'\bright\b', value):
                    return 'right'

                # Check for left
                if re.search(r'\bleft\b', value):
                    return 'left'

        return None

    def enrich_attributes_with_alignment(
        self,
        attributes: Dict[str, str],
        product_name: str,
        description: str = None
    ) -> Dict[str, str]:
        """
        Enrich product attributes with sofa alignment if applicable.

        Checks multiple sources in order of priority:
        1. Product name (most reliable)
        2. Product specifications/attributes
        3. Product description

        Args:
            attributes: Existing product attributes dict (from specifications)
            product_name: The product's name/title
            description: Optional product description

        Returns:
            Updated attributes dict with sofa_alignment if applicable
        """
        if self.is_sectional_sofa(product_name, description):
            # Try extracting from name first (most reliable)
            alignment = self.extract_sofa_alignment(product_name, None)

            # If not found in name, try specifications
            if not alignment:
                alignment = self.extract_alignment_from_specifications(attributes)

            # If still not found, try description
            if not alignment and description:
                alignment = self.extract_sofa_alignment(product_name, description)

            if alignment:
                attributes['sofa_alignment'] = alignment

        return attributes
