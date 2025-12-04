"""
Curated Styling API routes for AI-generated room looks
"""
import base64
import io
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from PIL import Image
from pydantic import BaseModel, Field
from services.curated_styling_service import curated_styling_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from database.models import CuratedLook as CuratedLookModel
from database.models import CuratedLookProduct, Product


# =============================================================================
# IN-MEMORY CACHE for curated looks (avoids re-processing thumbnails every request)
# =============================================================================
class CuratedLooksCache:
    """Simple in-memory cache with TTL for curated looks responses."""

    def __init__(self, ttl_seconds: int = 300):  # 5 minute default TTL
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None
        if time.time() - self._timestamps.get(key, 0) > self.ttl_seconds:
            # Expired - remove from cache
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
            return None
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """Set cache value with current timestamp."""
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate specific key or all keys if key is None."""
        if key is None:
            self._cache.clear()
            self._timestamps.clear()
        else:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)


# Global cache instance (5 minute TTL - balances freshness with performance)
_curated_looks_cache = CuratedLooksCache(ttl_seconds=300)


async def warm_curated_looks_cache(db_session_factory) -> None:
    """
    Warm up the curated looks cache at server startup.
    This pre-fetches and processes thumbnails so the first user request is instant.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    logger = logging.getLogger(__name__)
    logger.info("🔥 Warming up curated looks cache...")

    try:
        async with db_session_factory() as db:
            # Build query for published looks (same as get_curated_looks endpoint)
            query = (
                select(CuratedLookModel)
                .where(CuratedLookModel.is_published.is_(True))
                .options(
                    selectinload(CuratedLookModel.products)
                    .selectinload(CuratedLookProduct.product)
                    .selectinload(Product.images)
                )
                .order_by(CuratedLookModel.display_order.asc(), CuratedLookModel.created_at.desc())
            )

            result = await db.execute(query)
            looks_from_db = result.scalars().unique().all()

            logger.info(f"Found {len(looks_from_db)} published curated looks to cache")

            # Convert to response format and cache (same logic as endpoint)
            looks = []
            for look in looks_from_db:
                products = []
                for lp in sorted(look.products, key=lambda x: x.display_order or 0):
                    product = lp.product
                    if product:
                        products.append(
                            {
                                "id": product.id,
                                "name": product.name,
                                "price": product.price or 0,
                                "image_url": get_primary_image_url(product),
                                "source_website": product.source_website,
                                "source_url": product.source_url,
                                "product_type": lp.product_type or "",
                                "description": product.description,
                            }
                        )

                thumbnail = None
                if look.visualization_image:
                    thumbnail = create_thumbnail(look.visualization_image, max_width=400, quality=60)

                looks.append(
                    CuratedLook(
                        look_id=str(look.id),
                        style_theme=look.style_theme,
                        style_description=look.style_description or "",
                        room_image=None,  # Don't cache large images
                        visualization_image=thumbnail,
                        products=products,
                        total_price=look.total_price or 0,
                        generation_status="completed",
                        error_message=None,
                    )
                )

            # Determine room type for response
            response_room_type = looks_from_db[0].room_type if looks_from_db else "living_room"

            # Build and cache the default response (no room_type filter, include_images=False)
            response_data = {
                "session_id": "",
                "room_type": response_room_type,
                "looks": [look.model_dump() for look in looks],
                "generation_complete": True,
            }

            cache_key = "looks:all:False"
            _curated_looks_cache.set(cache_key, response_data)
            logger.info(f"✅ Curated looks cache warmed successfully (key: {cache_key}, {len(looks)} looks)")

    except Exception as e:
        logger.error(f"❌ Failed to warm curated looks cache: {e}", exc_info=True)


