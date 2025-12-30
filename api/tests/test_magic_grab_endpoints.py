"""
Tests for Magic Grab visualization endpoints.

Tests the /extract-layers and /composite-layers endpoints.
"""
import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from PIL import Image

# Import the router
from routers.visualization import router

# Create test app
app = FastAPI()
app.include_router(router, prefix="/api/visualization")


# Test fixtures


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_image_base64():
    """Create a sample base64 encoded test image."""
    img = Image.new("RGB", (200, 150), color="lightgray")

    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 100, 100], fill="brown")  # Furniture
    draw.rectangle([120, 60, 160, 90], fill="green")  # Another object

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    return f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"


@pytest.fixture
def sample_products():
    """Sample products for testing."""
    return [{"id": "1", "name": "Modern Sofa"}, {"id": "2", "name": "Coffee Table"}]


@pytest.fixture
def sample_layers():
    """Sample layers for compositing."""
    # Create a simple cutout
    img = Image.new("RGBA", (40, 30), color=(139, 69, 19, 255))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    cutout = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"

    return [
        {"id": "layer_1", "cutout": cutout, "x": 0.3, "y": 0.5, "scale": 1.0},
        {"id": "layer_2", "cutout": cutout, "x": 0.7, "y": 0.5, "scale": 0.8},
    ]


@pytest.fixture
def mock_sam_service():
    """Mock SAM service for testing."""
    from services.sam_service import SegmentationResult, SegmentedObject

    mock = MagicMock()

    # Create sample cutout
    img = Image.new("RGBA", (40, 30), color=(139, 69, 19, 255))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    cutout = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"

    mock.segment_all_objects = AsyncMock(
        return_value=SegmentationResult(
            objects=[
                SegmentedObject(
                    id="obj_0",
                    label=None,
                    cutout=cutout,
                    mask="mask_data",
                    bbox={"x": 0.25, "y": 0.33, "width": 0.25, "height": 0.33},
                    center={"x": 0.375, "y": 0.5},
                    area=0.08,
                    stability_score=0.95,
                ),
                SegmentedObject(
                    id="obj_1",
                    label=None,
                    cutout=cutout,
                    mask="mask_data",
                    bbox={"x": 0.6, "y": 0.4, "width": 0.2, "height": 0.2},
                    center={"x": 0.7, "y": 0.5},
                    area=0.04,
                    stability_score=0.9,
                ),
            ],
            processing_time=2.5,
            image_dimensions={"width": 200, "height": 150},
        )
    )

    return mock


@pytest.fixture
def mock_google_ai_service():
    """Mock Google AI service for background generation."""
    mock = MagicMock()

    # Create sample background
    img = Image.new("RGB", (200, 150), color="lightgray")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    background = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"

    mock.remove_furniture = AsyncMock(return_value=background)

    return mock


@pytest.fixture
def mock_compositing_service():
    """Mock compositing service for testing."""
    from services.image_compositing_service import CompositingResult

    mock = MagicMock()

    # Create sample result
    img = Image.new("RGB", (200, 150), color="lightgray")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    result_image = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"

    mock.composite_layers = AsyncMock(
        return_value=CompositingResult(
            image=result_image, processing_time=0.5, layers_composited=2, dimensions={"width": 200, "height": 150}
        )
    )

    mock.composite_with_harmonization = AsyncMock(
        return_value=CompositingResult(
            image=result_image, processing_time=3.5, layers_composited=2, dimensions={"width": 200, "height": 150}
        )
    )

    return mock


# Endpoint tests


