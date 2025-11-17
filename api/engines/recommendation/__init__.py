"""
Recommendation Engine

Handles product search, discovery, and filtering operations.
"""

from .core import RecommendationEngine, recommendation_engine
from .schemas import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationResult,
    SearchRequest,
    FilterCriteria,
    ProductScore
)
from .search_service import SearchService
from .filtering_service import FilteringService
from .ranking_service import RankingService

__all__ = [
    "RecommendationEngine",
    "recommendation_engine",
    "RecommendationRequest",
    "RecommendationResponse",
    "RecommendationResult",
    "SearchRequest",
    "FilterCriteria",
    "ProductScore",
    "SearchService",
    "FilteringService",
    "RankingService"
]
