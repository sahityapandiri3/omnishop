"""
Tests for Image Compositing Service.

Tests the layer compositing functionality used in Magic Grab finalization.
"""
import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image
from services.image_compositing_service import CompositingResult, ImageCompositingService, Layer, compositing_service

# Test fixtures


@pytest.fixture
def sample_background_base64():
    """Create a sample background image (clean room)."""
    img = Image.new("RGB", (200, 150), color="lightgray")

    # Add some room details
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 120, 200, 150], fill="brown")  # Floor
    draw.rectangle([0, 0, 200, 20], fill="beige")  # Ceiling

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    return f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"


@pytest.fixture
def sample_layer_cutout():
    """Create a sample furniture layer with transparency."""
    img = Image.new("RGBA", (40, 30), color=(0, 0, 0, 0))  # Transparent

    # Draw a simple furniture shape
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.rectangle([5, 5, 35, 25], fill=(139, 69, 19, 255))  # Brown furniture

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"


@pytest.fixture
def sample_layer(sample_layer_cutout):
    """Create a sample Layer object."""
    return Layer(
        id="layer_1", cutout=sample_layer_cutout, x=0.5, y=0.5, scale=1.0, rotation=0.0, opacity=1.0, z_index=0  # Center
    )


@pytest.fixture
def multiple_layers(sample_layer_cutout):
    """Create multiple layer objects for testing."""
    return [
        Layer(id="layer_1", cutout=sample_layer_cutout, x=0.3, y=0.6, scale=1.0, rotation=0.0, opacity=1.0, z_index=0),
        Layer(id="layer_2", cutout=sample_layer_cutout, x=0.7, y=0.6, scale=0.8, rotation=0.0, opacity=1.0, z_index=1),
    ]


@pytest.fixture
def compositing_svc():
    """Create compositing service instance."""
    return ImageCompositingService()


# Unit tests


class TestLayerDataclass:
    """Tests for Layer dataclass."""

    def test_layer_creation(self, sample_layer_cutout):
        """Test Layer can be created with all fields."""
        layer = Layer(
            id="test_layer", cutout=sample_layer_cutout, x=0.5, y=0.5, scale=1.0, rotation=45.0, opacity=0.8, z_index=5
        )

        assert layer.id == "test_layer"
        assert layer.x == 0.5
        assert layer.y == 0.5
        assert layer.scale == 1.0
        assert layer.rotation == 45.0
        assert layer.opacity == 0.8
        assert layer.z_index == 5

    def test_layer_defaults(self, sample_layer_cutout):
        """Test Layer default values."""
        layer = Layer(id="test", cutout=sample_layer_cutout, x=0.5, y=0.5)

        assert layer.scale == 1.0
        assert layer.rotation == 0.0
        assert layer.opacity == 1.0
        assert layer.z_index == 0


class TestImageLoading:
    """Tests for image loading functionality."""

    def test_load_image_with_data_uri(self, compositing_svc, sample_background_base64):
        """Test loading image with data URI prefix."""
        img = compositing_svc._load_image(sample_background_base64)

        assert isinstance(img, Image.Image)
        assert img.size == (200, 150)

    def test_load_image_without_data_uri(self, compositing_svc):
        """Test loading image without data URI prefix."""
        # Create raw base64
        img = Image.new("RGB", (50, 50), color="red")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        buffer.seek(0)
        raw_b64 = base64.b64encode(buffer.getvalue()).decode()

        loaded = compositing_svc._load_image(raw_b64)
        assert isinstance(loaded, Image.Image)
        assert loaded.size == (50, 50)


class TestFeathering:
    """Tests for edge feathering."""

    def test_feather_edges(self, compositing_svc):
        """Test edge feathering creates smoother edges."""
        # Create image with hard edges
        img = Image.new("RGBA", (50, 50), color=(255, 0, 0, 255))

        feathered = compositing_svc._feather_edges(img, radius=3)

        assert isinstance(feathered, Image.Image)
        assert feathered.mode == "RGBA"
        assert feathered.size == (50, 50)

    def test_feather_edges_non_rgba(self, compositing_svc):
        """Test feathering returns RGB images unchanged."""
        img = Image.new("RGB", (50, 50), color="red")

        result = compositing_svc._feather_edges(img, radius=3)

        # Should return unchanged
        assert result.mode == "RGB"