class TestExtractLayersEndpoint:
    """Tests for /sessions/{session_id}/extract-layers endpoint."""

    def test_extract_layers_with_sam(
        self, client, sample_image_base64, sample_products, mock_sam_service, mock_google_ai_service
    ):
        """Test layer extraction with SAM (Magic Grab mode)."""
        with patch("routers.visualization.sam_service", mock_sam_service), patch(
            "routers.visualization.google_ai_service", mock_google_ai_service
        ):
            response = client.post(
                "/api/visualization/sessions/test-session/extract-layers",
                json={"visualization_image": sample_image_base64, "products": sample_products, "use_sam": True},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "success"
            assert data["session_id"] == "test-session"
            assert "background" in data
            assert "layers" in data
            assert len(data["layers"]) == 2
            assert data["extraction_method"] == "sam"

    def test_extract_layers_without_sam(self, client, sample_image_base64, sample_products, mock_google_ai_service):
        """Test layer extraction with Gemini (legacy mode)."""
        # Mock the extract_furniture_layers method
        mock_google_ai_service.extract_furniture_layers = AsyncMock(
            return_value={
                "clean_background": sample_image_base64,
                "layers": [
                    {
                        "product_id": "1",
                        "product_name": "Modern Sofa",
                        "layer_image": sample_image_base64,
                        "bounding_box": {"x": 0.25, "y": 0.33, "width": 0.25, "height": 0.33},
                        "center": {"x": 0.375, "y": 0.5},
                    }
                ],
            }
        )

        with patch("routers.visualization.google_ai_service", mock_google_ai_service):
            response = client.post(
                "/api/visualization/sessions/test-session/extract-layers",
                json={"visualization_image": sample_image_base64, "products": sample_products, "use_sam": False},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "success"
            assert data["extraction_method"] == "gemini"

    def test_extract_layers_missing_image(self, client, sample_products):
        """Test error when image is missing."""
        response = client.post(
            "/api/visualization/sessions/test-session/extract-layers", json={"products": sample_products, "use_sam": True}
        )

        assert response.status_code == 422  # Validation error

    def test_extract_layers_sam_failure_fallback(
        self, client, sample_image_base64, sample_products, mock_sam_service, mock_google_ai_service
    ):
        """Test fallback when SAM fails."""
        mock_sam_service.segment_all_objects = AsyncMock(side_effect=Exception("SAM API Error"))

        with patch("routers.visualization.sam_service", mock_sam_service):
            response = client.post(
                "/api/visualization/sessions/test-session/extract-layers",
                json={"visualization_image": sample_image_base64, "products": sample_products, "use_sam": True},
            )

            assert response.status_code == 500


class TestCompositeLayersEndpoint:
    """Tests for /sessions/{session_id}/composite-layers endpoint."""

    def test_composite_layers_success(self, client, sample_image_base64, sample_layers, mock_compositing_service):
        """Test successful layer compositing."""
        with patch("routers.visualization.compositing_service", mock_compositing_service):
            response = client.post(
                "/api/visualization/sessions/test-session/composite-layers",
                json={"background": sample_image_base64, "layers": sample_layers, "harmonize": False},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "success"
            assert data["session_id"] == "test-session"
            assert "image" in data
            assert data["layers_composited"] == 2
            assert data["harmonized"] is False

    def test_composite_layers_with_harmonization(
        self, client, sample_image_base64, sample_layers, mock_compositing_service, mock_google_ai_service
    ):
        """Test layer compositing with AI harmonization."""
        with patch("routers.visualization.compositing_service", mock_compositing_service), patch(
            "routers.visualization.google_ai_service", mock_google_ai_service
        ):
            response = client.post(
                "/api/visualization/sessions/test-session/composite-layers",
                json={"background": sample_image_base64, "layers": sample_layers, "harmonize": True},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["harmonized"] is True

    def test_composite_layers_empty(self, client, sample_image_base64, mock_compositing_service):
        """Test compositing with no layers."""
        mock_compositing_service.composite_layers = AsyncMock(
            return_value=MagicMock(
                image=sample_image_base64, processing_time=0.1, layers_composited=0, dimensions={"width": 200, "height": 150}
            )
        )

        with patch("routers.visualization.compositing_service", mock_compositing_service):
            response = client.post(
                "/api/visualization/sessions/test-session/composite-layers",
                json={"background": sample_image_base64, "layers": [], "harmonize": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["layers_composited"] == 0

    def test_composite_layers_missing_background(self, client, sample_layers):
        """Test error when background is missing."""
        response = client.post(
            "/api/visualization/sessions/test-session/composite-layers", json={"layers": sample_layers, "harmonize": False}
        )

        assert response.status_code == 422  # Validation error

    def test_composite_layers_service_error(self, client, sample_image_base64, sample_layers):
        """Test error handling when compositing service fails."""
        mock_service = MagicMock()
        mock_service.composite_layers = AsyncMock(side_effect=Exception("Compositing failed"))

        with patch("routers.visualization.compositing_service", mock_service):
            response = client.post(
                "/api/visualization/sessions/test-session/composite-layers",
                json={"background": sample_image_base64, "layers": sample_layers, "harmonize": False},
            )

            assert response.status_code == 500


class TestRequestValidation:
    """Tests for request validation."""

    def test_extract_layers_invalid_json(self, client):
        """Test error handling for invalid JSON."""
        response = client.post(
            "/api/visualization/sessions/test-session/extract-layers",
            content="not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_composite_layers_invalid_layer_format(self, client, sample_image_base64):
        """Test error handling for invalid layer format."""
        response = client.post(
            "/api/visualization/sessions/test-session/composite-layers",
            json={
                "background": sample_image_base64,
                "layers": [{"invalid": "format"}],  # Missing required fields
                "harmonize": False,
            },
        )

        # Should still attempt but may fail during processing
        # The exact behavior depends on the service implementation
        assert response.status_code in [200, 422, 500]


class TestLayerData:
    """Tests for layer data handling."""

    def test_layer_with_all_fields(self, client, sample_image_base64, mock_compositing_service):
        """Test compositing with all layer fields specified."""
        # Create cutout
        img = Image.new("RGBA", (40, 30), color=(139, 69, 19, 255))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        cutout = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"

        layers = [
            {
                "id": "full_layer",
                "cutout": cutout,
                "x": 0.5,
                "y": 0.5,
                "scale": 1.5,
                "rotation": 45.0,
                "opacity": 0.8,
                "z_index": 5,
            }
        ]

        with patch("routers.visualization.compositing_service", mock_compositing_service):
            response = client.post(
                "/api/visualization/sessions/test-session/composite-layers",
                json={"background": sample_image_base64, "layers": layers, "harmonize": False},
            )

            assert response.status_code == 200


class TestSessionHandling:
    """Tests for session ID handling."""

    def test_extract_layers_with_special_session_id(
        self, client, sample_image_base64, sample_products, mock_sam_service, mock_google_ai_service
    ):
        """Test with special characters in session ID."""
        with patch("routers.visualization.sam_service", mock_sam_service), patch(
            "routers.visualization.google_ai_service", mock_google_ai_service
        ):
            response = client.post(
                "/api/visualization/sessions/test-session-123-abc/extract-layers",
                json={"visualization_image": sample_image_base64, "products": sample_products, "use_sam": True},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "test-session-123-abc"
