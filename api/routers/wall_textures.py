"""
Wall Textures API routes

Provides endpoints for fetching the wall texture catalog (Asian Paints and others)
for use in the design studio wall texture visualization feature.
"""
import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from schemas.wall_textures import (
    TEXTURE_TYPE_LABELS,
    TextureBrandSchema,
    TextureType,
    TextureTypeSchema,
    WallTexturesGroupedResponse,
    WallTextureVariantLightSchema,
    WallTextureVariantSchema,
    WallTextureWithVariantsLightSchema,
    WallTextureWithVariantsSchema,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, selectinload

from core.database import get_db
from database.models import TextureType as DBTextureType
from database.models import WallTexture, WallTextureVariant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wall-textures", tags=["wall-textures"])


@router.get("/", response_model=WallTexturesGroupedResponse)
async def get_wall_textures(
    brand: Optional[str] = Query(None, description="Filter by brand/vendor"),
    texture_type: Optional[TextureType] = Query(None, description="Filter by texture type"),
    collection: Optional[str] = Query(None, description="Filter by collection"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all wall textures with their variants, optionally filtered.

    Returns textures grouped with their color variants, along with
    available brands and texture types for filter UI.
    """
    try:
        # Build base query with eager loading of variants (but defer heavy image_data column)
        query = (
            select(WallTexture)
            .options(selectinload(WallTexture.variants).defer(WallTextureVariant.image_data))
            .where(WallTexture.is_active == True)
        )

        if brand:
            query = query.where(WallTexture.brand == brand)

        if texture_type:
            db_type = DBTextureType(texture_type.value)
            query = query.where(WallTexture.texture_type == db_type)

        if collection:
            query = query.where(WallTexture.collection == collection)

        query = query.order_by(WallTexture.display_order, WallTexture.name)

        result = await db.execute(query)
        textures = result.scalars().unique().all()

        # Convert to lightweight response schemas (no image_data for fast loading)
        texture_schemas = []
        for texture in textures:
            active_variants = [
                WallTextureVariantLightSchema(
                    id=v.id,
                    code=v.code,
                    name=v.name,
                    image_url=v.image_url,
                    color_family=v.color_family,
                    is_active=v.is_active,
                    display_order=v.display_order,
                )
                for v in texture.variants
                if v.is_active
            ]
            if active_variants:  # Only include textures with active variants
                texture_schemas.append(
                    WallTextureWithVariantsLightSchema(
                        id=texture.id,
                        name=texture.name,
                        collection=texture.collection,
                        texture_type=TextureType(texture.texture_type.value) if texture.texture_type else None,
                        brand=texture.brand,
                        description=texture.description,
                        variants=active_variants,
                    )
                )

        # Get brand counts
        brand_query = (
            select(WallTexture.brand, func.count(WallTexture.id).label("count"))
            .where(WallTexture.is_active == True)
            .group_by(WallTexture.brand)
            .order_by(WallTexture.brand)
        )
        brand_result = await db.execute(brand_query)
        brands = [TextureBrandSchema(name=row[0], texture_count=row[1]) for row in brand_result.all()]

        # Get texture type counts
        type_query = (
            select(WallTexture.texture_type, func.count(WallTexture.id).label("count"))
            .where(WallTexture.is_active == True)
            .where(WallTexture.texture_type.isnot(None))
            .group_by(WallTexture.texture_type)
        )
        type_result = await db.execute(type_query)
        type_counts = {row[0].value: row[1] for row in type_result.all() if row[0]}

        # Build texture types list with all types
        texture_types = []
        for t_type in TextureType:
            texture_types.append(
                TextureTypeSchema(
                    value=t_type,
                    label=TEXTURE_TYPE_LABELS.get(t_type, t_type.value),
                    texture_count=type_counts.get(t_type.value, 0),
                )
            )

        return WallTexturesGroupedResponse(
            textures=texture_schemas,
            brands=brands,
            texture_types=texture_types,
            total_count=len(texture_schemas),
        )

    except Exception as e:
        logger.error(f"Error fetching wall textures: {e}")
        raise HTTPException(status_code=500, detail="Error fetching wall textures")


@router.get("/brands", response_model=List[TextureBrandSchema])
async def get_texture_brands(
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of available texture vendors/brands with counts.

    Returns all brands that have active textures.
    """
    try:
        query = (
            select(WallTexture.brand, func.count(WallTexture.id).label("count"))
            .where(WallTexture.is_active == True)
            .group_by(WallTexture.brand)
            .order_by(WallTexture.brand)
        )
        result = await db.execute(query)

        return [TextureBrandSchema(name=row[0], texture_count=row[1]) for row in result.all()]

    except Exception as e:
        logger.error(f"Error fetching texture brands: {e}")
        raise HTTPException(status_code=500, detail="Error fetching texture brands")


@router.get("/types", response_model=List[TextureTypeSchema])
async def get_texture_types(
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of texture types with labels and counts.

    Returns all texture types with human-readable labels and
    the count of active textures in each type.
    """
    try:
        query = (
            select(WallTexture.texture_type, func.count(WallTexture.id).label("count"))
            .where(WallTexture.is_active == True)
            .where(WallTexture.texture_type.isnot(None))
            .group_by(WallTexture.texture_type)
        )
        result = await db.execute(query)
        type_counts = {row[0].value: row[1] for row in result.all() if row[0]}

        texture_types = []
        for t_type in TextureType:
            texture_types.append(
                TextureTypeSchema(
                    value=t_type,
                    label=TEXTURE_TYPE_LABELS.get(t_type, t_type.value),
                    texture_count=type_counts.get(t_type.value, 0),
                )
            )

        return texture_types

    except Exception as e:
        logger.error(f"Error fetching texture types: {e}")
        raise HTTPException(status_code=500, detail="Error fetching texture types")


@router.get("/collections", response_model=List[str])
async def get_texture_collections(
    brand: Optional[str] = Query(None, description="Filter by brand"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of available texture collections.

    Returns distinct collection names, optionally filtered by brand.
    """
    try:
        query = (
            select(WallTexture.collection)
            .where(WallTexture.is_active == True)
            .where(WallTexture.collection.isnot(None))
            .distinct()
            .order_by(WallTexture.collection)
        )

        if brand:
            query = query.where(WallTexture.brand == brand)

        result = await db.execute(query)
        return [row[0] for row in result.all() if row[0]]

    except Exception as e:
        logger.error(f"Error fetching texture collections: {e}")
        raise HTTPException(status_code=500, detail="Error fetching texture collections")


@router.get("/{texture_id}", response_model=WallTextureWithVariantsSchema)
async def get_wall_texture(
    texture_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific wall texture by ID with all its variants."""
    try:
        query = select(WallTexture).options(selectinload(WallTexture.variants)).where(WallTexture.id == texture_id)
        result = await db.execute(query)
        texture = result.scalar_one_or_none()

        if not texture:
            raise HTTPException(status_code=404, detail="Wall texture not found")

        active_variants = [WallTextureVariantSchema.model_validate(v) for v in texture.variants if v.is_active]

        return WallTextureWithVariantsSchema(
            id=texture.id,
            name=texture.name,
            collection=texture.collection,
            texture_type=TextureType(texture.texture_type.value) if texture.texture_type else None,
            brand=texture.brand,
            description=texture.description,
            variants=active_variants,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching wall texture {texture_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching wall texture")


@router.get("/variant/{variant_id}", response_model=WallTextureVariantSchema)
async def get_texture_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific texture variant by ID."""
    try:
        query = select(WallTextureVariant).where(WallTextureVariant.id == variant_id)
        result = await db.execute(query)
        variant = result.scalar_one_or_none()

        if not variant:
            raise HTTPException(status_code=404, detail="Texture variant not found")

        return WallTextureVariantSchema.model_validate(variant)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching texture variant {variant_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching texture variant")


@router.get("/variant/{variant_id}/image")
async def get_texture_variant_image(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the image for a texture variant as a binary response.

    Returns the image directly (not JSON-wrapped) for use in <img> tags.
    Supports browser caching via Cache-Control headers.
    """
    try:
        query = select(WallTextureVariant.image_data).where(WallTextureVariant.id == variant_id)
        result = await db.execute(query)
        row = result.one_or_none()

        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Texture variant image not found")

        image_data = row[0]

        # Strip data URL prefix if present
        if image_data.startswith("data:"):
            # Extract mime type and base64 data
            header, b64_data = image_data.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            image_bytes = base64.b64decode(b64_data)
        else:
            # Assume raw base64 JPEG
            mime_type = "image/jpeg"
            image_bytes = base64.b64decode(image_data)

        return Response(
            content=image_bytes,
            media_type=mime_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching texture variant image {variant_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching texture variant image")


@router.get("/variant/code/{code}", response_model=WallTextureVariantSchema)
async def get_texture_variant_by_code(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a texture variant by its code."""
    try:
        query = select(WallTextureVariant).where(WallTextureVariant.code == code)
        result = await db.execute(query)
        variant = result.scalar_one_or_none()

        if not variant:
            raise HTTPException(status_code=404, detail=f"Texture variant with code '{code}' not found")

        return WallTextureVariantSchema.model_validate(variant)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching texture variant by code {code}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching texture variant")
