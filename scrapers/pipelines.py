"""
Scrapy pipelines for processing scraped data
"""
import os
import hashlib
from urllib.parse import urlparse
from datetime import datetime
from typing import Optional
import logging

import scrapy
from scrapy.pipelines.images import ImagesPipeline
from scrapy.exceptions import DropItem
from itemadapter import ItemAdapter
from PIL import Image
import requests

from database.connection import get_db_session
from database.models import Product, ProductImage, ProductAttribute, Category, ScrapingStatus
from config.settings import settings
from .items import ProductItem, CategoryItem

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """Validate scraped items before processing"""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if isinstance(item, ProductItem):
            # Required fields validation (price is optional for enquiry-based pricing)
            required_fields = ['name', 'source_url', 'source_website']
            for field in required_fields:
                if not adapter.get(field):
                    raise DropItem(f"Missing required field: {field} in {adapter.get('source_url', 'unknown')}")

            # Price validation (if price exists, it must be valid)
            price = adapter.get('price')
            if price is not None and (price <= 0 or price > 1000000):
                raise DropItem(f"Invalid price: {price} for item {adapter.get('name', 'unknown')}")

            # URL validation
            source_url = adapter.get('source_url')
            if source_url and not source_url.startswith(('http://', 'https://')):
                raise DropItem(f"Invalid source URL: {source_url}")

        return item


class DuplicatesPipeline:
    """Filter out duplicate items based on source URL and external ID"""

    def __init__(self):
        self.seen_items = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        if isinstance(item, ProductItem):
            # Create unique identifier
            source_website = adapter.get('source_website')
            external_id = adapter.get('external_id')
            source_url = adapter.get('source_url')

            # Use external_id if available, otherwise use URL
            identifier = f"{source_website}:{external_id}" if external_id else source_url

            if identifier in self.seen_items:
                raise DropItem(f"Duplicate item found: {identifier}")
            else:
                self.seen_items.add(identifier)

        return item


class CustomImagesPipeline(ImagesPipeline):
    """Custom images pipeline with resizing and optimization"""

    def __init__(self, store_uri, download_func=None, settings=None):
        super().__init__(store_uri, download_func, settings)
        # Access settings the Scrapy way or use defaults
        self.thumbnail_size = (150, 150)
        self.medium_size = (400, 400)
        self.large_size = (800, 800)

    def get_media_requests(self, item, info):
        """Get image download requests"""
        adapter = ItemAdapter(item)
        urls = adapter.get('image_urls', [])

        for url in urls:
            yield scrapy.Request(
                url,
                meta={'item': item},
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )

    def item_completed(self, results, item, info):
        """Process downloaded images"""
        adapter = ItemAdapter(item)
        image_paths = []

        for success, result in results:
            if success:
                image_paths.append(result)
            else:
                logger.warning(f"Failed to download image: {result}")

        # Store image paths in item
        adapter['images'] = image_paths
        return item

    def file_path(self, request, response=None, info=None, *, item=None):
        """Generate file path for downloaded images"""
        url = request.url
        url_hash = hashlib.sha1(url.encode()).hexdigest()
        filename = url_hash + '.jpg'

        # Organize by source website
        adapter = ItemAdapter(item) if item else None
        source_website = adapter.get('source_website', 'unknown') if adapter else 'unknown'

        return f"{source_website}/{filename}"

    def convert_image(self, image, size=None):
        """Convert and resize image"""
        if size:
            image = image.convert('RGB')
            image.thumbnail(size, Image.LANCZOS)
        return image


class CategoryPipeline:
    """Process category items and create category hierarchy"""

    def process_item(self, item, spider):
        if isinstance(item, CategoryItem):
            adapter = ItemAdapter(item)

            with get_db_session() as session:
                # Check if category already exists
                existing_category = session.query(Category).filter_by(
                    slug=adapter.get('slug'),
                    name=adapter.get('name')
                ).first()

                if not existing_category:
                    # Create new category
                    category = Category(
                        name=adapter.get('name'),
                        slug=adapter.get('slug'),
                        description=adapter.get('description')
                    )

                    # Handle parent category
                    parent_name = adapter.get('parent_category')
                    if parent_name:
                        parent_category = session.query(Category).filter_by(
                            name=parent_name
                        ).first()
                        if parent_category:
                            category.parent_id = parent_category.id

                    session.add(category)
                    session.commit()
                    logger.info(f"Created category: {category.name}")

        return item


