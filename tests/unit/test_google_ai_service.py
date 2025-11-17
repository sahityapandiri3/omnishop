"""
Unit tests for Google AI Service module
Tests image analysis, room visualization, and AI integration
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import base64
import io
from PIL import Image
from api.services.google_ai_service import (
    google_ai_service,
    RoomAnalysis,
    SpatialAnalysis,
    VisualizationRequest,
    VisualizationResult
)


class TestGoogleAIServiceInitialization:
    """Tests for Google AI service initialization"""

    @pytest.mark.unit
    def test_service_initialized(self):
        """Test that Google AI service is properly initialized"""
        assert google_ai_service is not None
        assert google_ai_service.api_key is not None
        assert google_ai_service.base_url == "https://generativelanguage.googleapis.com/v1beta"

    @pytest.mark.unit
    def test_rate_limiter_exists(self):
        """Test that rate limiter is created"""
        assert google_ai_service.rate_limiter is not None

    @pytest.mark.unit
    def test_usage_stats_initialized(self):
        """Test that usage stats are initialized"""
        stats = google_ai_service.usage_stats
        assert "total_requests" in stats
        assert "successful_requests" in stats
        assert "failed_requests" in stats
        assert stats["total_requests"] >= 0


class TestImagePreprocessing:
    """Tests for image preprocessing"""

    @pytest.mark.unit
    def test_preprocess_base64_image(self):
        """Test preprocessing of base64 encoded image"""
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode()
        image_data = f"data:image/jpeg;base64,{image_base64}"

        processed = google_ai_service._preprocess_image(image_data)

        # Should return base64 encoded data
        assert isinstance(processed, str)
        assert len(processed) > 0

    @pytest.mark.unit
    def test_preprocess_strips_data_url_prefix(self):
        """Test that data URL prefix is stripped"""
        # Create test image
        img = Image.new('RGB', (100, 100), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode()
        image_data = f"data:image/jpeg;base64,{image_base64}"

        processed = google_ai_service._preprocess_image(image_data)

        # Should not contain data URL prefix
        assert not processed.startswith('data:image')

    @pytest.mark.unit
    def test_preprocess_converts_to_rgb(self):
        """Test that images are converted to RGB"""
        # Create RGBA image
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode()

        processed = google_ai_service._preprocess_image(image_base64)

        # Should successfully process and convert
        assert isinstance(processed, str)
        assert len(processed) > 0

    @pytest.mark.unit
    def test_preprocess_resizes_large_images(self):
        """Test that large images are resized"""
        # Create large image
        img = Image.new('RGB', (2000, 2000), color='green')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode()

        processed = google_ai_service._preprocess_image(image_base64)

        # Decode and check size
        processed_bytes = base64.b64decode(processed)
        processed_img = Image.open(io.BytesIO(processed_bytes))

        # Should be resized to max 1024px
        assert processed_img.width <= 1024
        assert processed_img.height <= 1024


class TestRoomAnalysisFallback:
    """Tests for fallback room analysis"""

    @pytest.mark.unit
    def test_fallback_room_analysis_structure(self):
        """Test that fallback room analysis has correct structure"""
        fallback = google_ai_service._create_fallback_room_analysis()

        assert isinstance(fallback, RoomAnalysis)
        assert fallback.room_type == "living_room"
        assert isinstance(fallback.dimensions, dict)
        assert fallback.confidence_score == 0.3

    @pytest.mark.unit
    def test_fallback_room_analysis_has_dimensions(self):
        """Test that fallback includes dimensions"""
        fallback = google_ai_service._create_fallback_room_analysis()

        assert "estimated_width_ft" in fallback.dimensions
        assert "estimated_length_ft" in fallback.dimensions
        assert "square_footage" in fallback.dimensions


class TestSpatialAnalysisFallback:
    """Tests for fallback spatial analysis"""

    @pytest.mark.unit
    def test_fallback_spatial_analysis_structure(self):
        """Test that fallback spatial analysis has correct structure"""
        fallback = google_ai_service._create_fallback_spatial_analysis()

        assert isinstance(fallback, SpatialAnalysis)
        assert fallback.layout_type == "open"
        assert isinstance(fallback.traffic_patterns, list)
        assert isinstance(fallback.focal_points, list)

    @pytest.mark.unit
    def test_fallback_spatial_analysis_has_recommendations(self):
        """Test that fallback includes placement suggestions"""
        fallback = google_ai_service._create_fallback_spatial_analysis()

        assert len(fallback.placement_suggestions) > 0
        assert isinstance(fallback.scale_recommendations, dict)


class TestVisualizationRequest:
    """Tests for VisualizationRequest dataclass"""

    @pytest.mark.unit
    def test_visualization_request_creation(self, sample_base64_image):
        """Test creating visualization request"""
        request = VisualizationRequest(
            base_image=sample_base64_image,
            products_to_place=[{"name": "Modern Sofa", "image_url": "https://example.com/sofa.jpg"}],
            placement_positions=[{"x": 100, "y": 200}],
            lighting_conditions="natural",
            render_quality="high",
            style_consistency=True,
            user_style_description="Place the sofa in the center"
        )

        assert request.base_image == sample_base64_image
        assert len(request.products_to_place) == 1
        assert request.lighting_conditions == "natural"
        assert request.render_quality == "high"
        assert request.style_consistency is True
        assert "center" in request.user_style_description

    @pytest.mark.unit
    def test_visualization_request_with_empty_description(self, sample_base64_image):
        """Test visualization request with empty user description"""
        request = VisualizationRequest(
            base_image=sample_base64_image,
            products_to_place=[],
            placement_positions=[],
            lighting_conditions="mixed",
            render_quality="medium",
            style_consistency=False
        )

        assert request.user_style_description == ""
        assert len(request.products_to_place) == 0


class TestVisualizationResult:
    """Tests for VisualizationResult dataclass"""

    @pytest.mark.unit
    def test_visualization_result_structure(self, sample_base64_image):
        """Test visualization result structure"""
        result = VisualizationResult(
            rendered_image=sample_base64_image,
            processing_time=2.5,
            quality_score=0.88,
            placement_accuracy=0.90,
            lighting_realism=0.85,
            confidence_score=0.87
        )

        assert result.rendered_image == sample_base64_image
        assert result.processing_time == 2.5
        assert 0 <= result.quality_score <= 1.0
        assert 0 <= result.placement_accuracy <= 1.0
        assert 0 <= result.lighting_realism <= 1.0
        assert 0 <= result.confidence_score <= 1.0


class TestRateLimiter:
    """Tests for rate limiter functionality"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire(self):
        """Test that rate limiter acquire works"""
        # This should not raise an error
        await google_ai_service.rate_limiter.acquire()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rate_limiter_tracks_requests(self):
        """Test that rate limiter tracks requests"""
        initial_count = len(google_ai_service.rate_limiter.requests)
        await google_ai_service.rate_limiter.acquire()
        new_count = len(google_ai_service.rate_limiter.requests)

        assert new_count >= initial_count


