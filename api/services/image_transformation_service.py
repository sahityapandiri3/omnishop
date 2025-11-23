"""
Image transformation service using Google Gemini 3 Pro Image (Nano Banana Pro)
This service handles image-to-image transformation for room design visualization
"""
import base64
import logging
import time
from io import BytesIO
from typing import Optional

from PIL import Image

try:
    from google import genai
    from google.genai import types

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logging.warning("google-genai package not installed. Image transformation will not work.")

from core.config import settings

logger = logging.getLogger(__name__)


class ImageTransformationService:
    """Service for transforming room images using Gemini 3 Pro Image (Nano Banana Pro)"""

    def __init__(self):
        """Initialize the image transformation service"""
        self.api_key = settings.google_ai_api_key
        self.model = "gemini-3-pro-image-preview"

        if GENAI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("✅ Image transformation service initialized with Gemini 3 Pro Image (Nano Banana Pro)")
            except Exception as e:
                logger.error(f"❌ Failed to initialize GenAI client: {e}")
                self.client = None
        else:
            self.client = None
            logger.warning("⚠️ Google GenAI not available - install with: pip install google-genai")

    def _base64_to_image(self, base64_string: str) -> Optional[Image.Image]:
        """Convert base64 string to PIL Image"""
        try:
            # Remove data URL prefix if present
            if "," in base64_string:
                base64_string = base64_string.split(",", 1)[1]

            image_data = base64.b64decode(base64_string)
            image = Image.open(BytesIO(image_data))
            return image
        except Exception as e:
            logger.error(f"❌ Failed to decode base64 image: {e}")
            return None

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """Convert PIL Image to base64 string with data URL prefix"""
        try:
            buffered = BytesIO()
            image.save(buffered, format=format)
            img_bytes = buffered.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            return f"data:image/{format.lower()};base64,{img_base64}"
        except Exception as e:
            logger.error(f"❌ Failed to encode image to base64: {e}")
            return ""

    async def transform_room_image(
        self, base_image_base64: str, style_prompt: str, user_preferences: Optional[dict] = None
    ) -> Optional[str]:
        """
        Transform a room image according to the style prompt

        Args:
            base_image_base64: Base64 encoded input image (with or without data URL prefix)
            style_prompt: The design style/transformation prompt from user
            user_preferences: Optional dict with user preferences for the transformation

        Returns:
            Base64 encoded transformed image (with data URL prefix) or None if failed
        """
        if not self.client:
            logger.error("❌ GenAI client not initialized")
            return None

        start_time = time.time()

        try:
            # Convert base64 to PIL Image
            logger.info("🔄 Converting base64 to image...")
            input_image = self._base64_to_image(base_image_base64)
            if not input_image:
                return None

            # Build the transformation prompt
            logger.info(f"🎨 Building transformation prompt for style: {style_prompt}")

            # Extract style information from user preferences if available
            style_details = ""
            if user_preferences:
                styles = user_preferences.get("design_styles", [])
                colors = user_preferences.get("color_preferences", [])
                materials = user_preferences.get("material_preferences", [])

                if styles:
                    style_details += f"Design styles: {', '.join(styles)}. "
                if colors:
                    style_details += f"Color preferences: {', '.join(colors)}. "
                if materials:
                    style_details += f"Material preferences: {', '.join(materials)}. "

            # Create comprehensive prompt
            full_prompt = f"""Transform this room image to match the following design request: {style_prompt}

{style_details}

Requirements:
- Maintain the room's basic structure and layout
- Keep the same perspective and viewing angle
- Transform furniture, decor, and styling to match the requested design
- Ensure photorealistic quality
- Preserve good lighting and realistic shadows
- Make the transformation look natural and cohesive

Generate a high-quality photorealistic image of the transformed room."""

            logger.info(f"📝 Full prompt: {full_prompt[:200]}...")
            logger.info("🚀 Calling Gemini 2.5 Flash Image API...")

            # Call Gemini 2.5 Flash Image with image + text prompt
            response = self.client.models.generate_content(
                model=self.model,
                contents=[full_prompt, input_image],
            )

            logger.info("✅ Received response from Gemini")

            # Extract image from response
            transformed_image = None
            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    logger.info(f"📄 Gemini response text: {part.text[:200]}...")
                elif part.inline_data is not None:
                    logger.info("🖼️ Found inline image data in response")
                    transformed_image = Image.open(BytesIO(part.inline_data.data))
                    break

            if not transformed_image:
                logger.error("❌ No image found in Gemini response")
                return None

            # Convert to base64
            logger.info("🔄 Converting transformed image to base64...")
            result_base64 = self._image_to_base64(transformed_image)

            processing_time = time.time() - start_time
            logger.info(f"✅ Image transformation completed in {processing_time:.2f}s")

            return result_base64

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Image transformation failed after {processing_time:.2f}s: {str(e)}")
            logger.exception("Full error traceback:")
            return None

    async def close(self):
        """Clean up resources"""
        # No persistent connections to close for GenAI client
        pass


# Global service instance
image_transformation_service = ImageTransformationService()
