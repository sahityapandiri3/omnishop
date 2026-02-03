"""
Pydantic schemas for wall texture API endpoints

Provides schemas for textures, texture variants, and visualization requests.
Textures are grouped by base name with multiple color variants per texture.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field
from schemas.wall_colors import WallColorFamily


class TextureType(str, Enum):
    """Texture finish types for wall textures"""

    MARBLE = "marble"
    VELVET = "velvet"
    STONE = "stone"
    CONCRETE = "concrete"
    THREE_D = "3d"
    WALL_TILE = "wall_tile"
    STUCCO = "stucco"
    RUST = "rust"
    OTHER = "other"


# Human-readable labels for texture types
TEXTURE_TYPE_LABELS = {
    TextureType.MARBLE: "Marble",
    TextureType.VELVET: "Velvet",
    TextureType.STONE: "Stone",
    TextureType.CONCRETE: "Concrete",
    TextureType.THREE_D: "3D",
    TextureType.WALL_TILE: "Wall Tile",
    TextureType.STUCCO: "Stucco",
    TextureType.RUST: "Rust",
    TextureType.OTHER: "Other",
}


class WallTextureVariantSchema(BaseModel):
    """Individual texture variant with image data"""

    id: int
    code: str
    name: Optional[str] = None
    image_data: str = Field(..., description="Base64 encoded room/wall shot image")
    image_url: Optional[str] = None
    swatch_url: Optional[str] = Field(None, description="URL for the texture swatch pattern image")
    color_family: Optional[WallColorFamily] = None
    is_active: bool = True
    display_order: int = 0

    class Config:
        from_attributes = True


class WallTextureVariantLightSchema(BaseModel):
    """Lightweight texture variant without inline image data (for list endpoints)"""

    id: int
    code: str
    name: Optional[str] = None
    image_url: Optional[str] = None
    swatch_url: Optional[str] = None
    color_family: Optional[WallColorFamily] = None
    is_active: bool = True
    display_order: int = 0

    class Config:
        from_attributes = True


class WallTextureSchema(BaseModel):
    """Base wall texture without variants"""

    id: int
    name: str
    collection: Optional[str] = None
    texture_type: Optional[TextureType] = None
    brand: str = "Asian Paints"
    description: Optional[str] = None
    is_active: bool = True
    display_order: int = 0

    class Config:
        from_attributes = True


class WallTextureWithVariantsSchema(BaseModel):
    """Wall texture with all its color variants (includes image data)"""

    id: int
    name: str
    collection: Optional[str] = None
    texture_type: Optional[TextureType] = None
    brand: str = "Asian Paints"
    description: Optional[str] = None
    variants: List[WallTextureVariantSchema] = []

    class Config:
        from_attributes = True


class WallTextureWithVariantsLightSchema(BaseModel):
    """Wall texture with lightweight variants (no inline images - for list endpoints)"""

    id: int
    name: str
    collection: Optional[str] = None
    texture_type: Optional[TextureType] = None
    brand: str = "Asian Paints"
    description: Optional[str] = None
    variants: List[WallTextureVariantLightSchema] = []

    class Config:
        from_attributes = True


class TextureTypeSchema(BaseModel):
    """Texture type with label"""

    value: TextureType
    label: str
    texture_count: int = 0


class TextureBrandSchema(BaseModel):
    """Texture brand with count"""

    name: str
    texture_count: int = 0


class WallTexturesGroupedResponse(BaseModel):
    """Wall textures with metadata for filters (lightweight, no inline images)"""

    textures: List[WallTextureWithVariantsLightSchema]
    brands: List[TextureBrandSchema]
    texture_types: List[TextureTypeSchema]
    total_count: int = 0


class ChangeWallTextureRequest(BaseModel):
    """Request to change wall texture in visualization"""

    room_image: str = Field(..., description="Base64 encoded current visualization image")
    texture_variant_id: int = Field(..., description="ID of the texture variant to apply")


class ChangeWallTextureResponse(BaseModel):
    """Response from wall texture change"""

    success: bool
    rendered_image: Optional[str] = Field(None, description="Base64 encoded result image")
    error_message: Optional[str] = None
    processing_time: float = Field(0.0, description="Processing time in seconds")
    texture_name: Optional[str] = None
    texture_type: Optional[str] = None
