"""
Furniture Layer Extraction Service

Handles extracting individual furniture pieces as separate layers from visualizations
using Google Gemini 2.5 Flash Image AI.
"""

import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .google_ai_service import GoogleAIStudioService

logger = logging.getLogger(__name__)


class FurnitureLayerService:
    """Service for extracting and managing furniture layers from visualizations"""

    def __init__(self):
        self.google_ai = GoogleAIStudioService()

    async def extract_furniture_layer(
        self, visualization_image: str, product_info: Dict[str, Any], layer_index: int
    ) -> Dict[str, Any]:
        """
        Extract a single furniture piece as a separate layer with transparent background

        Args:
            visualization_image: Base64 encoded visualization image
            product_info: Dict with product details (id, name, description)
            layer_index: Index for z-ordering (higher = on top)

        Returns:
            Dict with layer data including isolated image and position
        """
        product_name = product_info.get("name", "furniture item")
        product_id = product_info.get("id")

        logger.info(f"[FurnitureLayerService] Extracting layer for product: {product_name} (ID: {product_id})")

        # Step 1: Isolate the furniture piece with transparent background
        isolation_prompt = f"""Extract and isolate the {product_name} from this room visualization.

TASK: Create an image showing ONLY the {product_name} on a transparent background (PNG with alpha channel).

REQUIREMENTS:
- Preserve the EXACT perspective, lighting, shadows, and reflections from the original
- Keep the furniture's exact size, position, and orientation
- Remove ALL other elements (room, walls, floor, ceiling, other furniture)
- Maintain clean edges with proper alpha transparency
- Include the furniture's shadow as part of the layer (if it has one)
- Output format: PNG with transparency

IMPORTANT: The extracted furniture should look identical to how it appears in the visualization - same lighting, same shadows, same perspective. Only the background should be removed.
"""

        try:
            # Use Gemini to isolate the furniture with transparency
            isolated_image = await self._isolate_with_transparency(visualization_image, isolation_prompt)

            # Step 2: Detect the furniture's position and dimensions in the original image
            position_data = await self._detect_furniture_position(visualization_image, product_name)

            # Step 3: Compile layer data
            layer_data = {
                "layer_id": f"layer_{layer_index}",
                "product_id": str(product_id),
                "product_name": product_name,
                "layer_image": isolated_image,
                "position": position_data.get("position", {"x": 0.5, "y": 0.5}),
                "dimensions": position_data.get("dimensions", {"width": 0.2, "height": 0.2}),
                "z_index": layer_index,
                "extraction_confidence": position_data.get("confidence", 0.8),
            }

            logger.info(f"[FurnitureLayerService] Successfully extracted layer for {product_name}")
            return layer_data

        except Exception as e:
            logger.error(f"[FurnitureLayerService] Error extracting layer for {product_name}: {str(e)}")
            raise

    async def _isolate_with_transparency(self, image: str, prompt: str) -> str:
        """
        Use Gemini to isolate an object with transparent background

        Note: Since Gemini doesn't directly support transparency output,
        we'll ask it to create the isolation and return as base64.
        In production, you may want to add post-processing to create true transparency.
        """
        try:
            # Call Gemini with image generation capabilities
            # For now, we'll use Gemini's image editing capabilities
            # In a real implementation, you might need to use additional tools
            # like rembg or SAM (Segment Anything Model) for perfect transparency

            result = await self.google_ai.generate_image_with_prompt(base_image=image, prompt=prompt)

            return result

        except Exception as e:
            logger.error(f"[FurnitureLayerService] Error in transparency isolation: {str(e)}")
            # Fallback: return original image if isolation fails
            return image

    async def _detect_furniture_position(self, image: str, product_name: str) -> Dict[str, Any]:
        """
        Detect the position and dimensions of furniture in the image

        Uses Gemini Vision to analyze where the furniture is located
        """
        detection_prompt = f"""Analyze the position of the {product_name} in this room image.

Provide the following information in JSON format:

1. Position: Where is the {product_name} located as percentages of image dimensions?
   - x: horizontal position (0.0 = left edge, 1.0 = right edge, 0.5 = center)
   - y: vertical position (0.0 = top edge, 1.0 = bottom edge, 0.5 = center)

2. Dimensions: How much space does the {product_name} occupy?
   - width: percentage of image width (0.0 to 1.0)
   - height: percentage of image height (0.0 to 1.0)

3. Confidence: How confident are you in this detection? (0.0 to 1.0)

Return ONLY valid JSON in this exact format:
{{
  "position": {{"x": 0.0-1.0, "y": 0.0-1.0}},
  "dimensions": {{"width": 0.0-1.0, "height": 0.0-1.0}},
  "confidence": 0.0-1.0
}}
"""

        try:
            # Use Gemini to analyze the image
            response = await self.google_ai.analyze_image_with_prompt(image=image, prompt=detection_prompt)

            # Parse JSON response
            position_data = self._parse_position_json(response)
            return position_data

        except Exception as e:
            logger.warning(f"[FurnitureLayerService] Error detecting position for {product_name}: {str(e)}")
            # Return default centered position if detection fails
            return {"position": {"x": 0.5, "y": 0.5}, "dimensions": {"width": 0.2, "height": 0.2}, "confidence": 0.5}

    def _parse_position_json(self, response: str) -> Dict[str, Any]:
        """Parse position data from Gemini response"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[^}]+\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return data
            else:
                # Fallback: try parsing entire response
                return json.loads(response)
        except Exception as e:
            logger.warning(f"[FurnitureLayerService] Could not parse position JSON: {str(e)}")
            return {"position": {"x": 0.5, "y": 0.5}, "dimensions": {"width": 0.2, "height": 0.2}, "confidence": 0.5}

    async def extract_all_layers(
        self, visualization_image: str, products: List[Dict[str, Any]], session_id: str
    ) -> Dict[str, Any]:
        """
        Extract all furniture pieces as separate layers from a visualization

        Args:
            visualization_image: Base64 encoded visualization
            products: List of products that were placed in the visualization
            session_id: Session ID for tracking

        Returns:
            Dict containing base_layer and furniture_layers
        """
        logger.info(f"[FurnitureLayerService] Starting layer extraction for session {session_id}")
        logger.info(f"[FurnitureLayerService] Extracting {len(products)} furniture pieces")

        try:
            # Step 1: Extract base layer (clean room without furniture)
            logger.info("[FurnitureLayerService] Step 1: Extracting base room layer")
            base_layer = await self.get_base_room_layer(visualization_image)

            # Step 2: Extract each furniture piece as a layer
            furniture_layers = []
            for index, product in enumerate(products):
                logger.info(f"[FurnitureLayerService] Step 2.{index + 1}: Extracting layer for {product.get('name')}")

                layer_data = await self.extract_furniture_layer(
                    visualization_image, product, index + 1  # z_index starts at 1 (base layer is 0)
                )

                furniture_layers.append(layer_data)

            result = {
                "session_id": session_id,
                "base_layer": base_layer,
                "furniture_layers": furniture_layers,
                "total_layers": len(furniture_layers) + 1,  # +1 for base layer
                "extraction_status": "success",
            }

            logger.info(f"[FurnitureLayerService] Successfully extracted all layers for session {session_id}")
            return result

        except Exception as e:
            logger.error(f"[FurnitureLayerService] Error extracting layers: {str(e)}")
            return {
                "session_id": session_id,
                "base_layer": None,
                "furniture_layers": [],
                "total_layers": 0,
                "extraction_status": "failed",
                "error": str(e),
            }

    async def get_base_room_layer(self, visualization_image: str) -> str:
        """
        Extract the clean room (base layer) by removing all furniture

        Reuses the existing furniture removal functionality
        """
        logger.info("[FurnitureLayerService] Extracting base room layer (removing furniture)")

        try:
            # Use the existing furniture removal function from GoogleAIService
            clean_room = await self.google_ai.remove_furniture(visualization_image)

            logger.info("[FurnitureLayerService] Successfully extracted base room layer")
            return clean_room

        except Exception as e:
            logger.error(f"[FurnitureLayerService] Error extracting base room: {str(e)}")
            # Fallback: return original image if removal fails
            return visualization_image


# Singleton instance
_furniture_layer_service = None


def get_furniture_layer_service() -> FurnitureLayerService:
    """Get singleton instance of FurnitureLayerService"""
    global _furniture_layer_service
    if _furniture_layer_service is None:
        _furniture_layer_service = FurnitureLayerService()
    return _furniture_layer_service
