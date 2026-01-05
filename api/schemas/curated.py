"""
Pydantic schemas for curated looks API endpoints
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RoomType(str, Enum):
    """Available room types for curated looks"""

    living_room = "living_room"
    bedroom = "bedroom"


class GenerationStatus(str, Enum):
    """Status for curated look generation"""

    pending = "pending"
    generating = "generating"
    completed = "completed"
    failed = "failed"


class BudgetTier(str, Enum):
    """Budget tiers for curated looks"""

    essential = "essential"  # < ₹2L
    value = "value"  # ₹2L – ₹4L
    mid = "mid"  # ₹4L – ₹8L
    premium = "premium"  # ₹8L – ₹15L
    ultra_luxury = "ultra_luxury"  # ₹15L+


# Product schemas for curated looks
class CuratedLookProductBase(BaseModel):
    """Base schema for a product in a curated look"""

    product_id: int
    product_type: Optional[str] = None
    quantity: int = 1
    display_order: int = 0


class CuratedLookProductCreate(CuratedLookProductBase):
    """Schema for adding a product to a curated look"""

    pass


class CuratedLookProductSchema(BaseModel):
    """Product included in a curated look with full details"""

    id: int
    name: str
    price: Optional[float] = None
    image_url: Optional[str] = None
    source_website: str
    source_url: Optional[str] = None
    product_type: Optional[str] = None
    quantity: int = 1
    description: Optional[str] = None

    class Config:
        from_attributes = True


# Curated look schemas
class CuratedLookBase(BaseModel):
    """Base schema for curated look"""

    title: str = Field(..., max_length=200)
    style_theme: str = Field(..., max_length=100)
    style_description: Optional[str] = None
    style_labels: List[str] = []  # ["modern", "modern_luxury", "indian_contemporary"]
    room_type: RoomType


class CuratedLookCreate(CuratedLookBase):
    """Schema for creating a new curated look"""

    room_image: Optional[str] = None  # Base64 encoded
    visualization_image: Optional[str] = None  # Base64 encoded
    budget_tier: Optional[BudgetTier] = None  # Budget tier for filtering
    is_published: bool = False
    display_order: int = 0
    product_ids: List[int] = []  # Products to include with types
    product_types: Optional[List[str]] = None  # Types for each product
    product_quantities: Optional[List[int]] = None  # Quantities for each product


class CuratedLookUpdate(BaseModel):
    """Schema for updating a curated look"""

    title: Optional[str] = Field(None, max_length=200)
    style_theme: Optional[str] = Field(None, max_length=100)
    style_description: Optional[str] = None
    style_labels: Optional[List[str]] = None  # ["modern", "modern_luxury", "indian_contemporary"]
    room_type: Optional[RoomType] = None
    room_image: Optional[str] = None
    visualization_image: Optional[str] = None
    budget_tier: Optional[BudgetTier] = None  # Budget tier for filtering
    is_published: Optional[bool] = None
    display_order: Optional[int] = None
    # Product updates (optional - if provided, replaces all products)
    product_ids: Optional[List[int]] = None
    product_types: Optional[List[str]] = None
    product_quantities: Optional[List[int]] = None


class CuratedLookProductUpdate(BaseModel):
    """Schema for updating products in a curated look"""

    product_ids: List[int]
    product_types: Optional[List[str]] = None
    product_quantities: Optional[List[int]] = None


class CuratedLookSchema(BaseModel):
    """Complete curated look schema"""

    id: int
    title: str
    style_theme: str
    style_description: Optional[str] = None
    style_labels: List[str] = []
    room_type: str
    room_image: Optional[str] = None
    visualization_image: Optional[str] = None
    total_price: float = 0
    budget_tier: Optional[str] = None  # Budget tier for filtering
    is_published: bool = False
    display_order: int = 0
    products: List[CuratedLookProductSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CuratedLookSummarySchema(BaseModel):
    """Summary schema for curated look listings"""

    id: int
    title: str
    style_theme: str
    style_description: Optional[str] = None
    style_labels: List[str] = []
    room_type: str
    visualization_image: Optional[str] = None
    total_price: float = 0
    budget_tier: Optional[str] = None  # Budget tier for filtering
    is_published: bool = False
    display_order: int = 0
    product_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# Public API response schema (matches frontend CuratedLook interface)
class CuratedLookPublicSchema(BaseModel):
    """Public schema for curated looks (user-facing)"""

    look_id: str
    style_theme: str
    style_description: Optional[str] = None
    style_labels: List[str] = []
    room_image: Optional[str] = None  # Base room image for visualization
    visualization_image: Optional[str] = None
    products: List[CuratedLookProductSchema] = []
    total_price: float = 0
    generation_status: GenerationStatus = GenerationStatus.completed
    error_message: Optional[str] = None


class CuratedLooksPublicResponse(BaseModel):
    """Response schema for public curated looks endpoint"""

    session_id: str
    room_type: str
    looks: List[CuratedLookPublicSchema]
    generation_complete: bool = True


# Admin list response
class CuratedLookListResponse(BaseModel):
    """Response for admin curated looks list"""

    items: List[CuratedLookSummarySchema]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool
