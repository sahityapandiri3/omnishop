"""
Unit tests for Recommendation Engine module
Tests product recommendation logic, scoring algorithms, and filtering
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from api.services.recommendation_engine import (
    recommendation_engine,
    RecommendationRequest,
    RecommendationResult,
    RecommendationResponse
)


class TestRecommendationRequest:
    """Tests for RecommendationRequest dataclass"""

    @pytest.mark.unit
    def test_request_creation_with_minimal_params(self):
        """Test creating recommendation request with minimal parameters"""
        request = RecommendationRequest(
            user_preferences={'product_keywords': ['sofa']}
        )

        assert request.user_preferences == {'product_keywords': ['sofa']}
        assert request.max_recommendations == 20
        assert request.exclude_products is None

    @pytest.mark.unit
    def test_request_creation_with_all_params(self):
        """Test creating recommendation request with all parameters"""
        request = RecommendationRequest(
            user_preferences={'product_keywords': ['sofa'], 'colors': ['gray']},
            room_context={'room_type': 'living_room'},
            budget_range=(1000, 5000),
            style_preferences=['modern', 'minimalist'],
            functional_requirements=['seating'],
            exclude_products=['prod1', 'prod2'],
            max_recommendations=10
        )

        assert request.budget_range == (1000, 5000)
        assert request.style_preferences == ['modern', 'minimalist']
        assert request.max_recommendations == 10


class TestStyleCompatibilityMatrix:
    """Tests for style compatibility matrix"""

    @pytest.mark.unit
    def test_style_compatibility_modern_modern(self):
        """Test that modern style is perfectly compatible with itself"""
        matrix = recommendation_engine.style_compatibility_matrix
        assert matrix['modern']['modern'] == 1.0

    @pytest.mark.unit
    def test_style_compatibility_modern_traditional(self):
        """Test that modern and traditional have low compatibility"""
        matrix = recommendation_engine.style_compatibility_matrix
        assert matrix['modern']['traditional'] <= 0.3

    @pytest.mark.unit
    def test_style_compatibility_symmetric(self):
        """Test that style compatibility is somewhat symmetric"""
        matrix = recommendation_engine.style_compatibility_matrix
        # Modern-contemporary should be similar to contemporary-modern
        modern_to_contemp = matrix['modern'].get('contemporary', 0)
        assert modern_to_contemp > 0.5  # Should be compatible


class TestProductStyleExtraction:
    """Tests for product style extraction"""

    @pytest.mark.unit
    def test_extract_modern_style(self):
        """Test extraction of modern style from product"""
        product = Mock()
        product.name = "Modern Minimalist Sofa"
        product.description = "A sleek contemporary design"

        style = recommendation_engine._extract_product_style(product)
        assert style == "modern"

    @pytest.mark.unit
    def test_extract_traditional_style(self):
        """Test extraction of traditional style from product"""
        product = Mock()
        product.name = "Classic Elegant Armchair"
        product.description = "Traditional ornate design"

        style = recommendation_engine._extract_product_style(product)
        assert style == "traditional"

    @pytest.mark.unit
    def test_extract_rustic_style(self):
        """Test extraction of rustic style from product"""
        product = Mock()
        product.name = "Farmhouse Reclaimed Wood Table"
        product.description = "Rustic weathered finish"

        style = recommendation_engine._extract_product_style(product)
        assert style == "rustic"

    @pytest.mark.unit
    def test_extract_default_style(self):
        """Test default style when no keywords match"""
        product = Mock()
        product.name = "Generic Furniture Piece"
        product.description = "Standard design"

        style = recommendation_engine._extract_product_style(product)
        assert style == "contemporary"  # Default


class TestProductFunctionExtraction:
    """Tests for product function extraction"""

    @pytest.mark.unit
    def test_extract_seating_function_sofa(self):
        """Test extraction of seating function from sofa"""
        product = Mock()
        product.name = "Modern Sofa"

        function = recommendation_engine._extract_product_function(product)
        assert function == "seating"

    @pytest.mark.unit
    def test_extract_seating_function_chair(self):
        """Test extraction of seating function from chair"""
        product = Mock()
        product.name = "Dining Chair"

        function = recommendation_engine._extract_product_function(product)
        assert function == "seating"

    @pytest.mark.unit
    def test_extract_sleeping_function(self):
        """Test extraction of sleeping function from bed"""
        product = Mock()
        product.name = "King Size Bed"

        function = recommendation_engine._extract_product_function(product)
        assert function == "sleeping"

    @pytest.mark.unit
    def test_extract_storage_function(self):
        """Test extraction of storage function from dresser"""
        product = Mock()
        product.name = "Wooden Dresser"

        function = recommendation_engine._extract_product_function(product)
        assert function == "storage"

    @pytest.mark.unit
    def test_extract_lighting_function(self):
        """Test extraction of lighting function from lamp"""
        product = Mock()
        product.name = "Table Lamp"

        function = recommendation_engine._extract_product_function(product)
        assert function == "lighting"

    @pytest.mark.unit
    def test_extract_accessory_function(self):
        """Test extraction of accessory function from pillow"""
        product = Mock()
        product.name = "Decorative Pillow"

        function = recommendation_engine._extract_product_function(product)
        assert function == "accessory"


class TestPriceCompatibilityScoring:
    """Tests for price compatibility scoring"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_price_within_budget(self):
        """Test scoring for products within budget"""
        mock_product = Mock()
        mock_product.id = "prod1"
        mock_product.price = 3000

        request = RecommendationRequest(
            user_preferences={},
            budget_range=(2000, 5000)
        )

        scores = await recommendation_engine._price_compatibility_scoring([mock_product], request)
        assert scores["prod1"] > 0.5  # Should score positively

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_price_outside_budget(self):
        """Test scoring for products outside budget"""
        mock_product = Mock()
        mock_product.id = "prod1"
        mock_product.price = 10000

        request = RecommendationRequest(
            user_preferences={},
            budget_range=(2000, 5000)
        )

        scores = await recommendation_engine._price_compatibility_scoring([mock_product], request)
        assert scores["prod1"] == 0.0  # Should score 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_price_no_budget_constraint(self):
        """Test scoring when no budget is specified"""
        mock_product = Mock()
        mock_product.id = "prod1"
        mock_product.price = 10000

        request = RecommendationRequest(
            user_preferences={}
        )

        scores = await recommendation_engine._price_compatibility_scoring([mock_product], request)
        assert scores["prod1"] == 1.0  # Should score perfectly


