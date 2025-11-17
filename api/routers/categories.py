"""
Category API routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import logging

from core.database import get_db
from schemas.products import CategorySchema
from database.models import Category, Product

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", response_model=List[CategorySchema])
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get all categories with product counts"""
    try:
        # Get categories with product counts
        query = select(
            Category,
            func.count(Product.id).label('product_count')
        ).join(
            Product, Category.id == Product.category_id, isouter=True
        ).group_by(Category.id).order_by(Category.name)

        result = await db.execute(query)
        categories_with_counts = result.all()

        categories = []
        for category, product_count in categories_with_counts:
            category_schema = CategorySchema.from_orm(category)
            category_schema.product_count = product_count
            categories.append(category_schema)

        return categories

    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(status_code=500, detail="Error fetching categories")


@router.get("/{category_id}", response_model=CategorySchema)
async def get_category(category_id: int, db: AsyncSession = Depends(get_db)):
    """Get category by ID with product count"""
    try:
        # Get category with product count
        query = select(
            Category,
            func.count(Product.id).label('product_count')
        ).join(
            Product, Category.id == Product.category_id, isouter=True
        ).where(Category.id == category_id).group_by(Category.id)

        result = await db.execute(query)
        category_data = result.first()

        if not category_data:
            raise HTTPException(status_code=404, detail="Category not found")

        category, product_count = category_data
        category_schema = CategorySchema.from_orm(category)
        category_schema.product_count = product_count

        return category_schema

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching category {category_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching category")


@router.get("/tree/hierarchical", response_model=List[CategorySchema])
async def get_category_tree(db: AsyncSession = Depends(get_db)):
    """Get hierarchical category tree structure"""
    try:
        # Get all categories
        query = select(Category).order_by(Category.name)
        result = await db.execute(query)
        all_categories = result.scalars().all()

        # Build hierarchy
        category_map = {}
        root_categories = []

        # First pass: create all category objects
        for category in all_categories:
            category_schema = CategorySchema.from_orm(category)
            category_map[category.id] = category_schema

        # Second pass: build hierarchy
        for category in all_categories:
            category_schema = category_map[category.id]

            if category.parent_id is None:
                root_categories.append(category_schema)
            else:
                parent = category_map.get(category.parent_id)
                if parent:
                    if not hasattr(parent, 'children'):
                        parent.children = []
                    parent.children.append(category_schema)

        return root_categories

    except Exception as e:
        logger.error(f"Error fetching category tree: {e}")
        raise HTTPException(status_code=500, detail="Error fetching category tree")