class AttributeExtractionPipeline:
    """Extract product attributes using Gemini AI"""

    def __init__(self):
        self.extraction_service = None
        self.items_processed = 0
        self.extractions_succeeded = 0
        self.extractions_failed = 0

    def open_spider(self, spider):
        """Initialize attribute extraction service"""
        try:
            from api.services.google_ai_service import google_ai_service
            from api.services.attribute_extraction_service import AttributeExtractionService

            self.extraction_service = AttributeExtractionService(google_ai_service)
            logger.info("AttributeExtractionPipeline initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AttributeExtractionPipeline: {e}")
            self.extraction_service = None

    def process_item(self, item, spider):
        """Extract attributes from product"""
        if not isinstance(item, ProductItem):
            return item

        if not self.extraction_service:
            logger.warning("Attribute extraction service not available, skipping extraction")
            return item

        adapter = ItemAdapter(item)
        self.items_processed += 1

        try:
            # Get product info
            product_name = adapter.get('name')
            product_description = adapter.get('description', '')
            image_urls = adapter.get('image_urls', [])
            first_image_url = image_urls[0] if image_urls else None

            # Extract attributes (synchronous call in Scrapy pipeline)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self.extraction_service.extract_attributes(
                        product_id=0,  # Not saved yet
                        image_url=first_image_url,
                        product_name=product_name,
                        product_description=product_description
                    )
                )
            finally:
                loop.close()

            if result.success:
                # Build attributes dict for DatabasePipeline
                attributes = {}

                if result.furniture_type:
                    attributes['furniture_type'] = result.furniture_type

                if result.colors:
                    if result.colors.get('primary'):
                        attributes['color_primary'] = result.colors['primary']
                    if result.colors.get('secondary'):
                        attributes['color_secondary'] = result.colors['secondary']
                    if result.colors.get('accent'):
                        attributes['color_accent'] = result.colors['accent']

                if result.materials:
                    if result.materials.get('primary'):
                        attributes['material_primary'] = result.materials['primary']
                    if result.materials.get('secondary'):
                        attributes['material_secondary'] = result.materials['secondary']

                if result.style:
                    attributes['style'] = result.style

                if result.dimensions:
                    if result.dimensions.get('width'):
                        attributes['width'] = str(result.dimensions['width'])
                    if result.dimensions.get('depth'):
                        attributes['depth'] = str(result.dimensions['depth'])
                    if result.dimensions.get('height'):
                        attributes['height'] = str(result.dimensions['height'])

                if result.texture:
                    attributes['texture'] = result.texture

                if result.pattern:
                    attributes['pattern'] = result.pattern

                # Add attributes to item
                adapter['attributes'] = attributes

                self.extractions_succeeded += 1
                logger.info(f"✓ Extracted {len(attributes)} attributes for '{product_name[:50]}' "
                           f"(confidence: {result.confidence_scores.get('overall', 0):.2f})")
            else:
                self.extractions_failed += 1
                logger.warning(f"✗ Attribute extraction failed for '{product_name[:50]}': {result.error_message}")

        except Exception as e:
            self.extractions_failed += 1
            logger.error(f"Error during attribute extraction for '{adapter.get('name', 'unknown')[:50]}': {e}")

        return item

    def close_spider(self, spider):
        """Log final statistics"""
        logger.info(f"AttributeExtractionPipeline finished. "
                   f"Items: {self.items_processed}, "
                   f"Succeeded: {self.extractions_succeeded}, "
                   f"Failed: {self.extractions_failed}, "
                   f"Success rate: {(self.extractions_succeeded/max(self.items_processed,1))*100:.1f}%")


