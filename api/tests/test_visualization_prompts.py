"""
Test cases for Visualization Prompts refactoring.

Tests cover:
1. VisualizationPrompts class and prompt generation
2. Product dimension formatting
3. Workflow-specific prompts (BULK_INITIAL, INCREMENTAL_ADD, PRODUCT_REMOVAL, EDIT_BY_INSTRUCTION)
4. Dimension loading helpers
"""

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the classes and functions we're testing
from services.google_ai_service import VisualizationPrompts, enrich_products_with_dimensions, load_product_dimensions

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_product_with_dimensions():
    """Sample product with all dimensions specified."""
    return {
        "id": 1,
        "name": "Modern Velvet Sofa",
        "full_name": "Modern Velvet Sofa - Gray",
        "furniture_type": "sofa",
        "dimensions": {"width": 84, "depth": 36, "height": 32},
    }


@pytest.fixture
def sample_product_no_dimensions():
    """Sample product without dimensions."""
    return {
        "id": 2,
        "name": "Accent Chair",
        "full_name": "Accent Chair - Blue",
        "furniture_type": "accent_chair",
        "dimensions": {},
    }


@pytest.fixture
def sample_products_list():
    """List of sample products with varying dimensions."""
    return [
        {
            "id": 1,
            "name": "Modern Velvet Sofa",
            "full_name": "Modern Velvet Sofa - Gray",
            "furniture_type": "sofa",
            "dimensions": {"width": 84, "depth": 36, "height": 32},
        },
        {
            "id": 2,
            "name": "Accent Chair",
            "full_name": "Accent Chair - Blue",
            "furniture_type": "accent_chair",
            "dimensions": {"width": 28, "depth": 30, "height": 34},
        },
        {
            "id": 3,
            "name": "Coffee Table",
            "full_name": "Wooden Coffee Table",
            "furniture_type": "coffee_table",
            "dimensions": {"width": 48, "depth": 24, "height": 18},
        },
    ]


@pytest.fixture
def dimensions_map():
    """Sample dimensions map as returned by load_product_dimensions."""
    return {
        1: {"width": 84, "depth": 36, "height": 32},
        2: {"width": 28, "depth": 30, "height": 34},
        3: {"width": 48, "depth": 24, "height": 18},
    }


# =============================================================================
# Test 1: VisualizationPrompts Static Methods
# =============================================================================


class TestVisualizationPromptsStatic:
    """Test VisualizationPrompts static methods."""

    def test_get_system_intro(self):
        """Test that get_system_intro returns expected content."""
        intro = VisualizationPrompts.get_system_intro()

        assert "professional interior styling" in intro.lower()
        assert "visualizing tool" in intro.lower()

    def test_get_room_preservation_rules(self):
        """Test that get_room_preservation_rules contains key rules."""
        rules = VisualizationPrompts.get_room_preservation_rules()

        assert "ROOM PRESERVATION" in rules
        assert "OUTPUT DIMENSIONS" in rules or "dimensions" in rules.lower()
        assert "ASPECT RATIO" in rules or "aspect" in rules.lower()
        assert "CAMERA ANGLE" in rules or "camera" in rules.lower()
        assert "PHOTOREALISM" in rules or "photorealis" in rules.lower()

    def test_get_placement_guidelines(self):
        """Test that get_placement_guidelines contains product types."""
        guidelines = VisualizationPrompts.get_placement_guidelines()

        assert "SOFA" in guidelines.upper()
        assert "CHAIR" in guidelines.upper()
        assert "TABLE" in guidelines.upper()
        assert "LAMP" in guidelines.upper()
        # New additions from the plan
        assert "STORAGE" in guidelines.upper() or "CABINET" in guidelines.upper()
        assert "CURTAIN" in guidelines.upper() or "DRAPE" in guidelines.upper()

    def test_get_product_accuracy_rules(self):
        """Test that get_product_accuracy_rules contains accuracy requirements."""
        rules = VisualizationPrompts.get_product_accuracy_rules()

        assert "ACCURACY" in rules.upper()
        assert "MUST" in rules
        assert "reference" in rules.lower()


# =============================================================================
# Test 2: Product Dimension Formatting
# =============================================================================


class TestProductDimensionFormatting:
    """Test product dimension formatting methods."""

    def test_format_product_with_full_dimensions(self, sample_product_with_dimensions):
        """Test formatting a product with all dimensions."""
        result = VisualizationPrompts.format_product_with_dimensions(sample_product_with_dimensions, 1)

        assert "Product 1:" in result
        assert "Modern Velvet Sofa - Gray" in result
        assert "sofa" in result.lower()
        assert '84" W' in result
        assert '36" D' in result
        assert '32" H' in result

    def test_format_product_without_dimensions(self, sample_product_no_dimensions):
        """Test formatting a product without dimensions."""
        result = VisualizationPrompts.format_product_with_dimensions(sample_product_no_dimensions, 2)

        assert "Product 2:" in result
        assert "Accent Chair - Blue" in result
        assert "dimensions not specified" in result.lower()

    def test_format_product_partial_dimensions(self):
        """Test formatting a product with partial dimensions."""
        product = {
            "id": 5,
            "name": "Wall Art",
            "furniture_type": "wall_art",
            "dimensions": {"width": 36, "height": 24},  # No depth
        }
        result = VisualizationPrompts.format_product_with_dimensions(product, 3)

        assert '36" W' in result
        assert '24" H' in result
        # Depth should not appear
        assert "D" not in result or 'D"' not in result

    def test_format_products_list(self, sample_products_list):
        """Test formatting multiple products."""
        result = VisualizationPrompts.format_products_list(sample_products_list)

        assert "Product 1:" in result
        assert "Product 2:" in result
        assert "Product 3:" in result
        assert "Modern Velvet Sofa" in result
        assert "Accent Chair" in result
        assert "Coffee Table" in result