def create_thumbnail(base64_image: str, max_width: int = 400, quality: int = 60) -> str:
    """Create a compressed thumbnail from a base64 image."""
    try:
        # Decode base64
        image_data = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_data))

        # Calculate new size maintaining aspect ratio
        width, height = image.size
        if width > max_width:
            ratio = max_width / width
            new_size = (max_width, int(height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to RGB if necessary (for JPEG)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Save as compressed JPEG
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to create thumbnail: {e}")
        return base64_image  # Return original if compression fails


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/curated", tags=["curated"])


# Request/Response Models
class CuratedLooksRequest(BaseModel):
    """Request for generating curated looks"""

    room_image: str = Field(..., description="Base64-encoded room image")
    selected_stores: List[str] = Field(
        default_factory=list, description="List of store names to filter products (empty = all stores)"
    )
    num_looks: int = Field(default=3, ge=1, le=5, description="Number of looks to generate")


class ProductInLook(BaseModel):
    """Product included in a curated look"""

    id: int
    name: str
    price: float
    image_url: Optional[str] = None
    source_website: str
    source_url: Optional[str] = None
    product_type: str


class CuratedLook(BaseModel):
    """A single curated look with products and visualization"""

    look_id: str
    style_theme: str
    style_description: str
    room_image: Optional[str] = None  # Base room image (furniture removed)
    visualization_image: Optional[str] = None
    products: List[Dict[str, Any]] = Field(default_factory=list)
    total_price: float = 0.0
    generation_status: str = "pending"
    error_message: Optional[str] = None


class CuratedLooksResponse(BaseModel):
    """Response containing generated curated looks"""

    session_id: str
    room_type: str
    looks: List[CuratedLook] = Field(default_factory=list)
    generation_complete: bool = False


@router.post("/generate", response_model=CuratedLooksResponse)
async def generate_curated_looks(request: CuratedLooksRequest, db: AsyncSession = Depends(get_db)):
    """
    Generate AI-curated room looks based on uploaded room image.

    This endpoint:
    1. Analyzes the room image to detect room type
    2. Generates 3 distinct style themes using AI
    3. Selects products that match each theme
    4. Creates visualizations showing products in the room

    Returns a list of curated looks, each with:
    - Style theme name and description
    - Selected products with prices
    - Visualization image showing products in room
    """
    try:
        logger.info(f"Generating curated looks - stores: {request.selected_stores}, num_looks: {request.num_looks}")

        # Validate room image
        if not request.room_image:
            raise HTTPException(status_code=400, detail="Room image is required")

        # Handle base64 prefix if present
        room_image = request.room_image
        if room_image.startswith("data:image"):
            room_image = room_image.split(",", 1)[1] if "," in room_image else room_image

        # Generate curated looks
        result = await curated_styling_service.generate_curated_looks(
            room_image=room_image, selected_stores=request.selected_stores, db=db, num_looks=request.num_looks
        )

        # Convert to response model
        looks = []
        for look in result.looks:
            looks.append(
                CuratedLook(
                    look_id=look.look_id,
                    style_theme=look.style_theme,
                    style_description=look.style_description,
                    visualization_image=look.visualization_image,
                    products=look.products,
                    total_price=look.total_price,
                    generation_status=look.generation_status,
                    error_message=look.error_message,
                )
            )

        return CuratedLooksResponse(
            session_id=result.session_id,
            room_type=result.room_type,
            looks=looks,
            generation_complete=result.generation_complete,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating curated looks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate curated looks: {str(e)}")


@router.get("/health")
async def curated_health_check():
    """Health check for curated styling service"""
    return {"status": "healthy", "service": "curated_styling", "version": "1.0.0"}


def get_primary_image_url(product: Product) -> Optional[str]:
    """Get the primary image URL for a product"""
    if not product.images:
        return None
    primary = next((img for img in product.images if img.is_primary), None)
    if primary:
        return primary.original_url
    return product.images[0].original_url if product.images else None


@router.get("/looks", response_model=CuratedLooksResponse)
async def get_curated_looks(
    room_type: Optional[str] = Query(None, description="Filter by room type (living_room, bedroom)"),
    include_images: bool = Query(False, description="Include large base64 images (room_image, visualization_image)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get pre-curated room looks from the database.

    This endpoint returns published, pre-curated looks that were created by the admin.
    These are ready-to-use looks that load instantly (no AI generation needed).

    Returns a list of curated looks, each with:
    - Style theme name and description
    - Selected products with prices
    - Visualization image showing products in room

    NOTE: Response is cached for 5 minutes to avoid re-processing thumbnails.
    """
    try:
        # Build cache key based on query parameters
        cache_key = f"looks:{room_type or 'all'}:{include_images}"

        # Check cache first
        cached_response = _curated_looks_cache.get(cache_key)
        if cached_response:
            logger.info(f"Cache HIT for curated looks (key: {cache_key})")
            # Return cached response with new session ID
            cached_response["session_id"] = str(uuid.uuid4())
            return CuratedLooksResponse(**cached_response)

        logger.info(f"Cache MISS - Fetching curated looks from DB (room_type: {room_type})")
        start_time = time.time()

        # Build query for published looks
        query = (
            select(CuratedLookModel)
            .where(CuratedLookModel.is_published.is_(True))
            .options(
                selectinload(CuratedLookModel.products).selectinload(CuratedLookProduct.product).selectinload(Product.images)
            )
            .order_by(CuratedLookModel.display_order.asc(), CuratedLookModel.created_at.desc())
        )

        # Apply room type filter if provided
        if room_type:
            query = query.where(CuratedLookModel.room_type == room_type)

        result = await db.execute(query)
        looks_from_db = result.scalars().unique().all()

        db_time = time.time() - start_time
        logger.info(f"Found {len(looks_from_db)} published curated looks (DB query: {db_time:.3f}s)")

        # Convert to response format
        looks = []
        thumbnail_start = time.time()
        for look in looks_from_db:
            # Build product list
            products = []
            for lp in sorted(look.products, key=lambda x: x.display_order or 0):
                product = lp.product
                if product:
                    products.append(
                        {
                            "id": product.id,
                            "name": product.name,
                            "price": product.price or 0,
                            "image_url": get_primary_image_url(product),
                            "source_website": product.source_website,
                            "source_url": product.source_url,
                            "product_type": lp.product_type or "",
                            "description": product.description,
                        }
                    )

            # Create thumbnail for listing (compressed version) or use full image
            visualization = None
            if look.visualization_image:
                if include_images:
                    # Return full-quality image for landing page / detail views
                    visualization = look.visualization_image
                else:
                    # Return compressed thumbnail for listing/grid views
                    visualization = create_thumbnail(look.visualization_image, max_width=400, quality=60)

            looks.append(
                CuratedLook(
                    look_id=str(look.id),
                    style_theme=look.style_theme,
                    style_description=look.style_description or "",
                    room_image=look.room_image if include_images else None,
                    visualization_image=visualization,  # Full image or thumbnail based on include_images
                    products=products,
                    total_price=look.total_price or 0,
                    generation_status="completed",
                    error_message=None,
                )
            )

        thumbnail_time = time.time() - thumbnail_start
        logger.info(f"Thumbnail generation took {thumbnail_time:.3f}s for {len(looks)} looks")

        # Determine room type for response (use first look's room type or default)
        response_room_type = room_type or (looks_from_db[0].room_type if looks_from_db else "living_room")

        # Build response data for caching (without session_id)
        response_data = {
            "session_id": "",  # Placeholder, will be replaced on each request
            "room_type": response_room_type,
            "looks": [look.model_dump() for look in looks],
            "generation_complete": True,
        }

        # Cache the response
        _curated_looks_cache.set(cache_key, response_data)
        total_time = time.time() - start_time
        logger.info(f"Cached curated looks response (total: {total_time:.3f}s, key: {cache_key})")

        # Return with fresh session ID
        response_data["session_id"] = str(uuid.uuid4())
        return CuratedLooksResponse(**response_data)

    except Exception as e:
        logger.error(f"Error fetching curated looks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch curated looks: {str(e)}")


@router.get("/looks/{look_id}", response_model=CuratedLook)
async def get_curated_look_by_id(
    look_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single curated look by ID with full images.

    Use this endpoint when user clicks "Use Style" to get the visualization images.
    """
    try:
        logger.info(f"Fetching curated look ID: {look_id}")

        query = (
            select(CuratedLookModel)
            .where(CuratedLookModel.id == look_id)
            .where(CuratedLookModel.is_published.is_(True))
            .options(
                selectinload(CuratedLookModel.products).selectinload(CuratedLookProduct.product).selectinload(Product.images)
            )
        )

        result = await db.execute(query)
        look = result.scalars().first()

        if not look:
            raise HTTPException(status_code=404, detail=f"Curated look {look_id} not found")

        # Build product list
        products = []
        for lp in sorted(look.products, key=lambda x: x.display_order or 0):
            product = lp.product
            if product:
                products.append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price or 0,
                        "image_url": get_primary_image_url(product),
                        "source_website": product.source_website,
                        "source_url": product.source_url,
                        "product_type": lp.product_type or "",
                        "description": product.description,
                    }
                )

        return CuratedLook(
            look_id=str(look.id),
            style_theme=look.style_theme,
            style_description=look.style_description or "",
            room_image=look.room_image,
            visualization_image=look.visualization_image,
            products=products,
            total_price=look.total_price or 0,
            generation_status="completed",
            error_message=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch curated look: {str(e)}")
