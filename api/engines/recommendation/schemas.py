"""
Pydantic schemas for Recommendation Engine
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field

# ==================== ProductSearchCriteria for Omni Stylist ====================


class BudgetCriteria(BaseModel):
    """Budget constraints for product search"""

    min: Optional[float] = Field(default=None, description="Minimum price (optional)")
    max: Optional[float] = Field(default=None, description="Maximum price (required for recommendations)")
    currency: str = Field(default="INR", description="Currency code")


class StyleCriteria(BaseModel):
    """Style attributes for product search"""

    primary: Optional[str] = Field(default=None, description="Primary style (modern, minimalist, etc.)")
    secondary: Optional[List[str]] = Field(default=None, description="Additional style tags")


class ColorCriteria(BaseModel):
    """Color preferences for product search"""

    preferred: List[str] = Field(default_factory=list, description="Preferred colors")
    avoid: Optional[List[str]] = Field(default=None, description="Colors to exclude")


class MaterialCriteria(BaseModel):
    """Material preferences for product search"""

    preferred: List[str] = Field(default_factory=list, description="Preferred materials")
    avoid: Optional[List[str]] = Field(default=None, description="Materials to exclude")


class DimensionRange(BaseModel):
    """Dimension range for size filtering"""

    min: float
    max: float


class DimensionsCriteria(BaseModel):
    """Dimension constraints"""

    width: Optional[DimensionRange] = None
    height: Optional[DimensionRange] = None
    depth: Optional[DimensionRange] = None


class SizeCriteria(BaseModel):
    """Size/dimensions for product search"""

    seating_capacity: Optional[int] = Field(default=None, description="For sofas: 1, 2, 3")
    dimensions: Optional[DimensionsCriteria] = None


class ProductSearchCriteria(BaseModel):
    """
    Structured JSON output from Omni when ready to recommend products.
    This bridges the conversation to the database query.
    """

    # Required
    category: str = Field(description="Product category: sofas, coffee_tables, rugs, etc.")

    # Budget constraints
    budget: Optional[BudgetCriteria] = Field(default=None, description="Budget constraints")

    # Style attributes
    style: Optional[StyleCriteria] = Field(default=None, description="Style preferences")

    # Visual attributes
    colors: Optional[ColorCriteria] = Field(default=None, description="Color preferences")
    materials: Optional[MaterialCriteria] = Field(default=None, description="Material preferences")

    # Size/dimensions (category-specific)
    size: Optional[SizeCriteria] = Field(default=None, description="Size constraints")

    # Additional filters (category-specific attributes)
    attributes: Optional[Dict[str, Union[str, List[str], bool]]] = Field(
        default=None, description="Additional filters like has_storage, shape, finish"
    )

    # Search metadata
    source: Literal["user", "omni"] = Field(default="omni", description="Who specified these criteria")
    confidence: float = Field(default=85.0, ge=0, le=100, description="Confidence in the match (0-100)")

    # Sorting preference
    sort_by: Optional[Literal["relevance", "price_low", "price_high", "newest"]] = Field(
        default="relevance", description="Sorting preference"
    )
    limit: int = Field(default=20, ge=1, le=50, description="Max products to return")

    class Config:
        json_schema_extra = {
            "example": {
                "category": "sofas",
                "budget": {"min": None, "max": 75000, "currency": "INR"},
                "style": {"primary": "modern", "secondary": ["minimalist"]},
                "colors": {"preferred": ["grey", "cream"], "avoid": None},
                "materials": {"preferred": ["linen", "bouclé"], "avoid": ["leather"]},
                "size": {"seating_capacity": 3, "dimensions": None},
                "attributes": None,
                "source": "omni",
                "confidence": 85,
                "sort_by": "relevance",
                "limit": 20,
            }
        }

    def to_filter_criteria(self) -> "FilterCriteria":
        """Convert to FilterCriteria for existing search pipeline"""
        return FilterCriteria(
            price_min=self.budget.min if self.budget else None,
            price_max=self.budget.max if self.budget else None,
            category=self.category,
            style=[self.style.primary] + (self.style.secondary or []) if self.style and self.style.primary else None,
            color=self.colors.preferred if self.colors else None,
            material=self.materials.preferred if self.materials else None,
        )


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

    # AI stylist extracted attributes (used for ranking)
    color_palette: Optional[List[str]] = None
    styling_tips: Optional[List[str]] = None
    ai_product_types: Optional[List[str]] = None
    user_colors: Optional[List[str]] = None
    user_materials: Optional[List[str]] = None
    user_textures: Optional[List[str]] = None

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
