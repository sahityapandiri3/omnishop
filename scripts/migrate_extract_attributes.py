"""
Migration Script: Extract Attributes from Existing Products

This script processes all products in the database and extracts attributes
(color, material, style, dimensions, etc.) using the AttributeExtractionService.

Features:
- Batch processing with configurable batch size
- Progress tracking and resume capability
- Error logging and reporting
- Rate limiting for API calls
- Dry-run mode for testing
- Statistics generation

Usage:
    # Dry run on 10 products
    python scripts/migrate_extract_attributes.py --dry-run --limit 10

    # Full migration
    python scripts/migrate_extract_attributes.py --batch-size 50

    # Resume from last checkpoint
    python scripts/migrate_extract_attributes.py --resume

    # Retry failed products
    python scripts/migrate_extract_attributes.py --retry-failed
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import csv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload

from database.models import Product, ProductImage, ProductAttribute
from api.services.google_ai_service import google_ai_service
from api.services.attribute_extraction_service import AttributeExtractionService

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/attribute_extraction_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# State file for checkpointing
STATE_FILE = Path(__file__).parent.parent / "migration_state.json"
ERRORS_FILE = Path(__file__).parent.parent / "migration_errors.csv"


class MigrationState:
    """Track migration progress"""

    def __init__(self):
        self.last_processed_product_id = 0
        self.total_processed = 0
        self.successful = 0
        self.failed = 0
        self.start_time = None
        self.estimated_completion = None

    def load(self):
        """Load state from file"""
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                self.last_processed_product_id = data.get('last_processed_product_id', 0)
                self.total_processed = data.get('total_processed', 0)
                self.successful = data.get('successful', 0)
                self.failed = data.get('failed', 0)
                self.start_time = data.get('start_time')
            logger.info(f"Loaded state: {self.total_processed} products processed, "
                       f"last ID: {self.last_processed_product_id}")

    def save(self):
        """Save state to file"""
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'last_processed_product_id': self.last_processed_product_id,
                'total_processed': self.total_processed,
                'successful': self.successful,
                'failed': self.failed,
                'start_time': self.start_time,
                'estimated_completion': self.estimated_completion
            }, f, indent=2)

    def reset(self):
        """Reset state"""
        self.last_processed_product_id = 0
        self.total_processed = 0
        self.successful = 0
        self.failed = 0
        self.start_time = None
        if STATE_FILE.exists():
            STATE_FILE.unlink()


class ErrorLogger:
    """Log failed products to CSV"""

    def __init__(self):
        self.errors = []

    def log_error(self, product_id: int, product_name: str, error_type: str, error_message: str):
        """Log an error"""
        self.errors.append({
            'product_id': product_id,
            'product_name': product_name,
            'error_type': error_type,
            'error_message': error_message,
            'timestamp': datetime.now().isoformat()
        })

    def save(self):
        """Save errors to CSV"""
        if not self.errors:
            return

        with open(ERRORS_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['product_id', 'product_name', 'error_type', 'error_message', 'timestamp'])
            writer.writeheader()
            writer.writerows(self.errors)

        logger.info(f"Saved {len(self.errors)} errors to {ERRORS_FILE}")


async def get_products_to_process(
    db: AsyncSession,
    batch_size: int,
    offset: int = 0,
    retry_failed: bool = False
) -> List[Product]:
    """
    Get batch of products to process

    Args:
        db: Database session
        batch_size: Number of products to fetch
        offset: Starting product ID (for resume)
        retry_failed: Whether to retry products that failed previously

    Returns:
        List of Product objects with images loaded
    """
    query = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.is_available == True)
    )

    if offset > 0:
        query = query.where(Product.id > offset)

    if not retry_failed:
        # Exclude products that already have attributes
        # (unless we're retrying failed ones)
        subquery = (
            select(ProductAttribute.product_id)
            .where(ProductAttribute.attribute_name == 'furniture_type')
        )
        query = query.where(~Product.id.in_(subquery))

    query = query.order_by(Product.id).limit(batch_size)

    result = await db.execute(query)
    return result.scalars().all()


async def process_product(
    product: Product,
    extraction_service: AttributeExtractionService,
    db: AsyncSession,
    error_logger: ErrorLogger
) -> bool:
    """
    Process a single product

    Args:
        product: Product to process
        extraction_service: AttributeExtractionService instance
        db: Database session
        error_logger: ErrorLogger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get first product image
        image_url = None
        if product.images:
            primary_image = next((img for img in product.images if img.is_primary), None)
            if not primary_image and product.images:
                primary_image = product.images[0]
            if primary_image:
                image_url = primary_image.original_url

        # Extract attributes
        result = await extraction_service.extract_attributes(
            product_id=product.id,
            image_url=image_url,
            product_name=product.name,
            product_description=product.description
        )

        if not result.success:
            error_logger.log_error(
                product.id,
                product.name,
                'extraction_failed',
                result.error_message or 'Unknown error'
            )
            return False

        # Store attributes
        stored_count = await extraction_service.store_attributes(
            product.id,
            result,
            db
        )

        logger.info(f"✓ Product {product.id} '{product.name[:50]}': "
                   f"{stored_count} attributes, "
                   f"confidence={result.confidence_scores.get('overall', 0):.2f}")
        return True

    except Exception as e:
        logger.error(f"✗ Product {product.id} '{product.name[:50]}': {e}")
        error_logger.log_error(
            product.id,
            product.name,
            'exception',
            str(e)
        )
        return False


