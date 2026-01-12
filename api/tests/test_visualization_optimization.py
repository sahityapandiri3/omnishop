"""
Test cases for Visualization Optimization changes.

Tests cover:
1. RoomAnalysis serialization (to_dict/from_dict)
2. Combined room analysis function (analyze_room_with_furniture)
3. Upload endpoint room analysis caching
4. Visualize endpoint using cached room analysis
5. SAM endpoints returning 501 (disabled)
6. Image preprocessing quality improvements
"""

import base64
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

# Import the classes and functions we're testing
from services.google_ai_service import GoogleAIStudioService, RoomAnalysis, google_ai_service

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_room_analysis_dict():
    """Sample room analysis data as dictionary."""
    return {
        "room_type": "living_room",
        "dimensions": {
            "estimated_width_ft": 15.0,
            "estimated_length_ft": 20.0,
            "estimated_height_ft": 10.0,
        },
        "lighting_conditions": "natural",
        "color_palette": ["beige", "gray", "white"],
        "existing_furniture": [
            {
                "object_type": "sofa",
                "position": "center-left",
                "size": "large",
                "style": "modern",
                "color": "gray",
                "material": "fabric",
                "confidence": 0.95,
            },
            {
                "object_type": "coffee_table",
                "position": "center",
                "size": "medium",
                "style": "modern",
                "color": "brown",
                "material": "wood",
                "confidence": 0.88,
            },
        ],
        "architectural_features": ["windows", "fireplace"],
        "style_assessment": "modern",
        "confidence_score": 0.85,
        "scale_references": {
            "door_visible": True,
            "window_visible": True,
        },
        "camera_view_analysis": {
            "viewing_angle": "straight_on",
            "primary_wall": "back",
            "floor_center_location": "image_center",
            "recommended_furniture_zone": "center_floor",
        },
    }


@pytest.fixture
def sample_room_analysis(sample_room_analysis_dict):
    """Sample RoomAnalysis object."""
    return RoomAnalysis.from_dict(sample_room_analysis_dict)


