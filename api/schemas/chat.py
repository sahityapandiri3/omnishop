"""
Pydantic schemas for chat-related API endpoints
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer


class MessageType(str, Enum):
    """Chat message types"""

    user = "user"
    assistant = "assistant"
    system = "system"


class ConversationState(str, Enum):
    """Conversation states for guided design flow"""

    INITIAL = "INITIAL"  # Waiting for room image or first message
    GATHERING_USAGE = "GATHERING_USAGE"  # Asking about room usage
    GATHERING_STYLE = "GATHERING_STYLE"  # Asking about style preferences
    GATHERING_BUDGET = "GATHERING_BUDGET"  # Asking about budget
    GATHERING_SCOPE = "GATHERING_SCOPE"  # Asking about scope (full room vs specific)
    GATHERING_PREFERENCE_MODE = "GATHERING_PREFERENCE_MODE"  # Asking if user wants to provide preferences or stylist chooses
    GATHERING_ATTRIBUTES = "GATHERING_ATTRIBUTES"  # Gathering category-specific attributes
    READY_TO_RECOMMEND = "READY_TO_RECOMMEND"  # All info gathered, showing categories
    BROWSING = "BROWSING"  # User is browsing products
    DIRECT_SEARCH = "DIRECT_SEARCH"  # Direct category search (simple categories - show immediately)
    DIRECT_SEARCH_GATHERING = "DIRECT_SEARCH_GATHERING"  # Direct category search but need to gather attributes


class BudgetAllocation(BaseModel):
    """Budget range for a category"""

    min: int = 0
    max: int = Field(default=999999, description="Max budget for this category")


class CategoryRecommendation(BaseModel):
    """AI-selected category with budget allocation"""

    category_id: str = Field(..., description="Category identifier (e.g., 'sofas', 'coffee_tables')")
    display_name: str = Field(..., description="Human-readable category name")
    budget_allocation: Optional[BudgetAllocation] = None
    priority: int = Field(default=1, description="Display order priority (lower = higher priority)")
    product_count: Optional[int] = Field(default=None, description="Number of products in this category")


class ChatMessageSchema(BaseModel):
    """Chat message schema"""

    id: str
    type: MessageType
    content: str
    timestamp: datetime
    session_id: Optional[str] = None
    products: Optional[List[Dict[str, Any]]] = None
    image_url: Optional[str] = None

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize timestamp as ISO format with UTC indicator for correct JS parsing"""
        if value.tzinfo is None:
            # Treat naive datetime as UTC
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    class Config:
        from_attributes = True


class ChatSessionSchema(BaseModel):
    """Chat session schema"""

    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    user_id: Optional[str] = None

    @field_serializer("created_at", "updated_at")
    def serialize_timestamps(self, value: datetime) -> str:
        """Serialize timestamps as ISO format with UTC indicator for correct JS parsing"""
        if value.tzinfo is None:
            # Treat naive datetime as UTC
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    class Config:
        from_attributes = True


class DesignAnalysisSchema(BaseModel):
    """Design analysis schema from ChatGPT"""

    design_analysis: Dict[str, Any]
    product_matching_criteria: Optional[Dict[str, Any]] = {}
    visualization_guidance: Optional[Dict[str, Any]] = {}
    confidence_scores: Optional[Dict[str, float]] = {}
    recommendations: Optional[Dict[str, Any]] = {}
    user_friendly_response: Optional[str] = "I've analyzed your request and found some great recommendations for you!"

    # NEW: Guided conversation flow fields
    conversation_state: Optional[str] = Field(
        default="INITIAL",
        description="Current conversation state: INITIAL, GATHERING_USAGE, GATHERING_STYLE, GATHERING_BUDGET, GATHERING_SCOPE, GATHERING_PREFERENCE_MODE, GATHERING_ATTRIBUTES, READY_TO_RECOMMEND, BROWSING, DIRECT_SEARCH, DIRECT_SEARCH_GATHERING",
    )
    follow_up_question: Optional[str] = Field(default=None, description="Follow-up question to ask user if more info needed")
    total_budget: Optional[int] = Field(default=None, description="User's overall budget in INR")
    selected_categories: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="AI-selected categories with budget allocations"
    )

    # NEW: Intent detection fields (GPT as single source of truth)
    is_direct_search: bool = Field(
        default=False,
        description="True if user is searching for a specific category (e.g., 'show me sofas'), False for generic styling requests",
    )
    detected_category: Optional[str] = Field(
        default=None,
        description="The primary category detected from user's request (e.g., 'sofa', 'decor_accents'). Only set when is_direct_search=True",
    )
    preference_mode: Optional[str] = Field(
        default=None,
        description="User's preference mode: 'user_chooses' (user provides preferences) or 'stylist_chooses' (Omni suggests based on room)",
    )
    category_attributes: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Category-specific attributes gathered from user (e.g., {'seating_type': '3-seater', 'style': 'modern'})",
    )
    attributes_complete: bool = Field(
        default=False,
        description="True when all required attributes for the category have been gathered or user said 'you choose'",
    )

    class Config:
        from_attributes = True