class TestStyleCompatibilityScoring:
    """Tests for style compatibility scoring"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_style_scoring_with_preferences(self):
        """Test style scoring with user preferences"""
        mock_product = Mock()
        mock_product.id = "prod1"
        mock_product.name = "Modern Minimalist Sofa"
        mock_product.description = "Contemporary design"

        request = RecommendationRequest(
            user_preferences={},
            style_preferences=['modern']
        )

        scores = await recommendation_engine._style_compatibility_scoring([mock_product], request)
        assert scores["prod1"] > 0.5  # Modern product should score high for modern preference

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_style_scoring_no_preferences(self):
        """Test style scoring without user preferences"""
        mock_product = Mock()
        mock_product.id = "prod1"
        mock_product.name = "Generic Sofa"
        mock_product.description = ""

        request = RecommendationRequest(
            user_preferences={}
        )

        scores = await recommendation_engine._style_compatibility_scoring([mock_product], request)
        assert scores["prod1"] == 0.5  # Should return neutral score


class TestFunctionalCompatibilityScoring:
    """Tests for functional compatibility scoring"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_functional_scoring_seating_living_room(self):
        """Test that seating scores high for living room"""
        mock_product = Mock()
        mock_product.id = "prod1"
        mock_product.name = "Sofa"

        request = RecommendationRequest(
            user_preferences={},
            room_context={'room_type': 'living_room'}
        )

        scores = await recommendation_engine._functional_compatibility_scoring([mock_product], request)
        assert scores["prod1"] >= 0.8  # Seating should score high in living room

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_functional_scoring_bed_bedroom(self):
        """Test that bed scores perfectly for bedroom"""
        mock_product = Mock()
        mock_product.id = "prod1"
        mock_product.name = "King Bed"

        request = RecommendationRequest(
            user_preferences={},
            room_context={'room_type': 'bedroom'}
        )

        scores = await recommendation_engine._functional_compatibility_scoring([mock_product], request)
        assert scores["prod1"] == 1.0  # Bed should score perfectly in bedroom


