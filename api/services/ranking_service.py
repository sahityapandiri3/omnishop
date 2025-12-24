"""
Deterministic, explainable product ranking service.

This service implements a weighted scoring system for ranking products
based on multiple factors including vector similarity, style matching,
attribute matching, material/color preferences, and budget fit.

Scoring Formula:
    FINAL_SCORE =
        0.45 * vector_similarity      +
        0.15 * attribute_match_score  +
        0.15 * style_score            +
        0.10 * material_color_score   +
        0.10 * budget_score           +
        0.05 * text_intent_score

Budget Scoring:
    - Products within budget get score 1.0
    - Products up to 20% over budget get score 0.7
    - Products up to 50% over budget get score 0.4
    - Products over 50% above budget get score 0.2
    - If no budget specified, all products get neutral score 0.5
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RankedProduct:
    """A product with its ranking score and breakdown."""
    product: Any
    final_score: float
    breakdown: Dict[str, float]


class RankingService:
    """Deterministic, explainable product ranking."""

    # Scoring weights - must sum to 1.0
    WEIGHTS = {
        "vector_similarity": 0.45,
        "attribute_match": 0.15,
        "style": 0.15,
        "material_color": 0.10,
        "budget": 0.10,
        "text_intent": 0.05,
    }

    # Material family mappings for compatibility matching
    MATERIAL_FAMILIES = {
        "wood": [
            "oak", "walnut", "teak", "mango", "sheesham", "pine", "ash",
            "birch", "acacia", "rosewood", "mahogany", "cedar", "bamboo",
            "plywood", "mdf", "engineered wood", "solid wood", "reclaimed wood"
        ],
        "metal": [
            "iron", "steel", "brass", "copper", "aluminum", "chrome",
            "gold", "silver", "bronze", "stainless steel", "wrought iron",
            "powder coated", "galvanized"
        ],
        "fabric": [
            "cotton", "linen", "velvet", "polyester", "wool", "silk",
            "jute", "canvas", "tweed", "chenille", "microfiber", "suede",
            "leather", "faux leather", "leatherette", "upholstery"
        ],
        "stone": [
            "marble", "granite", "terrazzo", "concrete", "slate", "quartz",
            "limestone", "travertine", "onyx", "sandstone"
        ],
        "glass": [
            "tempered glass", "frosted glass", "clear glass", "tinted glass",
            "mirror", "acrylic"
        ],
        "rattan": [
            "rattan", "cane", "wicker", "bamboo", "seagrass", "water hyacinth"
        ],
    }

    # Color family mappings for similarity matching
    COLOR_FAMILIES = {
        "neutral": [
            "white", "black", "grey", "gray", "beige", "cream", "ivory",
            "off-white", "charcoal", "slate", "taupe", "natural"
        ],
        "brown": [
            "brown", "tan", "chocolate", "walnut", "oak", "espresso",
            "coffee", "caramel", "chestnut", "mahogany", "teak", "cognac"
        ],
        "blue": [
            "blue", "navy", "teal", "turquoise", "cyan", "indigo",
            "cobalt", "royal blue", "sky blue", "powder blue", "aqua"
        ],
        "green": [
            "green", "olive", "sage", "mint", "forest", "emerald",
            "moss", "lime", "hunter green", "seafoam"
        ],
        "warm": [
            "red", "orange", "yellow", "gold", "coral", "rust",
            "terracotta", "burgundy", "maroon", "amber", "mustard"
        ],
        "pink": [
            "pink", "rose", "blush", "magenta", "fuchsia", "salmon",
            "dusty pink", "mauve"
        ],
        "purple": [
            "purple", "violet", "lavender", "plum", "lilac", "grape"
        ],
    }

    # Adjacent/similar types for partial matching
    ADJACENT_TYPES = {
        "2-seater": ["3-seater", "loveseat", "2 seater"],
        "3-seater": ["2-seater", "4-seater", "3 seater"],
        "4-seater": ["3-seater", "sectional", "4 seater"],
        "sectional": ["4-seater", "l-shaped", "corner"],
        "l-shaped": ["sectional", "corner"],
        "round": ["oval", "circular"],
        "oval": ["round", "elliptical"],
        "rectangular": ["square", "oblong"],
        "square": ["rectangular"],
        "single": ["twin"],
        "twin": ["single"],
        "queen": ["double", "full"],
        "king": ["california king", "super king"],
    }

    def rank_products(
        self,
        products: list,
        vector_scores: Dict[int, float],
        query_embedding: Optional[List[float]] = None,
        user_category: Optional[str] = None,
        user_type: Optional[str] = None,
        user_capacity: Optional[int] = None,
        user_primary_style: Optional[str] = None,
        user_secondary_style: Optional[str] = None,
        user_materials: Optional[List[str]] = None,
        user_color: Optional[str] = None,
        user_budget_max: Optional[float] = None,
    ) -> List[RankedProduct]:
        """
        Rank products using weighted scoring.

        Args:
            products: List of Product model instances
            vector_scores: Dict mapping product_id to semantic similarity score [0,1]
            query_embedding: Optional query embedding for text intent matching
            user_category: Category ID/name the user is searching in
            user_type: Optional product type (e.g., "3-seater")
            user_capacity: Optional desired capacity (e.g., 4 for 4-seater)
            user_primary_style: User's primary style preference
            user_secondary_style: User's secondary style preference
            user_materials: List of preferred materials
            user_color: Preferred color
            user_budget_max: Maximum budget for this category (products over budget get lower scores)

        Returns:
            List of RankedProduct sorted by final_score (descending)
        """
        ranked = []

        for product in products:
            # Compute all score components
            scores = {
                "vector_similarity": vector_scores.get(product.id, 0.0),
                "attribute_match": self._compute_attribute_score(
                    product, user_category, user_type, user_capacity
                ),
                "style": self._compute_style_score(
                    product, user_primary_style, user_secondary_style
                ),
                "material_color": self._compute_material_color_score(
                    product, user_materials, user_color
                ),
                "budget": self._compute_budget_score(
                    product, user_budget_max
                ),
                "text_intent": self._compute_text_intent_score(
                    product, query_embedding
                ),
            }

            # Compute weighted final score
            final_score = sum(
                self.WEIGHTS[key] * scores[key]
                for key in self.WEIGHTS
            )

            ranked.append(RankedProduct(
                product=product,
                final_score=round(final_score, 4),
                breakdown={k: round(v, 4) for k, v in scores.items()}
            ))

        # Sort by final_score descending
        ranked.sort(key=lambda x: x.final_score, reverse=True)

        return ranked

    def _compute_attribute_score(
        self,
        product,
        user_category: Optional[str],
        user_type: Optional[str],
        user_capacity: Optional[int]
    ) -> float:
        """
        Compute attribute match score based on category, type, and capacity.

        Boost-only approach:
        - Match = boost (score > 0.5)
        - No match = neutral (0.5)

        Returns a score in [0, 1] range.
        """
        scores = []

        # Category match (should always be 1.0 if products are pre-filtered)
        if user_category is not None:
            category_match = 1.0 if str(product.category_id) == str(user_category) else 0.5  # Neutral if no match
            scores.append(category_match)

        # Type match (optional)
        if user_type:
            product_type = getattr(product, 'type', None) or getattr(product, 'product_type', None)
            if product_type:
                user_type_lower = user_type.lower()
                product_type_lower = product_type.lower()

                if product_type_lower == user_type_lower:
                    scores.append(1.0)  # Exact match = boost
                elif self._is_adjacent_type(product_type_lower, user_type_lower):
                    scores.append(0.75)  # Adjacent match = partial boost
                else:
                    scores.append(0.5)  # No match = neutral
            else:
                scores.append(0.5)  # No type info = neutral

        # Capacity match (optional)
        if user_capacity is not None:
            product_capacity = getattr(product, 'capacity', None) or getattr(product, 'seating_capacity', None)
            if product_capacity is not None:
                try:
                    diff = abs(int(product_capacity) - int(user_capacity))
                    if diff == 0:
                        scores.append(1.0)  # Exact match = boost
                    elif diff == 1:
                        scores.append(0.75)  # Close match = partial boost
                    elif diff == 2:
                        scores.append(0.6)  # Okay match = slight boost
                    else:
                        scores.append(0.5)  # No match = neutral
                except (ValueError, TypeError):
                    scores.append(0.5)  # Invalid data = neutral
            else:
                scores.append(0.5)  # No capacity info = neutral

        # Return average of all attribute scores, or neutral 0.5 if none
        return sum(scores) / len(scores) if scores else 0.5

    def _is_adjacent_type(self, product_type: str, user_type: str) -> bool:
        """Check if two types are adjacent/similar."""
        adjacent = self.ADJACENT_TYPES.get(product_type, [])
        return user_type in adjacent or product_type in self.ADJACENT_TYPES.get(user_type, [])

    def _compute_style_score(
        self,
        product,
        user_primary_style: Optional[str],
        user_secondary_style: Optional[str]
    ) -> float:
        """
        Compute style match score using categorical matching.

        Boost-only approach:
        - Match via primary_style = boost to 1.0
        - Match via secondary_style = boost to 0.75
        - No match = neutral (0.5)

        Formula: style_score = 0.7 * primary_match + 0.3 * secondary_match

        Returns neutral 0.5 if user has no style preference.
        """
        if not user_primary_style:
            return 0.5  # Neutral when user has no preference

        product_primary = getattr(product, 'primary_style', None)
        product_secondary = getattr(product, 'secondary_style', None)

        # Normalize styles for comparison
        user_primary_lower = user_primary_style.lower() if user_primary_style else None
        user_secondary_lower = user_secondary_style.lower() if user_secondary_style else None
        product_primary_lower = product_primary.lower() if product_primary else None
        product_secondary_lower = product_secondary.lower() if product_secondary else None

        # Does product match user's PRIMARY style preference?
        # Start at 0.5 (neutral), boost if match found
        primary_match = 0.5  # Neutral baseline
        if product_primary_lower == user_primary_lower:
            primary_match = 1.0  # Exact match on primary = full boost
        elif product_secondary_lower == user_primary_lower:
            primary_match = 0.75  # Match on secondary = partial boost

        # Does product match user's SECONDARY style preference?
        secondary_match = 0.5  # Neutral baseline
        if user_secondary_lower:
            if product_primary_lower == user_secondary_lower:
                secondary_match = 1.0  # Exact match on primary = full boost
            elif product_secondary_lower == user_secondary_lower:
                secondary_match = 0.75  # Match on secondary = partial boost

        # Combine with 70/30 weighting
        return 0.7 * primary_match + 0.3 * secondary_match

    def _compute_material_color_score(
        self,
        product,
        user_materials: Optional[List[str]],
        user_color: Optional[str]
    ) -> float:
        """
        Compute material and color match score.

        60% weight to material, 40% to color.
        Returns neutral 0.5 if user has no preferences.
        """
        material_score = 0.5  # Neutral default
        color_score = 0.5     # Neutral default

        if user_materials:
            product_material = getattr(product, 'material_primary', None)
            material_score = self._compute_material_match(product_material, user_materials)

        if user_color:
            product_color = getattr(product, 'color_primary', None)
            color_score = self._compute_color_match(product_color, user_color)

        return 0.6 * material_score + 0.4 * color_score

    def _compute_material_match(
        self,
        product_material: Optional[str],
        user_materials: List[str]
    ) -> float:
        """
        Compute material match score.

        Boost-only approach:
        - Exact match = 1.0 (full boost)
        - Family match = 0.8-0.9 (partial boost)
        - No match = 0.5 (neutral)
        - No material info = 0.5 (neutral)
        """
        if not product_material:
            return 0.5  # Neutral for missing info

        product_material_lower = product_material.lower()

        for pref in user_materials:
            pref_lower = pref.lower()

            # Exact match
            if product_material_lower == pref_lower:
                return 1.0

            # Check if product material is in the preferred family
            # e.g., user wants "wood", product has "oak"
            if pref_lower in self.MATERIAL_FAMILIES:
                if product_material_lower in self.MATERIAL_FAMILIES[pref_lower]:
                    return 0.9

            # Check if preference is a member of product material's family
            # e.g., user wants "oak", product has "wood"
            for family, members in self.MATERIAL_FAMILIES.items():
                if product_material_lower == family and pref_lower in members:
                    return 0.8

            # Check if both are in the same family
            for family, members in self.MATERIAL_FAMILIES.items():
                if product_material_lower in members and pref_lower in members:
                    return 0.85

        return 0.5  # No match = neutral

    def _compute_color_match(
        self,
        product_color: Optional[str],
        user_color: str
    ) -> float:
        """
        Compute color match score using color families.

        Boost-only approach:
        - Exact match = 1.0 (full boost)
        - Same color family = 0.85 (partial boost)
        - No match = 0.5 (neutral)
        - No color info = 0.5 (neutral)
        """
        if not product_color:
            return 0.5  # Neutral for missing info

        product_color_lower = product_color.lower()
        user_color_lower = user_color.lower()

        # Exact match
        if product_color_lower == user_color_lower:
            return 1.0

        # Find color families
        product_family = None
        user_family = None

        for family, colors in self.COLOR_FAMILIES.items():
            if product_color_lower in colors:
                product_family = family
            if user_color_lower in colors:
                user_family = family

        # Same color family = partial boost
        if product_family and user_family and product_family == user_family:
            return 0.85

        return 0.5  # Different colors = neutral

    def _compute_budget_score(
        self,
        product,
        user_budget_max: Optional[float]
    ) -> float:
        """
        Compute budget fit score based on product price vs category budget.

        Scoring approach:
        - Within budget = 1.0 (full score)
        - Up to 20% over = 0.7 (still good, slight stretch)
        - Up to 50% over = 0.4 (significant stretch)
        - Over 50% above budget = 0.2 (out of budget but still shown)
        - No budget specified = 0.5 (neutral)
        - No price info = 0.5 (neutral)

        Returns a score in [0, 1] range.
        """
        if not user_budget_max:
            return 0.5  # Neutral when no budget specified

        product_price = getattr(product, 'price', None)
        if not product_price:
            return 0.5  # Neutral for missing price info

        try:
            price = float(product_price)
            budget = float(user_budget_max)

            if price <= budget:
                return 1.0  # Within budget = perfect score

            # Calculate how much over budget
            over_ratio = (price - budget) / budget

            if over_ratio <= 0.20:
                return 0.7  # Up to 20% over = still good
            elif over_ratio <= 0.50:
                return 0.4  # Up to 50% over = significant stretch
            else:
                return 0.2  # Over 50% = out of budget but still shown

        except (ValueError, TypeError):
            return 0.5  # Invalid data = neutral

    def _compute_text_intent_score(
        self,
        product,
        query_embedding: Optional[List[float]]
    ) -> float:
        """
        Compute text intent score using cosine similarity between
        query embedding and product embedding.

        Returns neutral 0.5 if embeddings are unavailable.
        """
        if not query_embedding:
            return 0.5

        product_embedding_str = getattr(product, 'embedding', None)
        if not product_embedding_str:
            return 0.5

        try:
            product_embedding = json.loads(product_embedding_str)
            return self._cosine_similarity(query_embedding, product_embedding)
        except (json.JSONDecodeError, TypeError):
            return 0.5

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


# Singleton instance
_ranking_service: Optional[RankingService] = None


def get_ranking_service() -> RankingService:
    """Get or create the ranking service singleton."""
    global _ranking_service
    if _ranking_service is None:
        _ranking_service = RankingService()
    return _ranking_service
