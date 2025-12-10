"""
Admin API routes for managing curated looks
"""
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.curated import (
    CuratedLookCreate,
    CuratedLookListResponse,
    CuratedLookProductSchema,
    CuratedLookProductUpdate,
    CuratedLookSchema,
    CuratedLookSummarySchema,
    CuratedLookUpdate,
)
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from database.models import Category, CuratedLook, CuratedLookProduct, Product

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/curated", tags=["admin-curated"])

# Synonym dictionary for search terms - maps search term to list of synonyms
SEARCH_SYNONYMS = {
    "carpet": ["rug", "carpet", "runner", "mat", "floor covering"],
    "rug": ["rug", "carpet", "runner", "mat", "floor covering"],
    "sofa": ["sofa", "couch", "settee"],
    "sofas": ["sofa", "couch", "settee"],
    "couch": ["sofa", "couch", "settee"],
    "couches": ["sofa", "couch", "settee"],
    "cupboard": ["cupboard", "cabinet", "wardrobe", "armoire"],
    "cabinet": ["cupboard", "cabinet", "wardrobe", "armoire"],
    "lamp": ["lamp", "floor lamp", "standing lamp", "table lamp"],
    "lamps": ["lamp", "floor lamp", "standing lamp", "table lamp"],
    "floor lamp": ["floor lamp", "standing lamp", "lamp"],
    "standing lamp": ["standing lamp", "floor lamp", "lamp"],
    "table lamp": ["table lamp", "desk lamp", "lamp"],
    "light": ["light", "lighting", "chandelier", "pendant light"],
    "lights": ["light", "lighting", "chandelier", "pendant light"],
    "chandelier": ["chandelier", "pendant light", "ceiling light"],
    "table": ["table", "desk"],
    "tables": ["table", "desk"],
    "desk": ["table", "desk"],
    "desks": ["table", "desk"],
    "chair": ["chair", "seat", "seating"],
    "chairs": ["chair", "seat", "seating"],
    "curtain": ["curtain", "drape", "drapes", "blind", "blinds"],
    "curtains": ["curtain", "drape", "drapes", "blind", "blinds"],
    "drape": ["curtain", "drape", "drapes"],
    "drapes": ["curtain", "drape", "drapes"],
    # Bedroom furniture - handle plurals
    "bed": ["bed", "bedframe", "bed frame"],
    "beds": ["bed", "bedframe", "bed frame"],
    "bedside table": ["bedside table", "nightstand", "night stand", "bedside"],
    "bedside tables": ["bedside table", "nightstand", "night stand", "bedside"],
    "nightstand": ["nightstand", "bedside table", "night stand", "bedside"],
    "nightstands": ["nightstand", "bedside table", "night stand", "bedside"],
    # Planters and pots
    "planter": ["planter", "pot", "plant pot", "flower pot"],
    "planters": ["planter", "pot", "plant pot", "flower pot"],
    "pot": ["pot", "planter", "plant pot", "flower pot"],
    "pots": ["pot", "planter", "plant pot", "flower pot"],
}


def expand_search_query(query: str) -> list:
    """Expand a search query to include synonyms"""
    query_lower = query.lower().strip()
    # Check if the query matches any synonym key
    for key, synonyms in SEARCH_SYNONYMS.items():
        if key in query_lower or query_lower in key:
            return synonyms
    # Return original query if no synonyms found
    return [query]


def get_primary_image_url(product: Product) -> Optional[str]:
    """Get the primary image URL for a product"""
    if not product.images:
        return None
    primary = next((img for img in product.images if img.is_primary), None)
    if primary:
        return primary.original_url
    return product.images[0].original_url if product.images else None


# NOTE: These routes MUST be defined BEFORE the /{look_id} route
# otherwise FastAPI will try to match "categories" or "search" as a look_id


