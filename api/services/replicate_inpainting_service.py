"""
Replicate Stable Diffusion XL Inpainting service for furniture placement with room preservation
This service uses SDXL inpainting to place furniture while preserving the exact room structure
"""
import logging
import asyncio
import base64
import io
import time
import numpy as np
import cv2
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from PIL import Image
import replicate

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class InpaintingRequest:
    """Request for inpainting operation"""
    base_image: str  # Base64 encoded image
    mask: str  # Base64 encoded mask (white = inpaint, black = preserve)
    prompt: str  # What to generate in the masked area
    negative_prompt: str = ""  # What to avoid
    products: List[Dict[str, Any]] = None  # Products being placed
    product_image_url: str = None  # URL to product image for IP-Adapter reference


@dataclass
class InpaintingResult:
    """Result from inpainting operation"""
    rendered_image: str  # Base64 encoded result
    processing_time: float
    success: bool
    error_message: str = ""


class ReplicateInpaintingService:
    """Service for Replicate SDXL inpainting"""

    def __init__(self):
        """Initialize Replicate service"""
        self.api_key = settings.replicate_api_key
        self.model_sdxl = settings.replicate_model_sdxl_inpaint
        self.model_interior = settings.replicate_model_interior_design
        self.model_ip_adapter_sdxl = settings.replicate_model_ip_adapter_sdxl  # IP-Adapter SDXL for generating exact furniture

        self.usage_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "last_reset": datetime.now()
        }

        self._validate_api_key()

        # Set Replicate API token for the replicate module
        import os
        os.environ["REPLICATE_API_TOKEN"] = self.api_key
        replicate.api_token = self.api_key

        logger.info("Replicate SDXL inpainting service initialized with IP-Adapter support")

    def _validate_api_key(self):
        """Validate Replicate API key"""
        if not self.api_key:
            logger.error("Replicate API key not configured")
            raise ValueError("Replicate API key is required - set REPLICATE_API_KEY environment variable")

        logger.info("Replicate API key validated")

    async def inpaint_furniture(
        self,
        base_image: str,
        products_to_place: List[Dict[str, Any]],
        existing_furniture: List[Dict[str, Any]] = None,
        user_action: str = None
    ) -> InpaintingResult:
        """
        Inpaint furniture into room using SDXL while preserving room structure

        Args:
            base_image: Base64 encoded room image
            products_to_place: List of product dictionaries with name, description, etc.
            existing_furniture: List of detected furniture in the room
            user_action: "replace_one", "replace_all", or "add"

        Returns:
            InpaintingResult with rendered image
        """
        start_time = time.time()
        self.usage_stats["total_requests"] += 1

        try:
            # BUG #2 FIX: Two-Pass Inpainting for Replace Actions
            # Pass 1: Remove existing furniture
            # Pass 2: Add new furniture
            working_image = base_image

            if user_action in ["replace_one", "replace_all"] and existing_furniture:
                logger.info(f"BUG #2 FIX: Starting two-pass inpainting for {user_action}")

                # PASS 1: Remove existing furniture
                logger.info(f"PASS 1: Removing existing furniture...")
                removal_result = await self._remove_existing_furniture(
                    base_image=base_image,
                    furniture_to_remove=existing_furniture,
                    remove_all=(user_action == "replace_all")
                )

                if removal_result.success:
                    # CRITICAL FIX: Keep as base64 string (this service uses base64 throughout)
                    working_image = removal_result.rendered_image
                    logger.info(f"PASS 1 SUCCESS: Furniture removed, proceeding to PASS 2")
                else:
                    logger.warning(f"PASS 1 FAILED: {removal_result.error_message}, continuing with original image")
                    # Continue with original image if removal fails

                # PASS 2: Add new furniture (handled below)
                logger.info(f"PASS 2: Adding new furniture to cleaned image...")

            # Enrich products with dimensions and product images from database
            for product in products_to_place:
                product_id = product.get('id')
                product_name = product.get('full_name') or product.get('name', '')

                # 1. Fetch dimensions
                if not product.get('dimensions') and product_id:
                    db_dimensions = await self._get_product_dimensions_from_db(product_id)
                    if db_dimensions:
                        product['dimensions'] = db_dimensions

                # Fallback to typical dimensions by name
                if not product.get('dimensions') and product_name:
                    typical_dims = self._get_typical_dimensions_by_category(product_name)
                    product['dimensions'] = typical_dims
                    logger.info(f"Using typical dimensions for {product_name}: {typical_dims}")

                # 2. Fetch product image for IP-Adapter reference
                if not product.get('product_image_url') and product_id:
                    product_image_url = await self._get_product_image_from_db(product_id)
                    if product_image_url:
                        product['product_image_url'] = product_image_url
                        logger.info(f"Found product image for IP-Adapter reference: {product_name}")

            # Enrich existing furniture with dimensions if available
            if existing_furniture:
                for furniture in existing_furniture:
                    if not furniture.get('dimensions'):
                        furniture_type = furniture.get('object_type') or furniture.get('name', '')
                        if furniture_type:
                            typical_dims = self._get_typical_dimensions_by_category(furniture_type)
                            furniture['dimensions'] = typical_dims

            # Generate mask for inpainting
            # BUG #2 & #3 FIX: Use working_image (cleaned in Pass 1) and pass products for size calculation
            mask = await self._generate_furniture_mask(
                working_image,
                existing_furniture,
                user_action,
                products_to_place  # BUG #3 FIX: Pass products for accurate mask sizing
            )

            # Build prompt for furniture placement
            prompt = self._build_furniture_prompt(products_to_place, user_action)
            negative_prompt = self._build_negative_prompt()

            # TWO-STEP APPROACH: Generate exact furniture using IP-Adapter, then inpaint
            # Step 1: Check if we have product image for IP-Adapter
            product_image_url = None
            for product in products_to_place:
                if product.get('product_image_url'):
                    product_image_url = product['product_image_url']
                    break  # Use first product image

            # If we have a product image, use TWO-STEP workflow
            if product_image_url:
                logger.info("STEP 1: Generating exact furniture using IP-Adapter SDXL...")

                # First, analyze product image with ChatGPT Vision for detailed description
                visual_description = await self._analyze_product_image_with_chatgpt(
                    product_image_url,
                    products_to_place[0].get('full_name') or products_to_place[0].get('name', 'furniture')
                )

                if visual_description:
                    products_to_place[0]['visual_description'] = visual_description
                    logger.info(f"ChatGPT Vision analysis: {visual_description[:150]}...")

                # Generate isolated furniture image using IP-Adapter
                furniture_image = await self._generate_furniture_with_ip_adapter(
                    product_image_url=product_image_url,
                    product=products_to_place[0],
                    mask_dimensions=(mask.split(',')[1] if ',' in mask else mask)  # Get mask dimensions
                )

                if furniture_image:
                    logger.info("STEP 2: Placing IP-Adapter generated furniture into room using inpainting...")
                    # Use the IP-Adapter generated furniture in the prompt
                    prompt = self._build_furniture_prompt_with_reference(products_to_place, user_action, furniture_image)
                else:
                    logger.warning("IP-Adapter furniture generation failed, using ChatGPT Vision-enhanced text prompt")
                    # FALLBACK: Use ChatGPT Vision description to enhance the text prompt
                    if visual_description:
                        prompt = self._build_furniture_prompt_from_vision(products_to_place, user_action, visual_description)
                        logger.info(f"Using ChatGPT Vision-enhanced prompt: {prompt[:150]}...")
                    else:
                        logger.warning("No visual description available, using basic text prompt")

            # Create inpainting request
            # BUG #2 FIX: Use working_image (cleaned in Pass 1) as base for Pass 2
            request = InpaintingRequest(
                base_image=working_image,
                mask=mask,
                prompt=prompt,
                negative_prompt=negative_prompt,
                products=products_to_place,
                product_image_url=None  # Not used in standard inpainting
            )

            # Perform inpainting
            result = await self._run_sdxl_inpainting(request)

            processing_time = time.time() - start_time
            self.usage_stats["total_processing_time"] += processing_time

            if result.success:
                self.usage_stats["successful_requests"] += 1
                logger.info(f"SDXL inpainting successful in {processing_time:.2f}s")
            else:
                self.usage_stats["failed_requests"] += 1
                logger.error(f"SDXL inpainting failed: {result.error_message}")

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            self.usage_stats["failed_requests"] += 1
            logger.error(f"Error in inpaint_furniture: {e}", exc_info=True)

            return InpaintingResult(
                rendered_image=base_image,  # Return original on error
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )

    async def _generate_furniture_mask(
        self,
        base_image: str,
        existing_furniture: List[Dict[str, Any]],
        user_action: str,
        products_to_place: List[Dict[str, Any]] = None  # BUG #3 FIX: Added for size calculation
    ) -> str:
        """
        Generate mask for inpainting

        White pixels (255) = area to inpaint (replace/add furniture)
        Black pixels (0) = area to preserve (keep room structure)
        """
        try:
            # Decode base image
            image_bytes = self._decode_base64_image(base_image)
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size

            # Create mask (start with all black = preserve everything)
            mask = np.zeros((height, width), dtype=np.uint8)

            # BUG #2 FIX: For replace actions in two-pass inpainting, the furniture has
            # already been removed in Pass 1. So in Pass 2, we place new furniture at
            # the location where the old furniture was removed (for replace_one) or
            # centered (for replace_all).
            if user_action == "replace_one" and existing_furniture:
                # OPTION A FIX: Mask at the location of ONE detected furniture item
                # Use bounding box of the FIRST detected furniture item
                furniture = existing_furniture[0]
                furniture_type = furniture.get('object_type', 'furniture')

                # Get product to place for sizing
                product = products_to_place[0] if products_to_place else {}
                product_name = product.get('full_name') or product.get('name', furniture_type)

                # Get dimensions from product (for accurate sizing of new furniture)
                dimensions = product.get('dimensions')
                if not dimensions:
                    dimensions = self._get_typical_dimensions_by_category(product_name)

                # Get position from detected furniture
                position = furniture.get('position', 'center')
                if not isinstance(position, str):
                    position = "center"

                # Use bounding box if available
                if furniture.get('bounding_box'):
                    bbox = furniture['bounding_box']
                    x1 = int(bbox.get('x1', 0))
                    y1 = int(bbox.get('y1', 0))
                    x2 = int(bbox.get('x2', width))
                    y2 = int(bbox.get('y2', height))
                    logger.info(f"REPLACE_ONE: Using bounding box of detected {furniture_type} at ({x1},{y1})-({x2},{y2})")
                else:
                    # Calculate position from detected furniture's position descriptor
                    pixel_size = self._calculate_furniture_size_with_perspective(
                        dimensions, width, height, position
                    )
                    furn_width, furn_height = pixel_size

                    # Position map for calculating center coordinates
                    pos_map = {
                        "center": (0.5, 0.6),
                        "left": (0.25, 0.6),
                        "right": (0.75, 0.6),
                        "center-left": (0.35, 0.6),
                        "center-right": (0.65, 0.6),
                        "foreground": (0.5, 0.75),
                        "background": (0.5, 0.4),
                    }
                    pos_x_norm, pos_y_norm = pos_map.get(position.lower(), (0.5, 0.6))
                    center_x = int(width * pos_x_norm)
                    center_y = int(height * pos_y_norm)

                    # Add 10% padding for natural placement
                    mask_width = int(furn_width * 1.1)
                    mask_height = int(furn_height * 1.1)

                    x1 = max(0, center_x - mask_width // 2)
                    y1 = max(0, center_y - mask_height // 2)
                    x2 = min(width, center_x + mask_width // 2)
                    y2 = min(height, center_y + mask_height // 2)
                    logger.info(f"REPLACE_ONE: Using position '{position}' of detected {furniture_type} at ({center_x},{center_y})")

                mask[y1:y2, x1:x2] = 255
                logger.info(f"REPLACE_ONE: Generated mask for {product_name} at detected {furniture_type} location")

            elif user_action == "replace_all":
                # REPLACE_ALL: Use centered mask (after removing ALL furniture in Pass 1)
                # Use product dimensions to create TIGHT, PRECISE mask for SINGLE product

                # Calculate actual furniture dimensions from products_to_place
                if products_to_place and len(products_to_place) > 0:
                    product = products_to_place[0]
                    product_name = product.get('full_name') or product.get('name', 'sofa')

                    # Get dimensions from product or use typical dimensions
                    dimensions = product.get('dimensions')
                    if not dimensions:
                        dimensions = self._get_typical_dimensions_by_category(product_name)

                    # Calculate pixel size based on dimensions
                    pixel_size = self._calculate_furniture_size_with_perspective(
                        dimensions, width, height, "center"
                    )
                    furn_width, furn_height = pixel_size

                    # CRITICAL: Create TIGHT mask sized exactly for ONE product
                    # Add small padding (10%) for natural placement
                    mask_width = int(furn_width * 1.1)
                    mask_height = int(furn_height * 1.1)

                    # Center the mask
                    center_x = width // 2
                    center_y = int(height * 0.6)  # Slightly below center (typical furniture placement)

                    x1 = max(0, center_x - mask_width // 2)
                    y1 = max(0, center_y - mask_height // 2)
                    x2 = min(width, center_x + mask_width // 2)
                    y2 = min(height, center_y + mask_height // 2)

                    mask[y1:y2, x1:x2] = 255
                    logger.info(f"REPLACE_ALL: Generated TIGHT centered mask for single {product_name}: {mask_width}x{mask_height}px")
                else:
                    # Fallback: Use smaller generic mask (was 60%, now 35%)
                    region_height = int(height * 0.35)
                    region_y_start = height - region_height
                    region_width = int(width * 0.35)
                    region_x_start = int(width * 0.325)
                    mask[region_y_start:height, region_x_start:region_x_start+region_width] = 255
                    logger.info(f"REPLACE_ALL: Generated generic centered mask (35%)")

            elif user_action in ["replace_one_legacy", "replace_all_legacy"] and existing_furniture:
                # OLD BEHAVIOR: For replacement without two-pass (kept for fallback)
                # mark existing furniture locations for inpainting
                for furniture in existing_furniture:
                    # Try to get real dimensions or estimate from type
                    dimensions = {}
                    if furniture.get("dimensions"):
                        dimensions = self._parse_dimensions(furniture["dimensions"])
                    elif furniture.get("object_type"):
                        dimensions = self._get_typical_dimensions_by_category(furniture["object_type"])
                    elif furniture.get("name"):
                        dimensions = self._get_typical_dimensions_by_category(furniture["name"])

                    # Get position (ensure it's a string)
                    position = furniture.get("position", "center")
                    if not isinstance(position, str):
                        position = "center"

                    # Calculate size with perspective and dimensions
                    if dimensions:
                        pixel_size = self._calculate_furniture_size_with_perspective(
                            dimensions, width, height, position
                        )
                        furn_width, furn_height = pixel_size

                        # Get position coordinates
                        pos_map = {
                            "center": (0.5, 0.6),
                            "left": (0.25, 0.6),
                            "right": (0.75, 0.6),
                            "center-left": (0.35, 0.6),
                            "center-right": (0.65, 0.6),
                            "foreground": (0.5, 0.75),
                            "background": (0.5, 0.4),
                        }
                        pos_x_norm, pos_y_norm = pos_map.get(position.lower(), (0.5, 0.6))
                        center_x = int(width * pos_x_norm)
                        center_y = int(height * pos_y_norm)

                        x1 = max(0, center_x - furn_width // 2)
                        y1 = max(0, center_y - furn_height // 2)
                        x2 = min(width, center_x + furn_width // 2)
                        y2 = min(height, center_y + furn_height // 2)

                        logger.info(f"Dimension-based mask: {furniture.get('object_type', 'furniture')} {furn_width}x{furn_height}px at ({center_x},{center_y})")
                    else:
                        # Fallback to old method if no dimensions
                        bbox = self._estimate_furniture_bbox(
                            position,
                            furniture.get("size", "medium"),
                            width,
                            height
                        )
                        x1, y1, x2, y2 = bbox
                        logger.info(f"Heuristic mask: {furniture.get('object_type', 'furniture')} at bbox ({x1},{y1})-({x2},{y2})")

                    # Fill the bounding box with white (inpaint this area)
                    mask[y1:y2, x1:x2] = 255

                    if user_action == "replace_one_legacy":
                        # Only replace one piece, so break after first
                        break

            elif user_action == "add" or not existing_furniture:
                # BUG #3 FIX: Also reduce "add" mask size (was 60%, now use product dimensions)
                if products_to_place and len(products_to_place) > 0:
                    product = products_to_place[0]
                    product_name = product.get('full_name') or product.get('name', 'furniture')

                    # Get dimensions
                    dimensions = product.get('dimensions')
                    if not dimensions:
                        dimensions = self._get_typical_dimensions_by_category(product_name)

                    # Calculate pixel size
                    pixel_size = self._calculate_furniture_size_with_perspective(
                        dimensions, width, height, "center"
                    )
                    furn_width, furn_height = pixel_size

                    # Create TIGHT mask with 10% padding
                    mask_width = int(furn_width * 1.1)
                    mask_height = int(furn_height * 1.1)

                    center_x = width // 2
                    center_y = int(height * 0.6)

                    x1 = max(0, center_x - mask_width // 2)
                    y1 = max(0, center_y - mask_height // 2)
                    x2 = min(width, center_x + mask_width // 2)
                    y2 = min(height, center_y + mask_height // 2)

                    mask[y1:y2, x1:x2] = 255
                    logger.info(f"BUG #3 FIX (add): Generated TIGHT mask for {product_name}: {mask_width}x{mask_height}px")
                else:
                    # Fallback: Reduced from 60% to 35%
                    region_height = int(height * 0.35)
                    region_y_start = height - region_height
                    region_width = int(width * 0.35)
                    region_x_start = int(width * 0.325)
                    mask[region_y_start:height, region_x_start:region_x_start+region_width] = 255
                    logger.info(f"BUG #3 FIX (add): Generic mask reduced to 35%")

            # Convert mask to base64
            mask_image = Image.fromarray(mask, mode='L')
            buffered = io.BytesIO()
            mask_image.save(buffered, format="PNG")
            mask_base64 = base64.b64encode(buffered.getvalue()).decode()

            logger.info(f"Generated mask for action '{user_action}' with {np.sum(mask > 0)} inpaint pixels")
            return f"data:image/png;base64,{mask_base64}"

        except Exception as e:
            logger.error(f"Error generating mask: {e}", exc_info=True)
            logger.error(f"user_action={user_action}, existing_furniture={existing_furniture}")
            # Return empty mask (preserve entire image) on error
            mask = np.zeros((512, 512), dtype=np.uint8)
            mask_image = Image.fromarray(mask, mode='L')
            buffered = io.BytesIO()
            mask_image.save(buffered, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"

    def _estimate_furniture_bbox(
        self,
        position: str,
        size: str,
        width: int,
        height: int
    ) -> Tuple[int, int, int, int]:
        """
        Estimate bounding box for furniture based on position description

        Returns: (x1, y1, x2, y2)
        """
        # Size multipliers
        size_mult = {
            "small": 0.15,
            "medium": 0.25,
            "large": 0.35
        }.get(size, 0.25)

        # Calculate furniture dimensions
        furn_width = int(width * size_mult)
        furn_height = int(height * size_mult * 0.8)  # Furniture is typically wider than tall

        # Position mapping (normalized coordinates)
        position_map = {
            "center": (0.5, 0.6),
            "left": (0.25, 0.6),
            "right": (0.75, 0.6),
            "center-left": (0.35, 0.6),
            "center-right": (0.65, 0.6),
            "foreground": (0.5, 0.75),
            "background": (0.5, 0.4),
        }

        # Get position coordinates (default to center if not found)
        pos_x, pos_y = position_map.get(position.lower(), (0.5, 0.6))

        # Calculate bounding box
        center_x = int(width * pos_x)
        center_y = int(height * pos_y)

        x1 = max(0, center_x - furn_width // 2)
        y1 = max(0, center_y - furn_height // 2)
        x2 = min(width, center_x + furn_width // 2)
        y2 = min(height, center_y + furn_height // 2)

        return (x1, y1, x2, y2)

    def _build_furniture_prompt(
        self,
        products: List[Dict[str, Any]],
        user_action: str
    ) -> str:
        """Build prompt for furniture placement with visual descriptions from product images"""
        product_descriptions = []

        for product in products:
            # Check if we have visual description from Gemini Vision analysis
            if product.get('visual_description'):
                # Use the detailed visual description
                product_descriptions.append(product['visual_description'])
            else:
                # Fallback to product name
                name = product.get('full_name') or product.get('name', 'furniture')
                product_descriptions.append(name)

        # BUG #1 FIX: Determine quantity - default to 1 to prevent duplication
        quantity = len(products)  # Number of different products

        # Combine product descriptions
        if len(product_descriptions) == 1:
            product_desc = product_descriptions[0]
        else:
            product_desc = ", ".join(product_descriptions[:-1]) + f" and {product_descriptions[-1]}"

        # BUG #1 FIX: Add explicit quantity control to prevent SDXL from creating duplicates/pairs
        # Build detailed prompt with STRICT quantity enforcement
        if quantity == 1:
            # CRITICAL: Single product - prevent duplication with ULTRA-STRICT language
            prompt = f"A photorealistic interior photo with a single {product_desc} placed in the room. "
            prompt += "CRITICAL INSTRUCTION: Place ONE and ONLY ONE furniture item. "
            prompt += "STRICTLY FORBIDDEN: multiple copies, duplicate items, matching pairs, two chairs, symmetrical arrangement, mirrored placement, furniture sets. "
            prompt += "REQUIRED: singular furniture piece, solo item, individual chair, one unit only. "
            prompt += "COUNT VERIFICATION: exactly 1 item total, not 2, not a pair, not twins. "
        else:
            # Multiple different products
            prompt = f"A photorealistic interior photo showing {product_desc} placed naturally in the room. "

        prompt += "The furniture should have realistic lighting, proper shadows on the floor, and match the room's perspective. "
        prompt += "Professional interior photography, high quality, detailed textures, natural placement, proper scale and proportions. "

        if user_action == "replace_all":
            prompt += "The room layout, walls, floor, and windows remain exactly the same. "

        logger.info(f"BUG #1 FIX: Built prompt with quantity={quantity} enforcement: {prompt[:150]}...")
        return prompt

    def _build_negative_prompt(self) -> str:
        """Build negative prompt to avoid unwanted elements"""
        # BUG #1 & #2 FIX: ULTRA-STRONG negative prompt against duplication
        negative_prompt = "blurry, floating furniture, unrealistic shadows, distorted proportions, "
        negative_prompt += "cartoon, illustration, drawing, different room, changed walls, changed floor, "
        negative_prompt += "low quality, artifacts, "
        # CRITICAL: Prevent any form of duplication
        negative_prompt += "duplicates, multiple copies, pairs, two items, matching pair, symmetrical furniture, "
        negative_prompt += "matching set, twin chairs, double furniture, mirrored placement, repeated items, "
        negative_prompt += "furniture set, multiple units, two chairs, 2 chairs, pair of chairs, chair pair, "
        negative_prompt += "identical copies, cloned furniture, replicated items"
        return negative_prompt

    async def _generate_furniture_with_ip_adapter(
        self,
        product_image_url: str,
        product: Dict[str, Any],
        mask_dimensions: str
    ) -> Optional[str]:
        """
        STEP 1: Generate exact furniture image using IP-Adapter SDXL

        This creates an isolated, clean furniture image that matches the product reference
        exactly, which will then be used in Step 2 (inpainting into the room)

        Args:
            product_image_url: URL to product reference image
            product: Product dictionary with name, dimensions, etc.
            mask_dimensions: Dimensions for the generated furniture

        Returns:
            Base64 encoded furniture image, or None if generation fails
        """
        try:
            product_name = product.get('full_name') or product.get('name', 'furniture')

            # Build prompt for clean, isolated furniture generation
            prompt = (
                f"A professional product photo of a single {product_name}, "
                f"isolated on a clean white background, studio lighting, "
                f"high quality, detailed textures, front view, "
                f"photorealistic, product photography"
            )

            negative_prompt = (
                "room, interior, floor, walls, background objects, "
                "multiple items, people, text, watermark, "
                "low quality, blurry, distorted"
            )

            logger.info(f"Generating furniture with IP-Adapter: {product_name}")
            logger.info(f"Reference image: {product_image_url[:100]}...")

            # Call IP-Adapter SDXL model
            model_input = {
                "image": product_image_url,  # Product reference image
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "scale": 0.8,  # High influence from reference image
                "num_inference_steps": 30,
                "num_outputs": 1
            }

            output = await asyncio.to_thread(
                replicate.run,
                self.model_ip_adapter_sdxl,
                input=model_input
            )

            # Get output URL
            if isinstance(output, list) and len(output) > 0:
                output_url = output[0]
            elif isinstance(output, str):
                output_url = output
            else:
                raise ValueError(f"Unexpected output format: {type(output)}")

            # Download and encode the generated furniture image
            furniture_image = await self._download_and_encode_image(output_url)

            logger.info(f"IP-Adapter furniture generation successful")
            return furniture_image

        except Exception as e:
            logger.error(f"IP-Adapter furniture generation failed: {e}", exc_info=True)
            return None

    def _build_furniture_prompt_with_reference(
        self,
        products: List[Dict[str, Any]],
        user_action: str,
        furniture_reference_image: str
    ) -> str:
        """
        Build prompt for inpainting using IP-Adapter generated furniture as visual reference

        Args:
            products: List of products being placed
            user_action: User action (replace_one, etc.)
            furniture_reference_image: Base64 encoded furniture image from IP-Adapter

        Returns:
            Enhanced prompt string
        """
        product_name = products[0].get('full_name') or products[0].get('name', 'furniture')

        # Since we have the exact furniture from IP-Adapter, our prompt focuses on
        # natural placement, lighting, and perspective matching
        prompt = (
            f"A photorealistic interior photo with a {product_name} naturally placed in the room. "
            f"The furniture matches the exact style, color, and design from the reference. "
            f"Realistic lighting that matches the room's lighting, "
            f"proper shadows on the floor, correct perspective and scale, "
            f"seamless integration with the room environment. "
            f"Professional interior photography, high quality, natural placement."
        )

        if user_action == "replace_all":
            prompt += " The room layout, walls, floor, and windows remain exactly the same. "

        logger.info(f"Built prompt with IP-Adapter reference: {prompt[:150]}...")
        return prompt

    def _build_furniture_prompt_from_vision(
        self,
        products: List[Dict[str, Any]],
        user_action: str,
        visual_description: str
    ) -> str:
        """
        FALLBACK: Build ultra-detailed prompt using Gemini Vision analysis

        When IP-Adapter fails, use Gemini Vision's detailed product description
        to create a rich text prompt for inpainting

        Args:
            products: List of products being placed
            user_action: User action (replace_one, etc.)
            visual_description: Detailed visual description from Gemini Vision

        Returns:
            Enhanced prompt string with visual details
        """
        product_name = products[0].get('full_name') or products[0].get('name', 'furniture')

        # Build ultra-detailed prompt using Gemini Vision analysis
        prompt = (
            f"A photorealistic interior photo with a {product_name} naturally placed in the room. "
            f"The furniture has the following exact characteristics: {visual_description}. "
            f"Realistic lighting that matches the room's lighting, "
            f"proper shadows on the floor, correct perspective and scale, "
            f"seamless integration with the room environment. "
            f"Professional interior photography, high quality, natural placement, "
            f"accurate materials and textures."
        )

        if user_action == "replace_all":
            prompt += " The room layout, walls, floor, and windows remain exactly the same. "

        logger.info(f"Built Gemini Vision-enhanced prompt: {prompt[:150]}...")
        return prompt

    async def _run_sdxl_inpainting(self, request: InpaintingRequest) -> InpaintingResult:
        """Run SDXL inpainting via Replicate API (Step 2 of two-step workflow)"""
        try:
            # CRITICAL: Resize images to 512x512 to avoid tensor dimension mismatches
            # Decode base image
            image_bytes = self._decode_base64_image(request.base_image)
            base_img = Image.open(io.BytesIO(image_bytes))
            original_size = base_img.size

            # Resize to 512x512
            base_img_resized = base_img.resize((512, 512), Image.Resampling.LANCZOS)

            # Re-encode base image
            buffered_img = io.BytesIO()
            base_img_resized.save(buffered_img, format="PNG")
            image_base64 = base64.b64encode(buffered_img.getvalue()).decode()
            image_data_url = f"data:image/png;base64,{image_base64}"

            # Decode and resize mask
            mask_bytes = self._decode_base64_image(request.mask)
            mask_img = Image.open(io.BytesIO(mask_bytes))
            mask_img_resized = mask_img.resize((512, 512), Image.Resampling.LANCZOS)

            # Re-encode mask
            buffered_mask = io.BytesIO()
            mask_img_resized.save(buffered_mask, format="PNG")
            mask_base64 = base64.b64encode(buffered_mask.getvalue()).decode()
            mask_data_url = f"data:image/png;base64,{mask_base64}"

            logger.info(f"Resized images: {original_size} → 512x512 for model compatibility")

            # Use standard SDXL inpainting model
            model = self.model_sdxl
            logger.info(f"Running SDXL inpainting with prompt: {request.prompt[:100]}...")

            model_input = {
                "image": image_data_url,
                "mask": mask_data_url,
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "num_inference_steps": 35,  # Increased for better quality
                "guidance_scale": 9.5,  # INCREASED from 7.5 to 9.5 for stricter prompt adherence (prevent duplication)
                "strength": 0.99,  # High strength for complete replacement
            }

            # Run the model
            output = await asyncio.to_thread(
                replicate.run,
                model,
                input=model_input
            )

            # Output is a URL to the generated image
            if isinstance(output, list) and len(output) > 0:
                output_url = output[0]
            elif isinstance(output, str):
                output_url = output
            else:
                raise ValueError(f"Unexpected output format: {type(output)}")

            # Download the result image
            result_image_base64 = await self._download_and_encode_image(output_url)

            # Resize result back to original size
            result_bytes = self._decode_base64_image(result_image_base64)
            result_img = Image.open(io.BytesIO(result_bytes))
            result_img_original_size = result_img.resize(original_size, Image.Resampling.LANCZOS)

            # Re-encode to base64
            buffered_result = io.BytesIO()
            result_img_original_size.save(buffered_result, format="PNG")
            final_result_base64 = base64.b64encode(buffered_result.getvalue()).decode()
            final_result_data_url = f"data:image/png;base64,{final_result_base64}"

            logger.info(f"Resized result back: 512x512 → {original_size}")

            return InpaintingResult(
                rendered_image=final_result_data_url,
                processing_time=0.0,  # Timing handled by caller
                success=True
            )

        except Exception as e:
            logger.error(f"SDXL inpainting failed: {e}", exc_info=True)
            return InpaintingResult(
                rendered_image=request.base_image,
                processing_time=0.0,
                success=False,
                error_message=str(e)
            )

    async def _remove_existing_furniture(
        self,
        base_image: str,
        furniture_to_remove: List[Dict[str, Any]],
        remove_all: bool = True
    ) -> InpaintingResult:
        """
        BUG #2 FIX: Remove existing furniture by inpainting with empty space

        This is Pass 1 of two-pass inpainting for replace actions.

        Args:
            base_image: Base64 encoded room image
            furniture_to_remove: List of furniture detections to remove
            remove_all: If True, remove all furniture. If False, remove only the first one.

        Returns:
            InpaintingResult with cleaned image (furniture removed)
        """
        try:
            logger.info(f"BUG #2 FIX: Removing {len(furniture_to_remove)} furniture item(s)")

            # Generate mask for furniture removal
            removal_mask = await self._generate_removal_mask_from_detections(
                base_image=base_image,
                furniture_detections=furniture_to_remove,
                remove_all=remove_all
            )

            # Build prompt for clean empty space
            furniture_types = [f.get('object_type', 'furniture') for f in furniture_to_remove]
            furniture_list = ", ".join(set(furniture_types))  # Deduplicate

            # Prompt: Ask for clean empty floor where furniture was
            removal_prompt = (
                f"A photorealistic interior photo with clean empty floor space where the {furniture_list} was removed. "
                "The room layout, walls, floor pattern, windows, and lighting remain exactly the same. "
                "Natural empty floor, no furniture in the cleared area, consistent floor texture, realistic lighting. "
                "Professional interior photography, high quality, seamless removal."
            )

            # Negative prompt: Avoid generating new furniture
            removal_negative_prompt = (
                f"furniture, {furniture_list}, objects, items, decorations, "
                "floating objects, artifacts, inconsistent floor, different room, changed walls, "
                "blurry, low quality, distorted"
            )

            logger.info(f"BUG #2 FIX: Removal prompt: {removal_prompt[:100]}...")

            # Create inpainting request for removal
            removal_request = InpaintingRequest(
                base_image=base_image,
                mask=removal_mask,
                prompt=removal_prompt,
                negative_prompt=removal_negative_prompt,
                products=None,  # No products for removal pass
                product_image_url=None  # No IP-Adapter needed for removal
            )

            # Run SDXL inpainting to remove furniture
            result = await self._run_sdxl_inpainting(removal_request)

            if result.success:
                logger.info(f"BUG #2 FIX: Successfully removed furniture, cleaned image ready for Pass 2")
            else:
                logger.error(f"BUG #2 FIX: Furniture removal failed: {result.error_message}")

            return result

        except Exception as e:
            logger.error(f"BUG #2 FIX: Error in _remove_existing_furniture: {e}", exc_info=True)
            return InpaintingResult(
                rendered_image=base_image,
                processing_time=0.0,
                success=False,
                error_message=f"Furniture removal failed: {str(e)}"
            )

    async def _generate_removal_mask_from_detections(
        self,
        base_image: str,
        furniture_detections: List[Dict[str, Any]],
        remove_all: bool = True
    ) -> str:
        """
        BUG #2 FIX: Generate mask for removing detected furniture

        White pixels (255) = remove furniture (inpaint area)
        Black pixels (0) = preserve room (keep as-is)

        Args:
            base_image: Base64 encoded image
            furniture_detections: List of furniture with positions and dimensions
            remove_all: If True, mask all furniture. If False, mask only first one.

        Returns:
            Base64 encoded mask image
        """
        try:
            # Decode base image to get dimensions
            image_bytes = self._decode_base64_image(base_image)
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size

            # Create mask (start with all black = preserve everything)
            mask = np.zeros((height, width), dtype=np.uint8)

            # Mark each furniture location for removal
            for idx, furniture in enumerate(furniture_detections):
                # Get dimensions
                dimensions = {}
                if furniture.get("dimensions"):
                    dimensions = self._parse_dimensions(furniture["dimensions"])
                elif furniture.get("object_type"):
                    dimensions = self._get_typical_dimensions_by_category(furniture["object_type"])
                elif furniture.get("name"):
                    dimensions = self._get_typical_dimensions_by_category(furniture["name"])

                # Get position
                position = furniture.get("position", "center")
                if not isinstance(position, str):
                    position = "center"

                # Calculate size and position
                if dimensions:
                    pixel_size = self._calculate_furniture_size_with_perspective(
                        dimensions, width, height, position
                    )
                    furn_width, furn_height = pixel_size

                    # Get position coordinates
                    pos_map = {
                        "center": (0.5, 0.6),
                        "left": (0.25, 0.6),
                        "right": (0.75, 0.6),
                        "center-left": (0.35, 0.6),
                        "center-right": (0.65, 0.6),
                        "foreground": (0.5, 0.75),
                        "background": (0.5, 0.4),
                    }
                    pos_x_norm, pos_y_norm = pos_map.get(position.lower(), (0.5, 0.6))
                    center_x = int(width * pos_x_norm)
                    center_y = int(height * pos_y_norm)

                    x1 = max(0, center_x - furn_width // 2)
                    y1 = max(0, center_y - furn_height // 2)
                    x2 = min(width, center_x + furn_width // 2)
                    y2 = min(height, center_y + furn_height // 2)

                    logger.info(f"BUG #2 FIX: Removal mask for {furniture.get('object_type', 'furniture')}: {furn_width}x{furn_height}px at ({center_x},{center_y})")
                else:
                    # Fallback to heuristic bbox
                    bbox = self._estimate_furniture_bbox(
                        position,
                        furniture.get("size", "medium"),
                        width,
                        height
                    )
                    x1, y1, x2, y2 = bbox
                    logger.info(f"BUG #2 FIX: Removal mask (heuristic) for {furniture.get('object_type', 'furniture')}: bbox ({x1},{y1})-({x2},{y2})")

                # Fill the bounding box with white (remove this area)
                mask[y1:y2, x1:x2] = 255

                # If remove_all is False, only remove the first one
                if not remove_all:
                    break

            # Convert mask to base64
            mask_image = Image.fromarray(mask, mode='L')
            buffered = io.BytesIO()
            mask_image.save(buffered, format="PNG")
            mask_base64 = base64.b64encode(buffered.getvalue()).decode()

            logger.info(f"BUG #2 FIX: Generated removal mask with {np.sum(mask > 0)} pixels to inpaint")
            return f"data:image/png;base64,{mask_base64}"

        except Exception as e:
            logger.error(f"BUG #2 FIX: Error generating removal mask: {e}", exc_info=True)
            # Return empty mask on error
            mask = np.zeros((512, 512), dtype=np.uint8)
            mask_image = Image.fromarray(mask, mode='L')
            buffered = io.BytesIO()
            mask_image.save(buffered, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"

    async def _download_and_encode_image(self, url: str) -> str:
        """Download image from URL and encode to base64 with orientation correction"""
        try:
            import aiohttp
            from PIL import ImageOps

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_bytes = await response.read()

                        # ORIENTATION FIX: Load image and correct orientation using EXIF data
                        image = Image.open(io.BytesIO(image_bytes))

                        # Apply EXIF orientation correction (rotates image to correct orientation)
                        image = ImageOps.exif_transpose(image)

                        # Convert back to bytes
                        buffered = io.BytesIO()
                        image_format = image.format or 'PNG'
                        image.save(buffered, format=image_format)
                        corrected_bytes = buffered.getvalue()

                        image_base64 = base64.b64encode(corrected_bytes).decode()
                        logger.info(f"Downloaded and orientation-corrected image from {url[:100]}...")
                        return f"data:image/{image_format.lower()};base64,{image_base64}"
                    else:
                        raise Exception(f"Failed to download image: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            raise

    def _decode_base64_image(self, image_data: str) -> bytes:
        """Decode base64 image data"""
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        return base64.b64decode(image_data)

    def _parse_dimensions(self, dimension_str: str) -> Dict[str, float]:
        """
        Parse dimension string into structured dict

        Supports formats:
        - "72W x 36D x 30H inches"
        - "72\" W x 36\" D x 30\" H"
        - {"width": 72, "depth": 36, "height": 30}
        """
        if not dimension_str:
            return {}

        # If already a dict, return it directly
        if isinstance(dimension_str, dict):
            return dimension_str

        # Ensure we have a string
        if not isinstance(dimension_str, str):
            logger.warning(f"dimensions is not a string: {type(dimension_str)} = {dimension_str}")
            return {}

        # Try JSON format first
        try:
            parsed = json.loads(dimension_str)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # Parse text format
        dimensions = {}

        # Extract width (W, Width, w)
        width_match = re.search(r'(\d+(?:\.\d+)?)\s*["\']?\s*(?:W|Width|width)', dimension_str, re.IGNORECASE)
        if width_match:
            dimensions["width"] = float(width_match.group(1))

        # Extract depth (D, Depth, depth)
        depth_match = re.search(r'(\d+(?:\.\d+)?)\s*["\']?\s*(?:D|Depth|depth)', dimension_str, re.IGNORECASE)
        if depth_match:
            dimensions["depth"] = float(depth_match.group(1))

        # Extract height (H, Height, height)
        height_match = re.search(r'(\d+(?:\.\d+)?)\s*["\']?\s*(?:H|Height|height)', dimension_str, re.IGNORECASE)
        if height_match:
            dimensions["height"] = float(height_match.group(1))

        # If no labeled dimensions found, try simple "72 x 36 x 30" format
        if not dimensions:
            simple_match = re.findall(r'(\d+(?:\.\d+)?)', dimension_str)
            if len(simple_match) >= 3:
                dimensions = {
                    "width": float(simple_match[0]),
                    "depth": float(simple_match[1]),
                    "height": float(simple_match[2])
                }
            elif len(simple_match) == 2:
                dimensions = {
                    "width": float(simple_match[0]),
                    "height": float(simple_match[1])
                }

        return dimensions

    def _get_typical_dimensions_by_category(self, product_name: str) -> Dict[str, float]:
        """
        Get typical dimensions for furniture types when real dimensions unavailable
        All dimensions in inches
        """
        name_lower = product_name.lower()

        # Sofas and seating
        if 'sectional' in name_lower:
            return {"width": 120, "depth": 40, "height": 36}
        elif 'sofa' in name_lower or 'couch' in name_lower:
            return {"width": 84, "depth": 36, "height": 36}
        elif 'loveseat' in name_lower:
            return {"width": 60, "depth": 36, "height": 36}
        elif 'armchair' in name_lower or 'accent chair' in name_lower:
            return {"width": 32, "depth": 34, "height": 36}
        elif 'recliner' in name_lower:
            return {"width": 36, "depth": 40, "height": 42}
        elif 'chair' in name_lower:
            return {"width": 24, "depth": 24, "height": 36}

        # Tables
        elif 'coffee table' in name_lower or 'center table' in name_lower:
            return {"width": 48, "depth": 24, "height": 18}
        elif 'side table' in name_lower or 'end table' in name_lower:
            return {"width": 24, "depth": 18, "height": 24}
        elif 'console table' in name_lower:
            return {"width": 60, "depth": 16, "height": 30}
        elif 'dining table' in name_lower:
            return {"width": 72, "depth": 40, "height": 30}
        elif 'desk' in name_lower:
            return {"width": 60, "depth": 30, "height": 30}
        elif 'table' in name_lower:
            return {"width": 48, "depth": 30, "height": 30}

        # Beds
        elif 'king bed' in name_lower or 'king size' in name_lower:
            return {"width": 76, "depth": 80, "height": 24}
        elif 'queen bed' in name_lower or 'queen size' in name_lower:
            return {"width": 60, "depth": 80, "height": 24}
        elif 'full bed' in name_lower or 'double bed' in name_lower:
            return {"width": 54, "depth": 75, "height": 24}
        elif 'twin bed' in name_lower:
            return {"width": 38, "depth": 75, "height": 24}
        elif 'bed' in name_lower:
            return {"width": 60, "depth": 80, "height": 24}

        # Storage
        elif 'nightstand' in name_lower or 'bedside table' in name_lower:
            return {"width": 24, "depth": 18, "height": 24}
        elif 'dresser' in name_lower:
            return {"width": 60, "depth": 18, "height": 36}
        elif 'chest' in name_lower or 'drawer' in name_lower:
            return {"width": 36, "depth": 18, "height": 48}
        elif 'bookcase' in name_lower or 'bookshelf' in name_lower:
            return {"width": 36, "depth": 12, "height": 72}
        elif 'cabinet' in name_lower:
            return {"width": 48, "depth": 18, "height": 42}

        # Ottomans and benches
        elif 'ottoman' in name_lower:
            return {"width": 36, "depth": 24, "height": 18}
        elif 'bench' in name_lower:
            return {"width": 48, "depth": 16, "height": 18}

        # Lighting
        elif 'floor lamp' in name_lower:
            return {"width": 12, "depth": 12, "height": 60}
        elif 'table lamp' in name_lower:
            return {"width": 8, "depth": 8, "height": 24}

        # Default for unknown types
        return {"width": 48, "depth": 30, "height": 30}

    def _calculate_furniture_size_with_perspective(
        self,
        product_dimensions: Dict[str, float],
        room_image_width: int,
        room_image_height: int,
        placement_position: str
    ) -> Tuple[int, int]:
        """
        Calculate furniture size in pixels based on real dimensions and perspective

        Args:
            product_dimensions: Real furniture dimensions in inches {"width": 72, "depth": 36, "height": 30}
            room_image_width: Image width in pixels
            room_image_height: Image height in pixels
            placement_position: "foreground", "center", "background", etc.

        Returns:
            (pixel_width, pixel_height) for the mask
        """

        # 1. BASE SCALE: Assume standard 12x12 ft room
        # For a 12 ft (144 inches) room width in the image
        base_pixels_per_inch = room_image_width / 144

        # 2. PERSPECTIVE SCALING: Objects further away appear smaller
        perspective_scale = {
            "foreground": 1.3,     # 30% larger (closer to camera)
            "center": 1.0,         # Base size
            "center-left": 1.0,
            "center-right": 1.0,
            "left": 1.0,
            "right": 1.0,
            "background": 0.7,     # 30% smaller (further from camera)
        }.get(placement_position.lower(), 1.0)

        # 3. CALCULATE PIXEL DIMENSIONS
        real_width = product_dimensions.get("width", 60)
        real_height = product_dimensions.get("height", 30)

        # Use width as primary dimension (front-facing view)
        pixel_width = int(real_width * base_pixels_per_inch * perspective_scale)

        # Height with vertical compression (camera angle effect)
        # Typical camera angle makes vertical dimensions appear ~60-80% of actual
        vertical_compression = 0.7
        pixel_height = int(real_height * base_pixels_per_inch * perspective_scale * vertical_compression)

        # 4. CLAMP TO REASONABLE BOUNDS
        # Furniture should be between 10% and 45% of image dimensions
        min_width = int(room_image_width * 0.10)
        max_width = int(room_image_width * 0.45)
        min_height = int(room_image_height * 0.10)
        max_height = int(room_image_height * 0.45)

        pixel_width = max(min_width, min(pixel_width, max_width))
        pixel_height = max(min_height, min(pixel_height, max_height))

        logger.info(f"Calculated size: {real_width}\"W x {real_height}\"H → {pixel_width}px x {pixel_height}px (perspective: {perspective_scale}x)")

        return (pixel_width, pixel_height)

    async def _get_product_dimensions_from_db(self, product_id: int) -> Optional[Dict[str, float]]:
        """
        Fetch product dimensions from database

        Returns dimensions in inches: {"width": 72, "depth": 36, "height": 30}
        """
        try:
            from sqlalchemy import select
            from database.models import ProductAttribute
            from core.database import get_db

            # Get database session (this is simplified - in production use dependency injection)
            async for db in get_db():
                # Query dimensions attribute
                query = select(ProductAttribute).where(
                    ProductAttribute.product_id == product_id,
                    ProductAttribute.attribute_name.in_(['dimensions', 'dimension', 'size'])
                )

                result = await db.execute(query)
                dimension_attr = result.scalar_one_or_none()

                if dimension_attr:
                    dimensions = self._parse_dimensions(dimension_attr.attribute_value)
                    if dimensions:
                        logger.info(f"Found dimensions for product {product_id}: {dimensions}")
                        return dimensions

                break  # Exit after first iteration

        except Exception as e:
            logger.warning(f"Could not fetch dimensions from DB for product {product_id}: {e}")

        return None

    async def _get_product_image_from_db(self, product_id: int) -> Optional[str]:
        """
        Fetch primary product image URL from database

        Returns: Image URL string or None
        """
        try:
            from sqlalchemy import select
            from database.models import ProductImage
            from core.database import get_db

            async for db in get_db():
                # Query for primary image or first image
                query = select(ProductImage).where(
                    ProductImage.product_id == product_id
                ).order_by(
                    ProductImage.is_primary.desc(),
                    ProductImage.display_order.asc()
                ).limit(1)

                result = await db.execute(query)
                image = result.scalar_one_or_none()

                if image:
                    # Prefer higher quality images
                    image_url = image.large_url or image.medium_url or image.original_url
                    logger.info(f"Found product image for product {product_id}: {image_url[:100]}")
                    return image_url

                break  # Exit after first iteration

        except Exception as e:
            logger.warning(f"Could not fetch product image from DB for product {product_id}: {e}")

        return None

    async def _analyze_product_image_with_chatgpt(self, image_url: str, product_name: str) -> Optional[str]:
        """
        Use ChatGPT Vision to analyze product image and generate detailed description

        Args:
            image_url: URL to product image
            product_name: Product name for context

        Returns: Detailed visual description including size, color, dimensions, texture, style
        """
        try:
            from services.chatgpt_service import chatgpt_service

            analysis_prompt = f"""Analyze this {product_name} product image and provide a detailed visual description for AI image generation. Focus on:

1. **Size & Dimensions**: Overall size impression (compact, standard, oversized), proportions
2. **Colors**: Exact color names and tones (primary, secondary, accents)
3. **Texture & Materials**: Fabric type, wood grain, metal finish, leather quality, etc.
4. **Style**: Design aesthetic (modern, traditional, mid-century, industrial, minimalist, etc.)
5. **Key Features**: Tufting, patterns, legs, armrests, cushions, hardware, decorative elements
6. **Finish Quality**: Matte, glossy, distressed, polished, brushed, etc.

Format your response as a single paragraph optimized for SDXL image generation prompt. Be specific and descriptive but concise (max 150 words).

Example format: "A modern sofa with soft gray fabric upholstery featuring deep button tufting, wooden legs in natural oak finish with tapered design, three plush seat cushions, rolled arms, mid-century modern aesthetic, matte finish fabric texture..."

Provide ONLY the description, no additional text."""

            # Use ChatGPT Vision to analyze the product image
            description = await chatgpt_service.analyze_image_with_vision(
                image_url=image_url,
                prompt=analysis_prompt
            )

            if description:
                logger.info(f"ChatGPT Vision analysis for {product_name}: {description[:100]}...")
                return description.strip()

        except Exception as e:
            logger.warning(f"Could not analyze product image with ChatGPT Vision: {e}")

        return None

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            **self.usage_stats,
            "success_rate": (
                self.usage_stats["successful_requests"] /
                max(self.usage_stats["total_requests"], 1) * 100
            ),
            "average_processing_time": (
                self.usage_stats["total_processing_time"] /
                max(self.usage_stats["successful_requests"], 1)
            )
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check"""
        try:
            # Simple check - verify API key is set
            if not self.api_key:
                return {
                    "status": "unhealthy",
                    "error": "API key not configured",
                    "service": "replicate_inpainting"
                }

            return {
                "status": "healthy",
                "service": "replicate_inpainting",
                "api_key_configured": True,
                "usage_stats": self.get_usage_stats()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "service": "replicate_inpainting"
            }


# Global service instance
replicate_inpainting_service = ReplicateInpaintingService()
