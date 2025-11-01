"""
Cloud Inpainting Service using Replicate IP-Adapter and Stability AI
Provides production-ready inpainting with hosted APIs
"""
import io
import base64
import logging
import time
import asyncio
from typing import Optional, Dict, List, Any
from PIL import Image, ImageDraw, ImageOps
import numpy as np
import cv2
import aiohttp
import replicate
from functools import wraps

from api.core.config import settings

logger = logging.getLogger(__name__)


def retry_on_connection_error(max_retries=3, initial_delay=2.0):
    """
    Decorator to retry function on connection errors with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds (doubles each retry)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (ConnectionError, ConnectionResetError, BrokenPipeError, OSError) as e:
                    last_exception = e
                    if "Connection reset by peer" in str(e) or "Errno 54" in str(e):
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Connection error on attempt {attempt + 1}/{max_retries}: {e}. "
                                f"Retrying in {delay}s..."
                            )
                            await asyncio.sleep(delay)
                            delay *= 2  # Exponential backoff
                        else:
                            logger.error(f"Max retries ({max_retries}) reached. Last error: {e}")
                            raise
                    else:
                        # Not a connection reset error, don't retry
                        raise
                except Exception as e:
                    # For non-connection errors, don't retry
                    raise

            # If we get here, all retries failed
            raise last_exception

        return wrapper
    return decorator


class InpaintingResult:
    """Result from inpainting operation"""
    def __init__(self, rendered_image: str, processing_time: float, success: bool,
                 error_message: str = "", confidence_score: float = 0.0):
        self.rendered_image = rendered_image
        self.processing_time = processing_time
        self.success = success
        self.error_message = error_message
        self.confidence_score = confidence_score


class CloudInpaintingService:
    """
    Production inpainting service using:
    1. Replicate for IP-Adapter + ControlNet (product reference)
    2. Stability AI for official SDXL inpainting (fastest, highest quality)
    """

    def __init__(self):
        self.replicate_api_key = settings.replicate_api_key
        self.stability_api_key = settings.stability_ai_api_key

        # Set Replicate API token
        if self.replicate_api_key:
            import os
            os.environ["REPLICATE_API_TOKEN"] = self.replicate_api_key
            replicate.api_token = self.replicate_api_key

        self.usage_stats = {
            "total_requests": 0,
            "replicate_requests": 0,
            "stability_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
        }

        logger.info("Cloud Inpainting Service initialized (Replicate + Stability AI)")

    async def inpaint_furniture(
        self,
        base_image: str,
        products_to_place: List[Dict[str, Any]],
        existing_furniture: List[Dict[str, Any]] = None,
        user_action: str = None
    ) -> InpaintingResult:
        """
        Main inpainting method with intelligent service selection

        Strategy:
        1. Try Replicate SDXL first (official SDXL, fast, good quality)
        2. Fallback to Replicate ControlNet if SDXL fails
        3. Try Stability AI if both Replicate options fail
        4. Final fallback to Gemini if all cloud services fail
        """
        start_time = time.time()
        self.usage_stats["total_requests"] += 1

        try:
            logger.info("=" * 80)
            logger.info(f"🔵 STARTING CLOUD INPAINTING")
            logger.info(f"   Products: {len(products_to_place)}")
            logger.info(f"   user_action: {user_action}")
            logger.info(f"   existing_furniture: {len(existing_furniture) if existing_furniture else 0} items")
            logger.info(f"   base_image: {'provided' if base_image else 'MISSING'}")
            logger.info("=" * 80)

            # Decode base image
            room_image = self._decode_base64_image(base_image)

            # Get product images
            product_image_urls = []
            for product in products_to_place:
                if product.get('image_url'):
                    product_image_urls.append(product['image_url'])
                elif product.get('primary_image', {}).get('url'):
                    product_image_urls.append(product['primary_image']['url'])

            if not product_image_urls:
                raise ValueError("No product images provided")

            # Generate mask
            mask = await self._generate_placement_mask(
                room_image=room_image,
                products_to_place=products_to_place,
                existing_furniture=existing_furniture,
                user_action=user_action
            )

            # ENHANCED: Analyze product with ChatGPT Vision for detailed description
            product_vision_description = None
            if product_image_urls:
                logger.info("Analyzing product image with ChatGPT Vision...")
                product_vision_description = await self._analyze_product_with_chatgpt_vision(
                    image_url=product_image_urls[0],
                    product_name=products_to_place[0].get('full_name') or products_to_place[0].get('name', 'furniture')
                )
                if product_vision_description:
                    logger.info(f"ChatGPT Vision description: {product_vision_description[:150]}...")
                    # Store description in product for prompt building
                    products_to_place[0]['visual_description'] = product_vision_description

            # TWO-PASS APPROACH for replace actions
            working_image = room_image

            if user_action in ["replace_one", "replace_all"] and existing_furniture:
                logger.info(f"BUG #2 FIX: Starting two-pass inpainting for {user_action}")

                # PASS 1: Remove existing furniture
                logger.info(f"PASS 1: Removing existing furniture...")
                removal_result = await self._remove_existing_furniture(
                    room_image=room_image,
                    furniture_to_remove=existing_furniture,
                    remove_all=(user_action == "replace_all")
                )

                if removal_result and removal_result.success:
                    # CRITICAL FIX: Decode base64 string back to PIL Image for Pass 2
                    logger.info(f"PASS 1 SUCCESS: Decoding cleaned image for PASS 2")
                    working_image = self._decode_base64_image(removal_result.rendered_image)
                    logger.info(f"PASS 1: Cleaned image decoded, size: {working_image.size}")
                else:
                    logger.warning(f"PASS 1 FAILED: Using original image for PASS 2")
                    working_image = room_image

            # Build prompt (enhanced with ChatGPT Vision if available)
            prompt = self._build_inpainting_prompt(products_to_place, user_action)

            # PASS 2: Place new furniture (or single pass for "add" action)
            # CRITICAL FIX: Use IP-Adapter with product image reference for accurate placement
            if self.replicate_api_key:
                try:
                    if user_action in ["replace_one", "replace_all"]:
                        logger.info("PASS 2: Placing new furniture on cleaned image...")
                    else:
                        logger.info("Attempting IP-Adapter Inpainting with product reference...")

                    # Pass the full product object for detailed information extraction
                    product = products_to_place[0]

                    # Try IP-Adapter first (uses actual product image as reference)
                    if product_image_urls and len(product_image_urls) > 0:
                        logger.info(f"🎯 Using IP-Adapter with product image reference: {product_image_urls[0][:100]}...")
                        result_image = await self._run_ip_adapter_inpainting(
                            room_image=working_image,  # Use cleaned image from Pass 1 for replace actions
                            mask=mask,
                            product_image_url=product_image_urls[0],
                            prompt=prompt,
                            product=product
                        )

                        if result_image:
                            # Convert PIL Image to base64 data URI
                            buffered = io.BytesIO()
                            result_image.save(buffered, format="PNG", quality=95)
                            img_base64 = base64.b64encode(buffered.getvalue()).decode()
                            result_data_uri = f"data:image/png;base64,{img_base64}"
                            logger.info(f"✅ IP-Adapter successful, converted to base64 ({len(result_data_uri)} chars)")
                        else:
                            logger.warning("⚠️ IP-Adapter failed, falling back to text-only...")
                            result_data_uri = await self._run_text_only_inpainting(
                                room_image=working_image,
                                mask=mask,
                                prompt=prompt,
                                product=product
                            )
                    else:
                        # No product image available, use text-only
                        logger.warning("⚠️ No product image URL, using text-only inpainting...")
                        result_data_uri = await self._run_text_only_inpainting(
                            room_image=working_image,
                            mask=mask,
                            prompt=prompt,
                            product=product
                        )

                    if result_data_uri:
                        # _run_text_only_inpainting already returns base64 data URI
                        processing_time = time.time() - start_time

                        self.usage_stats["replicate_requests"] += 1
                        self.usage_stats["successful_requests"] += 1

                        logger.info(f"SDXL Text-Only model completed in {processing_time:.2f}s")
                        return InpaintingResult(
                            rendered_image=result_data_uri,
                            processing_time=processing_time,
                            success=True,
                            confidence_score=0.95  # Highest confidence - SDXL with ChatGPT Vision
                        )
                except Exception as model_error:
                    logger.error(f"🚨 SDXL Inpainting model failed: {model_error}", exc_info=True)
                    # No fallback - fail explicitly

            # No inpainting service available
            logger.error("🚨 All Replicate inpainting services failed - no API key or all methods failed")
            raise ValueError("No inpainting service available (all Replicate services failed)")

        except Exception as e:
            processing_time = time.time() - start_time
            self.usage_stats["failed_requests"] += 1

            # CRITICAL ERROR LOGGING
            logger.error("=" * 80)
            logger.error(f"🚨 CLOUD INPAINTING FAILED - RETURNING ORIGINAL IMAGE UNCHANGED")
            logger.error(f"🚨 Error: {e}")
            logger.error(f"🚨 Error type: {type(e).__name__}")
            logger.error(f"🚨 user_action: {user_action}")
            logger.error(f"🚨 existing_furniture count: {len(existing_furniture) if existing_furniture else 0}")
            logger.error("=" * 80)
            logger.error(f"Cloud inpainting failed: {e}", exc_info=True)

            return InpaintingResult(
                rendered_image=base_image,
                processing_time=processing_time,
                success=False,
                error_message=str(e),
                confidence_score=0.0
            )

    async def _run_stability_ai_inpainting(
        self,
        room_image: Image.Image,
        mask: Image.Image,
        prompt: str
    ) -> Optional[Image.Image]:
        """
        Run Stability AI official SDXL inpainting

        Docs: https://platform.stability.ai/docs/api-reference#tag/Edit/paths/~1v2beta~1stable-image~1edit~1inpaint/post
        """
        try:
            # Prepare images
            room_bytes = io.BytesIO()
            room_image.save(room_bytes, format='PNG')
            room_bytes.seek(0)

            mask_bytes = io.BytesIO()
            mask.save(mask_bytes, format='PNG')
            mask_bytes.seek(0)

            # Prepare multipart form data
            form_data = aiohttp.FormData()
            form_data.add_field('image', room_bytes, filename='room.png', content_type='image/png')
            form_data.add_field('mask', mask_bytes, filename='mask.png', content_type='image/png')
            form_data.add_field('prompt', prompt)
            form_data.add_field('output_format', 'png')
            form_data.add_field('seed', '0')  # Deterministic results

            headers = {
                "Authorization": f"Bearer {self.stability_api_key}",
                "Accept": "image/*"
            }

            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.stability_ai_endpoint,
                    data=form_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        result_image = Image.open(io.BytesIO(image_bytes))
                        logger.info("Stability AI inpainting successful")
                        return result_image
                    else:
                        error_text = await response.text()
                        logger.error(f"Stability AI error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Stability AI inpainting error: {e}")
            return None

    @retry_on_connection_error(max_retries=3, initial_delay=2.0)
    async def _run_ip_adapter_inpainting(
        self,
        room_image: Image.Image,
        mask: Image.Image,
        product_image_url: str,
        prompt: str,
        product: Dict[str, Any] = None
    ) -> Optional[Image.Image]:
        """
        Single-stage pipeline: Combined IP-Adapter + Inpainting + ControlNet

        Uses PUBLIC Replicate model (usamaehsan/controlnet-x-majic-mix-realistic-x-ip-adapter):
        - MajicMIX Realistic base (optimized for photorealistic interior design)
        - Accepts product reference image (ip_adapter_image)
        - Inpainting support (inpainting_image + mask_image)
        - Canny ControlNet for structure preservation (lineart_image)
        - Single API call with all images

        WITH RETRY: Automatically retries on connection reset errors
        """
        try:
            logger.info("Running Public MajicMIX Model (IP-Adapter + Inpainting + Canny ControlNet)...")

            # CRITICAL: Resize to fixed 512x512 dimensions
            # Many models work reliably with 512x512 fixed size
            target_size = (512, 512)

            original_size = room_image.size
            logger.info(f"Original image size: {original_size}")
            logger.info(f"Target size (fixed 512x512): {target_size}")

            # Resize room image to SDXL dimensions
            if room_image.size != target_size:
                logger.info(f"Resizing room image from {room_image.size} to {target_size}")
                room_image = room_image.resize(target_size, Image.Resampling.LANCZOS)

            # Resize mask to match
            if mask.size != target_size:
                logger.info(f"Resizing mask from {mask.size} to {target_size}")
                mask = mask.resize(target_size, Image.Resampling.LANCZOS)

            # Generate depth map for ControlNet
            depth_map = self._generate_depth_map(room_image)

            # Ensure depth map matches room_image size EXACTLY
            if depth_map.size != target_size:
                logger.info(f"Resizing depth map from {depth_map.size} to {target_size}")
                depth_map = depth_map.resize(target_size, Image.Resampling.LANCZOS)

            # Final size verification
            assert room_image.size == mask.size == depth_map.size, \
                f"Size mismatch: room={room_image.size}, mask={mask.size}, depth={depth_map.size}"
            assert room_image.size == (512, 512), \
                f"Image dimensions must be 512x512: {room_image.size}"
            logger.info(f"All images verified to be {room_image.size} (fixed 512x512) - proceeding with API call (IP-Adapter + Depth ControlNet)")

            # Convert to data URIs
            depth_data_uri = self._image_to_data_uri(depth_map)
            room_data_uri = self._image_to_data_uri(room_image)
            mask_data_uri = self._image_to_data_uri(mask)

            # Extract product information
            if product:
                product_name = product.get('full_name') or product.get('name', 'furniture')
                product_description = product.get('description', '')
            else:
                product_name = prompt.split("with a ")[-1].split(" naturally")[0] if "with a " in prompt else "furniture"
                product_description = ''

            # FIX 5: Try ChatGPT Vision API for enhanced product analysis (with fallback to local extraction)
            vision_result = await self._generate_product_prompt_with_vision(
                product_image_url, product_name, product_description
            )

            if vision_result:
                # Use Vision API results
                logger.info("Using ChatGPT Vision API analysis for product prompt")
                exact_color = vision_result.get('exact_color', '')
                material = vision_result.get('material', '')
                texture = vision_result.get('texture', '')
                style = vision_result.get('style', '')
                design_details = vision_result.get('design_details', '')
                dimensions_str = vision_result.get('dimensions', '')

                # Build enhanced prompt from Vision API analysis with placement instruction
                # Format: "Place <furniture name>, <description from chatgpt>"
                description_parts = []

                if exact_color:
                    description_parts.append(f"{exact_color} color")
                if material:
                    description_parts.append(f"{material} material")
                if texture:
                    description_parts.append(f"{texture} texture")
                if style:
                    description_parts.append(f"{style} style")
                if design_details:
                    description_parts.append(design_details)
                if dimensions_str:
                    description_parts.append(dimensions_str)

                # Join description parts
                description = ", ".join(description_parts)

                # Final prompt format: "Place <furniture name>, <description>"
                focused_prompt = f"Place {product_name}, {description}"
            else:
                # Fallback to local keyword extraction (FIX 2 & FIX 3)
                logger.info("Vision API unavailable - using local keyword extraction")

                # FIX 2: Extract color and material from product name for better matching
                color_descriptor = self._extract_color_descriptor(product_name)
                material_descriptor = self._extract_material_descriptor(product_name)

                # FIX 3: Extract dimensions from product description or use defaults
                dimensions_str = self._extract_dimensions_from_description(product_description, product_name)

                # Build enhanced product description with color, material, and dimensions
                enhanced_product_desc = product_name
                if color_descriptor:
                    enhanced_product_desc = f"{color_descriptor} {enhanced_product_desc}"
                if material_descriptor and material_descriptor not in product_name.lower():
                    enhanced_product_desc = f"{material_descriptor} {enhanced_product_desc}"

                # Build focused prompt for interior design with color, material, and dimensions
                # Format: "Place <furniture name>, <description from local extraction>"
                description_parts = [enhanced_product_desc]

                if dimensions_str:
                    description_parts.append(dimensions_str)

                # Join description parts
                description = ", ".join(description_parts)

                # Final prompt format: "Place <furniture name>, <description>"
                focused_prompt = f"Place {description}"

            logger.info(f"Using enhanced prompt: {focused_prompt}")
            logger.info(f"Product reference URL: {product_image_url}")

            # Use async polling for public model (handles queue times better than blocking replicate.run())
            model_version = settings.replicate_ip_adapter_inpainting

            # Log all parameters being sent to Replicate (with truncated data URIs)
            logger.info(f"========== REPLICATE API CALL (ASYNC POLLING) - IP-ADAPTER + DEPTH CONTROLNET ==========")
            logger.info(f"Model: {model_version}")
            logger.info(f"Parameters being sent:")
            logger.info(f"  - prompt: {focused_prompt}")
            logger.info(f"  - inpainting_image: data:image/png;base64,[{len(room_data_uri)} chars]")
            logger.info(f"  - mask_image: data:image/png;base64,[{len(mask_data_uri)} chars]")
            logger.info(f"  - depth_image: data:image/png;base64,[{len(depth_data_uri)} chars]")
            logger.info(f"  - ip_adapter_image: {product_image_url}")
            logger.info(f"  - ip_adapter_strength: 1.0")
            logger.info(f"  - sorted_controlnets: inpainting")
            logger.info(f"  - controlnet_conditioning_scale: 0.8")
            logger.info(f"  - strength: 0.7")
            logger.info(f"  - num_inference_steps: 40")
            logger.info(f"  - guidance_scale: 8")
            logger.info(f"  - max_width: 512")
            logger.info(f"  - max_height: 512")
            logger.info(f"  - negative_prompt: {self._build_negative_prompt()}")

            # Create prediction (non-blocking)
            def create_prediction():
                """Create prediction (synchronous call in thread) - IP-Adapter + Depth ControlNet"""
                return replicate.predictions.create(
                    version=model_version,
                    input={
                        "prompt": focused_prompt,
                        "inpainting_image": room_data_uri,           # Base room image (data URI)
                        "mask_image": mask_data_uri,                 # Mask for inpainting
                        "depth_image": depth_data_uri,               # Depth map for structure preservation
                        "ip_adapter_image": product_image_url,       # Product reference (URL)
                        "ip_adapter_strength": 1.0,                  # IP-Adapter strength for product matching
                        # REMOVED: "control_type": "depth" - not needed
                        "sorted_controlnets": "inpainting",          # ControlNet order
                        "controlnet_conditioning_scale": 0.8,        # ControlNet conditioning strength
                        "strength": 0.7,                             # Denoising strength for inpainting
                        "num_inference_steps": 40,                   # Inference steps for quality
                        "guidance_scale": 8,                         # Prompt adherence strength
                        "max_width": 512,                            # Fixed width constraint
                        "max_height": 512,                           # Fixed height constraint
                        "negative_prompt": self._build_negative_prompt()
                    }
                )

            logger.info(f"Creating prediction...")

            # Wrap prediction creation with explicit timeout (increased to 300s for public model queuing)
            try:
                prediction = await asyncio.wait_for(
                    asyncio.to_thread(create_prediction),
                    timeout=300.0
                )
            except asyncio.TimeoutError:
                logger.error("Prediction creation timed out after 300 seconds")
                raise asyncio.TimeoutError("Failed to create prediction on Replicate API (connection timeout)")

            prediction_id = prediction.id
            logger.info(f"Prediction created: {prediction_id}")
            logger.info(f"Status: {prediction.status}")

            # Poll for completion with timeout
            start_time = time.time()
            timeout = 600.0  # 10 minutes total timeout
            poll_interval = 2.0  # Poll every 2 seconds

            while time.time() - start_time < timeout:
                # Check status
                def get_prediction_status():
                    """Get prediction status (synchronous call in thread)"""
                    return replicate.predictions.get(prediction_id)

                prediction = await asyncio.to_thread(get_prediction_status)

                elapsed = time.time() - start_time
                logger.info(f"[{elapsed:.1f}s] Prediction status: {prediction.status}")

                if prediction.status == "succeeded":
                    logger.info(f"Prediction succeeded after {elapsed:.1f}s")
                    output = prediction.output
                    break
                elif prediction.status == "failed":
                    error_msg = getattr(prediction, 'error', 'Unknown error')
                    raise Exception(f"Prediction failed: {error_msg}")
                elif prediction.status == "canceled":
                    raise Exception("Prediction was canceled")

                # Wait before next poll
                await asyncio.sleep(poll_interval)
            else:
                # Timeout reached
                raise asyncio.TimeoutError(f"Prediction timed out after {timeout}s")

            logger.info(f"=========================================")


            # Download result
            if isinstance(output, list) and len(output) > 0:
                output_url = output[0]
            elif isinstance(output, str):
                output_url = output
            else:
                raise ValueError(f"Unexpected output format: {type(output)}")

            result_image = await self._download_image(output_url)
            logger.info("Public MajicMIX Model successful")
            return result_image

        except asyncio.TimeoutError:
            logger.error(f"Public MajicMIX Model timeout after 600 seconds")
            return None
        except Exception as e:
            logger.error(f"Public MajicMIX Model error: {e}")
            return None

    @retry_on_connection_error(max_retries=3, initial_delay=2.0)
    async def _run_basic_sdxl_inpainting(
        self,
        room_image: Image.Image,
        mask: Image.Image,
        prompt: str
    ) -> Optional[Image.Image]:
        """
        Basic SDXL Inpainting without IP-Adapter (fast primary option)
        Preserves room with mask, generates product from text prompt
        OPTIMIZED: Reduced steps for 3-4x faster generation
        WITH RETRY: Automatically retries on connection reset errors
        """
        try:
            logger.info("Running basic SDXL inpainting (fast, optimized)...")

            # Convert images to data URIs
            room_data_uri = self._image_to_data_uri(room_image)
            mask_data_uri = self._image_to_data_uri(mask)

            # Add timeout wrapper to prevent hanging
            output = await asyncio.wait_for(
                asyncio.to_thread(
                    replicate.run,
                    settings.replicate_sdxl_inpaint_model,
                    input={
                        "image": room_data_uri,
                        "mask": mask_data_uri,
                        "prompt": prompt,
                        "negative_prompt": self._build_negative_prompt(),
                        "steps": 20,  # Reduced from 30 for ~33% speed improvement
                        "strength": 0.8,  # Reduced from 0.85 for faster convergence
                        "guidance_scale": 7.0,  # Reduced from 8.0 for faster processing
                        "scheduler": "DPMSolverMultistep"  # Changed from K_EULER for faster convergence
                    }
                ),
                timeout=180.0  # 3 minutes timeout for image generation
            )

            # Download result
            if isinstance(output, list) and len(output) > 0:
                output_url = output[0]
            elif isinstance(output, str):
                output_url = output
            else:
                raise ValueError(f"Unexpected output format: {type(output)}")

            result_image = await self._download_image(output_url)
            logger.info("Basic SDXL inpainting successful")
            return result_image

        except asyncio.TimeoutError:
            logger.error(f"Basic SDXL inpainting timeout after 180 seconds")
            return None
        except Exception as e:
            logger.error(f"Basic SDXL inpainting error: {e}")
            return None


    async def _generate_segmentation_mask_with_grounded_sam(
        self,
        room_image: Image.Image,
        furniture_type: str
    ) -> Optional[Image.Image]:
        """
        Generate precise segmentation mask using Lang-Segment-Anything AI model (tmappdev/lang-segment-anything)

        Args:
            room_image: PIL Image of the room (should be 512x512)
            furniture_type: Type of furniture to segment (e.g., "sofa", "chair", "table")

        Returns:
            PIL Image mask (512x512, grayscale 'L' mode) where WHITE=inpaint, BLACK=preserve
            Returns None if segmentation fails
        """
        try:
            logger.info(f"Attempting Lang-Segment-Anything segmentation for furniture type: {furniture_type}")

            # Convert room image to data URI for Replicate API
            room_data_uri = self._image_to_data_uri(room_image)

            # Call Lang-Segment-Anything model with furniture type prompt
            # Model expects: image input + text prompt
            logger.info(f"Calling Lang-Segment-Anything API with prompt: '{furniture_type}'")

            # Create prediction using async polling
            def create_sam_prediction():
                """Create Lang-Segment-Anything prediction (synchronous call in thread)"""
                return replicate.predictions.create(
                    version=settings.replicate_grounded_sam_model,
                    input={
                        "image": room_data_uri,
                        "text_prompt": furniture_type  # Text prompt for object to segment
                    }
                )

            # Create prediction with timeout (increased to 180s for reliability)
            try:
                prediction = await asyncio.wait_for(
                    asyncio.to_thread(create_sam_prediction),
                    timeout=180.0
                )
            except asyncio.TimeoutError:
                logger.error("Lang-Segment-Anything prediction creation timed out after 180s")
                return None

            prediction_id = prediction.id
            logger.info(f"Lang-Segment-Anything prediction created: {prediction_id}")

            # Poll for completion
            start_time = time.time()
            timeout = 180.0  # 3 minutes for segmentation
            poll_interval = 2.0

            while time.time() - start_time < timeout:
                def get_prediction_status():
                    return replicate.predictions.get(prediction_id)

                prediction = await asyncio.to_thread(get_prediction_status)
                elapsed = time.time() - start_time

                if prediction.status == "succeeded":
                    logger.info(f"Lang-Segment-Anything succeeded after {elapsed:.1f}s")
                    output = prediction.output
                    break
                elif prediction.status == "failed":
                    error_msg = getattr(prediction, 'error', 'Unknown error')
                    logger.error(f"Lang-Segment-Anything failed: {error_msg}")
                    return None
                elif prediction.status == "canceled":
                    logger.error("Lang-Segment-Anything prediction was canceled")
                    return None

                await asyncio.sleep(poll_interval)
            else:
                logger.error(f"Lang-Segment-Anything timed out after {timeout}s")
                return None

            # Download the segmentation mask from output
            # Output format varies - could be URL string or list
            mask_url = None
            if isinstance(output, list) and len(output) > 0:
                mask_url = output[0]
            elif isinstance(output, str):
                mask_url = output
            else:
                logger.error(f"Unexpected Lang-Segment-Anything output format: {type(output)}")
                return None

            # Download mask image
            mask_image = await self._download_image(mask_url)
            logger.info(f"Downloaded Lang-Segment-Anything mask: {mask_image.size}, mode={mask_image.mode}")

            # Convert to grayscale 'L' mode if needed
            if mask_image.mode != 'L':
                mask_image = mask_image.convert('L')

            # Ensure mask is 512x512
            target_size = (512, 512)
            if mask_image.size != target_size:
                logger.info(f"Resizing Lang-Segment-Anything mask from {mask_image.size} to {target_size}")
                mask_image = mask_image.resize(target_size, Image.Resampling.LANCZOS)

            # CRITICAL FIX: Convert grayscale mask to pure binary (0 or 255)
            # Lang-Segment-Anything may return shades of grey - we need pure white/black
            mask_array = np.array(mask_image)
            binary_mask_array = np.where(mask_array > 128, 255, 0).astype(np.uint8)
            binary_mask = Image.fromarray(binary_mask_array, mode='L')
            logger.info(f"✅ Converted grayscale mask to binary: unique values = {np.unique(binary_mask_array)}")

            logger.info(f"Lang-Segment-Anything segmentation successful: {binary_mask.size}")
            return binary_mask

        except asyncio.TimeoutError:
            logger.error("Lang-Segment-Anything timeout")
            return None
        except Exception as e:
            logger.error(f"Lang-Segment-Anything segmentation error: {e}", exc_info=True)
            return None

    async def _generate_placement_mask(
        self,
        room_image: Image.Image,
        products_to_place: List[Dict[str, Any]],
        existing_furniture: List[Dict[str, Any]],
        user_action: str
    ) -> Image.Image:
        """
        Generate mask for product placement at 512x512 dimensions
        White = inpaint area, Black = preserve area

        IMPORTANT: This function ALWAYS returns masks at 512x512 to match the
        inpainting model requirements. The caller should resize the room image
        to 512x512 before passing to _run_ip_adapter_inpainting().

        Priority order:
        1. AI-powered Grounded-SAM segmentation (NEW - most accurate)
        2. Bounding box-based masks (for detected furniture)
        3. Centered masks based on product dimensions (fallback)
        """
        try:
            original_width, original_height = room_image.size
            logger.info(f"Mask generation - original image size: {original_width}x{original_height}")

            # CRITICAL: Work at 512x512 throughout to match inpainting model requirements
            # This avoids unnecessary resize operations (mask stays at 512x512)
            target_size = (512, 512)
            room_image_resized = room_image.resize(target_size, Image.Resampling.LANCZOS)
            logger.info(f"Resized room image to {target_size} for mask generation")

            width, height = target_size

            # Create black mask (preserve everything) at 512x512
            mask = Image.new('L', (width, height), color=0)  # Use grayscale 'L' mode
            draw = ImageDraw.Draw(mask)

            # Priority 1: Lang-Segment-Anything AI segmentation (pixel-perfect masks)
            # USE AI SEGMENTATION FOR REPLACE ACTIONS - provides accurate masks
            # This mask will be used for BOTH Pass 1 (removal) and Pass 2 (placement)
            use_ai_for_replace = user_action in ["replace_one", "replace_all"] and existing_furniture and len(existing_furniture) > 0

            if use_ai_for_replace:
                logger.info(f"🎯 Priority 1: USING AI segmentation for {user_action} action")
                logger.info(f"   Segmenting EXISTING furniture for pixel-perfect removal and replacement")

                # For replace actions, segment the EXISTING furniture type (not new product)
                existing_type = existing_furniture[0].get('object_type', '').lower()
                # Normalize type names
                type_map = {'couch': 'sofa', 'sectional': 'sofa', 'loveseat': 'sofa'}
                furniture_type = type_map.get(existing_type, existing_type)

                if furniture_type:
                    logger.info(f"✓ Segmenting existing '{furniture_type}' for replacement")
                    sam_mask = await self._generate_segmentation_mask_with_grounded_sam(
                        room_image=room_image_resized,  # Use resized 512x512 image
                        furniture_type=furniture_type
                    )

                    if sam_mask:
                        logger.info("✓ Lang-Segment-Anything SUCCESSFUL - using AI mask for both removal and placement")
                        return sam_mask
                    else:
                        logger.warning("✗ Lang-Segment-Anything failed - falling back to bounding boxes")
                else:
                    logger.warning(f"✗ Could not identify furniture type from existing furniture")
            else:
                # For ADD actions, segment the NEW product type
                logger.info(f"Priority 1: Attempting Lang-Segment-Anything segmentation for ADD action")
                if products_to_place and len(products_to_place) > 0:
                    product = products_to_place[0]
                    product_name = product.get('full_name') or product.get('name', 'furniture')
                    logger.info(f"Product name for segmentation: '{product_name}'")

                    # Detect furniture type from product name
                    furniture_type = self._get_furniture_type(product_name)
                    logger.info(f"Detected furniture type: '{furniture_type}' (None means no match)")

                    if furniture_type:
                        logger.info(f"✓ Furniture type detected: '{furniture_type}' - calling Lang-Segment-Anything API")
                        sam_mask = await self._generate_segmentation_mask_with_grounded_sam(
                            room_image=room_image_resized,  # Use resized 512x512 image
                            furniture_type=furniture_type
                        )

                        if sam_mask:
                            logger.info("✓ Lang-Segment-Anything segmentation SUCCESSFUL - using AI-generated mask at 512x512")
                            # Return mask at 512x512 (no resize needed - avoids quality loss)
                            return sam_mask
                        else:
                            logger.warning("✗ Lang-Segment-Anything failed - falling back to geometric masks")
                    else:
                        logger.warning(f"✗ Could not detect furniture type from '{product_name}' - skipping Lang-Segment-Anything")
                else:
                    logger.info("No products to place - skipping Lang-Segment-Anything")

            # Priority 2: Use existing furniture bounding boxes if available (for replacement mode)
            logger.info(f"Priority 2: Checking for bounding box masks")
            logger.info(f"DEBUG MASK: existing_furniture={existing_furniture}")
            logger.info(f"DEBUG MASK: user_action={user_action}")
            logger.info(f"DEBUG MASK: Condition check: existing_furniture={existing_furniture is not None}, len={len(existing_furniture) if existing_furniture else 0}, action in replace={user_action in ['replace_one', 'replace_all']}")

            if existing_furniture and len(existing_furniture) > 0 and user_action in ["replace_one", "replace_all"]:
                # replace_one: Mask FIRST detected furniture item only
                # replace_all: Mask ALL detected furniture items
                furniture_to_mask = [existing_furniture[0]] if user_action == "replace_one" else existing_furniture
                logger.info(f"Priority 2: Using detected furniture bounding boxes for {len(furniture_to_mask)} item(s) ({user_action})")
                logger.info(f"DEBUG MASK: furniture_to_mask={furniture_to_mask}")

                total_mask_area = 0
                for idx, furniture in enumerate(furniture_to_mask):
                    logger.info(f"DEBUG MASK: Processing furniture {idx}: {furniture}")
                    bbox = furniture.get('bounding_box')
                    logger.info(f"DEBUG MASK: Extracted bbox = {bbox}")

                    if bbox and all(key in bbox for key in ['x1', 'y1', 'x2', 'y2']):
                        # DEBUG: Log raw bbox values
                        logger.info(f"DEBUG MASK: ✅ Valid bbox found: {bbox}, image size = {width}x{height}")

                        # Bounding box format: {'x1': ..., 'y1': ..., 'x2': ..., 'y2': ...}
                        # Coordinates are normalized (0-1), scale to target image dimensions (512x512)
                        x1 = int(bbox['x1'] * width)
                        y1 = int(bbox['y1'] * height)
                        x2 = int(bbox['x2'] * width)
                        y2 = int(bbox['y2'] * height)

                        # DEBUG: Log calculated pixel coordinates
                        logger.info(f"DEBUG MASK: Calculated pixels BEFORE padding: x1={x1}, y1={y1}, x2={x2}, y2={y2}")

                        # Skip if coordinates are invalid (all zeros or negative area)
                        if x1 >= x2 or y1 >= y2 or (x1 == 0 and x2 == 0 and y1 == 0 and y2 == 0):
                            logger.warning(f"❌ Skipping invalid bounding box for {furniture.get('type', furniture.get('object_type', 'furniture'))}: {bbox}")
                            logger.warning(f"   Reason: x1={x1}, x2={x2}, y1={y1}, y2={y2}, invalid={x1 >= x2 or y1 >= y2}")
                            continue
                        else:
                            logger.info(f"✅ Valid coordinates: x1={x1}, x2={x2}, y1={y1}, y2={y2}")

                        # Add padding around detected furniture
                        # Use minimal padding for replace actions to avoid including extra items
                        # Use more padding for add actions to ensure full coverage
                        if user_action in ["replace_one", "replace_all"]:
                            padding_percent = 0.02  # 2% padding for replace - tight fit
                        else:
                            padding_percent = 0.1   # 10% padding for add - room for variation

                        box_width = x2 - x1
                        box_height = y2 - y1
                        padding_x = int(box_width * padding_percent)
                        padding_y = int(box_height * padding_percent)

                        logger.info(f"📏 Padding: {padding_percent*100}% ({padding_x}px x, {padding_y}px y) for {user_action}")

                        x1 = max(0, x1 - padding_x)
                        y1 = max(0, y1 - padding_y)
                        x2 = min(width, x2 + padding_x)
                        y2 = min(height, y2 + padding_y)

                        # Draw white rectangle for this furniture item
                        draw.rectangle([x1, y1, x2, y2], fill=255)

                        mask_area = (x2 - x1) * (y2 - y1)
                        total_mask_area += mask_area
                        logger.info(f"✅ Added mask for {furniture.get('type', furniture.get('object_type', 'furniture'))}: {x2-x1}x{y2-y1}px at ({x1}, {y1})")
                    else:
                        logger.warning(f"❌ Skipping furniture {idx}: Invalid or missing bounding box. bbox={bbox}, has_required_keys={bbox and all(key in bbox for key in ['x1', 'y1', 'x2', 'y2']) if bbox else False}")

                logger.info(f"Generated combined mask covering {len(furniture_to_mask)} items (total area: {total_mask_area}px)")

                # FALLBACK: If mask is empty (0 area), fall through to centered placement
                if total_mask_area > 0:
                    # Return mask at 512x512 (no resize needed - avoids quality loss)
                    return mask

                logger.warning("⚠️ Bounding boxes produced 0-area mask, falling back to centered placement")

            # Priority 3: Use product dimensions for centered placement (for add mode or fallback)
            logger.info(f"Priority 3: Using centered mask based on product dimensions")
            logger.info(f"DEBUG MASK: Reached Priority 3 - means Priority 1 & 2 were skipped or failed")
            if products_to_place and len(products_to_place) > 0:
                product = products_to_place[0]
                product_name = product.get('full_name') or product.get('name', 'furniture')

                # Get dimensions
                dimensions = product.get('dimensions')
                if not dimensions:
                    dimensions = self._get_typical_dimensions(product_name)

                # Calculate pixel size
                pixels_per_inch = width / 144  # 12ft room
                furn_width = int(dimensions.get('width', 60) * pixels_per_inch)
                furn_height = int(dimensions.get('height', 30) * pixels_per_inch * 0.7)

                # Clamp
                furn_width = max(int(width * 0.15), min(furn_width, int(width * 0.45)))
                furn_height = max(int(height * 0.15), min(furn_height, int(height * 0.45)))

                # Add padding
                mask_width = int(furn_width * 1.1)
                mask_height = int(furn_height * 1.1)

                # Center placement
                center_x = width // 2
                center_y = int(height * 0.6)

                x1 = center_x - mask_width // 2
                y1 = center_y - mask_height // 2
                x2 = center_x + mask_width // 2
                y2 = center_y + mask_height // 2

                # Draw white rectangle (255 = inpaint)
                draw.rectangle([x1, y1, x2, y2], fill=255)

                logger.info(f"Generated centered mask for {product_name}: {mask_width}x{mask_height}px at {target_size}")
                # Return mask at 512x512 (no resize needed - avoids quality loss)
                return mask
            else:
                # Fallback: generic center mask
                mask_width = int(width * 0.35)
                mask_height = int(height * 0.35)
                x1 = (width - mask_width) // 2
                y1 = (height - mask_height) // 2
                x2 = x1 + mask_width
                y2 = y1 + mask_height
                draw.rectangle([x1, y1, x2, y2], fill=255)
                logger.info(f"Generated fallback centered mask: {mask_width}x{mask_height}px at {target_size}")
                # Return mask at 512x512 (no resize needed - avoids quality loss)
                return mask

        except Exception as e:
            logger.error(f"Failed to generate mask: {e}")
            # Return empty mask at 512x512
            return Image.new('L', (512, 512), color=0)

    def _build_inpainting_prompt(
        self,
        products: List[Dict[str, Any]],
        user_action: str
    ) -> str:
        """Build prompt for inpainting (enhanced with ChatGPT Vision descriptions and table-specific placement)"""
        product = products[0] if products else {}
        product_name = product.get('full_name') or product.get('name', 'furniture')

        # Determine placement instruction based on furniture type
        placement_instruction = self._get_placement_instruction(product_name)

        # Check if we have ChatGPT Vision description
        visual_desc = product.get('visual_description')

        if visual_desc:
            # ENHANCED: Use ChatGPT Vision-generated detailed description
            prompt = (
                f"A photorealistic interior photograph with a {product_name} "
                f"{placement_instruction}. "
                f"The furniture has the following exact characteristics: {visual_desc}. "
                f"Realistic lighting that matches the room's existing light sources, "
                f"proper shadows on the floor, correct perspective and scale for the room dimensions, "
                f"seamless integration with the room environment. "
                f"Professional interior photography, high quality. "
                f"The room structure, walls, floor, windows, and doors remain completely unchanged."
            )
            logger.info(f"Using ChatGPT Vision-enhanced prompt with {placement_instruction}")
        else:
            # FALLBACK: Basic text prompt
            prompt = (
                f"A photorealistic interior photograph with a {product_name} "
                f"{placement_instruction}. "
                f"The furniture should have realistic lighting that matches the room's existing light sources, "
                f"proper shadows on the floor, correct perspective and scale for the room dimensions, "
                f"seamless integration with the room environment. "
                f"Professional interior photography, high quality, "
                f"accurate materials and textures. "
                f"The room structure, walls, floor, windows, and doors remain completely unchanged."
            )
            logger.info(f"Using basic text prompt (no Vision description) with {placement_instruction}")

        return prompt

    def _get_placement_instruction(self, product_name: str) -> str:
        """Get table-specific placement instructions based on furniture type"""
        name_lower = product_name.lower()

        # Center tables (coffee tables) - placed in front of sofa
        if 'coffee' in name_lower or 'center' in name_lower or 'centre' in name_lower:
            return "placed in the center of the room, in front of the sofa or seating area"

        # Side tables - placed beside furniture
        elif 'side' in name_lower or 'end' in name_lower or 'nightstand' in name_lower or 'bedside' in name_lower:
            return "placed on the side, next to the sofa, chair, or bed"

        # Default for other furniture
        else:
            return "naturally placed in the room"

    def _build_negative_prompt(self) -> str:
        """Build negative prompt"""
        return (
            "blurry, low quality, distorted, deformed, unrealistic, bad anatomy, "
            "floating furniture, incorrect shadows, cartoon, painting, illustration, "
            "different room, changed walls, changed floor, multiple copies, duplicates, "
            "wrong perspective, poor lighting, artifacts"
        )

    def _extract_color_descriptor(self, product_name: str) -> Optional[str]:
        """Extract color descriptor from product name"""
        colors = {
            'green', 'sage', 'olive', 'emerald', 'forest', 'lime', 'mint',
            'blue', 'navy', 'royal', 'sky', 'teal', 'azure', 'cobalt',
            'red', 'burgundy', 'crimson', 'maroon', 'ruby', 'cherry',
            'brown', 'tan', 'beige', 'camel', 'chocolate', 'espresso', 'walnut',
            'black', 'white', 'ivory', 'cream', 'off-white',
            'gray', 'grey', 'charcoal', 'slate', 'silver',
            'yellow', 'gold', 'mustard', 'amber',
            'pink', 'rose', 'blush', 'coral', 'salmon',
            'purple', 'violet', 'lavender', 'plum', 'mauve',
            'orange', 'rust', 'copper', 'terracotta'
        }

        name_lower = product_name.lower()
        for color in colors:
            if color in name_lower:
                return color
        return None

    def _extract_material_descriptor(self, product_name: str) -> Optional[str]:
        """Extract material descriptor from product name"""
        materials = {
            'leather', 'velvet', 'linen', 'cotton', 'fabric', 'upholstered',
            'wood', 'wooden', 'oak', 'walnut', 'teak', 'pine', 'mahogany',
            'metal', 'steel', 'iron', 'brass', 'copper', 'bronze',
            'glass', 'marble', 'stone', 'granite', 'quartz',
            'plastic', 'acrylic', 'resin', 'lucite',
            'wicker', 'rattan', 'bamboo', 'cane'
        }

        name_lower = product_name.lower()
        for material in materials:
            if material in name_lower:
                return material
        return None

    def _extract_dimensions_from_description(self, description: str, product_name: str) -> Optional[str]:
        """
        Extract dimensions from product description and format for prompt

        Looks for patterns like:
        - "84"W x 36"D x 36"H"
        - "Width: 84 inches, Depth: 36 inches, Height: 36 inches"
        - "Dimensions: 84 x 36 x 36"
        """
        import re

        if not description:
            return None

        # Try to find dimensions in format: 84"W x 36"D x 36"H or 84W x 36D x 36H
        pattern1 = r'(\d+)"?\s*[Ww]\s*x\s*(\d+)"?\s*[Dd]\s*x\s*(\d+)"?\s*[Hh]'
        match = re.search(pattern1, description)
        if match:
            width, depth, height = match.groups()
            return f"dimensions {width} inches wide by {depth} inches deep by {height} inches high"

        # Try format: Width: 84", Depth: 36", Height: 36"
        pattern2 = r'[Ww]idth[:\s]+(\d+)["\s]*(?:inches?)?.*[Dd]epth[:\s]+(\d+)["\s]*(?:inches?)?.*[Hh]eight[:\s]+(\d+)'
        match = re.search(pattern2, description)
        if match:
            width, depth, height = match.groups()
            return f"dimensions {width} inches wide by {depth} inches deep by {height} inches high"

        # Try format: Dimensions: 84 x 36 x 36 (assume W x D x H)
        pattern3 = r'[Dd]imensions?[:\s]+(\d+)\s*[xX×]\s*(\d+)\s*[xX×]\s*(\d+)'
        match = re.search(pattern3, description)
        if match:
            width, depth, height = match.groups()
            return f"dimensions {width} inches wide by {depth} inches deep by {height} inches high"

        # Try format: 84 x 36 inches (W x D, no height)
        pattern4 = r'(\d+)\s*[xX×]\s*(\d+)\s*(?:inches?|")'
        match = re.search(pattern4, description)
        if match:
            width, depth = match.groups()
            return f"dimensions {width} inches wide by {depth} inches deep"

        # If no dimensions found in description, use furniture type defaults
        furniture_type = self._get_furniture_type(product_name)
        if furniture_type:
            dims = self._get_typical_dimensions(product_name)
            return f"typical {furniture_type} dimensions approximately {int(dims.get('width', 48))} inches wide by {int(dims.get('depth', 30))} inches deep by {int(dims.get('height', 30))} inches high"

        return None

    def _get_furniture_type(self, product_name: str) -> Optional[str]:
        """Extract furniture type from product name"""
        name_lower = product_name.lower()

        furniture_types = [
            ('sofa', 'sofa'),
            ('couch', 'sofa'),
            ('chair', 'chair'),
            ('coffee table', 'coffee table'),
            ('side table', 'side table'),
            ('dining table', 'dining table'),
            ('bed', 'bed'),
            ('dresser', 'dresser'),
            ('desk', 'desk'),
            ('bookshelf', 'bookshelf'),
            ('cabinet', 'cabinet')
        ]

        for keyword, furniture_type in furniture_types:
            if keyword in name_lower:
                return furniture_type

        return None

    def _get_typical_dimensions(self, product_name: str) -> Dict[str, float]:
        """Get typical furniture dimensions in inches"""
        name_lower = product_name.lower()

        if 'sofa' in name_lower or 'couch' in name_lower:
            return {"width": 84, "depth": 36, "height": 36}
        elif 'chair' in name_lower:
            return {"width": 32, "depth": 34, "height": 36}
        elif 'coffee table' in name_lower:
            return {"width": 48, "depth": 24, "height": 18}
        elif 'side table' in name_lower:
            return {"width": 24, "depth": 18, "height": 24}
        elif 'dining table' in name_lower:
            return {"width": 72, "depth": 40, "height": 30}
        elif 'bed' in name_lower:
            return {"width": 60, "depth": 80, "height": 24}
        elif 'dresser' in name_lower:
            return {"width": 60, "depth": 18, "height": 36}

        return {"width": 48, "depth": 30, "height": 30}

    async def _generate_product_prompt_with_vision(
        self,
        product_image_url: str,
        product_name: str,
        product_description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Use ChatGPT Vision API to analyze product image and generate enhanced prompt

        Args:
            product_image_url: URL of the product image
            product_name: Product name from database
            product_description: Product description from database

        Returns:
            Dict with extracted attributes: {
                "exact_color": str,
                "material": str,
                "texture": str,
                "style": str,
                "design_details": str,
                "dimensions": str,
                "enhanced_prompt": str
            }
        """
        try:
            logger.info(f"Calling ChatGPT Vision API for product analysis: {product_name}")

            # Import openai client from settings
            import openai
            client = openai.AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=30.0,
                max_retries=2
            )

            # Build Vision API prompt
            vision_prompt = f"""Analyze this furniture product image carefully and extract the following details:

Product Name: {product_name}
Product Description: {product_description}

Please provide a detailed analysis in JSON format:

1. EXACT COLOR: Identify the precise color(s) visible in the image (not just from the name)
   - Main color (e.g., "sage green", "navy blue", "charcoal gray")
   - Secondary colors if applicable
   - Color undertones (warm/cool)

2. MATERIAL: Identify materials from visual texture cues
   - Upholstery material (e.g., "velvet", "leather", "linen", "cotton")
   - Frame material (e.g., "wood", "metal", "wicker")
   - Visible material qualities (e.g., "tufted", "smooth", "woven")

3. TEXTURE: Describe visible surface texture
   - Surface finish (e.g., "plush velvet", "smooth leather", "textured fabric")
   - Pattern details if visible

4. STYLE: Classify the design style
   - Primary style (e.g., "modern", "mid-century", "traditional", "contemporary")
   - Design era or aesthetic

5. DESIGN DETAILS: Specific visual characteristics
   - Arm style (e.g., "rolled arms", "track arms", "no arms")
   - Leg style (e.g., "tapered wooden legs", "metal hairpin legs", "no visible legs")
   - Cushion type (e.g., "loose cushions", "tight back", "tufted")
   - Special features (e.g., "nailhead trim", "button tufting", "pleated skirt")

6. DIMENSIONS: Extract from description or estimate from visual proportions
   - Width, Depth, Height in inches
   - Overall size classification (small/medium/large)

Return ONLY valid JSON in this exact format:
{{
  "exact_color": "primary color with descriptive terms",
  "secondary_colors": ["color1", "color2"],
  "material": "primary material",
  "material_details": "additional material information",
  "texture": "surface texture description",
  "style": "design style classification",
  "design_details": "specific design characteristics",
  "dimensions": "extracted or estimated dimensions",
  "size_category": "small/medium/large",
  "enhanced_prompt": "A concise prompt combining all visual details for AI image generation"
}}"""

            # Prepare messages with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": vision_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": product_image_url,
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]

            # Call ChatGPT Vision API with timeout
            start_time = time.time()
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.openai_model,  # gpt-4-vision-preview or gpt-4o
                    messages=messages,
                    max_tokens=1000,
                    temperature=0.3,  # Low temperature for factual analysis
                    response_format={"type": "json_object"}
                ),
                timeout=30.0
            )

            response_time = time.time() - start_time

            # Extract response content
            response_content = response.choices[0].message.content if response.choices else None
            if not response_content:
                logger.warning("ChatGPT Vision API returned empty response")
                return None

            # Parse JSON response
            import json
            result = json.loads(response_content)

            logger.info(f"ChatGPT Vision API analysis completed in {response_time:.2f}s")
            logger.info(f"Extracted color: {result.get('exact_color')}, material: {result.get('material')}, style: {result.get('style')}")

            return result

        except asyncio.TimeoutError:
            logger.warning("ChatGPT Vision API timeout - falling back to local extraction")
            return None
        except Exception as e:
            logger.warning(f"ChatGPT Vision API failed: {e} - falling back to local extraction")
            return None

    def _generate_depth_map(self, image: Image.Image) -> Image.Image:
        """
        Generate depth map from room image for structure preservation

        Simple depth estimation using grayscale conversion and blur
        For production, consider using MiDaS or other depth estimation models

        Args:
            image: Input PIL Image (room photo)

        Returns:
            PIL Image of depth map (grayscale)
        """
        try:
            # Convert PIL Image to numpy array
            img_array = np.array(image)

            # Convert to grayscale for simple depth approximation
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # Apply bilateral filter to preserve edges while smoothing
            # This creates a depth-like effect
            depth = cv2.bilateralFilter(gray, 9, 75, 75)

            # Normalize to 0-255 range
            depth = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX)

            # Convert back to PIL Image
            depth_image = Image.fromarray(depth.astype(np.uint8))

            logger.info(f"Generated depth map: {depth_image.size}")
            return depth_image

        except Exception as e:
            logger.error(f"Failed to generate depth map: {e}")
            # Return a blank depth map as fallback
            return Image.new('L', image.size, color=128)

    def _generate_canny_edge_image(self, image: Image.Image) -> Image.Image:
        """
        Generate Canny edge detection image from room image for structure preservation

        This edge map will be used by Canny ControlNet to preserve the full room structure
        (walls, floor, windows, doors) while only replacing furniture in the masked area.

        Args:
            image: Input PIL Image (room photo)

        Returns:
            PIL Image of Canny edges (grayscale)
        """
        try:
            # Convert PIL Image to numpy array
            img_array = np.array(image)

            # Convert RGB to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # Apply Gaussian blur to reduce noise
            # Kernel size (5,5) and sigma=1.4 provide good edge quality
            blurred = cv2.GaussianBlur(gray, (5, 5), 1.4)

            # Apply Canny edge detection
            # Low threshold: 50, High threshold: 150 (recommended 1:2 or 1:3 ratio)
            # These values capture structural edges while ignoring texture details
            edges = cv2.Canny(blurred, 50, 150)

            # Convert back to PIL Image
            edge_image = Image.fromarray(edges)

            logger.info(f"Generated Canny edge map: {edge_image.size}")
            return edge_image

        except Exception as e:
            logger.error(f"Failed to generate Canny edge image: {e}")
            # Return a blank edge map as fallback
            return Image.new('L', image.size, color=0)

    def _decode_base64_image(self, base64_string: str) -> Image.Image:
        """Decode base64 string to PIL Image"""
        try:
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]

            image_bytes = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image)

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

    def _image_to_data_uri(self, image: Image.Image) -> str:
        """Convert PIL Image to data URI"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_base64}"

    async def _download_image(self, url: str) -> Image.Image:
        """Download image from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        image = Image.open(io.BytesIO(image_bytes))
                        image = ImageOps.exif_transpose(image)

                        if image.mode != 'RGB':
                            image = image.convert('RGB')

                        return image
                    else:
                        raise Exception(f"Failed to download: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            raise

    async def _analyze_product_with_chatgpt_vision(self, image_url: str, product_name: str) -> Optional[str]:
        """
        Analyze product image with ChatGPT Vision to generate detailed description

        Args:
            image_url: URL to product image
            product_name: Product name for context

        Returns: Detailed visual description including size, color, dimensions, texture, style
        """
        try:
            from api.services.chatgpt_service import chatgpt_service

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

    async def _run_text_only_inpainting(
        self,
        room_image: Image.Image,
        mask: Image.Image,
        prompt: str,
        product: Dict[str, Any],
        negative_prompt: Optional[str] = None
    ) -> str:
        """
        Run inpainting with text-only prompts (NO IP-Adapter)
        Uses MajicMIX Realistic model with ChatGPT Vision-enhanced prompts

        Args:
            room_image: Room image (PIL Image)
            mask: Placement mask (PIL Image)
            prompt: Text prompt (enhanced with ChatGPT Vision description)
            product: Product dict for logging

        Returns: Base64-encoded result image with data URL prefix
        """
        try:
            model_version = settings.replicate_sdxl_inpaint_model
            logger.info(f"Using SDXL Inpainting model (TEXT-ONLY): {model_version}")

            # Resize to 512x512 for model compatibility
            original_size = room_image.size
            room_image_512 = room_image.resize((512, 512), Image.Resampling.LANCZOS)
            mask_512 = mask.resize((512, 512), Image.Resampling.LANCZOS)

            # Convert to base64
            room_data_uri = self._image_to_data_uri(room_image_512)
            mask_data_uri = self._image_to_data_uri(mask_512)

            # Log parameters
            logger.info("SDXL Text-Only Inpainting Parameters:")
            logger.info(f"  - Model: lucataco/sdxl-inpainting (text-only mode)")
            logger.info(f"  - Prompt: {prompt[:100]}...")
            logger.info(f"  - Image size: 512x512")
            logger.info(f"  - NO IP-Adapter (text-only)")

            # Create prediction with TEXT-ONLY parameters (NO IP-Adapter!)
            def create_prediction():
                """Create prediction (synchronous call in thread)"""
                return replicate.predictions.create(
                    version=model_version,
                    input={
                        "prompt": prompt,
                        "image": room_data_uri,
                        "mask": mask_data_uri,
                        # NO ip_adapter_image - text-only!
                        "negative_prompt": negative_prompt or self._build_negative_prompt(),
                        "num_inference_steps": 35,
                        "guidance_scale": 9.5,
                        "strength": 0.99
                    }
                )

            # Run in thread pool
            prediction = await asyncio.to_thread(create_prediction)
            logger.info(f"Prediction created: {prediction.id}, status: {prediction.status}")

            # Wait for completion
            max_wait = 300  # 5 minutes
            start_time = time.time()
            wait_logged = False

            while prediction.status not in ["succeeded", "failed", "canceled"]:
                if time.time() - start_time > max_wait:
                    raise TimeoutError(f"Prediction timed out after {max_wait}s")

                if not wait_logged:
                    logger.info(f"Waiting for prediction {prediction.id}...")
                    wait_logged = True

                await asyncio.sleep(1)
                prediction = await asyncio.to_thread(replicate.predictions.get, prediction.id)

            if prediction.status != "succeeded":
                raise Exception(f"Prediction failed: {prediction.status}")

            # Get result URL
            output_url = prediction.output[0] if isinstance(prediction.output, list) else prediction.output

            # Download and resize back to original
            result_image = await self._download_image(output_url)
            result_image_original = result_image.resize(original_size, Image.Resampling.LANCZOS)

            # Convert to base64 data URI
            result_data_uri = self._image_to_data_uri(result_image_original)

            logger.info(f"Text-only inpainting successful, resized back to {original_size}")
            return result_data_uri

        except Exception as e:
            logger.error(f"Text-only inpainting failed: {e}", exc_info=True)
            raise

    async def _remove_existing_furniture(
        self,
        room_image: Image.Image,
        furniture_to_remove: List[Dict[str, Any]],
        remove_all: bool = True
    ) -> Optional['InpaintingResult']:
        """
        BUG #2 FIX: Remove existing furniture by inpainting with empty space

        This is Pass 1 of two-pass inpainting for replace actions.

        Args:
            room_image: Room image (PIL Image)
            furniture_to_remove: List of furniture detections to remove
            remove_all: If True, remove all furniture. If False, remove only the first one.

        Returns:
            InpaintingResult with cleaned image (furniture removed)
        """
        try:
            logger.info(f"BUG #2 FIX: Removing {len(furniture_to_remove)} furniture item(s)")

            # Generate mask for furniture removal
            removal_mask = await self._generate_removal_mask_from_detections(
                room_image=room_image,
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

            # Run SDXL inpainting to remove furniture
            result_data_uri = await self._run_text_only_inpainting(
                room_image=room_image,
                mask=removal_mask,
                prompt=removal_prompt,
                product={"name": "removal"},  # Dummy product for logging
                negative_prompt=removal_negative_prompt  # Custom negative prompt for removal
            )

            if result_data_uri:
                logger.info(f"BUG #2 FIX: Successfully removed furniture, cleaned image ready for Pass 2")
                # Create InpaintingResult with the cleaned image (class defined at top of this file)
                return InpaintingResult(
                    rendered_image=result_data_uri,
                    processing_time=0.0,
                    success=True
                )
            else:
                logger.error(f"BUG #2 FIX: Furniture removal failed")
                return None

        except Exception as e:
            logger.error(f"BUG #2 FIX: Error in _remove_existing_furniture: {e}", exc_info=True)
            return None

    async def _generate_removal_mask_from_detections(
        self,
        room_image: Image.Image,
        furniture_detections: List[Dict[str, Any]],
        remove_all: bool = True
    ) -> Image.Image:
        """
        BUG #2 FIX: Generate mask for removing detected furniture

        White pixels (255) = remove furniture (inpaint area)
        Black pixels (0) = preserve room (keep as-is)

        Args:
            room_image: PIL Image
            furniture_detections: List of furniture with bounding boxes
            remove_all: If True, mask all furniture. If False, mask only first one.

        Returns:
            PIL Image mask
        """
        try:
            width, height = room_image.size

            # Create mask (start with all black = preserve everything)
            mask = np.zeros((height, width), dtype=np.uint8)

            # Mark each furniture location for removal using bounding boxes
            items_to_remove = furniture_detections if remove_all else [furniture_detections[0]]

            for furniture in items_to_remove:
                bbox = furniture.get('bounding_box')
                if bbox and all(key in bbox for key in ['x1', 'y1', 'x2', 'y2']):
                    # Bounding box coordinates (normalized 0-1)
                    x1 = int(bbox['x1'] * width)
                    y1 = int(bbox['y1'] * height)
                    x2 = int(bbox['x2'] * width)
                    y2 = int(bbox['y2'] * height)

                    # Ensure valid coordinates
                    x1 = max(0, min(x1, width))
                    x2 = max(0, min(x2, width))
                    y1 = max(0, min(y1, height))
                    y2 = max(0, min(y2, height))

                    # Fill the bounding box with white (remove this area)
                    mask[y1:y2, x1:x2] = 255

                    logger.info(f"BUG #2 FIX: Removal mask for {furniture.get('object_type', 'furniture')}: bbox ({x1},{y1})-({x2},{y2})")
                else:
                    logger.warning(f"BUG #2 FIX: No bounding box for {furniture.get('object_type', 'furniture')}, skipping")

            # Convert mask to PIL Image
            mask_image = Image.fromarray(mask, mode='L')

            logger.info(f"BUG #2 FIX: Generated removal mask for {len(items_to_remove)} furniture item(s)")
            return mask_image

        except Exception as e:
            logger.error(f"BUG #2 FIX: Error generating removal mask: {e}", exc_info=True)
            # Return empty mask on error
            return Image.new('L', (width, height), color=0)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            **self.usage_stats,
            "success_rate": (
                self.usage_stats["successful_requests"] /
                max(self.usage_stats["total_requests"], 1) * 100
            )
        }


# Global service instance
cloud_inpainting_service = CloudInpaintingService()
