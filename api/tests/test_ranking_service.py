"""
Automated tests for the RankingService search and scoring logic.

Test cases cover:
1. Search by category
2. Search by color
3. Search by type
4. Search by material
5. Search by style
6. Combined preferences
7. Edge cases (missing data, no preferences)

Run with: pytest tests/test_ranking_service.py -v
"""
import pytest
from dataclasses import dataclass
from typing import Optional, List
from services.ranking_service import RankingService, RankedProduct


@dataclass
class MockProduct:
    """Mock product for testing."""
    id: int
    name: str
    category_id: int
    primary_style: Optional[str] = None
    secondary_style: Optional[str] = None
    material_primary: Optional[str] = None
    color_primary: Optional[str] = None
    type: Optional[str] = None
    capacity: Optional[int] = None
    embedding: Optional[str] = None


class TestRankingService:
    """Test suite for RankingService."""

    @pytest.fixture
    def ranking_service(self):
        """Create a RankingService instance."""
        return RankingService()

    @pytest.fixture
    def sample_sofas(self):
        """Create sample sofa products for testing."""
        return [
            MockProduct(
                id=1,
                name="Modern Oak 3-Seater Sofa",
                category_id=10,
                primary_style="modern",
                secondary_style="minimalist",
                material_primary="oak",
                color_primary="brown",
                type="3-seater",
                capacity=3,
            ),
            MockProduct(
                id=2,
                name="Boho Velvet Sectional",
                category_id=10,
                primary_style="boho",
                secondary_style="eclectic",
                material_primary="velvet",
                color_primary="teal",
                type="sectional",
                capacity=5,
            ),
            MockProduct(
                id=3,
                name="Minimalist Leather 2-Seater",
                category_id=10,
                primary_style="minimalist",
                secondary_style="modern",
                material_primary="leather",
                color_primary="black",
                type="2-seater",
                capacity=2,
            ),
            MockProduct(
                id=4,
                name="Scandinavian Fabric Sofa",
                category_id=10,
                primary_style="scandinavian",
                secondary_style="minimalist",
                material_primary="linen",
                color_primary="beige",
                type="3-seater",
                capacity=3,
            ),
            MockProduct(
                id=5,
                name="Industrial Metal Frame Couch",
                category_id=10,
                primary_style="industrial",
                secondary_style="modern",
                material_primary="steel",
                color_primary="grey",
                type="3-seater",
                capacity=3,
            ),
        ]

    @pytest.fixture
    def sample_tables(self):
        """Create sample table products for testing."""
        return [
            MockProduct(
                id=101,
                name="Round Marble Dining Table",
                category_id=20,
                primary_style="modern",
                secondary_style="luxury",
                material_primary="marble",
                color_primary="white",
                type="round",
            ),
            MockProduct(
                id=102,
                name="Rectangular Wooden Dining Table",
                category_id=20,
                primary_style="scandinavian",
                secondary_style="minimalist",
                material_primary="walnut",
                color_primary="brown",
                type="rectangular",
            ),
            MockProduct(
                id=103,
                name="Industrial Coffee Table",
                category_id=21,  # Different category (coffee tables)
                primary_style="industrial",
                secondary_style="rustic",
                material_primary="iron",
                color_primary="black",
                type="rectangular",
            ),
        ]

    # =========================================================================
    # TEST CATEGORY MATCHING
    # =========================================================================

    class TestCategoryMatching:
        """Tests for category-based ranking."""

        def test_category_match_boosts_score(self, ranking_service, sample_sofas):
            """Products matching user's category should score higher."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_category=10,  # Sofas category
            )

            # All products match category, so attribute_match should be 1.0
            for rp in ranked:
                assert rp.breakdown["attribute_match"] == 1.0

        def test_category_no_match_is_neutral(self, ranking_service, sample_sofas):
            """Products not matching category should get neutral score (0.5)."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_category=99,  # Non-matching category
            )

            # No products match, so attribute_match should be 0.5 (neutral)
            for rp in ranked:
                assert rp.breakdown["attribute_match"] == 0.5

        def test_mixed_category_ranking(self, ranking_service, sample_tables):
            """Products from matching category should rank higher than non-matching."""
            vector_scores = {p.id: 0.5 for p in sample_tables}

            ranked = ranking_service.rank_products(
                products=sample_tables,
                vector_scores=vector_scores,
                user_category=20,  # Dining tables category
            )

            # Products 101 and 102 should rank higher than 103
            product_ids = [rp.product.id for rp in ranked]
            assert product_ids.index(101) < product_ids.index(103)
            assert product_ids.index(102) < product_ids.index(103)

    # =========================================================================
    # TEST COLOR MATCHING
    # =========================================================================

    class TestColorMatching:
        """Tests for color-based ranking."""

        def test_exact_color_match_boosts_score(self, ranking_service, sample_sofas):
            """Products with exact color match should get highest color score."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_color="brown",
            )

            # Product 1 (brown) should rank highest for color preference
            brown_product = next(rp for rp in ranked if rp.product.id == 1)
            other_products = [rp for rp in ranked if rp.product.id != 1]

            # Brown product should have higher material_color score
            for other in other_products:
                assert brown_product.breakdown["material_color"] >= other.breakdown["material_color"]

        def test_color_family_match(self, ranking_service, sample_sofas):
            """Products in same color family should get partial boost."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            # User wants "chocolate" which is in brown family
            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_color="chocolate",
            )

            # Product 1 (brown) should get partial boost (same family as chocolate)
            brown_product = next(rp for rp in ranked if rp.product.id == 1)
            assert brown_product.breakdown["material_color"] > 0.5  # Should be boosted

        def test_neutral_colors_grouped(self, ranking_service, sample_sofas):
            """Neutral colors (black, grey, beige) should match each other."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            # User wants "grey", products with black/beige should also get boost
            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_color="grey",
            )

            # Product 3 (black) and 4 (beige) are in neutral family with grey
            black_product = next(rp for rp in ranked if rp.product.id == 3)
            beige_product = next(rp for rp in ranked if rp.product.id == 4)
            grey_product = next(rp for rp in ranked if rp.product.id == 5)

            # Grey (exact), black and beige (same family) should all be boosted
            assert grey_product.breakdown["material_color"] > 0.5
            assert black_product.breakdown["material_color"] > 0.5
            assert beige_product.breakdown["material_color"] > 0.5

        def test_no_color_preference_is_neutral(self, ranking_service, sample_sofas):
            """Without color preference, all products should have neutral score."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_color=None,
            )

            for rp in ranked:
                assert rp.breakdown["material_color"] == 0.5

    # =========================================================================
    # TEST TYPE MATCHING
    # =========================================================================

    class TestTypeMatching:
        """Tests for type-based ranking."""

        def test_exact_type_match_boosts_score(self, ranking_service, sample_sofas):
            """Products with exact type match should get highest attribute score."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_category=10,
                user_type="3-seater",
            )

            # Products 1, 4, 5 are 3-seaters and should rank higher
            three_seater_ids = [1, 4, 5]
            for rp in ranked[:3]:
                assert rp.product.id in three_seater_ids

        def test_adjacent_type_partial_boost(self, ranking_service, sample_sofas):
            """Adjacent types (e.g., 2-seater vs 3-seater) should get partial boost."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_category=10,
                user_type="2-seater",
            )

            # Product 3 is exact match (2-seater)
            two_seater = next(rp for rp in ranked if rp.product.id == 3)

            # Products 1, 4, 5 are 3-seaters (adjacent to 2-seater)
            three_seaters = [rp for rp in ranked if rp.product.id in [1, 4, 5]]

            # Exact match should have higher attribute score than adjacent
            for ts in three_seaters:
                assert two_seater.breakdown["attribute_match"] > ts.breakdown["attribute_match"]

        def test_sectional_l_shaped_adjacent(self, ranking_service, sample_sofas):
            """Sectional and L-shaped should be considered adjacent types."""
            # Add an L-shaped sofa
            products = sample_sofas + [
                MockProduct(
                    id=6,
                    name="L-Shaped Corner Sofa",
                    category_id=10,
                    primary_style="modern",
                    type="l-shaped",
                )
            ]
            vector_scores = {p.id: 0.5 for p in products}

            ranked = ranking_service.rank_products(
                products=products,
                vector_scores=vector_scores,
                user_category=10,
                user_type="sectional",
            )

            # Product 2 (sectional) should be exact match
            sectional = next(rp for rp in ranked if rp.product.id == 2)
            # Product 6 (l-shaped) should get partial boost as adjacent
            l_shaped = next(rp for rp in ranked if rp.product.id == 6)

            assert sectional.breakdown["attribute_match"] > l_shaped.breakdown["attribute_match"]
            assert l_shaped.breakdown["attribute_match"] > 0.5  # Should still be boosted

    # =========================================================================
    # TEST MATERIAL MATCHING
    # =========================================================================

    class TestMaterialMatching:
        """Tests for material-based ranking."""

        def test_exact_material_match(self, ranking_service, sample_sofas):
            """Exact material match should get highest score."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_materials=["leather"],
            )

            # Product 3 (leather) should have highest material_color score
            leather_product = next(rp for rp in ranked if rp.product.id == 3)
            # 0.6 * 1.0 (exact material match) + 0.4 * 0.5 (no color pref = neutral) = 0.8
            assert leather_product.breakdown["material_color"] == pytest.approx(0.8, abs=0.05)

        def test_material_family_match(self, ranking_service, sample_sofas):
            """User wants 'wood', product has 'oak' (wood family) should boost."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_materials=["wood"],
            )

            # Product 1 (oak) is in wood family, should be boosted
            oak_product = next(rp for rp in ranked if rp.product.id == 1)
            assert oak_product.breakdown["material_color"] > 0.5

        def test_fabric_family_includes_velvet_linen(self, ranking_service, sample_sofas):
            """Fabric family should include velvet and linen."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_materials=["fabric"],
            )

            # Product 2 (velvet) and 4 (linen) are in fabric family
            velvet_product = next(rp for rp in ranked if rp.product.id == 2)
            linen_product = next(rp for rp in ranked if rp.product.id == 4)

            assert velvet_product.breakdown["material_color"] > 0.5
            assert linen_product.breakdown["material_color"] > 0.5

        def test_metal_family_includes_steel(self, ranking_service, sample_sofas):
            """Metal family should include steel."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_materials=["metal"],
            )

            # Product 5 (steel) is in metal family
            steel_product = next(rp for rp in ranked if rp.product.id == 5)
            assert steel_product.breakdown["material_color"] > 0.5

        def test_multiple_material_preferences(self, ranking_service, sample_sofas):
            """Multiple material preferences should all boost matching products."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_materials=["wood", "leather"],
            )

            # Both oak (wood family) and leather should be boosted
            oak_product = next(rp for rp in ranked if rp.product.id == 1)
            leather_product = next(rp for rp in ranked if rp.product.id == 3)

            assert oak_product.breakdown["material_color"] > 0.5
            assert leather_product.breakdown["material_color"] > 0.5

    # =========================================================================
    # TEST STYLE MATCHING
    # =========================================================================

    class TestStyleMatching:
        """Tests for style-based ranking."""

        def test_primary_style_exact_match(self, ranking_service, sample_sofas):
            """Product with primary_style matching user preference should get full boost."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_primary_style="modern",
            )

            # Product 1 has primary_style="modern"
            modern_product = next(rp for rp in ranked if rp.product.id == 1)
            assert modern_product.breakdown["style"] > 0.5  # Should be boosted

        def test_secondary_style_match(self, ranking_service, sample_sofas):
            """Product with secondary_style matching should get partial boost."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_primary_style="minimalist",
            )

            # Product 3 has primary_style="minimalist" (full boost)
            # Products 1 and 4 have secondary_style="minimalist" (partial boost)
            minimalist_primary = next(rp for rp in ranked if rp.product.id == 3)
            minimalist_secondary_1 = next(rp for rp in ranked if rp.product.id == 1)
            minimalist_secondary_4 = next(rp for rp in ranked if rp.product.id == 4)

            # Primary match should have higher style score than secondary match
            assert minimalist_primary.breakdown["style"] > minimalist_secondary_1.breakdown["style"]
            assert minimalist_primary.breakdown["style"] > minimalist_secondary_4.breakdown["style"]

            # Secondary match should still be boosted above neutral
            assert minimalist_secondary_1.breakdown["style"] > 0.5
            assert minimalist_secondary_4.breakdown["style"] > 0.5

        def test_user_secondary_style_preference(self, ranking_service, sample_sofas):
            """User's secondary style preference should also boost matching products."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_primary_style="boho",
                user_secondary_style="modern",
            )

            # Product 2 matches primary (boho)
            # Product 1 matches secondary (modern)
            boho_product = next(rp for rp in ranked if rp.product.id == 2)
            modern_product = next(rp for rp in ranked if rp.product.id == 1)

            # Both should be boosted, but boho (primary match) should be higher
            assert boho_product.breakdown["style"] > modern_product.breakdown["style"]
            assert modern_product.breakdown["style"] > 0.5

        def test_no_style_preference_is_neutral(self, ranking_service, sample_sofas):
            """Without style preference, all products should have neutral style score."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_primary_style=None,
            )

            for rp in ranked:
                assert rp.breakdown["style"] == 0.5

        def test_no_style_match_is_neutral(self, ranking_service, sample_sofas):
            """Products not matching user's style should get neutral score (not penalty)."""
            vector_scores = {p.id: 0.5 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_primary_style="art_deco",  # No products have this style
            )

            # All products should have neutral style score (0.5)
            for rp in ranked:
                assert rp.breakdown["style"] == 0.5

    # =========================================================================
    # TEST COMBINED PREFERENCES
    # =========================================================================

    class TestCombinedPreferences:
        """Tests for combined search preferences."""

        def test_modern_brown_wood_3seater(self, ranking_service, sample_sofas):
            """User wants: modern style, brown color, wood material, 3-seater."""
            vector_scores = {p.id: 0.7 for p in sample_sofas}  # Equal vector scores

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_category=10,
                user_type="3-seater",
                user_primary_style="modern",
                user_materials=["wood"],
                user_color="brown",
            )

            # Product 1 should rank first (matches all criteria)
            assert ranked[0].product.id == 1

            # Verify breakdown
            top_product = ranked[0]
            assert top_product.breakdown["attribute_match"] == 1.0  # Category + type match
            assert top_product.breakdown["style"] > 0.5  # Modern match
            assert top_product.breakdown["material_color"] > 0.5  # Wood + brown match

        def test_minimalist_neutral_fabric(self, ranking_service, sample_sofas):
            """User wants: minimalist style, neutral colors, fabric material."""
            vector_scores = {p.id: 0.6 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_primary_style="minimalist",
                user_materials=["fabric"],
                user_color="beige",
            )

            # Product 4 (scandinavian/minimalist, linen, beige) should rank high
            # Product 3 (minimalist, leather, black) should also rank high
            top_3_ids = [rp.product.id for rp in ranked[:3]]
            assert 4 in top_3_ids  # Best match for fabric + beige + minimalist secondary
            assert 3 in top_3_ids  # Best match for minimalist primary

        def test_vector_similarity_dominates(self, ranking_service, sample_sofas):
            """High vector similarity should significantly affect ranking."""
            # Give product 5 a much higher vector score
            vector_scores = {
                1: 0.3,
                2: 0.3,
                3: 0.3,
                4: 0.3,
                5: 0.95,  # Much higher vector score
            }

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_primary_style="modern",  # Product 1 matches, but low vector score
            )

            # Product 5 should rank first due to high vector similarity (50% weight)
            assert ranked[0].product.id == 5

    # =========================================================================
    # TEST EDGE CASES
    # =========================================================================

    class TestEdgeCases:
        """Tests for edge cases and missing data."""

        def test_missing_product_style(self, ranking_service):
            """Products without style should get neutral style score."""
            products = [
                MockProduct(id=1, name="No Style Product", category_id=10),
            ]
            vector_scores = {1: 0.5}

            ranked = ranking_service.rank_products(
                products=products,
                vector_scores=vector_scores,
                user_primary_style="modern",
            )

            assert ranked[0].breakdown["style"] == 0.5  # Neutral, not penalized

        def test_missing_product_material(self, ranking_service):
            """Products without material should get neutral material score."""
            products = [
                MockProduct(id=1, name="No Material Product", category_id=10),
            ]
            vector_scores = {1: 0.5}

            ranked = ranking_service.rank_products(
                products=products,
                vector_scores=vector_scores,
                user_materials=["wood"],
            )

            # material_color = 0.6 * 0.5 (no material) + 0.4 * 0.5 (no color) = 0.5
            assert ranked[0].breakdown["material_color"] == 0.5

        def test_missing_product_color(self, ranking_service):
            """Products without color should get neutral color score."""
            products = [
                MockProduct(id=1, name="No Color Product", category_id=10, material_primary="oak"),
            ]
            vector_scores = {1: 0.5}

            ranked = ranking_service.rank_products(
                products=products,
                vector_scores=vector_scores,
                user_color="brown",
            )

            # Color portion should be neutral (0.5)
            assert ranked[0].breakdown["material_color"] == pytest.approx(0.5, abs=0.1)

        def test_no_preferences_all_neutral(self, ranking_service, sample_sofas):
            """Without any preferences, all non-vector scores should be neutral."""
            vector_scores = {p.id: 0.6 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                # No preferences specified
            )

            for rp in ranked:
                assert rp.breakdown["attribute_match"] == 0.5
                assert rp.breakdown["style"] == 0.5
                assert rp.breakdown["material_color"] == 0.5
                assert rp.breakdown["text_intent"] == 0.5

        def test_empty_product_list(self, ranking_service):
            """Empty product list should return empty results."""
            ranked = ranking_service.rank_products(
                products=[],
                vector_scores={},
            )

            assert ranked == []

        def test_missing_vector_score(self, ranking_service):
            """Products missing from vector_scores should get 0.0 vector similarity."""
            products = [
                MockProduct(id=1, name="Product 1", category_id=10),
                MockProduct(id=2, name="Product 2", category_id=10),
            ]
            vector_scores = {1: 0.8}  # Product 2 missing

            ranked = ranking_service.rank_products(
                products=products,
                vector_scores=vector_scores,
            )

            product_1 = next(rp for rp in ranked if rp.product.id == 1)
            product_2 = next(rp for rp in ranked if rp.product.id == 2)

            assert product_1.breakdown["vector_similarity"] == 0.8
            assert product_2.breakdown["vector_similarity"] == 0.0

        def test_case_insensitive_matching(self, ranking_service):
            """Style, color, material matching should be case-insensitive."""
            products = [
                MockProduct(
                    id=1,
                    name="Test Product",
                    category_id=10,
                    primary_style="MODERN",  # Uppercase
                    material_primary="OAK",  # Uppercase
                    color_primary="BROWN",  # Uppercase
                ),
            ]
            vector_scores = {1: 0.5}

            ranked = ranking_service.rank_products(
                products=products,
                vector_scores=vector_scores,
                user_primary_style="modern",  # Lowercase
                user_materials=["wood"],  # Lowercase
                user_color="brown",  # Lowercase
            )

            # All should match despite case differences
            assert ranked[0].breakdown["style"] > 0.5
            assert ranked[0].breakdown["material_color"] > 0.5

    # =========================================================================
    # TEST SCORE RANGES
    # =========================================================================

    class TestScoreRanges:
        """Tests to verify scores are in valid ranges."""

        def test_all_scores_between_0_and_1(self, ranking_service, sample_sofas):
            """All component scores should be between 0 and 1."""
            vector_scores = {p.id: 0.7 for p in sample_sofas}

            ranked = ranking_service.rank_products(
                products=sample_sofas,
                vector_scores=vector_scores,
                user_category=10,
                user_type="3-seater",
                user_primary_style="modern",
                user_secondary_style="minimalist",
                user_materials=["wood", "fabric"],
                user_color="brown",
            )

            for rp in ranked:
                assert 0 <= rp.final_score <= 1
                for component, score in rp.breakdown.items():
                    assert 0 <= score <= 1, f"{component} score {score} out of range"

        def test_final_score_is_weighted_sum(self, ranking_service):
            """Final score should be weighted sum of components."""
            products = [
                MockProduct(id=1, name="Test", category_id=10, primary_style="modern"),
            ]
            vector_scores = {1: 0.8}

            ranked = ranking_service.rank_products(
                products=products,
                vector_scores=vector_scores,
                user_category=10,
                user_primary_style="modern",
            )

            rp = ranked[0]
            expected_score = (
                0.50 * rp.breakdown["vector_similarity"] +
                0.20 * rp.breakdown["attribute_match"] +
                0.15 * rp.breakdown["style"] +
                0.10 * rp.breakdown["material_color"] +
                0.05 * rp.breakdown["text_intent"]
            )

            assert rp.final_score == pytest.approx(expected_score, abs=0.001)


