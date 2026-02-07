"""
Product API routes
"""
import logging
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.products import (
    CategorySchema,
    ProductDetailResponse,
    ProductFilters,
    ProductQuery,
    ProductSchema,
    ProductSearchResponse,
    ProductStatsResponse,
    ProductSummarySchema,
)
from services.search_service import (
    build_keyword_conditions,
    expand_search_query_grouped,
    get_exclusion_terms,
    semantic_search_products,
    should_exclude_product,
)
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from database.models import Category, Product, ProductAttribute, ProductImage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["products"])


def _format_product(product) -> dict:
    """Format a product for API response."""
    primary_image_url = None
    formatted_images = []
    if product.images:
        for img in product.images:
            img_data = {
                "id": img.id,
                "original_url": img.original_url,
                "thumbnail_url": img.thumbnail_url,
                "medium_url": img.medium_url,
                "large_url": img.large_url,
                "is_primary": img.is_primary,
            }
            formatted_images.append(img_data)
            if img.is_primary:
                primary_image_url = img.large_url or img.medium_url or img.original_url
        if not primary_image_url and formatted_images:
            first_img = formatted_images[0]
            primary_image_url = first_img.get("large_url") or first_img.get("medium_url") or first_img.get("original_url")

    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "original_price": product.original_price,
        "currency": product.currency or "INR",
        "brand": product.brand,
        "source_website": product.source_website,
        "source_url": product.source_url,
        "is_available": product.is_available,
        "is_on_sale": product.is_on_sale,
        "image_url": primary_image_url,
        "images": formatted_images,
        "category": {
            "id": product.category.id,
            "name": product.category.name,
        }
        if product.category
        else None,
        "description": product.description,
    }


def _name_matches_all_groups(product_name: str, groups: List[List[str]]) -> bool:
    """Check if product name contains at least one term from EACH group."""
    if not groups:
        return True
    name_lower = product_name.lower()
    name_normalized = re.sub(r"\s*-\s*", "-", name_lower)
    name_spaced = re.sub(r"-", " ", name_lower)

    for group in groups:
        group_matched = False
        for term in group:
            term_normalized = re.sub(r"\s*-\s*", "-", term.lower())
            if term_normalized in name_normalized or term_normalized in name_spaced:
                group_matched = True
                break
            term_spaced = re.sub(r"-", " ", term.lower())
            if term_spaced in name_lower or term_spaced in name_spaced:
                group_matched = True
                break
        if not group_matched:
            return False
    return True


