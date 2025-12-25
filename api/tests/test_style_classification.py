"""
Unit tests for style classification.

Tests the classify_product_style method and fallback text classification.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.style_definitions import (
    PREDEFINED_STYLES,
    STYLE_DESCRIPTIONS,
    get_style_similarity,
    is_valid_style,
    normalize_style,
)


class TestStyleDefinitions:
    """Test cases for style definitions and utilities."""

    def test_predefined_styles_count(self):
        """Test we have exactly 11 predefined styles."""
        assert len(PREDEFINED_STYLES) == 11

    def test_all_styles_have_descriptions(self):
        """Test all predefined styles have descriptions."""
        for style in PREDEFINED_STYLES:
            assert style in STYLE_DESCRIPTIONS
            assert len(STYLE_DESCRIPTIONS[style]) > 10

    def test_is_valid_style(self):
        """Test style validation."""
        assert is_valid_style("modern") is True
        assert is_valid_style("minimalist") is True
        assert is_valid_style("indian_contemporary") is True
        assert is_valid_style("invalid_style") is False
        assert is_valid_style("") is False

    def test_normalize_style_direct_match(self):
        """Test normalization with direct matches."""
        assert normalize_style("modern") == "modern"
        assert normalize_style("MODERN") == "modern"
        assert normalize_style("  modern  ") == "modern"

    def test_normalize_style_aliases(self):
        """Test normalization with common aliases."""
        assert normalize_style("minimal") == "minimalist"
        assert normalize_style("scandi") == "scandinavian"
        assert normalize_style("nordic") == "scandinavian"
        assert normalize_style("mcm") == "mid_century_modern"
        assert normalize_style("midcentury") == "mid_century_modern"
        assert normalize_style("bohemian") == "boho"
        assert normalize_style("japanese") == "japandi"
        assert normalize_style("zen") == "japandi"
        assert normalize_style("loft") == "industrial"

    def test_normalize_style_with_hyphens_and_spaces(self):
        """Test normalization handles different formats."""
        assert normalize_style("mid-century-modern") == "mid_century_modern"
        assert normalize_style("mid century modern") == "mid_century_modern"
        assert normalize_style("indian-contemporary") == "indian_contemporary"

    def test_get_style_similarity_same_style(self):
        """Test same style returns 1.0."""
        assert get_style_similarity("modern", "modern") == 1.0
        assert get_style_similarity("boho", "boho") == 1.0

    def test_get_style_similarity_related_styles(self):
        """Test related styles have high similarity."""
        # Japandi and Scandinavian are very related
        assert get_style_similarity("japandi", "scandinavian") >= 0.8

        # Modern and minimalist are related
        assert get_style_similarity("modern", "minimalist") >= 0.7

        # Contemporary and modern are related
        assert get_style_similarity("contemporary", "modern") >= 0.8

    def test_get_style_similarity_unrelated_styles(self):
        """Test unrelated styles have low similarity."""
        # Boho and minimalist are quite different
        sim = get_style_similarity("boho", "minimalist")
        assert sim < 0.5

    def test_get_style_similarity_symmetric(self):
        """Test similarity is symmetric (A->B == B->A)."""
        assert get_style_similarity("modern", "scandinavian") == get_style_similarity("scandinavian", "modern")
        assert get_style_similarity("boho", "eclectic") == get_style_similarity("eclectic", "boho")


class TestStyleClassification:
    """Test cases for style classification via Google AI service."""

    @pytest.fixture
    def mock_google_ai_service(self):
        """Create mock Google AI service."""
        with patch('services.google_ai_service.GoogleAIStudioService') as MockService:
            mock = MockService.return_value
            mock._download_image = AsyncMock(return_value="base64encodeddata")
            mock._make_api_request = AsyncMock()
            return mock

    def test_fallback_style_classification_modern(self):
        """Test text-based fallback classification for modern style."""
        from services.google_ai_service import GoogleAIStudioService

        service = GoogleAIStudioService()
        result = service._fallback_style_classification(
            "Modern Sleek Sofa",
            "A clean-lined modern sofa with streamlined design"
        )

        assert result["primary_style"] == "modern"
        assert result["confidence"] > 0

    def test_fallback_style_classification_boho(self):
        """Test text-based fallback for bohemian style."""
        from services.google_ai_service import GoogleAIStudioService

        service = GoogleAIStudioService()
        result = service._fallback_style_classification(
            "Boho Rattan Chair",
            "Bohemian wicker chair with macrame details and jute accents"
        )

        assert result["primary_style"] == "boho"
        assert result["confidence"] > 0

    def test_fallback_style_classification_industrial(self):
        """Test text-based fallback for industrial style."""
        from services.google_ai_service import GoogleAIStudioService

        service = GoogleAIStudioService()
        result = service._fallback_style_classification(
            "Industrial Metal Shelf",
            "Iron pipe shelving unit with raw metal finish, loft warehouse style"
        )

        assert result["primary_style"] == "industrial"
        assert result["confidence"] > 0

    def test_fallback_style_classification_scandinavian(self):
        """Test text-based fallback for Scandinavian style."""
        from services.google_ai_service import GoogleAIStudioService

        service = GoogleAIStudioService()
        result = service._fallback_style_classification(
            "Nordic Oak Dining Table",
            "Scandinavian design with Danish craftsmanship, hygge inspired"
        )

        assert result["primary_style"] == "scandinavian"
        assert result["confidence"] > 0

    def test_fallback_style_classification_indian_contemporary(self):
        """Test text-based fallback for Indian contemporary style."""
        from services.google_ai_service import GoogleAIStudioService

        service = GoogleAIStudioService()
        result = service._fallback_style_classification(
            "Carved Indian Console",
            "Traditional Indian brass work with ethnic motifs, jharokha design"
        )

        assert result["primary_style"] == "indian_contemporary"
        assert result["confidence"] > 0

    def test_fallback_style_classification_no_match(self):
        """Test fallback returns modern as default."""
        from services.google_ai_service import GoogleAIStudioService

        service = GoogleAIStudioService()
        result = service._fallback_style_classification(
            "Generic Chair",
            "A chair for sitting"
        )

        # Default should be modern
        assert result["primary_style"] == "modern"
        assert result["confidence"] == 0.2  # Low confidence for default


class TestStyleClassificationIntegration:
    """Integration tests for style classification (require API)."""

    @pytest.mark.skip(reason="Requires API key and image")
    @pytest.mark.asyncio
    async def test_classify_product_style_with_image(self):
        """Test classification with actual product image."""
        from services.google_ai_service import google_ai_service

        result = await google_ai_service.classify_product_style(
            image_url="https://example.com/modern-sofa.jpg",
            product_name="Modern Gray Sofa",
            product_description="A sleek modern sofa with clean lines"
        )

        assert result["primary_style"] in PREDEFINED_STYLES
        assert 0 <= result["confidence"] <= 1
        assert "reasoning" in result

    @pytest.mark.skip(reason="Requires API key")
    @pytest.mark.asyncio
    async def test_classify_product_style_without_image(self):
        """Test classification falls back to text when no image."""
        from services.google_ai_service import google_ai_service

        result = await google_ai_service.classify_product_style(
            image_url="",
            product_name="Scandinavian Oak Chair",
            product_description="Light wood Danish inspired chair with hygge comfort"
        )

        assert result["primary_style"] in PREDEFINED_STYLES
        # Should have lower confidence without image
        assert result["confidence"] < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