class EmbeddingAndStylePipeline:
    """Generate embeddings and classify styles for products during scraping"""

    def __init__(self):
        self.embedding_service = None
        self.google_ai_service = None
        self.items_processed = 0
        self.embeddings_generated = 0
        self.styles_classified = 0
        self.errors = 0

    def open_spider(self, spider):
        """Initialize services"""
        try:
            # Import services
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

            from api.services.embedding_service import EmbeddingService
            from api.services.google_ai_service import GoogleAIStudioService

            self.embedding_service = EmbeddingService()
            self.google_ai_service = GoogleAIStudioService()
            logger.info("EmbeddingAndStylePipeline initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EmbeddingAndStylePipeline: {e}")

    def process_item(self, item, spider):
        """Generate embedding and classify style for product"""
        if not isinstance(item, ProductItem):
            return item

        adapter = ItemAdapter(item)
        self.items_processed += 1

        # Generate embedding
        try:
            embedding = self._generate_embedding(adapter)
            if embedding:
                adapter['embedding'] = embedding
                adapter['embedding_text'] = self._build_embedding_text(adapter)
                self.embeddings_generated += 1
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            self.errors += 1

        # Classify style
        try:
            primary_style, secondary_style, confidence = self._classify_style(adapter)
            if primary_style:
                adapter['primary_style'] = primary_style
                adapter['secondary_style'] = secondary_style
                adapter['style_confidence'] = confidence
                adapter['style_extraction_method'] = 'scraping_pipeline'
                self.styles_classified += 1
        except Exception as e:
            logger.error(f"Error classifying style: {e}")
            self.errors += 1

        return item

    def _build_embedding_text(self, adapter) -> str:
        """Build text for embedding generation"""
        parts = []

        # Product name (most important)
        name = adapter.get('name', '')
        if name:
            parts.append(f"Product: {name}")

        # Category
        category = adapter.get('category', '')
        if category:
            parts.append(f"Category: {category}")

        # Brand
        brand = adapter.get('brand', '')
        if brand:
            parts.append(f"Brand: {brand}")

        # Description (truncated)
        description = adapter.get('description', '')
        if description:
            # Truncate long descriptions
            desc_text = description[:500] if len(description) > 500 else description
            parts.append(f"Description: {desc_text}")

        # Extracted attributes (if available)
        attributes = adapter.get('attributes', {})
        if attributes:
            attr_parts = []
            if attributes.get('color_primary'):
                attr_parts.append(f"Color: {attributes['color_primary']}")
            if attributes.get('material_primary'):
                attr_parts.append(f"Material: {attributes['material_primary']}")
            if attributes.get('style'):
                attr_parts.append(f"Style: {attributes['style']}")
            if attr_parts:
                parts.append("Attributes: " + ", ".join(attr_parts))

        return " | ".join(parts)

    def _generate_embedding(self, adapter) -> Optional[list]:
        """Generate embedding vector for product"""
        if not self.embedding_service or not self.embedding_service.client:
            return None

        embedding_text = self._build_embedding_text(adapter)
        if not embedding_text:
            return None

        try:
            # Run async embedding generation in sync context
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                embedding = loop.run_until_complete(
                    self.embedding_service.generate_embedding(
                        text=embedding_text,
                        task_type="RETRIEVAL_DOCUMENT"
                    )
                )
                return embedding
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def _classify_style(self, adapter) -> tuple:
        """Classify product style using Gemini Vision or text"""
        if not self.google_ai_service:
            return None, None, None

        product_name = adapter.get('name', '')
        description = adapter.get('description', '')
        image_urls = adapter.get('image_urls', [])
        first_image = image_urls[0] if image_urls else None

        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Try vision-based classification first if image available
                if first_image:
                    result = loop.run_until_complete(
                        self._classify_with_vision(first_image, product_name, description)
                    )
                    if result[0]:
                        return result

                # Fallback to text-based classification
                result = loop.run_until_complete(
                    self._classify_with_text(product_name, description)
                )
                return result
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Style classification failed: {e}")
            return None, None, None

    async def _fetch_image_as_base64(self, image_url: str) -> Optional[str]:
        """Fetch image from URL and convert to base64"""
        import aiohttp
        import base64

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                async with session.get(image_url, headers=headers) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        return base64.b64encode(image_data).decode('utf-8')
                    else:
                        logger.debug(f"Failed to fetch image: {response.status}")
        except Exception as e:
            logger.debug(f"Error fetching image: {e}")

        return None

    async def _classify_with_vision(self, image_url: str, name: str, description: str) -> tuple:
        """Classify style using Gemini Vision API"""
        from api.config.style_definitions import PREDEFINED_STYLES, STYLE_DESCRIPTIONS

        # Fetch and convert image to base64
        image_base64 = await self._fetch_image_as_base64(image_url)
        if not image_base64:
            logger.debug(f"Could not fetch image from {image_url[:50]}...")
            return None, None, None

        style_list = "\n".join([f"- {s}: {STYLE_DESCRIPTIONS.get(s, '')}" for s in PREDEFINED_STYLES])

        prompt = f"""Analyze this furniture/home decor product image and classify its design style.

Product: {name}
Description: {description[:300] if description else 'N/A'}

Available styles:
{style_list}

Respond ONLY with valid JSON (no markdown, no explanation):
{{"primary_style": "style_name", "secondary_style": "style_name_or_null", "confidence": 0.8}}

Rules:
- Choose from ONLY the styles listed above
- Pick the most dominant style as primary_style
- If the product has elements of another style, include secondary_style, otherwise use null
- confidence should be 0.0-1.0"""

        try:
            # Use Gemini Vision to analyze the image
            response_text = await self.google_ai_service.analyze_image_with_prompt(
                image=image_base64,
                prompt=prompt
            )

            if response_text:
                # Parse JSON response
                import json
                import re
                # Extract JSON from response (handle potential markdown wrapping)
                response_text = response_text.strip()
                if response_text.startswith('```'):
                    # Remove markdown code block
                    response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
                    response_text = re.sub(r'\s*```$', '', response_text)

                json_match = re.search(r'\{[^}]+\}', response_text)
                if json_match:
                    data = json.loads(json_match.group())
                    primary = data.get('primary_style')
                    secondary = data.get('secondary_style')
                    confidence = data.get('confidence', 0.7)

                    # Validate styles
                    if primary and primary in PREDEFINED_STYLES:
                        if secondary and secondary not in PREDEFINED_STYLES:
                            secondary = None
                        logger.info(f"✓ Gemini Vision classified: {primary} (confidence: {confidence:.2f})")
                        return primary, secondary, confidence

        except Exception as e:
            logger.debug(f"Vision classification failed: {e}")

        return None, None, None

    async def _classify_with_text(self, name: str, description: str) -> tuple:
        """Classify style using text-based analysis"""
        from api.config.style_definitions import PREDEFINED_STYLES, STYLE_DESCRIPTIONS

        if not name:
            return None, None, None

        style_list = "\n".join([f"- {s}: {STYLE_DESCRIPTIONS.get(s, '')}" for s in PREDEFINED_STYLES])

        prompt = f"""Based on this product information, classify its design style.

Product Name: {name}
Description: {description[:500] if description else 'N/A'}

Available styles:
{style_list}

Respond in JSON format:
{{
    "primary_style": "style_name",
    "secondary_style": "style_name or null",
    "confidence": 0.0-1.0
}}

Choose from ONLY the styles listed above."""

        try:
            result = await self.google_ai_service.generate_content(prompt, max_tokens=200)

            if result:
                import json
                import re
                json_match = re.search(r'\{[^}]+\}', result)
                if json_match:
                    data = json.loads(json_match.group())
                    primary = data.get('primary_style')
                    secondary = data.get('secondary_style')
                    confidence = data.get('confidence', 0.5)

                    if primary and primary in PREDEFINED_STYLES:
                        if secondary and secondary not in PREDEFINED_STYLES:
                            secondary = None
                        return primary, secondary, confidence

        except Exception as e:
            logger.debug(f"Text classification failed: {e}")

        return None, None, None

    def close_spider(self, spider):
        """Log final statistics"""
        logger.info(
            f"EmbeddingAndStylePipeline finished. "
            f"Items: {self.items_processed}, "
            f"Embeddings: {self.embeddings_generated}, "
            f"Styles: {self.styles_classified}, "
            f"Errors: {self.errors}"
        )