# =============================================================================
# Test 3: Workflow-Specific Prompts
# =============================================================================


class TestWorkflowPrompts:
    """Test workflow-specific prompt generation."""

    def test_bulk_initial_prompt(self, sample_products_list):
        """Test BULK_INITIAL workflow prompt."""
        prompt = VisualizationPrompts.get_bulk_initial_prompt(sample_products_list)

        # Should contain system intro
        assert "professional interior styling" in prompt.lower()

        # Should contain task description
        assert "INITIAL" in prompt.upper() or "FIRST TIME" in prompt.upper()

        # Should contain product count
        assert "3 product" in prompt.lower()

        # Should contain products with dimensions
        assert '84" W' in prompt  # Sofa width
        assert '28" W' in prompt  # Chair width

        # Should contain room preservation rules
        assert "ROOM PRESERVATION" in prompt or "PRESERVATION" in prompt.upper()

        # Should contain placement guidelines
        assert "PLACEMENT" in prompt.upper()

    def test_incremental_add_prompt(self, sample_products_list):
        """Test INCREMENTAL_ADD workflow prompt."""
        new_products = [sample_products_list[2]]  # Coffee table
        existing_products = sample_products_list[:2]  # Sofa and chair

        prompt = VisualizationPrompts.get_incremental_add_prompt(new_products, existing_products)

        # Should contain task description
        assert "ADD" in prompt.upper()

        # Should list existing products
        assert "EXISTING PRODUCTS" in prompt.upper()
        assert "Modern Velvet Sofa" in prompt

        # Should list new products
        assert "NEW PRODUCTS" in prompt.upper()
        assert "Coffee Table" in prompt

        # Should emphasize preservation
        assert "DO NOT MODIFY" in prompt.upper() or "EXACT same position" in prompt

    def test_removal_prompt(self, sample_products_list):
        """Test PRODUCT_REMOVAL workflow prompt."""
        products_to_remove = [
            {
                "name": "Accent Chair",
                "full_name": "Accent Chair - Blue",
                "quantity": 1,
                "dimensions": {"width": 28, "depth": 30, "height": 34},
            }
        ]
        remaining = [sample_products_list[0], sample_products_list[2]]  # Sofa and coffee table

        prompt = VisualizationPrompts.get_removal_prompt(products_to_remove, remaining)

        # Should use removal-specific intro (NOT the styling intro)
        assert "inpainting tool" in prompt.lower()
        assert "REMOVAL/DELETION TASK" in prompt.upper()

        # Should contain task description
        assert "DELETE" in prompt.upper() or "REMOVE" in prompt.upper()

        # Should list products to remove
        assert "Accent Chair" in prompt

        # Should list remaining products
        assert "REMAIN" in prompt.upper()
        assert "Modern Velvet Sofa" in prompt

        # Should mention what NOT to do
        assert "DO NOT add" in prompt

        # Should mention inpainting/background
        assert "background" in prompt.lower() or "inpaint" in prompt.lower()

    def test_edit_by_instruction_prompt_placement(self, sample_products_list):
        """Test EDIT_BY_INSTRUCTION workflow prompt for placement changes."""
        instruction = "Move the sofa to the left wall"

        prompt = VisualizationPrompts.get_edit_by_instruction_prompt(
            instruction=instruction,
            instruction_type="placement",
            current_products=sample_products_list,
            reference_image_provided=False,
        )

        # Should contain task description
        assert "MODIFY" in prompt.upper() or "EDIT" in prompt.upper()

        # Should contain user instruction
        assert "Move the sofa to the left wall" in prompt

        # Should contain placement-specific guidance
        assert "PLACEMENT" in prompt.upper()
        assert "move" in prompt.lower() or "position" in prompt.lower()

        # Should contain current products
        assert "CURRENT PRODUCTS" in prompt.upper()

    def test_edit_by_instruction_prompt_brightness(self, sample_products_list):
        """Test EDIT_BY_INSTRUCTION workflow prompt for brightness changes."""
        instruction = "Make the room brighter"

        prompt = VisualizationPrompts.get_edit_by_instruction_prompt(
            instruction=instruction,
            instruction_type="brightness",
            current_products=sample_products_list,
            reference_image_provided=False,
        )

        # Should contain brightness-specific guidance
        assert "BRIGHTNESS" in prompt.upper() or "LIGHTING" in prompt.upper()

        # Should contain user instruction
        assert "Make the room brighter" in prompt

    def test_edit_by_instruction_prompt_reference(self, sample_products_list):
        """Test EDIT_BY_INSTRUCTION workflow prompt with reference image."""
        instruction = "Make it look like this reference"

        prompt = VisualizationPrompts.get_edit_by_instruction_prompt(
            instruction=instruction,
            instruction_type="reference",
            current_products=sample_products_list,
            reference_image_provided=True,
        )

        # Should contain reference-specific guidance
        assert "REFERENCE" in prompt.upper()

        # Should mention reference image provided
        assert "reference image" in prompt.lower()