# =========================================================================
# INTEGRATION TESTS - Real-world Search Scenarios
# =========================================================================

class TestRealWorldScenarios:
    """Integration tests simulating real user searches."""

    @pytest.fixture
    def ranking_service(self):
        return RankingService()

    @pytest.fixture
    def furniture_catalog(self):
        """A more comprehensive furniture catalog for realistic testing."""
        return [
            # Sofas
            MockProduct(id=1, name="Milano Modern 3-Seater Sofa", category_id=10,
                       primary_style="modern", secondary_style="minimalist",
                       material_primary="leather", color_primary="black", type="3-seater"),
            MockProduct(id=2, name="Countryside Boho Sectional", category_id=10,
                       primary_style="boho", secondary_style="eclectic",
                       material_primary="cotton", color_primary="terracotta", type="sectional"),
            MockProduct(id=3, name="Nordic Scandinavian Loveseat", category_id=10,
                       primary_style="scandinavian", secondary_style="minimalist",
                       material_primary="linen", color_primary="grey", type="2-seater"),
            MockProduct(id=4, name="Tokyo Japandi Sofa", category_id=10,
                       primary_style="japandi", secondary_style="minimalist",
                       material_primary="oak", color_primary="beige", type="3-seater"),
            # Dining Tables
            MockProduct(id=10, name="Marble Top Dining Table", category_id=20,
                       primary_style="modern", secondary_style="luxury",
                       material_primary="marble", color_primary="white", type="rectangular"),
            MockProduct(id=11, name="Rustic Oak Farmhouse Table", category_id=20,
                       primary_style="rustic", secondary_style="traditional",
                       material_primary="oak", color_primary="brown", type="rectangular"),
            MockProduct(id=12, name="Industrial Metal Dining Table", category_id=20,
                       primary_style="industrial", secondary_style="modern",
                       material_primary="steel", color_primary="black", type="rectangular"),
            # Chairs
            MockProduct(id=20, name="Velvet Accent Chair", category_id=30,
                       primary_style="modern", secondary_style="luxury",
                       material_primary="velvet", color_primary="navy", type="accent"),
            MockProduct(id=21, name="Rattan Dining Chair", category_id=30,
                       primary_style="boho", secondary_style="coastal",
                       material_primary="rattan", color_primary="natural", type="dining"),
        ]

    def test_scenario_modern_living_room(self, ranking_service, furniture_catalog):
        """User searching for modern living room furniture."""
        sofas = [p for p in furniture_catalog if p.category_id == 10]
        vector_scores = {p.id: 0.6 for p in sofas}
        vector_scores[1] = 0.85  # Modern sofa has high semantic match

        ranked = ranking_service.rank_products(
            products=sofas,
            vector_scores=vector_scores,
            user_category=10,
            user_primary_style="modern",
            user_secondary_style="minimalist",
        )

        # Modern sofa should rank first
        assert ranked[0].product.id == 1
        print(f"\nModern living room search results:")
        for rp in ranked:
            print(f"  {rp.product.name}: {rp.final_score:.3f} - {rp.breakdown}")

    def test_scenario_wood_dining_set(self, ranking_service, furniture_catalog):
        """User searching for wooden dining furniture."""
        tables = [p for p in furniture_catalog if p.category_id == 20]
        vector_scores = {p.id: 0.5 for p in tables}

        ranked = ranking_service.rank_products(
            products=tables,
            vector_scores=vector_scores,
            user_category=20,
            user_materials=["wood"],
            user_color="brown",
        )

        # Oak farmhouse table should rank first (wood + brown)
        assert ranked[0].product.id == 11
        print(f"\nWood dining search results:")
        for rp in ranked:
            print(f"  {rp.product.name}: {rp.final_score:.3f} - {rp.breakdown}")

    def test_scenario_neutral_minimalist(self, ranking_service, furniture_catalog):
        """User searching for neutral-colored minimalist furniture."""
        all_products = furniture_catalog
        vector_scores = {p.id: 0.5 for p in all_products}

        ranked = ranking_service.rank_products(
            products=all_products,
            vector_scores=vector_scores,
            user_primary_style="minimalist",
            user_color="grey",
        )

        # Products with minimalist style and neutral colors should rank high
        top_3 = [rp.product.id for rp in ranked[:3]]
        assert 3 in top_3  # Nordic Scandinavian (minimalist secondary, grey)
        print(f"\nNeutral minimalist search results:")
        for rp in ranked[:5]:
            print(f"  {rp.product.name}: {rp.final_score:.3f} - {rp.breakdown}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