class TestDropShadow:
    """Tests for drop shadow creation."""

    def test_create_drop_shadow(self, compositing_svc):
        """Test drop shadow is created correctly."""
        # Create image with transparency
        img = Image.new("RGBA", (50, 50), color=(0, 0, 0, 0))
        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)
        draw.ellipse([10, 10, 40, 40], fill=(255, 0, 0, 255))

        shadow = compositing_svc._create_drop_shadow(img)

        assert isinstance(shadow, Image.Image)
        assert shadow.mode == "RGBA"
        assert shadow.size == (50, 50)

    def test_drop_shadow_has_transparency(self, compositing_svc):
        """Test shadow has proper transparency."""
        # Create image with transparent center and opaque edges
        img = Image.new("RGBA", (50, 50), color=(0, 0, 0, 0))
        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)
        draw.ellipse([10, 10, 40, 40], fill=(255, 0, 0, 255))

        shadow = compositing_svc._create_drop_shadow(img, shadow_color=(0, 0, 0, 80), blur=5)

        # Shadow should have some opacity where the object is
        center_pixel = shadow.getpixel((25, 25))
        assert center_pixel[3] > 0  # Has some opacity

        # Edge of shadow should be more transparent due to blur
        edge_pixel = shadow.getpixel((5, 5))
        # Edge should be less opaque than center (due to blur)
        assert edge_pixel[3] <= center_pixel[3]


class TestCompositing:
    """Tests for main compositing functionality."""

    @pytest.mark.asyncio
    async def test_composite_single_layer(self, compositing_svc, sample_background_base64, sample_layer):
        """Test compositing a single layer onto background."""
        result = await compositing_svc.composite_layers(
            background=sample_background_base64, layers=[sample_layer], apply_shadows=True, feather_edges=True
        )

        assert isinstance(result, CompositingResult)
        assert result.image.startswith("data:image/jpeg;base64,")
        assert result.layers_composited == 1
        assert result.processing_time >= 0
        assert result.dimensions["width"] == 200
        assert result.dimensions["height"] == 150

    @pytest.mark.asyncio
    async def test_composite_multiple_layers(self, compositing_svc, sample_background_base64, multiple_layers):
        """Test compositing multiple layers."""
        result = await compositing_svc.composite_layers(background=sample_background_base64, layers=multiple_layers)

        assert result.layers_composited == 2

    @pytest.mark.asyncio
    async def test_composite_respects_z_index(self, compositing_svc, sample_background_base64, sample_layer_cutout):
        """Test that layers are composited in z_index order."""
        # Create two overlapping layers
        layer1 = Layer(id="bottom", cutout=sample_layer_cutout, x=0.5, y=0.5, scale=1.0, z_index=0)
        layer2 = Layer(id="top", cutout=sample_layer_cutout, x=0.5, y=0.5, scale=1.0, z_index=1)

        # Pass in reverse order - should still composite correctly
        result = await compositing_svc.composite_layers(
            background=sample_background_base64, layers=[layer2, layer1]  # Wrong order
        )

        # Should complete without error
        assert result.layers_composited == 2

    @pytest.mark.asyncio
    async def test_composite_with_scaling(self, compositing_svc, sample_background_base64, sample_layer_cutout):
        """Test layer scaling during compositing."""
        layer = Layer(id="scaled", cutout=sample_layer_cutout, x=0.5, y=0.5, scale=2.0)  # Double size

        result = await compositing_svc.composite_layers(background=sample_background_base64, layers=[layer])

        assert result.layers_composited == 1

    @pytest.mark.asyncio
    async def test_composite_with_rotation(self, compositing_svc, sample_background_base64, sample_layer_cutout):
        """Test layer rotation during compositing."""
        layer = Layer(id="rotated", cutout=sample_layer_cutout, x=0.5, y=0.5, rotation=45.0)

        result = await compositing_svc.composite_layers(background=sample_background_base64, layers=[layer])

        assert result.layers_composited == 1

    @pytest.mark.asyncio
    async def test_composite_with_opacity(self, compositing_svc, sample_background_base64, sample_layer_cutout):
        """Test layer opacity during compositing."""
        layer = Layer(id="transparent", cutout=sample_layer_cutout, x=0.5, y=0.5, opacity=0.5)

        result = await compositing_svc.composite_layers(background=sample_background_base64, layers=[layer])

        assert result.layers_composited == 1

    @pytest.mark.asyncio
    async def test_composite_without_shadows(self, compositing_svc, sample_background_base64, sample_layer):
        """Test compositing without drop shadows."""
        result = await compositing_svc.composite_layers(
            background=sample_background_base64, layers=[sample_layer], apply_shadows=False
        )

        assert result.layers_composited == 1

    @pytest.mark.asyncio
    async def test_composite_without_feathering(self, compositing_svc, sample_background_base64, sample_layer):
        """Test compositing without edge feathering."""
        result = await compositing_svc.composite_layers(
            background=sample_background_base64, layers=[sample_layer], feather_edges=False
        )

        assert result.layers_composited == 1

    @pytest.mark.asyncio
    async def test_composite_quality_setting(self, compositing_svc, sample_background_base64, sample_layer):
        """Test different output quality settings."""
        result_low = await compositing_svc.composite_layers(
            background=sample_background_base64, layers=[sample_layer], output_quality=30
        )

        result_high = await compositing_svc.composite_layers(
            background=sample_background_base64, layers=[sample_layer], output_quality=95
        )

        # Higher quality should produce larger file
        assert len(result_high.image) > len(result_low.image)

    @pytest.mark.asyncio
    async def test_composite_empty_layers(self, compositing_svc, sample_background_base64):
        """Test compositing with no layers."""
        result = await compositing_svc.composite_layers(background=sample_background_base64, layers=[])

        assert result.layers_composited == 0
        # Should still return the background
        assert result.image.startswith("data:image/jpeg;base64,")


