"""
Pydantic schemas for Home Styling API endpoints
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RoomType(str, Enum):
    """Available room types"""

    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"


class StyleType(str, Enum):
    """Available style types for V1"""

    MODERN = "modern"
    MODERN_LUXURY = "modern_luxury"
    INDIAN_CONTEMPORARY = "indian_contemporary"


class ColorPalette(str, Enum):
    """Available color palettes"""

    WARM = "warm"
    NEUTRAL = "neutral"
    COOL = "cool"
    BOLD = "bold"


class SessionStatus(str, Enum):
    """Session status values"""

    PREFERENCES = "preferences"
    UPLOAD = "upload"
    TIER_SELECTION = "tier_selection"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class TierType(str, Enum):
    """Available tiers"""

    FREE = "free"  # 1 view
    BASIC = "basic"  # 3 views
    PREMIUM = "premium"  # 6 views (coming soon)


class BudgetTier(str, Enum):
    """Budget tiers for curated looks filtering"""

    POCKET_FRIENDLY = "pocket_friendly"  # Under ₹2L
    MID_TIER = "mid_tier"  # ₹2L – ₹8L
    PREMIUM = "premium"  # ₹8L – ₹15L
    LUXURY = "luxury"  # ₹15L+


# Request schemas
class CreateSessionRequest(BaseModel):
    """Request to create a new home styling session"""

    room_type: Optional[RoomType] = None
    style: Optional[StyleType] = None
    color_palette: Optional[List[ColorPalette]] = None
    budget_tier: Optional[BudgetTier] = None
    selected_tier: Optional[str] = None  # Pricing tier from frontend (free, basic, basic_plus, advanced, curator)


class UpdatePreferencesRequest(BaseModel):
    """Request to update session preferences"""

    room_type: Optional[RoomType] = None
    style: Optional[StyleType] = None
    color_palette: Optional[List[ColorPalette]] = None
    budget_tier: Optional[BudgetTier] = None


class UploadImageRequest(BaseModel):
    """Request to upload room image"""

    image: str = Field(..., description="Base64 encoded room image")


class SelectTierRequest(BaseModel):
    """Request to select a tier"""

    tier: TierType


# Response schemas
class ProductInView(BaseModel):
    """Product included in a home styling view"""

    id: int
    name: str
    price: Optional[float] = None
    image_url: Optional[str] = None
    source_website: str
    source_url: Optional[str] = None
    product_type: Optional[str] = None


class HomeStylingViewSchema(BaseModel):
    """Schema for a generated view"""

    id: int
    view_number: int
    visualization_image: Optional[str] = None
    curated_look_id: Optional[int] = None
    style_theme: Optional[str] = None
    generation_status: str
    error_message: Optional[str] = None
    is_fallback: bool = False  # True if showing curated look image instead of user's room
    products: List[ProductInView] = []
    total_price: float = 0

    class Config:
        from_attributes = True


class HomeStylingSessionSchema(BaseModel):
    """Schema for home styling session response"""

    id: str
    user_id: Optional[str] = None
    room_type: Optional[str] = None
    style: Optional[str] = None
    color_palette: List[str] = []
    budget_tier: Optional[str] = None
    original_room_image: Optional[str] = None
    clean_room_image: Optional[str] = None
    selected_tier: Optional[str] = None
    views_count: int = 1
    status: str
    views: List[HomeStylingViewSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PreviousRoomSchema(BaseModel):
    """Schema for a previously uploaded room"""

    session_id: str
    room_type: Optional[str] = None
    style: Optional[str] = None
    clean_room_image: str  # Thumbnail version of cleaned room
    created_at: datetime

    class Config:
        from_attributes = True


class PreviousRoomsResponse(BaseModel):
    """Response for list of previous rooms"""

    rooms: List[PreviousRoomSchema]
    total: int


# Analytics schemas
class TrackEventRequest(BaseModel):
    """Request to track an analytics event"""

    event_type: str = Field(..., description="Type of event (page_view, preferences_selected, etc.)")
    session_id: Optional[str] = None
    step_name: Optional[str] = None
    event_data: Optional[Dict[str, Any]] = None


class TrackEventResponse(BaseModel):
    """Response for tracking event"""

    success: bool
    event_id: int


# Purchase schemas
class PurchaseSchema(BaseModel):
    """Schema for a purchase (completed homestyling session) in list view"""

    id: str
    title: str  # e.g., "3 looks - Jan 19th, 2026"
    views_count: int
    room_type: Optional[str] = None
    style: Optional[str] = None
    created_at: datetime
    thumbnail: Optional[str] = None  # First view's visualization image

    class Config:
        from_attributes = True


class PurchaseDetailSchema(BaseModel):
    """Schema for purchase details with all views"""

    id: str
    title: str
    views_count: int
    room_type: Optional[str] = None
    style: Optional[str] = None
    budget_tier: Optional[str] = None
    original_room_image: Optional[str] = None
    clean_room_image: Optional[str] = None  # Furniture-removed version for design page
    created_at: datetime
    views: List[HomeStylingViewSchema] = []

    class Config:
        from_attributes = True


class PurchaseListResponse(BaseModel):
    """Response for listing purchases"""

    purchases: List[PurchaseSchema]
    total: int
