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

from core.auth import require_admin
from core.database import get_db
from database.models import Category, CuratedLook, CuratedLookProduct, Product, ProductAttribute, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/curated", tags=["admin-curated"])


# Simple singular/plural normalization
def normalize_singular_plural(word: str) -> list:
    """
    Returns both singular and plural forms of a word.
    Handles common English patterns.
    """
    word = word.lower().strip()
    forms = [word]

    # Common irregular plurals
    irregulars = {
        "furniture": "furniture",  # Uncountable
        "decor": "decor",
        "seating": "seating",
    }

    if word in irregulars:
        return [word]

    # If word ends in 's', try to get singular
    if word.endswith("ies"):
        # categories -> category
        forms.append(word[:-3] + "y")
    elif word.endswith("es"):
        # boxes -> box, dishes -> dish
        if word.endswith("sses") or word.endswith("shes") or word.endswith("ches") or word.endswith("xes"):
            forms.append(word[:-2])
        else:
            forms.append(word[:-1])  # tables -> table (via 'es' -> 'e')
            forms.append(word[:-2])  # boxes -> box
    elif word.endswith("s") and not word.endswith("ss"):
        # sculptures -> sculpture
        forms.append(word[:-1])

    # If word doesn't end in 's', try to get plural
    if not word.endswith("s"):
        if word.endswith("y") and len(word) > 2 and word[-2] not in "aeiou":
            # category -> categories
            forms.append(word[:-1] + "ies")
        elif word.endswith(("s", "sh", "ch", "x", "z")):
            # box -> boxes
            forms.append(word + "es")
        else:
            # sculpture -> sculptures
            forms.append(word + "s")

    return list(set(forms))  # Remove duplicates


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
    # Wall art and paintings
    "painting": ["painting", "wall art", "artwork", "canvas art", "art print"],
    "paintings": ["painting", "wall art", "artwork", "canvas art", "art print"],
    "wall art": ["wall art", "painting", "artwork", "canvas art", "art print"],
    "artwork": ["artwork", "wall art", "painting", "canvas art", "art print"],
    "art": ["art", "wall art", "painting", "artwork", "art print"],
}


def expand_search_query(query: str) -> list:
    """Expand a search query to include synonyms and singular/plural forms"""
    query_lower = query.lower().strip()

    # First, check if the query matches any synonym key directly
    for key, synonyms in SEARCH_SYNONYMS.items():
        if key in query_lower or query_lower in key:
            return synonyms

    # If not found in synonyms, try singular/plural forms
    word_forms = normalize_singular_plural(query_lower)

    # Check if any form matches synonyms
    for form in word_forms:
        for key, synonyms in SEARCH_SYNONYMS.items():
            if key == form or form == key:
                return synonyms

    # No synonym match - return all singular/plural forms for direct search
    # This ensures "sculpture" and "sculptures" both match products with either form
    logger.info(f"No synonym match for '{query}', using singular/plural forms: {word_forms}")
    return word_forms


def get_primary_image_url(product: Product) -> Optional[str]:
    """Get the primary image URL for a product"""
    if not product.images:
        return None
    primary = next((img for img in product.images if img.is_primary), None)
    if primary:
        return primary.original_url
    return product.images[0].original_url if product.images else None


