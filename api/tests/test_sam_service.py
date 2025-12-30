"""
Tests for SAM (Segment Anything Model) Service.

Tests the automatic object segmentation functionality used in Magic Grab editing.
"""
import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image
from services.sam_service import SAMService, SegmentationResult, SegmentedObject

# Test fixtures


@pytest.fixture
def sample_image_base64():
    """Create a sample base64 encoded test image."""
    # Create a simple 100x100 RGB image with some shapes
    img = Image.new("RGB", (100, 100), color="white")

    # Draw a simple rectangle (simulating furniture)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 60, 60], fill="brown")  # Furniture-like object
    draw.rectangle([70, 40, 90, 80], fill="green")  # Another object

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()


@pytest.fixture
def sample_image_with_data_uri(sample_image_base64):
    """Create a sample image with data URI prefix."""
    return f"data:image/jpeg;base64,{sample_image_base64}"


@pytest.fixture
def mock_replicate_output():
    """Mock output from Replicate SAM API."""
    # Create a simple binary mask
    mask_img = Image.new("L", (100, 100), color=0)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(mask_img)
    draw.rectangle([20, 20, 60, 60], fill=255)

    buffer = io.BytesIO()
    mask_img.save(buffer, format="PNG")
    buffer.seek(0)
    mask_b64 = base64.b64encode(buffer.getvalue()).decode()

    return [{"mask": mask_b64, "bbox": [20, 20, 40, 40], "area": 1600, "stability_score": 0.95}]


@pytest.fixture
def sam_service():
    """Create SAM service instance with mocked API key."""
    with patch.object(SAMService, "_validate_api_key"):
        service = SAMService()
        service.api_key = "test_api_key"
        return service


# Unit tests


class TestSAMServiceInit:
    """Tests for SAM service initialization."""

    def test_init_with_api_key(self):
        """Test service initializes correctly with API key."""
        with patch("services.sam_service.settings") as mock_settings:
            mock_settings.replicate_api_key = "test_key"
            service = SAMService()
            assert service.api_key == "test_key"

    def test_init_without_api_key(self):
        """Test service handles missing API key gracefully."""
        with patch("services.sam_service.settings") as mock_settings:
            mock_settings.replicate_api_key = ""
            service = SAMService()
            assert service.api_key == ""

    def test_usage_stats_initialized(self, sam_service):
        """Test usage stats are properly initialized."""
        stats = sam_service.get_usage_stats()
        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0