async def run_migration(
    batch_size: int = 50,
    limit: int = None,
    dry_run: bool = False,
    resume: bool = False,
    retry_failed: bool = False
):
    """
    Run the migration

    Args:
        batch_size: Number of products to process per batch
        limit: Maximum number of products to process (for testing)
        dry_run: If True, don't commit changes
        resume: If True, resume from last checkpoint
        retry_failed: If True, retry products that failed previously
    """
    # Initialize state
    state = MigrationState()
    if resume:
        state.load()
    else:
        state.reset()

    state.start_time = datetime.now().isoformat()
    error_logger = ErrorLogger()

    # Database setup
    from api.core.config import settings
    engine = create_async_engine(
        settings.database_url.replace('postgresql://', 'postgresql+asyncpg://'),
        echo=False
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize services
    if not google_ai_service.api_key:
        logger.error("Google AI API key not configured!")
        return

    extraction_service = AttributeExtractionService(google_ai_service)

    # Get total product count
    async with async_session() as db:
        total_query = select(func.count(Product.id)).where(Product.is_available == True)
        if state.last_processed_product_id > 0:
            total_query = total_query.where(Product.id > state.last_processed_product_id)

        result = await db.execute(total_query)
        total_products = result.scalar()

    logger.info("="*80)
    logger.info("ATTRIBUTE EXTRACTION MIGRATION")
    logger.info("="*80)
    logger.info(f"Total products to process: {total_products}")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Resume: {resume}")
    logger.info(f"Retry failed: {retry_failed}")
    if limit:
        logger.info(f"Limit: {limit} products")
    logger.info("="*80)
    logger.info("")

    # Process in batches
    processed_count = 0
    offset = state.last_processed_product_id

    while True:
        async with async_session() as db:
            # Get batch
            products = await get_products_to_process(
                db, batch_size, offset, retry_failed
            )

            if not products:
                logger.info("No more products to process")
                break

            logger.info(f"\nProcessing batch: {len(products)} products "
                       f"(starting from ID {products[0].id})")

            # Process each product
            batch_successful = 0
            batch_failed = 0

            for product in products:
                success = await process_product(
                    product,
                    extraction_service,
                    db,
                    error_logger
                )

                if success:
                    batch_successful += 1
                    state.successful += 1
                else:
                    batch_failed += 1
                    state.failed += 1

                state.total_processed += 1
                state.last_processed_product_id = product.id
                processed_count += 1

                # Rate limiting: 30 requests/min for Gemini free tier
                await asyncio.sleep(2)  # 2 seconds between products = 30/min

                # Save checkpoint every 100 products
                if state.total_processed % 100 == 0:
                    if not dry_run:
                        state.save()
                    logger.info(f"Checkpoint: {state.total_processed} products processed")

                # Check limit
                if limit and processed_count >= limit:
                    logger.info(f"Reached limit of {limit} products")
                    break

            logger.info(f"Batch complete: {batch_successful} successful, {batch_failed} failed")

            # Commit or rollback
            if dry_run:
                logger.info("Dry run - rolling back changes")
                await db.rollback()
            else:
                await db.commit()

            # Update offset for next batch
            offset = state.last_processed_product_id

            # Check limit
            if limit and processed_count >= limit:
                break

    # Save final state
    if not dry_run:
        state.save()
        error_logger.save()

    # Generate report
    logger.info("")
    logger.info("="*80)
    logger.info("MIGRATION COMPLETE")
    logger.info("="*80)
    logger.info(f"Total products processed: {state.total_processed}")
    logger.info(f"Successful: {state.successful} ({state.successful/max(state.total_processed,1)*100:.1f}%)")
    logger.info(f"Failed: {state.failed} ({state.failed/max(state.total_processed,1)*100:.1f}%)")
    logger.info(f"Success rate: {state.successful/max(state.total_processed,1)*100:.1f}%")

    if state.failed > 0:
        logger.info(f"Error log saved to: {ERRORS_FILE}")

    if dry_run:
        logger.info("\n⚠️  DRY RUN - No changes were committed to database")

    logger.info("="*80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Extract attributes from existing products using Gemini AI'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Number of products to process per batch (default: 50)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of products to process (for testing)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without committing changes (for testing)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last checkpoint'
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='Retry products that failed previously'
    )

    args = parser.parse_args()

    # Run migration
    asyncio.run(run_migration(
        batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run,
        resume=args.resume,
        retry_failed=args.retry_failed
    ))


if __name__ == '__main__':
    main()
