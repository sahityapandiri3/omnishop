"""
IP-Adapter + ControlNet + SDXL Inpainting Service
Uses product images as visual references for precise furniture placement
"""
import io
import base64
import logging
import time
import numpy as np
from typing import Optional, Dict, List, Any
from PIL import Image, ImageDraw, ImageOps
from dataclasses import dataclass
import aiohttp

from api.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class InpaintingResult:
    """Result from inpainting operation"""
    rendered_image: str  # Base64 encoded result
    processing_time: float
    success: bool
    error_message: str = ""
    confidence_score: float = 0.0


class IPAdapterInpaintingService:
    """
    Advanced inpainting service using IP-Adapter + ControlNet + SDXL

    This approach provides the best quality by:
    1. Using actual product images as visual reference (IP-Adapter)
    2. Preserving room structure with edge detection (ControlNet)
    3. Generating photorealistic results (SDXL Inpainting)
    """

    def __init__(self):
        self.hf_api_key = settings.replicate_api_key  # Reuse for HF API key for now
        # We'll use local diffusers library for best control
        self.pipeline = None
        self._model_loaded = False

        logger.info("IP-Adapter + ControlNet + SDXL Inpainting service initialized")

    async def inpaint_furniture(
        self,
        base_image: str,
        products_to_place: List[Dict[str, Any]],
        existing_furniture: List[Dict[str, Any]] = None,
        user_action: str = None
    ) -> InpaintingResult:
        """
        Main inpainting method using IP-Adapter workflow

        Args:
            base_image: Base64 encoded room image
            products_to_place: List of products with image URLs
            existing_furniture: Detected furniture in room
            user_action: "replace_one", "replace_all", or "add"

        Returns:
            InpaintingResult with rendered image
        """
        start_time = time.time()

        try:
            logger.info(f"Starting IP-Adapter inpainting for {len(products_to_place)} product(s)")

            # Decode room image
            room_image = self._decode_base64_image(base_image)

            # Get product image URLs
            product_image_urls = []
            for product in products_to_place:
                if product.get('image_url'):
                    product_image_urls.append(product['image_url'])
                elif product.get('primary_image', {}).get('url'):
                    product_image_urls.append(product['primary_image']['url'])

            if not product_image_urls:
                raise ValueError("No product images provided for IP-Adapter reference")

            # Download product reference images
            product_images = []
            for url in product_image_urls:
                img = await self._download_product_image(url)
                if img:
                    product_images.append(img)

            if not product_images:
                raise ValueError("Failed to download product images")

            # Generate mask for product placement
            mask = await self._generate_placement_mask(
                room_image=room_image,
                products_to_place=products_to_place,
                existing_furniture=existing_furniture,
                user_action=user_action
            )

            # Generate control image (edge detection) for ControlNet
            control_image = self._generate_control_image(room_image)

            # Build prompt for inpainting
            prompt = self._build_inpainting_prompt(products_to_place, user_action)
            negative_prompt = self._build_negative_prompt()

            # Run IP-Adapter + ControlNet + SDXL Inpainting
            result_image = await self._run_ip_adapter_inpainting(
                room_image=room_image,
                mask=mask,
                product_reference_images=product_images,
                control_image=control_image,
                prompt=prompt,
                negative_prompt=negative_prompt
            )

            # Encode result
            result_base64 = self._encode_image_to_base64(result_image)

            processing_time = time.time() - start_time
            logger.info(f"IP-Adapter inpainting completed in {processing_time:.2f}s")

            return InpaintingResult(
                rendered_image=result_base64,
                processing_time=processing_time,
                success=True,
                confidence_score=0.95
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"IP-Adapter inpainting failed: {e}", exc_info=True)

            return InpaintingResult(
                rendered_image=base_image,
                processing_time=processing_time,
                success=False,
                error_message=str(e),
                confidence_score=0.0
            )

    async def _run_ip_adapter_inpainting(
        self,
        room_image: Image.Image,
        mask: Image.Image,
        product_reference_images: List[Image.Image],
        control_image: Image.Image,
        prompt: str,
        negative_prompt: str
    ) -> Image.Image:
        """
        Run the IP-Adapter + ControlNet + SDXL pipeline

        This is the core inpainting logic that combines:
        - Product images as visual reference (IP-Adapter)
        - Room structure preservation (ControlNet edges)
        - High-quality generation (SDXL)
        """
        try:
            # Load pipeline if not already loaded
            await self._load_pipeline()

            # Prepare images (ensure correct sizes)
            width, height = room_image.size
            # SDXL requires dimensions divisible by 8
            width = (width // 8) * 8
            height = (height // 8) * 8

            room_image = room_image.resize((width, height), Image.Resampling.LANCZOS)
            mask = mask.resize((width, height), Image.Resampling.LANCZOS)
            control_image = control_image.resize((width, height), Image.Resampling.LANCZOS)

            # Resize product reference images
            product_refs = []
            for img in product_reference_images:
                # IP-Adapter works best with 512x512 or 1024x1024
                img_resized = img.resize((512, 512), Image.Resampling.LANCZOS)
                product_refs.append(img_resized)

            logger.info(f"Running IP-Adapter pipeline with {len(product_refs)} reference image(s)")

            # Run the pipeline
            # NOTE: This requires diffusers with IP-Adapter support
            import torch

            # Use IP-Adapter scale to control influence of product image
            # Higher = more faithful to product image (0.0-1.0)
            ip_adapter_scale = 0.8

            # ControlNet scale for room structure preservation
            controlnet_conditioning_scale = 0.7

            result = self.pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=room_image,
                mask_image=mask,
                control_image=control_image,
                ip_adapter_image=product_refs[0] if len(product_refs) == 1 else product_refs,
                num_inference_steps=40,
                guidance_scale=8.5,
                ip_adapter_scale=ip_adapter_scale,
                controlnet_conditioning_scale=controlnet_conditioning_scale,
                strength=0.99  # High strength for complete replacement in masked area
            )

            output_image = result.images[0]
            logger.info("IP-Adapter inpainting pipeline completed successfully")

            return output_image

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            raise

    async def _load_pipeline(self):
        """Load the IP-Adapter + ControlNet + SDXL pipeline"""
        if self._model_loaded:
            return

        try:
            logger.info("Loading IP-Adapter + ControlNet + SDXL pipeline...")

            from diffusers import (
                StableDiffusionXLControlNetInpaintPipeline,
                ControlNetModel,
                AutoencoderKL
            )
            from diffusers.utils import load_image
            import torch

            # Determine device
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"

            logger.info(f"Using device: {device}")

            # Load ControlNet (Canny edge detection)
            controlnet = ControlNetModel.from_pretrained(
                "diffusers/controlnet-canny-sdxl-1.0",
                torch_dtype=torch.float16 if device != "cpu" else torch.float32,
                variant="fp16" if device != "cpu" else None
            )

            # Load VAE for better quality
            vae = AutoencoderKL.from_pretrained(
                "madebyollin/sdxl-vae-fp16-fix",
                torch_dtype=torch.float16 if device != "cpu" else torch.float32
            )

            # Load SDXL Inpainting pipeline with ControlNet
            self.pipeline = StableDiffusionXLControlNetInpaintPipeline.from_pretrained(
                "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
                controlnet=controlnet,
                vae=vae,
                torch_dtype=torch.float16 if device != "cpu" else torch.float32,
                variant="fp16" if device != "cpu" else None
            )

            # Load IP-Adapter
            self.pipeline.load_ip_adapter(
                "h94/IP-Adapter",
                subfolder="sdxl_models",
                weight_name="ip-adapter_sdxl.bin"
            )

            # Move to device
            self.pipeline.to(device)

            # Enable memory optimizations
            if device == "mps":
                self.pipeline.enable_attention_slicing()
            elif device == "cuda":
                self.pipeline.enable_model_cpu_offload()

            self._model_loaded = True
            logger.info("Pipeline loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load pipeline: {e}", exc_info=True)
            raise

    def _generate_control_image(self, image: Image.Image) -> Image.Image:
        """
        Generate ControlNet control image using Canny edge detection
        This preserves room structure during inpainting
        """
        try:
            import cv2

            # Convert PIL to numpy
            img_array = np.array(image)

            # Convert to grayscale
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Apply Canny edge detection
            # Low threshold = 100, High threshold = 200 (good for room edges)
            edges = cv2.Canny(gray, 100, 200)

            # Convert back to PIL
            control_image = Image.fromarray(edges)

            # Convert to RGB (ControlNet expects 3 channels)
            control_image = control_image.convert("RGB")

            logger.info("Generated ControlNet edge detection image")
            return control_image

        except Exception as e:
            logger.error(f"Failed to generate control image: {e}")
            # Return original image as fallback
            return image.convert("RGB")

    async def _generate_placement_mask(
        self,
        room_image: Image.Image,
        products_to_place: List[Dict[str, Any]],
        existing_furniture: List[Dict[str, Any]],
        user_action: str
    ) -> Image.Image:
        """
        Generate mask for product placement
        White = inpaint area (place product)
        Black = preserve area (keep room as-is)
        """
        try:
            width, height = room_image.size

            # Create black mask (preserve everything initially)
            mask = Image.new('RGB', (width, height), color='black')
            draw = ImageDraw.Draw(mask)

            # Calculate furniture dimensions
            if products_to_place and len(products_to_place) > 0:
                product = products_to_place[0]
                product_name = product.get('full_name') or product.get('name', 'furniture')

                # Get or estimate dimensions
                dimensions = product.get('dimensions')
                if not dimensions:
                    dimensions = self._get_typical_dimensions(product_name)

                # Calculate pixel size from real dimensions
                # Assume standard 12ft (144") room width
                pixels_per_inch = width / 144

                furn_width = int(dimensions.get('width', 60) * pixels_per_inch)
                furn_height = int(dimensions.get('height', 30) * pixels_per_inch * 0.7)  # Perspective compression

                # Clamp to reasonable bounds
                furn_width = max(int(width * 0.15), min(furn_width, int(width * 0.45)))
                furn_height = max(int(height * 0.15), min(furn_height, int(height * 0.45)))

                # Add 10% padding for natural placement
                mask_width = int(furn_width * 1.1)
                mask_height = int(furn_height * 1.1)

                # Center placement (can be adjusted based on user_action)
                center_x = width // 2
                center_y = int(height * 0.6)  # Slightly below center

                # Draw white rectangle for inpaint region
                x1 = center_x - mask_width // 2
                y1 = center_y - mask_height // 2
                x2 = center_x + mask_width // 2
                y2 = center_y + mask_height // 2

                draw.rectangle([x1, y1, x2, y2], fill='white')

                logger.info(f"Generated mask for {product_name}: {mask_width}x{mask_height}px at center")
            else:
                # Fallback: generic center placement
                mask_width = int(width * 0.35)
                mask_height = int(height * 0.35)

                x1 = (width - mask_width) // 2
                y1 = (height - mask_height) // 2
                x2 = x1 + mask_width
                y2 = y1 + mask_height

                draw.rectangle([x1, y1, x2, y2], fill='white')

            return mask

        except Exception as e:
            logger.error(f"Failed to generate mask: {e}")
            # Return empty mask (preserve entire image)
            return Image.new('RGB', room_image.size, color='black')

    def _build_inpainting_prompt(
        self,
        products: List[Dict[str, Any]],
        user_action: str
    ) -> str:
        """Build prompt for IP-Adapter inpainting"""
        product_names = [p.get('full_name') or p.get('name', 'furniture') for p in products]

        if len(product_names) == 1:
            product_desc = product_names[0]
        else:
            product_desc = ", ".join(product_names[:-1]) + f" and {product_names[-1]}"

        prompt = (
            f"A photorealistic interior photograph with a {product_desc} "
            f"naturally placed in the room. "
            f"The furniture matches the exact style, color, materials, and design from the reference image. "
            f"Realistic lighting that matches the room's existing light sources, "
            f"proper shadows on the floor, correct perspective and scale for the room dimensions, "
            f"seamless integration with the room environment. "
            f"Professional interior photography, high quality, natural placement, "
            f"accurate materials and textures from the reference product image. "
            f"The room structure, walls, floor, windows, and doors remain completely unchanged."
        )

        logger.info(f"Inpainting prompt: {prompt[:150]}...")
        return prompt

    def _build_negative_prompt(self) -> str:
        """Build negative prompt to avoid unwanted elements"""
        return (
            "blurry, low quality, distorted, deformed, unrealistic, bad anatomy, "
            "floating furniture, incorrect shadows, cartoon, painting, illustration, "
            "different room, changed walls, changed floor, multiple copies, duplicates, "
            "wrong perspective, poor lighting, artifacts, watermark, text"
        )

    def _get_typical_dimensions(self, product_name: str) -> Dict[str, float]:
        """Get typical furniture dimensions in inches"""
        name_lower = product_name.lower()

        # Seating
        if 'sofa' in name_lower or 'couch' in name_lower:
            return {"width": 84, "depth": 36, "height": 36}
        elif 'chair' in name_lower:
            return {"width": 32, "depth": 34, "height": 36}
        # Tables
        elif 'coffee table' in name_lower:
            return {"width": 48, "depth": 24, "height": 18}
        elif 'side table' in name_lower:
            return {"width": 24, "depth": 18, "height": 24}
        elif 'dining table' in name_lower:
            return {"width": 72, "depth": 40, "height": 30}
        # Beds
        elif 'bed' in name_lower:
            return {"width": 60, "depth": 80, "height": 24}
        # Storage
        elif 'dresser' in name_lower:
            return {"width": 60, "depth": 18, "height": 36}
        # Default
        return {"width": 48, "depth": 30, "height": 30}

    def _decode_base64_image(self, base64_string: str) -> Image.Image:
        """Decode base64 string to PIL Image with orientation correction"""
        try:
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]

            image_bytes = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_bytes))

            # Apply EXIF orientation correction
            image = ImageOps.exif_transpose(image)

            # Ensure RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')

            return image
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            raise

    def _encode_image_to_base64(self, image: Image.Image) -> str:
        """Encode PIL Image to base64 string"""
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG", quality=95)
            img_bytes = buffered.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode()
            return f"data:image/png;base64,{img_base64}"
        except Exception as e:
            logger.error(f"Failed to encode image to base64: {e}")
            raise

    async def _download_product_image(self, url: str) -> Optional[Image.Image]:
        """Download product image from URL with orientation correction"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        image = Image.open(io.BytesIO(image_bytes))

                        # Apply EXIF orientation correction
                        image = ImageOps.exif_transpose(image)

                        # Ensure RGB
                        if image.mode != 'RGB':
                            image = image.convert('RGB')

                        logger.info(f"Downloaded product image from {url[:80]}...")
                        return image
                    else:
                        logger.error(f"Failed to download image: HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading product image: {e}")
            return None


# Global service instance
ip_adapter_inpainting_service = IPAdapterInpaintingService()
