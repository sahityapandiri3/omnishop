"""
Backfill product embeddings using Google text-embedding-004.

This script processes products in batches, generating vector embeddings
for semantic search using the embedding service.

Features:
- Batch processing (configurable batch size)
- Checkpoint for resume capability
- Progress tracking and statistics
- Rate limiting to avoid API throttling

Usage:
    python scripts/backfill_embeddings.py [--batch-size 100] [--resume] [--limit 1000]
"""
import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.config import settings
from database.models import Product, ProductAttribute, Category
from services.embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("backfill_embeddings.log")
    ]
)
logger = logging.getLogger(__name__)

# Checkpoint file for resume capability
CHECKPOINT_FILE = Path(__file__).parent / ".embedding_backfill_checkpoint.json"


class EmbeddingBackfillProcessor:
    """Processes products for embedding generation."""

    def __init__(
        self,
        database_url: str,
        batch_size: int = 100,
        rate_limit_delay: float = 0.5
    ):
        self.database_url = database_url
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay

        # Initialize database
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)

        # Initialize embedding service
        self.embedding_service = EmbeddingService()

        # Statistics
        self.stats = {
            "total_processed": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "last_processed_id": 0
        }

    def load_checkpoint(self) -> Optional[Dict]:
        """Load checkpoint from file."""
        if CHECKPOINT_FILE.exists():
            try:
                with open(CHECKPOINT_FILE, "r") as f:
                    checkpoint = json.load(f)
                logger.info(
                    f"Loaded checkpoint: last_id={checkpoint.get('last_processed_id')}, "
                    f"processed={checkpoint.get('total_processed')}"
                )
                return checkpoint
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
        return None

    def save_checkpoint(self):
        """Save current progress to checkpoint file."""
        try:
            checkpoint = {
                "last_processed_id": self.stats["last_processed_id"],
                "total_processed": self.stats["total_processed"],
                "success": self.stats["success"],
                "failed": self.stats["failed"],
                "skipped": self.stats["skipped"],
                "timestamp": datetime.now().isoformat()
            }
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump(checkpoint, f, indent=2)
            logger.debug(f"Saved checkpoint at product_id={self.stats['last_processed_id']}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def clear_checkpoint(self):
        """Remove checkpoint file."""
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
            logger.info("Checkpoint cleared")

    def get_products_to_process(
        self,
        session,
        start_id: int = 0,
        limit: Optional[int] = None,
        regenerate: bool = False
    ) -> List[Product]:
        """Get products that need embedding generation."""
        query = session.query(Product).filter(Product.id > start_id)

        if not regenerate:
            # Only products without embeddings
            query = query.filter(Product.embedding.is_(None))

        query = query.order_by(Product.id)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_category_name(self, session, category_id: int) -> Optional[str]:
        """Get category name by ID."""
        if not category_id:
            return None
        category = session.query(Category).filter(Category.id == category_id).first()
        return category.name if category else None

    def get_product_attributes(self, session, product_id: int) -> Dict[str, str]:
        """Get product attributes as a dictionary."""
        attributes = (
            session.query(ProductAttribute)
            .filter(ProductAttribute.product_id == product_id)
            .all()
        )
        return {attr.attribute_name: attr.attribute_value for attr in attributes}

    async def process_product(self, session, product: Product) -> bool:
        """
        Process a single product for embedding generation.

        Returns True if successful, False otherwise.
        """
        try:
            # Get category name
            category_name = self.get_category_name(session, product.category_id)

            # Get attributes
            attributes = self.get_product_attributes(session, product.id)

            # Build embedding text
            embedding_text = self.embedding_service.build_product_embedding_text(
                product,
                category_name=category_name,
                attributes=attributes
            )

            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(
                embedding_text,
                task_type="RETRIEVAL_DOCUMENT"
            )

            if embedding:
                # Store as JSON string
                product.embedding = json.dumps(embedding)
                product.embedding_text = embedding_text
                product.embedding_updated_at = datetime.utcnow()

                self.stats["success"] += 1
                logger.debug(f"Product {product.id}: Generated embedding ({len(embedding)} dims)")
                return True
            else:
                self.stats["failed"] += 1
                logger.warning(f"Product {product.id}: No embedding returned")
                return False

        except Exception as e:
            logger.error(f"Error processing product {product.id}: {e}")
            self.stats["failed"] += 1
            return False

    async def process_batch(self, product_ids: List[int]) -> int:
        """
        Process a batch of products by ID.

        Returns number of successfully processed products.
        """
        session = self.Session()
        successful = 0

        try:
            # Re-fetch products in THIS session so changes will be tracked
            products = session.query(Product).filter(Product.id.in_(product_ids)).all()

            for product in products:
                success = await self.process_product(session, product)

                if success:
                    successful += 1

                self.stats["total_processed"] += 1
                self.stats["last_processed_id"] = product.id

                # Rate limiting between API calls
                await asyncio.sleep(self.rate_limit_delay)

            # Commit batch
            session.commit()
            logger.info(
                f"Batch committed: {successful}/{len(products)} successful, "
                f"total processed: {self.stats['total_processed']}"
            )

            # Save checkpoint after each batch
            self.save_checkpoint()

        except Exception as e:
            session.rollback()
            logger.error(f"Batch processing error: {e}")
            raise
        finally:
            session.close()

        return successful

    async def run(
        self,
        resume: bool = False,
        limit: Optional[int] = None,
        regenerate: bool = False
    ):
        """
        Run the backfill process.

        Args:
            resume: If True, resume from last checkpoint
            limit: Maximum number of products to process
            regenerate: If True, regenerate embeddings for all products
        """
        self.stats["start_time"] = time.time()

        # Load checkpoint if resuming
        start_id = 0
        if resume:
            checkpoint = self.load_checkpoint()
            if checkpoint:
                start_id = checkpoint.get("last_processed_id", 0)
                self.stats["total_processed"] = checkpoint.get("total_processed", 0)
                self.stats["success"] = checkpoint.get("success", 0)
                self.stats["failed"] = checkpoint.get("failed", 0)
                self.stats["skipped"] = checkpoint.get("skipped", 0)
                logger.info(f"Resuming from product ID {start_id}")

        # Get product IDs to process (not full objects)
        session = self.Session()
        try:
            products = self.get_products_to_process(session, start_id, limit, regenerate)
            product_ids = [p.id for p in products]  # Extract IDs only
            total_products = len(product_ids)
            logger.info(f"Found {total_products} products to process")
        finally:
            session.close()

        if total_products == 0:
            logger.info("No products need embedding generation")
            return

        # Process in batches using IDs
        for i in range(0, total_products, self.batch_size):
            batch_ids = product_ids[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_products + self.batch_size - 1) // self.batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_ids)} products)")

            await self.process_batch(batch_ids)

            # Progress report
            elapsed = time.time() - self.stats["start_time"]
            rate = self.stats["total_processed"] / elapsed if elapsed > 0 else 0
            remaining = total_products - (i + len(batch_ids))
            eta = remaining / rate if rate > 0 else 0

            logger.info(
                f"Progress: {self.stats['total_processed']}/{total_products} "
                f"({100 * self.stats['total_processed'] / total_products:.1f}%) | "
                f"Rate: {rate:.1f}/s | ETA: {eta/60:.1f} min"
            )

        # Final report
        self._print_summary()

        # Clear checkpoint on successful completion
        if not limit:  # Only clear if we processed all
            self.clear_checkpoint()

    def _print_summary(self):
        """Print final processing summary."""
        elapsed = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0

        print("\n" + "=" * 60)
        print("EMBEDDING BACKFILL COMPLETE")
        print("=" * 60)
        print(f"Total processed:    {self.stats['total_processed']}")
        print(f"Success:            {self.stats['success']}")
        print(f"Failed:             {self.stats['failed']}")
        print(f"Skipped:            {self.stats['skipped']}")
        print(f"Time elapsed:       {elapsed/60:.1f} minutes")
        print(f"Average rate:       {self.stats['total_processed']/elapsed:.2f}/sec" if elapsed > 0 else "N/A")
        print("=" * 60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill product embeddings using Google text-embedding-004"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of products to process per batch (default: 100)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of products to process"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.5,
        help="Delay in seconds between API calls (default: 0.5)"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL (default: from settings)"
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate embeddings even for products that already have them"
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Clear existing checkpoint and start fresh"
    )

    args = parser.parse_args()

    # Get database URL
    database_url = args.database_url or settings.database_url
    if not database_url:
        logger.error("No database URL configured")
        sys.exit(1)

    # Check for Google AI API key
    if not settings.google_ai_api_key:
        logger.error("GOOGLE_AI_API_KEY not configured")
        sys.exit(1)

    logger.info(f"Database: {database_url[:50]}...")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Rate limit: {args.rate_limit}s delay")
    if args.regenerate:
        logger.info("Regeneration mode: will update existing embeddings")

    # Create processor
    processor = EmbeddingBackfillProcessor(
        database_url=database_url,
        batch_size=args.batch_size,
        rate_limit_delay=args.rate_limit
    )

    # Clear checkpoint if requested
    if args.clear_checkpoint:
        processor.clear_checkpoint()

    # Run backfill
    try:
        await processor.run(
            resume=args.resume,
            limit=args.limit,
            regenerate=args.regenerate
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Progress saved to checkpoint.")
        processor.save_checkpoint()
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        processor.save_checkpoint()
        raise


if __name__ == "__main__":
    asyncio.run(main())
