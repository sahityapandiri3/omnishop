"""
Pydantic schemas for Recommendation Engine
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    """Request for product recommendations"""

    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    room_context: Optional[Dict[str, Any]] = None
    budget_range: Optional[Tuple[float, float]] = None
    style_preferences: Optional[List[str]] = None
    functional_requirements: Optional[List[str]] = None
    product_keywords: Optional[List[str]] = None
    exclude_products: Optional[List[str]] = None
    max_recommendations: int = Field(default=20, ge=1, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "user_preferences": {"colors": ["blue", "white"], "materials": ["wood"]},
                "room_context": {"room_type": "living_room", "style": "modern"},
                "budget_range": [500, 2000],
                "style_preferences": ["modern", "minimalist"],
                "product_keywords": ["sofa", "couch"],
                "max_recommendations": 20,
            }
        }


class RecommendationResult(BaseModel):
    """Single product recommendation result"""

    product_id: str
    product_name: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: List[str] = Field(default_factory=list)
    style_match_score: float = Field(ge=0.0, le=1.0)
    functional_match_score: float = Field(ge=0.0, le=1.0)
    price_score: float = Field(ge=0.0, le=1.0)
    popularity_score: float = Field(ge=0.0, le=1.0)
    compatibility_score: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)


class RecommendationResponse(BaseModel):
    """Complete recommendation response"""

    recommendations: List[RecommendationResult]
    total_found: int = Field(ge=0)
    processing_time: float = Field(ge=0.0)
    recommendation_strategy: str
    personalization_level: float = Field(ge=0.0, le=1.0)
    diversity_score: float = Field(ge=0.0, le=1.0)


class SearchRequest(BaseModel):
    """Request for product search"""

    query: str = Field(min_length=1)
    keywords: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    limit: int = Field(default=20, ge=1, le=100)


class FilterCriteria(BaseModel):
    """Filtering criteria for products"""

    price_min: Optional[float] = Field(default=None, ge=0)
    price_max: Optional[float] = None
    website: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    in_stock: Optional[bool] = None
    on_sale: Optional[bool] = None
    style: Optional[List[str]] = None
    material: Optional[List[str]] = None
    color: Optional[List[str]] = None
    # Match mode for colors/materials: "or" (union - any match) vs "and" (intersection - all must match)
    color_match_mode: str = Field(default="or", pattern="^(or|and)$")
    material_match_mode: str = Field(default="or", pattern="^(or|and)$")


class ProductScore(BaseModel):
    """Scoring breakdown for a single product"""

    product_id: str
    content_score: float = Field(ge=0.0, le=1.0)
    popularity_score: float = Field(ge=0.0, le=1.0)
    style_score: float = Field(ge=0.0, le=1.0)
    functional_score: float = Field(ge=0.0, le=1.0)
    price_score: float = Field(ge=0.0, le=1.0)
    collaborative_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
