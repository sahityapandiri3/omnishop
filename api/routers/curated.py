"""
Curated Styling API routes for AI-generated room looks
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from services.curated_styling_service import curated_styling_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from database.models import CuratedLook as CuratedLookModel
from database.models import CuratedLookProduct, Product

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
    """
    try:
        logger.info(f"Fetching curated looks - room_type filter: {room_type}")

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

        logger.info(f"Found {len(looks_from_db)} published curated looks")

        # Convert to response format
        looks = []
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

            looks.append(
                CuratedLook(
                    look_id=str(look.id),
                    style_theme=look.style_theme,
                    style_description=look.style_description or "",
                    room_image=look.room_image,  # Include base room image
                    visualization_image=look.visualization_image,
                    products=products,
                    total_price=look.total_price or 0,
                    generation_status="completed",
                    error_message=None,
                )
            )

        # Generate a session ID for this request
        session_id = str(uuid.uuid4())

        # Determine room type for response (use first look's room type or default)
        response_room_type = room_type or (looks_from_db[0].room_type if looks_from_db else "living_room")

        return CuratedLooksResponse(session_id=session_id, room_type=response_room_type, looks=looks, generation_complete=True)

    except Exception as e:
        logger.error(f"Error fetching curated looks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch curated looks: {str(e)}")