class OnboardingPreferences(BaseModel):
    """User preferences collected during onboarding wizard"""

    roomType: Optional[str] = None  # "living_room", "bedroom", etc.
    primaryStyle: Optional[str] = None  # Primary style preference
    secondaryStyle: Optional[str] = None  # Secondary style preference
    budget: Optional[int] = None  # Budget in INR
    budgetFlexible: bool = False  # Whether budget is flexible
    roomImage: Optional[str] = None  # Base64 encoded room image


class ChatMessageRequest(BaseModel):
    """Request to send a chat message"""

    message: str = Field(..., max_length=2000)
    session_id: Optional[str] = None
    image: Optional[str] = None  # Base64 encoded image
    selected_product_id: Optional[str] = None  # Product ID user wants to visualize
    user_action: Optional[str] = None  # "add" or "replace"
    selected_stores: Optional[List[str]] = None  # Filter products by selected stores
    onboarding_preferences: Optional[OnboardingPreferences] = None  # Preferences from onboarding wizard


class ChatMessageResponse(BaseModel):
    """Response from chat message"""

    message: ChatMessageSchema
    analysis: Optional[DesignAnalysisSchema] = None

    # NEW: Category-based recommendations
    conversation_state: str = Field(default="INITIAL", description="Current conversation state")
    selected_categories: Optional[List[CategoryRecommendation]] = Field(
        default=None, description="AI-selected categories based on room type and user preferences"
    )
    products_by_category: Optional[Dict[str, List[Dict[str, Any]]]] = Field(
        default=None, description="Products grouped by category_id"
    )
    follow_up_question: Optional[str] = Field(default=None, description="Follow-up question if more info needed from user")
    total_budget: Optional[int] = Field(default=None, description="User's overall budget for the room")

    # Legacy fields (kept for backward compatibility)
    recommended_products: Optional[List[Dict[str, Any]]] = None
    detected_furniture: Optional[List[Dict[str, Any]]] = None  # All furniture detected in uploaded image
    similar_furniture_items: Optional[List[Dict[str, Any]]] = None  # Similar furniture to selected product (for replacement)
    requires_action_choice: bool = False  # True if user needs to choose add/replace
    action_options: Optional[List[str]] = None  # Available actions: ["add", "replace"]


class ChatHistoryResponse(BaseModel):
    """Chat history response"""

    session: ChatSessionSchema
    messages: List[ChatMessageSchema]


class StartSessionRequest(BaseModel):
    """Request to start a new chat session"""

    user_id: Optional[str] = None


class StartSessionResponse(BaseModel):
    """Response for starting a new session"""

    session_id: str
    message: str = "Hello! I'm your AI interior design assistant. How can I help you transform your space today?"


# ============================================================================
# Pagination Schemas for Product Discovery
# ============================================================================


class PaginationCursor(BaseModel):
    """Cursor for cursor-based pagination - encodes position in sorted results"""

    style_score: float = Field(..., description="Style score of the last product in the previous page")
    product_id: int = Field(..., description="ID of the last product in the previous page")


class PaginatedProductsRequest(BaseModel):
    """Request for paginated products within a category"""

    category_id: str = Field(..., description="Category identifier to fetch products for")
    page_size: int = Field(default=24, ge=1, le=50, description="Number of products per page")
    cursor: Optional[PaginationCursor] = Field(default=None, description="Cursor for next page (None for first page)")
    style_attributes: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Style attributes for scoring (style_keywords, colors, materials, size_keywords)",
    )
    budget_min: Optional[float] = Field(default=None, description="Minimum price filter")
    budget_max: Optional[float] = Field(default=None, description="Maximum price filter")
    selected_stores: Optional[List[str]] = Field(default=None, description="Filter by store names")


class PaginatedProductsResponse(BaseModel):
    """Response for paginated products"""

    products: List[Dict[str, Any]] = Field(..., description="List of products for this page")
    next_cursor: Optional[PaginationCursor] = Field(default=None, description="Cursor for next page (None if no more pages)")
    has_more: bool = Field(..., description="Whether there are more products to load")
    total_estimated: int = Field(..., description="Estimated total product count for this category")


class CategoryProductsMetadata(BaseModel):
    """Metadata for paginated category products - used in initial response"""

    products: List[Dict[str, Any]] = Field(..., description="Initial page of products")
    total_estimated: int = Field(default=0, description="Estimated total product count")
    has_more: bool = Field(default=False, description="Whether there are more products")
    next_cursor: Optional[PaginationCursor] = Field(default=None, description="Cursor for next page")