# =============================================================================
# Test 4: Dimension Loading Helpers
# =============================================================================


class TestDimensionLoadingHelpers:
    """Test dimension loading helper functions."""

    def test_enrich_products_with_dimensions(self, dimensions_map):
        """Test enriching products with dimensions from map."""
        products = [
            {"id": 1, "name": "Sofa"},
            {"id": 2, "name": "Chair"},
            {"id": 999, "name": "Unknown Product"},  # Not in map
        ]

        result = enrich_products_with_dimensions(products, dimensions_map)

        # Sofa should have dimensions
        assert result[0]["dimensions"]["width"] == 84
        assert result[0]["dimensions"]["depth"] == 36
        assert result[0]["dimensions"]["height"] == 32

        # Chair should have dimensions
        assert result[1]["dimensions"]["width"] == 28

        # Unknown product should have empty dimensions
        assert result[2]["dimensions"] == {}

    def test_enrich_products_preserves_existing_dimensions(self):
        """Test that existing dimensions are preserved if not in map."""
        products = [{"id": 1, "name": "Product", "dimensions": {"width": 100}}]
        dimensions_map = {}  # Empty map

        result = enrich_products_with_dimensions(products, dimensions_map)

        # Should preserve existing dimensions
        assert result[0]["dimensions"]["width"] == 100

    @pytest.mark.asyncio
    async def test_load_product_dimensions_with_mock_db(self):
        """Test load_product_dimensions with mocked database."""
        # Create mock database session
        mock_db = AsyncMock()

        # Create mock result
        mock_attr1 = MagicMock()
        mock_attr1.product_id = 1
        mock_attr1.attribute_name = "width"
        mock_attr1.attribute_value = "84"

        mock_attr2 = MagicMock()
        mock_attr2.product_id = 1
        mock_attr2.attribute_name = "height"
        mock_attr2.attribute_value = "32"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_attr1, mock_attr2]
        mock_db.execute.return_value = mock_result

        result = await load_product_dimensions(mock_db, [1])

        assert 1 in result
        assert result[1]["width"] == 84.0
        assert result[1]["height"] == 32.0

    @pytest.mark.asyncio
    async def test_load_product_dimensions_handles_invalid_values(self):
        """Test that invalid dimension values are handled gracefully."""
        mock_db = AsyncMock()

        # Create mock with invalid value
        mock_attr = MagicMock()
        mock_attr.product_id = 1
        mock_attr.attribute_name = "width"
        mock_attr.attribute_value = "not_a_number"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_attr]
        mock_db.execute.return_value = mock_result

        result = await load_product_dimensions(mock_db, [1])

        # Should have empty dimensions for product 1 (invalid value skipped)
        assert 1 in result
        assert "width" not in result[1]


# =============================================================================
# Test 5: Integration - Full Prompt with Dimensions
# =============================================================================


class TestPromptIntegration:
    """Integration tests for complete prompt generation."""

    def test_full_bulk_prompt_includes_all_components(self, sample_products_list):
        """Test that bulk prompt includes all required components."""
        prompt = VisualizationPrompts.get_bulk_initial_prompt(sample_products_list)

        # Must include system intro
        assert VisualizationPrompts.SYSTEM_INTRO in prompt

        # Must include room preservation rules (check for key phrases)
        assert "OUTPUT DIMENSIONS" in prompt or "ROOM PRESERVATION" in prompt

        # Must include placement guidelines
        assert "SOFA" in prompt.upper()

        # Must include product accuracy rules
        assert "ACCURACY" in prompt.upper() or "EXACT" in prompt.upper()

        # Must include products with dimensions
        for product in sample_products_list:
            assert product["full_name"] in prompt or product["name"] in prompt

    def test_prompt_dimension_format_consistency(self, sample_products_list):
        """Test that dimensions are formatted consistently across prompts."""
        bulk_prompt = VisualizationPrompts.get_bulk_initial_prompt(sample_products_list)
        add_prompt = VisualizationPrompts.get_incremental_add_prompt([sample_products_list[0]], sample_products_list[1:])

        # Both should use the same dimension format: W x D x H
        assert '" W' in bulk_prompt
        assert '" D' in bulk_prompt
        assert '" H' in bulk_prompt

        assert '" W' in add_prompt
        assert '" D' in add_prompt
        assert '" H' in add_prompt


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