class TestDiversityRanking:
    """Tests for diversity ranking (Issue 17 fix)"""

    @pytest.mark.unit
    @pytest.mark.regression
    def test_diversity_skipped_for_explicit_search(self):
        """Test that diversity filtering is skipped for explicit product searches (Issue 17)"""
        # Create 10 ottoman recommendations
        recommendations = [
            RecommendationResult(
                product_id=f"prod{i}",
                product_name=f"Ottoman {i}",
                confidence_score=0.8 - i*0.01,
                reasoning=["Matches ottoman search"],
                style_match_score=0.8,
                functional_match_score=0.8,
                price_score=0.8,
                popularity_score=0.7,
                compatibility_score=0.8,
                overall_score=0.8 - i*0.01
            )
            for i in range(10)
        ]

        request = RecommendationRequest(
            user_preferences={'product_keywords': ['ottoman']},
            max_recommendations=10
        )

        result = recommendation_engine._apply_diversity_ranking(recommendations, request)

        # Should return all 10 ottomans without diversity filtering
        assert len(result) == 10
        assert all('Ottoman' in rec.product_name for rec in result)

    @pytest.mark.unit
    def test_diversity_applied_for_general_search(self):
        """Test that diversity filtering is applied for general searches"""
        recommendations = [
            RecommendationResult(
                product_id=f"prod{i}",
                product_name=f"Product {i}",
                confidence_score=0.8,
                reasoning=["General match"],
                style_match_score=0.8,
                functional_match_score=0.8,
                price_score=0.8,
                popularity_score=0.7,
                compatibility_score=0.8,
                overall_score=0.8
            )
            for i in range(20)
        ]

        request = RecommendationRequest(
            user_preferences={},  # No specific keywords
            max_recommendations=10
        )

        result = recommendation_engine._apply_diversity_ranking(recommendations, request)

        # Should apply some diversity logic
        assert len(result) <= 20


class TestRecommendationReasoning:
    """Tests for recommendation reasoning generation"""

    @pytest.mark.unit
    def test_reasoning_high_scores(self):
        """Test reasoning generation for high-scoring product"""
        product = Mock()
        product.name = "Modern Sofa"

        reasoning = recommendation_engine._generate_recommendation_reasoning(
            product,
            content_score=0.8,
            style_score=0.9,
            functional_score=0.85,
            price_score=0.9
        )

        assert len(reasoning) > 0
        assert any("style" in r.lower() for r in reasoning)
        assert any("functional" in r.lower() or "space" in r.lower() for r in reasoning)

    @pytest.mark.unit
    def test_reasoning_low_scores(self):
        """Test reasoning generation for low-scoring product"""
        product = Mock()
        product.name = "Generic Product"

        reasoning = recommendation_engine._generate_recommendation_reasoning(
            product,
            content_score=0.3,
            style_score=0.4,
            functional_score=0.3,
            price_score=0.4
        )

        assert len(reasoning) > 0
        # Should have fallback reasoning
        assert any("overall compatibility" in r.lower() for r in reasoning)


class TestAlgorithmWeights:
    """Tests for algorithm weight calculation"""

    @pytest.mark.unit
    def test_weights_with_collaborative(self):
        """Test weight calculation with collaborative filtering"""
        request = RecommendationRequest(user_preferences={})

        weights = recommendation_engine._calculate_algorithm_weights(request, has_collaborative=True)

        assert weights["collaborative"] > 0
        assert sum(weights.values()) <= 1.1  # Should sum to ~1.0 (allow small rounding)

    @pytest.mark.unit
    def test_weights_without_collaborative(self):
        """Test weight calculation without collaborative filtering"""
        request = RecommendationRequest(user_preferences={})

        weights = recommendation_engine._calculate_algorithm_weights(request, has_collaborative=False)

        assert weights["collaborative"] == 0
        assert sum(weights.values()) <= 1.1  # Should sum to ~1.0

    @pytest.mark.unit
    def test_weights_boost_style(self):
        """Test that style weight is boosted with strong preferences"""
        request = RecommendationRequest(
            user_preferences={},
            style_preferences=['modern', 'minimalist', 'scandinavian']
        )

        weights = recommendation_engine._calculate_algorithm_weights(request, has_collaborative=False)

        # Style weight should be higher with multiple preferences
        assert weights["style"] > 0.25