class DatabasePipeline:
    """Save items to database"""

    def __init__(self):
        self.items_count = 0
        self.errors_count = 0

    def process_item(self, item, spider):
        if isinstance(item, ProductItem):
            try:
                self._save_product(item, spider)
                self.items_count += 1
                if self.items_count % 100 == 0:
                    logger.info(f"Processed {self.items_count} products")
            except Exception as e:
                self.errors_count += 1
                logger.error(f"Error saving product: {e}")
                # Don't drop item, just log error
        return item

    def _save_product(self, item, spider):
        """Save product to database"""
        adapter = ItemAdapter(item)

        with get_db_session() as session:
            # Check if product already exists
            existing_product = session.query(Product).filter_by(
                source_website=adapter.get('source_website'),
                external_id=adapter.get('external_id')
            ).first()

            if existing_product:
                # Update existing product
                product = existing_product
                product.last_updated = datetime.utcnow()
            else:
                # Create new product
                product = Product()
                product.scraped_at = datetime.utcnow()

            # Update product fields
            product.external_id = adapter.get('external_id')
            product.name = adapter.get('name')
            product.description = adapter.get('description')
            product.price = adapter.get('price')
            product.original_price = adapter.get('original_price')
            product.currency = adapter.get('currency', 'USD')
            product.brand = adapter.get('brand')
            product.model = adapter.get('model')
            product.sku = adapter.get('sku')
            product.source_website = adapter.get('source_website')
            product.source_url = adapter.get('source_url')
            product.is_available = adapter.get('is_available', True)
            product.is_on_sale = adapter.get('is_on_sale', False)
            product.stock_status = adapter.get('stock_status', 'in_stock')

            # Save embedding if generated
            embedding = adapter.get('embedding')
            if embedding:
                product.embedding = embedding
                product.embedding_text = adapter.get('embedding_text')
                product.embedding_updated_at = datetime.utcnow()

            # Save style classification if available
            primary_style = adapter.get('primary_style')
            if primary_style:
                product.primary_style = primary_style
                product.secondary_style = adapter.get('secondary_style')
                product.style_confidence = adapter.get('style_confidence')
                product.style_extraction_method = adapter.get('style_extraction_method', 'scraping_pipeline')

            # Handle category
            category_name = adapter.get('category')
            if category_name:
                category = session.query(Category).filter_by(name=category_name).first()
                if not category:
                    # Auto-create category if it doesn't exist
                    import re
                    slug = re.sub(r'[^\w\s-]', '', category_name.lower())
                    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
                    category = Category(
                        name=category_name,
                        slug=slug
                    )
                    session.add(category)
                    session.flush()  # Get the ID
                    logger.info(f"Auto-created category: {category_name}")
                product.category_id = category.id

            # Save product first to get ID
            if not existing_product:
                session.add(product)
                session.flush()  # Get the ID without committing

            # Handle images
            self._save_product_images(product, adapter, session)

            # Handle attributes
            self._save_product_attributes(product, adapter, session)

            session.commit()

    def _save_product_images(self, product, adapter, session):
        """Save product images"""
        # Try to get images from pipeline first, then from URLs
        images_data = adapter.get('images', [])
        image_urls = adapter.get('image_urls', [])

        # If we have processed images from ImagesPipeline, use those
        if images_data:
            for i, image_data in enumerate(images_data):
                # Check if image already exists
                existing_image = session.query(ProductImage).filter_by(
                    product_id=product.id,
                    original_url=image_data.get('url', '')
                ).first()

                if not existing_image:
                    image = ProductImage(
                        product_id=product.id,
                        original_url=image_data.get('url', ''),
                        thumbnail_url=image_data.get('thumbnail_url'),
                        medium_url=image_data.get('medium_url'),
                        large_url=image_data.get('large_url'),
                        display_order=i,
                        is_primary=(i == 0)  # First image is primary
                    )
                    session.add(image)
        # Otherwise use direct URLs from scraper
        elif image_urls:
            for i, url in enumerate(image_urls):
                # Check if image already exists
                existing_image = session.query(ProductImage).filter_by(
                    product_id=product.id,
                    original_url=url
                ).first()

                if not existing_image:
                    image = ProductImage(
                        product_id=product.id,
                        original_url=url,
                        display_order=i,
                        is_primary=(i == 0)  # First image is primary
                    )
                    session.add(image)

    def _save_product_attributes(self, product, adapter, session):
        """Save product attributes"""
        attributes = adapter.get('attributes', {})

        for attr_name, attr_value in attributes.items():
            if attr_value:
                # Check if attribute already exists
                existing_attr = session.query(ProductAttribute).filter_by(
                    product_id=product.id,
                    attribute_name=attr_name
                ).first()

                if not existing_attr:
                    attribute = ProductAttribute(
                        product_id=product.id,
                        attribute_name=attr_name,
                        attribute_value=str(attr_value)
                    )
                    session.add(attribute)
                else:
                    # Update existing attribute
                    existing_attr.attribute_value = str(attr_value)

    def close_spider(self, spider):
        """Log final statistics"""
        logger.info(f"DatabasePipeline finished. Items saved: {self.items_count}, Errors: {self.errors_count}")


