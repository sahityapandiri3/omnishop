"""
Visualization API routes for spatial analysis and room rendering
"""
import base64
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from schemas.chat import ChatMessageSchema
from services.chatgpt_service import chatgpt_service
from services.google_ai_service import google_ai_service
from services.ml_recommendation_model import ml_recommendation_model
from services.recommendation_engine import RecommendationRequest, recommendation_engine
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from database.models import Product

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/visualization", tags=["visualization"])


# Request/Response Models
class RoomAnalysisRequest:
    def __init__(self, image_data: str, session_id: Optional[str] = None):
        self.image_data = image_data
        self.session_id = session_id


class SpatialAnalysisRequest:
    def __init__(self, room_analysis: Dict[str, Any], additional_context: Optional[str] = None):
        self.room_analysis = room_analysis
        self.additional_context = additional_context


class VisualizationGenerationRequest:
    def __init__(
        self, base_image: str, products: List[Dict[str, Any]], placement_preferences: Optional[Dict[str, Any]] = None
    ):
        self.base_image = base_image
        self.products = products
        self.placement_preferences = placement_preferences or {}


class ExtractLayersRequest(BaseModel):
    """Request model for furniture layer extraction (Magic Grab)"""

    visualization_image: str
    products: List[Dict[str, Any]]
    use_sam: bool = True  # Use SAM for precise segmentation (vs bounding box crops)
    curated_look_id: Optional[int] = None  # For cache lookup by curated look


class CompositeLayersRequest(BaseModel):
    """Request model for layer compositing"""

    background: str  # Base64 clean background image
    layers: List[Dict[str, Any]]  # List of {id, cutout, x, y, scale}
    harmonize: bool = False  # Apply AI lighting harmonization


class ProductInfo(BaseModel):
    """Product info for matching"""

    id: int
    name: str
    image_url: Optional[str] = None


class SegmentAtPointRequest(BaseModel):
    """Request model for click-to-select segmentation"""

    image_base64: str  # The visualization image
    point: Dict[str, float]  # {"x": 0.3, "y": 0.5} normalized coords
    label: Optional[str] = "object"  # Optional label for the object
    products: Optional[List[ProductInfo]] = None  # Products in the visualization for matching
    curated_look_id: Optional[int] = None  # For curated looks cache lookup


class SegmentAtPointsRequest(BaseModel):
    """Request model for multi-point selection (e.g., sofa + pillows)"""

    image_base64: str
    points: List[Dict[str, float]]  # Multiple click points
    label: Optional[str] = "object"


class FinalizeMoveRequest(BaseModel):
    """Request model for finalizing moved objects"""

    original_image: str  # Original visualization image
    mask: str  # Mask of original object location (for inpainting)
    cutout: str  # The extracted object PNG
    inpainted_background: Optional[str] = None  # Clean background with object removed (from Gemini)
    product_id: Optional[int] = None  # Product ID to fetch clean image from DB
    original_position: Dict[str, float]  # {"x": 0.2, "y": 0.3} where object was
    new_position: Dict[str, float]  # {"x": 0.5, "y": 0.4} where object is now
    scale: float = 1.0  # Scale factor applied to object


class ProductPosition(BaseModel):
    """Position data for a single product"""

    product_id: int
    x: float  # Normalized x position (0-1)
    y: float  # Normalized y position (0-1)
    scale: float = 1.0


class RevisualizeWithPositionsRequest(BaseModel):
    """Request model for full scene re-visualization with custom positions"""

    room_image: str  # Clean room image (without furniture)
    products: List[Dict[str, Any]]  # All products with their info
    positions: List[ProductPosition]  # Positions for all products
    curated_look_id: Optional[int] = None


class ProductInfo(BaseModel):
    """Product information for edit reference"""

    id: int
    name: str
    quantity: int = 1
    image_url: Optional[str] = None


class EditWithInstructionsRequest(BaseModel):
    """Request model for text-based image editing"""

    image: str  # Current visualization image (base64)
    instructions: str  # User's text instructions (e.g., "Place the flower vase on the bench")
    products: Optional[List[ProductInfo]] = None  # Products in the scene for reference