@router.get("/categories")
async def get_product_categories(db: AsyncSession = Depends(get_db)):
    """Get all product categories for filtering"""
    try:
        # Get categories that have products
        query = select(Category).order_by(Category.name)
        result = await db.execute(query)
        categories = result.scalars().all()

        return {"categories": [{"id": c.id, "name": c.name, "slug": c.slug} for c in categories]}

    except Exception as e:
        logger.error(f"Error fetching categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching categories")


@router.get("/search/products")
async def search_products_for_look(
    query: Optional[str] = Query(None, min_length=1),
    category_id: Optional[int] = Query(None),
    source_website: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    colors: Optional[str] = Query(None, description="Comma-separated list of colors"),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Search for products to add to a curated look. Can search by text query or filter by category."""
    try:
        # Build search query
        search_query = select(Product).options(selectinload(Product.images)).where(Product.is_available.is_(True))

        # Apply text search if query provided (with synonym expansion for name only)
        if query:
            search_terms = expand_search_query(query)
            logger.info(f"Search query '{query}' expanded to: {search_terms}")

            # Build search conditions using word boundaries for accurate matching
            # This prevents "bed" from matching "bedspread", "bedding", etc.
            name_conditions = []
            for term in search_terms:
                escaped_term = re.escape(term)
                # Use PostgreSQL regex with word boundaries (\y) for accurate matching
                name_conditions.append(Product.name.op("~*")(rf"\y{escaped_term}\y"))

            # Also match original query in brand and description with word boundaries
            escaped_query = re.escape(query)
            original_query_conditions = [
                Product.brand.op("~*")(rf"\y{escaped_query}\y"),
                Product.description.op("~*")(rf"\y{escaped_query}\y"),
            ]

            # Combine: (synonym matches in name) OR (original query in brand/description)
            all_conditions = name_conditions + original_query_conditions
            if all_conditions:
                search_query = search_query.where(or_(*all_conditions))

        # Filter by category if specified
        if category_id:
            search_query = search_query.where(Product.category_id == category_id)

        # Filter by store if specified
        if source_website:
            search_query = search_query.where(Product.source_website == source_website)

        # Filter by price range
        if min_price is not None:
            search_query = search_query.where(Product.price >= min_price)
        if max_price is not None:
            search_query = search_query.where(Product.price <= max_price)

        # Filter by colors (search in name, description, color field)
        if colors:
            color_list = [c.strip().lower() for c in colors.split(",")]
            color_conditions = []
            for color in color_list:
                color_conditions.append(or_(Product.name.ilike(f"%{color}%"), Product.description.ilike(f"%{color}%")))
            if color_conditions:
                search_query = search_query.where(or_(*color_conditions))

        # Order by: exact match priority (if searching), then price
        # This ensures "bedside table" shows bedside tables first, not random matches
        if query:
            escaped_query = re.escape(query)
            # Case expression to prioritize exact matches in name
            exact_match_priority = case(
                (Product.name.op("~*")(rf"\y{escaped_query}\y"), 0), else_=1  # Exact query match first
            )
            search_query = search_query.order_by(exact_match_priority, Product.price.desc().nullslast())
        else:
            search_query = search_query.order_by(Product.price.desc().nullslast())

        # Limit results
        search_query = search_query.limit(limit)

        result = await db.execute(search_query)
        products = result.scalars().unique().all()

        # Convert to response format
        return {
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "image_url": get_primary_image_url(p),
                    "source_website": p.source_website,
                    "source_url": p.source_url,
                    "brand": p.brand,
                    "category_id": p.category_id,
                    "description": p.description,
                }
                for p in products
            ]
        }

    except Exception as e:
        logger.error(f"Error searching products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching products")


@router.get("/", response_model=CuratedLookListResponse)
async def list_curated_looks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    room_type: Optional[str] = Query(None),
    is_published: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all curated looks with pagination (admin view)"""
    try:
        # Build base query
        query = select(CuratedLook).options(selectinload(CuratedLook.products))

        # Apply filters
        if room_type:
            query = query.where(CuratedLook.room_type == room_type)
        if is_published is not None:
            query = query.where(CuratedLook.is_published == is_published)

        # Order by display_order, then created_at
        query = query.order_by(CuratedLook.display_order.asc(), CuratedLook.created_at.desc())

        # Get total count
        count_query = select(func.count()).select_from(CuratedLook)
        if room_type:
            count_query = count_query.where(CuratedLook.room_type == room_type)
        if is_published is not None:
            count_query = count_query.where(CuratedLook.is_published == is_published)

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)

        # Execute query
        result = await db.execute(query)
        looks = result.scalars().unique().all()

        # Calculate pagination
        pages = (total + size - 1) // size if total else 0
        has_next = page < pages
        has_prev = page > 1

        # Convert to summary schemas
        look_summaries = [
            CuratedLookSummarySchema(
                id=look.id,
                title=look.title,
                style_theme=look.style_theme,
                style_description=look.style_description,
                room_type=look.room_type,
                visualization_image=look.visualization_image,
                total_price=look.total_price or 0,
                is_published=look.is_published,
                display_order=look.display_order or 0,
                product_count=len(look.products) if look.products else 0,
                created_at=look.created_at,
            )
            for look in looks
        ]

        return CuratedLookListResponse(
            items=look_summaries, total=total, page=page, size=size, pages=pages, has_next=has_next, has_prev=has_prev
        )

    except Exception as e:
        logger.error(f"Error listing curated looks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching curated looks")