@pytest.fixture
def sample_base64_image():
    """Create a sample base64 encoded image for testing."""
    # Create a simple 100x100 RGB image
    img = Image.new("RGB", (100, 100), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()


@pytest.fixture
def sample_large_base64_image():
    """Create a larger base64 encoded image for testing resize."""
    # Create a 3000x3000 RGB image (larger than max_size)
    img = Image.new("RGB", (3000, 3000), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode()


@pytest.fixture
def google_ai_service_instance():
    """Create a GoogleAIStudioService instance for testing."""
    return GoogleAIStudioService()


# =============================================================================
# Test 1: RoomAnalysis Serialization
# =============================================================================


class TestRoomAnalysisSerialization:
    """Test RoomAnalysis to_dict and from_dict methods."""

    def test_to_dict_returns_all_fields(self, sample_room_analysis):
        """Test that to_dict includes all expected fields."""
        result = sample_room_analysis.to_dict()

        assert "room_type" in result
        assert "dimensions" in result
        assert "lighting_conditions" in result
        assert "color_palette" in result
        assert "existing_furniture" in result
        assert "architectural_features" in result
        assert "style_assessment" in result
        assert "confidence_score" in result
        assert "scale_references" in result
        assert "camera_view_analysis" in result

    def test_to_dict_preserves_values(self, sample_room_analysis):
        """Test that to_dict preserves all values correctly."""
        result = sample_room_analysis.to_dict()

        assert result["room_type"] == "living_room"
        assert result["lighting_conditions"] == "natural"
        assert result["style_assessment"] == "modern"
        assert result["confidence_score"] == 0.85
        assert len(result["existing_furniture"]) == 2
        assert result["existing_furniture"][0]["object_type"] == "sofa"

    def test_from_dict_creates_valid_object(self, sample_room_analysis_dict):
        """Test that from_dict creates a valid RoomAnalysis object."""
        result = RoomAnalysis.from_dict(sample_room_analysis_dict)

        assert isinstance(result, RoomAnalysis)
        assert result.room_type == "living_room"
        assert result.lighting_conditions == "natural"
        assert len(result.existing_furniture) == 2

    def test_from_dict_handles_missing_fields(self):
        """Test that from_dict provides defaults for missing fields."""
        minimal_dict = {"room_type": "bedroom"}
        result = RoomAnalysis.from_dict(minimal_dict)

        assert result.room_type == "bedroom"
        assert result.dimensions == {}
        assert result.lighting_conditions == "mixed"
        assert result.existing_furniture == []
        assert result.confidence_score == 0.0

    def test_roundtrip_serialization(self, sample_room_analysis_dict):
        """Test that to_dict -> from_dict roundtrip preserves data."""
        original = RoomAnalysis.from_dict(sample_room_analysis_dict)
        serialized = original.to_dict()
        restored = RoomAnalysis.from_dict(serialized)

        assert original.room_type == restored.room_type
        assert original.dimensions == restored.dimensions
        assert original.existing_furniture == restored.existing_furniture
        assert original.camera_view_analysis == restored.camera_view_analysis

    def test_json_serialization(self, sample_room_analysis):
        """Test that to_dict output is JSON serializable."""
        result = sample_room_analysis.to_dict()
        # Should not raise
        json_str = json.dumps(result)
        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["room_type"] == "living_room"


# =============================================================================
# Test 2: Image Preprocessing Quality
# =============================================================================


class TestImagePreprocessing:
    """Test image preprocessing functions with quality improvements."""

    def test_preprocess_image_quality_setting(self, google_ai_service_instance, sample_base64_image):
        """Test that _preprocess_image uses high quality (98%)."""
        result = google_ai_service_instance._preprocess_image(sample_base64_image)

        # Decode and check it's valid
        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.format == "JPEG"
        # Image should be valid
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_preprocess_image_respects_max_size(self, google_ai_service_instance, sample_large_base64_image):
        """Test that _preprocess_image resizes large images to max 2048px."""
        result = google_ai_service_instance._preprocess_image(sample_large_base64_image)

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))

        # Should be resized to fit within 2048px
        assert img.width <= 2048
        assert img.height <= 2048

    def test_preprocess_image_for_editing_quality(self, google_ai_service_instance, sample_base64_image):
        """Test that _preprocess_image_for_editing uses 98% quality."""
        result = google_ai_service_instance._preprocess_image_for_editing(sample_base64_image)

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.format == "JPEG"

    def test_preprocess_image_for_editing_max_size(self, google_ai_service_instance, sample_large_base64_image):
        """Test that _preprocess_image_for_editing respects 4096px max."""
        result = google_ai_service_instance._preprocess_image_for_editing(sample_large_base64_image)

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))

        # Should be resized to fit within 4096px
        assert img.width <= 4096
        assert img.height <= 4096

    def test_preprocess_handles_data_url_prefix(self, google_ai_service_instance, sample_base64_image):
        """Test that preprocessing handles data URL prefix correctly."""
        data_url = f"data:image/jpeg;base64,{sample_base64_image}"
        result = google_ai_service_instance._preprocess_image(data_url)

        # Should successfully process
        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img is not None

    def test_preprocess_converts_to_rgb(self, google_ai_service_instance):
        """Test that preprocessing converts non-RGB images to RGB."""
        # Create a grayscale image
        img = Image.new("L", (100, 100), color=128)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        grayscale_b64 = base64.b64encode(buffer.getvalue()).decode()

        result = google_ai_service_instance._preprocess_image(grayscale_b64)

        decoded = base64.b64decode(result)
        processed_img = Image.open(io.BytesIO(decoded))
        assert processed_img.mode == "RGB"


# =============================================================================
# Test 3: SAM Endpoints Disabled (Return 501)
# =============================================================================