class TestUsageStatistics:
    """Tests for usage statistics"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_usage_statistics(self):
        """Test getting usage statistics"""
        stats = await google_ai_service.get_usage_statistics()

        assert "total_requests" in stats
        assert "successful_requests" in stats
        assert "failed_requests" in stats
        assert "success_rate" in stats
        assert "average_processing_time" in stats

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_usage_statistics_calculations(self):
        """Test that usage statistics are calculated correctly"""
        stats = await google_ai_service.get_usage_statistics()

        # Success rate should be between 0 and 100
        assert 0 <= stats["success_rate"] <= 100

        # Average processing time should be non-negative
        assert stats["average_processing_time"] >= 0


class TestRoomAnalysisDataclass:
    """Tests for RoomAnalysis dataclass"""

    @pytest.mark.unit
    def test_room_analysis_creation(self):
        """Test creating room analysis"""
        analysis = RoomAnalysis(
            room_type="bedroom",
            dimensions={"width": 12, "length": 15, "height": 9},
            lighting_conditions="natural",
            color_palette=["white", "gray", "blue"],
            existing_furniture=[{"type": "bed", "position": "center"}],
            architectural_features=["windows", "closet"],
            style_assessment="modern",
            confidence_score=0.85
        )

        assert analysis.room_type == "bedroom"
        assert analysis.dimensions["width"] == 12
        assert len(analysis.color_palette) == 3
        assert analysis.confidence_score == 0.85


class TestSpatialAnalysisDataclass:
    """Tests for SpatialAnalysis dataclass"""

    @pytest.mark.unit
    def test_spatial_analysis_creation(self):
        """Test creating spatial analysis"""
        analysis = SpatialAnalysis(
            layout_type="open",
            traffic_patterns=["main_entrance", "hallway"],
            focal_points=[{"type": "window", "importance": "high"}],
            available_spaces=[{"area": "center", "size": 100}],
            placement_suggestions=[{"furniture": "sofa", "position": "north_wall"}],
            scale_recommendations={"sofa": "84_inches"}
        )

        assert analysis.layout_type == "open"
        assert len(analysis.traffic_patterns) == 2
        assert len(analysis.focal_points) == 1


class TestImageDownload:
    """Tests for image download functionality"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_download_image_success(self):
        """Test successful image download"""
        # Create test image
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()

        # Create mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=image_bytes)

        # Create async context manager mock using MagicMock
        from unittest.mock import MagicMock
        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=False)

        # Mock session
        mock_session = Mock()
        mock_session.get = Mock(return_value=mock_context_manager)

        # Patch _get_session to return our mock_session
        async def mock_get_session():
            return mock_session

        with patch.object(google_ai_service, '_get_session', new=mock_get_session):
            result = await google_ai_service._download_image("https://example.com/image.jpg")

            assert result is not None
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_download_image_failure(self):
        """Test failed image download"""
        # Create mock response with error
        mock_response = Mock()
        mock_response.status = 404

        # Create async context manager mock using MagicMock
        from unittest.mock import MagicMock
        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=False)

        # Mock session
        mock_session = Mock()
        mock_session.get = Mock(return_value=mock_context_manager)

        # Patch _get_session to return our mock_session
        async def mock_get_session():
            return mock_session

        with patch.object(google_ai_service, '_get_session', new=mock_get_session):
            result = await google_ai_service._download_image("https://example.com/notfound.jpg")

            assert result is None


