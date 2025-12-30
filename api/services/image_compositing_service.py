"""
Image Compositing Service for Magic Grab layer-based editing.

Composites multiple transparent PNG layers onto a background image
at specified positions. Pure Python/PIL implementation - no AI costs.

This is the final step in Magic Grab editing:
1. User drags objects on canvas (frontend)
2. Frontend sends new positions
3. This service composites all layers at new positions
4. Result is the edited visualization
"""
import asyncio
import base64
import io
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)


@dataclass
class Layer:
    """A single layer to composite."""

    id: str
    cutout: str  # Base64 PNG with transparency
    x: float  # Normalized position (0-1)
    y: float  # Normalized position (0-1)
    scale: float = 1.0  # Scale factor (1.0 = original size)
    rotation: float = 0.0  # Rotation in degrees
    opacity: float = 1.0  # Opacity (0-1)
    z_index: int = 0  # Stacking order (higher = on top)


@dataclass
class CompositingResult:
    """Result from layer compositing."""

    image: str  # Base64 encoded final image
    processing_time: float
    layers_composited: int
    dimensions: Dict[str, int]


class ImageCompositingService:
    """
    Service for compositing layers onto a background image.

    Features:
    - Position layers by normalized coordinates (0-1)
    - Scale and rotate layers
    - Apply drop shadows for realism
    - Blend layers with proper transparency
    - Optional edge feathering for seamless compositing
    """

    def __init__(self):
        """Initialize compositing service."""
        logger.info("Image Compositing Service initialized")

    async def composite_layers(
        self,
        background: str,
        layers: List[Layer],
        apply_shadows: bool = True,
        feather_edges: bool = True,
        output_quality: int = 95,
    ) -> CompositingResult:
        """
        Composite all layers onto the background at their positions.

        Args:
            background: Base64 encoded background image
            layers: List of Layer objects with positions
            apply_shadows: Add drop shadows under moved objects
            feather_edges: Feather layer edges for seamless blending
            output_quality: JPEG quality for output (1-100)

        Returns:
            CompositingResult with final composited image
        """
        start_time = time.time()

        try:
            # Load background
            bg_image = self._load_image(background)
            width, height = bg_image.size
            logger.info(f"[Composite] Background size: {width}x{height}")

            # Ensure RGBA mode
            if bg_image.mode != "RGBA":
                bg_image = bg_image.convert("RGBA")

            # Sort layers by z_index
            sorted_layers = sorted(layers, key=lambda l: l.z_index)

            # Composite each layer
            for layer in sorted_layers:
                try:
                    bg_image = await self._composite_single_layer(bg_image, layer, width, height, apply_shadows, feather_edges)
                except Exception as e:
                    logger.warning(f"[Composite] Failed to composite layer {layer.id}: {e}")
                    continue

            # Convert back to RGB for JPEG output
            final_image = bg_image.convert("RGB")

            # Encode result
            buffer = io.BytesIO()
            final_image.save(buffer, format="JPEG", quality=output_quality)
            buffer.seek(0)
            result_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"

            processing_time = time.time() - start_time
            logger.info(f"[Composite] Complete: {len(layers)} layers in {processing_time:.2f}s")

            return CompositingResult(
                image=result_b64,
                processing_time=processing_time,
                layers_composited=len(layers),
                dimensions={"width": width, "height": height},
            )

        except Exception as e:
            logger.error(f"[Composite] Failed: {e}")
            raise

    async def _composite_single_layer(
        self, background: Image.Image, layer: Layer, width: int, height: int, apply_shadows: bool, feather_edges: bool
    ) -> Image.Image:
        """
        Composite a single layer onto the background.

        Args:
            background: Current background image (modified in place)
            layer: Layer to composite
            width, height: Background dimensions
            apply_shadows: Add drop shadow
            feather_edges: Feather layer edges

        Returns:
            Updated background image
        """
        # Load layer image
        layer_image = self._load_image(layer.cutout)

        if layer_image.mode != "RGBA":
            layer_image = layer_image.convert("RGBA")

        # Apply scale
        if layer.scale != 1.0:
            new_width = int(layer_image.width * layer.scale)
            new_height = int(layer_image.height * layer.scale)
            layer_image = layer_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Apply rotation
        if layer.rotation != 0:
            layer_image = layer_image.rotate(layer.rotation, resample=Image.Resampling.BICUBIC, expand=True)

        # Apply opacity
        if layer.opacity < 1.0:
            alpha = layer_image.split()[3]
            alpha = alpha.point(lambda p: int(p * layer.opacity))
            layer_image.putalpha(alpha)

        # Feather edges for smoother blending
        if feather_edges:
            layer_image = self._feather_edges(layer_image, radius=2)

        # Calculate pixel position (x, y are centers in normalized coords)
        px = int(layer.x * width - layer_image.width / 2)
        py = int(layer.y * height - layer_image.height / 2)

        # Add drop shadow
        if apply_shadows:
            shadow = self._create_drop_shadow(layer_image, offset=(5, 5), blur=10)
            background.paste(shadow, (px + 3, py + 3), shadow)

        # Paste layer onto background
        background.paste(layer_image, (px, py), layer_image)

        return background

    def _load_image(self, image_data: str) -> Image.Image:
        """Load image from base64 string."""
        # Remove data URL prefix if present
        if image_data.startswith("data:image"):
            image_data = image_data.split(",")[1]

        image_bytes = base64.b64decode(image_data)
        return Image.open(io.BytesIO(image_bytes))

    def _feather_edges(self, image: Image.Image, radius: int = 3) -> Image.Image:
        """
        Feather the edges of a transparent image for smoother blending.

        Args:
            image: RGBA image
            radius: Feathering radius in pixels

        Returns:
            Image with feathered edges
        """
        if image.mode != "RGBA":
            return image

        # Get alpha channel
        r, g, b, a = image.split()

        # Apply slight blur to alpha channel for feathering
        a = a.filter(ImageFilter.GaussianBlur(radius=radius))

        # Recombine
        return Image.merge("RGBA", (r, g, b, a))

    def _create_drop_shadow(
        self, image: Image.Image, offset: tuple = (5, 5), blur: int = 10, shadow_color: tuple = (0, 0, 0, 80)
    ) -> Image.Image:
        """
        Create a drop shadow for an image.

        Args:
            image: Source RGBA image
            offset: Shadow offset (x, y)
            blur: Blur radius
            shadow_color: RGBA shadow color

        Returns:
            Shadow image (same size as source)
        """
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        # Create shadow from alpha channel
        alpha = image.split()[3]

        # Create solid shadow color
        shadow = Image.new("RGBA", image.size, shadow_color)

        # Use original alpha as shadow shape
        shadow.putalpha(alpha)

        # Blur the shadow
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))

        return shadow

    async def composite_with_harmonization(
        self, background: str, layers: List[Layer], harmonize_service: Any = None
    ) -> CompositingResult:
        """
        Composite layers and optionally harmonize lighting with AI.

        This is a two-step process:
        1. PIL compositing (fast, free)
        2. Optional Gemini harmonization pass (slower, has cost)

        Args:
            background: Base64 background image
            layers: Layers to composite
            harmonize_service: Google AI service for harmonization (optional)

        Returns:
            CompositingResult with harmonized image
        """
        # First do standard compositing
        result = await self.composite_layers(background, layers, apply_shadows=True, feather_edges=True)

        # Optional: harmonize with AI
        if harmonize_service:
            try:
                logger.info("[Composite] Running AI harmonization...")
                harmonized = await harmonize_service.harmonize_lighting(result.image)
                result.image = harmonized
                result.processing_time += 3.0  # Approximate AI time
            except Exception as e:
                logger.warning(f"[Composite] Harmonization failed, using raw composite: {e}")

        return result

    async def preview_layer_position(self, background: str, layer: Layer) -> str:
        """
        Generate quick preview of a single layer at a position.

        Useful for real-time preview during dragging.
        Returns lower quality image for speed.

        Args:
            background: Base64 background
            layer: Single layer to preview

        Returns:
            Base64 preview image
        """
        result = await self.composite_layers(
            background,
            [layer],
            apply_shadows=False,  # Skip shadows for speed
            feather_edges=False,  # Skip feathering for speed
            output_quality=60,  # Lower quality for speed
        )
        return result.image


# Global service instance
compositing_service = ImageCompositingService()
