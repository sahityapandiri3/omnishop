"""
SAM (Segment Anything Model) Service for automatic object segmentation.

Uses Replicate's SAM API to detect and extract furniture objects from room images
with precise segmentation masks (not just bounding boxes).

This enables the "Magic Grab" style editing where users can:
1. See all objects detected automatically
2. Click and drag any object in real-time
3. Get clean cutouts with transparency for compositing
"""
import asyncio
import base64
import io
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SegmentedObject:
    """A single segmented object from SAM."""

    id: str
    label: Optional[str]  # Optional label from Gemini identification
    cutout: str  # Base64 PNG with transparency
    mask: str  # Base64 binary mask
    bbox: Dict[str, float]  # {"x": 0.2, "y": 0.3, "width": 0.15, "height": 0.2}
    center: Dict[str, float]  # {"x": 0.275, "y": 0.4}
    area: float  # Percentage of image area (0-1)
    stability_score: float  # SAM's confidence score


@dataclass
class SegmentationResult:
    """Result from SAM segmentation."""

    objects: List[SegmentedObject]
    processing_time: float
    image_dimensions: Dict[str, int]  # {"width": 1024, "height": 768}


class SAMService:
    """
    Service for automatic object segmentation using SAM via Replicate.

    Architecture:
    - Uses Replicate's SAM automatic mask generator
    - Returns all detected objects with transparent cutouts
    - Can filter by size to focus on furniture-sized objects
    """

    def __init__(self):
        """Initialize SAM service with Replicate API."""
        self.api_key = settings.replicate_api_key

        # SAM model on Replicate - automatic mask generator
        # Using pablodawson/segment-anything-automatic with specific version
        # Version ID confirmed working: 14fbb04535964b3d0c7fad03bb4ed272130f15b956cbedb7b2f20b5b8a2dbaa0
        self.sam_model = (
            "pablodawson/segment-anything-automatic:14fbb04535964b3d0c7fad03bb4ed272130f15b956cbedb7b2f20b5b8a2dbaa0"
        )

        # SAM model for point-based segmentation (click-to-select)
        # Uses ocg2347/sam-pointprompt which supports point prompts for images
        self.sam_pointprompt_model = "ocg2347/sam-pointprompt:0fae4c357d9bdd3822a1c8d6cd949e2b78fab3c860f4ef9df1e01a171fe84906"

        self.usage_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "last_reset": datetime.now(),
        }

        self._validate_api_key()

        # Set Replicate API token
        if self.api_key:
            os.environ["REPLICATE_API_TOKEN"] = self.api_key

        logger.info("SAM Service initialized")

    def _validate_api_key(self):
        """Validate Replicate API key exists."""
        if not self.api_key:
            logger.warning("Replicate API key not configured - SAM segmentation will not work")
            # Try to get from environment as fallback
            import os

            env_key = os.environ.get("REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_KEY")
            if env_key:
                self.api_key = env_key
                os.environ["REPLICATE_API_TOKEN"] = env_key
                logger.info(f"Replicate API key loaded from environment: {env_key[:15]}...")
        else:
            logger.info(f"Replicate API key validated for SAM: {self.api_key[:15]}...")

    async def segment_all_objects(
        self,
        image_base64: str,
        min_area_percent: float = 0.5,  # Minimum object size (% of image)
        max_objects: int = 20,  # Maximum objects to return
        stability_threshold: float = 0.85,  # SAM confidence threshold
        furniture_filter: bool = True,  # Filter for furniture-like objects
    ) -> SegmentationResult:
        """
        Automatically segment ALL objects in the image using SAM.

        This is the core method for Magic Grab functionality.

        Args:
            image_base64: Base64 encoded image (with or without data URL prefix)
            min_area_percent: Minimum object size as percentage of image (filter noise)
            max_objects: Maximum number of objects to return
            stability_threshold: SAM stability score threshold (higher = more confident)
            furniture_filter: If True, filter to furniture-like objects based on size/position

        Returns:
            SegmentationResult with list of SegmentedObject items
        """
        start_time = time.time()
        self.usage_stats["total_requests"] += 1

        try:
            logger.info("[SAM] Starting automatic segmentation")

            # Preprocess image
            image_data, pil_image = self._prepare_image(image_base64)
            width, height = pil_image.size
            logger.info(f"[SAM] Image size: {width}x{height}")

            # Call SAM via Replicate
            masks = await self._call_sam_api(image_data, pil_image)
            logger.info(f"[SAM] Got {len(masks)} raw masks from SAM")

            # Process masks into SegmentedObject instances
            objects = []
            for i, mask_data in enumerate(masks):
                try:
                    # Calculate mask area
                    area = mask_data.get("area", 0) / (width * height)

                    # Skip very small objects (noise) - less than 0.5%
                    if area < min_area_percent / 100:
                        logger.debug(f"[SAM] Skipping mask {i}: too small (area={area:.4f})")
                        continue

                    # Skip low-confidence masks
                    stability = mask_data.get("stability_score", 0)
                    if stability < stability_threshold:
                        logger.debug(f"[SAM] Skipping mask {i}: low stability ({stability:.2f})")
                        continue

                    # Get bounding box to check furniture-like characteristics
                    bbox_raw = mask_data.get("bbox", [0, 0, width, height])
                    if isinstance(bbox_raw, list) and len(bbox_raw) >= 4:
                        bx, by, bw, bh = bbox_raw[:4]
                    else:
                        bx, by, bw, bh = 0, 0, width, height

                    # Normalize bbox
                    norm_x = bx / width
                    norm_y = by / height
                    norm_w = bw / width
                    norm_h = bh / height
                    norm_center_y = norm_y + norm_h / 2

                    # Apply furniture filter
                    if furniture_filter:
                        # Skip objects that are too large (likely walls, ceiling, floor)
                        if area > 0.5:  # More than 50% of image
                            logger.info(f"[SAM] Skipping mask {i}: too large for furniture (area={area:.2f})")
                            continue

                        # Skip objects near the top of image (likely ceiling/AC)
                        if norm_center_y < 0.2:  # Top 20% of image
                            logger.info(f"[SAM] Skipping mask {i}: too high (likely ceiling) y={norm_center_y:.2f}")
                            continue

                        # Skip very wide/short objects (likely floor baseboard)
                        aspect_ratio = norm_w / max(norm_h, 0.01)
                        if aspect_ratio > 8 and norm_h < 0.1:  # Very wide and thin
                            logger.info(f"[SAM] Skipping mask {i}: too wide/thin (floor?) aspect={aspect_ratio:.1f}")
                            continue

                        # Skip very tall/narrow objects on edges (likely walls)
                        if aspect_ratio < 0.15 and (norm_x < 0.05 or norm_x + norm_w > 0.95):
                            logger.info(f"[SAM] Skipping mask {i}: likely wall edge, aspect={aspect_ratio:.2f}")
                            continue

                    # Create cutout with transparency
                    cutout, mask_b64, bbox = self._create_cutout(pil_image, mask_data, width, height)

                    center = {"x": bbox["x"] + bbox["width"] / 2, "y": bbox["y"] + bbox["height"] / 2}

                    obj = SegmentedObject(
                        id=f"obj_{i}",
                        label=None,  # Will be filled by Gemini later
                        cutout=cutout,
                        mask=mask_b64,
                        bbox=bbox,
                        center=center,
                        area=area,
                        stability_score=stability,
                    )
                    objects.append(obj)
                    logger.info(
                        f"[SAM] Kept mask {i}: area={area:.3f}, center=({center['x']:.2f}, {center['y']:.2f}), bbox=({bbox['x']:.2f}, {bbox['y']:.2f}, {bbox['width']:.2f}, {bbox['height']:.2f})"
                    )

                    if len(objects) >= max_objects:
                        break

                except Exception as e:
                    logger.warning(f"[SAM] Failed to process mask {i}: {e}")
                    continue

            # Sort by area (largest first - furniture is usually larger)
            objects.sort(key=lambda x: x.area, reverse=True)

            processing_time = time.time() - start_time
            self.usage_stats["successful_requests"] += 1
            self.usage_stats["total_processing_time"] += processing_time

            logger.info(f"[SAM] Segmentation complete: {len(objects)} objects in {processing_time:.2f}s")

            return SegmentationResult(
                objects=objects, processing_time=processing_time, image_dimensions={"width": width, "height": height}
            )

        except Exception as e:
            self.usage_stats["failed_requests"] += 1
            logger.error(f"[SAM] Segmentation failed: {e}")
            raise

    async def segment_with_points(
        self,
        image_base64: str,
        points: List[Dict[str, float]],  # [{"x": 0.5, "y": 0.5, "label": 1}]
    ) -> SegmentationResult:
        """
        Segment specific objects using point prompts.

        Useful when user clicks on a specific object that SAM automatic
        detection might have missed or merged with another.

        Args:
            image_base64: Base64 encoded image
            points: List of points with normalized x, y and label (1=foreground, 0=background)

        Returns:
            SegmentationResult with segmented objects at each point
        """
        start_time = time.time()
        self.usage_stats["total_requests"] += 1

        try:
            image_data, pil_image = self._prepare_image(image_base64)
            width, height = pil_image.size

            # Convert normalized points to pixel coordinates
            pixel_points = []
            labels = []
            for pt in points:
                pixel_points.append([int(pt["x"] * width), int(pt["y"] * height)])
                labels.append(pt.get("label", 1))

            # Call SAM with point prompts
            masks = await self._call_sam_with_points(image_data, pil_image, pixel_points, labels)

            objects = []
            for i, mask_data in enumerate(masks):
                try:
                    area = mask_data.get("area", 0) / (width * height)
                    stability = mask_data.get("stability_score", 0.9)

                    cutout, mask_b64, bbox = self._create_cutout(pil_image, mask_data, width, height)

                    center = {"x": bbox["x"] + bbox["width"] / 2, "y": bbox["y"] + bbox["height"] / 2}

                    obj = SegmentedObject(
                        id=f"point_obj_{i}",
                        label=None,
                        cutout=cutout,
                        mask=mask_b64,
                        bbox=bbox,
                        center=center,
                        area=area,
                        stability_score=stability,
                    )
                    objects.append(obj)

                except Exception as e:
                    logger.warning(f"[SAM] Failed to process point mask {i}: {e}")

            processing_time = time.time() - start_time
            self.usage_stats["successful_requests"] += 1

            return SegmentationResult(
                objects=objects, processing_time=processing_time, image_dimensions={"width": width, "height": height}
            )

        except Exception as e:
            self.usage_stats["failed_requests"] += 1
            logger.error(f"[SAM] Point segmentation failed: {e}")
            raise

    def _prepare_image(self, image_base64: str) -> tuple:
        """
        Prepare image for SAM processing.

        Returns:
            Tuple of (clean base64 data, PIL Image)
        """
        # Remove data URL prefix if present
        image_data = image_base64
        if image_data.startswith("data:image"):
            image_data = image_data.split(",")[1]

        # Decode to PIL
        image_bytes = base64.b64decode(image_data)
        pil_image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB (SAM expects RGB)
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        return image_data, pil_image

    async def _call_sam_api(self, image_data: str, pil_image: Image.Image) -> List[Dict[str, Any]]:
        """
        Call SAM automatic mask generator via Replicate.

        Returns list of mask dictionaries with:
        - segmentation: binary mask data
        - area: pixel count
        - bbox: [x, y, w, h] in pixels
        - stability_score: confidence
        """
        import replicate

        # Create data URL for Replicate
        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=90)
        buffer.seek(0)
        image_url = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"

        try:
            # Use pablodawson/segment-anything-automatic for automatic mask generation
            # This model auto-generates masks for all objects in the image
            logger.info(f"[SAM] Calling Replicate model: {self.sam_model}")
            output = await asyncio.to_thread(
                replicate.run,
                self.sam_model,
                input={
                    "image": image_url,
                    "resize_width": 1024,  # Standard size for good results
                    "points_per_side": 32,  # Detection density (higher = more masks)
                    "pred_iou_thresh": 0.88,  # Quality threshold
                    "stability_score_thresh": 0.92,  # Stability threshold
                    "crops_n_layers": 0,  # Number of crop layers (0 = no cropping)
                    "min_mask_region_area": 100,  # Minimum mask area in pixels
                },
            )

            logger.info(f"[SAM] Replicate returned output type: {type(output)}")

            # Parse SAM automatic output
            # pablodawson/segment-anything-automatic returns different format
            masks = self._parse_sam_automatic_output(output, pil_image.size)
            return masks

        except Exception as e:
            logger.error(f"[SAM] Replicate API call failed: {e}")
            # Fallback to simpler segmentation if SAM fails
            return await self._fallback_segmentation(pil_image)

    async def _call_sam_with_points(
        self, image_data: str, pil_image: Image.Image, points: List[List[int]], labels: List[int]
    ) -> List[Dict[str, Any]]:
        """Call SAM with point prompts."""
        import replicate

        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=90)
        buffer.seek(0)
        image_url = f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"

        try:
            output = await asyncio.to_thread(
                replicate.run,
                "meta/sam-2-base",
                input={
                    "image": image_url,
                    "point_coords": points,
                    "point_labels": labels,
                    "multimask_output": True,
                },
            )

            masks = self._parse_sam_output(output, pil_image.size)
            return masks

        except Exception as e:
            logger.error(f"[SAM] Point-based segmentation failed: {e}")
            return []

    def _parse_sam_output(self, output: Any, image_size: tuple) -> List[Dict[str, Any]]:
        """
        Parse SAM Replicate output into mask dictionaries.

        SAM 2 returns mask images that need to be converted to our format.
        """
        masks = []
        width, height = image_size

        # Handle different output formats from Replicate
        if isinstance(output, dict):
            # Single mask output
            if "mask" in output:
                masks.append(self._process_mask_output(output, width, height))
        elif isinstance(output, list):
            # Multiple masks
            for item in output:
                if isinstance(item, dict) and "mask" in item:
                    masks.append(self._process_mask_output(item, width, height))
                elif isinstance(item, str) and item.startswith("http"):
                    # URL to mask image
                    masks.append(self._fetch_mask_from_url(item, width, height))
        elif isinstance(output, str):
            # Single URL to combined mask
            masks.append(self._fetch_mask_from_url(output, width, height))

        return masks

    def _process_mask_output(self, mask_dict: Dict, width: int, height: int) -> Dict[str, Any]:
        """Process a single mask dictionary from SAM."""
        mask_data = mask_dict.get("mask", "")

        # Calculate bounding box if not provided
        bbox = mask_dict.get("bbox", [0, 0, width, height])
        if isinstance(bbox, list) and len(bbox) == 4:
            x, y, w, h = bbox
        else:
            x, y, w, h = 0, 0, width, height

        return {
            "segmentation": mask_data,
            "bbox": [x, y, w, h],
            "area": mask_dict.get("area", w * h),
            "stability_score": mask_dict.get("stability_score", 0.9),
        }

    def _fetch_mask_from_url(self, url: str, width: int, height: int) -> Dict[str, Any]:
        """Fetch mask image from URL and convert to our format."""
        import httpx

        try:
            response = httpx.get(url, timeout=30.0)
            response.raise_for_status()

            mask_image = Image.open(io.BytesIO(response.content))
            mask_array = np.array(mask_image)

            # Find non-zero pixels for bounding box
            if len(mask_array.shape) == 3:
                mask_array = mask_array[:, :, 0]  # Take first channel

            non_zero = np.where(mask_array > 127)
            if len(non_zero[0]) > 0:
                y_min, y_max = non_zero[0].min(), non_zero[0].max()
                x_min, x_max = non_zero[1].min(), non_zero[1].max()
                bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
                area = len(non_zero[0])
            else:
                bbox = [0, 0, width, height]
                area = 0

            # Convert mask to base64
            mask_b64 = base64.b64encode(response.content).decode()

            return {"segmentation": mask_b64, "bbox": bbox, "area": area, "stability_score": 0.9}

        except Exception as e:
            logger.error(f"[SAM] Failed to fetch mask from URL: {e}")
            return {"segmentation": "", "bbox": [0, 0, width, height], "area": 0, "stability_score": 0.5}

    def _parse_sam_automatic_output(self, output: Any, image_size: tuple) -> List[Dict[str, Any]]:
        """
        Parse output from pablodawson/segment-anything-automatic model.

        This model typically returns a single combined PNG image where each
        detected object is shown in a different color. We need to extract
        individual masks from this combined image.

        Can also handle:
        - URL to a JSON file with masks
        - Dict with masks
        - List of mask URLs
        """
        import httpx

        masks = []
        width, height = image_size

        logger.info(f"[SAM] Parsing automatic output: {type(output)}")

        try:
            # Handle URL output (most common - model returns URL to combined mask image)
            if isinstance(output, str) and output.startswith("http"):
                logger.info(f"[SAM] Fetching masks from URL: {output[:100]}...")
                response = httpx.get(output, timeout=60.0)
                response.raise_for_status()

                # Check content type to determine format
                content_type = response.headers.get("content-type", "")
                logger.info(f"[SAM] Response content-type: {content_type}")

                if "json" in content_type or output.endswith(".json"):
                    # JSON format with individual masks
                    data = response.json()
                    if isinstance(data, list):
                        masks = self._process_mask_list(data, width, height)
                    elif isinstance(data, dict) and "masks" in data:
                        masks = self._process_mask_list(data["masks"], width, height)
                else:
                    # Image format - this is a COMBINED mask with different colors for each object
                    # Extract individual masks from the color-coded image
                    logger.info("[SAM] Output is combined mask image - extracting individual masks by color")
                    masks = self._extract_individual_masks_from_combined(
                        response.content, width, height, min_area=500  # Filter out small noise regions
                    )

                    # If color extraction failed, fall back to treating as single mask
                    if not masks:
                        logger.warning("[SAM] Color extraction failed, treating as single mask")
                        masks.append(self._process_mask_image(response.content, width, height))

            # Handle dict with masks
            elif isinstance(output, dict):
                if "masks" in output:
                    masks = self._process_mask_list(output["masks"], width, height)
                elif "combined_mask" in output:
                    # Single combined mask URL
                    mask_url = output["combined_mask"]
                    if isinstance(mask_url, str) and mask_url.startswith("http"):
                        response = httpx.get(mask_url, timeout=30.0)
                        masks = self._extract_individual_masks_from_combined(response.content, width, height)

            # Handle list of masks or URLs
            elif isinstance(output, list):
                for item in output:
                    if isinstance(item, str) and item.startswith("http"):
                        # URL to mask image - could be individual or combined
                        response = httpx.get(item, timeout=30.0)
                        # If it's a list of URLs, each is likely an individual mask
                        masks.append(self._process_mask_image(response.content, width, height))
                    elif isinstance(item, dict):
                        masks.append(self._process_mask_dict(item, width, height))

            logger.info(f"[SAM] Parsed {len(masks)} masks from automatic output")
            return masks

        except Exception as e:
            logger.error(f"[SAM] Error parsing automatic output: {e}", exc_info=True)
            return []

    def _process_mask_list(self, mask_list: List[Any], width: int, height: int) -> List[Dict[str, Any]]:
        """Process a list of mask objects."""
        masks = []
        for item in mask_list:
            if isinstance(item, dict):
                masks.append(self._process_mask_dict(item, width, height))
        return masks

    def _process_mask_dict(self, mask_dict: Dict, width: int, height: int) -> Dict[str, Any]:
        """Process a mask dictionary from SAM automatic."""
        # Handle different key names
        mask_data = mask_dict.get("segmentation") or mask_dict.get("mask") or ""
        bbox = mask_dict.get("bbox", mask_dict.get("bounding_box", [0, 0, width, height]))

        # Normalize bbox format
        if isinstance(bbox, list) and len(bbox) == 4:
            x, y, w, h = bbox
        else:
            x, y, w, h = 0, 0, width, height

        return {
            "segmentation": mask_data,
            "bbox": [x, y, w, h],
            "area": mask_dict.get("area", w * h),
            "stability_score": mask_dict.get("stability_score", mask_dict.get("predicted_iou", 0.9)),
        }

    def _process_mask_image(self, image_content: bytes, width: int, height: int) -> Dict[str, Any]:
        """Process a mask image (PNG/JPEG) and extract bbox."""
        try:
            mask_image = Image.open(io.BytesIO(image_content))
            mask_array = np.array(mask_image)

            # Handle different image formats
            if len(mask_array.shape) == 3:
                if mask_array.shape[2] == 4:  # RGBA
                    mask_array = mask_array[:, :, 3]  # Use alpha channel
                else:
                    mask_array = mask_array[:, :, 0]  # Use first channel

            # Find bounding box from non-zero pixels
            non_zero = np.where(mask_array > 127)
            if len(non_zero[0]) > 0:
                y_min, y_max = int(non_zero[0].min()), int(non_zero[0].max())
                x_min, x_max = int(non_zero[1].min()), int(non_zero[1].max())
                bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
                area = int(len(non_zero[0]))
            else:
                bbox = [0, 0, width, height]
                area = 0

            # Convert to base64
            mask_b64 = base64.b64encode(image_content).decode()

            return {"segmentation": mask_b64, "bbox": bbox, "area": area, "stability_score": 0.9}

        except Exception as e:
            logger.error(f"[SAM] Failed to process mask image: {e}")
            return {"segmentation": "", "bbox": [0, 0, width, height], "area": 0, "stability_score": 0.5}

    def _extract_individual_masks_from_combined(
        self, image_content: bytes, width: int, height: int, min_area: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Extract individual object masks from a combined color mask image.

        SAM automatic mask generators often return a single image where each
        detected object is shown in a different color. This method separates
        them into individual binary masks.

        Args:
            image_content: Raw bytes of the combined mask image
            width, height: Original image dimensions
            min_area: Minimum pixel area for a valid mask

        Returns:
            List of mask dictionaries, each representing one object
        """
        try:
            mask_image = Image.open(io.BytesIO(image_content)).convert("RGB")

            # Resize mask to match original image if needed
            if mask_image.size != (width, height):
                mask_image = mask_image.resize((width, height), Image.NEAREST)

            mask_array = np.array(mask_image)

            logger.info(f"[SAM] Combined mask image shape: {mask_array.shape}")

            # Find unique colors (each color = one object)
            # Reshape to 2D array of RGB values
            pixels = mask_array.reshape(-1, 3)
            unique_colors = np.unique(pixels, axis=0)

            logger.info(f"[SAM] Found {len(unique_colors)} unique colors in mask")

            masks = []
            for color in unique_colors:
                # Skip black (background) and near-black colors
                if np.sum(color) < 30:
                    continue

                # Skip white/near-white (often background too)
                if np.sum(color) > 700:
                    continue

                # Create binary mask for this color
                color_match = np.all(mask_array == color, axis=2)
                binary_mask = (color_match * 255).astype(np.uint8)

                # Calculate area
                area = np.sum(color_match)

                # Skip small regions (noise)
                if area < min_area:
                    continue

                # Find bounding box
                non_zero = np.where(color_match)
                if len(non_zero[0]) == 0:
                    continue

                y_min, y_max = int(non_zero[0].min()), int(non_zero[0].max())
                x_min, x_max = int(non_zero[1].min()), int(non_zero[1].max())

                # Convert binary mask to PNG base64
                mask_pil = Image.fromarray(binary_mask)
                buffer = io.BytesIO()
                mask_pil.save(buffer, format="PNG")
                buffer.seek(0)
                mask_b64 = base64.b64encode(buffer.getvalue()).decode()

                masks.append(
                    {
                        "segmentation": mask_b64,
                        "bbox": [x_min, y_min, x_max - x_min, y_max - y_min],
                        "area": int(area),
                        "stability_score": 0.9,
                        "color": color.tolist(),  # Store original color for debugging
                    }
                )

                logger.info(
                    f"[SAM] Extracted mask: color={color.tolist()}, area={area}, bbox=[{x_min},{y_min},{x_max-x_min},{y_max-y_min}]"
                )

            # Sort by area (largest first)
            masks.sort(key=lambda x: x["area"], reverse=True)

            logger.info(f"[SAM] Extracted {len(masks)} individual masks from combined image")
            return masks

        except Exception as e:
            logger.error(f"[SAM] Failed to extract individual masks: {e}", exc_info=True)
            return []

    async def _fallback_segmentation(self, pil_image: Image.Image) -> List[Dict[str, Any]]:
        """
        Fallback segmentation using simple color-based detection.

        Used when SAM API fails. Less accurate but ensures some functionality.
        """
        logger.warning("[SAM] Using fallback segmentation")

        # Simple edge detection + contour finding
        # This is a basic fallback - not as good as SAM
        width, height = pil_image.size

        # Return empty list for now - let the frontend handle gracefully
        return []

    def _create_cutout(self, pil_image: Image.Image, mask_data: Dict[str, Any], width: int, height: int) -> tuple:
        """
        Create a transparent PNG cutout using the mask.

        Args:
            pil_image: Original image
            mask_data: Mask dictionary with segmentation data
            width, height: Image dimensions

        Returns:
            Tuple of (cutout_base64, mask_base64, normalized_bbox)
        """
        # Get mask as array
        mask_b64 = mask_data.get("segmentation", "")

        if isinstance(mask_b64, str) and mask_b64:
            try:
                mask_bytes = base64.b64decode(mask_b64)
                mask_image = Image.open(io.BytesIO(mask_bytes)).convert("L")
                mask_array = np.array(mask_image)
            except Exception:
                # Create full white mask as fallback
                mask_array = np.ones((height, width), dtype=np.uint8) * 255
        else:
            # No mask data - create from bbox
            bbox = mask_data.get("bbox", [0, 0, width, height])
            mask_array = np.zeros((height, width), dtype=np.uint8)
            x, y, w, h = [int(v) for v in bbox]
            mask_array[y : y + h, x : x + w] = 255

        # Create RGBA image with mask as alpha
        rgba_image = pil_image.convert("RGBA")

        # Resize mask if needed
        if mask_array.shape != (height, width):
            mask_pil = Image.fromarray(mask_array)
            mask_pil = mask_pil.resize((width, height), Image.NEAREST)
            mask_array = np.array(mask_pil)

        # Apply mask as alpha channel
        alpha = Image.fromarray(mask_array)
        rgba_image.putalpha(alpha)

        # Crop to bounding box
        bbox_pixels = mask_data.get("bbox", [0, 0, width, height])
        x, y, w, h = [int(v) for v in bbox_pixels]

        # Add small padding
        pad = 5
        x = max(0, x - pad)
        y = max(0, y - pad)
        w = min(width - x, w + 2 * pad)
        h = min(height - y, h + 2 * pad)

        cropped = rgba_image.crop((x, y, x + w, y + h))

        # Convert to base64
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        buffer.seek(0)
        cutout_b64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"

        # Mask as base64
        mask_buffer = io.BytesIO()
        alpha.crop((x, y, x + w, y + h)).save(mask_buffer, format="PNG")
        mask_buffer.seek(0)
        mask_out_b64 = base64.b64encode(mask_buffer.getvalue()).decode()

        # Normalized bounding box
        normalized_bbox = {"x": x / width, "y": y / height, "width": w / width, "height": h / height}

        return cutout_b64, mask_out_b64, normalized_bbox

    async def segment_at_point(self, image_base64: str, point: Dict[str, float], label: str = "object") -> SegmentedObject:
        """
        Segment object at a specific clicked point using SAM with point prompts.

        Uses ocg2347/sam-pointprompt model which supports direct point-based
        segmentation without needing to run automatic detection first.

        Args:
            image_base64: The image (with or without data URI prefix)
            point: {"x": 0.3, "y": 0.5} normalized coordinates (0-1)
            label: Optional label for the object

        Returns:
            SegmentedObject with cutout, mask, bbox, center
        """
        import tempfile
        import uuid

        import httpx
        import replicate

        start_time = time.time()
        self.usage_stats["total_requests"] += 1

        try:
            # Prepare image
            _, pil_image = self._prepare_image(image_base64)
            width, height = pil_image.size

            # Convert normalized coords to pixel coords
            pixel_x = int(point["x"] * width)
            pixel_y = int(point["y"] * height)

            logger.info(f"Segmenting at point ({pixel_x}, {pixel_y}) in {width}x{height} image")

            # Save image to temp file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                pil_image.save(tmp_file, format="PNG")
                tmp_path = tmp_file.name

            try:
                # Call SAM pointprompt model
                logger.info(f"Calling SAM pointprompt model with point ({pixel_x}, {pixel_y})...")
                with open(tmp_path, "rb") as f:
                    output = await asyncio.to_thread(
                        replicate.run,
                        self.sam_pointprompt_model,
                        input={"image": f, "input_points": f"[[{pixel_x},{pixel_y}]]"},
                    )
            finally:
                import os

                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            logger.info(f"SAM pointprompt output: {output}")

            # Output is a URL to the mask image
            if not output or not isinstance(output, str):
                raise ValueError(f"SAM pointprompt did not return a valid mask URL: {output}")

            # Fetch mask from URL with longer timeout (SAM models can be slow)
            async with httpx.AsyncClient(timeout=60.0) as client:
                mask_response = await client.get(output)
                mask_response.raise_for_status()

            # SAM pointprompt returns a binary mask image
            result_image = Image.open(io.BytesIO(mask_response.content))

            logger.info(f"SAM output image mode: {result_image.mode}, size: {result_image.size}")

            # Convert to grayscale/binary for mask processing
            if result_image.mode == "1":
                # Binary image - convert to L (grayscale)
                mask_image = result_image.convert("L")
            elif result_image.mode == "L":
                mask_image = result_image
            elif result_image.mode in ("RGB", "RGBA"):
                # If it's a color overlay, convert to grayscale
                mask_image = result_image.convert("L")
            else:
                mask_image = result_image.convert("L")

            # Resize if different from original
            if mask_image.size != (width, height):
                mask_image = mask_image.resize((width, height), Image.NEAREST)

            mask_array = np.array(mask_image)

            # For binary masks, white (255) is the segmented region
            # Ensure it's a proper binary mask
            mask_array = (mask_array > 128).astype(np.uint8) * 255

            logger.info(
                f"Mask stats: min={mask_array.min()}, max={mask_array.max()}, "
                f"white_pixels={np.sum(mask_array > 128)}, total={mask_array.size}"
            )

            # Calculate bounding box from mask
            rows = np.any(mask_array > 128, axis=1)
            cols = np.any(mask_array > 128, axis=0)

            if not rows.any() or not cols.any():
                raise ValueError("Mask is empty - no object detected at click point")

            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]

            # Add padding
            pad = 5
            rmin = max(0, rmin - pad)
            rmax = min(height - 1, rmax + pad)
            cmin = max(0, cmin - pad)
            cmax = min(width - 1, cmax + pad)

            bbox_width = cmax - cmin + 1
            bbox_height = rmax - rmin + 1

            # Create cutout with transparency
            rgba_image = pil_image.convert("RGBA")
            alpha = Image.fromarray(mask_array)
            rgba_image.putalpha(alpha)

            # Crop to bounding box
            cropped = rgba_image.crop((cmin, rmin, cmax + 1, rmax + 1))

            # Convert cutout to base64
            cutout_buffer = io.BytesIO()
            cropped.save(cutout_buffer, format="PNG")
            cutout_buffer.seek(0)
            cutout_b64 = f"data:image/png;base64,{base64.b64encode(cutout_buffer.getvalue()).decode()}"

            # Convert cropped mask to base64
            cropped_mask = alpha.crop((cmin, rmin, cmax + 1, rmax + 1))
            mask_buffer = io.BytesIO()
            cropped_mask.save(mask_buffer, format="PNG")
            mask_buffer.seek(0)
            mask_b64 = base64.b64encode(mask_buffer.getvalue()).decode()

            # Calculate normalized bbox
            normalized_bbox = {
                "x": cmin / width,
                "y": rmin / height,
                "width": bbox_width / width,
                "height": bbox_height / height,
            }

            # Calculate center
            center = {"x": (cmin + bbox_width / 2) / width, "y": (rmin + bbox_height / 2) / height}

            # Calculate area
            area = np.sum(mask_array > 128) / (width * height)

            processing_time = time.time() - start_time
            self.usage_stats["successful_requests"] += 1
            self.usage_stats["total_processing_time"] += processing_time

            logger.info(f"Point segmentation completed in {processing_time:.2f}s, area: {area:.2%}")

            return SegmentedObject(
                id=str(uuid.uuid4()),
                label=label,
                cutout=cutout_b64,
                mask=mask_b64,
                bbox=normalized_bbox,
                center=center,
                area=area,
                stability_score=0.95,
            )

        except Exception as e:
            self.usage_stats["failed_requests"] += 1
            logger.error(f"Point segmentation failed: {e}")
            raise

    async def segment_at_points(
        self, image_base64: str, points: List[Dict[str, float]], label: str = "object"
    ) -> SegmentedObject:
        """
        Segment object using multiple point prompts (for grouped selection).

        Multiple points will be combined to select a larger region,
        useful for selecting sofa + pillows as one unit.

        Args:
            image_base64: The image (with or without data URI prefix)
            points: List of {"x": 0.3, "y": 0.5} normalized coordinates
            label: Label for the combined object

        Returns:
            SegmentedObject with cutout, mask, bbox, center
        """
        import tempfile
        import uuid

        import httpx
        import replicate

        if len(points) == 1:
            return await self.segment_at_point(image_base64, points[0], label)

        start_time = time.time()
        self.usage_stats["total_requests"] += 1

        try:
            # Prepare image
            _, pil_image = self._prepare_image(image_base64)
            width, height = pil_image.size

            # Convert all points to pixel coords
            pixel_points = [[int(p["x"] * width), int(p["y"] * height)] for p in points]

            logger.info(f"Segmenting at {len(points)} points in {width}x{height} image")

            # Save image to temp file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                pil_image.save(tmp_file, format="PNG")
                tmp_path = tmp_file.name

            try:
                # Format for SAM pointprompt: [[x1,y1],[x2,y2],...]
                points_str = ",".join([f"[{p[0]},{p[1]}]" for p in pixel_points])
                input_points = f"[{points_str}]"

                logger.info(f"Calling SAM pointprompt model with {len(points)} points...")

                # Call SAM pointprompt with multiple points
                with open(tmp_path, "rb") as f:
                    output = await asyncio.to_thread(
                        replicate.run, self.sam_pointprompt_model, input={"image": f, "input_points": input_points}
                    )
            finally:
                import os

                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            logger.info(f"SAM pointprompt multi-point output: {output}")

            # Output is a URL to the mask image
            if not output or not isinstance(output, str):
                raise ValueError(f"SAM pointprompt did not return a valid mask URL: {output}")

            # Fetch mask from URL with longer timeout (SAM models can be slow)
            async with httpx.AsyncClient(timeout=60.0) as client:
                mask_response = await client.get(output)
                mask_response.raise_for_status()

            # Process result - SAM pointprompt returns a binary mask
            result_image = Image.open(io.BytesIO(mask_response.content))

            logger.info(f"SAM output image mode: {result_image.mode}, size: {result_image.size}")

            # Convert to grayscale for mask processing
            if result_image.mode == "1":
                mask_image = result_image.convert("L")
            else:
                mask_image = result_image.convert("L")

            if mask_image.size != (width, height):
                mask_image = mask_image.resize((width, height), Image.NEAREST)

            mask_array = np.array(mask_image)
            mask_array = (mask_array > 128).astype(np.uint8) * 255

            # Calculate bounding box from mask
            rows = np.any(mask_array > 128, axis=1)
            cols = np.any(mask_array > 128, axis=0)

            if not rows.any() or not cols.any():
                raise ValueError("Mask is empty - no objects detected at click points")

            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]

            # Add padding
            pad = 5
            rmin = max(0, rmin - pad)
            rmax = min(height, rmax + pad)
            cmin = max(0, cmin - pad)
            cmax = min(width, cmax + pad)

            bbox_width = cmax - cmin
            bbox_height = rmax - rmin

            # Create cutout with transparency
            rgba_image = pil_image.convert("RGBA")
            alpha = Image.fromarray(mask_array)
            rgba_image.putalpha(alpha)

            # Crop to bounding box
            cropped = rgba_image.crop((cmin, rmin, cmax, rmax))

            # Convert cutout to base64
            cutout_buffer = io.BytesIO()
            cropped.save(cutout_buffer, format="PNG")
            cutout_buffer.seek(0)
            cutout_b64 = f"data:image/png;base64,{base64.b64encode(cutout_buffer.getvalue()).decode()}"

            # Convert cropped mask to base64
            cropped_mask = alpha.crop((cmin, rmin, cmax, rmax))
            mask_buffer = io.BytesIO()
            cropped_mask.save(mask_buffer, format="PNG")
            mask_buffer.seek(0)
            mask_b64 = base64.b64encode(mask_buffer.getvalue()).decode()

            # Calculate normalized bbox
            normalized_bbox = {
                "x": cmin / width,
                "y": rmin / height,
                "width": bbox_width / width,
                "height": bbox_height / height,
            }

            # Calculate center
            center = {"x": (cmin + bbox_width / 2) / width, "y": (rmin + bbox_height / 2) / height}

            # Calculate area
            area = np.sum(mask_array > 128) / (width * height)

            processing_time = time.time() - start_time
            self.usage_stats["successful_requests"] += 1
            self.usage_stats["total_processing_time"] += processing_time

            logger.info(f"Multi-point segmentation completed in {processing_time:.2f}s")

            return SegmentedObject(
                id=str(uuid.uuid4()),
                label=label,
                cutout=cutout_b64,
                mask=mask_b64,
                bbox=normalized_bbox,
                center=center,
                area=area,
                stability_score=0.95,
            )

        except Exception as e:
            self.usage_stats["failed_requests"] += 1
            logger.error(f"SAM 2 multi-point segmentation failed: {e}")
            raise

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get service usage statistics."""
        return {
            **self.usage_stats,
            "average_processing_time": (
                self.usage_stats["total_processing_time"] / max(self.usage_stats["successful_requests"], 1)
            ),
        }


# Global service instance
sam_service = SAMService()
