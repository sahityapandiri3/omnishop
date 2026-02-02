"""
Pydantic schemas for wall color API endpoints
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class WallColorFamily(str, Enum):
    """Color families for wall paint categorization"""

    WHITES_OFFWHITES = "whites_offwhites"
    GREYS = "greys"
    BLUES = "blues"
    BROWNS = "browns"
    YELLOWS_GREENS = "yellows_greens"
    REDS_ORANGES = "reds_oranges"
    PURPLES_PINKS = "purples_pinks"


# Human-readable labels for color families
WALL_COLOR_FAMILY_LABELS = {
    WallColorFamily.WHITES_OFFWHITES: "Whites & Off-Whites",
    WallColorFamily.GREYS: "Greys",
    WallColorFamily.BLUES: "Blues",
    WallColorFamily.BROWNS: "Browns",
    WallColorFamily.YELLOWS_GREENS: "Yellows & Greens",
    WallColorFamily.REDS_ORANGES: "Reds & Oranges",
    WallColorFamily.PURPLES_PINKS: "Purples & Pinks",
}


class WallColorSchema(BaseModel):
    """Wall color response schema"""

    id: int
    code: str
    name: str
    hex_value: str
    family: WallColorFamily
    brand: str = "Asian Paints"
    is_active: bool = True
    display_order: int = 0

    class Config:
        from_attributes = True


class WallColorFamilySchema(BaseModel):
    """Color family with label"""

    value: WallColorFamily
    label: str
    color_count: int = 0


class WallColorsGroupedResponse(BaseModel):
    """Wall colors grouped by family"""

    families: List[WallColorFamilySchema]
    colors: dict  # family -> list of colors


class ChangeWallColorRequest(BaseModel):
    """Request to change wall color in visualization"""

    room_image: str = Field(..., description="Base64 encoded current visualization image")
    color_name: str = Field(..., description="Asian Paints color name")
    color_code: str = Field(..., description="Asian Paints color code (e.g., L134)")
    color_hex: str = Field(..., description="Hex color value (e.g., #F5F5F0)")


class ChangeWallColorResponse(BaseModel):
    """Response from wall color change"""

    success: bool
    rendered_image: Optional[str] = Field(None, description="Base64 encoded result image")
    error_message: Optional[str] = None
    processing_time: float = Field(0.0, description="Processing time in seconds")