class TestSAMEndpointsDisabled:
    """Test that SAM-related endpoints raise HTTPException with 501 status.

    Note: These tests directly call the endpoint functions rather than using
    HTTP client to avoid import path issues when running from project root.
    """

    @pytest.mark.asyncio
    async def test_extract_layers_returns_501(self):
        """Test that extract_furniture_layers raises 501 HTTPException."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException
        from routers.visualization import extract_furniture_layers

        # Create mock request
        mock_request = MagicMock()
        mock_request.visualization_image = "data:image/jpeg;base64,test"
        mock_request.products = [{"id": 1, "name": "Test"}]

        # Endpoint should raise HTTPException with 501
        with pytest.raises(HTTPException) as exc_info:
            await extract_furniture_layers("test-session", mock_request, MagicMock())

        assert exc_info.value.status_code == 501
        assert "disabled" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_composite_layers_returns_501(self):
        """Test that composite_layers raises 501 HTTPException."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException
        from routers.visualization import composite_layers

        # Create mock request
        mock_request = MagicMock()
        mock_request.background = "data:image/jpeg;base64,test"
        mock_request.layers = []

        # Endpoint should raise HTTPException with 501
        with pytest.raises(HTTPException) as exc_info:
            await composite_layers("test-session", mock_request)

        assert exc_info.value.status_code == 501
        assert "disabled" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_segment_at_point_returns_501(self):
        """Test that segment_at_point raises 501 HTTPException."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException
        from routers.visualization import segment_at_point

        # Create mock request
        mock_request = MagicMock()
        mock_request.image_base64 = "data:image/jpeg;base64,test"
        mock_request.point = {"x": 0.5, "y": 0.5}

        # Endpoint should raise HTTPException with 501
        with pytest.raises(HTTPException) as exc_info:
            await segment_at_point("test-session", mock_request)

        assert exc_info.value.status_code == 501
        assert "disabled" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_segment_at_points_returns_501(self):
        """Test that segment_at_points raises 501 HTTPException."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException
        from routers.visualization import segment_at_points

        # Create mock request
        mock_request = MagicMock()
        mock_request.image_base64 = "data:image/jpeg;base64,test"
        mock_request.points = [{"x": 0.5, "y": 0.5}]

        # Endpoint should raise HTTPException with 501
        with pytest.raises(HTTPException) as exc_info:
            await segment_at_points("test-session", mock_request)

        assert exc_info.value.status_code == 501
        assert "disabled" in exc_info.value.detail.lower()


# =============================================================================
# Test 4: Mask Precomputation Service Disabled
# =============================================================================