async def fetch_curated_look_with_products(look_id: int, db: AsyncSession) -> CuratedLookSchema:
    """Helper function to fetch a curated look with full details - can be called directly"""
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
                    quantity=lp.quantity or 1,
                    description=product.description,
                )
            )

    return CuratedLookSchema(
        id=look.id,
        title=look.title,
        style_theme=look.style_theme,
        style_description=look.style_description,
        style_labels=look.style_labels or [],
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


# NOTE: These routes MUST be defined BEFORE the /{look_id} route
# otherwise FastAPI will try to match "categories" or "search" as a look_id


@router.get("/categories")
async def get_product_categories(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
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
    styles: Optional[str] = Query(None, description="Comma-separated list of primary_style values"),
    materials: Optional[str] = Query(None, description="Comma-separated list of materials"),
    limit: int = Query(500, ge=1, le=1000),
    current_user: User = Depends(require_admin),
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

        # Filter by styles (uses Product.primary_style field)
        if styles:
            style_list = [s.strip().lower() for s in styles.split(",") if s.strip()]
            if style_list:
                # OR logic: match any of the selected styles
                search_query = search_query.where(func.lower(Product.primary_style).in_(style_list))

        # Filter by materials (uses ProductAttribute with material/material_primary)
        if materials:
            material_list = [m.strip().lower() for m in materials.split(",") if m.strip()]
            if material_list:
                # Subquery to find products with matching materials in ProductAttribute
                material_subquery = (
                    select(ProductAttribute.product_id)
                    .where(ProductAttribute.attribute_name.in_(["material", "material_primary"]))
                    .where(func.lower(ProductAttribute.attribute_value).in_(material_list))
                )
                search_query = search_query.where(Product.id.in_(material_subquery))

        # Order by: match priority (name > brand > description), then price
        # This ensures "paintings" shows actual paintings first, not rugs that mention paintings
        if query:
            escaped_query = re.escape(query)
            # Build name match condition for ALL expanded search terms
            # e.g., for "paintings" -> check "painting", "wall art", "artwork", etc in name
            name_match_conditions = [Product.name.op("~*")(rf"\y{re.escape(term)}\y") for term in search_terms]
            # Case expression to prioritize matches by field:
            # - Priority 0: Name matches ANY synonym (most relevant - actual paintings/wall art)
            # - Priority 1: Brand matches
            # - Priority 2: Description matches (least relevant - rugs mentioning paintings)
            match_priority = case(
                (or_(*name_match_conditions), 0),  # Name matches any synonym - highest priority
                (Product.brand.op("~*")(rf"\y{escaped_query}\y"), 1),  # Brand match - medium priority
                else_=2,  # Description only match - lowest priority
            )
            search_query = search_query.order_by(match_priority, Product.price.desc().nullslast())
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
    current_user: User = Depends(require_admin),
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
                style_labels=look.style_labels or [],
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
async def get_curated_look(
    look_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get a single curated look with full details"""
    try:
        return await fetch_curated_look_with_products(look_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching curated look")


@router.post("/", response_model=CuratedLookSchema)
async def create_curated_look(
    look_data: CuratedLookCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
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
            style_labels=look_data.style_labels or [],
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
        product_quantities = look_data.product_quantities or []

        for i, product_id in enumerate(look_data.product_ids):
            # Verify product exists and get price
            product_query = select(Product).where(Product.id == product_id)
            product_result = await db.execute(product_query)
            product = product_result.scalar_one_or_none()

            if product:
                product_type = product_types[i] if i < len(product_types) else None
                quantity = product_quantities[i] if i < len(product_quantities) else 1
                look_product = CuratedLookProduct(
                    curated_look_id=look.id,
                    product_id=product_id,
                    product_type=product_type,
                    quantity=quantity,
                    display_order=i,
                    created_at=datetime.utcnow(),
                )
                db.add(look_product)
                if product.price:
                    total_price += product.price * quantity

        # Update total price
        look.total_price = total_price
        await db.commit()
        await db.refresh(look)

        # Return the created look with full details
        return await fetch_curated_look_with_products(look.id, db)

    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating curated look: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating curated look: {str(e)}")


@router.put("/{look_id}", response_model=CuratedLookSchema)
async def update_curated_look(
    look_id: int,
    look_data: CuratedLookUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a curated look's details and optionally its products"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        # Update metadata fields if provided
        if look_data.title is not None:
            look.title = look_data.title
        if look_data.style_theme is not None:
            look.style_theme = look_data.style_theme
        if look_data.style_description is not None:
            look.style_description = look_data.style_description
        if look_data.style_labels is not None:
            look.style_labels = look_data.style_labels
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

        # Update products if provided
        if look_data.product_ids is not None:
            logger.info(f"Updating products for look {look_id}: {len(look_data.product_ids)} products")

            # Delete existing products
            await db.execute(delete(CuratedLookProduct).where(CuratedLookProduct.curated_look_id == look_id))

            # Add new products with quantities
            total_price = 0
            product_types = look_data.product_types or []
            product_quantities = look_data.product_quantities or []

            for i, product_id in enumerate(look_data.product_ids):
                # Verify product exists and get price
                product_query = select(Product).where(Product.id == product_id)
                product_result = await db.execute(product_query)
                product = product_result.scalar_one_or_none()

                if product:
                    product_type = product_types[i] if i < len(product_types) else None
                    quantity = product_quantities[i] if i < len(product_quantities) else 1

                    logger.info(f"  Product {product_id}: type={product_type}, quantity={quantity}")

                    look_product = CuratedLookProduct(
                        curated_look_id=look_id,
                        product_id=product_id,
                        product_type=product_type,
                        quantity=quantity,
                        display_order=i,
                        created_at=datetime.utcnow(),
                    )
                    db.add(look_product)
                    if product.price:
                        total_price += product.price * quantity

            # Update total price
            look.total_price = total_price

        look.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(look)

        return await fetch_curated_look_with_products(look_id, db)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating curated look")


@router.put("/{look_id}/products", response_model=CuratedLookSchema)
async def update_curated_look_products(
    look_id: int,
    product_data: CuratedLookProductUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
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

        return await fetch_curated_look_with_products(look_id, db)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating products for look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating curated look products")


@router.delete("/{look_id}")
async def delete_curated_look(
    look_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
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
async def publish_curated_look(
    look_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
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
async def unpublish_curated_look(
    look_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
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
