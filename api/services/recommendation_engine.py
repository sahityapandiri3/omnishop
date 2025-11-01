"""
Advanced Product Recommendation Engine for Interior Design
"""
import logging
import numpy as np
import asyncio
import re
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import json
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from database.models import Product, ProductImage, ChatSession, ChatMessage
from api.services.nlp_processor import design_nlp_processor

logger = logging.getLogger(__name__)


@dataclass
class RecommendationRequest:
    """Request for product recommendations"""
    user_preferences: Dict[str, Any]
    room_context: Optional[Dict[str, Any]] = None
    budget_range: Optional[Tuple[float, float]] = None
    style_preferences: List[str] = None
    functional_requirements: List[str] = None
    product_keywords: List[str] = None
    exclude_products: List[str] = None
    max_recommendations: int = 20


@dataclass
class RecommendationResult:
    """Single product recommendation result"""
    product_id: str
    product_name: str
    confidence_score: float
    reasoning: List[str]
    style_match_score: float
    functional_match_score: float
    price_score: float
    popularity_score: float
    compatibility_score: float
    overall_score: float


@dataclass
class RecommendationResponse:
    """Complete recommendation response"""
    recommendations: List[RecommendationResult]
    total_found: int
    processing_time: float
    recommendation_strategy: str
    personalization_level: float
    diversity_score: float


