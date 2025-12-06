"""
Pydantic schemas for chat-related API endpoints
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    READY_TO_RECOMMEND = "READY_TO_RECOMMEND"  # All info gathered, showing categories
    BROWSING = "BROWSING"  # User is browsing products


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

    class Config:
        from_attributes = True


class ChatSessionSchema(BaseModel):
    """Chat session schema"""

    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    user_id: Optional[str] = None

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
        description="Current conversation state: INITIAL, GATHERING_USAGE, GATHERING_STYLE, GATHERING_BUDGET, READY_TO_RECOMMEND, BROWSING",
    )
    follow_up_question: Optional[str] = Field(default=None, description="Follow-up question to ask user if more info needed")
    total_budget: Optional[int] = Field(default=None, description="User's overall budget in INR")
    selected_categories: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="AI-selected categories with budget allocations"
    )

    class Config:
        from_attributes = True


class ChatMessageRequest(BaseModel):
    """Request to send a chat message"""

    message: str = Field(..., max_length=2000)
    session_id: Optional[str] = None
    image: Optional[str] = None  # Base64 encoded image
    selected_product_id: Optional[str] = None  # Product ID user wants to visualize
    user_action: Optional[str] = None  # "add" or "replace"
    selected_stores: Optional[List[str]] = None  # Filter products by selected stores


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
