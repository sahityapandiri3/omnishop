"""
Pydantic schemas for chat-related API endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """Chat message types"""
    user = "user"
    assistant = "assistant"
    system = "system"


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

    class Config:
        from_attributes = True


class ChatMessageRequest(BaseModel):
    """Request to send a chat message"""
    message: str = Field(..., max_length=2000)
    session_id: Optional[str] = None
    image: Optional[str] = None  # Base64 encoded image
    selected_product_id: Optional[str] = None  # Product ID user wants to visualize
    user_action: Optional[str] = None  # "add", "replace_selected", "replace_all"
    furniture_ids_to_replace: Optional[List[str]] = None  # Specific furniture IDs to replace (when user_action="replace_selected")


class ChatMessageResponse(BaseModel):
    """Response from chat message"""
    message: ChatMessageSchema
    analysis: Optional[DesignAnalysisSchema] = None
    recommended_products: Optional[List[Dict[str, Any]]] = None
    detected_furniture: Optional[List[Dict[str, Any]]] = None  # All furniture detected in uploaded image
    similar_furniture_items: Optional[List[Dict[str, Any]]] = None  # Similar furniture to selected product (for replacement)
    requires_action_choice: bool = False  # True if user needs to choose add/replace
    action_options: Optional[Dict[str, Any]] = None  # Available actions: {"add": true, "replace": {"count": 3, "items": [...]}


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