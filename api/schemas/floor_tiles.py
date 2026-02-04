"""
Pydantic schemas for floor tile API endpoints.

Floor tiles behave like wall textures: singular on canvas (only one at a time),
swatch-based visualization sent to Gemini. Different filters from furniture:
size, finish, look, color, vendor.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class FloorTileSchema(BaseModel):
    """Full floor tile with all data including swatch."""

    id: int
    product_code: str
    name: str
    description: Optional[str] = None
    size: str
    size_width_mm: Optional[int] = None
    size_height_mm: Optional[int] = None
    finish: Optional[str] = None
    look: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    vendor: str = "Nitco"
    product_url: Optional[str] = None
    swatch_data: Optional[str] = Field(None, description="Base64 swatch for AI visualization")
    swatch_url: Optional[str] = None
    image_url: Optional[str] = None
    image_data: Optional[str] = Field(None, description="Base64 display thumbnail")
    additional_images: Optional[list] = None
    is_active: bool = True
    display_order: int = 0

    class Config:
        from_attributes = True


class FloorTileLightSchema(BaseModel):
    """Lightweight floor tile without base64 data fields (for listing)."""

    id: int
    product_code: str
    name: str
    description: Optional[str] = None
    size: str
    size_width_mm: Optional[int] = None
    size_height_mm: Optional[int] = None
    finish: Optional[str] = None
    look: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    vendor: str = "Nitco"
    product_url: Optional[str] = None
    swatch_url: Optional[str] = None
    image_url: Optional[str] = None
    additional_images: Optional[list] = None
    is_active: bool = True
    display_order: int = 0

    class Config:
        from_attributes = True


class FloorTileFilterOptions(BaseModel):
    """Available filter values for floor tiles."""

    vendors: List[str] = []
    sizes: List[str] = []
    finishes: List[str] = []
    looks: List[str] = []
    colors: List[str] = []


class FloorTilesResponse(BaseModel):
    """Floor tiles listing with filter metadata."""

    tiles: List[FloorTileLightSchema]
    filters: FloorTileFilterOptions
    total_count: int = 0


class ChangeFloorTileRequest(BaseModel):
    """Request to change floor tile in visualization."""

    room_image: str = Field(..., description="Base64 encoded current visualization image")
    tile_id: int = Field(..., description="ID of the floor tile to apply")
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ChangeFloorTileResponse(BaseModel):
    """Response from floor tile change."""

    success: bool
    rendered_image: Optional[str] = Field(None, description="Base64 encoded result image")
    error_message: Optional[str] = None
    processing_time: float = Field(0.0, description="Processing time in seconds")
    tile_name: Optional[str] = None
    tile_size: Optional[str] = None