class StatsPipeline:
    """Collect and log scraping statistics"""

    def __init__(self):
        self.start_time = datetime.utcnow()
        self.items_count = 0
        self.images_count = 0

    def process_item(self, item, spider):
        if isinstance(item, ProductItem):
            self.items_count += 1
            adapter = ItemAdapter(item)
            images = adapter.get('images', [])
            self.images_count += len(images)
        return item

    def close_spider(self, spider):
        """Log final statistics"""
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()

        stats = {
            'spider_name': spider.name,
            'items_scraped': self.items_count,
            'images_downloaded': self.images_count,
            'duration_seconds': duration,
            'items_per_second': self.items_count / duration if duration > 0 else 0
        }

        logger.info(f"Scraping completed: {stats}")

        # Save stats to database
        try:
            with get_db_session() as session:
                from database.models import ScrapingLog
                log_entry = ScrapingLog(
                    website=spider.allowed_domains[0] if spider.allowed_domains else 'unknown',
                    spider_name=spider.name,
                    started_at=self.start_time,
                    finished_at=end_time,
                    duration_seconds=int(duration),
                    status=ScrapingStatus.SUCCESS,
                    products_found=self.items_count,
                    products_processed=self.items_count,
                    products_saved=self.items_count,  # Assuming all were saved
                    images_downloaded=self.images_count
                )
                session.add(log_entry)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to save scraping log: {e}")
