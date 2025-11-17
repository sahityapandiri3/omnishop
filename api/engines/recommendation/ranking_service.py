"""
Ranking Service for Product Scoring and Ranking

Handles multiple recommendation algorithms and score combination.
"""
import logging
import random
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Product
from .schemas import RecommendationRequest, RecommendationResult, ProductScore

logger = logging.getLogger(__name__)


class RankingService:
    """Service for scoring and ranking products"""

    def __init__(self):
        self.style_compatibility_matrix = self._build_style_compatibility_matrix()
        self.functional_compatibility_rules = self._build_functional_rules()
        self.price_segments = self._define_price_segments()
        logger.info("RankingService initialized")

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

    async def score_products(
        self,
        products: List[Product],
        request: RecommendationRequest,
        db: AsyncSession,
        user_id: Optional[str] = None
    ) -> List[ProductScore]:
        """
        Score all products using multiple algorithms

        Args:
            products: List of candidate products
            request: Recommendation request with preferences
            db: Database session
            user_id: Optional user ID for collaborative filtering

        Returns:
            List of ProductScore objects with detailed scoring
        """
        # Calculate individual scores
        content_scores = await self._content_based_filtering(products, request, db)
        popularity_scores = await self._popularity_based_scoring(products, db)
        style_scores = await self._style_compatibility_scoring(products, request)
        functional_scores = await self._functional_compatibility_scoring(products, request)
        price_scores = await self._price_compatibility_scoring(products, request)

        # Collaborative filtering if user available
        collaborative_scores = {}
        if user_id:
            collaborative_scores = await self._collaborative_filtering(products, user_id, db)

        # Calculate algorithm weights
        weights = self._calculate_algorithm_weights(request, bool(collaborative_scores))

        # Combine scores
        product_scores = []
        for product in products:
            pid = product.id

            content = content_scores.get(pid, 0.0)
            popularity = popularity_scores.get(pid, 0.0)
            style = style_scores.get(pid, 0.0)
            functional = functional_scores.get(pid, 0.0)
            price = price_scores.get(pid, 0.0)
            collaborative = collaborative_scores.get(pid, 0.0)

            # Calculate weighted overall score
            overall = (
                content * weights["content"] +
                popularity * weights["popularity"] +
                style * weights["style"] +
                functional * weights["functional"] +
                price * weights["price"] +
                collaborative * weights["collaborative"]
            )

            product_scores.append(ProductScore(
                product_id=pid,
                content_score=content,
                popularity_score=popularity,
                style_score=style,
                functional_score=functional,
                price_score=price,
                collaborative_score=collaborative,
                overall_score=overall
            ))

        return product_scores

    async def _content_based_filtering(
        self,
        candidates: List[Product],
        request: RecommendationRequest,
        db: AsyncSession
    ) -> Dict[str, float]:
        """Content-based filtering using product attributes"""
        scores = {}
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

        for product in candidates:
            base_popularity = 0.5

            # Simulate popularity based on price point
            if product.price > 2000:
                base_popularity *= 0.8
            elif product.price < 200:
                base_popularity *= 1.2

            # Add randomness to simulate real data
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
                if budget_range > 0:
                    position = (product.price - min_budget) / budget_range
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
        # Placeholder - would implement real collaborative filtering
        return {product.id: 0.5 for product in candidates}

    def _calculate_algorithm_weights(self, request: RecommendationRequest, has_collaborative: bool) -> Dict[str, float]:
        """Calculate weights for different algorithms based on request"""
        weights = {
            "content": 0.25,
            "popularity": 0.15,
            "style": 0.25,
            "functional": 0.20,
            "price": 0.15,
            "collaborative": 0.0
        }

        if has_collaborative:
            weights["collaborative"] = 0.20
            for key in ["content", "popularity", "style"]:
                weights[key] *= 0.8

        if request.style_preferences and len(request.style_preferences) > 1:
            weights["style"] += 0.1
            weights["content"] -= 0.05
            weights["popularity"] -= 0.05

        if request.room_context and len(request.functional_requirements or []) > 2:
            weights["functional"] += 0.1
            weights["popularity"] -= 0.1

        return weights

    def rank_and_generate_recommendations(
        self,
        products: List[Product],
        product_scores: List[ProductScore],
        request: RecommendationRequest
    ) -> List[RecommendationResult]:
        """
        Convert product scores to recommendations with reasoning

        Args:
            products: List of products
            product_scores: Scoring results
            request: Original request

        Returns:
            List of RecommendationResult objects
        """
        # Create product ID to product mapping
        product_map = {p.id: p for p in products}

        recommendations = []
        for score_obj in product_scores:
            product = product_map.get(score_obj.product_id)
            if not product:
                continue

            reasoning = self._generate_recommendation_reasoning(
                product,
                score_obj.content_score,
                score_obj.style_score,
                score_obj.functional_score,
                score_obj.price_score
            )

            recommendation = RecommendationResult(
                product_id=product.id,
                product_name=product.name,
                confidence_score=score_obj.overall_score,
                reasoning=reasoning,
                style_match_score=score_obj.style_score,
                functional_match_score=score_obj.functional_score,
                price_score=score_obj.price_score,
                popularity_score=score_obj.popularity_score,
                compatibility_score=(score_obj.style_score + score_obj.functional_score) / 2,
                overall_score=score_obj.overall_score
            )

            recommendations.append(recommendation)

        # Sort by overall score
        recommendations.sort(key=lambda x: x.overall_score, reverse=True)

        return recommendations

    # Helper methods
    def _extract_product_style(self, product: Product) -> str:
        """Extract style from product data"""
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

        return "contemporary"

    def _extract_product_function(self, product: Product) -> str:
        """Extract primary function from product"""
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

        return "decoration"

    def _calculate_style_similarity(self, style1: str, style2: str) -> float:
        """Calculate similarity between two styles"""
        return self.style_compatibility_matrix.get(style1, {}).get(style2, 0.0)

    def _calculate_color_match(self, product: Product, preferred_colors: List[str]) -> float:
        """Calculate color match score"""
        return 0.7  # Placeholder

    def _calculate_material_match(self, product: Product, preferred_materials: List[str]) -> float:
        """Calculate material match score"""
        return 0.6  # Placeholder

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
