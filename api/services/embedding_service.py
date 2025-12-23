"""
Embedding service for semantic search using Google text-embedding-004.

This service generates vector embeddings for products and user queries,
enabling semantic similarity search in product recommendations.
"""
import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import settings
from database.models import Product, ProductAttribute, Category

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing product embeddings."""

    # Embedding model configuration
    MODEL_NAME = "text-embedding-004"
    EMBEDDING_DIMENSION = 768

    # Caching configuration
    QUERY_CACHE_TTL = 3600  # 1 hour TTL for query cache
    MAX_CACHE_SIZE = 1000  # Maximum cached queries

    # Rate limiting
    BATCH_SIZE = 100
    RATE_LIMIT_DELAY = 0.5  # seconds between batches

    def __init__(self):
        """Initialize the embedding service."""
        self.client = None
        self._query_cache: Dict[str, Dict[str, Any]] = {}
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Google Generative AI client."""
        if settings.google_ai_api_key:
            self.client = genai.Client(api_key=settings.google_ai_api_key)
            logger.info("EmbeddingService initialized with Google AI client")
        else:
            logger.warning("Google AI API key not configured - embedding service disabled")

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> Optional[List[float]]:
        """
        Generate embedding for text using Google text-embedding-004.

        Args:
            text: The text to embed
            task_type: Either "RETRIEVAL_DOCUMENT" for products or "RETRIEVAL_QUERY" for queries

        Returns:
            List of 768 floats representing the embedding, or None on error
        """
        if not self.client:
            logger.error("Embedding client not initialized")
            return None

        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None

        try:
            # Truncate text if too long (model limit is ~8000 tokens)
            truncated_text = text[:8000] if len(text) > 8000 else text

            result = self.client.models.embed_content(
                model=self.MODEL_NAME,
                contents=truncated_text,
                config={
                    "task_type": task_type,
                    "output_dimensionality": self.EMBEDDING_DIMENSION
                }
            )

            if result and result.embeddings:
                embedding = result.embeddings[0].values
                logger.debug(f"Generated embedding with {len(embedding)} dimensions")
                return list(embedding)

            logger.warning("No embedding returned from API")
            return None

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    async def get_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Get embedding for user query with caching.

        Args:
            query: User's search query

        Returns:
            List of floats representing the query embedding
        """
        # Normalize query for cache key
        normalized_query = query.lower().strip()
        cache_key = hashlib.md5(normalized_query.encode()).hexdigest()

        # Check cache
        if cache_key in self._query_cache:
            cached = self._query_cache[cache_key]
            if time.time() - cached['timestamp'] < self.QUERY_CACHE_TTL:
                logger.debug(f"Query embedding cache hit for: {query[:50]}...")
                return cached['embedding']

        # Generate new embedding
        embedding = await self.generate_embedding(query, task_type="RETRIEVAL_QUERY")

        if embedding:
            # Cache the result
            self._query_cache[cache_key] = {
                'embedding': embedding,
                'timestamp': time.time()
            }

            # Prune cache if too large
            if len(self._query_cache) > self.MAX_CACHE_SIZE:
                self._prune_cache()

        return embedding

    def _prune_cache(self):
        """Remove oldest entries from cache."""
        if len(self._query_cache) <= self.MAX_CACHE_SIZE:
            return

        # Sort by timestamp and remove oldest 20%
        sorted_keys = sorted(
            self._query_cache.keys(),
            key=lambda k: self._query_cache[k]['timestamp']
        )
        keys_to_remove = sorted_keys[:int(len(sorted_keys) * 0.2)]

        for key in keys_to_remove:
            del self._query_cache[key]

        logger.info(f"Pruned {len(keys_to_remove)} entries from query cache")

    def build_product_embedding_text(
        self,
        product: Product,
        category_name: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Build the text representation of a product for embedding.

        Args:
            product: The Product model instance
            category_name: Optional category name
            attributes: Optional dict of attribute name -> value

        Returns:
            Concatenated text for embedding
        """
        parts = []

        # Product name (most important)
        if product.name:
            parts.append(product.name)

        # Description
        if product.description:
            # Truncate long descriptions
            desc = product.description[:1000] if len(product.description) > 1000 else product.description
            parts.append(desc)

        # Category
        if category_name:
            parts.append(f"Category: {category_name}")

        # Style
        if product.primary_style:
            style_text = f"Style: {product.primary_style}"
            if product.secondary_style:
                style_text += f", {product.secondary_style}"
            parts.append(style_text)

        # Attributes (colors, materials, etc.)
        if attributes:
            attr_parts = []
            if 'color_primary' in attributes:
                attr_parts.append(f"Color: {attributes['color_primary']}")
            if 'color_secondary' in attributes:
                attr_parts.append(f"Secondary color: {attributes['color_secondary']}")
            if 'material_primary' in attributes:
                attr_parts.append(f"Material: {attributes['material_primary']}")
            if 'material_secondary' in attributes:
                attr_parts.append(f"Secondary material: {attributes['material_secondary']}")
            if 'texture' in attributes:
                attr_parts.append(f"Texture: {attributes['texture']}")
            if 'pattern' in attributes:
                attr_parts.append(f"Pattern: {attributes['pattern']}")

            if attr_parts:
                parts.append(" | ".join(attr_parts))

        # Brand
        if product.brand:
            parts.append(f"Brand: {product.brand}")

        return "\n".join(parts)

    async def generate_product_embedding(
        self,
        product: Product,
        db: AsyncSession
    ) -> Optional[Tuple[List[float], str]]:
        """
        Generate embedding for a single product.

        Args:
            product: The Product model instance
            db: Database session for fetching related data

        Returns:
            Tuple of (embedding, embedding_text) or None on error
        """
        try:
            # Get category name
            category_name = None
            if product.category_id:
                result = await db.execute(
                    select(Category.name).where(Category.id == product.category_id)
                )
                category_row = result.first()
                if category_row:
                    category_name = category_row[0]

            # Get attributes
            result = await db.execute(
                select(ProductAttribute).where(ProductAttribute.product_id == product.id)
            )
            attributes_rows = result.scalars().all()
            attributes = {attr.attribute_name: attr.attribute_value for attr in attributes_rows}

            # Build embedding text
            embedding_text = self.build_product_embedding_text(
                product,
                category_name=category_name,
                attributes=attributes
            )

            # Generate embedding
            embedding = await self.generate_embedding(embedding_text, task_type="RETRIEVAL_DOCUMENT")

            if embedding:
                return (embedding, embedding_text)

            return None

        except Exception as e:
            logger.error(f"Error generating embedding for product {product.id}: {e}")
            return None

    async def batch_generate_embeddings(
        self,
        product_ids: List[int],
        db: AsyncSession,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, int]:
        """
        Generate embeddings for multiple products in batches.

        Args:
            product_ids: List of product IDs to process
            db: Database session
            progress_callback: Optional callback(processed, total) for progress updates

        Returns:
            Dict with stats: {"processed": N, "success": N, "failed": N}
        """
        stats = {"processed": 0, "success": 0, "failed": 0}
        total = len(product_ids)

        for i in range(0, total, self.BATCH_SIZE):
            batch_ids = product_ids[i:i + self.BATCH_SIZE]

            # Fetch products
            result = await db.execute(
                select(Product).where(Product.id.in_(batch_ids))
            )
            products = result.scalars().all()

            for product in products:
                try:
                    result = await self.generate_product_embedding(product, db)

                    if result:
                        embedding, embedding_text = result

                        # Update product with embedding
                        product.embedding = json.dumps(embedding)
                        product.embedding_text = embedding_text
                        product.embedding_updated_at = datetime.utcnow()

                        stats["success"] += 1
                    else:
                        stats["failed"] += 1

                except Exception as e:
                    logger.error(f"Error processing product {product.id}: {e}")
                    stats["failed"] += 1

                stats["processed"] += 1

                if progress_callback:
                    progress_callback(stats["processed"], total)

            # Commit batch
            await db.commit()

            # Rate limiting
            if i + self.BATCH_SIZE < total:
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        logger.info(f"Batch embedding complete: {stats}")
        return stats

    async def update_product_embedding(
        self,
        product_id: int,
        db: AsyncSession
    ) -> bool:
        """
        Update embedding for a single product (e.g., after attribute change).

        Args:
            product_id: The product ID to update
            db: Database session

        Returns:
            True if successful, False otherwise
        """
        try:
            result = await db.execute(
                select(Product).where(Product.id == product_id)
            )
            product = result.scalar_one_or_none()

            if not product:
                logger.warning(f"Product {product_id} not found")
                return False

            result = await self.generate_product_embedding(product, db)

            if result:
                embedding, embedding_text = result
                product.embedding = json.dumps(embedding)
                product.embedding_text = embedding_text
                product.embedding_updated_at = datetime.utcnow()
                await db.commit()
                logger.info(f"Updated embedding for product {product_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating embedding for product {product_id}: {e}")
            return False

    def compute_cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have same dimension")

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def warm_cache(self, common_queries: List[str]):
        """
        Pre-warm the query cache with common queries.

        Args:
            common_queries: List of queries to pre-cache
        """
        logger.info(f"Warming query cache with {len(common_queries)} queries")

        for query in common_queries:
            await self.get_query_embedding(query)
            await asyncio.sleep(0.1)  # Small delay to avoid rate limiting

        logger.info("Query cache warming complete")


# Common queries to pre-cache on startup
COMMON_QUERIES = [
    "modern sofa",
    "minimalist furniture",
    "comfortable couch",
    "wooden dining table",
    "scandinavian chair",
    "cozy living room",
    "elegant bedroom",
    "industrial decor",
    "bohemian rug",
    "luxury lighting",
]


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def initialize_embedding_service():
    """Initialize embedding service and warm cache on startup."""
    service = get_embedding_service()
    await service.warm_cache(COMMON_QUERIES)
