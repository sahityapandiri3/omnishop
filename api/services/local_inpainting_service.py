"""
Local SDXL Inpainting Service using HuggingFace Diffusers
Provides inpainting + masking workflow for furniture placement
"""
import io
import base64
import logging
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageOps
import numpy as np
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)


class LocalInpaintingService:
    """
    Local SDXL inpainting service using HuggingFace Diffusers
    Implements proper inpainting + masking workflow
    """

    def __init__(self):
        self.pipeline = None
        self._model_loaded = False
        self._load_lock = asyncio.Lock()
        logger.info("LocalInpaintingService initialized")

    async def _load_model(self):
        """Lazy load the SDXL inpainting model"""
        if self._model_loaded:
            return

        async with self._load_lock:
            if self._model_loaded:  # Double-check after acquiring lock
                return

            try:
                logger.info("Loading SDXL inpainting pipeline from HuggingFace...")

                # Import here to avoid loading if not needed
                from diffusers import StableDiffusionXLInpaintPipeline
                import torch

                # Determine device
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                logger.info(f"Using device: {device}")

                # Load the pipeline
                self.pipeline = StableDiffusionXLInpaintPipeline.from_pretrained(
                    "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
                    torch_dtype=torch.float16 if device != "cpu" else torch.float32,
                    variant="fp16" if device != "cpu" else None,
                )

                # Move to device
                self.pipeline.to(device)

                # Enable memory optimizations
                if device == "mps":
                    self.pipeline.enable_attention_slicing()

                self._model_loaded = True
                logger.info("SDXL inpainting pipeline loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load SDXL inpainting pipeline: {e}")
                raise

    async def create_furniture_mask(
        self,
        room_width: int,
        room_height: int,
        furniture_bbox: dict,
        furniture_dimensions: dict
    ) -> Image.Image:
        """
        Create a mask for furniture placement

        Args:
            room_width: Width of room image in pixels
            room_height: Height of room image in pixels
            furniture_bbox: Bounding box dict with x, y, width, height
            furniture_dimensions: Product dimensions for scaling

        Returns:
            PIL Image mask (white = inpaint, black = preserve)
        """
        # Create black image (preserve all)
        mask = Image.new('RGB', (room_width, room_height), color='black')
        draw = ImageDraw.Draw(mask)

        # Extract bbox coordinates
        x = furniture_bbox.get('x', room_width // 2)
        y = furniture_bbox.get('y', room_height // 2)
        width = furniture_bbox.get('width', 200)
        height = furniture_bbox.get('height', 200)

        # Draw white rectangle where furniture should be placed
        draw.rectangle(
            [x, y, x + width, y + height],
            fill='white'
        )

        logger.info(f"Created mask: bbox=({x}, {y}, {width}, {height})")
        return mask

    async def inpaint_furniture(
        self,
        room_image: Image.Image,
        mask: Image.Image,
        product_image: Image.Image,
        prompt: str,
        negative_prompt: Optional[str] = None,
        strength: float = 0.99,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 50
    ) -> Image.Image:
        """
        Inpaint furniture into room using mask

        Args:
            room_image: Original room image
            mask: Mask image (white = inpaint region)
            product_image: Product image to place
            prompt: Text prompt describing the placement
            negative_prompt: Negative prompt for quality control
            strength: How much to transform masked region (0-1)
            guidance_scale: How closely to follow prompt
            num_inference_steps: Number of denoising steps

        Returns:
            Inpainted image with furniture
        """
        await self._load_model()

        try:
            logger.info(f"Starting inpainting: prompt='{prompt[:100]}...'")

            # Ensure images are RGB
            room_image = room_image.convert("RGB")
            mask = mask.convert("RGB")

            # Resize to model requirements (must be multiples of 8)
            width = (room_image.width // 8) * 8
            height = (room_image.height // 8) * 8

            room_image = room_image.resize((width, height))
            mask = mask.resize((width, height))

            # Default negative prompt
            if negative_prompt is None:
                negative_prompt = (
                    "blurry, low quality, distorted, deformed, "
                    "unrealistic, bad anatomy, cartoon, painting"
                )

            # Run inpainting
            result = self.pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=room_image,
                mask_image=mask,
                strength=strength,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
            )

            output_image = result.images[0]
            logger.info("Inpainting completed successfully")

            return output_image

        except Exception as e:
            logger.error(f"Inpainting failed: {e}")
            raise

    async def visualize_furniture_placement(
        self,
        room_image_base64: str,
        product_image_url: str,
        product_name: str,
        product_description: str,
        placement_bbox: dict,
        product_dimensions: dict
    ) -> str:
        """
        Main method: Place furniture product into room image

        Args:
            room_image_base64: Base64 encoded room image
            product_image_url: URL to product image
            product_name: Name of product
            product_description: Description of product
            placement_bbox: Where to place (x, y, width, height)
            product_dimensions: Product dimensions for scaling

        Returns:
            Base64 encoded result image
        """
        try:
            # Decode room image
            room_image = self._decode_base64_image(room_image_base64)

            # Download product image
            product_image = await self._download_product_image(product_image_url)

            # Create mask for placement region
            mask = await self.create_furniture_mask(
                room_width=room_image.width,
                room_height=room_image.height,
                furniture_bbox=placement_bbox,
                furniture_dimensions=product_dimensions
            )

            # Build inpainting prompt
            prompt = self._build_inpainting_prompt(
                product_name=product_name,
                product_description=product_description,
                placement_bbox=placement_bbox
            )

            # Run inpainting
            result_image = await self.inpaint_furniture(
                room_image=room_image,
                mask=mask,
                product_image=product_image,
                prompt=prompt
            )

            # Encode result
            result_base64 = self._encode_image_to_base64(result_image)

            logger.info("Furniture placement visualization completed")
            return result_base64

        except Exception as e:
            logger.error(f"Furniture placement visualization failed: {e}")
            raise

    def _build_inpainting_prompt(
        self,
        product_name: str,
        product_description: str,
        placement_bbox: dict
    ) -> str:
        """Build detailed prompt for inpainting"""
        prompt = (
            f"A realistic interior design photograph showing a {product_name} "
            f"placed in a room. {product_description}. "
            f"The furniture should look natural and properly scaled for the space, "
            f"with realistic lighting, shadows, and perspective. "
            f"Professional interior photography, high quality, photorealistic."
        )
        return prompt

    def _decode_base64_image(self, base64_string: str) -> Image.Image:
        """Decode base64 string to PIL Image with orientation correction"""
        try:
            # Remove data URL prefix if present
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]

            image_bytes = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_bytes))

            # Apply EXIF orientation correction
            image = ImageOps.exif_transpose(image)

            return image
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise

    def _encode_image_to_base64(self, image: Image.Image) -> str:
        """Encode PIL Image to base64 string"""
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode()
            return f"data:image/png;base64,{img_base64}"
        except Exception as e:
            logger.error(f"Failed to encode image to base64: {e}")
            raise

    async def _download_product_image(self, url: str) -> Image.Image:
        """Download product image from URL with orientation correction"""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        image = Image.open(io.BytesIO(image_bytes))

                        # Apply EXIF orientation correction
                        image = ImageOps.exif_transpose(image)

                        logger.info(f"Downloaded product image from {url[:100]}...")
                        return image
                    else:
                        raise Exception(f"Failed to download image: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error downloading product image: {e}")
            raise


# Global instance
_local_inpainting_service = None


def get_local_inpainting_service() -> LocalInpaintingService:
    """Get or create global LocalInpaintingService instance"""
    global _local_inpainting_service
    if _local_inpainting_service is None:
        _local_inpainting_service = LocalInpaintingService()
    return _local_inpainting_service