@router.post("/analyze-room")
async def analyze_room_image(image_data: str, session_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Analyze room image for spatial understanding and design assessment"""
    try:
        # Perform room analysis using Google AI Studio
        room_analysis = await google_ai_service.analyze_room_image(image_data)

        # Update room context in conversation if session provided
        if session_id:
            room_context = {
                "room_type": room_analysis.room_type,
                "dimensions": room_analysis.dimensions,
                "style_assessment": room_analysis.style_assessment,
                "existing_furniture": room_analysis.existing_furniture,
                "architectural_features": room_analysis.architectural_features,
                "analysis_timestamp": datetime.utcnow().isoformat(),
            }

            chatgpt_service.update_room_context(session_id, room_context)

        return {
            "room_analysis": {
                "room_type": room_analysis.room_type,
                "dimensions": room_analysis.dimensions,
                "lighting_conditions": room_analysis.lighting_conditions,
                "color_palette": room_analysis.color_palette,
                "existing_furniture": room_analysis.existing_furniture,
                "architectural_features": room_analysis.architectural_features,
                "style_assessment": room_analysis.style_assessment,
                "confidence_score": room_analysis.confidence_score,
            },
            "session_updated": session_id is not None,
            "analysis_id": str(uuid.uuid4()),
        }

    except Exception as e:
        logger.error(f"Error analyzing room: {e}")
        raise HTTPException(status_code=500, detail=f"Room analysis failed: {str(e)}")


@router.post("/spatial-analysis")
async def perform_spatial_analysis(room_analysis: Dict[str, Any], additional_context: Optional[str] = None):
    """Perform detailed spatial analysis for furniture placement"""
    try:
        # Convert dict back to RoomAnalysis object for processing
        from services.google_ai_service import RoomAnalysis

        room_analysis_obj = RoomAnalysis(
            room_type=room_analysis.get("room_type", "unknown"),
            dimensions=room_analysis.get("dimensions", {}),
            lighting_conditions=room_analysis.get("lighting_conditions", "mixed"),
            color_palette=room_analysis.get("color_palette", []),
            existing_furniture=room_analysis.get("existing_furniture", []),
            architectural_features=room_analysis.get("architectural_features", []),
            style_assessment=room_analysis.get("style_assessment", "unknown"),
            confidence_score=room_analysis.get("confidence_score", 0.5),
        )

        # Perform spatial analysis
        spatial_analysis = await google_ai_service.perform_spatial_analysis(room_analysis_obj)

        return {
            "spatial_analysis": {
                "layout_type": spatial_analysis.layout_type,
                "traffic_patterns": spatial_analysis.traffic_patterns,
                "focal_points": spatial_analysis.focal_points,
                "available_spaces": spatial_analysis.available_spaces,
                "placement_suggestions": spatial_analysis.placement_suggestions,
                "scale_recommendations": spatial_analysis.scale_recommendations,
            },
            "additional_insights": additional_context,
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error in spatial analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Spatial analysis failed: {str(e)}")


@router.post("/detect-objects")
async def detect_room_objects(image_data: str):
    """Detect and classify objects in room image"""
    try:
        objects = await google_ai_service.detect_objects_in_room(image_data)

        return {
            "detected_objects": objects,
            "object_count": len(objects),
            "detection_timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error detecting objects: {e}")
        raise HTTPException(status_code=500, detail=f"Object detection failed: {str(e)}")


@router.post("/generate-visualization")
async def generate_room_visualization(
    base_image: str,
    products: List[Dict[str, Any]],
    placement_preferences: Optional[Dict[str, Any]] = None,
    render_quality: str = "high",
    session_id: Optional[str] = None,
):
    """Generate photorealistic room visualization with placed products"""
    try:
        from services.google_ai_service import VisualizationRequest

        # Create visualization request
        viz_request = VisualizationRequest(
            base_image=base_image,
            products_to_place=products,
            placement_positions=placement_preferences.get("positions", []) if placement_preferences else [],
            lighting_conditions=placement_preferences.get("lighting", "natural") if placement_preferences else "natural",
            render_quality=render_quality,
            style_consistency=placement_preferences.get("style_consistency", True) if placement_preferences else True,
        )

        # Generate visualization
        result = await google_ai_service.generate_room_visualization(viz_request)

        # Save visualization to conversation context if session provided
        if session_id:
            visualization_data = {
                "rendered_image": result.rendered_image,
                "products_placed": products,
                "quality_metrics": {
                    "quality_score": result.quality_score,
                    "placement_accuracy": result.placement_accuracy,
                    "lighting_realism": result.lighting_realism,
                    "confidence_score": result.confidence_score,
                },
                "processing_time": result.processing_time,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Update conversation context
            context = chatgpt_service.get_enhanced_conversation_context(session_id)
            context["latest_visualization"] = visualization_data

        return {
            "visualization": {
                "rendered_image": result.rendered_image,
                "processing_time": result.processing_time,
                "quality_metrics": {
                    "overall_quality": result.quality_score,
                    "placement_accuracy": result.placement_accuracy,
                    "lighting_realism": result.lighting_realism,
                    "confidence_score": result.confidence_score,
                },
            },
            "products_placed": len(products),
            "render_settings": {
                "quality": render_quality,
                "lighting": viz_request.lighting_conditions,
                "style_consistency": viz_request.style_consistency,
            },
            "session_updated": session_id is not None,
        }

    except Exception as e:
        logger.error(f"Error generating visualization: {e}")
        raise HTTPException(status_code=500, detail=f"Visualization generation failed: {str(e)}")


@router.post("/upload-room-image")
async def upload_room_image(file: UploadFile = File(...)):
    """Upload room image for analysis"""
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Read and encode image
        contents = await file.read()
        encoded_image = base64.b64encode(contents).decode()

        return {
            "image_data": f"data:{file.content_type};base64,{encoded_image}",
            "filename": file.filename,
            "size": len(contents),
            "content_type": file.content_type,
            "upload_timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")


@router.post("/sessions/{session_id}/extract-layers")
async def extract_furniture_layers(session_id: str, request: ExtractLayersRequest, db: AsyncSession = Depends(get_db)):
    """
    Extract all objects as draggable layers for Magic Grab editing.

    This is the entry point for the Magic Grab workflow:
    1. SAM automatically detects and segments ALL objects in the image
    2. Each object is extracted as a transparent PNG cutout
    3. Gemini generates a clean background (furniture removed)
    4. Frontend receives layers for real-time drag-and-drop editing

    OPTIMIZED: First checks for pre-computed masks from background processing.
    Falls back to real-time computation if cache miss.

    Args:
        session_id: The session ID for this visualization
        request: Request body containing visualization_image and products

    Returns:
        background: Clean room image with furniture removed
        layers: List of extracted layers with transparent cutouts and positions
    """
    try:
        logger.info(f"[ExtractLayers] Starting Magic Grab extraction for session {session_id}")

        # CHECK CACHE FIRST - pre-computed masks from background processing
        try:
            from services.mask_precomputation_service import mask_precomputation_service

            # Convert products to cache key format
            products_for_cache = [
                {"id": p.get("id") or p.get("product_id"), "name": p.get("name", "")} for p in request.products
            ]

            cached_result = None

            # Try curated_look_id first if provided (for curated looks)
            if request.curated_look_id:
                logger.info(f"[ExtractLayers] Checking cache for curated_look_id={request.curated_look_id}")
                cached_result = await mask_precomputation_service.get_cached_masks_for_curated_look(
                    db,
                    request.curated_look_id,
                    request.visualization_image,
                    products_for_cache,
                )

            # Fallback to session-based lookup
            if not cached_result:
                cached_result = await mask_precomputation_service.get_cached_masks(
                    db,
                    session_id,
                    request.visualization_image,
                    products_for_cache,
                )

            if cached_result:
                logger.info(f"[ExtractLayers] CACHE HIT - returning pre-computed masks instantly!")

                # Normalize layer field names for frontend compatibility
                # Cached layers use: bbox, cutout, mask
                # Frontend expects: bounding_box, layer_image
                normalized_layers = []
                for layer in cached_result.get("layers", []):
                    normalized_layers.append(
                        {
                            "id": layer.get("id"),
                            "product_id": layer.get("product_id"),
                            "product_name": layer.get("product_name"),
                            "layer_image": layer.get("cutout") or layer.get("layer_image"),  # Use cutout as layer_image
                            "bounding_box": layer.get("bbox") or layer.get("bounding_box"),  # Use bbox as bounding_box
                            "center": layer.get("center", {"x": layer.get("x", 0.5), "y": layer.get("y", 0.5)}),
                            "mask": layer.get("mask"),
                            "cutout": layer.get("cutout"),
                            "bbox": layer.get("bbox"),
                            "x": layer.get("x", layer.get("center", {}).get("x", 0.5)),
                            "y": layer.get("y", layer.get("center", {}).get("y", 0.5)),
                            "width": layer.get("width", layer.get("bbox", {}).get("width", 0.1)),
                            "height": layer.get("height", layer.get("bbox", {}).get("height", 0.1)),
                            "scale": layer.get("scale", 1.0),
                            "stability_score": layer.get("stability_score", 0.9),
                            "area": layer.get("area", 0.05),
                        }
                    )

                return {
                    "session_id": session_id,
                    "background": cached_result["background"],
                    "layers": normalized_layers,
                    "total_layers": len(normalized_layers),
                    "extraction_method": cached_result["extraction_method"],
                    "image_dimensions": cached_result["image_dimensions"],
                    "extraction_time": cached_result["processing_time"],
                    "extraction_timestamp": datetime.utcnow().isoformat(),
                    "status": "success",
                    "cached": True,
                    "cache_job_id": cached_result.get("cache_job_id"),
                }

            logger.info(f"[ExtractLayers] CACHE MISS - computing in real-time")

        except Exception as cache_error:
            logger.warning(f"[ExtractLayers] Cache check failed, proceeding with real-time: {cache_error}")

        sam_succeeded = False

        if request.use_sam:
            # Try SAM for precise object segmentation (Magic Grab style)
            try:
                import asyncio
                import os

                from services.sam_service import sam_service

                # Ensure Replicate API key is set (critical for SAM)
                replicate_key = settings.replicate_api_key
                if not replicate_key:
                    replicate_key = os.environ.get("REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_KEY")
                if replicate_key:
                    os.environ["REPLICATE_API_TOKEN"] = replicate_key
                    sam_service.api_key = replicate_key
                    logger.info(f"[ExtractLayers] Replicate API key set: {replicate_key[:15]}...")
                else:
                    logger.warning("[ExtractLayers] No Replicate API key found!")

                logger.info("[ExtractLayers] Using hybrid approach: Gemini positions + SAM segmentation")

                # Step 1: Get product positions from Gemini (knows our actual products)
                logger.info("[ExtractLayers] Getting product positions from Gemini...")
                product_positions = await google_ai_service._detect_product_positions(
                    request.visualization_image, request.products
                )
                logger.info(f"[ExtractLayers] Gemini detected {len(product_positions)} product positions")

                if len(product_positions) > 0:
                    # Step 2: Run SAM automatic segmentation with furniture filtering
                    logger.info("[ExtractLayers] Running SAM automatic segmentation with furniture filter...")
                    segmentation = await sam_service.segment_all_objects(
                        image_base64=request.visualization_image,
                        min_area_percent=1.0,  # Minimum 1% of image (furniture is usually larger)
                        max_objects=30,  # Allow enough objects for large rooms
                        stability_threshold=0.7,  # Lower threshold to catch more
                        furniture_filter=True,  # Filter out walls, ceiling, floor
                    )
                    logger.info(f"[ExtractLayers] SAM detected {len(segmentation.objects)} objects")

                    # Step 3: Generate clean background in parallel
                    background_task = asyncio.create_task(google_ai_service.remove_furniture(request.visualization_image))

                    # Step 4: Create layers from SAM objects directly
                    # Instead of trying to match Gemini positions to SAM, we use SAM's
                    # detected objects directly. This gives us proper object-shaped cutouts.
                    layers = []

                    # Log all SAM objects for debugging
                    logger.info(f"[ExtractLayers] SAM detected {len(segmentation.objects)} objects:")
                    for i, obj in enumerate(segmentation.objects):
                        logger.info(
                            f"[ExtractLayers]   SAM obj {i}: center=({obj.center['x']:.3f}, {obj.center['y']:.3f}), "
                            f"bbox=({obj.bbox['x']:.3f}, {obj.bbox['y']:.3f}, {obj.bbox['width']:.3f}, {obj.bbox['height']:.3f}), "
                            f"area={obj.area:.4f}"
                        )

                    # Log all Gemini-detected product positions
                    logger.info(f"[ExtractLayers] Gemini detected {len(product_positions)} products:")
                    for pos in product_positions:
                        bbox = pos.get("bounding_box", pos.get("bbox", {}))
                        logger.info(
                            f"[ExtractLayers]   Product '{pos.get('product_name')}': "
                            f"bbox=({bbox.get('x', 0):.3f}, {bbox.get('y', 0):.3f}, {bbox.get('width', 0):.3f}, {bbox.get('height', 0):.3f})"
                        )

                    # Strategy: Use SAM objects directly, matching to products by proximity
                    # This gives us proper object-shaped cutouts instead of rectangles
                    used_sam_objects = set()

                    for pos in product_positions:
                        product_bbox = pos.get("bounding_box", pos.get("bbox", {}))
                        bbox_x = product_bbox.get("x", 0)
                        bbox_y = product_bbox.get("y", 0)
                        bbox_w = product_bbox.get("width", 0.2)
                        bbox_h = product_bbox.get("height", 0.2)

                        product_center_x = bbox_x + bbox_w / 2
                        product_center_y = bbox_y + bbox_h / 2

                        # Find best matching SAM object - use wider tolerance
                        best_match = None
                        best_distance = float("inf")

                        for i, obj in enumerate(segmentation.objects):
                            if i in used_sam_objects:
                                continue

                            sam_center_x = obj.center["x"]
                            sam_center_y = obj.center["y"]

                            # Calculate distance between product center and SAM center
                            distance = ((product_center_x - sam_center_x) ** 2 + (product_center_y - sam_center_y) ** 2) ** 0.5

                            # Also check for bbox overlap
                            sam_bbox = obj.bbox
                            overlap_x = max(
                                0, min(bbox_x + bbox_w, sam_bbox["x"] + sam_bbox["width"]) - max(bbox_x, sam_bbox["x"])
                            )
                            overlap_y = max(
                                0, min(bbox_y + bbox_h, sam_bbox["y"] + sam_bbox["height"]) - max(bbox_y, sam_bbox["y"])
                            )
                            overlap_area = overlap_x * overlap_y

                            # Prefer objects that overlap with product bbox or are close
                            if overlap_area > 0 or distance < 0.3:  # Within 30% of image diagonal
                                if distance < best_distance:
                                    best_distance = distance
                                    best_match = (i, obj)

                        if best_match:
                            i, obj = best_match
                            used_sam_objects.add(i)
                            logger.info(
                                f"[ExtractLayers] Matched '{pos.get('product_name')}' to SAM obj {i} (distance={best_distance:.3f})"
                            )

                            # Use SAM's cutout (object-shaped) positioned at SAM's center
                            # Frontend expects x,y to be CENTER position (uses offsetX/offsetY)
                            sam_center_x = obj.bbox["x"] + obj.bbox["width"] / 2
                            sam_center_y = obj.bbox["y"] + obj.bbox["height"] / 2

                            layers.append(
                                {
                                    "id": f"product_{len(layers)}",
                                    "product_id": pos.get("product_id"),
                                    "product_name": pos.get("product_name", f"Product {len(layers)}"),
                                    "cutout": obj.cutout,
                                    "mask": obj.mask,
                                    "bbox": obj.bbox,
                                    "center": obj.center,
                                    "x": sam_center_x,  # CENTER position for frontend
                                    "y": sam_center_y,
                                    "width": obj.bbox["width"],
                                    "height": obj.bbox["height"],
                                    "scale": 1.0,
                                    "stability_score": obj.stability_score,
                                    "area": obj.area,
                                }
                            )
                            logger.info(
                                f"[ExtractLayers]   Layer: x={sam_center_x:.3f}, y={sam_center_y:.3f}, w={obj.bbox['width']:.3f}, h={obj.bbox['height']:.3f}"
                            )
                        else:
                            logger.warning(f"[ExtractLayers] No SAM match for '{pos.get('product_name')}', using Gemini bbox")
                            cutout = await _create_cutout_from_bbox(request.visualization_image, product_bbox)
                            # Frontend expects x,y to be CENTER position
                            layers.append(
                                {
                                    "id": f"product_{len(layers)}",
                                    "product_id": pos.get("product_id"),
                                    "product_name": pos.get("product_name", f"Product {len(layers)}"),
                                    "cutout": cutout,
                                    "mask": None,
                                    "bbox": product_bbox,
                                    "center": {"x": product_center_x, "y": product_center_y},
                                    "x": product_center_x,  # CENTER position
                                    "y": product_center_y,
                                    "width": bbox_w,
                                    "height": bbox_h,
                                    "scale": 1.0,
                                    "stability_score": 0.8,
                                    "area": bbox_w * bbox_h,
                                }
                            )
                            logger.info(
                                f"[ExtractLayers]   Fallback layer: x={product_center_x:.3f}, y={product_center_y:.3f}, w={bbox_w:.3f}, h={bbox_h:.3f}"
                            )

                    logger.info(f"[ExtractLayers] Created {len(layers)} product layers from matching")
                    logger.info(f"[ExtractLayers] SAM objects matched: {len(used_sam_objects)} of {len(segmentation.objects)}")

                    # If no products matched to SAM objects, use SAM objects directly
                    # This gives us object-shaped cutouts even without perfect matching
                    sam_match_count = len(used_sam_objects)
                    if sam_match_count == 0 and len(segmentation.objects) > 0:
                        logger.info(f"[ExtractLayers] No SAM matches found! Using SAM objects directly as layers")
                        layers = []
                        for i, obj in enumerate(segmentation.objects):
                            # Skip very small objects (likely noise)
                            if obj.area < 0.01:  # Less than 1% of image
                                continue
                            sam_center_x = obj.bbox["x"] + obj.bbox["width"] / 2
                            sam_center_y = obj.bbox["y"] + obj.bbox["height"] / 2
                            layers.append(
                                {
                                    "id": f"sam_obj_{i}",
                                    "product_id": None,
                                    "product_name": f"Object {i+1}",
                                    "cutout": obj.cutout,
                                    "mask": obj.mask,
                                    "bbox": obj.bbox,
                                    "center": obj.center,
                                    "x": sam_center_x,
                                    "y": sam_center_y,
                                    "width": obj.bbox["width"],
                                    "height": obj.bbox["height"],
                                    "scale": 1.0,
                                    "stability_score": obj.stability_score,
                                    "area": obj.area,
                                }
                            )
                            logger.info(
                                f"[ExtractLayers]   SAM Layer {i}: center=({sam_center_x:.3f}, {sam_center_y:.3f}), "
                                f"size=({obj.bbox['width']:.3f}, {obj.bbox['height']:.3f}), area={obj.area:.4f}"
                            )
                        logger.info(f"[ExtractLayers] Created {len(layers)} layers from SAM objects directly")

                    sam_succeeded = True
                    clean_background = await background_task

                    return {
                        "session_id": session_id,
                        "background": clean_background,
                        "layers": layers,
                        "total_layers": len(layers),
                        "extraction_method": "hybrid_gemini_sam" if sam_match_count > 0 else "sam_direct",
                        "sam_objects_detected": len(segmentation.objects),
                        "sam_matches_found": sam_match_count,
                        "image_dimensions": segmentation.image_dimensions,
                        "extraction_time": segmentation.processing_time,
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "status": "success",
                    }
                else:
                    logger.warning("[ExtractLayers] Gemini detected 0 products, using fallback")

            except Exception as sam_error:
                logger.warning(f"[ExtractLayers] SAM failed, falling back to Gemini: {str(sam_error)}")

        # Fallback to Gemini (if SAM failed or returned no objects)
        if not sam_succeeded:
            # Fallback: Use Gemini for bounding box detection (less precise)
            logger.info("[ExtractLayers] Using Gemini for layer extraction (fallback)")

            result = await google_ai_service.extract_furniture_layers(
                visualization_image=request.visualization_image, products=request.products
            )

            # Transform to new format
            layers = []
            for layer in result.get("layers", []):
                layers.append(
                    {
                        "id": layer.get("product_id"),
                        "product_id": layer.get("product_id"),
                        "product_name": layer.get("product_name"),
                        "cutout": layer.get("layer_image"),  # Cropped rectangle
                        "mask": None,
                        "bbox": layer.get("bounding_box"),
                        "center": layer.get("center"),
                        "x": layer.get("center", {}).get("x", 0.5),
                        "y": layer.get("center", {}).get("y", 0.5),
                        "width": layer.get("bounding_box", {}).get("width", 0.1),
                        "height": layer.get("bounding_box", {}).get("height", 0.1),
                        "scale": 1.0,
                        "stability_score": 0.9,
                        "area": 0.05,
                    }
                )

            return {
                "session_id": session_id,
                "background": result.get("clean_background"),
                "layers": layers,
                "total_layers": len(layers),
                "extraction_method": "gemini",
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "status": "success",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExtractLayers] Error extracting layers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Layer extraction failed: {str(e)}")


def _match_object_to_product(center: Dict[str, float], products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Try to match a detected object to a product based on position.

    This is a simple heuristic - objects near each other are likely matches.
    """
    # For now, just return None - let frontend handle matching
    # Could be enhanced with Gemini Vision to identify products
    return None


async def _create_cutout_from_bbox(image_base64: str, bbox: Dict[str, float]) -> str:
    """
    Create a rectangular cutout from the image using a bounding box.

    Used as fallback when SAM doesn't find a matching object.
    """
    import io

    from PIL import Image

    # Decode image
    image_data = image_base64
    if image_data.startswith("data:image"):
        image_data = image_data.split(",")[1]

    image_bytes = base64.b64decode(image_data)
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    width, height = pil_image.size

    # Convert normalized bbox to pixels
    x = int(bbox.get("x", 0) * width)
    y = int(bbox.get("y", 0) * height)
    w = int(bbox.get("width", 0.2) * width)
    h = int(bbox.get("height", 0.2) * height)

    # Ensure bounds are valid
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = min(w, width - x)
    h = min(h, height - y)

    # Crop the region
    cropped = pil_image.crop((x, y, x + w, y + h))

    # Convert to base64
    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    buffer.seek(0)
    cutout_b64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"

    return cutout_b64


@router.post("/sessions/{session_id}/composite-layers")
async def composite_layers(session_id: str, request: CompositeLayersRequest):
    """
    Composite all layers at their new positions to create final image.

    This is called when user clicks "Done" after editing positions:
    1. PIL composites all layer cutouts onto the background
    2. (Optional) Gemini harmonizes lighting for seamless blending
    3. Returns the final edited visualization

    Args:
        session_id: The session ID
        request: Background image and layers with new positions

    Returns:
        Final composited image
    """
    try:
        logger.info(f"[CompositeLayers] Starting compositing for session {session_id}")
        logger.info(f"[CompositeLayers] Compositing {len(request.layers)} layers")

        from services.image_compositing_service import Layer, compositing_service

        # Convert request layers to Layer objects
        layers = []
        for layer_data in request.layers:
            layer = Layer(
                id=str(layer_data.get("id", "")),
                cutout=layer_data.get("cutout", ""),
                x=float(layer_data.get("x", 0.5)),
                y=float(layer_data.get("y", 0.5)),
                scale=float(layer_data.get("scale", 1.0)),
                rotation=float(layer_data.get("rotation", 0.0)),
                opacity=float(layer_data.get("opacity", 1.0)),
                z_index=int(layer_data.get("z_index", 0)),
            )
            layers.append(layer)

        # Composite layers
        if request.harmonize:
            # Use harmonization (optional Gemini pass)
            result = await compositing_service.composite_with_harmonization(
                background=request.background, layers=layers, harmonize_service=google_ai_service
            )
        else:
            # Standard PIL compositing (fast, free)
            result = await compositing_service.composite_layers(
                background=request.background, layers=layers, apply_shadows=True, feather_edges=True
            )

        logger.info(f"[CompositeLayers] Complete in {result.processing_time:.2f}s")

        return {
            "session_id": session_id,
            "image": result.image,
            "layers_composited": result.layers_composited,
            "dimensions": result.dimensions,
            "processing_time": result.processing_time,
            "harmonized": request.harmonize,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
        }

    except Exception as e:
        logger.error(f"[CompositeLayers] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Layer compositing failed: {str(e)}")


@router.get("/session/{session_id}/room-context")
async def get_session_room_context(session_id: str):
    """Get room context for a conversation session"""
    try:
        context = chatgpt_service.get_enhanced_conversation_context(session_id)

        return {
            "session_id": session_id,
            "room_context": context.get("room_context"),
            "has_room_analysis": "room_context" in context,
            "conversation_state": context.get("conversation_state", "unknown"),
            "context_timestamp": context.get("last_updated"),
        }

    except Exception as e:
        logger.error(f"Error getting room context: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get room context: {str(e)}")


@router.get("/health")
async def visualization_health_check():
    """Health check for visualization services"""
    try:
        # Check Google AI Studio service
        google_ai_health = await google_ai_service.health_check()

        return {
            "status": "healthy" if google_ai_health["status"] == "healthy" else "unhealthy",
            "services": {"google_ai_studio": google_ai_health},
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@router.get("/usage-stats")
async def get_visualization_usage_stats():
    """Get usage statistics for visualization services"""
    try:
        google_stats = await google_ai_service.get_usage_statistics()

        return {"google_ai_studio": google_stats, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage statistics")


@router.post("/sessions/{session_id}/analyze-preferences")
async def analyze_room_preferences(session_id: str, room_description: str, db: AsyncSession = Depends(get_db)):
    """Analyze room preferences from natural language description"""
    try:
        # Use ChatGPT to extract room requirements
        room_requirements = await chatgpt_service.extract_room_requirements(room_description, image_data=None)

        # Get enhanced analysis using NLP
        design_preferences = await chatgpt_service.analyze_design_preferences(room_description)

        return {
            "session_id": session_id,
            "room_requirements": room_requirements,
            "design_preferences": design_preferences,
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error analyzing room preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Preference analysis failed: {str(e)}")


@router.post("/compare-visualizations")
async def compare_visualizations(
    visualization_1: Dict[str, Any], visualization_2: Dict[str, Any], comparison_criteria: Optional[List[str]] = None
):
    """Compare two room visualizations"""
    try:
        criteria = comparison_criteria or ["quality", "realism", "style_consistency", "placement"]

        comparison_result = {
            "visualization_1_scores": {
                "quality": visualization_1.get("quality_metrics", {}).get("overall_quality", 0),
                "realism": visualization_1.get("quality_metrics", {}).get("lighting_realism", 0),
                "placement": visualization_1.get("quality_metrics", {}).get("placement_accuracy", 0),
            },
            "visualization_2_scores": {
                "quality": visualization_2.get("quality_metrics", {}).get("overall_quality", 0),
                "realism": visualization_2.get("quality_metrics", {}).get("lighting_realism", 0),
                "placement": visualization_2.get("quality_metrics", {}).get("placement_accuracy", 0),
            },
            "comparison_summary": {
                "winner": "visualization_1",  # Would be calculated based on scores
                "key_differences": ["Better lighting in visualization 1", "More accurate placement in visualization 2"],
                "recommendations": ["Consider hybrid approach", "Focus on lighting improvements"],
            },
            "comparison_criteria": criteria,
            "comparison_timestamp": datetime.utcnow().isoformat(),
        }

        return comparison_result

    except Exception as e:
        logger.error(f"Error comparing visualizations: {e}")
        raise HTTPException(status_code=500, detail=f"Visualization comparison failed: {str(e)}")


@router.post("/recommend-for-visualization")
async def recommend_products_for_visualization(
    room_analysis: Dict[str, Any],
    spatial_analysis: Dict[str, Any],
    style_preferences: Optional[List[str]] = None,
    budget_range: Optional[Tuple[float, float]] = None,
    max_products: int = 10,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Recommend products specifically optimized for room visualization"""
    try:
        # Extract room context from analyses
        room_context = {
            "room_type": room_analysis.get("room_type", "living_room"),
            "dimensions": room_analysis.get("dimensions", {}),
            "style_assessment": room_analysis.get("style_assessment", "modern"),
            "existing_furniture": room_analysis.get("existing_furniture", []),
            "layout_type": spatial_analysis.get("layout_type", "open"),
            "available_spaces": spatial_analysis.get("available_spaces", []),
        }

        # Extract functional requirements from spatial analysis
        functional_requirements = []
        placement_suggestions = spatial_analysis.get("placement_suggestions", [])
        for suggestion in placement_suggestions:
            furniture_type = suggestion.get("furniture_type")
            if furniture_type:
                functional_requirements.append(furniture_type)

        # Create user preferences for recommendation
        user_preferences = {
            "colors": room_analysis.get("color_palette", []),
            "style": room_analysis.get("style_assessment", "modern"),
            "materials": [],  # Could be extracted from existing furniture
            "room_compatibility": True,
        }

        # Build recommendation request
        recommendation_request = RecommendationRequest(
            user_preferences=user_preferences,
            room_context=room_context,
            budget_range=budget_range,
            style_preferences=style_preferences or [room_analysis.get("style_assessment", "modern")],
            functional_requirements=functional_requirements,
            max_recommendations=max_products,
        )

        # Get ML-enhanced recommendations
        recommendation_response = await recommendation_engine.get_recommendations(recommendation_request, db, user_id)

        # Enhance recommendations with visualization-specific data
        enhanced_recommendations = []
        for rec in recommendation_response.recommendations:
            # Get product details
            product_query = select(Product).where(Product.id == rec.product_id)
            product_result = await db.execute(product_query)
            product = product_result.scalar_one_or_none()

            if product:
                # Get optimal placement position for this product type
                optimal_placement = _get_optimal_placement(product, spatial_analysis, room_analysis)

                enhanced_rec = {
                    "product": {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "brand": product.brand,
                        "category": product.category,
                        "description": product.description,
                    },
                    "recommendation_scores": {
                        "overall_score": rec.overall_score,
                        "style_match": rec.style_match_score,
                        "functional_match": rec.functional_match_score,
                        "price_score": rec.price_score,
                        "confidence": rec.confidence_score,
                    },
                    "visualization_data": {
                        "optimal_placement": optimal_placement,
                        "scale_recommendation": _get_scale_recommendation(product, room_analysis),
                        "lighting_requirements": _get_lighting_requirements(product),
                        "compatibility_with_existing": _check_compatibility_with_existing(
                            product, room_analysis.get("existing_furniture", [])
                        ),
                    },
                    "reasoning": rec.reasoning,
                }
                enhanced_recommendations.append(enhanced_rec)

        return {
            "recommendations": enhanced_recommendations,
            "recommendation_metadata": {
                "total_found": recommendation_response.total_found,
                "processing_time": recommendation_response.processing_time,
                "personalization_level": recommendation_response.personalization_level,
                "diversity_score": recommendation_response.diversity_score,
                "strategy_used": recommendation_response.recommendation_strategy,
            },
            "visualization_context": {
                "room_type": room_context["room_type"],
                "style_theme": room_analysis.get("style_assessment"),
                "available_spaces": len(spatial_analysis.get("available_spaces", [])),
                "placement_opportunities": len(placement_suggestions),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error recommending products for visualization: {e}")
        raise HTTPException(status_code=500, detail=f"Visualization recommendation failed: {str(e)}")


@router.post("/generate-visualization-with-ml")
async def generate_visualization_with_ml_recommendations(
    base_image: str,
    room_analysis: Dict[str, Any],
    spatial_analysis: Dict[str, Any],
    user_preferences: Optional[Dict[str, Any]] = None,
    auto_select_products: bool = True,
    max_products: int = 5,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate visualization using ML-recommended products automatically"""
    try:
        # Get ML recommendations for the space
        if auto_select_products:
            # Use ML to select optimal products
            room_context = {
                "room_type": room_analysis.get("room_type", "living_room"),
                "dimensions": room_analysis.get("dimensions", {}),
                "style_assessment": room_analysis.get("style_assessment", "modern"),
            }

            # Create recommendation request
            recommendation_request = RecommendationRequest(
                user_preferences=user_preferences or {},
                room_context=room_context,
                style_preferences=[room_analysis.get("style_assessment", "modern")],
                max_recommendations=max_products,
            )

            # Get recommendations
            recommendation_response = await recommendation_engine.get_recommendations(recommendation_request, db, user_id)

            # Convert recommendations to product data for visualization
            products_for_visualization = []
            for rec in recommendation_response.recommendations:
                # Get product details
                product_query = select(Product).where(Product.id == rec.product_id)
                product_result = await db.execute(product_query)
                product = product_result.scalar_one_or_none()

                if product:
                    # Get optimal placement
                    placement = _get_optimal_placement(product, spatial_analysis, room_analysis)

                    product_viz_data = {
                        "id": product.id,
                        "name": product.name,
                        "category": product.category,
                        "style": _extract_product_style(product),
                        "placement": placement,
                        "confidence": rec.confidence_score,
                    }
                    products_for_visualization.append(product_viz_data)

        else:
            products_for_visualization = []

        # Calculate placement positions using spatial analysis
        placement_positions = []
        for i, product_data in enumerate(products_for_visualization):
            placement_positions.append(
                {
                    "product_id": product_data["id"],
                    "position": product_data["placement"]["position"],
                    "orientation": product_data["placement"]["orientation"],
                    "scale": product_data["placement"]["scale"],
                }
            )

        # Generate visualization
        from services.google_ai_service import VisualizationRequest

        viz_request = VisualizationRequest(
            base_image=base_image,
            products_to_place=products_for_visualization,
            placement_positions=placement_positions,
            lighting_conditions=room_analysis.get("lighting_conditions", "natural"),
            render_quality="high",
            style_consistency=True,
        )

        # Generate the visualization
        visualization_result = await google_ai_service.generate_room_visualization(viz_request)

        return {
            "visualization": {
                "rendered_image": visualization_result.rendered_image,
                "quality_metrics": {
                    "overall_quality": visualization_result.quality_score,
                    "placement_accuracy": visualization_result.placement_accuracy,
                    "lighting_realism": visualization_result.lighting_realism,
                    "confidence_score": visualization_result.confidence_score,
                },
                "processing_time": visualization_result.processing_time,
            },
            "products_used": products_for_visualization,
            "ml_recommendations": {
                "strategy_used": recommendation_response.recommendation_strategy if auto_select_products else "manual",
                "personalization_level": recommendation_response.personalization_level if auto_select_products else 0.0,
                "total_candidates": recommendation_response.total_found if auto_select_products else 0,
            },
            "spatial_optimization": {
                "placement_method": "ai_optimized",
                "layout_efficiency": _calculate_layout_efficiency(placement_positions, spatial_analysis),
                "traffic_flow_maintained": _check_traffic_flow(placement_positions, spatial_analysis),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating ML-powered visualization: {e}")
        raise HTTPException(status_code=500, detail=f"ML visualization generation failed: {str(e)}")


# Helper functions for visualization-specific recommendations


def _get_optimal_placement(product: Product, spatial_analysis: Dict, room_analysis: Dict) -> Dict[str, Any]:
    """Calculate optimal placement for a product based on spatial analysis"""
    try:
        # Extract available spaces
        available_spaces = spatial_analysis.get("available_spaces", [])
        placement_suggestions = spatial_analysis.get("placement_suggestions", [])

        # Find best placement based on product type and available spaces
        product_function = _extract_product_function(product)

        optimal_placement = {
            "position": "center",
            "orientation": "facing_main_focal_point",
            "scale": "appropriate",
            "reasoning": "Default placement",
        }

        # Look for specific placement suggestions for this product type
        for suggestion in placement_suggestions:
            if suggestion.get("furniture_type") == product_function:
                optimal_placement = {
                    "position": suggestion.get("recommended_position", "center"),
                    "orientation": suggestion.get("orientation", "facing_main_focal_point"),
                    "scale": suggestion.get("distance_from_wall", "18_inches"),
                    "reasoning": suggestion.get("reasoning", "Optimized for room layout"),
                }
                break

        return optimal_placement

    except Exception as e:
        logger.error(f"Error calculating optimal placement: {e}")
        return {"position": "center", "orientation": "default", "scale": "medium", "reasoning": "Default"}


def _get_scale_recommendation(product: Product, room_analysis: Dict) -> Dict[str, Any]:
    """Get scale recommendations based on room dimensions"""
    try:
        dimensions = room_analysis.get("dimensions", {})
        room_area = dimensions.get("square_footage", 200)

        # Basic scale recommendations based on room size
        if room_area < 100:
            scale_factor = "small"
            size_recommendation = "Choose compact versions"
        elif room_area < 300:
            scale_factor = "medium"
            size_recommendation = "Standard sizing appropriate"
        else:
            scale_factor = "large"
            size_recommendation = "Can accommodate larger pieces"

        return {"scale_factor": scale_factor, "size_recommendation": size_recommendation, "room_area": room_area}

    except Exception:
        return {"scale_factor": "medium", "size_recommendation": "Standard sizing", "room_area": 200}


def _get_lighting_requirements(product: Product) -> List[str]:
    """Get lighting requirements for optimal product visualization"""
    product_function = _extract_product_function(product)

    lighting_map = {
        "seating": ["ambient_lighting", "task_lighting"],
        "dining": ["overhead_lighting", "ambient_lighting"],
        "workspace": ["task_lighting", "ambient_lighting"],
        "storage": ["accent_lighting"],
        "decoration": ["accent_lighting", "highlighting"],
    }

    return lighting_map.get(product_function, ["ambient_lighting"])


def _check_compatibility_with_existing(product: Product, existing_furniture: List[Dict]) -> Dict[str, Any]:
    """Check compatibility with existing furniture"""
    try:
        compatibility_score = 0.8  # Default
        compatibility_notes = []

        product_style = _extract_product_style(product)

        # Check style compatibility with existing pieces
        existing_styles = []
        for item in existing_furniture:
            item_style = item.get("style", "unknown")
            existing_styles.append(item_style)

        if existing_styles:
            # Simple compatibility check
            if product_style in existing_styles:
                compatibility_score = 0.9
                compatibility_notes.append("Matches existing furniture style")
            else:
                compatibility_score = 0.6
                compatibility_notes.append("Complementary style that adds visual interest")

        return {
            "compatibility_score": compatibility_score,
            "notes": compatibility_notes,
            "existing_styles": existing_styles,
            "product_style": product_style,
        }

    except Exception:
        return {
            "compatibility_score": 0.7,
            "notes": ["Standard compatibility"],
            "existing_styles": [],
            "product_style": "modern",
        }


def _extract_product_style(product: Product) -> str:
    """Extract style from product (same as in recommendation engine)"""
    style_keywords = {
        "modern": ["modern", "contemporary", "sleek", "minimalist"],
        "traditional": ["traditional", "classic", "ornate", "elegant"],
        "rustic": ["rustic", "farmhouse", "reclaimed", "weathered"],
        "scandinavian": ["scandinavian", "nordic", "hygge", "light"],
    }

    product_text = (product.name + " " + (product.description or "")).lower()

    for style, keywords in style_keywords.items():
        if any(keyword in product_text for keyword in keywords):
            return style

    return "contemporary"


def _extract_product_function(product: Product) -> str:
    """Extract primary function from product (same as in recommendation engine)"""
    function_map = {
        "sofa": "seating",
        "chair": "seating",
        "armchair": "seating",
        "table": "dining",
        "desk": "workspace",
        "bed": "sleeping",
        "dresser": "storage",
        "bookshelf": "storage",
        "cabinet": "storage",
        "lamp": "lighting",
        "chandelier": "lighting",
    }

    product_name = product.name.lower()
    for keyword, function in function_map.items():
        if keyword in product_name:
            return function

    return "decoration"


def _calculate_layout_efficiency(placement_positions: List[Dict], spatial_analysis: Dict) -> float:
    """Calculate how efficiently the layout uses available space"""
    try:
        # Simple efficiency calculation based on space utilization
        available_spaces = spatial_analysis.get("available_spaces", [])
        used_spaces = len(placement_positions)
        total_spaces = len(available_spaces)

        if total_spaces == 0:
            return 0.5  # Default

        utilization_ratio = used_spaces / total_spaces
        # Optimal utilization is around 60-80%
        if 0.6 <= utilization_ratio <= 0.8:
            efficiency = 0.9
        elif 0.4 <= utilization_ratio < 0.6:
            efficiency = 0.7
        elif 0.8 < utilization_ratio <= 1.0:
            efficiency = 0.8
        else:
            efficiency = 0.5

        return efficiency

    except Exception:
        return 0.7  # Default efficiency score


def _check_traffic_flow(placement_positions: List[Dict], spatial_analysis: Dict) -> bool:
    """Check if furniture placement maintains good traffic flow"""
    try:
        # Simple check based on traffic patterns and placement
        traffic_patterns = spatial_analysis.get("traffic_patterns", [])

        # If no traffic patterns defined, assume flow is maintained
        if not traffic_patterns:
            return True

        # For now, assume good traffic flow if not too many items placed
        return len(placement_positions) <= 5

    except Exception:
        return True


# Furniture Position Management Endpoints


@router.post("/sessions/{session_id}/furniture-positions")
async def save_furniture_positions(session_id: str, positions: List[Dict[str, Any]], db: AsyncSession = Depends(get_db)):
    """Save furniture positions for a visualization session"""
    try:
        from sqlalchemy import delete

        from database.models import FurniturePosition

        # Delete existing positions for this session
        delete_stmt = delete(FurniturePosition).where(FurniturePosition.session_id == session_id)
        await db.execute(delete_stmt)

        # Insert new positions
        saved_positions = []
        for pos in positions:
            # Handle product IDs with quantity suffix (e.g., "552-1" -> 552)
            product_id_str = str(pos.get("productId", "0"))
            base_product_id = product_id_str.split("-")[0]  # Extract base ID
            try:
                product_id = int(base_product_id)
            except ValueError:
                logger.warning(f"Invalid product ID: {product_id_str}, skipping")
                continue

            furniture_position = FurniturePosition(
                session_id=session_id,
                product_id=product_id,
                x=float(pos.get("x")),
                y=float(pos.get("y")),
                width=float(pos.get("width")) if pos.get("width") else None,
                height=float(pos.get("height")) if pos.get("height") else None,
                label=pos.get("label"),
                is_ai_placed=pos.get("isAiPlaced", False),
            )
            db.add(furniture_position)
            saved_positions.append(furniture_position)

        await db.commit()

        return {
            "session_id": session_id,
            "positions_saved": len(saved_positions),
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error saving furniture positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save positions: {str(e)}")


@router.get("/sessions/{session_id}/furniture-positions")
async def get_furniture_positions(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get saved furniture positions for a visualization session"""
    try:
        from sqlalchemy import select

        from database.models import FurniturePosition

        # Query positions for this session
        query = select(FurniturePosition).where(FurniturePosition.session_id == session_id)
        result = await db.execute(query)
        positions = result.scalars().all()

        # Format positions for frontend
        formatted_positions = []
        for pos in positions:
            formatted_positions.append(
                {
                    "productId": str(pos.product_id),
                    "x": pos.x,
                    "y": pos.y,
                    "width": pos.width,
                    "height": pos.height,
                    "label": pos.label,
                    "isAiPlaced": pos.is_ai_placed,
                    "createdAt": pos.created_at.isoformat(),
                    "updatedAt": pos.updated_at.isoformat(),
                }
            )

        return {
            "session_id": session_id,
            "positions": formatted_positions,
            "total_count": len(formatted_positions),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving furniture positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve positions: {str(e)}")


@router.put("/sessions/{session_id}/furniture-positions/{product_id}")
async def update_furniture_position(
    session_id: str, product_id: int, position_update: Dict[str, Any], db: AsyncSession = Depends(get_db)
):
    """Update a specific furniture position"""
    try:
        from sqlalchemy import select, update

        from database.models import FurniturePosition

        # Update position
        update_stmt = (
            update(FurniturePosition)
            .where(FurniturePosition.session_id == session_id)
            .where(FurniturePosition.product_id == product_id)
            .values(
                x=float(position_update.get("x")),
                y=float(position_update.get("y")),
                width=float(position_update.get("width")) if position_update.get("width") else None,
                height=float(position_update.get("height")) if position_update.get("height") else None,
                is_ai_placed=False,  # Mark as user-adjusted
                updated_at=datetime.utcnow(),
            )
        )
        await db.execute(update_stmt)
        await db.commit()

        return {
            "session_id": session_id,
            "product_id": product_id,
            "status": "updated",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating furniture position: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update position: {str(e)}")


@router.delete("/sessions/{session_id}/furniture-positions")
async def delete_all_furniture_positions(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete all furniture positions for a session"""
    try:
        from sqlalchemy import delete

        from database.models import FurniturePosition

        delete_stmt = delete(FurniturePosition).where(FurniturePosition.session_id == session_id)
        result = await db.execute(delete_stmt)
        await db.commit()

        # Also invalidate pre-computed masks for this session
        masks_invalidated = 0
        try:
            from services.mask_precomputation_service import mask_precomputation_service

            masks_invalidated = await mask_precomputation_service.invalidate_session_masks(db, session_id)
        except Exception as invalidate_error:
            logger.warning(f"[ExtractLayers] Failed to invalidate masks: {invalidate_error}")

        return {
            "session_id": session_id,
            "positions_deleted": result.rowcount,
            "masks_invalidated": masks_invalidated,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting furniture positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete positions: {str(e)}")


# ============================================================================
# CLICK-TO-SELECT EDIT POSITIONS ENDPOINTS
# ============================================================================


@router.post("/sessions/{session_id}/segment-at-point")
async def segment_at_point(session_id: str, request: SegmentAtPointRequest):
    """
    Segment object at a clicked point using Gemini + SAM.

    This is the core endpoint for "click-to-select" functionality.

    Flow:
    1. Use Gemini to identify what object is at the click point
    2. Get a bounding box estimate for just that object
    3. Use SAM with the bounding box for precise segmentation

    This prevents selecting entire tables when user clicks on a small decor item.

    Args:
        session_id: The chat/visualization session ID
        request: Contains image, click point, and optional label

    Returns:
        Layer object with cutout, mask, bbox, center for dragging
    """
    import asyncio
    import base64
    import io
    import json
    import re

    import httpx
    import numpy as np
    from google import genai
    from google.genai import types
    from PIL import Image

    from core.config import settings

    try:
        logger.info(f"[{session_id}] Segmenting at point {request.point}")
        logger.info(f"[{session_id}] Products received for matching: {len(request.products) if request.products else 0}")
        if request.products:
            logger.info(f"[{session_id}] Product IDs: {[p.id for p in request.products]}")

        # Decode image
        image_data = request.image_base64
        if image_data.startswith("data:"):
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        width, height = pil_image.size

        # Convert click point to pixel coordinates
        click_x = int(request.point["x"] * width)
        click_y = int(request.point["y"] * height)
        click_norm_x = request.point["x"]
        click_norm_y = request.point["y"]

        # ============================================================
        # CHECK PRE-COMPUTED LAYERS FIRST (instant response if found)
        # ============================================================
        try:
            from services.mask_precomputation_service import mask_precomputation_service

            from core.database import AsyncSessionLocal

            async with AsyncSessionLocal() as cache_db:
                # Use simpler image-based lookup (doesn't require exact product hash match)
                cached_result = await mask_precomputation_service.get_cached_layers_by_image(
                    cache_db,
                    request.image_base64,
                    session_id=session_id,
                    curated_look_id=request.curated_look_id,
                )

                if cached_result and cached_result.get("layers"):
                    # Find the SMALLEST layer bbox that contains the click point
                    # (Smaller bbox = more precise match for the clicked object)
                    best_match = None
                    best_match_area = float("inf")
                    margin = 0.02  # 2% margin for easier selection

                    for layer in cached_result["layers"]:
                        layer_bbox = layer.get("bbox", {})
                        layer_x = layer_bbox.get("x", 0)
                        layer_y = layer_bbox.get("y", 0)
                        layer_w = layer_bbox.get("width", 0)
                        layer_h = layer_bbox.get("height", 0)

                        # Check if click is inside this layer's bbox
                        if (
                            layer_x - margin <= click_norm_x <= layer_x + layer_w + margin
                            and layer_y - margin <= click_norm_y <= layer_y + layer_h + margin
                        ):
                            # Calculate bbox area - prefer smaller bboxes (more precise)
                            bbox_area = layer_w * layer_h
                            if bbox_area < best_match_area:
                                best_match = layer
                                best_match_area = bbox_area
                                logger.debug(
                                    f"[{session_id}] Found candidate layer: {layer.get('product_name')} (area={bbox_area:.4f})"
                                )

                    if best_match:
                        layer = best_match
                        layer_bbox = layer.get("bbox", {})
                        layer_x = layer_bbox.get("x", 0)
                        layer_y = layer_bbox.get("y", 0)
                        layer_w = layer_bbox.get("width", 0)
                        layer_h = layer_bbox.get("height", 0)

                        logger.info(
                            f"[{session_id}] CACHE HIT - Using pre-computed layer for product {layer.get('product_id')} ({layer.get('product_name')}) [smallest bbox area={best_match_area:.4f}]"
                        )

                        # Do real-time inpainting for just this product's area
                        # (Don't use pre-computed background which has ALL furniture removed)
                        try:
                            from services.google_ai_service import google_ai_service

                            # Get the product's bbox in pixel coordinates for targeted inpainting
                            img_dims = cached_result.get("image_dimensions", {})
                            img_w = img_dims.get("width", 1024)
                            img_h = img_dims.get("height", 1024)

                            product_bbox_px = {
                                "x": int(layer_x * img_w),
                                "y": int(layer_y * img_h),
                                "width": int(layer_w * img_w),
                                "height": int(layer_h * img_h),
                            }

                            # Inpaint just this product's area
                            inpainted_bg = await google_ai_service.inpaint_product_area(
                                request.image_base64, product_bbox_px, layer.get("product_name", "furniture")
                            )
                            logger.info(f"[{session_id}] Real-time inpainting completed for cached layer")
                        except Exception as inpaint_err:
                            logger.warning(f"[{session_id}] Real-time inpainting failed, using original image: {inpaint_err}")
                            inpainted_bg = request.image_base64

                        # Return the pre-computed layer with real-time inpainted background
                        return {
                            "session_id": session_id,
                            "layer": {
                                "id": layer.get("id", f"cached_{layer.get('product_id', 'unknown')}"),
                                "cutout": layer.get("cutout"),
                                "mask": layer.get("mask"),
                                "bbox": layer_bbox,
                                "x": layer.get("x", layer_x + layer_w / 2),
                                "y": layer.get("y", layer_y + layer_h / 2),
                                "width": layer_w,
                                "height": layer_h,
                            },
                            "matched_product_id": layer.get("product_id"),
                            "matched_product_name": layer.get("product_name"),
                            "inpainted_background": inpainted_bg,
                            "extraction_method": "precomputed_cache",
                            "cached": True,
                        }

                    logger.info(
                        f"[{session_id}] Cache exists but click point ({click_norm_x:.2f}, {click_norm_y:.2f}) not in any layer bbox"
                    )
        except Exception as cache_err:
            logger.debug(f"[{session_id}] Pre-computed layer check failed: {cache_err}")

        # ============================================================
        # NO CACHE HIT - Fall back to Gemini + SAM extraction
        # ============================================================
        logger.info(f"[{session_id}] No pre-computed layer found, using Gemini + SAM")

        # Step 1: Use Gemini to identify what specific object is at the click point
        # and get a bounding box for the COMPLETE object
        identify_prompt = f"""Look at this interior room image. There is a RED CIRCLE marker showing exactly where I clicked.

I clicked at position ({click_x}, {click_y}) in a {width}x{height} image. The RED CIRCLE shows the exact click location.

TASK: Identify ONLY the object that is DIRECTLY at the RED CIRCLE marker. Return the bounding box for that COMPLETE object.

⚠️ CRITICAL: Look ONLY at what the RED CIRCLE is touching. Do NOT identify nearby objects.

OBJECT IDENTIFICATION RULES:
1. FLOOR LAMPS / STANDING LAMPS - If the red circle is on a tall standing lamp:
   - Identify it as "floor lamp" or "standing lamp"
   - Bbox should include the ENTIRE lamp from base to top

2. CHAIRS - If the red circle is on a chair:
   - Include the ENTIRE chair (back, seat, legs, armrest)
   - Bbox from top of back to bottom of legs

3. SOFAS - If the red circle is on a sofa:
   - Include the ENTIRE sofa (all cushions, back, armrests, legs)

4. TABLES - If the red circle is on a table:
   - Include the ENTIRE table (top, legs, base)

5. CHANDELIERS / PENDANT LIGHTS - If the red circle is on a hanging light:
   - Include the ENTIRE light fixture

6. SMALL DECOR (vases, plants, sculptures) - If the red circle is on small decor ON furniture:
   - Include ONLY the decor item, NOT the furniture it sits on

Return a JSON object with:
{{
  "object_name": "specific name of the object AT the red circle (e.g., 'white floor lamp', 'cane accent chair', 'velvet sofa')",
  "object_type": "furniture|lighting|decor|accessory",
  "is_small_item": true if small decor placed on furniture, false otherwise,
  "estimated_bbox": {{
    "x": left edge (0-{width}),
    "y": top edge (0-{height}),
    "width": FULL object width in pixels,
    "height": FULL object height in pixels
  }}
}}

IMPORTANT: The bbox MUST be for the object the RED CIRCLE is ON, not nearby objects."""

        # Draw a marker on the image to show Gemini where the click was
        marked_image = pil_image.copy()
        from PIL import ImageDraw

        draw = ImageDraw.Draw(marked_image)
        # Draw crosshair at click point
        marker_size = 20
        draw.line([(click_x - marker_size, click_y), (click_x + marker_size, click_y)], fill="red", width=3)
        draw.line([(click_x, click_y - marker_size), (click_x, click_y + marker_size)], fill="red", width=3)
        draw.ellipse([(click_x - 10, click_y - 10), (click_x + 10, click_y + 10)], outline="red", width=2)

        client = genai.Client(api_key=settings.google_ai_api_key)

        def _identify_object():
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[identify_prompt, marked_image],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                ),
            )
            if response.text:
                return response.text
            return None

        loop = asyncio.get_event_loop()
        gemini_response = await asyncio.wait_for(loop.run_in_executor(None, _identify_object), timeout=30)

        object_info = None
        if gemini_response:
            logger.info(f"[{session_id}] Gemini object identification: {gemini_response[:200]}...")
            # Parse JSON from response
            try:
                # Find JSON in response
                json_match = re.search(r"\{[\s\S]*\}", gemini_response)
                if json_match:
                    object_info = json.loads(json_match.group())
                    logger.info(
                        f"[{session_id}] Identified object: {object_info.get('object_name')}, bbox: {object_info.get('estimated_bbox')}"
                    )
            except json.JSONDecodeError:
                logger.warning(f"[{session_id}] Could not parse Gemini response as JSON")

        # Step 2: Use the bbox info to create a focused crop and segment
        from services.sam_service import sam_service

        if object_info and object_info.get("estimated_bbox"):
            bbox = object_info["estimated_bbox"]
            is_furniture = object_info.get("object_type") == "furniture" or not object_info.get("is_small_item", True)

            # Add padding - MORE for furniture to ensure full object capture
            # Furniture often has legs that extend beyond the main body
            if is_furniture:
                # For furniture: add 20% of object size as padding, minimum 50px
                pad_x = max(50, int(bbox["width"] * 0.2))
                pad_y = max(50, int(bbox["height"] * 0.3))  # More vertical padding for legs
                logger.info(f"[{session_id}] Furniture detected - using extended padding: x={pad_x}, y={pad_y}")
            else:
                # For small decor items: smaller padding
                pad_x = 30
                pad_y = 30

            crop_x1 = max(0, bbox["x"] - pad_x)
            crop_y1 = max(0, bbox["y"] - pad_y)
            crop_x2 = min(width, bbox["x"] + bbox["width"] + pad_x)
            crop_y2 = min(height, bbox["y"] + bbox["height"] + pad_y)

            # Create cropped image for SAM
            cropped_image = pil_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))
            crop_width, crop_height = cropped_image.size

            # Convert cropped image to base64
            crop_buffer = io.BytesIO()
            cropped_image.save(crop_buffer, format="PNG")
            crop_buffer.seek(0)
            crop_b64 = f"data:image/png;base64,{base64.b64encode(crop_buffer.getvalue()).decode()}"

            # Calculate click point relative to crop
            relative_point = {"x": (click_x - crop_x1) / crop_width, "y": (click_y - crop_y1) / crop_height}

            logger.info(f"[{session_id}] Using cropped region ({crop_x1},{crop_y1})-({crop_x2},{crop_y2}) for SAM")

            # For furniture, use multiple points to capture the full object
            # Adapt point placement based on furniture shape (aspect ratio)
            if is_furniture:
                # Generate points within the INTERIOR of the furniture bounding box
                # The bbox is relative to the full image, convert to crop coordinates
                bbox_left = (bbox["x"] - crop_x1) / crop_width
                bbox_right = (bbox["x"] + bbox["width"] - crop_x1) / crop_width
                bbox_top = (bbox["y"] - crop_y1) / crop_height
                bbox_bottom = (bbox["y"] + bbox["height"] - crop_y1) / crop_height
                bbox_center_x = (bbox_left + bbox_right) / 2
                bbox_center_y = (bbox_top + bbox_bottom) / 2

                # Calculate aspect ratio to determine point placement strategy
                aspect_ratio = bbox["width"] / bbox["height"] if bbox["height"] > 0 else 1.0

                if aspect_ratio < 0.6:
                    # TALL/VERTICAL furniture (floor lamps, standing mirrors, coat racks)
                    # Use vertical spread but avoid very bottom (where floor/carpet is)
                    logger.info(f"[{session_id}] Detected TALL furniture (aspect ratio {aspect_ratio:.2f})")
                    multi_points = [
                        relative_point,  # Original click point
                        {"x": bbox_center_x, "y": bbox_center_y},  # Center
                        {"x": bbox_center_x, "y": bbox_top + (bbox_bottom - bbox_top) * 0.15},  # Upper region
                        {"x": bbox_center_x, "y": bbox_top + (bbox_bottom - bbox_top) * 0.35},  # Upper-middle
                        # Bottom point at 75% height - captures lower parts but avoids floor
                        {"x": bbox_center_x, "y": bbox_top + (bbox_bottom - bbox_top) * 0.75},
                    ]
                    point_strategy = "vertical"
                else:
                    # WIDE/NORMAL furniture (chairs, sofas, tables, beds)
                    # Use GRID approach: horizontal spread at MULTIPLE heights
                    # This captures both tabletops and bases, chair seats and backs
                    logger.info(f"[{session_id}] Detected WIDE furniture (aspect ratio {aspect_ratio:.2f})")

                    # Heights: 25% (upper), 50% (center), 75% (lower but not bottom)
                    upper_y = bbox_top + (bbox_bottom - bbox_top) * 0.25
                    lower_y = bbox_top + (bbox_bottom - bbox_top) * 0.75

                    multi_points = [
                        relative_point,  # Original click point
                        {"x": bbox_center_x, "y": bbox_center_y},  # Center
                        # Upper row (for tabletops, chair backs)
                        {"x": bbox_left + (bbox_right - bbox_left) * 0.25, "y": upper_y},
                        {"x": bbox_left + (bbox_right - bbox_left) * 0.75, "y": upper_y},
                        # Lower row (for table bases, chair legs)
                        {"x": bbox_left + (bbox_right - bbox_left) * 0.25, "y": lower_y},
                        {"x": bbox_left + (bbox_right - bbox_left) * 0.75, "y": lower_y},
                    ]
                    point_strategy = "grid"

                # Clamp all points to valid range
                multi_points = [{"x": max(0.05, min(0.95, p["x"])), "y": max(0.05, min(0.95, p["y"]))} for p in multi_points]

                logger.info(f"[{session_id}] Using {len(multi_points)} {point_strategy} points for furniture segmentation")

                # Call SAM with multiple points
                result = await sam_service.segment_at_points(
                    image_base64=crop_b64, points=multi_points, label=object_info.get("object_name", request.label or "object")
                )
            else:
                # For small items, single point is fine
                result = await sam_service.segment_at_point(
                    image_base64=crop_b64,
                    point=relative_point,
                    label=object_info.get("object_name", request.label or "object"),
                )

            # Adjust bbox back to full image coordinates
            full_bbox = {
                "x": (crop_x1 + result.bbox["x"] * crop_width) / width,
                "y": (crop_y1 + result.bbox["y"] * crop_height) / height,
                "width": result.bbox["width"] * crop_width / width,
                "height": result.bbox["height"] * crop_height / height,
            }

            full_center = {
                "x": (crop_x1 + result.center["x"] * crop_width) / width,
                "y": (crop_y1 + result.center["y"] * crop_height) / height,
            }

            # Step 3: Match cutout to a product if products list provided
            # Uses visual comparison with product images for accurate matching
            matched_product_id = None
            if request.products and len(request.products) > 0:
                logger.info(f"[{session_id}] Matching cutout to {len(request.products)} products")

                # Decode cutout for matching
                cutout_data = result.cutout
                if cutout_data.startswith("data:"):
                    cutout_data = cutout_data.split(",", 1)[1]
                cutout_bytes = base64.b64decode(cutout_data)
                cutout_pil = Image.open(io.BytesIO(cutout_bytes)).convert("RGBA")

                # Fetch product images for visual comparison
                product_images = []
                for p in request.products:
                    if p.image_url:
                        try:
                            async with httpx.AsyncClient(timeout=10.0) as http_client:
                                img_response = await http_client.get(p.image_url)
                                if img_response.status_code == 200:
                                    p_img = Image.open(io.BytesIO(img_response.content)).convert("RGB")
                                    # Resize to consistent size for comparison
                                    p_img.thumbnail((200, 200))
                                    product_images.append((p.id, p.name, p_img))
                                    logger.debug(f"[{session_id}] Loaded image for product {p.id}: {p.name}")
                        except Exception as img_err:
                            logger.debug(f"[{session_id}] Failed to load image for product {p.id}: {img_err}")
                            product_images.append((p.id, p.name, None))
                    else:
                        product_images.append((p.id, p.name, None))

                if product_images:
                    # Build prompt with visual comparison
                    product_list = "\n".join([f"- ID {pid}: {pname}" for pid, pname, _ in product_images])

                    # Build content with cutout and product images
                    contents = [
                        f"""I'm showing you a furniture/decor item extracted from a room visualization (first image),
followed by product images from our catalog. Match the extracted item to the correct product.

Products in the visualization:
{product_list}

Look at the extracted item and compare it visually to each product image.
Consider shape, style, color, and overall appearance.

Return ONLY the product ID number that best matches the extracted item. Just the number, nothing else.
If none match well, return 0.""",
                        cutout_pil,  # The extracted item
                    ]

                    # Add product images that we successfully loaded
                    for pid, pname, pimg in product_images:
                        if pimg:
                            contents.append(f"Product ID {pid} ({pname}):")
                            contents.append(pimg)

                    def _match_product():
                        response = client.models.generate_content(
                            model="gemini-2.0-flash-exp",
                            contents=contents,
                            config=types.GenerateContentConfig(temperature=0.1),
                        )
                        if response.text:
                            return response.text.strip()
                        return None

                    try:
                        match_result = await asyncio.wait_for(loop.run_in_executor(None, _match_product), timeout=20)
                        if match_result:
                            # Extract number from response
                            match_num = re.search(r"\d+", match_result)
                            if match_num:
                                matched_id = int(match_num.group())
                                if matched_id > 0 and any(p.id == matched_id for p in request.products):
                                    matched_product_id = matched_id
                                    matched_name = next((p.name for p in request.products if p.id == matched_id), "unknown")
                                    logger.info(f"[{session_id}] Matched to product {matched_product_id}: {matched_name}")
                                else:
                                    logger.warning(f"[{session_id}] Gemini returned ID {matched_id} but not in product list")
                    except Exception as match_err:
                        logger.warning(f"[{session_id}] Product matching failed: {match_err}")

            # Step 4: Get clean background (try cache first, then inpaint)
            # This creates a clean background for the user to drag over

            # Decode the mask from SAM result and create full-image mask (needed for both paths)
            mask_data = result.mask
            if mask_data.startswith("data:"):
                mask_data = mask_data.split(",", 1)[1]
            mask_bytes = base64.b64decode(mask_data)
            crop_mask = Image.open(io.BytesIO(mask_bytes)).convert("L")

            # Create full-size mask
            full_mask = Image.new("L", (width, height), 0)
            # Resize crop mask to match the crop region size and paste
            crop_mask_resized = crop_mask.resize((crop_x2 - crop_x1, crop_y2 - crop_y1), Image.NEAREST)
            full_mask.paste(crop_mask_resized, (crop_x1, crop_y1))

            # Dilate mask slightly for better inpainting
            from PIL import ImageFilter

            full_mask = full_mask.filter(ImageFilter.MaxFilter(7))

            # CHECK CACHE for pre-computed clean background
            inpainted_b64 = None
            try:
                from services.mask_precomputation_service import mask_precomputation_service

                from core.database import AsyncSessionLocal

                async with AsyncSessionLocal() as cache_db:
                    cached_result = None

                    # First try curated_look_id cache (if provided)
                    if request.curated_look_id:
                        cached_result = await mask_precomputation_service.get_cached_masks_for_curated_look(
                            cache_db, request.curated_look_id, request.image_base64
                        )
                        if cached_result and cached_result.get("background"):
                            inpainted_b64 = cached_result["background"]
                            logger.info(
                                f"[{session_id}] CACHE HIT (curated look {request.curated_look_id}) - Using pre-computed clean background (saved ~3s)"
                            )

                    # Fall back to session_id cache
                    if not inpainted_b64:
                        cached_result = await mask_precomputation_service.get_cached_masks(
                            cache_db, session_id, request.image_base64, []
                        )
                        if cached_result and cached_result.get("background"):
                            inpainted_b64 = cached_result["background"]
                            logger.info(
                                f"[{session_id}] CACHE HIT (session) - Using pre-computed clean background (saved ~3s)"
                            )
            except Exception as cache_err:
                logger.debug(f"[{session_id}] Cache check failed: {cache_err}")

            # If no cached background, do inpainting with Gemini
            if not inpainted_b64:
                logger.info(f"[{session_id}] CACHE MISS - Inpainting original object location with Gemini")

                object_name = object_info.get("object_name", "object")
                inpaint_prompt = f"""Edit this interior room image.

TASK: Remove the {object_name} that has been selected (shown by the white area in the mask).
Fill the area where the {object_name} was with matching background - continue the floor, wall, or surface pattern naturally.

IMPORTANT:
- Only modify the masked area (where the object was)
- Do NOT change anything else in the room
- Make the fill seamless and natural
- Match the lighting and perspective

Generate the room image with the {object_name} cleanly removed."""

                def _run_inpaint():
                    """Run Gemini inpainting to remove the object"""
                    # Use gemini-3-pro-image-preview which supports image generation
                    response = client.models.generate_content(
                        model="gemini-3-pro-image-preview",
                        contents=[inpaint_prompt, pil_image, full_mask.convert("RGB")],
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            temperature=0.3,
                        ),
                    )

                    inpainted_image = None
                    parts = None
                    if hasattr(response, "parts") and response.parts:
                        parts = response.parts
                    elif hasattr(response, "candidates") and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                            parts = candidate.content.parts

                    if parts:
                        for part in parts:
                            if hasattr(part, "inline_data") and part.inline_data is not None:
                                image_bytes = part.inline_data.data
                                if isinstance(image_bytes, bytes):
                                    first_hex = image_bytes[:4].hex()
                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        inpainted_image = Image.open(io.BytesIO(image_bytes))
                                    else:
                                        decoded = base64.b64decode(image_bytes)
                                        inpainted_image = Image.open(io.BytesIO(decoded))
                    return inpainted_image

                try:
                    inpainted_background = await asyncio.wait_for(loop.run_in_executor(None, _run_inpaint), timeout=60)
                    if inpainted_background:
                        # Resize to match original if needed
                        if inpainted_background.size != (width, height):
                            inpainted_background = inpainted_background.resize((width, height), Image.LANCZOS)

                        # Convert to base64
                        inpaint_buffer = io.BytesIO()
                        inpainted_background.convert("RGB").save(inpaint_buffer, format="PNG")
                        inpaint_buffer.seek(0)
                        inpainted_b64 = f"data:image/png;base64,{base64.b64encode(inpaint_buffer.getvalue()).decode()}"
                        logger.info(f"[{session_id}] Inpainting successful")
                    else:
                        logger.warning(f"[{session_id}] Inpainting returned no image")
                except Exception as inpaint_error:
                    logger.warning(
                        f"[{session_id}] Inpainting failed: {inpaint_error}, continuing without inpainted background"
                    )

            return {
                "layer": {
                    "id": result.id,
                    "label": object_info.get("object_name", result.label),
                    "cutout": result.cutout,
                    "mask": result.mask,
                    "bbox": full_bbox,
                    "x": full_center["x"],
                    "y": full_center["y"],
                    "width": full_bbox["width"],
                    "height": full_bbox["height"],
                    "scale": 1.0,
                    "area": result.area,
                    "stability_score": result.stability_score,
                    "product_id": matched_product_id,  # Matched product from DB
                },
                "inpainted_background": inpainted_b64,  # Clean background with object removed
                "matched_product_id": matched_product_id,  # For easy access
                "session_id": session_id,
                "status": "success",
                "object_info": object_info,
            }

        # Fallback: use SAM on full image if Gemini didn't help
        logger.info(f"[{session_id}] Falling back to full-image SAM")
        result = await sam_service.segment_at_point(
            image_base64=request.image_base64, point=request.point, label=request.label or "object"
        )

        # Also do inpainting for fallback path
        mask_data = result.mask
        if mask_data.startswith("data:"):
            mask_data = mask_data.split(",", 1)[1]
        mask_bytes = base64.b64decode(mask_data)
        full_mask = Image.open(io.BytesIO(mask_bytes)).convert("L")

        # Resize mask to match image if needed
        if full_mask.size != (width, height):
            full_mask = full_mask.resize((width, height), Image.NEAREST)

        # Dilate mask slightly
        from PIL import ImageFilter

        full_mask = full_mask.filter(ImageFilter.MaxFilter(7))

        inpaint_prompt = f"""Edit this interior room image.

TASK: Remove the object that has been selected (shown by the white area in the mask).
Fill the area where the object was with matching background - continue the floor, wall, or surface pattern naturally.

IMPORTANT:
- Only modify the masked area
- Do NOT change anything else in the room
- Make the fill seamless and natural

Generate the room image with the object cleanly removed."""

        def _run_fallback_inpaint():
            # Use gemini-3-pro-image-preview which supports image generation
            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=[inpaint_prompt, pil_image, full_mask.convert("RGB")],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.3,
                ),
            )
            inpainted_image = None
            parts = None
            if hasattr(response, "parts") and response.parts:
                parts = response.parts
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    parts = candidate.content.parts
            if parts:
                for part in parts:
                    if hasattr(part, "inline_data") and part.inline_data is not None:
                        img_bytes = part.inline_data.data
                        if isinstance(img_bytes, bytes):
                            first_hex = img_bytes[:4].hex()
                            if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                inpainted_image = Image.open(io.BytesIO(img_bytes))
                            else:
                                decoded = base64.b64decode(img_bytes)
                                inpainted_image = Image.open(io.BytesIO(decoded))
            return inpainted_image

        fallback_inpainted_b64 = None
        try:
            fallback_inpainted = await asyncio.wait_for(loop.run_in_executor(None, _run_fallback_inpaint), timeout=60)
            if fallback_inpainted:
                if fallback_inpainted.size != (width, height):
                    fallback_inpainted = fallback_inpainted.resize((width, height), Image.LANCZOS)
                fb_buffer = io.BytesIO()
                fallback_inpainted.convert("RGB").save(fb_buffer, format="PNG")
                fb_buffer.seek(0)
                fallback_inpainted_b64 = f"data:image/png;base64,{base64.b64encode(fb_buffer.getvalue()).decode()}"
        except Exception as fb_err:
            logger.warning(f"[{session_id}] Fallback inpainting failed: {fb_err}")

        return {
            "layer": {
                "id": result.id,
                "label": result.label,
                "cutout": result.cutout,
                "mask": result.mask,
                "bbox": result.bbox,
                "x": result.center["x"],
                "y": result.center["y"],
                "width": result.bbox["width"],
                "height": result.bbox["height"],
                "scale": 1.0,
                "area": result.area,
                "stability_score": result.stability_score,
            },
            "inpainted_background": fallback_inpainted_b64,
            "session_id": session_id,
            "status": "success",
        }

    except ValueError as e:
        logger.warning(f"[{session_id}] Segment at point failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{session_id}] Error in segment-at-point: {e}")
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {str(e)}")


@router.post("/sessions/{session_id}/segment-at-points")
async def segment_at_points(session_id: str, request: SegmentAtPointsRequest):
    """
    Segment object using multiple click points (grouped selection).

    Use this when user wants to select multiple items as one unit,
    e.g., sofa + all pillows, or table + all objects on it.

    All points with the same label are merged into a single mask.
    """
    try:
        from services.sam_service import sam_service

        logger.info(f"[{session_id}] Segmenting at {len(request.points)} points")

        # Call SAM 2 with multiple points
        result = await sam_service.segment_at_points(
            image_base64=request.image_base64, points=request.points, label=request.label or "object"
        )

        return {
            "layer": {
                "id": result.id,
                "label": result.label,
                "cutout": result.cutout,
                "mask": result.mask,
                "bbox": result.bbox,
                "x": result.center["x"],
                "y": result.center["y"],
                "width": result.bbox["width"],
                "height": result.bbox["height"],
                "scale": 1.0,
                "area": result.area,
                "stability_score": result.stability_score,
            },
            "session_id": session_id,
            "status": "success",
        }

    except ValueError as e:
        logger.warning(f"[{session_id}] Segment at points failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[{session_id}] Error in segment-at-points: {e}")
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {str(e)}")


class FinalizeWithRevisualizationRequest(BaseModel):
    """Request model for finalizing with re-visualization"""

    original_image: str  # Original visualization image
    cutout: str  # The extracted object PNG (for reference)
    object_description: Optional[str] = None  # Description of the moved object
    original_position: Dict[str, float]  # {"x": 0.2, "y": 0.3} normalized
    new_position: Dict[str, float]  # {"x": 0.5, "y": 0.4} normalized
    scale: float = 1.0


@router.post("/sessions/{session_id}/finalize-move")
async def finalize_move(session_id: str, request: FinalizeMoveRequest, db: AsyncSession = Depends(get_db)):
    """
    Finalize object movement using Gemini re-visualization.

    Uses the clean product image from the database (if product_id provided)
    and places it naturally into the inpainted background at the new position.

    Flow:
    1. Fetch product image from DB (or use cutout as fallback)
    2. Use inpainted background as the base room
    3. Have Gemini place the product at the new position like a new product addition
    """
    import asyncio
    import base64
    import io

    import httpx
    from google import genai
    from google.genai import types
    from PIL import Image
    from sqlalchemy import select

    from core.config import settings

    try:
        logger.info(
            f"[{session_id}] Re-visualizing with object moved to {request.new_position}, product_id={request.product_id}"
        )

        # Decode original image
        original_data = request.original_image
        if original_data.startswith("data:"):
            original_data = original_data.split(",", 1)[1]
        original_bytes = base64.b64decode(original_data)
        original_image = Image.open(io.BytesIO(original_bytes)).convert("RGB")
        width, height = original_image.size

        # Get product image from database if product_id provided
        product_image = None
        product_name = "furniture item"
        if request.product_id:
            logger.info(f"[{session_id}] Fetching product {request.product_id} from database")
            result = await db.execute(select(Product).where(Product.id == request.product_id))
            product = result.scalar_one_or_none()
            if product:
                product_name = product.name or "furniture item"
                # Get product images
                from database.models import ProductImage

                img_result = await db.execute(
                    select(ProductImage)
                    .where(ProductImage.product_id == request.product_id)
                    .order_by(ProductImage.display_order)
                )
                images = img_result.scalars().all()
                if images:
                    # Try to get the best quality image
                    img_url = images[0].large_url or images[0].medium_url or images[0].original_url
                    if img_url:
                        try:
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                img_response = await client.get(img_url)
                                img_response.raise_for_status()
                                product_image = Image.open(io.BytesIO(img_response.content)).convert("RGBA")
                                logger.info(f"[{session_id}] Loaded product image: {product_name}")
                        except Exception as img_err:
                            logger.warning(f"[{session_id}] Failed to fetch product image: {img_err}")

        # Fall back to cutout if no product image
        if not product_image:
            cutout_data = request.cutout
            if cutout_data.startswith("data:"):
                cutout_data = cutout_data.split(",", 1)[1]
            cutout_bytes = base64.b64decode(cutout_data)
            product_image = Image.open(io.BytesIO(cutout_bytes)).convert("RGBA")
            logger.info(f"[{session_id}] Using cutout as product image (no product_id or fetch failed)")

        # Decode inpainted background if provided (clean background with object removed)
        inpainted_image = None
        if request.inpainted_background:
            inpainted_data = request.inpainted_background
            if inpainted_data.startswith("data:"):
                inpainted_data = inpainted_data.split(",", 1)[1]
            inpainted_bytes = base64.b64decode(inpainted_data)
            inpainted_image = Image.open(io.BytesIO(inpainted_bytes)).convert("RGB")
            logger.info(f"[{session_id}] Using pre-inpainted background for re-visualization")

        # Initialize Gemini client
        client = genai.Client(api_key=settings.google_ai_api_key)

        # Convert normalized coords to pixel position
        pixel_x = int(request.new_position["x"] * width)
        pixel_y = int(request.new_position["y"] * height)
        orig_pixel_x = int(request.original_position["x"] * width)
        orig_pixel_y = int(request.original_position["y"] * height)
        logger.info(f"[{session_id}] Moving from ({orig_pixel_x}, {orig_pixel_y}) to ({pixel_x}, {pixel_y})")

        # HYBRID APPROACH: Precise positioning with PIL, then Gemini harmonization
        # Step 1: Composite cutout onto inpainted background at exact position
        # Step 2: Have Gemini harmonize/blend the composited image

        def _create_precise_composite():
            """Create a precise composite with cutout at exact new position"""
            # Use inpainted background if available, otherwise original
            base_image = inpainted_image if inpainted_image else original_image.copy()
            base_image = base_image.convert("RGBA")

            # Prepare cutout
            cutout_to_paste = product_image.convert("RGBA")

            # Apply scale if needed
            if request.scale != 1.0:
                new_w = int(cutout_to_paste.width * request.scale)
                new_h = int(cutout_to_paste.height * request.scale)
                cutout_to_paste = cutout_to_paste.resize((new_w, new_h), Image.LANCZOS)

            # Calculate paste position (center the cutout at the new position)
            paste_x = int(pixel_x - cutout_to_paste.width / 2)
            paste_y = int(pixel_y - cutout_to_paste.height / 2)

            # Clamp to image bounds
            paste_x = max(0, min(width - cutout_to_paste.width, paste_x))
            paste_y = max(0, min(height - cutout_to_paste.height, paste_y))

            logger.info(f"[{session_id}] Compositing cutout at ({paste_x}, {paste_y}), size {cutout_to_paste.size}")

            # Paste with alpha mask for transparency
            base_image.paste(cutout_to_paste, (paste_x, paste_y), cutout_to_paste)

            return base_image.convert("RGB")

        # Create the precise composite first
        composited_image = _create_precise_composite()
        logger.info(f"[{session_id}] Created precise composite at position ({pixel_x}, {pixel_y})")

        revisualize_prompt = f"""HARMONIZE this interior design image.

The "{product_name}" has been placed in the room. Your task is to make it look natural:

INSTRUCTIONS:
1. KEEP the {product_name} EXACTLY where it is currently placed - DO NOT move it
2. Adjust lighting and shadows on the {product_name} to match the room's lighting
3. Blend edges naturally with the surrounding floor/furniture
4. Ensure the product looks like it naturally belongs in this position
5. Keep ALL other furniture and elements exactly as they are

CRITICAL: The {product_name} position is CORRECT. Do NOT change its location. Only harmonize lighting and shadows.

QUALITY REQUIREMENTS:
- Output at MAXIMUM resolution: {width}x{height} pixels
- Generate HIGHEST QUALITY photorealistic output
- Preserve all fine details from the input image"""

        def _run_revisualize():
            """Run the re-visualization with Gemini harmonization"""
            # Use the pre-composited image where object is already at the new position
            background_to_use = composited_image
            logger.info(f"[{session_id}] Using PRE-COMPOSITED image for Gemini harmonization ({background_to_use.size})")

            # Only send the composited image - product is already placed at the correct position
            # Gemini just needs to harmonize lighting/shadows, not move anything
            contents = [
                revisualize_prompt,
                "Room image with product already placed (harmonize this):",
                background_to_use,
            ]

            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.4,
                ),
            )

            result_image = None
            parts = None
            if hasattr(response, "parts") and response.parts:
                parts = response.parts
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate.content, "parts"):
                    parts = candidate.content.parts

            if parts:
                for part in parts:
                    if hasattr(part, "inline_data") and part.inline_data is not None:
                        image_data = part.inline_data.data
                        if isinstance(image_data, bytes):
                            first_hex = image_data[:4].hex()
                            if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                result_image = Image.open(io.BytesIO(image_data))
                            else:
                                decoded = base64.b64decode(image_data)
                                result_image = Image.open(io.BytesIO(decoded))
                        logger.info("Gemini re-visualization successful")
            return result_image

        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(loop.run_in_executor(None, _run_revisualize), timeout=90)

        if result:
            if result.size != (width, height):
                result = result.resize((width, height), Image.LANCZOS)

            result_buffer = io.BytesIO()
            result.convert("RGB").save(result_buffer, format="PNG", optimize=False)
            result_buffer.seek(0)
            result_b64 = f"data:image/png;base64,{base64.b64encode(result_buffer.getvalue()).decode()}"

            return {
                "image": result_b64,
                "session_id": session_id,
                "status": "success",
                "dimensions": {"width": width, "height": height},
            }

        raise ValueError("Gemini failed to generate visualization")

    except Exception as e:
        logger.error(f"[{session_id}] Error in re-visualization: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to finalize move: {str(e)}")