class TestImagePreparation:
    """Tests for image preprocessing."""

    def test_prepare_image_with_base64(self, sam_service, sample_image_base64):
        """Test image preparation with raw base64."""
        image_data, pil_image = sam_service._prepare_image(sample_image_base64)

        assert isinstance(pil_image, Image.Image)
        assert pil_image.mode == "RGB"
        assert pil_image.size == (100, 100)

    def test_prepare_image_with_data_uri(self, sam_service, sample_image_with_data_uri):
        """Test image preparation with data URI prefix."""
        image_data, pil_image = sam_service._prepare_image(sample_image_with_data_uri)

        assert isinstance(pil_image, Image.Image)
        assert pil_image.mode == "RGB"

    def test_prepare_image_converts_rgba_to_rgb(self, sam_service):
        """Test that RGBA images are converted to RGB."""
        # Create RGBA image
        img = Image.new("RGBA", (50, 50), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        b64 = base64.b64encode(buffer.getvalue()).decode()

        _, pil_image = sam_service._prepare_image(b64)
        assert pil_image.mode == "RGB"


class TestCutoutCreation:
    """Tests for object cutout creation."""

    def test_create_cutout_with_mask(self, sam_service, sample_image_base64):
        """Test cutout creation with valid mask."""
        _, pil_image = sam_service._prepare_image(sample_image_base64)

        # Create a simple mask
        mask_img = Image.new("L", (100, 100), color=0)
        from PIL import ImageDraw

        draw = ImageDraw.Draw(mask_img)
        draw.rectangle([20, 20, 60, 60], fill=255)

        buffer = io.BytesIO()
        mask_img.save(buffer, format="PNG")
        buffer.seek(0)
        mask_b64 = base64.b64encode(buffer.getvalue()).decode()

        mask_data = {"segmentation": mask_b64, "bbox": [20, 20, 40, 40], "area": 1600, "stability_score": 0.9}

        cutout_b64, mask_out_b64, bbox = sam_service._create_cutout(pil_image, mask_data, 100, 100)

        # Verify cutout is valid base64 PNG
        assert cutout_b64.startswith("data:image/png;base64,")

        # Verify bbox is normalized
        assert 0 <= bbox["x"] <= 1
        assert 0 <= bbox["y"] <= 1
        assert 0 < bbox["width"] <= 1
        assert 0 < bbox["height"] <= 1

    def test_create_cutout_from_bbox_only(self, sam_service, sample_image_base64):
        """Test cutout creation when only bbox is provided (no mask)."""
        _, pil_image = sam_service._prepare_image(sample_image_base64)

        mask_data = {"segmentation": "", "bbox": [20, 20, 40, 40], "area": 1600, "stability_score": 0.9}  # No mask

        cutout_b64, _, bbox = sam_service._create_cutout(pil_image, mask_data, 100, 100)

        # Should still produce a valid cutout
        assert cutout_b64.startswith("data:image/png;base64,")


class TestSegmentation:
    """Tests for the main segmentation functionality."""

    @pytest.mark.asyncio
    async def test_segment_all_objects_success(self, sam_service, sample_image_base64, mock_replicate_output):
        """Test successful object segmentation."""
        with patch.object(sam_service, "_call_sam_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_replicate_output

            result = await sam_service.segment_all_objects(
                sample_image_base64, min_area_percent=0.1, max_objects=10, stability_threshold=0.5
            )

            assert isinstance(result, SegmentationResult)
            assert len(result.objects) > 0
            assert result.processing_time >= 0
            assert result.image_dimensions["width"] == 100
            assert result.image_dimensions["height"] == 100

    @pytest.mark.asyncio
    async def test_segment_all_objects_filters_small(self, sam_service, sample_image_base64, mock_replicate_output):
        """Test that small objects are filtered out."""
        with patch.object(sam_service, "_call_sam_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_replicate_output

            # Set very high min area to filter everything
            result = await sam_service.segment_all_objects(
                sample_image_base64, min_area_percent=50, max_objects=10, stability_threshold=0.5  # 50% of image - too high
            )

            # All objects should be filtered
            assert len(result.objects) == 0

    @pytest.mark.asyncio
    async def test_segment_all_objects_respects_max(self, sam_service, sample_image_base64):
        """Test that max_objects limit is respected."""
        # Create multiple mask outputs
        multi_output = []
        for i in range(5):
            mask_img = Image.new("L", (100, 100), color=0)
            from PIL import ImageDraw

            draw = ImageDraw.Draw(mask_img)
            draw.rectangle([10 + i * 15, 10, 20 + i * 15, 30], fill=255)

            buffer = io.BytesIO()
            mask_img.save(buffer, format="PNG")
            buffer.seek(0)
            mask_b64 = base64.b64encode(buffer.getvalue()).decode()

            multi_output.append({"mask": mask_b64, "bbox": [10 + i * 15, 10, 10, 20], "area": 200, "stability_score": 0.9})

        with patch.object(sam_service, "_call_sam_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = multi_output

            result = await sam_service.segment_all_objects(
                sample_image_base64, min_area_percent=0.01, max_objects=2, stability_threshold=0.5  # Only want 2
            )

            assert len(result.objects) <= 2

    @pytest.mark.asyncio
    async def test_segment_all_objects_updates_stats(self, sam_service, sample_image_base64, mock_replicate_output):
        """Test that usage stats are updated after segmentation."""
        with patch.object(sam_service, "_call_sam_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_replicate_output

            initial_stats = sam_service.get_usage_stats()

            await sam_service.segment_all_objects(sample_image_base64)

            final_stats = sam_service.get_usage_stats()
            assert final_stats["total_requests"] == initial_stats["total_requests"] + 1
            assert final_stats["successful_requests"] == initial_stats["successful_requests"] + 1

    @pytest.mark.asyncio
    async def test_segment_all_objects_handles_api_error(self, sam_service, sample_image_base64):
        """Test error handling when API fails."""
        with patch.object(sam_service, "_call_sam_api", new_callable=AsyncMock) as mock_api:
            mock_api.side_effect = Exception("API Error")

            with pytest.raises(Exception):
                await sam_service.segment_all_objects(sample_image_base64)

            stats = sam_service.get_usage_stats()
            assert stats["failed_requests"] > 0


class TestPointBasedSegmentation:
    """Tests for point-based segmentation (user click)."""

    @pytest.mark.asyncio
    async def test_segment_with_points(self, sam_service, sample_image_base64, mock_replicate_output):
        """Test segmentation with point prompts."""
        with patch.object(sam_service, "_call_sam_with_points", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = mock_replicate_output

            points = [{"x": 0.4, "y": 0.4, "label": 1}]  # Click on center

            result = await sam_service.segment_with_points(sample_image_base64, points)

            assert isinstance(result, SegmentationResult)
            mock_api.assert_called_once()


class TestSegmentedObject:
    """Tests for SegmentedObject dataclass."""

    def test_segmented_object_creation(self):
        """Test SegmentedObject can be created with all fields."""
        obj = SegmentedObject(
            id="obj_1",
            label="sofa",
            cutout="base64data",
            mask="maskdata",
            bbox={"x": 0.2, "y": 0.3, "width": 0.4, "height": 0.3},
            center={"x": 0.4, "y": 0.45},
            area=0.12,
            stability_score=0.95,
        )

        assert obj.id == "obj_1"
        assert obj.label == "sofa"
        assert obj.stability_score == 0.95

    def test_segmented_object_optional_label(self):
        """Test SegmentedObject works with None label."""
        obj = SegmentedObject(
            id="obj_1",
            label=None,
            cutout="base64data",
            mask="maskdata",
            bbox={"x": 0.2, "y": 0.3, "width": 0.4, "height": 0.3},
            center={"x": 0.4, "y": 0.45},
            area=0.12,
            stability_score=0.95,
        )

        assert obj.label is None


# Integration tests (would need real API key)


class TestSAMIntegration:
    """Integration tests - skipped unless REPLICATE_API_KEY is set."""

    @pytest.mark.skip(reason="Requires real Replicate API key")
    @pytest.mark.asyncio
    async def test_real_segmentation(self, sample_image_base64):
        """Test real SAM API call (requires API key)."""
        service = SAMService()
        result = await service.segment_all_objects(sample_image_base64)

        assert isinstance(result, SegmentationResult)
        assert result.processing_time > 0
