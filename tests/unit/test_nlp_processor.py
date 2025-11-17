"""
Unit tests for NLP Processor module
Tests design style extraction, preference analysis, and intent classification
"""
import pytest
from api.services.nlp_processor import (
    design_nlp_processor,
    StyleExtraction,
    PreferenceAnalysis,
    IntentClassification
)


class TestStyleExtraction:
    """Tests for style extraction functionality"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_modern_style_detection(self):
        """Test detection of modern style keywords"""
        text = "I want a modern and minimalist living room with clean lines"
        result = await design_nlp_processor.extract_design_styles(text)

        assert isinstance(result, StyleExtraction)
        assert result.primary_style == "modern"
        assert "minimalist" in result.style_keywords or "modern" in result.style_keywords
        assert result.confidence_score > 0.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_traditional_style_detection(self):
        """Test detection of traditional style keywords"""
        text = "I prefer traditional and classic elegant furniture"
        result = await design_nlp_processor.extract_design_styles(text)

        assert result.primary_style == "traditional"
        assert result.confidence_score > 0.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mixed_style_detection(self):
        """Test detection when multiple styles are mentioned"""
        text = "I like modern furniture but with some rustic elements"
        result = await design_nlp_processor.extract_design_styles(text)

        assert result.primary_style in ["modern", "rustic"]
        assert len(result.secondary_styles) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_style_mentioned(self):
        """Test fallback when no style is mentioned"""
        text = "I need some furniture"
        result = await design_nlp_processor.extract_design_styles(text)

        assert result.primary_style == "modern"  # Default fallback
        assert result.confidence_score < 0.3


class TestPreferenceAnalysis:
    """Tests for preference analysis functionality"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_color_extraction(self):
        """Test extraction of color preferences"""
        text = "I want white walls with gray accents and blue furniture"
        result = await design_nlp_processor.analyze_preferences(text)

        assert isinstance(result, PreferenceAnalysis)
        assert "white" in result.colors or "gray" in result.colors or "blue" in result.colors
        assert len(result.colors) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_material_extraction(self):
        """Test extraction of material preferences"""
        text = "I prefer wooden furniture with metal accents"
        result = await design_nlp_processor.analyze_preferences(text)

        assert "wood" in result.materials or "wooden" in result.materials or "metal" in result.materials
        assert len(result.materials) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_budget_analysis(self):
        """Test budget indicator analysis"""
        text = "I'm looking for luxury high-end furniture"
        result = await design_nlp_processor.analyze_preferences(text)

        assert result.budget_indicators == "luxury"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_budget_analysis_affordable(self):
        """Test affordable budget detection"""
        text = "I need budget-friendly affordable furniture"
        result = await design_nlp_processor.analyze_preferences(text)

        assert result.budget_indicators == "budget"


class TestIntentClassification:
    """Tests for intent classification functionality"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_browse_products_intent(self):
        """Test detection of product browsing intent"""
        text = "Show me some sofas"
        result = await design_nlp_processor.classify_intent(text)

        assert isinstance(result, IntentClassification)
        assert result.primary_intent == "browse_products"
        assert result.confidence_score > 0.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_design_consultation_intent(self):
        """Test detection of design consultation intent"""
        text = "Can you help me design my living room?"
        result = await design_nlp_processor.classify_intent(text)

        assert result.primary_intent == "design_consultation"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_visualization_intent(self):
        """Test detection of visualization intent"""
        text = "I want to visualize how this sofa would look in my room"
        result = await design_nlp_processor.classify_intent(text)

        assert result.primary_intent == "visualization"

    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.regression
    async def test_image_modification_intent_remove(self):
        """Test detection of removal modification intent (Issue 21 regression test)"""
        test_cases = [
            "remove all furniture from the room",
            "remove everything from the space",
            "clear the room",
            "get rid of everything",
            "remove all the furniture"
        ]

        for text in test_cases:
            result = await design_nlp_processor.classify_intent(text)
            assert result.primary_intent == "image_modification", f"Failed for: {text}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    @pytest.mark.regression
    async def test_image_modification_intent_placement(self):
        """Test detection of placement modification intent (Issue 15 regression test)"""
        test_cases = [
            "place the ottoman in front of the sofa",
            "move the lamp to the corner",
            "put the table in the center",
            "reposition the chair near the window"
        ]

        for text in test_cases:
            result = await design_nlp_processor.classify_intent(text)
            assert result.primary_intent == "image_modification", f"Failed for: {text}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_entity_extraction(self):
        """Test extraction of entities from text"""
        text = "I need a sofa for my living room that is 6 feet long"
        result = await design_nlp_processor.classify_intent(text)

        assert "sofa" in result.entities.get("furniture", [])
        assert "living room" in result.entities.get("rooms", [])


class TestConversationHistory:
    """Tests for conversation history processing"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_conversation_history_processing(self):
        """Test processing of entire conversation history"""
        messages = [
            {"role": "user", "content": "I want modern furniture"},
            {"role": "assistant", "content": "Great choice!"},
            {"role": "user", "content": "Show me gray sofas"}
        ]

        result = await design_nlp_processor.process_conversation_history(messages)

        assert "style_analysis" in result
        assert "preferences" in result
        assert "intent" in result
        assert result["style_analysis"]["primary_style"] == "modern"
        assert "gray" in result["preferences"]["colors"] or "grey" in result["preferences"]["colors"]


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_text(self):
        """Test handling of empty text input"""
        result = await design_nlp_processor.classify_intent("")

        assert result.primary_intent == "general_inquiry"
        assert result.confidence_score == 0.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_very_long_text(self):
        """Test handling of very long text"""
        text = " ".join(["furniture"] * 1000)
        result = await design_nlp_processor.classify_intent(text)

        assert isinstance(result, IntentClassification)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Test handling of special characters"""
        text = "I need @#$% furniture !!! ???"
        result = await design_nlp_processor.classify_intent(text)

        assert isinstance(result, IntentClassification)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_multilingual_input(self):
        """Test handling of non-English text"""
        text = "Je veux des meubles modernes"  # French
        result = await design_nlp_processor.extract_design_styles(text)

        # Should still work or provide fallback
        assert isinstance(result, StyleExtraction)