class TestHealthCheck:
    """Tests for health check functionality"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_structure(self):
        """Test that health check returns proper structure"""
        # Mock the API request
        with patch.object(google_ai_service, '_make_api_request', return_value={"candidates": []}):
            result = await google_ai_service.health_check()

            assert "status" in result
            assert "api_key_valid" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_on_api_error(self):
        """Test health check when API fails"""
        # Mock API request failure
        with patch.object(google_ai_service, '_make_api_request', side_effect=Exception("API Error")):
            result = await google_ai_service.health_check()

            assert result["status"] == "unhealthy"
            assert "error" in result


class TestVisualizationErrorHandling:
    """Tests for visualization error handling"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_visualization_returns_original_on_error(self, sample_base64_image):
        """Test that visualization returns original image on error"""
        request = VisualizationRequest(
            base_image=sample_base64_image,
            products_to_place=[{"name": "Sofa"}],
            placement_positions=[],
            lighting_conditions="natural",
            render_quality="high",
            style_consistency=True
        )

        # Mock the genai client to raise an error
        with patch.object(google_ai_service.genai_client.models, 'generate_content_stream', side_effect=Exception("API Error")):
            result = await google_ai_service.generate_room_visualization(request)

            # Should return original image on error
            assert result.rendered_image == sample_base64_image
            assert result.confidence_score <= 0.5


class TestSessionManagement:
    """Tests for HTTP session management"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_session_creates_session(self):
        """Test that get_session creates a session"""
        # Clear existing session
        google_ai_service.session = None

        session = await google_ai_service._get_session()

        assert session is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_session_reuses_existing(self):
        """Test that get_session reuses existing session"""
        session1 = await google_ai_service._get_session()
        session2 = await google_ai_service._get_session()

        # Should return same session instance
        assert session1 is session2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing HTTP session"""
        # Ensure session exists
        await google_ai_service._get_session()

        # Close session
        await google_ai_service.close()

        # Session should be None
        assert google_ai_service.session is None


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @pytest.mark.unit
    def test_preprocess_invalid_base64(self):
        """Test preprocessing with invalid base64"""
        invalid_data = "not_valid_base64_data"

        # Should handle gracefully and return input
        result = google_ai_service._preprocess_image(invalid_data)

        # Should return the input data when processing fails
        assert result == invalid_data

    @pytest.mark.unit
    def test_preprocess_empty_string(self):
        """Test preprocessing with empty string"""
        result = google_ai_service._preprocess_image("")

        # Should return empty string
        assert result == ""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_visualization_with_empty_products(self, sample_base64_image):
        """Test visualization request with no products"""
        request = VisualizationRequest(
            base_image=sample_base64_image,
            products_to_place=[],
            placement_positions=[],
            lighting_conditions="natural",
            render_quality="high",
            style_consistency=True,
            user_style_description="Make this room modern"
        )

        # Should handle empty products list
        assert len(request.products_to_place) == 0
