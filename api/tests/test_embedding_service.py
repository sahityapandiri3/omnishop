"""
Unit tests for the embedding service.

Tests embedding generation, caching, and cosine similarity computation.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.embedding_service import EmbeddingService, get_embedding_service


class TestEmbeddingService:
    """Test cases for EmbeddingService."""

    @pytest.fixture
    def embedding_service(self):
        """Create embedding service instance."""
        with patch.object(EmbeddingService, '_initialize_client'):
            service = EmbeddingService()
            service.client = MagicMock()
            return service

    def test_embedding_service_singleton(self):
        """Test that get_embedding_service returns singleton."""
        service1 = get_embedding_service()
        service2 = get_embedding_service()
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_768_dimensions(self, embedding_service):
        """Test embedding has correct dimensionality."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.embeddings = [MagicMock(values=[0.1] * 768)]
        embedding_service.client.models.embed_content.return_value = mock_response

        result = await embedding_service.generate_embedding("test text")

        assert result is not None
        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text_returns_none(self, embedding_service):
        """Test empty text returns None."""
        result = await embedding_service.generate_embedding("")
        assert result is None

        result = await embedding_service.generate_embedding("   ")
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_embedding_no_client_returns_none(self):
        """Test returns None when client not initialized."""
        with patch.object(EmbeddingService, '_initialize_client'):
            service = EmbeddingService()
            service.client = None

            result = await service.generate_embedding("test")
            assert result is None

    def test_build_product_embedding_text(self, embedding_service):
        """Test embedding text construction from product."""
        # Create mock product
        product = MagicMock()
        product.name = "Modern Gray Sofa"
        product.description = "A comfortable modern sofa in gray fabric"
        product.brand = "TestBrand"
        product.primary_style = "modern"
        product.secondary_style = "minimalist"

        result = embedding_service.build_product_embedding_text(
            product,
            category_name="Sofas",
            attributes={
                "color_primary": "gray",
                "material_primary": "fabric"
            }
        )

        assert "Modern Gray Sofa" in result
        assert "comfortable modern sofa" in result
        assert "Category: Sofas" in result
        assert "Style: modern, minimalist" in result
        assert "Color: gray" in result
        assert "Material: fabric" in result
        assert "Brand: TestBrand" in result

    def test_build_product_embedding_text_minimal(self, embedding_service):
        """Test embedding text with minimal product data."""
        product = MagicMock()
        product.name = "Simple Chair"
        product.description = None
        product.brand = None
        product.primary_style = None
        product.secondary_style = None

        result = embedding_service.build_product_embedding_text(product)

        assert "Simple Chair" in result
        assert "Category" not in result
        assert "Style" not in result

    @pytest.mark.asyncio
    async def test_query_embedding_caching(self, embedding_service):
        """Test query embedding is cached."""
        mock_response = MagicMock()
        mock_response.embeddings = [MagicMock(values=[0.1] * 768)]
        embedding_service.client.models.embed_content.return_value = mock_response

        # First call - should generate embedding
        result1 = await embedding_service.get_query_embedding("modern sofa")
        assert result1 is not None

        # Second call with same query - should use cache
        result2 = await embedding_service.get_query_embedding("modern sofa")
        assert result2 is not None
        assert result1 == result2

        # Should only call API once (cached second time)
        assert embedding_service.client.models.embed_content.call_count == 1

    @pytest.mark.asyncio
    async def test_query_embedding_cache_normalization(self, embedding_service):
        """Test query normalization for cache key."""
        mock_response = MagicMock()
        mock_response.embeddings = [MagicMock(values=[0.1] * 768)]
        embedding_service.client.models.embed_content.return_value = mock_response

        # Different cases should hit same cache key
        await embedding_service.get_query_embedding("Modern Sofa")
        await embedding_service.get_query_embedding("modern sofa")
        await embedding_service.get_query_embedding("  MODERN SOFA  ")

        # Should only call API once due to normalization
        assert embedding_service.client.models.embed_content.call_count == 1

    def test_compute_cosine_similarity(self, embedding_service):
        """Test cosine similarity computation."""
        # Identical vectors = 1.0
        vec1 = [1.0, 0.0, 0.0]
        result = embedding_service.compute_cosine_similarity(vec1, vec1)
        assert abs(result - 1.0) < 0.0001

        # Orthogonal vectors = 0.0
        vec2 = [0.0, 1.0, 0.0]
        result = embedding_service.compute_cosine_similarity(vec1, vec2)
        assert abs(result - 0.0) < 0.0001

        # Opposite vectors = -1.0
        vec3 = [-1.0, 0.0, 0.0]
        result = embedding_service.compute_cosine_similarity(vec1, vec3)
        assert abs(result - (-1.0)) < 0.0001

    def test_compute_cosine_similarity_zero_vector(self, embedding_service):
        """Test cosine similarity with zero vector returns 0."""
        vec1 = [1.0, 2.0, 3.0]
        vec_zero = [0.0, 0.0, 0.0]

        result = embedding_service.compute_cosine_similarity(vec1, vec_zero)
        assert result == 0.0

    def test_compute_cosine_similarity_dimension_mismatch(self, embedding_service):
        """Test dimension mismatch raises error."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0]

        with pytest.raises(ValueError, match="same dimension"):
            embedding_service.compute_cosine_similarity(vec1, vec2)

    def test_prune_cache(self, embedding_service):
        """Test cache pruning removes oldest entries."""
        import time

        # Manually fill cache beyond max size
        embedding_service.MAX_CACHE_SIZE = 10

        for i in range(15):
            embedding_service._query_cache[f"key_{i}"] = {
                'embedding': [0.1] * 768,
                'timestamp': time.time() - (15 - i)  # Older entries first
            }

        embedding_service._prune_cache()

        # Should have pruned oldest 20% (3 entries)
        assert len(embedding_service._query_cache) == 12

        # Oldest entries should be removed
        assert "key_0" not in embedding_service._query_cache
        assert "key_1" not in embedding_service._query_cache
        assert "key_2" not in embedding_service._query_cache


class TestEmbeddingIntegration:
    """Integration tests requiring actual API (marked for skip in CI)."""

    @pytest.mark.skip(reason="Requires API key")
    @pytest.mark.asyncio
    async def test_real_embedding_generation(self):
        """Test actual embedding generation with Google API."""
        service = get_embedding_service()

        result = await service.generate_embedding(
            "A modern minimalist sofa in gray fabric"
        )

        assert result is not None
        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.skip(reason="Requires API key")
    @pytest.mark.asyncio
    async def test_semantic_similarity_cozy_comfortable(self):
        """Test that 'cozy' and 'comfortable' have high similarity."""
        service = get_embedding_service()

        emb_cozy = await service.generate_embedding("cozy")
        emb_comfortable = await service.generate_embedding("comfortable")

        similarity = service.compute_cosine_similarity(emb_cozy, emb_comfortable)

        # These should be semantically similar
        assert similarity > 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