@router.get("/{look_id}", response_model=CuratedLookSchema)
async def get_curated_look(look_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single curated look with full details"""
    try:
        query = (
            select(CuratedLook)
            .where(CuratedLook.id == look_id)
            .options(selectinload(CuratedLook.products).selectinload(CuratedLookProduct.product).selectinload(Product.images))
        )
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        # Build product list with details
        products = []
        for lp in sorted(look.products, key=lambda x: x.display_order or 0):
            product = lp.product
            if product:
                products.append(
                    CuratedLookProductSchema(
                        id=product.id,
                        name=product.name,
                        price=product.price,
                        image_url=get_primary_image_url(product),
                        source_website=product.source_website,
                        source_url=product.source_url,
                        product_type=lp.product_type,
                        description=product.description,
                    )
                )

        return CuratedLookSchema(
            id=look.id,
            title=look.title,
            style_theme=look.style_theme,
            style_description=look.style_description,
            room_type=look.room_type,
            room_image=look.room_image,
            visualization_image=look.visualization_image,
            total_price=look.total_price or 0,
            is_published=look.is_published,
            display_order=look.display_order or 0,
            products=products,
            created_at=look.created_at,
            updated_at=look.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching curated look")


@router.post("/", response_model=CuratedLookSchema)
async def create_curated_look(look_data: CuratedLookCreate, db: AsyncSession = Depends(get_db)):
    """Create a new curated look"""
    # Log request details
    viz_size = len(look_data.visualization_image) if look_data.visualization_image else 0
    room_size = len(look_data.room_image) if look_data.room_image else 0
    logger.info(
        f"[Create Curated Look] Received: title='{look_data.title}', viz_size={viz_size/1024:.1f}KB, room_size={room_size/1024:.1f}KB, products={len(look_data.product_ids)}"
    )

    try:
        # Create the look
        look = CuratedLook(
            title=look_data.title,
            style_theme=look_data.style_theme,
            style_description=look_data.style_description,
            room_type=look_data.room_type.value,
            room_image=look_data.room_image,
            visualization_image=look_data.visualization_image,
            is_published=look_data.is_published,
            display_order=look_data.display_order,
            total_price=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(look)
        await db.flush()  # Get the ID

        # Add products if provided
        total_price = 0
        product_types = look_data.product_types or []

        for i, product_id in enumerate(look_data.product_ids):
            # Verify product exists and get price
            product_query = select(Product).where(Product.id == product_id)
            product_result = await db.execute(product_query)
            product = product_result.scalar_one_or_none()

            if product:
                product_type = product_types[i] if i < len(product_types) else None
                look_product = CuratedLookProduct(
                    curated_look_id=look.id,
                    product_id=product_id,
                    product_type=product_type,
                    display_order=i,
                    created_at=datetime.utcnow(),
                )
                db.add(look_product)
                if product.price:
                    total_price += product.price

        # Update total price
        look.total_price = total_price
        await db.commit()
        await db.refresh(look)

        # Return the created look with full details
        return await get_curated_look(look.id, db)

    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating curated look: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating curated look: {str(e)}")


@router.put("/{look_id}", response_model=CuratedLookSchema)
async def update_curated_look(look_id: int, look_data: CuratedLookUpdate, db: AsyncSession = Depends(get_db)):
    """Update a curated look's details"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        # Update fields if provided
        if look_data.title is not None:
            look.title = look_data.title
        if look_data.style_theme is not None:
            look.style_theme = look_data.style_theme
        if look_data.style_description is not None:
            look.style_description = look_data.style_description
        if look_data.room_type is not None:
            look.room_type = look_data.room_type.value
        if look_data.room_image is not None:
            look.room_image = look_data.room_image
        if look_data.visualization_image is not None:
            look.visualization_image = look_data.visualization_image
        if look_data.is_published is not None:
            look.is_published = look_data.is_published
        if look_data.display_order is not None:
            look.display_order = look_data.display_order

        look.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(look)

        return await get_curated_look(look_id, db)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating curated look")


@router.put("/{look_id}/products", response_model=CuratedLookSchema)
async def update_curated_look_products(
    look_id: int, product_data: CuratedLookProductUpdate, db: AsyncSession = Depends(get_db)
):
    """Update the products in a curated look"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        # Delete existing products
        await db.execute(delete(CuratedLookProduct).where(CuratedLookProduct.curated_look_id == look_id))

        # Add new products
        total_price = 0
        product_types = product_data.product_types or []

        for i, product_id in enumerate(product_data.product_ids):
            # Verify product exists and get price
            product_query = select(Product).where(Product.id == product_id)
            product_result = await db.execute(product_query)
            product = product_result.scalar_one_or_none()

            if product:
                product_type = product_types[i] if i < len(product_types) else None
                look_product = CuratedLookProduct(
                    curated_look_id=look_id,
                    product_id=product_id,
                    product_type=product_type,
                    display_order=i,
                    created_at=datetime.utcnow(),
                )
                db.add(look_product)
                if product.price:
                    total_price += product.price

        # Update total price
        look.total_price = total_price
        look.updated_at = datetime.utcnow()
        await db.commit()

        return await get_curated_look(look_id, db)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating products for look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating curated look products")


@router.delete("/{look_id}")
async def delete_curated_look(look_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a curated look"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        # Delete associated products first (cascade should handle this, but being explicit)
        await db.execute(delete(CuratedLookProduct).where(CuratedLookProduct.curated_look_id == look_id))

        # Delete the look
        await db.delete(look)
        await db.commit()

        return {"message": "Curated look deleted successfully", "id": look_id}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error deleting curated look")


@router.post("/{look_id}/publish")
async def publish_curated_look(look_id: int, db: AsyncSession = Depends(get_db)):
    """Publish a curated look (make it visible to users)"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        look.is_published = True
        look.updated_at = datetime.utcnow()
        await db.commit()

        return {"message": "Curated look published", "id": look_id}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error publishing curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error publishing curated look")


@router.post("/{look_id}/unpublish")
async def unpublish_curated_look(look_id: int, db: AsyncSession = Depends(get_db)):
    """Unpublish a curated look (hide from users)"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        look.is_published = False
        look.updated_at = datetime.utcnow()
        await db.commit()

        return {"message": "Curated look unpublished", "id": look_id}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error unpublishing curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error unpublishing curated look")
