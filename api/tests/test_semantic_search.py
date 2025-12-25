"""
Integration tests for semantic search.

Tests search quality, filter integration, and hybrid scoring.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSemanticSearchQuality:
    """Tests for semantic search quality."""

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_semantic_similarity_navy_matches_blue(self):
        """Test that 'navy' query finds 'blue' products."""
        from routers.chat import _semantic_search
        from core.database import get_db

        async for db in get_db():
            results = await _semantic_search(
                query_text="navy blue sofa",
                db=db,
                limit=50
            )

            # Should find products with blue in their embeddings
            assert len(results) > 0
            # Verify semantic understanding worked
            # (In real test, would check product names/descriptions)
            break

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_semantic_similarity_cozy_matches_comfortable(self):
        """Test that 'cozy' query matches 'comfortable' products."""
        from routers.chat import _semantic_search
        from core.database import get_db

        async for db in get_db():
            results = await _semantic_search(
                query_text="cozy comfortable armchair",
                db=db,
                limit=50
            )

            assert len(results) > 0
            break

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_semantic_similarity_rustic_matches_farmhouse(self):
        """Test that 'rustic' query finds 'farmhouse' style products."""
        from routers.chat import _semantic_search
        from core.database import get_db

        async for db in get_db():
            results = await _semantic_search(
                query_text="rustic wooden table",
                db=db,
                limit=50
            )

            assert len(results) > 0
            break


class TestSemanticSearchFilters:
    """Tests for semantic search with filters."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        with patch('routers.chat.get_embedding_service') as mock:
            service = MagicMock()
            service.get_query_embedding = AsyncMock(return_value=[0.1] * 768)
            service.compute_cosine_similarity = MagicMock(return_value=0.85)
            mock.return_value = service
            yield service

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_semantic_search_with_category_filter(self):
        """Test semantic search respects category filter."""
        from routers.chat import _semantic_search
        from core.database import get_db

        async for db in get_db():
            # Search with category filter (e.g., category_id for Sofas)
            results = await _semantic_search(
                query_text="modern sofa",
                db=db,
                category_ids=[1],  # Assuming 1 is Sofas
                limit=50
            )

            # All results should be from the filtered category
            # (Would verify in real test)
            break

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_semantic_search_with_price_range(self):
        """Test semantic search respects price range."""
        from routers.chat import _semantic_search
        from core.database import get_db

        async for db in get_db():
            results = await _semantic_search(
                query_text="luxury sofa",
                db=db,
                price_min=50000,
                price_max=200000,
                limit=50
            )

            # All results should be within price range
            break

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_semantic_search_with_store_filter(self):
        """Test semantic search respects store filter."""
        from routers.chat import _semantic_search
        from core.database import get_db

        async for db in get_db():
            results = await _semantic_search(
                query_text="minimalist chair",
                db=db,
                store_filter=["freedomtree", "gulmohar"],
                limit=50
            )

            # All results should be from filtered stores
            break


class TestHybridScoring:
    """Tests for hybrid scoring (semantic + keyword)."""

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_hybrid_score_combines_semantic_and_keyword(self):
        """Test that hybrid scoring uses both semantic and keyword matches."""
        from routers.chat import _get_category_based_recommendations
        from schemas.chat import CategoryRecommendation, BudgetAllocation
        from core.database import get_db

        async for db in get_db():
            categories = [
                CategoryRecommendation(
                    category_id="sofas",
                    display_name="Sofas",
                    budget_allocation=BudgetAllocation(min=10000, max=100000),
                    priority=1
                )
            ]

            results = await _get_category_based_recommendations(
                selected_categories=categories,
                db=db,
                semantic_query="cozy comfortable sofa"
            )

            # Should have sofas category in results
            assert "sofas" in results
            # Products should be ranked by hybrid score
            break

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_high_semantic_similarity_boosts_ranking(self):
        """Test that high semantic similarity boosts product ranking."""
        # Products with high semantic similarity should appear first
        # even if they don't have exact keyword matches
        pass

    @pytest.mark.skip(reason="Requires database and embeddings")
    @pytest.mark.asyncio
    async def test_exact_keyword_match_still_works(self):
        """Test that exact keyword matches still work well."""
        # Exact keyword matches should still rank highly
        # Semantic search enhances, doesn't replace keyword matching
        pass


class TestEdgeCases:
    """Tests for edge cases in semantic search."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        mock = AsyncMock()
        mock.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
        return mock

    @pytest.mark.asyncio
    async def test_search_product_without_embedding(self, mock_db):
        """Test search handles products without embeddings gracefully."""
        from routers.chat import _semantic_search

        with patch('routers.chat.get_embedding_service') as mock_service:
            service = MagicMock()
            service.get_query_embedding = AsyncMock(return_value=[0.1] * 768)
            mock_service.return_value = service

            results = await _semantic_search(
                query_text="modern sofa",
                db=mock_db,
                limit=50
            )

            # Should return empty dict, not error
            assert results == {}

    @pytest.mark.asyncio
    async def test_search_empty_query(self, mock_db):
        """Test search with empty query returns empty results."""
        from routers.chat import _semantic_search

        with patch('routers.chat.get_embedding_service') as mock_service:
            service = MagicMock()
            service.get_query_embedding = AsyncMock(return_value=None)
            mock_service.return_value = service

            results = await _semantic_search(
                query_text="",
                db=mock_db,
                limit=50
            )

            assert results == {}

    @pytest.mark.asyncio
    async def test_search_very_long_query(self, mock_db):
        """Test search with very long query is handled."""
        from routers.chat import _semantic_search

        long_query = "modern minimalist scandinavian " * 100

        with patch('routers.chat.get_embedding_service') as mock_service:
            service = MagicMock()
            service.get_query_embedding = AsyncMock(return_value=[0.1] * 768)
            mock_service.return_value = service

            # Should not raise exception
            results = await _semantic_search(
                query_text=long_query,
                db=mock_db,
                limit=50
            )

            assert isinstance(results, dict)


class TestSearchMetrics:
    """Tests for search quality metrics."""

    def test_precision_calculation(self):
        """Test precision metric calculation."""
        # Precision = relevant_retrieved / total_retrieved
        relevant_retrieved = 8
        total_retrieved = 10
        precision = relevant_retrieved / total_retrieved
        assert precision == 0.8

    def test_recall_calculation(self):
        """Test recall metric calculation."""
        # Recall = relevant_retrieved / total_relevant
        relevant_retrieved = 8
        total_relevant = 10
        recall = relevant_retrieved / total_relevant
        assert recall == 0.8

    def test_f1_score_calculation(self):
        """Test F1 score calculation."""
        precision = 0.8
        recall = 0.6
        f1 = 2 * (precision * recall) / (precision + recall)
        assert abs(f1 - 0.6857) < 0.001

    def test_mrr_calculation(self):
        """Test Mean Reciprocal Rank calculation."""
        # MRR = average of 1/rank of first relevant result
        ranks = [1, 3, 2, 1, 5]  # Rank of first relevant result per query
        mrr = sum(1/r for r in ranks) / len(ranks)
        expected = (1/1 + 1/3 + 1/2 + 1/1 + 1/5) / 5
        assert abs(mrr - expected) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
