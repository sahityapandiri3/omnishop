"""
Stores API routes for store/source management
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from database.models import Product

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stores", tags=["stores"])


class StoresResponse(BaseModel):
    """Response model for stores list"""

    stores: List[str]


class CacheWarmResponse(BaseModel):
    """Response model for cache warming"""

    success: bool
    message: str
    stores: List[str]


# Module-level cache for stores
_stores_cache: Optional[List[str]] = None
_cache_timestamp: Optional[datetime] = None
_cache_ttl = timedelta(hours=24)  # Cache for 24 hours after deployment


async def _fetch_stores_from_db(db: AsyncSession) -> List[str]:
    """
    Fetch stores from database
    Internal function used by both the main endpoint and cache warming
    """
    logger.info("Fetching stores from database")

    # Query for distinct source_website where products are available
    query = select(Product.source_website).where(Product.is_available == True).distinct()  # noqa: E712

    result = await db.execute(query)
    stores = [row[0] for row in result.fetchall() if row[0]]  # Filter out None values

    # Sort alphabetically for consistent ordering
    stores_sorted = sorted(stores)

    logger.info(f"Found {len(stores_sorted)} available stores: {stores_sorted}")
    return stores_sorted


def _is_cache_valid() -> bool:
    """Check if the cache is valid (not expired)"""
    if _stores_cache is None or _cache_timestamp is None:
        return False

    age = datetime.now() - _cache_timestamp
    return age < _cache_ttl


@router.get("", response_model=StoresResponse)
async def get_available_stores(db: AsyncSession = Depends(get_db)):
    """
    Get list of unique stores that have available products
    Returns stores sorted alphabetically

    This endpoint uses a 24-hour cache to improve performance.
    The cache can be warmed after deployment using the /warm-cache endpoint.
    """
    global _stores_cache, _cache_timestamp

    try:
        # Check if cache is valid
        if _is_cache_valid():
            logger.info(f"Returning cached stores (cached at {_cache_timestamp})")
            return StoresResponse(stores=_stores_cache)

        # Cache miss or expired - fetch from database
        logger.info("Cache miss or expired, fetching from database")
        stores_sorted = await _fetch_stores_from_db(db)

        # Update cache
        _stores_cache = stores_sorted
        _cache_timestamp = datetime.now()

        return StoresResponse(stores=stores_sorted)

    except Exception as e:
        logger.error(f"Error fetching available stores: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch stores: {str(e)}")


@router.post("/warm-cache", response_model=CacheWarmResponse)
async def warm_stores_cache(db: AsyncSession = Depends(get_db)):
    """
    Warm the stores cache by fetching and caching the store list

    This endpoint should be called after each deployment to ensure the cache
    is populated with fresh data. This prevents the first user request from
    experiencing the database query delay.

    Returns:
        - success: Whether the cache warming was successful
        - message: Status message
        - stores: The list of stores that were cached
    """
    global _stores_cache, _cache_timestamp

    try:
        logger.info("Warming stores cache...")

        # Fetch stores from database
        stores_sorted = await _fetch_stores_from_db(db)

        # Update cache
        _stores_cache = stores_sorted
        _cache_timestamp = datetime.now()

        logger.info(f"✅ Cache warmed successfully with {len(stores_sorted)} stores")

        return CacheWarmResponse(
            success=True,
            message=f"Cache warmed successfully with {len(stores_sorted)} stores at {_cache_timestamp}",
            stores=stores_sorted,
        )

    except Exception as e:
        logger.error(f"Error warming stores cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to warm cache: {str(e)}")
