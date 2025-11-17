"""
Recommendation Engine Core

Main orchestration class for product recommendations.
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import RecommendationRequest, RecommendationResponse, RecommendationResult
from .search_service import SearchService
from .filtering_service import FilteringService
from .ranking_service import RankingService

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Main Recommendation Engine

    Orchestrates product search, filtering, scoring, and ranking to generate
    personalized product recommendations.
    """

    def __init__(self):
        """Initialize the recommendation engine with all services"""
        self.search_service = SearchService()
        self.filtering_service = FilteringService()
        self.ranking_service = RankingService()

        logger.info("RecommendationEngine initialized with all services")

    async def get_recommendations(
        self,
        request: RecommendationRequest,
        db: AsyncSession,
        user_id: Optional[str] = None
    ) -> RecommendationResponse:
        """
        Get comprehensive product recommendations

        Args:
            request: Recommendation request with user preferences
            db: Database session
            user_id: Optional user ID for personalized recommendations

        Returns:
            RecommendationResponse with ranked products and metadata
        """
        start_time = datetime.now()

        try:
            # Step 1: Search for candidate products
            logger.info(f"Starting recommendation search with keywords: {request.product_keywords}")
            candidates = await self.search_service.search_products(
                keywords=request.product_keywords or [],
                db=db,
                budget_range=request.budget_range,
                exclude_products=request.exclude_products,
                limit=1000
            )

            logger.info(f"Found {len(candidates)} candidate products")

            if not candidates:
                return self._empty_response(start_time, "no_candidates_found")

            # Step 2: Apply advanced filtering (if needed)
            # Note: Basic filtering already done in search

            # Step 3: Score all products using multiple algorithms
            logger.info("Scoring products using multiple algorithms")
            product_scores = await self.ranking_service.score_products(
                products=candidates,
                request=request,
                db=db,
                user_id=user_id
            )

            # Step 4: Convert scores to recommendations with reasoning
            logger.info("Generating recommendations with reasoning")
            recommendations = self.ranking_service.rank_and_generate_recommendations(
                products=candidates,
                product_scores=product_scores,
                request=request
            )

            # Step 5: Apply diversity ranking (future enhancement)
            # recommendations = self._apply_diversity_ranking(recommendations, request)

            # Step 6: Calculate response metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            personalization_level = self._calculate_personalization_level(request, user_id)
            diversity_score = self._calculate_diversity_score(recommendations)
            strategy = self._determine_strategy(request, user_id)

            # Limit to requested max recommendations
            final_recommendations = recommendations[:request.max_recommendations]

            logger.info(
                f"Returning {len(final_recommendations)} recommendations "
                f"(processing time: {processing_time:.2f}s, strategy: {strategy})"
            )

            return RecommendationResponse(
                recommendations=final_recommendations,
                total_found=len(candidates),
                processing_time=processing_time,
                recommendation_strategy=strategy,
                personalization_level=personalization_level,
                diversity_score=diversity_score
            )

        except Exception as e:
            logger.error(f"Error in recommendation engine: {e}", exc_info=True)
            return self._empty_response(start_time, "error_fallback")

    def _empty_response(self, start_time: datetime, strategy: str) -> RecommendationResponse:
        """Generate empty response for error/no results cases"""
        processing_time = (datetime.now() - start_time).total_seconds()

        return RecommendationResponse(
            recommendations=[],
            total_found=0,
            processing_time=processing_time,
            recommendation_strategy=strategy,
            personalization_level=0.0,
            diversity_score=0.0
        )

    def _calculate_personalization_level(
        self,
        request: RecommendationRequest,
        user_id: Optional[str]
    ) -> float:
        """Calculate how personalized the recommendations are"""
        personalization = 0.0

        if user_id:
            personalization += 0.3

        if request.style_preferences:
            personalization += 0.2 * min(len(request.style_preferences) / 3, 1.0)

        if request.functional_requirements:
            personalization += 0.2 * min(len(request.functional_requirements) / 5, 1.0)

        if request.room_context:
            personalization += 0.3

        return min(personalization, 1.0)

    def _calculate_diversity_score(self, recommendations: list[RecommendationResult]) -> float:
        """Calculate diversity score of recommendations"""
        if len(recommendations) < 2:
            return 0.0

        # Simple diversity calculation based on score variance
        scores = [rec.overall_score for rec in recommendations]
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)

        # Normalize to 0-1 range
        return min(variance * 4, 1.0)

    def _determine_strategy(self, request: RecommendationRequest, user_id: Optional[str]) -> str:
        """Determine which recommendation strategy was primarily used"""
        if user_id:
            return "collaborative_hybrid"
        elif request.style_preferences and request.functional_requirements:
            return "content_based_hybrid"
        elif request.room_context:
            return "contextual_content_based"
        else:
            return "popularity_content_based"


# Global recommendation engine instance
recommendation_engine = RecommendationEngine()