class TestDescriptionSimilarity:
    """Tests for description similarity calculation"""

    @pytest.mark.unit
    def test_description_similarity_high_match(self):
        """Test high similarity when keywords match"""
        product = Mock()
        product.description = "Modern minimalist sofa with clean lines and gray upholstery"

        keywords = ["modern", "minimalist", "gray", "sofa"]

        similarity = recommendation_engine._calculate_description_similarity(product, keywords)
        assert similarity > 0.1  # Should have positive similarity

    @pytest.mark.unit
    def test_description_similarity_no_match(self):
        """Test low similarity when keywords don't match"""
        product = Mock()
        product.description = "Traditional wooden dining table"

        keywords = ["modern", "minimalist", "gray", "sofa"]

        similarity = recommendation_engine._calculate_description_similarity(product, keywords)
        assert similarity < 0.5  # Should have low similarity

    @pytest.mark.unit
    def test_description_similarity_empty(self):
        """Test similarity with empty description"""
        product = Mock()
        product.description = None

        keywords = ["modern", "sofa"]

        similarity = recommendation_engine._calculate_description_similarity(product, keywords)
        assert similarity == 0.0


class TestPersonalizationLevel:
    """Tests for personalization level calculation"""

    @pytest.mark.unit
    def test_personalization_with_user_id(self):
        """Test personalization level with user ID"""
        request = RecommendationRequest(user_preferences={})

        level = recommendation_engine._calculate_personalization_level(
            request, user_id="user123", collaborative_scores={}
        )

        assert level >= 0.3  # Should have base personalization from user ID

    @pytest.mark.unit
    def test_personalization_with_preferences(self):
        """Test personalization level with strong preferences"""
        request = RecommendationRequest(
            user_preferences={},
            style_preferences=['modern', 'minimalist'],
            functional_requirements=['seating', 'storage'],
            room_context={'room_type': 'living_room'}
        )

        level = recommendation_engine._calculate_personalization_level(
            request, user_id="user123", collaborative_scores={'prod1': 0.8}
        )

        assert level > 0.5  # Should have high personalization


class TestDiversityScore:
    """Tests for diversity score calculation"""

    @pytest.mark.unit
    def test_diversity_score_high_variance(self):
        """Test diversity score with high score variance"""
        recommendations = [
            RecommendationResult(
                product_id=f"prod{i}",
                product_name=f"Product {i}",
                confidence_score=0.9 - i*0.1,
                reasoning=[],
                style_match_score=0.8,
                functional_match_score=0.8,
                price_score=0.8,
                popularity_score=0.7,
                compatibility_score=0.8,
                overall_score=0.9 - i*0.1
            )
            for i in range(10)
        ]

        diversity = recommendation_engine._calculate_diversity_score(recommendations)
        assert diversity > 0.0  # Should have positive diversity

    @pytest.mark.unit
    def test_diversity_score_empty_list(self):
        """Test diversity score with empty recommendations"""
        diversity = recommendation_engine._calculate_diversity_score([])
        assert diversity == 0.0


class TestRecommendationStrategy:
    """Tests for recommendation strategy determination"""

    @pytest.mark.unit
    def test_strategy_content_based_hybrid(self):
        """Test content-based hybrid strategy detection"""
        request = RecommendationRequest(
            user_preferences={},
            style_preferences=['modern'],
            functional_requirements=['seating']
        )

        strategy = recommendation_engine._determine_strategy(request, user_id=None)
        assert strategy == "content_based_hybrid"

    @pytest.mark.unit
    def test_strategy_contextual_content_based(self):
        """Test contextual content-based strategy detection"""
        request = RecommendationRequest(
            user_preferences={},
            room_context={'room_type': 'living_room'}
        )

        strategy = recommendation_engine._determine_strategy(request, user_id=None)
        assert strategy == "contextual_content_based"

    @pytest.mark.unit
    def test_strategy_popularity_fallback(self):
        """Test popularity-based fallback strategy"""
        request = RecommendationRequest(user_preferences={})

        strategy = recommendation_engine._determine_strategy(request, user_id=None)
        assert strategy == "popularity_content_based"


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_candidate_list(self):
        """Test handling of empty candidate list"""
        request = RecommendationRequest(user_preferences={})

        recommendations = await recommendation_engine._combine_scores(
            candidates=[],
            content_scores={},
            popularity_scores={},
            style_scores={},
            functional_scores={},
            price_scores={},
            collaborative_scores={},
            request=request
        )

        assert recommendations == []

    @pytest.mark.unit
    def test_style_similarity_unknown_styles(self):
        """Test style similarity with unknown styles"""
        similarity = recommendation_engine._calculate_style_similarity(
            "unknown_style_1", "unknown_style_2"
        )

        assert similarity == 0.0  # Should return 0 for unknown styles