@router.post("/sessions/{session_id}/revisualize-with-positions")
async def revisualize_with_positions(
    session_id: str,
    request: RevisualizeWithPositionsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Re-visualize the entire scene with products at specified positions.

    This is the proper way to handle furniture repositioning:
    1. Takes the clean room image (without any furniture)
    2. Takes all products with their positions
    3. Generates a complete re-visualization with all products at their specified positions

    This approach is more reliable than trying to edit an existing visualization.
    """
    import httpx
    from services.google_ai_service import VisualizationRequest, google_ai_service
    from sqlalchemy import select

    from database.models import Product, ProductImage

    try:
        logger.info(f"[{session_id}] Re-visualizing with {len(request.positions)} product positions")

        # Build position lookup by product_id
        position_map = {pos.product_id: pos for pos in request.positions}

        # Fetch product details from database
        product_ids = [pos.product_id for pos in request.positions]
        products_query = select(Product).where(Product.id.in_(product_ids))
        products_result = await db.execute(products_query)
        db_products = {p.id: p for p in products_result.scalars().all()}

        # Fetch product images
        images_query = select(ProductImage).where(ProductImage.product_id.in_(product_ids))
        images_result = await db.execute(images_query)
        product_images = {}
        for img in images_result.scalars().all():
            if img.product_id not in product_images:
                product_images[img.product_id] = []
            product_images[img.product_id].append(img)

        # Build products list with images for visualization
        products_to_place = []
        custom_positions = []

        for idx, pos in enumerate(request.positions):
            product = db_products.get(pos.product_id)
            if not product:
                logger.warning(f"Product {pos.product_id} not found in database")
                continue

            # Get product image URL
            image_url = None
            if pos.product_id in product_images:
                imgs = sorted(product_images[pos.product_id], key=lambda x: x.display_order)
                if imgs:
                    image_url = imgs[0].large_url or imgs[0].medium_url or imgs[0].original_url

            # Fetch product image as base64
            product_image_b64 = None
            if image_url:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        img_response = await client.get(image_url)
                        img_response.raise_for_status()
                        import base64

                        product_image_b64 = f"data:image/jpeg;base64,{base64.b64encode(img_response.content).decode()}"
                except Exception as e:
                    logger.warning(f"Failed to fetch product image for {product.name}: {e}")

            # Build product info
            product_info = {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "product_type": product.product_type,
                "quantity": 1,
            }
            if product_image_b64:
                product_info["image"] = product_image_b64

            products_to_place.append(product_info)

            # Build custom position (normalized x,y to position description)
            # Convert normalized coordinates to position description for Gemini
            x_pos = "left" if pos.x < 0.33 else "right" if pos.x > 0.66 else "center"
            y_pos = "front" if pos.y > 0.66 else "back" if pos.y < 0.33 else "middle"
            position_desc = f"{y_pos}-{x_pos}"

            custom_positions.append(
                {
                    "product_index": idx,
                    "position": position_desc,
                    "normalized_x": pos.x,
                    "normalized_y": pos.y,
                }
            )

            logger.info(f"Product {product.name}: position ({pos.x:.2f}, {pos.y:.2f}) -> {position_desc}")

        if not products_to_place:
            raise HTTPException(status_code=400, detail="No valid products found")

        # Generate visualization using existing service
        viz_request = VisualizationRequest(
            base_image=request.room_image,
            products_to_place=products_to_place,
            placement_positions=custom_positions,
            lighting_conditions="natural daylight",
            render_quality="high",
            style_consistency=True,
            user_style_description="",
            exclusive_products=True,  # Only show specified products
        )

        logger.info(f"[{session_id}] Calling visualization service with {len(products_to_place)} products")
        viz_result = await google_ai_service.generate_room_visualization(viz_request)

        if viz_result and viz_result.rendered_image:
            logger.info(f"[{session_id}] Re-visualization complete")
            return {
                "image": viz_result.rendered_image,
                "session_id": session_id,
                "status": "success",
                "processing_time": viz_result.processing_time,
                "quality_score": viz_result.quality_score,
            }

        raise ValueError("Visualization service failed to generate image")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{session_id}] Error in revisualize-with-positions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Re-visualization failed: {str(e)}")


async def _fallback_composite(
    original_image: "Image.Image", cutout_image: "Image.Image", new_position: Dict[str, float], scale: float, session_id: str
) -> Dict:
    """Fallback: simple composite without inpainting"""
    import base64
    import io

    from PIL import Image

    width, height = original_image.size

    if scale != 1.0:
        new_size = (int(cutout_image.width * scale), int(cutout_image.height * scale))
        cutout_image = cutout_image.resize(new_size, Image.LANCZOS)

    paste_x = int(new_position["x"] * width - cutout_image.width / 2)
    paste_y = int(new_position["y"] * height - cutout_image.height / 2)
    paste_x = max(0, min(width - cutout_image.width, paste_x))
    paste_y = max(0, min(height - cutout_image.height, paste_y))

    result = original_image.convert("RGBA")
    result.paste(cutout_image, (paste_x, paste_y), cutout_image)

    result_buffer = io.BytesIO()
    result.convert("RGB").save(result_buffer, format="PNG")
    result_buffer.seek(0)
    result_b64 = f"data:image/png;base64,{base64.b64encode(result_buffer.getvalue()).decode()}"

    return {
        "image": result_b64,
        "session_id": session_id,
        "status": "success",
        "fallback": True,
        "dimensions": {"width": width, "height": height},
    }


async def _inpaint_region(image: "Image.Image", mask: "Image.Image", prompt: str) -> "Image.Image":
    """
    Inpaint a region of an image using Gemini's image editing capability.

    Uses Gemini to intelligently fill in the masked region with appropriate
    room background (floor, wall, etc.).
    """
    import asyncio
    import base64
    import io

    import numpy as np
    from google import genai
    from google.genai import types
    from PIL import Image

    from core.config import settings

    try:
        logger.info("Starting inpainting with Gemini...")

        # Create composite image with mask overlay to show Gemini what to fill
        # We'll create an image where the masked area is highlighted
        image_rgba = image.convert("RGBA")
        mask_array = np.array(mask)

        # Create a red overlay on the masked area to show what to remove
        overlay = image_rgba.copy()
        overlay_array = np.array(overlay)

        # Where mask is white (255), make it semi-transparent red to indicate "fill this"
        mask_bool = mask_array > 128
        overlay_array[mask_bool] = [255, 0, 0, 180]  # Red with alpha

        overlay_with_mask = Image.fromarray(overlay_array)

        # Create the marked image showing what to fill
        marked_image = image_rgba.copy()
        marked_array = np.array(marked_image)
        # Apply red tint to masked area
        marked_array[mask_bool, 0] = 255  # Red channel
        marked_array[mask_bool, 1] = 0  # Green channel
        marked_array[mask_bool, 2] = 0  # Blue channel
        marked_image = Image.fromarray(marked_array).convert("RGB")

        # Send the marked image to Gemini so it sees what area to fill
        img_for_gemini = marked_image

        inpaint_prompt = f"""Edit this interior room image.

The red/highlighted area in the overlay shows where an object has been removed.
Fill in this area with appropriate room background - matching floor, wall, or rug texture
that naturally continues from the surrounding area.

Make the filled area blend seamlessly with the rest of the room.
Do NOT add any new furniture or objects - just fill with matching background.

The goal is to make it look like there was never anything in that spot."""

        # Initialize Gemini client
        client = genai.Client(api_key=settings.google_ai_api_key)

        def _run_inpaint():
            """Run the blocking generate_content call"""
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[inpaint_prompt, img_for_gemini],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.3,
                ),
            )

            result_image = None
            parts = None
            if hasattr(response, "parts") and response.parts:
                parts = response.parts
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    parts = candidate.content.parts

            if parts:
                for part in parts:
                    if hasattr(part, "inline_data") and part.inline_data is not None:
                        image_data = part.inline_data.data

                        if isinstance(image_data, bytes):
                            first_hex = image_data[:4].hex()
                            if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                # Raw image bytes
                                result_image = Image.open(io.BytesIO(image_data))
                            else:
                                # Base64 encoded
                                decoded = base64.b64decode(image_data)
                                result_image = Image.open(io.BytesIO(decoded))
                        logger.info("Gemini inpainting successful")

            return result_image

        # Run with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(loop.run_in_executor(None, _run_inpaint), timeout=60)

        if result:
            # Resize to match original if needed
            if result.size != image.size:
                result = result.resize(image.size, Image.LANCZOS)
            return result.convert("RGBA")

        logger.warning("Gemini inpainting returned no image, returning original")
        return image

    except Exception as e:
        logger.error(f"Gemini inpainting failed: {e}, returning original image")
        return image


@router.post("/sessions/{session_id}/edit-with-instructions")
async def edit_with_instructions(
    session_id: str,
    request: EditWithInstructionsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Edit a visualization using text-based instructions.

    Takes the current visualization image and a user instruction (e.g., "Place the flower vase on the bench")
    and uses Gemini to edit the image according to the instructions while keeping everything else the same.

    This is the preferred approach for repositioning furniture as it:
    1. Uses the existing visualization (preserves room context and lighting)
    2. Lets Gemini understand spatial context from the text instruction
    3. Keeps all other elements exactly as they are
    4. Includes product reference images so Gemini preserves exact product appearance
    """
    import asyncio
    import base64
    import io

    import httpx
    from google import genai
    from google.genai import types
    from PIL import Image

    from core.config import settings

    try:
        logger.info(f"[{session_id}] Editing visualization with instructions: {request.instructions[:100]}...")

        # Parse the input image
        image_data = request.image
        if image_data.startswith("data:"):
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        input_image = Image.open(io.BytesIO(image_bytes))
        width, height = input_image.size

        logger.info(f"[{session_id}] Input image size: {width}x{height}")

        # Fetch product reference images
        product_images = []
        product_list_text = ""
        if request.products:
            logger.info(f"[{session_id}] Fetching {len(request.products)} product reference images...")
            product_list_text = "\n\nPRODUCTS IN THIS SCENE (these must appear EXACTLY as shown in reference images):\n"
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                for product in request.products:
                    product_list_text += f"- {product.name} (quantity: {product.quantity})\n"
                    if product.image_url:
                        try:
                            img_response = await http_client.get(product.image_url)
                            img_response.raise_for_status()
                            prod_img = Image.open(io.BytesIO(img_response.content))
                            product_images.append((product.name, prod_img))
                            logger.info(f"[{session_id}] Fetched reference image for: {product.name}")
                        except Exception as e:
                            logger.warning(f"[{session_id}] Failed to fetch image for {product.name}: {e}")

        # Build the prompt for Gemini
        edit_prompt = f"""You are an interior design image editor. RELOCATE furniture in this room image.

INSTRUCTION: {request.instructions}
{product_list_text}
WHAT "MOVE" MEANS:
- MOVE = RELOCATE = Take the item FROM its current position and PUT it at the new position
- The item must NO LONGER EXIST at its original location
- The original location should show the floor/wall/background that was behind it
- DO NOT DUPLICATE - there should be exactly ONE of each item (unless quantity specifies more)

ABSOLUTE RULES - VIOLATION IS FAILURE:
1. NEVER ADD NEW ITEMS - if there is 1 bench, there must still be exactly 1 bench
2. NEVER DUPLICATE - moving an item means it disappears from original spot
3. The item being moved must VANISH from its original position (show background there instead)
4. Total item count BEFORE edit must EQUAL total item count AFTER edit
5. Products must look IDENTICAL to reference images (same design, color, texture)
6. Output the ENTIRE room, same dimensions, same perspective

EXAMPLE:
- "Move the bench to the right" means:
  - Find the bench in the image
  - REMOVE it from its current position (show floor/background where it was)
  - Place the SAME bench (not a copy) at a position to the right
  - Result: Still only 1 bench, now on the right side

QUALITY: Maximum resolution {width}x{height}, photorealistic, natural lighting."""

        # Initialize Gemini client
        client = genai.Client(api_key=settings.google_ai_api_key)

        def _run_edit():
            """Run the edit with Gemini"""
            # Build contents list with room image and product reference images
            contents = [
                edit_prompt,
                "Current room image to edit:",
                input_image,
            ]

            # Add product reference images
            if product_images:
                contents.append("\n\nPRODUCT REFERENCE IMAGES (products must look EXACTLY like these):")
                for name, img in product_images:
                    contents.append(f"\n{name}:")
                    contents.append(img)

            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    temperature=0.4,
                ),
            )

            result_image = None
            parts = None

            if hasattr(response, "parts") and response.parts:
                parts = response.parts
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    parts = candidate.content.parts

            if parts:
                for part in parts:
                    if hasattr(part, "inline_data") and part.inline_data is not None:
                        img_data = part.inline_data.data
                        if isinstance(img_data, bytes):
                            first_hex = img_data[:4].hex()
                            if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                result_image = Image.open(io.BytesIO(img_data))
                            else:
                                decoded = base64.b64decode(img_data)
                                result_image = Image.open(io.BytesIO(decoded))
                        logger.info(f"[{session_id}] Gemini edit successful")

            return result_image

        # Run with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(loop.run_in_executor(None, _run_edit), timeout=90)

        if result:
            # Resize to match original if needed
            if result.size != (width, height):
                logger.info(f"[{session_id}] Resizing result from {result.size} to {width}x{height}")
                result = result.resize((width, height), Image.LANCZOS)

            # Convert to base64
            result_buffer = io.BytesIO()
            result.convert("RGB").save(result_buffer, format="PNG", optimize=False)
            result_buffer.seek(0)
            result_b64 = f"data:image/png;base64,{base64.b64encode(result_buffer.getvalue()).decode()}"

            logger.info(f"[{session_id}] Edit with instructions completed successfully")

            return {
                "image": result_b64,
                "session_id": session_id,
                "status": "success",
                "dimensions": {"width": width, "height": height},
            }

        raise ValueError("Gemini failed to generate edited image")

    except Exception as e:
        logger.error(f"[{session_id}] Error in edit-with-instructions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply edit instructions: {str(e)}")
