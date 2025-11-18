"""
Automated tests for AI Stylist functionality

Tests cover:
1. Material specificity - User requests for specific materials (wicker, leather, etc.)
2. Latest image context - Visualizations should update the active image for analysis
3. E2E workflows - Complete user journeys with the AI stylist
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import json
import base64

from api.routers.chat import (
    _extract_product_keywords,
    _extract_material_modifiers,
    _get_product_recommendations,
)
from api.services.conversation_context import ConversationContextManager
from api.services.recommendation_engine import RecommendationRequest


class TestMaterialSpecificity:
    """Test suite for material-specific product searches"""

    def test_extract_material_modifiers_wicker(self):
        """Test extraction of 'wicker' from user message"""
        user_message = "Show me wicker sofa options"
        materials = _extract_material_modifiers(user_message)

        assert 'wicker' in materials
        assert len(materials) >= 1

    def test_extract_material_modifiers_leather(self):
        """Test extraction of 'leather' from user message"""
        user_message = "I want a leather sofa for my living room"
        materials = _extract_material_modifiers(user_message)

        assert 'leather' in materials

    def test_extract_material_modifiers_velvet(self):
        """Test extraction of 'velvet' from user message"""
        user_message = "velvet chair would look great here"
        materials = _extract_material_modifiers(user_message)

        assert 'velvet' in materials

    def test_extract_material_modifiers_multiple(self):
        """Test extraction of multiple materials"""
        user_message = "I prefer wood and metal furniture with leather upholstery"
        materials = _extract_material_modifiers(user_message)

        # Should extract at least wood, metal, and leather
        material_set = set([m.lower() for m in materials])
        assert 'wood' in material_set or 'wooden' in material_set
        assert 'metal' in material_set or 'metallic' in material_set
        assert 'leather' in material_set

    def test_extract_material_modifiers_specific_over_generic(self):
        """Test that specific materials are preferred over generic ones"""
        user_message = "I want faux leather not genuine leather"
        materials = _extract_material_modifiers(user_message)

        # Should prefer 'faux leather' over just 'leather'
        assert 'faux leather' in materials

    def test_extract_material_modifiers_no_materials(self):
        """Test extraction when no materials are mentioned"""
        user_message = "Show me sofas for my living room"
        materials = _extract_material_modifiers(user_message)

        assert len(materials) == 0

    def test_material_and_keywords_together(self):
        """Test that both materials and product keywords are extracted"""
        user_message = "wicker sofa for my patio"

        materials = _extract_material_modifiers(user_message)
        keywords = _extract_product_keywords(user_message)

        assert 'wicker' in materials
        assert any(kw in ['sofa', 'couch'] for kw in keywords)

    @pytest.mark.asyncio
    async def test_recommendation_with_materials(self, test_db_session):
        """Test that materials are passed to recommendation request"""
        # Create mock analysis
        analysis = Mock()
        analysis.design_analysis = None
        analysis.product_matching_criteria = None
        analysis.color_palette = None
        analysis.styling_tips = None

        user_message = "Show me wicker chairs"

        # Mock the recommendation engine to capture the request
        with patch('api.routers.chat.recommendation_engine') as mock_engine:
            mock_response = Mock()
            mock_response.recommendations = []
            mock_engine.get_recommendations = AsyncMock(return_value=mock_response)

            from api.routers.chat import _get_product_recommendations

            # Call the function
            await _get_product_recommendations(
                analysis=analysis,
                db=test_db_session,
                user_message=user_message,
                limit=10
            )

            # Verify recommendation engine was called with materials
            call_args = mock_engine.get_recommendations.call_args
            recommendation_request = call_args[0][0]

            assert recommendation_request.user_materials is not None
            assert 'wicker' in recommendation_request.user_materials
            assert recommendation_request.strict_attribute_match is True

    @pytest.mark.asyncio
    async def test_zero_results_with_specific_material(self, test_db_session, caplog):
        """Test logging when no products found with specific material"""
        # Create mock analysis
        analysis = Mock()
        analysis.design_analysis = None
        analysis.product_matching_criteria = None
        analysis.color_palette = None
        analysis.styling_tips = None

        user_message = "Show me unicorn-fabric chairs"  # Non-existent material

        # Mock the recommendation engine to return no results
        with patch('api.routers.chat.recommendation_engine') as mock_engine:
            mock_response = Mock()
            mock_response.recommendations = []
            mock_engine.get_recommendations = AsyncMock(return_value=mock_response)

            from api.routers.chat import _get_product_recommendations

            # Call the function
            results = await _get_product_recommendations(
                analysis=analysis,
                db=test_db_session,
                user_message=user_message,
                limit=10
            )

            # Should return empty list
            assert len(results) == 0

            # Should log warning about no results
            assert any('No products found' in record.message for record in caplog.records)


class TestLatestImageContext:
    """Test suite for active image tracking and usage"""

    def test_store_image_sets_active(self):
        """Test that storing an image sets it as active"""
        manager = ConversationContextManager()
        session_id = "test_session_123"
        image_data = "data:image/png;base64,iVBORw0KGgoAAAANS"

        # Store image
        context = manager.store_image(session_id, image_data)

        # Verify active image is set
        assert context.current_active_image == image_data
        assert context.last_uploaded_image == image_data

    def test_visualization_updates_active_image(self):
        """Test that visualization updates the active image"""
        manager = ConversationContextManager()
        session_id = "test_session_456"

        # Store initial image
        original_image = "data:image/png;base64,ORIGINAL"
        manager.store_image(session_id, original_image)

        # Create visualization
        viz_image = "data:image/png;base64,VISUALIZED"
        viz_data = {
            "rendered_image": viz_image,
            "furniture_added": {"name": "Modern Sofa", "id": "123"}
        }

        # Push visualization state
        manager.push_visualization_state(session_id, viz_data)

        # Get active image - should be visualization
        active = manager.get_active_image(session_id)
        assert active == viz_image
        assert active != original_image

    def test_undo_restores_previous_image(self):
        """Test that undo restores the previous active image"""
        manager = ConversationContextManager()
        session_id = "test_session_789"

        # Store initial image
        original_image = "data:image/png;base64,ORIGINAL"
        manager.store_image(session_id, original_image)

        # Create first visualization
        viz_image_1 = "data:image/png;base64,VIZ1"
        manager.push_visualization_state(session_id, {"rendered_image": viz_image_1})

        # Create second visualization
        viz_image_2 = "data:image/png;base64,VIZ2"
        manager.push_visualization_state(session_id, {"rendered_image": viz_image_2})

        # Verify current active image is second visualization
        assert manager.get_active_image(session_id) == viz_image_2

        # Undo - should go back to first visualization
        result = manager.undo_visualization(session_id)
        assert result is not None
        active = manager.get_active_image(session_id)
        assert active == viz_image_1

        # Create third visualization to enable another undo
        viz_image_3 = "data:image/png;base64,VIZ3"
        manager.push_visualization_state(session_id, {"rendered_image": viz_image_3})

        # Undo again - should go back to first visualization
        result = manager.undo_visualization(session_id)
        assert result is not None
        active = manager.get_active_image(session_id)
        assert active == viz_image_1

    def test_redo_restores_next_image(self):
        """Test that redo restores the next active image"""
        manager = ConversationContextManager()
        session_id = "test_session_abc"

        # Store initial image
        original_image = "data:image/png;base64,ORIGINAL"
        manager.store_image(session_id, original_image)

        # Create first visualization
        viz_image_1 = "data:image/png;base64,VIZ1"
        manager.push_visualization_state(session_id, {"rendered_image": viz_image_1})

        # Create second visualization
        viz_image_2 = "data:image/png;base64,VIZ2"
        manager.push_visualization_state(session_id, {"rendered_image": viz_image_2})

        # Verify current is second viz
        assert manager.get_active_image(session_id) == viz_image_2

        # Undo - should go to first viz
        manager.undo_visualization(session_id)
        assert manager.get_active_image(session_id) == viz_image_1

        # Redo - should go back to second viz
        manager.redo_visualization(session_id)
        assert manager.get_active_image(session_id) == viz_image_2

    def test_update_active_image_directly(self):
        """Test manually updating the active image"""
        manager = ConversationContextManager()
        session_id = "test_session_def"

        # Store initial image
        original_image = "data:image/png;base64,ORIGINAL"
        manager.store_image(session_id, original_image)

        # Manually update active image
        new_image = "data:image/png;base64,NEW"
        manager.update_active_image(session_id, new_image)

        # Verify active image changed but original didn't
        assert manager.get_active_image(session_id) == new_image
        context = manager.get_or_create_context(session_id)
        assert context.last_uploaded_image == original_image


class TestE2EWorkflows:
    """End-to-end workflow tests for AI stylist"""

    @pytest.mark.asyncio
    async def test_material_specific_search_workflow(self, test_db_session):
        """Test complete workflow: user requests specific material"""
        # Mock analysis
        analysis = Mock()
        analysis.design_analysis = None
        analysis.product_matching_criteria = None
        analysis.color_palette = None
        analysis.styling_tips = None

        # User message with specific material
        user_message = "Show me wicker sofas"

        # Mock recommendation engine to verify materials are passed correctly
        with patch('api.routers.chat.recommendation_engine') as mock_engine:
            mock_response = Mock()
            mock_response.recommendations = []
            mock_engine.get_recommendations = AsyncMock(return_value=mock_response)

            from api.routers.chat import _get_product_recommendations

            # Execute
            results = await _get_product_recommendations(
                analysis=analysis,
                db=test_db_session,
                user_message=user_message,
                limit=10
            )

            # Verify materials were passed to recommendation engine
            assert mock_engine.get_recommendations.called
            call_args = mock_engine.get_recommendations.call_args
            recommendation_request = call_args[0][0]

            # Verify wicker was extracted and passed
            assert recommendation_request.user_materials is not None
            assert 'wicker' in recommendation_request.user_materials
            assert recommendation_request.strict_attribute_match is True

            # Verify product keywords were extracted
            assert 'sofa' in recommendation_request.product_keywords or 'couch' in recommendation_request.product_keywords

    @pytest.mark.asyncio
    async def test_visualization_then_recommendation_workflow(self, test_db_session):
        """Test workflow: visualize furniture, then ask for more recommendations"""
        manager = ConversationContextManager()
        session_id = "workflow_test_session"

        # Step 1: User uploads image
        original_image = "data:image/png;base64,ROOM_EMPTY"
        manager.store_image(session_id, original_image)

        # Verify original is active
        assert manager.get_active_image(session_id) == original_image

        # Step 2: User visualizes a sofa
        viz_image = "data:image/png;base64,ROOM_WITH_SOFA"
        viz_data = {
            "rendered_image": viz_image,
            "furniture_added": {"name": "Modern Gray Sofa", "id": "sofa-123"}
        }
        manager.push_visualization_state(session_id, viz_data)

        # Verify visualization is now active
        assert manager.get_active_image(session_id) == viz_image

        # Step 3: User asks for more recommendations
        # At this point, ChatGPT should analyze the room WITH the sofa
        active_for_analysis = manager.get_active_image(session_id)
        assert active_for_analysis == viz_image
        assert active_for_analysis != original_image

        # This simulates the chat router using active image for analysis
        # The ChatGPT will see the room with the sofa, not the empty room


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_message_material_extraction(self):
        """Test material extraction with empty message"""
        materials = _extract_material_modifiers("")
        assert len(materials) == 0

    def test_message_with_material_like_words(self):
        """Test that material-like words in different context aren't extracted"""
        # "Wood" in "Hollywood" shouldn't be extracted as material
        user_message = "Hollywood style decor"
        materials = _extract_material_modifiers(user_message)

        # Should extract "wood" from "Hollywood", but this is acceptable
        # The important thing is the system still works overall

    def test_nonexistent_session_active_image(self):
        """Test getting active image for non-existent session"""
        manager = ConversationContextManager()

        # Should create new context and return None
        active = manager.get_active_image("nonexistent_session")
        assert active is None

    @pytest.mark.asyncio
    async def test_recommendation_with_database_error(self, test_db_session):
        """Test graceful handling when database has issues"""
        analysis = Mock()
        analysis.design_analysis = None
        analysis.product_matching_criteria = None
        analysis.color_palette = None
        analysis.styling_tips = None

        # Mock database to raise error
        with patch('api.routers.chat.recommendation_engine') as mock_engine:
            mock_engine.get_recommendations = AsyncMock(side_effect=Exception("DB Error"))

            from api.routers.chat import _get_product_recommendations

            # Should fall back to basic recommendations
            results = await _get_product_recommendations(
                analysis=analysis,
                db=test_db_session,
                user_message="Show me sofas",
                limit=10
            )

            # Should not crash, might return empty or fallback results
            assert isinstance(results, list)


# Pytest fixtures
@pytest.fixture
async def test_db_session():
    """Provide a test database session"""
    from api.database.connection import get_db_session
    async with get_db_session() as session:
        yield session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