@router.get("/search")
async def search_products(
    query: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    source_website: Optional[str] = Query(None, description="Comma-separated list of stores"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    colors: Optional[str] = Query(None),
    styles: Optional[str] = Query(None),
    materials: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search products with semantic + keyword search and filters - public endpoint for design studio"""
    try:
        # Parse comma-separated source websites
        source_websites: Optional[List[str]] = None
        if source_website:
            source_websites = [s.strip() for s in source_website.split(",") if s.strip()]
            if not source_websites:
                source_websites = None

        logger.info(f"Search products: query={query}, sources={source_websites}, category={category_id}, page={page}")

        # ---- Step 1: Semantic search (numpy-vectorized) ----
        semantic_ids: Dict[int, float] = {}
        if query:
            try:
                semantic_ids = await semantic_search_products(
                    query_text=query,
                    db=db,
                    category_ids=[category_id] if category_id else None,
                    source_websites=source_websites,
                    min_price=min_price,
                    max_price=max_price,
                    limit=10000,
                )
                logger.info(f"[SEARCH] Semantic search returned {len(semantic_ids)} products")
            except Exception as e:
                logger.warning(f"[SEARCH] Semantic search failed, using keyword only: {e}")

        # ---- Step 2: Keyword search (word-boundary + AND-grouped synonyms) ----
        search_groups: List[List[str]] = []
        base_query = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.images))
            .where(Product.is_available.is_(True))
        )

        if query:
            where_clause, search_groups = build_keyword_conditions(query)
            base_query = base_query.where(where_clause)

        if category_id:
            base_query = base_query.where(Product.category_id == category_id)
        if source_websites:
            base_query = base_query.where(Product.source_website.in_(source_websites))
        if min_price is not None:
            base_query = base_query.where(Product.price >= min_price)
        if max_price is not None:
            base_query = base_query.where(Product.price <= max_price)

        # Filter by colors
        if colors:
            color_list = [c.strip().lower() for c in colors.split(",")]
            color_conditions = []
            for color in color_list:
                color_conditions.append(or_(Product.name.ilike(f"%{color}%"), Product.description.ilike(f"%{color}%")))
            if color_conditions:
                base_query = base_query.where(or_(*color_conditions))

        # Filter by styles
        if styles:
            style_list = [s.strip().lower() for s in styles.split(",") if s.strip()]
            if style_list:
                base_query = base_query.where(func.lower(Product.primary_style).in_(style_list))

        # Filter by materials
        if materials:
            material_list = [m.strip().lower() for m in materials.split(",") if m.strip()]
            if material_list:
                material_subquery = (
                    select(ProductAttribute.product_id)
                    .where(ProductAttribute.attribute_name.in_(["material", "material_primary"]))
                    .where(func.lower(ProductAttribute.attribute_value).in_(material_list))
                )
                base_query = base_query.where(Product.id.in_(material_subquery))

        # Order by match priority (name > brand > description)
        if query:
            escaped_query = re.escape(query)
            all_search_terms = [term for group in search_groups for term in group]
            name_match_conditions = [Product.name.op("~*")(rf"\y{re.escape(term)}\y") for term in all_search_terms]
            match_priority = case(
                (or_(*name_match_conditions), 0) if name_match_conditions else (Product.id.isnot(None), 2),
                (Product.brand.op("~*")(rf"\y{escaped_query}\y"), 1),
                else_=2,
            )
            base_query = base_query.order_by(match_priority, Product.price.desc().nullslast())
        else:
            base_query = base_query.order_by(Product.price.desc().nullslast())

        base_query = base_query.limit(10000)

        keyword_result = await db.execute(base_query)
        keyword_products = keyword_result.scalars().unique().all()
        keyword_ids = {p.id for p in keyword_products}

        # ---- Step 3: Merge semantic + keyword, apply exclusions ----
        exclusion_terms = get_exclusion_terms(query) if query else []
        if exclusion_terms:
            logger.info(f"[SEARCH] Exclusion terms for '{query}': {exclusion_terms}")

        ordered_product_ids: List[int] = []
        semantic_scores: Dict[int, float] = {}
        seen_ids: set = set()

        SIMILARITY_THRESHOLD = 0.3

        if semantic_ids:
            keyword_product_names = {p.id: p.name for p in keyword_products}
            semantic_sorted = sorted(semantic_ids.items(), key=lambda x: x[1], reverse=True)

            # Fetch names for semantic-only products if we need exclusion checks
            semantic_only_names: Dict[int, str] = {}
            if exclusion_terms:
                semantic_only_id_list = [pid for pid, _ in semantic_sorted if pid not in keyword_ids]
                if semantic_only_id_list:
                    names_query = select(Product.id, Product.name).where(Product.id.in_(semantic_only_id_list))
                    names_result = await db.execute(names_query)
                    semantic_only_names = {row[0]: row[1] for row in names_result.fetchall()}

            for product_id, similarity in semantic_sorted:
                if similarity >= SIMILARITY_THRESHOLD:
                    if product_id in keyword_ids or similarity >= 0.5:
                        product_name = keyword_product_names.get(product_id) or semantic_only_names.get(product_id, "")
                        if exclusion_terms and should_exclude_product(product_name, exclusion_terms):
                            continue
                        ordered_product_ids.append(product_id)
                        semantic_scores[product_id] = similarity
                        seen_ids.add(product_id)

        # Add keyword-only results
        for p in keyword_products:
            if p.id not in seen_ids:
                if exclusion_terms and should_exclude_product(p.name, exclusion_terms):
                    continue
                ordered_product_ids.append(p.id)
                seen_ids.add(p.id)

        total_results = len(ordered_product_ids)

        # ---- Calculate total_primary / total_related ----
        total_primary = 0
        total_related = 0
        if ordered_product_ids and search_groups:
            names_query = select(Product.id, Product.name).where(Product.id.in_(ordered_product_ids))
            names_result = await db.execute(names_query)
            all_product_names = {row[0]: row[1] for row in names_result.fetchall()}
            for product_id in ordered_product_ids:
                name = all_product_names.get(product_id, "")
                if _name_matches_all_groups(name, search_groups):
                    total_primary += 1
                else:
                    total_related += 1
        else:
            total_primary = total_results

        # ---- Step 4: Paginate ----
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_product_ids = ordered_product_ids[start_idx:end_idx]
        has_more = end_idx < total_results

        # ---- Step 5: Fetch product details for this page ----
        if page_product_ids:
            products_query = (
                select(Product)
                .options(selectinload(Product.category), selectinload(Product.images))
                .where(Product.id.in_(page_product_ids))
            )
            products_result = await db.execute(products_query)
            products_map = {p.id: p for p in products_result.scalars().unique().all()}

            formatted_products = []
            for product_id in page_product_ids:
                if product_id in products_map:
                    p = products_map[product_id]
                    formatted = _format_product(p)
                    formatted["is_primary_match"] = _name_matches_all_groups(p.name, search_groups) if search_groups else True
                    formatted["similarity_score"] = (
                        round(semantic_scores[product_id], 3) if product_id in semantic_scores else None
                    )
                    formatted_products.append(formatted)
        else:
            formatted_products = []

        return {
            "products": formatted_products,
            "total": total_results,
            "total_primary": total_primary,
            "total_related": total_related,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        }

    except Exception as e:
        logger.error(f"Error searching products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error searching products: {str(e)}")


@router.get("/", response_model=ProductSearchResponse)
async def get_products(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    brand: Optional[List[str]] = Query(None),
    source_website: Optional[List[str]] = Query(None),
    is_available: Optional[bool] = Query(None),
    is_on_sale: Optional[bool] = Query(None),
    sort_by: str = Query("created_at"),
    sort_direction: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated product list with filtering and search"""
    try:
        logger.info("Starting get_products endpoint")

        # Build base query
        query = select(Product).options(selectinload(Product.category), selectinload(Product.images))
        logger.info("Base query built with eager loading")

        # Apply search with synonym expansion + word boundaries
        if search:
            search_groups = expand_search_query_grouped(search)
            # Build AND conditions across groups, OR within each group
            and_conditions = []
            for group in search_groups:
                group_conditions = []
                for term in group:
                    escaped_term = re.escape(term)
                    group_conditions.append(
                        or_(
                            Product.name.op("~*")(rf"\y{escaped_term}\y"),
                            Product.description.op("~*")(rf"\y{escaped_term}\y"),
                            Product.brand.op("~*")(rf"\y{escaped_term}\y"),
                        )
                    )
                if group_conditions:
                    and_conditions.append(or_(*group_conditions))
            if and_conditions:
                query = query.where(and_(*and_conditions))

        if category_id:
            query = query.where(Product.category_id == category_id)

        if min_price is not None:
            query = query.where(Product.price >= min_price)

        if max_price is not None:
            query = query.where(Product.price <= max_price)

        if brand:
            query = query.where(Product.brand.in_(brand))

        if source_website:
            query = query.where(Product.source_website.in_(source_website))

        if is_available is not None:
            query = query.where(Product.is_available == is_available)

        if is_on_sale is not None:
            query = query.where(Product.is_on_sale == is_on_sale)

        # Apply sorting
        if sort_by == "price":
            if sort_direction == "desc":
                query = query.order_by(Product.price.desc())
            else:
                query = query.order_by(Product.price.asc())
        elif sort_by == "name":
            if sort_direction == "desc":
                query = query.order_by(Product.name.desc())
            else:
                query = query.order_by(Product.name.asc())
        else:  # default to created_at
            if sort_direction == "desc":
                query = query.order_by(Product.scraped_at.desc())
            else:
                query = query.order_by(Product.scraped_at.asc())

        # Get total count (must use same WHERE conditions)
        count_query = select(func.count()).select_from(Product)
        if search:
            count_and_conditions = []
            for group in search_groups:
                group_conditions = []
                for term in group:
                    escaped_term = re.escape(term)
                    group_conditions.append(
                        or_(
                            Product.name.op("~*")(rf"\y{escaped_term}\y"),
                            Product.description.op("~*")(rf"\y{escaped_term}\y"),
                            Product.brand.op("~*")(rf"\y{escaped_term}\y"),
                        )
                    )
                if group_conditions:
                    count_and_conditions.append(or_(*group_conditions))
            if count_and_conditions:
                count_query = count_query.where(and_(*count_and_conditions))

        if category_id:
            count_query = count_query.where(Product.category_id == category_id)
        if min_price is not None:
            count_query = count_query.where(Product.price >= min_price)
        if max_price is not None:
            count_query = count_query.where(Product.price <= max_price)
        if brand:
            count_query = count_query.where(Product.brand.in_(brand))
        if source_website:
            count_query = count_query.where(Product.source_website.in_(source_website))
        if is_available is not None:
            count_query = count_query.where(Product.is_available == is_available)
        if is_on_sale is not None:
            count_query = count_query.where(Product.is_on_sale == is_on_sale)

        logger.info("Executing count query")
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        logger.info(f"Total products found: {total}")

        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)

        # Execute query
        logger.info(f"Executing main query with offset={offset}, limit={size}")
        result = await db.execute(query)
        products = result.scalars().unique().all()
        logger.info(f"Retrieved {len(products)} products from database")

        # Calculate pagination info
        pages = (total + size - 1) // size
        has_next = page < pages
        has_prev = page > 1

        # Convert to summary schemas
        product_summaries = []
        for product in products:
            try:
                primary_image = None
                if product.images:
                    primary_image = next((img for img in product.images if img.is_primary), product.images[0])

                category = product.category

                product_summaries.append(
                    ProductSummarySchema(
                        id=product.id,
                        name=product.name,
                        price=product.price,
                        original_price=product.original_price,
                        currency=product.currency,
                        brand=product.brand,
                        source_website=product.source_website,
                        is_available=product.is_available,
                        is_on_sale=product.is_on_sale,
                        primary_image=primary_image,
                        category=category,
                    )
                )
            except Exception as e:
                logger.error(f"Error processing product {product.id}: {e}", exc_info=True)
                raise

        return ProductSearchResponse(
            items=product_summaries,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev,
            query=search,
            filters_applied={
                "category_id": category_id,
                "min_price": min_price,
                "max_price": max_price,
                "brand": brand,
                "source_website": source_website,
                "is_available": is_available,
                "is_on_sale": is_on_sale,
            },
        )

    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail="Error fetching products")


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed product information"""
    try:
        # Get main product
        query = select(Product).where(Product.id == product_id)
        result = await db.execute(query)
        product = result.scalar_one_or_none()

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Get related products (same category, different product)
        related_query = (
            select(Product)
            .where(and_(Product.category_id == product.category_id, Product.id != product.id, Product.is_available == True))
            .limit(6)
        )

        related_result = await db.execute(related_query)
        related_products = related_result.scalars().all()

        # Convert related products to summaries
        related_summaries = []
        for related in related_products:
            primary_image = None
            if related.images:
                primary_image = next((img for img in related.images if img.is_primary), related.images[0])

            related_summaries.append(
                ProductSummarySchema(
                    id=related.id,
                    name=related.name,
                    price=related.price,
                    original_price=related.original_price,
                    currency=related.currency,
                    brand=related.brand,
                    source_website=related.source_website,
                    is_available=related.is_available,
                    is_on_sale=related.is_on_sale,
                    primary_image=primary_image,
                    category=related.category,
                )
            )

        return ProductDetailResponse(product=ProductSchema.from_orm(product), related_products=related_summaries)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching product details")


@router.get("/stats/overview", response_model=ProductStatsResponse)
async def get_product_stats(db: AsyncSession = Depends(get_db)):
    """Get product statistics and overview"""
    try:
        # Total products
        total_query = select(func.count()).select_from(Product)
        total_result = await db.execute(total_query)
        total_products = total_result.scalar()

        # By source website
        source_query = select(Product.source_website, func.count(Product.id)).group_by(Product.source_website)
        source_result = await db.execute(source_query)
        by_source = {row[0]: row[1] for row in source_result.all()}

        # By category
        category_query = (
            select(Category.name, func.count(Product.id))
            .join(Product, Category.id == Product.category_id, isouter=True)
            .group_by(Category.name)
        )
        category_result = await db.execute(category_query)
        by_category = {row[0] or "Uncategorized": row[1] for row in category_result.all()}

        # Price ranges
        price_ranges = {"Under $50": 0, "$50-$200": 0, "$200-$500": 0, "$500-$1000": 0, "Over $1000": 0}

        price_query = select(Product.price).where(Product.price.isnot(None))
        price_result = await db.execute(price_query)
        prices = price_result.scalars().all()

        for price in prices:
            if price < 50:
                price_ranges["Under $50"] += 1
            elif price < 200:
                price_ranges["$50-$200"] += 1
            elif price < 500:
                price_ranges["$200-$500"] += 1
            elif price < 1000:
                price_ranges["$500-$1000"] += 1
            else:
                price_ranges["Over $1000"] += 1

        # Availability
        availability_query = select(Product.is_available, func.count(Product.id)).group_by(Product.is_available)
        availability_result = await db.execute(availability_query)
        availability = {"Available": 0, "Out of Stock": 0}

        for is_available, count in availability_result.all():
            if is_available:
                availability["Available"] = count
            else:
                availability["Out of Stock"] = count

        return ProductStatsResponse(
            total_products=total_products,
            by_source=by_source,
            by_category=by_category,
            price_ranges=price_ranges,
            availability=availability,
        )

    except Exception as e:
        logger.error(f"Error fetching product stats: {e}")
        raise HTTPException(status_code=500, detail="Error fetching statistics")
