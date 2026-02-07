"""
Admin API routes for managing curated looks
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

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
from services.search_service import (
    expand_search_query_grouped,
    get_exclusion_terms,
    semantic_search_products,
    should_exclude_product,
)
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.auth import require_admin
from core.database import get_db
from database.models import Category, CuratedLook, CuratedLookProduct, Product, ProductAttribute, User


def calculate_budget_tier(total_price: float) -> str:
    """
    Calculate budget tier based on total price.

    Thresholds (in INR):
    - Pocket-friendly: < ₹2L (< 200,000)
    - Mid-tier: ₹2L – ₹8L (200,000 - 800,000)
    - Premium: ₹8L – ₹15L (800,000 - 1,500,000)
    - Luxury: ₹15L+ (>= 1,500,000)
    """
    if total_price < 200000:
        return "pocket_friendly"
    elif total_price < 800000:
        return "mid_tier"
    elif total_price < 1500000:
        return "premium"
    else:
        return "luxury"


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/curated", tags=["admin-curated"])


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
        budget_tier=look.budget_tier if look.budget_tier else None,
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
    source_website: Optional[str] = Query(None, description="Comma-separated list of stores to filter by"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    colors: Optional[str] = Query(None, description="Comma-separated list of colors"),
    styles: Optional[str] = Query(None, description="Comma-separated list of primary_style values"),
    materials: Optional[str] = Query(None, description="Comma-separated list of materials"),
    use_semantic: bool = Query(True, description="Use semantic search (embeddings) when available"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(50, ge=1, le=200, description="Number of products per page"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Search for products to add to a curated look. Uses semantic search + keyword fallback with pagination."""
    try:
        semantic_product_ids: Dict[int, float] = {}
        search_groups = []

        # Parse comma-separated stores into a list
        source_websites: Optional[List[str]] = None
        if source_website:
            source_websites = [s.strip() for s in source_website.split(",") if s.strip()]
            if not source_websites:
                source_websites = None

        # Step 1: Try semantic search first (for products with embeddings)
        # Get all semantic matches (we'll paginate the combined results later)
        if query and use_semantic:
            try:
                semantic_product_ids = await semantic_search_products(
                    query_text=query,
                    db=db,
                    category_ids=[category_id] if category_id else None,
                    source_websites=source_websites,
                    min_price=min_price,
                    max_price=max_price,
                    limit=10000,  # Get all semantic matches, pagination happens later
                )
                logger.info(f"[SEARCH] Semantic search returned {len(semantic_product_ids)} products")
            except Exception as e:
                logger.warning(f"[SEARCH] Semantic search failed, falling back to keyword: {e}")
                semantic_product_ids = {}

        # Step 2: Build keyword search query (for products without embeddings or as fallback)
        search_query = select(Product).options(selectinload(Product.images)).where(Product.is_available.is_(True))

        logger.info(f"[SEARCH DEBUG] query='{query}', source_websites={source_websites}, page={page}")

        # Apply text search if query provided (with synonym expansion for name only)
        if query:
            # Use grouped expansion for AND logic between word groups
            search_groups = expand_search_query_grouped(query)
            logger.info(f"Search query '{query}' expanded to groups: {search_groups}")

            # Build AND conditions: product must match at least one term from EACH group
            # Example: "L-shaped sofa" -> must match (l-shaped OR l-shapeds) AND (sofa OR couch OR settee)
            and_conditions = []
            for group in search_groups:
                group_conditions = []
                for term in group:
                    escaped_term = re.escape(term)
                    # Use PostgreSQL regex with word boundaries (\y) for accurate matching
                    group_conditions.append(Product.name.op("~*")(rf"\y{escaped_term}\y"))
                if group_conditions:
                    # OR within each group
                    and_conditions.append(or_(*group_conditions))

            # Broad terms that should NOT match in description (too many false positives)
            BROAD_TERMS = {"decor", "art", "furniture", "home", "living", "style", "design"}

            # Also match original query in brand and description with word boundaries
            escaped_query = re.escape(query)
            query_lower = query.lower().strip()

            original_query_conditions = [
                Product.brand.op("~*")(rf"\y{escaped_query}\y"),
            ]

            # Only match description for specific (non-broad) terms
            if query_lower not in BROAD_TERMS:
                original_query_conditions.append(Product.description.op("~*")(rf"\y{escaped_query}\y"))

            # Final condition: (all AND conditions from groups) OR (original query in brand/description)
            if and_conditions:
                # AND between all groups
                grouped_condition = and_(*and_conditions)
                # OR with brand/description match for full phrase
                all_conditions = [grouped_condition] + original_query_conditions
                search_query = search_query.where(or_(*all_conditions))

        # Filter by category if specified
        if category_id:
            search_query = search_query.where(Product.category_id == category_id)

        # Filter by store(s) if specified
        if source_websites:
            search_query = search_query.where(Product.source_website.in_(source_websites))

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
            # Build name match condition for ALL expanded search terms (flatten the groups)
            all_search_terms = [term for group in search_groups for term in group]
            name_match_conditions = [Product.name.op("~*")(rf"\y{re.escape(term)}\y") for term in all_search_terms]
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

        # Get all keyword matches (no limit - we paginate combined results)
        search_query = search_query.limit(10000)

        result = await db.execute(search_query)
        keyword_products = result.scalars().unique().all()

        # STEP 3: Merge semantic and keyword results into ordered list of product IDs
        # Priority: semantic matches first (sorted by similarity), then keyword-only matches
        ordered_product_ids: List[int] = []
        semantic_scores: Dict[int, float] = {}
        seen_product_ids = set()

        # Get exclusion terms for the query (e.g., "center table" excludes "dining")
        exclusion_terms = get_exclusion_terms(query) if query else []
        if exclusion_terms:
            logger.info(f"[SEARCH] Exclusion terms for '{query}': {exclusion_terms}")

        # Helper: Check if product name matches ALL search groups (for primary match)
        def name_matches_all_groups(product_name: str, groups: List[List[str]]) -> bool:
            """Check if product name contains at least one term from EACH group."""
            if not groups:
                return True
            name_lower = product_name.lower()
            # Normalize: "L - Shaped" -> "l-shaped"
            name_normalized = re.sub(r"\s*-\s*", "-", name_lower)
            name_spaced = re.sub(r"-", " ", name_lower)  # Also try with spaces

            for group in groups:
                group_matched = False
                for term in group:
                    term_normalized = re.sub(r"\s*-\s*", "-", term.lower())
                    # Check various forms
                    if term_normalized in name_normalized or term_normalized in name_spaced:
                        group_matched = True
                        break
                    # Also check with spaces
                    term_spaced = re.sub(r"-", " ", term.lower())
                    if term_spaced in name_lower or term_spaced in name_spaced:
                        group_matched = True
                        break
                if not group_matched:
                    return False
            return True

        if semantic_product_ids:
            # First, include products from semantic search that ALSO match keyword search
            # This prevents "carpet" search from returning cushions/curtains just because they're semantically similar
            semantic_threshold = 0.3
            semantic_sorted = sorted(semantic_product_ids.items(), key=lambda x: x[1], reverse=True)

            # Get the set of keyword-matching product IDs and names
            keyword_product_ids = {p.id for p in keyword_products}
            keyword_product_names = {p.id: p.name for p in keyword_products}

            # If we have exclusion terms, we need to fetch names for semantic-only products
            semantic_only_names = {}
            if exclusion_terms:
                semantic_only_ids = [pid for pid, _ in semantic_sorted if pid not in keyword_product_ids]
                if semantic_only_ids:
                    names_query = select(Product.id, Product.name).where(Product.id.in_(semantic_only_ids))
                    names_result = await db.execute(names_query)
                    semantic_only_names = {row[0]: row[1] for row in names_result.fetchall()}

            excluded_count = 0
            for product_id, similarity in semantic_sorted:
                if similarity >= semantic_threshold:
                    # Only include semantic results that also match keyword search
                    # OR have very high similarity (>= 0.5) for genuine semantic matches
                    if product_id in keyword_product_ids or similarity >= 0.5:
                        # Check exclusion terms
                        product_name = keyword_product_names.get(product_id) or semantic_only_names.get(product_id, "")
                        if exclusion_terms and should_exclude_product(product_name, exclusion_terms):
                            excluded_count += 1
                            continue

                        ordered_product_ids.append(product_id)
                        semantic_scores[product_id] = similarity
                        seen_product_ids.add(product_id)

            logger.info(
                f"[SEARCH] Added {len(seen_product_ids)} semantic results (threshold={semantic_threshold}, keyword-filtered, {excluded_count} excluded)"
            )

        # Add keyword-only results (products without embeddings or below semantic threshold)
        excluded_keyword_count = 0
        for p in keyword_products:
            if p.id not in seen_product_ids:
                # Check exclusion terms
                if exclusion_terms and should_exclude_product(p.name, exclusion_terms):
                    excluded_keyword_count += 1
                    continue
                ordered_product_ids.append(p.id)
                seen_product_ids.add(p.id)

        if excluded_keyword_count > 0:
            logger.info(f"[SEARCH] Excluded {excluded_keyword_count} keyword results due to exclusion terms")

        total_results = len(ordered_product_ids)

        # Calculate total_primary and total_related by fetching ALL product names
        # This is needed for accurate counts across pagination
        total_primary = 0
        total_related = 0
        if ordered_product_ids and search_groups:
            # Fetch just names for all products (efficient - no images/full data)
            names_query = select(Product.id, Product.name).where(Product.id.in_(ordered_product_ids))
            names_result = await db.execute(names_query)
            all_products_names = {row[0]: row[1] for row in names_result.fetchall()}

            for product_id in ordered_product_ids:
                name = all_products_names.get(product_id, "")
                if name_matches_all_groups(name, search_groups):
                    total_primary += 1
                else:
                    total_related += 1

            logger.info(f"[SEARCH] Total counts: {total_primary} primary, {total_related} related (out of {total_results})")
        else:
            # No search query - all are primary matches
            total_primary = total_results
            total_related = 0

        # STEP 4: Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_product_ids = ordered_product_ids[start_idx:end_idx]
        has_more = end_idx < total_results

        # STEP 5: Fetch product details for this page
        if page_product_ids:
            products_query = select(Product).options(selectinload(Product.images)).where(Product.id.in_(page_product_ids))
            products_result = await db.execute(products_query)
            products_map = {p.id: p for p in products_result.scalars().unique().all()}

            # Build response in the correct order
            final_products = []
            for product_id in page_product_ids:
                if product_id in products_map:
                    p = products_map[product_id]
                    similarity = semantic_scores.get(product_id, 0)

                    # Primary match = product name contains ALL search terms (using synonym groups)
                    # This is more accurate than similarity threshold for specific queries like "L-shaped sofa"
                    is_primary = name_matches_all_groups(p.name, search_groups) if search_groups else True

                    product_data = {
                        "id": p.id,
                        "name": p.name,
                        "price": p.price,
                        "image_url": get_primary_image_url(p),
                        "source_website": p.source_website,
                        "source_url": p.source_url,
                        "brand": p.brand,
                        "category_id": p.category_id,
                        "description": p.description,
                        "is_primary_match": is_primary,
                        "similarity_score": round(similarity, 3) if similarity > 0 else None,
                    }
                    final_products.append(product_data)
        else:
            final_products = []

        # Count primary matches in this page
        page_primary_count = sum(1 for p in final_products if p.get("is_primary_match"))
        logger.info(
            f"[SEARCH] Page {page}: {len(final_products)} products, {page_primary_count} primary (name matches all search terms)"
        )

        return {
            "products": final_products,
            "total": total_results,
            "total_primary": total_primary,
            "total_related": total_related,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
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
    search: Optional[str] = Query(None, description="Search by title or style theme"),
    style: Optional[str] = Query(None, description="Filter by style theme"),
    budget_tier: Optional[str] = Query(None, description="Filter by budget tier"),
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

        # Search filter (case-insensitive search in title and style_theme)
        if search:
            search_pattern = f"%{search}%"
            query = query.where(or_(CuratedLook.title.ilike(search_pattern), CuratedLook.style_theme.ilike(search_pattern)))

        # Style filter
        if style:
            # Handle underscore to space conversion (e.g., "indian_contemporary" -> "Indian Contemporary")
            style_pattern = f"%{style.replace('_', ' ')}%"
            query = query.where(CuratedLook.style_theme.ilike(style_pattern))

        # Budget tier filter
        if budget_tier:
            query = query.where(CuratedLook.budget_tier == budget_tier)

        # Order by: latest first (created_at DESC)
        query = query.order_by(CuratedLook.created_at.desc())

        # Get total count (with same filters)
        count_query = select(func.count()).select_from(CuratedLook)
        if room_type:
            count_query = count_query.where(CuratedLook.room_type == room_type)
        if is_published is not None:
            count_query = count_query.where(CuratedLook.is_published == is_published)
        if search:
            search_pattern = f"%{search}%"
            count_query = count_query.where(
                or_(CuratedLook.title.ilike(search_pattern), CuratedLook.style_theme.ilike(search_pattern))
            )
        if style:
            style_pattern = f"%{style.replace('_', ' ')}%"
            count_query = count_query.where(CuratedLook.style_theme.ilike(style_pattern))
        if budget_tier:
            count_query = count_query.where(CuratedLook.budget_tier == budget_tier)

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
                budget_tier=look.budget_tier if look.budget_tier else None,
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
        # Create the look (budget_tier will be auto-calculated after products are added)
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

        # Update total price and auto-calculate budget tier
        look.total_price = total_price
        look.budget_tier = calculate_budget_tier(total_price)
        await db.commit()
        await db.refresh(look)

        # Return the created look with full details
        # Note: Pre-computation happens after /visualize endpoint, not here
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

        # Update metadata fields if provided (budget_tier is auto-calculated, not manual)
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

            # Update total price and auto-calculate budget tier
            look.total_price = total_price
            look.budget_tier = calculate_budget_tier(total_price)

        look.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(look)

        # Note: Pre-computation happens after /visualize endpoint, not here
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

        # Update total price and auto-calculate budget tier
        look.total_price = total_price
        look.budget_tier = calculate_budget_tier(total_price)
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


@router.post("/{look_id}/precompute-masks")
async def precompute_masks_for_curated_look(
    look_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger mask precomputation for a curated look.
    This pre-computes SAM segmentation masks for instant "Edit Position" functionality.
    """
    from services.mask_precomputation_service import mask_precomputation_service

    try:
        # Get the curated look with products
        query = (
            select(CuratedLook)
            .options(selectinload(CuratedLook.products).selectinload(CuratedLookProduct.product))
            .where(CuratedLook.id == look_id)
        )
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        if not look.visualization_image:
            raise HTTPException(status_code=400, detail="Curated look has no visualization image")

        # Build products list
        products = []
        for clp in look.products:
            if clp.product:
                products.append({"id": clp.product.id, "name": clp.product.name})

        logger.info(f"[PrecomputeMasks] Starting precomputation for look {look_id} with {len(products)} products")

        # Delete any existing masks for this look (force refresh)
        await mask_precomputation_service.invalidate_curated_look_masks(db, look_id)

        # Trigger precomputation
        job_id = await mask_precomputation_service.trigger_precomputation_for_curated_look(
            db, look_id, look.visualization_image, products
        )

        if not job_id:
            raise HTTPException(status_code=500, detail="Failed to create precomputation job")

        # Process synchronously (blocking) so we can return results
        await mask_precomputation_service.process_precomputation(db, job_id, look.visualization_image, products)

        # Get results
        from database.models import PrecomputedMask

        result = await db.execute(select(PrecomputedMask).where(PrecomputedMask.id == job_id))
        mask_record = result.scalar_one_or_none()

        if mask_record:
            layer_count = len(mask_record.layers_data) if mask_record.layers_data else 0
            return {
                "message": "Precomputation completed",
                "look_id": look_id,
                "job_id": job_id,
                "status": mask_record.status.value,
                "layer_count": layer_count,
                "processing_time": mask_record.processing_time,
            }

        return {"message": "Precomputation triggered", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error precomputing masks for look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error precomputing masks: {str(e)}")
