"""
Wall Colors API routes

Provides endpoints for fetching the wall color catalog (Asian Paints)
for use in the design studio wall color visualization feature.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.wall_colors import (
    WALL_COLOR_FAMILY_LABELS,
    WallColorFamily,
    WallColorFamilySchema,
    WallColorSchema,
    WallColorsGroupedResponse,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from database.models import WallColor
from database.models import WallColorFamily as DBWallColorFamily

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wall-colors", tags=["wall-colors"])


@router.get("/", response_model=List[WallColorSchema])
async def get_wall_colors(
    family: Optional[WallColorFamily] = Query(None, description="Filter by color family"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all wall colors, optionally filtered by family or brand.

    Colors are ordered by family and then by display_order within each family.
    """
    try:
        query = select(WallColor).where(WallColor.is_active == True)

        if family:
            # Convert schema enum to DB enum
            db_family = DBWallColorFamily(family.value)
            query = query.where(WallColor.family == db_family)

        if brand:
            query = query.where(WallColor.brand == brand)

        # Order by family then display_order
        query = query.order_by(WallColor.family, WallColor.display_order, WallColor.name)

        result = await db.execute(query)
        colors = result.scalars().all()

        return [WallColorSchema.model_validate(color) for color in colors]

    except Exception as e:
        logger.error(f"Error fetching wall colors: {e}")
        raise HTTPException(status_code=500, detail="Error fetching wall colors")


@router.get("/families", response_model=List[WallColorFamilySchema])
async def get_color_families(
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of color families with labels and color counts.

    Returns all color families with human-readable labels and
    the count of active colors in each family.
    """
    try:
        # Get color counts per family
        query = (
            select(WallColor.family, func.count(WallColor.id).label("count"))
            .where(WallColor.is_active == True)
            .group_by(WallColor.family)
        )
        result = await db.execute(query)
        family_counts = {row[0].value: row[1] for row in result.all()}

        # Build response with all families (even if 0 colors)
        families = []
        for family in WallColorFamily:
            families.append(
                WallColorFamilySchema(
                    value=family,
                    label=WALL_COLOR_FAMILY_LABELS.get(family, family.value),
                    color_count=family_counts.get(family.value, 0),
                )
            )

        return families

    except Exception as e:
        logger.error(f"Error fetching color families: {e}")
        raise HTTPException(status_code=500, detail="Error fetching color families")


@router.get("/grouped", response_model=WallColorsGroupedResponse)
async def get_wall_colors_grouped(
    db: AsyncSession = Depends(get_db),
):
    """
    Get all wall colors grouped by family.

    Returns a structure optimized for rendering the wall color panel
    with family headers and swatches grouped together.
    """
    try:
        # Get all active colors
        query = (
            select(WallColor)
            .where(WallColor.is_active == True)
            .order_by(WallColor.family, WallColor.display_order, WallColor.name)
        )
        result = await db.execute(query)
        colors = result.scalars().all()

        # Group colors by family
        colors_by_family = {}
        family_counts = {}

        for color in colors:
            family_key = color.family.value
            if family_key not in colors_by_family:
                colors_by_family[family_key] = []
                family_counts[family_key] = 0

            colors_by_family[family_key].append(WallColorSchema.model_validate(color))
            family_counts[family_key] += 1

        # Build family list
        families = []
        for family in WallColorFamily:
            families.append(
                WallColorFamilySchema(
                    value=family,
                    label=WALL_COLOR_FAMILY_LABELS.get(family, family.value),
                    color_count=family_counts.get(family.value, 0),
                )
            )

        return WallColorsGroupedResponse(
            families=families,
            colors=colors_by_family,
        )

    except Exception as e:
        logger.error(f"Error fetching grouped wall colors: {e}")
        raise HTTPException(status_code=500, detail="Error fetching wall colors")


@router.get("/{color_id}", response_model=WallColorSchema)
async def get_wall_color(
    color_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific wall color by ID."""
    try:
        query = select(WallColor).where(WallColor.id == color_id)
        result = await db.execute(query)
        color = result.scalar_one_or_none()

        if not color:
            raise HTTPException(status_code=404, detail="Wall color not found")

        return WallColorSchema.model_validate(color)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching wall color {color_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching wall color")


@router.get("/code/{color_code}", response_model=WallColorSchema)
async def get_wall_color_by_code(
    color_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a wall color by its Asian Paints code (e.g., L134)."""
    try:
        query = select(WallColor).where(WallColor.code == color_code)
        result = await db.execute(query)
        color = result.scalar_one_or_none()

        if not color:
            raise HTTPException(status_code=404, detail=f"Wall color with code '{color_code}' not found")

        return WallColorSchema.model_validate(color)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching wall color by code {color_code}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching wall color")