class AdvancedRecommendationEngine:
    """Advanced recommendation engine with multiple algorithms"""

    def __init__(self):
        self.style_compatibility_matrix = self._build_style_compatibility_matrix()
        self.functional_compatibility_rules = self._build_functional_rules()
        self.price_segments = self._define_price_segments()
        self.recommendation_cache = {}
        self.user_interaction_history = defaultdict(list)

        logger.info("Advanced Recommendation Engine initialized")

    def _build_style_compatibility_matrix(self) -> Dict[str, Dict[str, float]]:
        """Build style compatibility scoring matrix"""
        return {
            "modern": {
                "modern": 1.0, "contemporary": 0.9, "minimalist": 0.8, "scandinavian": 0.7,
                "industrial": 0.6, "transitional": 0.7, "mid_century": 0.5, "traditional": 0.2,
                "rustic": 0.2, "bohemian": 0.3, "art_deco": 0.4, "mediterranean": 0.2
            },
            "traditional": {
                "traditional": 1.0, "transitional": 0.8, "mediterranean": 0.7, "art_deco": 0.6,
                "rustic": 0.5, "modern": 0.2, "contemporary": 0.3, "minimalist": 0.1,
                "industrial": 0.1, "scandinavian": 0.2, "bohemian": 0.4, "mid_century": 0.3
            },
            "scandinavian": {
                "scandinavian": 1.0, "minimalist": 0.9, "modern": 0.7, "contemporary": 0.6,
                "transitional": 0.5, "rustic": 0.6, "industrial": 0.3, "traditional": 0.2,
                "bohemian": 0.3, "art_deco": 0.2, "mediterranean": 0.3, "mid_century": 0.4
            },
            "industrial": {
                "industrial": 1.0, "modern": 0.6, "contemporary": 0.5, "loft": 0.9,
                "minimalist": 0.4, "mid_century": 0.5, "transitional": 0.3, "traditional": 0.1,
                "scandinavian": 0.3, "rustic": 0.4, "bohemian": 0.3, "art_deco": 0.3
            },
            "bohemian": {
                "bohemian": 1.0, "eclectic": 0.9, "mediterranean": 0.6, "rustic": 0.5,
                "traditional": 0.4, "art_deco": 0.5, "modern": 0.3, "minimalist": 0.1,
                "industrial": 0.3, "scandinavian": 0.3, "contemporary": 0.3, "mid_century": 0.4
            },
            # Add more style combinations...
        }

    def _build_functional_rules(self) -> Dict[str, Dict[str, float]]:
        """Build functional compatibility rules"""
        return {
            "seating": {
                "living_room": 1.0, "bedroom": 0.6, "office": 0.8, "dining_room": 0.4,
                "kitchen": 0.2, "bathroom": 0.1, "entryway": 0.3
            },
            "storage": {
                "living_room": 0.8, "bedroom": 1.0, "office": 0.9, "dining_room": 0.6,
                "kitchen": 0.7, "bathroom": 0.8, "entryway": 0.7
            },
            "lighting": {
                "living_room": 1.0, "bedroom": 1.0, "office": 1.0, "dining_room": 1.0,
                "kitchen": 0.9, "bathroom": 0.8, "entryway": 0.9
            },
            "dining": {
                "dining_room": 1.0, "kitchen": 0.8, "living_room": 0.3, "office": 0.2,
                "bedroom": 0.1, "bathroom": 0.0, "entryway": 0.1
            }
        }

    def _define_price_segments(self) -> Dict[str, Tuple[float, float]]:
        """Define price segments for budget matching"""
        return {
            "budget": (0, 500),
            "mid_range": (500, 2000),
            "premium": (2000, 5000),
            "luxury": (5000, float('inf'))
        }

    async def get_recommendations(
        self,
        request: RecommendationRequest,
        db: AsyncSession,
        user_id: Optional[str] = None
    ) -> RecommendationResponse:
        """Get comprehensive product recommendations"""
        start_time = datetime.now()

        try:
            # Get candidate products
            candidates = await self._get_candidate_products(request, db)

            # Apply multiple recommendation strategies
            content_based_scores = await self._content_based_filtering(candidates, request, db)
            popularity_scores = await self._popularity_based_scoring(candidates, db)
            style_scores = await self._style_compatibility_scoring(candidates, request)
            functional_scores = await self._functional_compatibility_scoring(candidates, request)
            price_scores = await self._price_compatibility_scoring(candidates, request)

            # Collaborative filtering if user history available
            collaborative_scores = {}
            if user_id:
                collaborative_scores = await self._collaborative_filtering(candidates, user_id, db)

            # Combine scores using weighted approach
            final_recommendations = await self._combine_scores(
                candidates, content_based_scores, popularity_scores, style_scores,
                functional_scores, price_scores, collaborative_scores, request
            )

            # Apply diversity and ranking
            final_recommendations = self._apply_diversity_ranking(final_recommendations, request)

            # Calculate response metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            personalization_level = self._calculate_personalization_level(request, user_id, collaborative_scores)
            diversity_score = self._calculate_diversity_score(final_recommendations)

            return RecommendationResponse(
                recommendations=final_recommendations[:request.max_recommendations],
                total_found=len(candidates),
                processing_time=processing_time,
                recommendation_strategy=self._determine_strategy(request, user_id),
                personalization_level=personalization_level,
                diversity_score=diversity_score
            )

        except Exception as e:
            logger.error(f"Error in recommendation engine: {e}")
            return RecommendationResponse(
                recommendations=[],
                total_found=0,
                processing_time=0.0,
                recommendation_strategy="error_fallback",
                personalization_level=0.0,
                diversity_score=0.0
            )

    def _categorize_keywords(self, keywords: List[str]) -> Dict[str, List[str]]:
        """Categorize keywords into product categories to enable strict filtering"""

        # Define mutually exclusive product categories
        categories = {
            'ceiling_lighting': ['ceiling lamp', 'ceiling light', 'chandelier', 'pendant', 'overhead light', 'pendant light'],
            'portable_lighting': ['table lamp', 'desk lamp', 'floor lamp'],
            'wall_lighting': ['wall lamp', 'sconce', 'wall light'],
            'seating_furniture': ['sofa', 'couch', 'sectional', 'loveseat', 'chair', 'armchair', 'recliner', 'bench', 'stool', 'ottoman'],
            'center_tables': ['coffee table', 'center table', 'centre table'],  # Placed in front of sofa
            'side_tables': ['side table', 'end table', 'nightstand', 'bedside table'],  # Placed beside furniture
            'dining_tables': ['dining table'],  # Separate category for dining tables
            'other_tables': ['console table', 'desk', 'table'],  # Generic tables
            'storage_furniture': ['dresser', 'chest', 'cabinet', 'bookshelf', 'shelving', 'shelf', 'wardrobe'],
            'bedroom_furniture': ['bed', 'mattress', 'headboard'],
            'decor': ['mirror', 'rug', 'carpet', 'mat'],
            'general_lighting': ['lamp', 'lighting'],  # Catch-all for generic lighting terms
        }

        # Map keywords to their categories
        keyword_to_category = {}
        for category, terms in categories.items():
            for term in terms:
                keyword_to_category[term] = category

        # Group keywords by category
        categorized = defaultdict(list)
        for keyword in keywords:
            category = keyword_to_category.get(keyword.lower())
            if category:
                categorized[category].append(keyword)
            else:
                # Unknown keyword - put in its own category
                categorized['other'].append(keyword)

        logger.info(f"Categorized keywords: {dict(categorized)}")
        return dict(categorized)

    async def _get_candidate_products(self, request: RecommendationRequest, db: AsyncSession) -> List[Product]:
        """Get candidate products based on basic criteria with strict category filtering"""
        from sqlalchemy.orm import selectinload

        query = select(Product).where(Product.is_available == True)

        # Apply product keyword filter (MOST IMPORTANT - filter by what user asked for)
        if request.product_keywords:
            logger.info(f"Filtering products by keywords: {request.product_keywords}")

            # STEP 1: Categorize keywords to determine product category
            categorized_keywords = self._categorize_keywords(request.product_keywords)

            # STEP 2: Build category-aware query
            # If all keywords belong to the same category, we can use strict filtering
            # to prevent cross-category contamination (e.g., "lamp" matching non-lighting products)

            category_conditions = []
            for category, keywords in categorized_keywords.items():
                # Build OR condition within this category
                keyword_conditions = []
                for keyword in keywords:
                    # Use PostgreSQL regex with word boundaries (\y)
                    # ~* is case-insensitive regex operator
                    escaped_keyword = re.escape(keyword)
                    keyword_conditions.append(Product.name.op('~*')(rf'\y{escaped_keyword}\y'))
                    keyword_conditions.append(Product.description.op('~*')(rf'\y{escaped_keyword}\y'))

                if keyword_conditions:
                    # Combine keywords within category with OR
                    category_conditions.append(or_(*keyword_conditions))

            # STEP 3: Combine category conditions
            # If keywords span multiple categories, OR them together
            # This allows "sofa or lamp" queries while preventing unrelated matches
            if category_conditions:
                if len(category_conditions) == 1:
                    # Single category - strict filtering
                    query = query.where(category_conditions[0])
                else:
                    # Multiple categories - OR them but still category-aware
                    query = query.where(or_(*category_conditions))

            logger.info(f"Applied category-aware filtering for {len(category_conditions)} categories")
        else:
            logger.warning("No product keywords provided - returning all products")

        # Apply budget filter
        if request.budget_range:
            min_price, max_price = request.budget_range
            query = query.where(and_(Product.price >= min_price, Product.price <= max_price))

        # Exclude specific products
        if request.exclude_products:
            query = query.where(~Product.id.in_(request.exclude_products))

        # Apply room type filter if available
        # Note: Temporarily disabled due to relationship filtering issue
        # This needs proper category ID resolution
        # if request.room_context and request.room_context.get("room_type"):
        #     room_type = request.room_context["room_type"]
        #     room_categories = self._get_room_categories(room_type)
        #     if room_categories:
        #         # TODO: Convert category names to IDs before filtering
        #         query = query.where(Product.category_id.in_(room_categories))

        # Eagerly load images relationship to avoid lazy loading issues
        query = query.options(selectinload(Product.images))

        # Limit initial candidates for performance
        query = query.limit(1000)

        result = await db.execute(query)
        return result.scalars().all()

    def _get_room_categories(self, room_type: str) -> List[str]:
        """Map room types to relevant product categories"""
        room_category_map = {
            "living_room": ["sofas", "chairs", "coffee_tables", "entertainment_centers", "rugs", "lighting"],
            "bedroom": ["beds", "dressers", "nightstands", "mirrors", "lighting", "rugs"],
            "dining_room": ["dining_tables", "dining_chairs", "sideboards", "lighting"],
            "kitchen": ["bar_stools", "kitchen_islands", "storage", "lighting"],
            "office": ["desks", "office_chairs", "bookcases", "storage", "lighting"],
            "bathroom": ["vanities", "mirrors", "storage", "lighting"]
        }
        return room_category_map.get(room_type, [])

    async def _content_based_filtering(
        self,
        candidates: List[Product],
        request: RecommendationRequest,
        db: AsyncSession
    ) -> Dict[str, float]:
        """Content-based filtering using product attributes"""
        scores = {}

        # Extract preferences from request
        style_preferences = request.style_preferences or []
        user_prefs = request.user_preferences

        for product in candidates:
            score = 0.0

            # Style matching
            if style_preferences:
                product_style = self._extract_product_style(product)
                style_match = max([
                    self._calculate_style_similarity(style, product_style)
                    for style in style_preferences
                ], default=0.0)
                score += style_match * 0.3

            # Color matching
            if "colors" in user_prefs:
                color_match = self._calculate_color_match(product, user_prefs["colors"])
                score += color_match * 0.2

            # Material matching
            if "materials" in user_prefs:
                material_match = self._calculate_material_match(product, user_prefs["materials"])
                score += material_match * 0.2

            # Description similarity
            if "description_keywords" in user_prefs:
                desc_match = self._calculate_description_similarity(product, user_prefs["description_keywords"])
                score += desc_match * 0.3

            scores[product.id] = min(score, 1.0)

        return scores

    async def _popularity_based_scoring(self, candidates: List[Product], db: AsyncSession) -> Dict[str, float]:
        """Calculate popularity scores based on interaction data"""
        scores = {}

        # In a real implementation, this would query interaction/view/purchase data
        # For now, we'll simulate based on product attributes

        for product in candidates:
            # Simulate popularity based on price point and category
            base_popularity = 0.5

            # Premium products might have lower popularity but higher conversion
            if product.price > 2000:
                base_popularity *= 0.8
            elif product.price < 200:
                base_popularity *= 1.2

            # Add some randomness to simulate real data
            import random
            popularity_factor = random.uniform(0.3, 1.0)
            scores[product.id] = base_popularity * popularity_factor

        return scores

    async def _style_compatibility_scoring(
        self,
        candidates: List[Product],
        request: RecommendationRequest
    ) -> Dict[str, float]:
        """Score products based on style compatibility"""
        scores = {}

        if not request.style_preferences:
            return {product.id: 0.5 for product in candidates}

        for product in candidates:
            product_style = self._extract_product_style(product)
            max_compatibility = 0.0

            for user_style in request.style_preferences:
                compatibility = self.style_compatibility_matrix.get(user_style, {}).get(product_style, 0.0)
                max_compatibility = max(max_compatibility, compatibility)

            scores[product.id] = max_compatibility

        return scores

    async def _functional_compatibility_scoring(
        self,
        candidates: List[Product],
        request: RecommendationRequest
    ) -> Dict[str, float]:
        """Score products based on functional requirements"""
        scores = {}

        room_type = request.room_context.get("room_type", "living_room") if request.room_context else "living_room"

        for product in candidates:
            product_function = self._extract_product_function(product)
            compatibility = self.functional_compatibility_rules.get(product_function, {}).get(room_type, 0.5)
            scores[product.id] = compatibility

        return scores

    async def _price_compatibility_scoring(
        self,
        candidates: List[Product],
        request: RecommendationRequest
    ) -> Dict[str, float]:
        """Score products based on price compatibility with budget"""
        scores = {}

        if not request.budget_range:
            return {product.id: 1.0 for product in candidates}

        min_budget, max_budget = request.budget_range
        budget_range = max_budget - min_budget

        for product in candidates:
            if min_budget <= product.price <= max_budget:
                # Score based on position within budget range
                if budget_range > 0:
                    position = (product.price - min_budget) / budget_range
                    # Peak score at 60% of budget (good value)
                    optimal_position = 0.6
                    distance_from_optimal = abs(position - optimal_position)
                    score = 1.0 - (distance_from_optimal * 0.5)
                else:
                    score = 1.0
            else:
                score = 0.0

            scores[product.id] = max(score, 0.0)

        return scores

    async def _collaborative_filtering(
        self,
        candidates: List[Product],
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, float]:
        """Collaborative filtering based on user behavior patterns"""
        scores = {}

        # This would implement user-based or item-based collaborative filtering
        # For now, we'll return neutral scores
        return {product.id: 0.5 for product in candidates}

    async def _combine_scores(
        self,
        candidates: List[Product],
        content_scores: Dict[str, float],
        popularity_scores: Dict[str, float],
        style_scores: Dict[str, float],
        functional_scores: Dict[str, float],
        price_scores: Dict[str, float],
        collaborative_scores: Dict[str, float],
        request: RecommendationRequest
    ) -> List[RecommendationResult]:
        """Combine all scoring methods into final recommendations"""

        recommendations = []

        # Define weights based on request characteristics
        weights = self._calculate_algorithm_weights(request, bool(collaborative_scores))

        for product in candidates:
            product_id = product.id

            # Get individual scores
            content_score = content_scores.get(product_id, 0.0)
            popularity_score = popularity_scores.get(product_id, 0.0)
            style_score = style_scores.get(product_id, 0.0)
            functional_score = functional_scores.get(product_id, 0.0)
            price_score = price_scores.get(product_id, 0.0)
            collaborative_score = collaborative_scores.get(product_id, 0.0)

            # Calculate weighted overall score
            overall_score = (
                content_score * weights["content"] +
                popularity_score * weights["popularity"] +
                style_score * weights["style"] +
                functional_score * weights["functional"] +
                price_score * weights["price"] +
                collaborative_score * weights["collaborative"]
            )

            # Generate reasoning
            reasoning = self._generate_recommendation_reasoning(
                product, content_score, style_score, functional_score, price_score
            )

            recommendation = RecommendationResult(
                product_id=product_id,
                product_name=product.name,
                confidence_score=overall_score,
                reasoning=reasoning,
                style_match_score=style_score,
                functional_match_score=functional_score,
                price_score=price_score,
                popularity_score=popularity_score,
                compatibility_score=(style_score + functional_score) / 2,
                overall_score=overall_score
            )

            recommendations.append(recommendation)

        return recommendations

    def _calculate_algorithm_weights(self, request: RecommendationRequest, has_collaborative: bool) -> Dict[str, float]:
        """Calculate weights for different algorithms based on request"""
        # Base weights
        weights = {
            "content": 0.25,
            "popularity": 0.15,
            "style": 0.25,
            "functional": 0.20,
            "price": 0.15,
            "collaborative": 0.0
        }

        # Adjust based on available information
        if has_collaborative:
            weights["collaborative"] = 0.20
            # Redistribute other weights
            for key in ["content", "popularity", "style"]:
                weights[key] *= 0.8

        # Boost style weight if strong style preferences
        if request.style_preferences and len(request.style_preferences) > 1:
            weights["style"] += 0.1
            weights["content"] -= 0.05
            weights["popularity"] -= 0.05

        # Boost functional weight if room context is strong
        if request.room_context and len(request.functional_requirements or []) > 2:
            weights["functional"] += 0.1
            weights["popularity"] -= 0.1

        return weights

    def _apply_diversity_ranking(
        self,
        recommendations: List[RecommendationResult],
        request: RecommendationRequest
    ) -> List[RecommendationResult]:
        """Apply diversity and final ranking to recommendations"""

        # Sort by overall score first
        recommendations.sort(key=lambda x: x.overall_score, reverse=True)

        # Apply diversity constraints
        diverse_recommendations = []
        seen_categories = set()
        seen_price_ranges = set()

        for rec in recommendations:
            # Add diversity logic here
            # For now, just return sorted recommendations
            diverse_recommendations.append(rec)

        return diverse_recommendations

    def _calculate_personalization_level(
        self,
        request: RecommendationRequest,
        user_id: Optional[str],
        collaborative_scores: Dict[str, float]
    ) -> float:
        """Calculate how personalized the recommendations are"""
        personalization = 0.0

        if user_id:
            personalization += 0.3

        if request.style_preferences:
            personalization += 0.2 * len(request.style_preferences) / 3

        if request.functional_requirements:
            personalization += 0.2 * len(request.functional_requirements) / 5

        if request.room_context:
            personalization += 0.3

        if collaborative_scores:
            personalization += 0.2

        return min(personalization, 1.0)

    def _calculate_diversity_score(self, recommendations: List[RecommendationResult]) -> float:
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
        if user_id and len(self.user_interaction_history.get(user_id, [])) > 10:
            return "collaborative_hybrid"
        elif request.style_preferences and request.functional_requirements:
            return "content_based_hybrid"
        elif request.room_context:
            return "contextual_content_based"
        else:
            return "popularity_content_based"

    # Helper methods for scoring calculations
    def _extract_product_style(self, product: Product) -> str:
        """Extract style from product data"""
        # This would analyze product name, description, tags
        # For now, return a default style
        style_keywords = {
            "modern": ["modern", "contemporary", "sleek", "minimalist"],
            "traditional": ["traditional", "classic", "ornate", "elegant"],
            "rustic": ["rustic", "farmhouse", "reclaimed", "weathered"],
            "scandinavian": ["scandinavian", "nordic", "hygge", "light"]
        }

        product_text = (product.name + " " + (product.description or "")).lower()

        for style, keywords in style_keywords.items():
            if any(keyword in product_text for keyword in keywords):
                return style

        return "contemporary"  # default

    def _extract_product_function(self, product: Product) -> str:
        """Extract primary function from product"""
        # Map product categories/names to functions
        function_map = {
            "sofa": "seating", "chair": "seating", "armchair": "seating",
            "table": "dining", "desk": "workspace", "bed": "sleeping",
            "dresser": "storage", "bookshelf": "storage", "cabinet": "storage",
            "lamp": "lighting", "chandelier": "lighting"
        }

        product_name = product.name.lower()
        for keyword, function in function_map.items():
            if keyword in product_name:
                return function

        return "decoration"  # default

    def _calculate_style_similarity(self, style1: str, style2: str) -> float:
        """Calculate similarity between two styles"""
        return self.style_compatibility_matrix.get(style1, {}).get(style2, 0.0)

    def _calculate_color_match(self, product: Product, preferred_colors: List[str]) -> float:
        """Calculate color match score"""
        # This would analyze product images and descriptions for color
        # For now, return a simulated score
        return 0.7  # placeholder

    def _calculate_material_match(self, product: Product, preferred_materials: List[str]) -> float:
        """Calculate material match score"""
        # This would analyze product descriptions for materials
        # For now, return a simulated score
        return 0.6  # placeholder

    def _calculate_description_similarity(self, product: Product, keywords: List[str]) -> float:
        """Calculate description similarity score"""
        if not product.description or not keywords:
            return 0.0

        product_words = set(product.description.lower().split())
        keyword_words = set(word.lower() for word in keywords)

        intersection = len(product_words.intersection(keyword_words))
        union = len(product_words.union(keyword_words))

        return intersection / union if union > 0 else 0.0

    def _generate_recommendation_reasoning(
        self,
        product: Product,
        content_score: float,
        style_score: float,
        functional_score: float,
        price_score: float
    ) -> List[str]:
        """Generate human-readable reasoning for recommendation"""
        reasoning = []

        if style_score > 0.7:
            reasoning.append("Excellent style match for your preferences")
        elif style_score > 0.5:
            reasoning.append("Good style compatibility")

        if functional_score > 0.8:
            reasoning.append("Perfect functional fit for your space")
        elif functional_score > 0.6:
            reasoning.append("Suitable for your room requirements")

        if price_score > 0.8:
            reasoning.append("Excellent value within your budget")
        elif price_score > 0.6:
            reasoning.append("Good price point for your budget")

        if content_score > 0.7:
            reasoning.append("Matches your specific preferences well")

        if not reasoning:
            reasoning.append("Recommended based on overall compatibility")

        return reasoning


# Global recommendation engine instance
recommendation_engine = AdvancedRecommendationEngine()