"""
Stores API routes for store/source management
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from database.models import Product, Store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stores", tags=["stores"])


class StoreInfo(BaseModel):
    """Store information with display name and tier"""

    name: str
    display_name: str
    budget_tier: Optional[str] = None


class StoreCategory(BaseModel):
    """A category of stores grouped by budget tier"""

    tier: str
    label: str
    stores: List[StoreInfo]


class StoresResponse(BaseModel):
    """Response model for stores list"""

    stores: List[str]


class CategorizedStoresResponse(BaseModel):
    """Response model for categorized stores"""

    categories: List[StoreCategory]
    all_stores: List[StoreInfo]


class CacheWarmResponse(BaseModel):
    """Response model for cache warming"""

    success: bool
    message: str
    stores: List[str]


# Module-level cache for stores
_stores_cache: Optional[List[str]] = None
_categorized_cache: Optional[CategorizedStoresResponse] = None
_cache_timestamp: Optional[datetime] = None
_cache_ttl = timedelta(hours=24)  # Cache for 24 hours after deployment

# Budget tier display labels and order
TIER_CONFIG = {
    "pocket_friendly": {"label": "Pocket Friendly", "order": 1},
    "mid_tier": {"label": "Mid-Range", "order": 2},
    "premium": {"label": "Premium", "order": 3},
    "luxury": {"label": "Luxury", "order": 4},
}


async def _fetch_stores_from_db(db: AsyncSession) -> List[str]:
    """
    Fetch stores from database
    Internal function used by both the main endpoint and cache warming
    Tries stores table first, falls back to products table if not available
    """
    logger.info("Fetching stores from database")

    # First, try to get stores from stores table
    try:
        # Check if stores table exists
        check_result = await db.execute(
            text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'stores')")
        )
        table_exists = check_result.scalar()

        if table_exists:
            # Query from stores table
            query = select(Store.name).where(Store.is_active == True).order_by(Store.name)  # noqa: E712
            result = await db.execute(query)
            stores = [row[0] for row in result.fetchall() if row[0]]

            if stores:
                logger.info(f"Found {len(stores)} stores from stores table: {stores}")
                return stores

    except Exception as e:
        logger.warning(f"Could not query stores table, falling back to products: {e}")

    # Fallback: Query for distinct source_website where products are available
    query = select(Product.source_website).where(Product.is_available == True).distinct()  # noqa: E712

    result = await db.execute(query)
    stores = [row[0] for row in result.fetchall() if row[0]]  # Filter out None values

    # Sort alphabetically for consistent ordering
    stores_sorted = sorted(stores)

    logger.info(f"Found {len(stores_sorted)} available stores from products: {stores_sorted}")
    return stores_sorted


async def _fetch_categorized_stores_from_db(db: AsyncSession) -> CategorizedStoresResponse:
    """
    Fetch stores from database with budget tier categorization.
    Returns stores grouped by category.
    """
    logger.info("Fetching categorized stores from database")

    # Get all active stores with their tier info
    query = select(Store).where(Store.is_active == True).order_by(Store.budget_tier, Store.display_name)  # noqa: E712
    result = await db.execute(query)
    stores = result.scalars().all()

    # Group stores by tier
    tier_groups: Dict[str, List[StoreInfo]] = {}
    all_stores: List[StoreInfo] = []

    for store in stores:
        store_info = StoreInfo(
            name=store.name,
            display_name=store.display_name or store.name.replace("_", " ").title(),
            budget_tier=store.budget_tier.value if store.budget_tier else None,
        )
        all_stores.append(store_info)

        tier_key = store.budget_tier.value if store.budget_tier else "other"
        if tier_key not in tier_groups:
            tier_groups[tier_key] = []
        tier_groups[tier_key].append(store_info)

    # Build categories in order
    categories: List[StoreCategory] = []
    for tier_key, config in sorted(TIER_CONFIG.items(), key=lambda x: x[1]["order"]):
        if tier_key in tier_groups:
            categories.append(
                StoreCategory(tier=tier_key, label=config["label"], stores=tier_groups[tier_key])
            )

    # Add "Other" category for uncategorized stores
    if "other" in tier_groups:
        categories.append(StoreCategory(tier="other", label="Other", stores=tier_groups["other"]))

    logger.info(f"Found {len(all_stores)} stores in {len(categories)} categories")
    return CategorizedStoresResponse(categories=categories, all_stores=all_stores)


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


@router.get("/categorized", response_model=CategorizedStoresResponse)
async def get_categorized_stores(db: AsyncSession = Depends(get_db)):
    """
    Get stores grouped by budget tier category.

    Returns stores organized into categories:
    - Pocket Friendly: Budget-friendly stores
    - Mid-Range: Mid-tier stores
    - Premium: Premium/luxury stores

    Uses 24-hour caching for performance.
    """
    global _categorized_cache, _cache_timestamp

    try:
        # Check if cache is valid
        if _is_cache_valid() and _categorized_cache is not None:
            logger.info(f"Returning cached categorized stores (cached at {_cache_timestamp})")
            return _categorized_cache

        # Cache miss or expired - fetch from database
        logger.info("Cache miss or expired, fetching categorized stores from database")
        categorized = await _fetch_categorized_stores_from_db(db)

        # Update cache
        _categorized_cache = categorized
        _cache_timestamp = datetime.now()

        return categorized

    except Exception as e:
        logger.error(f"Error fetching categorized stores: {e}", exc_info=True)
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