class TestPreviewGeneration:
    """Tests for quick preview generation."""

    @pytest.mark.asyncio
    async def test_preview_layer_position(self, compositing_svc, sample_background_base64, sample_layer):
        """Test quick preview generation."""
        result = await compositing_svc.preview_layer_position(background=sample_background_base64, layer=sample_layer)

        assert result.startswith("data:image/jpeg;base64,")


class TestHarmonization:
    """Tests for harmonization with AI service."""

    @pytest.mark.asyncio
    async def test_composite_with_harmonization(self, compositing_svc, sample_background_base64, sample_layer):
        """Test compositing with optional harmonization."""
        mock_harmonize_service = MagicMock()
        mock_harmonize_service.harmonize_lighting = AsyncMock(return_value="data:image/jpeg;base64,harmonized_image_data")

        result = await compositing_svc.composite_with_harmonization(
            background=sample_background_base64, layers=[sample_layer], harmonize_service=mock_harmonize_service
        )

        assert result.layers_composited == 1
        mock_harmonize_service.harmonize_lighting.assert_called_once()

    @pytest.mark.asyncio
    async def test_composite_harmonization_failure_fallback(self, compositing_svc, sample_background_base64, sample_layer):
        """Test fallback when harmonization fails."""
        mock_harmonize_service = MagicMock()
        mock_harmonize_service.harmonize_lighting = AsyncMock(side_effect=Exception("Harmonization failed"))

        # Should not raise, should return raw composite
        result = await compositing_svc.composite_with_harmonization(
            background=sample_background_base64, layers=[sample_layer], harmonize_service=mock_harmonize_service
        )

        assert result.layers_composited == 1
        # Should still have valid image
        assert result.image.startswith("data:image/jpeg;base64,")


class TestCompositingResult:
    """Tests for CompositingResult dataclass."""

    def test_compositing_result_creation(self):
        """Test CompositingResult creation."""
        result = CompositingResult(
            image="data:image/jpeg;base64,test",
            processing_time=1.5,
            layers_composited=3,
            dimensions={"width": 800, "height": 600},
        )

        assert result.image == "data:image/jpeg;base64,test"
        assert result.processing_time == 1.5
        assert result.layers_composited == 3
        assert result.dimensions["width"] == 800


class TestGlobalServiceInstance:
    """Tests for global service instance."""

    def test_global_instance_exists(self):
        """Test that global compositing_service instance exists."""
        assert compositing_service is not None
        assert isinstance(compositing_service, ImageCompositingService)