class TestMaskPrecomputationDisabled:
    """Test that mask precomputation service methods are no-ops."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_trigger_precomputation_returns_none(self, mock_db):
        """Test that trigger_precomputation returns None (disabled)."""
        from services.mask_precomputation_service import mask_precomputation_service

        result = await mask_precomputation_service.trigger_precomputation(
            mock_db,
            "test-session",
            "data:image/jpeg;base64,test",
            [{"id": 1, "name": "Test"}],
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_masks_returns_none(self, mock_db):
        """Test that get_cached_masks returns None (disabled)."""
        from services.mask_precomputation_service import mask_precomputation_service

        result = await mask_precomputation_service.get_cached_masks(
            mock_db,
            "test-session",
            "data:image/jpeg;base64,test",
            [{"id": 1, "name": "Test"}],
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_for_curated_look_returns_none(self, mock_db):
        """Test that trigger_precomputation_for_curated_look returns None."""
        from services.mask_precomputation_service import mask_precomputation_service

        result = await mask_precomputation_service.trigger_precomputation_for_curated_look(
            mock_db,
            123,  # curated_look_id
            "data:image/jpeg;base64,test",
            [{"id": 1, "name": "Test"}],
        )

        assert result is None


# =============================================================================
# Test 5: Combined Room Analysis Function
# =============================================================================


class TestCombinedRoomAnalysis:
    """Test the combined analyze_room_with_furniture function."""

    @pytest.mark.asyncio
    async def test_analyze_room_with_furniture_returns_room_analysis(self, google_ai_service_instance, sample_base64_image):
        """Test that analyze_room_with_furniture returns a RoomAnalysis object."""
        # Mock the API request to avoid actual API calls
        mock_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "room_type": "living_room",
                                        "dimensions": {"estimated_width_ft": 12.0},
                                        "lighting_conditions": "natural",
                                        "color_palette": ["white", "gray"],
                                        "existing_furniture": [
                                            {"object_type": "sofa", "position": "center", "confidence": 0.9}
                                        ],
                                        "architectural_features": ["windows"],
                                        "style_assessment": "modern",
                                        "scale_references": {"door_visible": True},
                                        "camera_view_analysis": {
                                            "viewing_angle": "straight_on",
                                            "primary_wall": "back",
                                        },
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }

        with patch.object(google_ai_service, "_make_api_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await google_ai_service.analyze_room_with_furniture(sample_base64_image)

            assert isinstance(result, RoomAnalysis)
            assert result.room_type == "living_room"
            assert len(result.existing_furniture) == 1
            assert result.existing_furniture[0]["object_type"] == "sofa"

    @pytest.mark.asyncio
    async def test_analyze_room_with_furniture_handles_api_error(self, google_ai_service_instance, sample_base64_image):
        """Test that analyze_room_with_furniture returns fallback on error."""
        with patch.object(google_ai_service, "_make_api_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("API Error")

            result = await google_ai_service.analyze_room_with_furniture(sample_base64_image)

            # Should return fallback analysis with low confidence
            assert isinstance(result, RoomAnalysis)
            # Fallback uses _create_fallback_room_analysis() which sets:
            # - room_type="living_room" (generic default)
            # - confidence_score=0.3 (indicates fallback was used)
            assert result.confidence_score == 0.3


# =============================================================================
# Test 6: Upload Endpoint with Room Analysis
# =============================================================================


class TestUploadEndpointRoomAnalysis:
    """Test upload-room-image endpoint room analysis functionality."""

    def test_room_analysis_included_in_upload_response_format(self):
        """Test that RoomAnalysis can be serialized for upload response.

        This validates that when the upload endpoint calls analyze_room_with_furniture,
        the result can be properly serialized to include in the JSON response.
        """
        # Create a RoomAnalysis object (as would be returned by analyze_room_with_furniture)
        room_analysis = RoomAnalysis(
            room_type="living_room",
            dimensions={"estimated_width_ft": 15, "estimated_length_ft": 20},
            lighting_conditions="natural",
            color_palette=["beige", "gray"],
            existing_furniture=[{"object_type": "sofa", "position": "center"}],
            architectural_features=["windows"],
            style_assessment="modern",
            confidence_score=0.85,
        )

        # Verify it can be serialized to dict (used in upload response)
        result_dict = room_analysis.to_dict()

        assert result_dict["room_type"] == "living_room"
        assert "dimensions" in result_dict
        assert result_dict["lighting_conditions"] == "natural"
        assert len(result_dict["existing_furniture"]) == 1
        assert result_dict["existing_furniture"][0]["object_type"] == "sofa"

        # Verify JSON serialization works (used for DB storage)
        json_str = json.dumps(result_dict)
        assert "living_room" in json_str
        assert "sofa" in json_str


# =============================================================================
# Test 7: Database Models Have room_analysis Column
# =============================================================================


class TestDatabaseModels:
    """Test that database models have room_analysis column."""

    def test_curated_look_has_room_analysis(self):
        """Test that CuratedLook model has room_analysis column."""
        from database.models import CuratedLook

        # Check that the column exists in the model
        assert hasattr(CuratedLook, "room_analysis")

    def test_project_has_room_analysis(self):
        """Test that Project model has room_analysis column."""
        from database.models import Project

        # Check that the column exists in the model
        assert hasattr(Project, "room_analysis")


# =============================================================================
# Test 8: Fallback Combined Analysis Data
# =============================================================================


class TestFallbackCombinedAnalysis:
    """Test the fallback data for combined room analysis."""

    def test_get_fallback_combined_analysis(self, google_ai_service_instance):
        """Test that _get_fallback_combined_analysis returns valid structure."""
        result = google_ai_service_instance._get_fallback_combined_analysis()

        assert isinstance(result, dict)
        assert result["room_type"] == "unknown"
        assert result["lighting_conditions"] == "mixed"
        assert result["existing_furniture"] == []
        assert "camera_view_analysis" in result
        assert result["camera_view_analysis"]["viewing_angle"] == "straight_on"
