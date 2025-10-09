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
            # Required fields validation
            required_fields = ['name', 'price', 'source_url', 'source_website']
            for field in required_fields:
                if not adapter.get(field):
                    raise DropItem(f"Missing required field: {field} in {adapter.get('source_url', 'unknown')}")

            # Price validation
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

            # Handle category
            category_name = adapter.get('category')
            if category_name:
                category = session.query(Category).filter_by(name=category_name).first()
                if category:
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