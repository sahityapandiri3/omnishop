"""
Pydantic schemas for projects
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ProjectStatusEnum(str, Enum):
    """Project status enum for draft/published state"""

    DRAFT = "draft"
    PUBLISHED = "published"


# Request schemas
class ProjectCreate(BaseModel):
    """Schema for creating a project"""

    name: str = Field(..., min_length=1, max_length=200)
    status: Optional[ProjectStatusEnum] = ProjectStatusEnum.DRAFT


class ProjectUpdate(BaseModel):
    """Schema for updating a project (manual save)"""

    name: Optional[str] = Field(None, max_length=200)
    status: Optional[ProjectStatusEnum] = None  # draft or published
    room_image: Optional[str] = None  # Base64
    clean_room_image: Optional[str] = None  # Base64
    visualization_image: Optional[str] = None  # Base64
    canvas_products: Optional[str] = None  # JSON string
    visualization_history: Optional[str] = None  # JSON string of visualization history for undo/redo
    chat_session_id: Optional[str] = None  # Link to chat session for restoring conversation


# Response schemas
class ProjectListItem(BaseModel):
    """Schema for project in list view (without large image data)"""

    id: str
    name: str
    status: str  # "draft" or "published"
    has_room_image: bool
    has_visualization: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    """Schema for full project response (including image data)"""

    id: str
    name: str
    status: str  # "draft" or "published"
    room_image: Optional[str] = None
    clean_room_image: Optional[str] = None
    visualization_image: Optional[str] = None
    canvas_products: Optional[str] = None
    visualization_history: Optional[str] = None  # JSON string of visualization history for undo/redo
    chat_session_id: Optional[str] = None  # Link to chat session for restoring conversation
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectsListResponse(BaseModel):
    """Schema for list of projects"""

    projects: List[ProjectListItem]
    total: int
