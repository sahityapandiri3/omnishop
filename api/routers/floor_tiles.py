"""
Floor Tiles Router

Provides endpoints for browsing the floor tile catalog with filtering.
Mirrors the wall_textures router pattern but with tile-specific filters
(vendor, size, finish, look, color).
"""

import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from schemas.floor_tiles import FloorTileFilterOptions, FloorTileLightSchema, FloorTileSchema, FloorTilesResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from core.database import get_db
from database.models import FloorTile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/floor-tiles")


@router.get("/", response_model=FloorTilesResponse)
async def get_floor_tiles(
    vendor: Optional[List[str]] = Query(None, description="Filter by vendor(s)"),
    size: Optional[List[str]] = Query(None, description="Filter by size(s)"),
    finish: Optional[List[str]] = Query(None, description="Filter by finish(es)"),
    look: Optional[List[str]] = Query(None, description="Filter by look(s)"),
    color: Optional[List[str]] = Query(None, description="Filter by color(s)"),
    db: AsyncSession = Depends(get_db),
):
    """
    List floor tiles with optional multi-select filters and filter metadata.

    Each filter accepts multiple values (e.g., ?finish=Glossy&finish=Matte).
    Returns lightweight tile data (no base64 fields) for efficient listing,
    plus available filter values for the UI.
    """
    try:
        # Build query — exclude heavy base64 columns for listing
        query = (
            select(FloorTile)
            .options(defer(FloorTile.swatch_data), defer(FloorTile.image_data))
            .where(FloorTile.is_active == True)
            .order_by(FloorTile.display_order, FloorTile.name)
        )

        if vendor:
            query = query.where(FloorTile.vendor.in_(vendor))
        if size:
            query = query.where(FloorTile.size.in_(size))
        if finish:
            query = query.where(FloorTile.finish.in_(finish))
        if look:
            query = query.where(FloorTile.look.in_(look))
        if color:
            query = query.where(FloorTile.color.in_(color))

        result = await db.execute(query)
        tiles = result.scalars().all()

        # Build tile list
        tile_schemas = [FloorTileLightSchema.model_validate(t) for t in tiles]

        # Get filter metadata — distinct values from ALL active tiles (not filtered subset)
        filters = await _get_filter_options(db)

        return FloorTilesResponse(
            tiles=tile_schemas,
            filters=filters,
            total_count=len(tile_schemas),
        )

    except Exception as e:
        logger.error(f"Error fetching floor tiles: {e}")
        raise HTTPException(status_code=500, detail="Error fetching floor tiles")


@router.get("/filters", response_model=FloorTileFilterOptions)
async def get_floor_tile_filters(
    db: AsyncSession = Depends(get_db),
):
    """Get distinct filter values for floor tiles."""
    try:
        return await _get_filter_options(db)
    except Exception as e:
        logger.error(f"Error fetching floor tile filters: {e}")
        raise HTTPException(status_code=500, detail="Error fetching floor tile filters")


@router.get("/{tile_id}", response_model=FloorTileSchema)
async def get_floor_tile(
    tile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific floor tile by ID (includes swatch_data for visualization)."""
    try:
        query = select(FloorTile).where(FloorTile.id == tile_id)
        result = await db.execute(query)
        tile = result.scalar_one_or_none()

        if not tile:
            raise HTTPException(status_code=404, detail="Floor tile not found")

        return FloorTileSchema.model_validate(tile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching floor tile {tile_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching floor tile")


@router.get("/{tile_id}/image")
async def get_floor_tile_image(
    tile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the display image for a floor tile as binary (for <img> tags)."""
    try:
        query = select(FloorTile.image_data).where(FloorTile.id == tile_id)
        result = await db.execute(query)
        row = result.one_or_none()

        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Floor tile image not found")

        image_data = row[0]

        # Strip data URL prefix if present
        if image_data.startswith("data:"):
            header, b64_data = image_data.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            image_bytes = base64.b64decode(b64_data)
        else:
            mime_type = "image/jpeg"
            image_bytes = base64.b64decode(image_data)

        return Response(
            content=image_bytes,
            media_type=mime_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching floor tile image {tile_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching floor tile image")


@router.get("/{tile_id}/swatch")
async def get_floor_tile_swatch(
    tile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the swatch image for a floor tile as binary."""
    try:
        query = select(FloorTile.swatch_data).where(FloorTile.id == tile_id)
        result = await db.execute(query)
        row = result.one_or_none()

        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Floor tile swatch not found")

        swatch_data = row[0]

        # Strip data URL prefix if present
        if swatch_data.startswith("data:"):
            header, b64_data = swatch_data.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            image_bytes = base64.b64decode(b64_data)
        else:
            mime_type = "image/jpeg"
            image_bytes = base64.b64decode(swatch_data)

        return Response(
            content=image_bytes,
            media_type=mime_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching floor tile swatch {tile_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching floor tile swatch")


async def _get_filter_options(db: AsyncSession) -> FloorTileFilterOptions:
    """Fetch distinct filter values from all active floor tiles."""
    base_filter = FloorTile.is_active == True

    # Vendors
    vendors_q = await db.execute(
        select(FloorTile.vendor).where(base_filter).where(FloorTile.vendor.isnot(None)).distinct().order_by(FloorTile.vendor)
    )
    vendors = [r[0] for r in vendors_q.all() if r[0]]

    # Sizes
    sizes_q = await db.execute(
        select(FloorTile.size).where(base_filter).where(FloorTile.size.isnot(None)).distinct().order_by(FloorTile.size)
    )
    sizes = [r[0] for r in sizes_q.all() if r[0]]

    # Finishes
    finishes_q = await db.execute(
        select(FloorTile.finish).where(base_filter).where(FloorTile.finish.isnot(None)).distinct().order_by(FloorTile.finish)
    )
    finishes = [r[0] for r in finishes_q.all() if r[0]]

    # Looks
    looks_q = await db.execute(
        select(FloorTile.look).where(base_filter).where(FloorTile.look.isnot(None)).distinct().order_by(FloorTile.look)
    )
    looks = [r[0] for r in looks_q.all() if r[0]]

    # Colors
    colors_q = await db.execute(
        select(FloorTile.color).where(base_filter).where(FloorTile.color.isnot(None)).distinct().order_by(FloorTile.color)
    )
    colors = [r[0] for r in colors_q.all() if r[0]]

    return FloorTileFilterOptions(
        vendors=vendors,
        sizes=sizes,
        finishes=finishes,
        looks=looks,
        colors=colors,
    )
