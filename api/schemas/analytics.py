"""
Pydantic schemas for Analytics API endpoints
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# --- Event Tracking Schemas ---


class TrackEventRequest(BaseModel):
    """Single event tracking request"""

    event_type: str = Field(..., max_length=100, description="Event type in category.action format")
    step_name: Optional[str] = Field(None, max_length=100, description="Funnel step name")
    event_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional event data")
    timestamp: Optional[datetime] = Field(None, description="Client-side timestamp (defaults to server time)")
    page_url: Optional[str] = Field(None, max_length=500, description="Page URL where event occurred")


class TrackBatchRequest(BaseModel):
    """Batch event tracking request"""

    events: List[TrackEventRequest] = Field(..., min_length=1, max_length=100)


class TrackEventResponse(BaseModel):
    """Response for event tracking"""

    success: bool
    event_id: Optional[int] = None
    events_tracked: Optional[int] = None


# --- Admin Dashboard Response Schemas ---


class OverviewCard(BaseModel):
    """Single metric card for overview"""

    label: str
    value: int


class EventsPerDay(BaseModel):
    """Events count for a single day"""

    date: str
    count: int


class OverviewResponse(BaseModel):
    """Admin overview summary"""

    total_users: int
    active_users: int
    new_signups: int
    total_events: int
    events_per_day: List[EventsPerDay]


class FunnelStep(BaseModel):
    """Single step in a funnel"""

    step: str
    count: int
    percentage: float = Field(description="Percentage relative to first step")


class FunnelResponse(BaseModel):
    """User lifecycle funnel"""

    steps: List[FunnelStep]


class PageMetric(BaseModel):
    """Metrics for a single page"""

    path: str
    views: int
    unique_users: int


class PagesResponse(BaseModel):
    """Page-level metrics"""

    pages: List[PageMetric]


class FeatureUsage(BaseModel):
    """Usage metrics for a feature category"""

    feature: str
    event_count: int
    unique_users: int


class FeaturesResponse(BaseModel):
    """Feature usage breakdown"""

    features: List[FeatureUsage]


class DropoffStep(BaseModel):
    """Single step in a drop-off analysis"""

    step: str
    count: int
    retained_pct: float = Field(description="Percentage retained from previous step")


class DropoffFunnel(BaseModel):
    """A named drop-off funnel"""

    name: str
    steps: List[DropoffStep]


class DropoffResponse(BaseModel):
    """Drop-off analysis for multiple funnels"""

    funnels: List[DropoffFunnel]


# --- Detailed Event Views ---


class ActiveUser(BaseModel):
    """User info for filter dropdown"""

    user_id: str
    email: str
    name: Optional[str] = None
    event_count: int


class ActiveUsersResponse(BaseModel):
    """List of active users for filtering"""

    users: List[ActiveUser]


class SearchEvent(BaseModel):
    """A product search event with details"""

    id: int
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    query: Optional[str] = None
    results_count: Optional[int] = None
    filters_applied: Optional[Dict[str, Any]] = None
    page_url: Optional[str] = None
    created_at: datetime


class SearchEventsResponse(BaseModel):
    """Search and filter events"""

    events: List[SearchEvent]
    total: int


class VisualizationEvent(BaseModel):
    """A visualization event with details (supports both design studio and homestyling)"""

    id: int
    event_type: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    project_id: Optional[str] = None  # Design studio
    session_id: Optional[str] = None  # Homestyling
    product_count: Optional[int] = None  # Design studio
    views_count: Optional[int] = None  # Homestyling (1, 3, or 6 views)
    products: Optional[List[Dict[str, Any]]] = None
    wall_color: Optional[Dict[str, Any]] = None
    wall_texture: Optional[Dict[str, Any]] = None
    floor_tile: Optional[Dict[str, Any]] = None
    method: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_ms: Optional[int] = None
    success: Optional[bool] = None
    page_url: Optional[str] = None
    created_at: datetime


class VisualizationEventsResponse(BaseModel):
    """Visualization events"""

    events: List[VisualizationEvent]
    total: int
