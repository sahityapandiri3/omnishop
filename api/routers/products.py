"""
Product API routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
import logging

from api.core.database import get_db
from api.schemas.products import (
    ProductSchema, ProductSummarySchema, ProductDetailResponse,
    ProductSearchResponse, ProductQuery, ProductFilters,
    CategorySchema, ProductStatsResponse
)
from database.models import Product, Category, ProductImage, ProductAttribute

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["products"])


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
    db: AsyncSession = Depends(get_db)
):
    """Get paginated product list with filtering and search"""
    try:
        logger.info("Starting get_products endpoint")

        # Build base query
        query = select(Product).options(selectinload(Product.category), selectinload(Product.images))
        logger.info("Base query built with eager loading")

        # Apply filters
        if search:
            query = query.where(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%"),
                    Product.brand.ilike(f"%{search}%")
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
                    Product.name.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%"),
                    Product.brand.ilike(f"%{search}%")
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
                product_summaries.append(ProductSummarySchema(
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
                    category=category
                ))
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
                "is_on_sale": is_on_sale
            }
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
        related_query = select(Product).where(
            and_(
                Product.category_id == product.category_id,
                Product.id != product.id,
                Product.is_available == True
            )
        ).limit(6)

        related_result = await db.execute(related_query)
        related_products = related_result.scalars().all()

        # Convert related products to summaries
        related_summaries = []
        for related in related_products:
            primary_image = None
            if related.images:
                primary_image = next((img for img in related.images if img.is_primary), related.images[0])

            related_summaries.append(ProductSummarySchema(
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
                category=related.category
            ))

        return ProductDetailResponse(
            product=ProductSchema.from_orm(product),
            related_products=related_summaries
        )

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
        category_query = select(Category.name, func.count(Product.id)).join(
            Product, Category.id == Product.category_id, isouter=True
        ).group_by(Category.name)
        category_result = await db.execute(category_query)
        by_category = {row[0] or "Uncategorized": row[1] for row in category_result.all()}

        # Price ranges
        price_ranges = {
            "Under $50": 0,
            "$50-$200": 0,
            "$200-$500": 0,
            "$500-$1000": 0,
            "Over $1000": 0
        }

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
            availability=availability
        )

    except Exception as e:
        logger.error(f"Error fetching product stats: {e}")
        raise HTTPException(status_code=500, detail="Error fetching statistics")