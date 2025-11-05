"""
Advanced Product Recommendation Engine for Interior Design
"""
import logging
import numpy as np
import asyncio
import re
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import json
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from database.models import Product, ProductImage, ProductAttribute, ChatSession, ChatMessage
from api.services.nlp_processor import design_nlp_processor

logger = logging.getLogger(__name__)


@dataclass
class RecommendationRequest:
    """Request for product recommendations with attribute matching"""
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    room_context: Optional[Dict[str, Any]] = None
    budget_range: Optional[Tuple[float, float]] = None
    style_preferences: List[str] = field(default_factory=list)
    functional_requirements: List[str] = field(default_factory=list)
    product_keywords: List[str] = field(default_factory=list)
    exclude_products: List[str] = field(default_factory=list)
    max_recommendations: int = 20

    # NEW FIELDS for attribute matching
    user_colors: Optional[List[str]] = None  # e.g., ['red', 'burgundy']
    user_materials: Optional[List[str]] = None  # e.g., ['leather', 'wood']
    user_textures: Optional[List[str]] = None  # e.g., ['smooth', 'soft']
    user_patterns: Optional[List[str]] = None  # e.g., ['solid', 'striped']
    user_dimensions: Optional[Dict[str, float]] = None  # e.g., {'room_width': 120, 'room_depth': 100}
    user_styles: Optional[List[str]] = None  # e.g., ['modern', 'contemporary']
    strict_attribute_match: bool = False  # Enable strict filtering (zero false positives)


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
            },
            "sleeping": {
                "bedroom": 1.0, "living_room": 0.2, "office": 0.1, "dining_room": 0.0,
                "kitchen": 0.0, "bathroom": 0.0, "entryway": 0.0
            },
            "workspace": {
                "office": 1.0, "bedroom": 0.6, "living_room": 0.5, "dining_room": 0.3,
                "kitchen": 0.2, "bathroom": 0.0, "entryway": 0.1
            },
            "accessory": {
                "living_room": 0.9, "bedroom": 0.9, "office": 0.7, "dining_room": 0.8,
                "kitchen": 0.6, "bathroom": 0.7, "entryway": 0.8
            },
            "decoration": {
                "living_room": 0.8, "bedroom": 0.8, "office": 0.6, "dining_room": 0.7,
                "kitchen": 0.5, "bathroom": 0.6, "entryway": 0.7
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

            # Apply strict attribute filtering if enabled (ZERO false positives)
            if request.strict_attribute_match:
                candidates = await self._apply_strict_attribute_filtering(candidates, request, db)
                logger.info(f"Strict filtering: {len(candidates)} products match attribute criteria")

                # If no products match, return empty results
                if not candidates:
                    logger.info("Strict filtering returned zero products - no matches found")
                    return RecommendationResponse(
                        recommendations=[],
                        total_found=0,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        recommendation_strategy="strict_filtering_zero_results",
                        personalization_level=0.0,
                        diversity_score=0.0
                    )

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

    async def _apply_strict_attribute_filtering(
        self,
        candidates: List[Product],
        request: RecommendationRequest,
        db: AsyncSession
    ) -> List[Product]:
        """
        Apply strict attribute filtering to ensure ZERO false positives

        Only returns products that match ALL specified attributes:
        - If user specifies color → ONLY products with that color
        - If user specifies material → ONLY products with that material
        - If user specifies style → ONLY products with that style
        - If user specifies texture → ONLY products with that texture
        - If user specifies pattern → ONLY products with that pattern

        Products with NULL attributes are EXCLUDED when that attribute is specified.
        """
        filtered_candidates = []

        # Extract user preferences
        user_colors = request.user_colors or []
        user_materials = request.user_materials or []
        user_textures = request.user_textures or []
        user_patterns = request.user_patterns or []
        user_styles = request.user_styles or []

        # If no attributes specified, return all candidates
        if not any([user_colors, user_materials, user_textures, user_patterns, user_styles]):
            return candidates

        for product in candidates:
            # Check each specified attribute
            passes_filter = True

            # Color filtering
            if user_colors:
                result = await db.execute(
                    select(ProductAttribute.attribute_value)
                    .where(
                        ProductAttribute.product_id == product.id,
                        ProductAttribute.attribute_name.in_(['color_primary', 'color_secondary', 'color_accent'])
                    )
                )
                product_colors = [c.lower() for c in result.scalars().all() if c]

                # Product MUST have matching color
                if not product_colors or not any(uc.lower() in product_colors for uc in user_colors):
                    # Check color families for fuzzy matching
                    color_families = self._get_color_families()
                    has_family_match = False
                    for user_color in user_colors:
                        user_family = color_families.get(user_color.lower(), [])
                        if any(pc in user_family for pc in product_colors):
                            has_family_match = True
                            break
                    if not has_family_match:
                        passes_filter = False

            # Material filtering
            if passes_filter and user_materials:
                result = await db.execute(
                    select(ProductAttribute.attribute_value)
                    .where(
                        ProductAttribute.product_id == product.id,
                        ProductAttribute.attribute_name.in_(['material_primary', 'material_secondary'])
                    )
                )
                product_materials = [m.lower() for m in result.scalars().all() if m]

                # Product MUST have matching material
                if not product_materials or not any(um.lower() in product_materials for um in user_materials):
                    passes_filter = False

            # Texture filtering
            if passes_filter and user_textures:
                result = await db.execute(
                    select(ProductAttribute.attribute_value)
                    .where(
                        ProductAttribute.product_id == product.id,
                        ProductAttribute.attribute_name == 'texture'
                    )
                )
                product_texture = result.scalar_one_or_none()

                # Product MUST have matching texture
                if not product_texture or not any(ut.lower() in product_texture.lower() for ut in user_textures):
                    passes_filter = False

            # Pattern filtering
            if passes_filter and user_patterns:
                result = await db.execute(
                    select(ProductAttribute.attribute_value)
                    .where(
                        ProductAttribute.product_id == product.id,
                        ProductAttribute.attribute_name == 'pattern'
                    )
                )
                product_pattern = result.scalar_one_or_none()

                # Product MUST have matching pattern
                if not product_pattern or not any(up.lower() in product_pattern.lower() for up in user_patterns):
                    passes_filter = False

            # Style filtering
            if passes_filter and user_styles:
                result = await db.execute(
                    select(ProductAttribute.attribute_value)
                    .where(
                        ProductAttribute.product_id == product.id,
                        ProductAttribute.attribute_name == 'style'
                    )
                )
                product_style = result.scalar_one_or_none()

                # Product MUST have matching style
                if not product_style or not any(us.lower() in product_style.lower() for us in user_styles):
                    passes_filter = False

            # Add to filtered list if passes all checks
            if passes_filter:
                filtered_candidates.append(product)

        logger.info(f"Strict attribute filtering: {len(candidates)} → {len(filtered_candidates)} products "
                   f"(colors={user_colors}, materials={user_materials}, styles={user_styles})")

        return filtered_candidates

    def _categorize_keywords(self, keywords: List[str]) -> Dict[str, List[str]]:
        """Categorize keywords into product categories to enable strict filtering"""

        # Define mutually exclusive product categories
        categories = {
            'ceiling_lighting': ['ceiling lamp', 'ceiling light', 'chandelier', 'pendant', 'overhead light', 'pendant light'],
            'portable_lighting': ['table lamp', 'desk lamp', 'floor lamp'],
            'wall_lighting': ['wall lamp', 'sconce', 'wall light'],
            'sofas': ['sofa', 'couch', 'sectional', 'loveseat'],  # Sofas - replaceable items
            'chairs': ['chair', 'armchair', 'accent chair', 'side chair', 'sofa chair', 'recliner', 'dining chair'],  # Chairs - additive items only
            'other_seating': ['bench', 'stool', 'ottoman'],  # Other seating - additive items
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
                    # IMPORTANT: Only match against product NAME, not description
                    # Description matching causes false positives (e.g., "place next to a sofa" in table descriptions)
                    escaped_keyword = re.escape(keyword)
                    keyword_conditions.append(Product.name.op('~*')(rf'\y{escaped_keyword}\y'))

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

        # CRITICAL: Exclude accessories and non-furniture items
        # These terms indicate the product is NOT actual furniture (e.g., "Sofa Swatches" is not a sofa)
        accessory_exclusions = [
            'swatch', 'swatches', 'sample', 'samples',  # Fabric samples
            'fabric', 'material', 'textile',  # Materials only
            'cushion', 'pillow', 'throw pillow',  # Soft accessories
            'cover', 'slipcover', 'protector',  # Covers
            'accessory', 'accessories',  # Generic accessories
            'part', 'parts', 'component',  # Replacement parts
            'hardware', 'screw', 'nail', 'bolt',  # Hardware
            'tool', 'tools', 'kit',  # Tools
            'cleaner', 'polish', 'wax',  # Maintenance products
            'manual', 'guide', 'instruction',  # Documentation
        ]

        # Build exclusion conditions
        exclusion_conditions = []
        for exclusion in accessory_exclusions:
            escaped = re.escape(exclusion)
            # Exclude if word appears in product name
            exclusion_conditions.append(~Product.name.op('~*')(rf'\y{escaped}\y'))

        if exclusion_conditions:
            query = query.where(and_(*exclusion_conditions))
            logger.info(f"Applied {len(accessory_exclusions)} accessory exclusions")

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
        """
        Content-based filtering using product attributes

        NEW SCORING WEIGHTS (with real attribute matching):
        - Keyword relevance: 30% (reduced from 40%)
        - Color match: 15% (increased from 10%, now uses real data)
        - Material match: 15% (increased from 10%, now uses real data)
        - Style match: 15% (reduced from 20%)
        - Size match: 10% (NEW)
        - Texture match: 5% (NEW)
        - Pattern match: 5% (NEW)
        - Description: 5% (reduced from 20%)
        """
        scores = {}

        # Extract preferences from request
        style_preferences = request.style_preferences or []
        user_prefs = request.user_preferences or {}

        # Get user attribute preferences
        user_colors = request.user_colors or user_prefs.get("colors", [])
        user_materials = request.user_materials or user_prefs.get("materials", [])
        user_textures = request.user_textures or user_prefs.get("textures", [])
        user_patterns = request.user_patterns or user_prefs.get("patterns", [])
        user_dimensions = request.user_dimensions or user_prefs.get("dimensions", {})

        for product in candidates:
            score = 0.0

            # Keyword relevance matching (30% - reduced from 40%)
            if request.product_keywords:
                keyword_match = self._calculate_keyword_relevance(product, request.product_keywords)
                score += keyword_match * 0.30
                logger.debug(f"Product {product.id} '{product.name}': keyword_match={keyword_match:.2f}")

            # Color matching (15% - was placeholder, now real)
            if user_colors:
                color_match = await self._calculate_color_match(product, user_colors, db)
                score += color_match * 0.15
                logger.debug(f"Product {product.id}: color_match={color_match:.2f}")

            # Material matching (15% - was placeholder, now real)
            if user_materials:
                material_match = await self._calculate_material_match(product, user_materials, db)
                score += material_match * 0.15
                logger.debug(f"Product {product.id}: material_match={material_match:.2f}")

            # Style matching (15% - reduced from 20%)
            if style_preferences:
                product_style = self._extract_product_style(product)
                style_match = max([
                    self._calculate_style_similarity(style, product_style)
                    for style in style_preferences
                ], default=0.0)
                score += style_match * 0.15

            # Size matching (10% - NEW)
            if user_dimensions:
                size_match = await self._calculate_size_match(product, user_dimensions, db)
                score += size_match * 0.10

            # Texture matching (5% - NEW)
            if user_textures:
                texture_match = await self._calculate_texture_match(product, user_textures, db)
                score += texture_match * 0.05

            # Pattern matching (5% - NEW)
            if user_patterns:
                pattern_match = await self._calculate_pattern_match(product, user_patterns, db)
                score += pattern_match * 0.05

            # Description similarity (5% - reduced from 20%)
            if "description_keywords" in user_prefs:
                desc_match = self._calculate_description_similarity(product, user_prefs["description_keywords"])
                score += desc_match * 0.05

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
        # Base weights - Content now includes keyword relevance, so boost it significantly
        weights = {
            "content": 0.40,       # Increased from 0.25 - now includes keyword relevance
            "popularity": 0.10,    # Decreased from 0.15
            "style": 0.20,         # Decreased from 0.25
            "functional": 0.20,    # Same
            "price": 0.10,         # Decreased from 0.15
            "collaborative": 0.0
        }

        # Adjust based on available information
        if has_collaborative:
            weights["collaborative"] = 0.20
            # Redistribute other weights
            for key in ["content", "popularity", "style"]:
                weights[key] *= 0.8

        # Boost content weight if specific product keywords provided (user knows what they want)
        if request.product_keywords and len(request.product_keywords) > 0:
            weights["content"] += 0.15  # Boost content score heavily for keyword searches
            weights["popularity"] -= 0.10
            weights["style"] -= 0.05

        # Boost style weight if strong style preferences
        if request.style_preferences and len(request.style_preferences) > 1:
            weights["style"] += 0.1
            weights["content"] -= 0.05
            weights["popularity"] -= 0.05

        # Boost functional weight if room context is strong
        if request.room_context and len(request.functional_requirements or []) > 2:
            weights["functional"] += 0.1
            weights["popularity"] -= 0.1

        # Normalize to ensure sum is 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

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
        # Order matters: check more specific terms first
        function_map = {
            # Lighting (check before 'table')
            "lamp": "lighting", "chandelier": "lighting", "light": "lighting",
            # Seating
            "sofa": "seating", "chair": "seating", "armchair": "seating", "bench": "seating",
            # Sleeping
            "bed": "sleeping", "mattress": "sleeping",
            # Storage
            "dresser": "storage", "bookshelf": "storage", "cabinet": "storage", "wardrobe": "storage",
            # Workspace
            "desk": "workspace", "office": "workspace",
            # Dining (check after lamp to avoid 'table lamp' matching as dining)
            "dining table": "dining", "table": "dining",
            # Accessories
            "pillow": "accessory", "cushion": "accessory", "throw": "accessory",
            "vase": "accessory", "mirror": "accessory", "rug": "accessory"
        }

        product_name = product.name.lower()
        for keyword, function in function_map.items():
            if keyword in product_name:
                return function

        return "decoration"  # default

    def _calculate_keyword_relevance(self, product: Product, keywords: List[str]) -> float:
        """
        Calculate how relevant a product is to the search keywords
        Higher scores for exact matches in product name, especially at the beginning
        """
        if not keywords:
            return 0.5  # Neutral score if no keywords

        product_name = product.name.lower()
        product_desc = (product.description or "").lower()

        max_score = 0.0

        for keyword in keywords:
            keyword = keyword.lower().strip()
            score = 0.0

            # HIGHEST PRIORITY: Keyword at start of product name (e.g., "Sofa Bed" for "sofa")
            if product_name.startswith(keyword + " ") or product_name == keyword:
                score = 1.0

            # HIGH PRIORITY: Keyword is a standalone word in product name (with word boundaries)
            elif re.search(rf'\b{re.escape(keyword)}\b', product_name):
                # Check position - earlier is better
                match_pos = product_name.find(keyword)
                # Score: 0.9 if in first half of name, 0.7 otherwise
                score = 0.9 if match_pos < len(product_name) / 2 else 0.7

            # MEDIUM PRIORITY: Keyword contained in a word (e.g., "sectional" contains "section")
            elif keyword in product_name:
                score = 0.5

            # LOW PRIORITY: Keyword in description
            elif re.search(rf'\b{re.escape(keyword)}\b', product_desc):
                score = 0.3

            # Keep the highest score across all keywords
            max_score = max(max_score, score)

        return max_score

    def _calculate_style_similarity(self, style1: str, style2: str) -> float:
        """Calculate similarity between two styles"""
        return self.style_compatibility_matrix.get(style1, {}).get(style2, 0.0)

    async def _calculate_color_match(
        self,
        product: Product,
        preferred_colors: List[str],
        db: AsyncSession
    ) -> float:
        """
        Calculate color match score using ProductAttribute table

        Returns:
            1.0 = Exact match (primary color matches)
            0.8 = Secondary match (secondary/accent color matches)
            0.5 = Color family match (similar colors)
            0.0 = No match
        """
        if not preferred_colors:
            return 1.0  # No preference = all colors acceptable

        try:
            # Query product colors from ProductAttribute
            result = await db.execute(
                select(ProductAttribute.attribute_value)
                .where(
                    ProductAttribute.product_id == product.id,
                    ProductAttribute.attribute_name.in_(['color_primary', 'color_secondary', 'color_accent'])
                )
            )
            product_colors = [color.lower() for color in result.scalars().all() if color]

            if not product_colors:
                return 0.0  # No color data = exclude if user specified color

            # Exact match
            for user_color in preferred_colors:
                if user_color.lower() in product_colors:
                    return 1.0

            # Color family match
            color_families = self._get_color_families()
            for user_color in preferred_colors:
                user_family = color_families.get(user_color.lower(), [])
                for product_color in product_colors:
                    if product_color in user_family:
                        return 0.5

            return 0.0

        except Exception as e:
            logger.error(f"Error calculating color match for product {product.id}: {e}")
            return 0.5  # Default to neutral score on error

    async def _calculate_material_match(
        self,
        product: Product,
        preferred_materials: List[str],
        db: AsyncSession
    ) -> float:
        """
        Calculate material match score using ProductAttribute table

        Returns:
            1.0 = Exact match (primary material matches)
            0.7 = Compatible materials (contains preferred material)
            0.0 = No match
        """
        if not preferred_materials:
            return 1.0  # No preference = all materials acceptable

        try:
            # Query product materials from ProductAttribute
            result = await db.execute(
                select(ProductAttribute.attribute_value)
                .where(
                    ProductAttribute.product_id == product.id,
                    ProductAttribute.attribute_name.in_(['material_primary', 'material_secondary'])
                )
            )
            product_materials = [mat.lower() for mat in result.scalars().all() if mat]

            if not product_materials:
                return 0.0  # No material data = exclude

            # Exact match
            for user_material in preferred_materials:
                if user_material.lower() in product_materials:
                    return 1.0

            # Compatible materials (substring match)
            for user_material in preferred_materials:
                for product_material in product_materials:
                    if (user_material.lower() in product_material or
                        product_material in user_material.lower()):
                        return 0.7

            return 0.0

        except Exception as e:
            logger.error(f"Error calculating material match for product {product.id}: {e}")
            return 0.5  # Default to neutral score on error

    async def _calculate_size_match(
        self,
        product: Product,
        room_dimensions: Dict[str, float],
        db: AsyncSession
    ) -> float:
        """
        Calculate size match score based on room dimensions

        Returns:
            1.0 = Product fits comfortably (<30% of room dimension)
            0.7 = Tight fit (30-50% of room dimension)
            0.3 = Very tight (50-70%)
            0.0 = Too large (>70%)
        """
        if not room_dimensions:
            return 1.0  # No room size specified, assume fits

        try:
            # Query product dimensions
            result = await db.execute(
                select(ProductAttribute.attribute_name, ProductAttribute.attribute_value)
                .where(
                    ProductAttribute.product_id == product.id,
                    ProductAttribute.attribute_name.in_(['width', 'depth', 'height'])
                )
            )

            dimensions = {row[0]: float(row[1]) for row in result.all() if row[1]}

            if not dimensions:
                return 0.8  # No dimension data, assume average size

            # Calculate fit score based on room dimensions
            fit_scores = []

            if 'width' in dimensions and 'room_width' in room_dimensions:
                ratio = dimensions['width'] / room_dimensions['room_width']
                if ratio < 0.3:
                    fit_scores.append(1.0)
                elif ratio < 0.5:
                    fit_scores.append(0.7)
                elif ratio < 0.7:
                    fit_scores.append(0.3)
                else:
                    fit_scores.append(0.0)

            return sum(fit_scores) / len(fit_scores) if fit_scores else 0.8

        except Exception as e:
            logger.error(f"Error calculating size match for product {product.id}: {e}")
            return 0.8  # Default to acceptable size on error

    async def _calculate_texture_match(
        self,
        product: Product,
        preferred_textures: List[str],
        db: AsyncSession
    ) -> float:
        """
        Calculate texture match score

        Returns:
            1.0 = Exact match
            0.0 = No match
        """
        if not preferred_textures:
            return 1.0  # No preference

        try:
            result = await db.execute(
                select(ProductAttribute.attribute_value)
                .where(
                    ProductAttribute.product_id == product.id,
                    ProductAttribute.attribute_name == 'texture'
                )
            )
            product_texture = result.scalar_one_or_none()

            if not product_texture:
                return 0.5  # No texture data, neutral score

            for user_texture in preferred_textures:
                if user_texture.lower() in product_texture.lower():
                    return 1.0

            return 0.0

        except Exception as e:
            logger.error(f"Error calculating texture match for product {product.id}: {e}")
            return 0.5

    async def _calculate_pattern_match(
        self,
        product: Product,
        preferred_patterns: List[str],
        db: AsyncSession
    ) -> float:
        """
        Calculate pattern match score

        Returns:
            1.0 = Exact match
            0.0 = No match
        """
        if not preferred_patterns:
            return 1.0  # No preference

        try:
            result = await db.execute(
                select(ProductAttribute.attribute_value)
                .where(
                    ProductAttribute.product_id == product.id,
                    ProductAttribute.attribute_name == 'pattern'
                )
            )
            product_pattern = result.scalar_one_or_none()

            if not product_pattern:
                return 0.5  # No pattern data, neutral score

            for user_pattern in preferred_patterns:
                if user_pattern.lower() in product_pattern.lower():
                    return 1.0

            return 0.0

        except Exception as e:
            logger.error(f"Error calculating pattern match for product {product.id}: {e}")
            return 0.5

    def _get_color_families(self) -> Dict[str, List[str]]:
        """Get color family mappings for fuzzy color matching"""
        return {
            # Reds
            'red': ['red', 'crimson', 'burgundy', 'maroon', 'ruby', 'cherry', 'wine'],
            'crimson': ['red', 'crimson', 'burgundy', 'maroon'],
            'burgundy': ['burgundy', 'maroon', 'wine', 'red'],
            'maroon': ['maroon', 'burgundy', 'red'],

            # Blues
            'blue': ['blue', 'navy', 'royal blue', 'cobalt', 'azure', 'turquoise'],
            'navy': ['navy', 'blue', 'dark blue', 'midnight blue'],
            'azure': ['azure', 'blue', 'light blue', 'sky blue'],

            # Greens
            'green': ['green', 'emerald', 'sage', 'olive', 'forest green'],
            'emerald': ['emerald', 'green', 'jade'],
            'sage': ['sage', 'green', 'mint'],

            # Neutrals
            'gray': ['gray', 'grey', 'charcoal', 'slate', 'silver'],
            'grey': ['gray', 'grey', 'charcoal', 'slate', 'silver'],
            'beige': ['beige', 'tan', 'khaki', 'cream', 'ivory'],
            'white': ['white', 'off-white', 'cream', 'ivory'],
            'black': ['black', 'charcoal', 'ebony'],

            # Browns
            'brown': ['brown', 'chocolate', 'espresso', 'walnut', 'mahogany'],
            'tan': ['tan', 'beige', 'camel', 'khaki'],
        }

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