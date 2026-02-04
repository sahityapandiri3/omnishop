"""
Product API routes
"""
import json
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
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from database.models import Category, Product, ProductAttribute, ProductImage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["products"])

# Embedding service singleton for semantic search
_embedding_service = None


def _get_embedding_service():
    """Lazily initialize the embedding service for semantic search."""
    global _embedding_service
    if _embedding_service is None:
        try:
            from services.embedding_service import EmbeddingService

            _embedding_service = EmbeddingService()
            logger.info("[SEARCH] Embedding service initialized for public search")
        except Exception as e:
            logger.warning(f"[SEARCH] Could not initialize embedding service: {e}")
            return None
    return _embedding_service


async def _semantic_search(
    query_text: str,
    db: AsyncSession,
    source_websites: Optional[List[str]] = None,
    category_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 10000,
) -> Dict[int, float]:
    """
    Perform semantic search using embeddings.
    Returns dict mapping product_id to similarity score.
    """
    embedding_service = _get_embedding_service()
    if not embedding_service:
        return {}

    query_embedding = await embedding_service.get_query_embedding(query_text)
    if not query_embedding:
        return {}

    # Fetch products with embeddings
    emb_query = (
        select(Product.id, Product.embedding).where(Product.is_available.is_(True)).where(Product.embedding.isnot(None))
    )
    if source_websites:
        emb_query = emb_query.where(Product.source_website.in_(source_websites))
    if category_id:
        emb_query = emb_query.where(Product.category_id == category_id)
    if min_price is not None:
        emb_query = emb_query.where(Product.price >= min_price)
    if max_price is not None:
        emb_query = emb_query.where(Product.price <= max_price)

    result = await db.execute(emb_query)
    rows = result.fetchall()

    if not rows:
        return {}

    scores: Dict[int, float] = {}
    for product_id, embedding_json in rows:
        try:
            product_embedding = json.loads(embedding_json)
            similarity = embedding_service.compute_cosine_similarity(query_embedding, product_embedding)
            scores[product_id] = similarity
        except Exception:
            continue

    # Sort and limit
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return dict(sorted_scores)


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

        # Step 1: Try semantic search for the query
        semantic_ids: Dict[int, float] = {}
        if query:
            try:
                semantic_ids = await _semantic_search(
                    query_text=query,
                    db=db,
                    source_websites=source_websites,
                    category_id=category_id,
                    min_price=min_price,
                    max_price=max_price,
                )
                logger.info(f"[SEARCH] Semantic search returned {len(semantic_ids)} products")
            except Exception as e:
                logger.warning(f"[SEARCH] Semantic search failed, using keyword only: {e}")

        # Step 2: Keyword search (ILIKE)
        # Split query into words and match each word individually for better recall.
        # Also generate singular/plural variants so "single seaters" matches "single seater".
        base_query = select(Product).options(selectinload(Product.category), selectinload(Product.images))

        if query:
            query_words = [w.strip() for w in query.split() if w.strip()]
            # Generate word variants (singular/plural)
            word_variants = set()
            for w in query_words:
                word_variants.add(w)
                if w.endswith("s") and len(w) > 3:
                    word_variants.add(w[:-1])  # seaters -> seater
                elif w.endswith("ies") and len(w) > 4:
                    word_variants.add(w[:-3] + "y")  # categories -> category
                else:
                    word_variants.add(w + "s")  # seater -> seaters

            # Each variant should match in name, description, or brand
            word_conditions = []
            for variant in word_variants:
                word_conditions.append(Product.name.ilike(f"%{variant}%"))
                word_conditions.append(Product.description.ilike(f"%{variant}%"))
                word_conditions.append(Product.brand.ilike(f"%{variant}%"))
            # Also match the full original query as a phrase
            word_conditions.append(Product.name.ilike(f"%{query}%"))
            word_conditions.append(Product.description.ilike(f"%{query}%"))
            word_conditions.append(Product.brand.ilike(f"%{query}%"))

            base_query = base_query.where(or_(*word_conditions))

        if category_id:
            base_query = base_query.where(Product.category_id == category_id)

        # Support comma-separated source websites with IN filter
        if source_websites:
            base_query = base_query.where(Product.source_website.in_(source_websites))

        if min_price is not None:
            base_query = base_query.where(Product.price >= min_price)
        if max_price is not None:
            base_query = base_query.where(Product.price <= max_price)

        base_query = base_query.where(Product.is_available == True)

        # Execute keyword search
        keyword_result = await db.execute(base_query)
        keyword_products = keyword_result.scalars().unique().all()
        keyword_ids = {p.id for p in keyword_products}

        # Step 3: Merge results - semantic matches that aren't in keyword results
        # Fetch high-similarity semantic-only products (similarity >= 0.3)
        SIMILARITY_THRESHOLD = 0.3
        HIGH_SIMILARITY = 0.5
        semantic_only_ids = [
            pid for pid, score in semantic_ids.items() if pid not in keyword_ids and score >= SIMILARITY_THRESHOLD
        ]

        semantic_only_products = []
        if semantic_only_ids:
            sem_query = (
                select(Product)
                .options(selectinload(Product.category), selectinload(Product.images))
                .where(Product.id.in_(semantic_only_ids))
            )
            sem_result = await db.execute(sem_query)
            semantic_only_products = list(sem_result.scalars().unique().all())

        # Combine and rank: keyword matches first (boosted if also semantic), then semantic-only
        # Track which products are primary (keyword) matches for the frontend
        all_products = []  # List of (product, is_primary) tuples
        seen_ids = set()

        # Primary: keyword matches, sorted by semantic score if available
        keyword_list = sorted(
            keyword_products,
            key=lambda p: semantic_ids.get(p.id, 0),
            reverse=True,
        )
        for p in keyword_list:
            if p.id not in seen_ids:
                all_products.append((p, True))
                seen_ids.add(p.id)

        # Related: semantic-only matches, sorted by similarity
        semantic_sorted = sorted(
            semantic_only_products,
            key=lambda p: semantic_ids.get(p.id, 0),
            reverse=True,
        )
        for p in semantic_sorted:
            if p.id not in seen_ids:
                all_products.append((p, False))
                seen_ids.add(p.id)

        total_primary = len(keyword_products)
        total_related = len(semantic_only_products)
        total = total_primary + total_related

        # Apply pagination
        offset = (page - 1) * page_size
        paginated = all_products[offset : offset + page_size]

        formatted_products = []
        for product, is_primary in paginated:
            formatted = _format_product(product)
            formatted["is_primary_match"] = is_primary
            formatted_products.append(formatted)
        has_more = (offset + len(paginated)) < total

        return {
            "products": formatted_products,
            "total": total,
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

        # Apply filters
        if search:
            # Use PostgreSQL regex with word boundaries (\y) for accurate matching
            # This prevents "bed" from matching "bedspread", "bedside", etc.
            escaped_search = re.escape(search)
            query = query.where(
                or_(
                    Product.name.op("~*")(rf"\y{escaped_search}\y"),
                    Product.description.op("~*")(rf"\y{escaped_search}\y"),
                    Product.brand.op("~*")(rf"\y{escaped_search}\y"),
                )
            )

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

        # Get total count
        count_query = select(func.count()).select_from(Product)
        if search:
            count_query = count_query.where(
                or_(
                    Product.name.op("~*")(rf"\y{escaped_search}\y"),
                    Product.description.op("~*")(rf"\y{escaped_search}\y"),
                    Product.brand.op("~*")(rf"\y{escaped_search}\y"),
                )
            )

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
        logger.info("Converting products to summary schemas")
        product_summaries = []
        for idx, product in enumerate(products):
            try:
                logger.info(f"Processing product {idx+1}/{len(products)}: {product.id}")

                primary_image = None
                logger.info(f"  - Accessing product.images for product {product.id}")
                if product.images:
                    primary_image = next((img for img in product.images if img.is_primary), product.images[0])
                    logger.info(f"  - Found primary image: {primary_image.id if primary_image else None}")

                logger.info(f"  - Accessing product.category for product {product.id}")
                category = product.category
                logger.info(f"  - Category: {category.name if category else None}")

                logger.info(f"  - Creating ProductSummarySchema for product {product.id}")
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
                logger.info(f"  - Successfully processed product {product.id}")
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
