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
from services.api_usage_service import log_gemini_usage
from services.chatgpt_service import chatgpt_service
from services.google_ai_service import generate_workflow_id, google_ai_service
from services.ml_recommendation_model import ml_recommendation_model
from services.recommendation_engine import RecommendationRequest, recommendation_engine
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from core.database import get_db
from database.models import CuratedLook, FloorTile, Product, Project, WallTexture, WallTextureVariant

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
        room_analysis = await google_ai_service.analyze_room_image(image_data, session_id=session_id)

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
async def upload_room_image(
    file: UploadFile = File(...),
    curated_look_id: Optional[int] = None,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload room image and perform combined room analysis.

    This endpoint now performs room analysis during upload (not during visualization),
    saving 4-13 seconds per subsequent visualization by caching the analysis.

    Args:
        file: The room image file
        curated_look_id: If provided, saves room_analysis to CuratedLook table (admin curation flow)
        project_id: If provided, saves room_analysis to Project table (design page flow)
        db: Database session

    Returns:
        image_data: Base64 encoded image data
        room_analysis: Cached room analysis (camera view, dimensions, existing furniture, etc.)
    """
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Read and encode image
        contents = await file.read()
        encoded_image = base64.b64encode(contents).decode()

        # Perform combined room analysis (room type, dimensions, camera view, AND furniture detection)
        # This is done ONCE during upload instead of on every visualization
        logger.info(
            f"[upload-room-image] Starting combined room analysis (curated_look_id={curated_look_id}, project_id={project_id})"
        )
        room_analysis = await google_ai_service.analyze_room_with_furniture(encoded_image)
        room_analysis_dict = room_analysis.to_dict()
        logger.info(
            f"[upload-room-image] Room analysis complete: {room_analysis.room_type}, {len(room_analysis.existing_furniture)} furniture items detected"
        )

        # Save room analysis to CuratedLook (admin curation flow)
        if curated_look_id:
            logger.info(f"[upload-room-image] Saving room analysis to curated_look {curated_look_id}")
            await db.execute(
                update(CuratedLook).where(CuratedLook.id == curated_look_id).values(room_analysis=room_analysis_dict)
            )
            await db.commit()

        # Save room analysis to Project (design page flow)
        if project_id:
            logger.info(f"[upload-room-image] Saving room analysis to project {project_id}")
            await db.execute(update(Project).where(Project.id == project_id).values(room_analysis=room_analysis_dict))
            await db.commit()

        return {
            "image_data": f"data:{file.content_type};base64,{encoded_image}",
            "filename": file.filename,
            "size": len(contents),
            "content_type": file.content_type,
            "upload_timestamp": datetime.utcnow().isoformat(),
            "room_analysis": room_analysis_dict,
        }

    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")


@router.post("/sessions/{session_id}/extract-layers")
async def extract_furniture_layers(session_id: str, request: ExtractLayersRequest, db: AsyncSession = Depends(get_db)):
    """
    Extract all objects as draggable layers for Magic Grab editing.

    NOTE: This endpoint is DISABLED as SAM segmentation is not currently used.
    The Magic Grab feature has been deprecated in favor of Gemini-based editing.

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
    # SAM-based Magic Grab is disabled - return 501 Not Implemented
    raise HTTPException(status_code=501, detail="Magic Grab (SAM segmentation) is disabled. Use Gemini-based editing instead.")

    # Original implementation (disabled):
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

    NOTE: This endpoint is DISABLED as SAM segmentation is not currently used.
    The Magic Grab feature has been deprecated in favor of Gemini-based editing.

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
    # SAM-based layer compositing is disabled - return 501 Not Implemented
    raise HTTPException(status_code=501, detail="Layer compositing (SAM-based) is disabled. Use Gemini-based editing instead.")

    # Original implementation (disabled):
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


class ChangeWallColorRequest(BaseModel):
    """Request to change wall color in visualization"""

    room_image: str  # Base64 encoded current visualization image
    color_name: str  # Asian Paints color name (e.g., "Air Breeze")
    color_code: str  # Asian Paints code (e.g., "L134")
    color_hex: str  # Hex color value (e.g., "#F5F5F0")
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ChangeWallColorResponse(BaseModel):
    """Response from wall color change"""

    success: bool
    rendered_image: Optional[str] = None  # Base64 encoded result image
    error_message: Optional[str] = None
    processing_time: float = 0.0


@router.post("/change-wall-color", response_model=ChangeWallColorResponse)
async def change_wall_color(request: ChangeWallColorRequest):
    """
    Change wall color in a room visualization using AI-powered inpainting.

    This endpoint takes a room visualization image and repaints the walls
    with the specified Asian Paints color while preserving all furniture
    and other room elements.

    Note: Color matching is approximate (~80% match). The UI should display
    the exact hex value for reference alongside the rendered result.
    """
    import time

    start_time = time.time()

    try:
        logger.info(f"[WallColor API] Changing wall color to {request.color_name} ({request.color_hex})")

        # Strip data URL prefix if present
        room_image = request.room_image
        if room_image.startswith("data:"):
            room_image = room_image.split(",", 1)[1]

        # Call the Google AI service to change wall color
        result_image = await google_ai_service.change_wall_color(
            room_image=room_image,
            color_name=request.color_name,
            color_hex=request.color_hex,
            user_id=request.user_id,
            session_id=request.session_id,
        )

        processing_time = time.time() - start_time

        if result_image:
            logger.info(f"[WallColor API] Successfully changed wall color in {processing_time:.2f}s")
            return ChangeWallColorResponse(
                success=True,
                rendered_image=result_image,
                processing_time=processing_time,
            )
        else:
            logger.error("[WallColor API] Failed to generate wall color change")
            return ChangeWallColorResponse(
                success=False,
                error_message="Failed to generate wall color visualization. Please try again.",
                processing_time=processing_time,
            )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"[WallColor API] Error: {e}", exc_info=True)
        return ChangeWallColorResponse(
            success=False,
            error_message=f"Error changing wall color: {str(e)}",
            processing_time=processing_time,
        )


class ChangeWallTextureRequest(BaseModel):
    """Request to change wall texture in visualization"""

    room_image: str  # Base64 encoded current visualization image
    texture_variant_id: int  # ID of the texture variant to apply
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ChangeWallTextureResponse(BaseModel):
    """Response from wall texture change"""

    success: bool
    rendered_image: Optional[str] = None  # Base64 encoded result image
    error_message: Optional[str] = None
    processing_time: float = 0.0
    texture_name: Optional[str] = None
    texture_type: Optional[str] = None


@router.post("/change-wall-texture", response_model=ChangeWallTextureResponse)
async def change_wall_texture(request: ChangeWallTextureRequest, db: AsyncSession = Depends(get_db)):
    """
    Change wall texture in a room visualization using AI-powered inpainting.

    This endpoint takes a room visualization image and applies a textured wall finish
    by passing both the room image and the texture swatch to the AI model.
    The AI uses the texture swatch as a reference to accurately apply the pattern
    to all visible walls while preserving furniture and other room elements.

    Args:
        request: Contains room_image (base64) and texture_variant_id

    Returns:
        ChangeWallTextureResponse with rendered image or error
    """
    import time

    start_time = time.time()

    try:
        # Import models here to avoid circular imports
        from database.models import WallTexture, WallTextureVariant

        logger.info(f"[WallTexture API] Changing wall texture using variant ID {request.texture_variant_id}")

        # Fetch texture variant from database
        query = (
            select(WallTextureVariant)
            .options(selectinload(WallTextureVariant.texture))
            .where(WallTextureVariant.id == request.texture_variant_id)
        )
        result = await db.execute(query)
        variant = result.scalar_one_or_none()

        if not variant:
            logger.error(f"[WallTexture API] Texture variant {request.texture_variant_id} not found")
            return ChangeWallTextureResponse(
                success=False,
                error_message=f"Texture variant with ID {request.texture_variant_id} not found",
                processing_time=time.time() - start_time,
            )

        texture = variant.texture
        texture_name = texture.name
        texture_type = texture.texture_type.value if texture.texture_type else "other"

        logger.info(f"[WallTexture API] Applying texture: {texture_name} ({texture_type})")

        # Strip data URL prefix if present
        room_image = request.room_image
        if room_image.startswith("data:"):
            room_image = room_image.split(",", 1)[1]

        # Get texture image from variant — prefer swatch (pure texture pattern) over room shot
        texture_image = variant.swatch_data or variant.image_data
        if not texture_image:
            logger.error(f"[WallTexture API] Texture variant {variant.id} has no image data")
            return ChangeWallTextureResponse(
                success=False,
                error_message=f"Texture variant {variant.id} has no image data",
                processing_time=time.time() - start_time,
                texture_name=texture_name,
                texture_type=texture_type,
            )
        if texture_image.startswith("data:"):
            texture_image = texture_image.split(",", 1)[1]

        # Call the Google AI service to change wall texture
        result_image = await google_ai_service.change_wall_texture(
            room_image=room_image,
            texture_image=texture_image,
            texture_name=texture_name,
            texture_type=texture_type,
            user_id=request.user_id,
            session_id=request.session_id,
        )

        processing_time = time.time() - start_time

        if result_image:
            logger.info(f"[WallTexture API] Successfully applied texture in {processing_time:.2f}s")
            return ChangeWallTextureResponse(
                success=True,
                rendered_image=result_image,
                processing_time=processing_time,
                texture_name=texture_name,
                texture_type=texture_type,
            )
        else:
            logger.error("[WallTexture API] Failed to generate texture visualization")
            return ChangeWallTextureResponse(
                success=False,
                error_message="Failed to generate texture visualization. Please try again.",
                processing_time=processing_time,
                texture_name=texture_name,
                texture_type=texture_type,
            )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"[WallTexture API] Error: {e}", exc_info=True)
        return ChangeWallTextureResponse(
            success=False,
            error_message=f"Error applying wall texture: {str(e)}",
            processing_time=processing_time,
        )


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

    NOTE: This endpoint is DISABLED as SAM segmentation is not currently used.
    Click-to-select has been deprecated in favor of Gemini-based editing.

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
    # SAM-based click-to-select is disabled - return 501 Not Implemented
    raise HTTPException(
        status_code=501, detail="Click-to-select (SAM segmentation) is disabled. Use Gemini-based editing instead."
    )

    # Original implementation (disabled):
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
            log_gemini_usage(response, "identify_object", "gemini-2.0-flash-exp", session_id=session_id)
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
                        log_gemini_usage(response, "match_product", "gemini-2.0-flash-exp", session_id=session_id)
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
                    log_gemini_usage(response, "inpaint_object_removal", "gemini-3-pro-image-preview", session_id=session_id)

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
            log_gemini_usage(response, "fallback_inpaint", "gemini-3-pro-image-preview", session_id=session_id)
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

    NOTE: This endpoint is DISABLED as SAM segmentation is not currently used.
    Multi-point selection has been deprecated in favor of Gemini-based editing.

    Use this when user wants to select multiple items as one unit,
    e.g., sofa + all pillows, or table + all objects on it.

    All points with the same label are merged into a single mask.
    """
    # SAM-based multi-point selection is disabled - return 501 Not Implemented
    raise HTTPException(
        status_code=501, detail="Multi-point selection (SAM segmentation) is disabled. Use Gemini-based editing instead."
    )

    # Original implementation (disabled):
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
            log_gemini_usage(response, "replace_product_harmonize", "gemini-3-pro-image-preview", session_id=session_id)

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
            log_gemini_usage(response, "visualize_curated_look_inpaint", "gemini-2.0-flash-exp")

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

        # Log image hash to debug consecutive edit issues
        import hashlib

        image_hash = hashlib.md5(image_bytes).hexdigest()[:12]
        logger.info(f"[{session_id}] Input image size: {width}x{height}, hash: {image_hash}")

        # Fetch product reference images
        product_images = []
        product_list_text = ""
        total_item_count = 0
        if request.products:
            logger.info(f"[{session_id}] Fetching {len(request.products)} product reference images...")
            product_lines = []
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                for product in request.products:
                    qty = product.quantity or 1
                    total_item_count += qty
                    product_lines.append(f"- {product.name}: EXACTLY {qty} {'items' if qty > 1 else 'item'}")

            product_list_text = (
                f"""

⚠️ EXACT ITEM COUNT IN SCENE: {total_item_count} total items ⚠️
PRODUCTS (your output must have EXACTLY these counts):
"""
                + "\n".join(product_lines)
                + f"""

🔢 VERIFICATION: After your edit, count the items. There must be EXACTLY {total_item_count} items total.
"""
            )

            # Now fetch images
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                for product in request.products:
                    # (image fetching continues below)
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
        edit_prompt = f"""You are an interior design image editor. Edit the room image according to the user's instructions.

INSTRUCTION: {request.instructions}
{product_list_text}

⛔⛔⛔ CRITICAL: MOVE = DELETE FROM OLD + CREATE AT NEW ⛔⛔⛔
═══════════════════════════════════════════════════════════════════════
When asked to MOVE, REPOSITION, or RELOCATE an item:

1. FIRST: ERASE/DELETE the item completely from its ORIGINAL location
   - The original spot must show the floor, wall, or background behind it
   - The item must VANISH from where it was

2. THEN: Place the SAME item at the NEW location
   - There should be EXACTLY ONE of each item after the move
   - NEVER leave a copy at the old position

🚨 DUPLICATION IS FORBIDDEN 🚨
- If you see 1 chair before the move, there must be EXACTLY 1 chair after
- If you see 2 chairs before the move, there must be EXACTLY 2 chairs after
- NEVER ADD EXTRA ITEMS - the count must MATCH before and after

WHAT MOVING MEANS:
- "Position chairs next to each other" → Take chairs from their current spots, DELETE them there, place them side by side
- "Move the table to the left" → REMOVE table from original spot, show empty space, place table on the left
- Each moved item must DISAPPEAR from its original location
═══════════════════════════════════════════════════════════════════════

TYPES OF EDITS:

1. REPOSITIONING (move, relocate, position):
   - STEP 1: Completely REMOVE the item from its current position (show floor/wall behind)
   - STEP 2: Place the item at the new position
   - The old position must be EMPTY after the move
   - COUNT CHECK: Same number of items before and after

2. APPEARANCE CORRECTION (fix shape, color, size):
   - If user says a product looks wrong (wrong shape, color, etc.), FIX it
   - Use the REFERENCE IMAGES provided to see the correct appearance
   - Products must look IDENTICAL to their reference images

ABSOLUTE RULES:
1. ⛔ NEVER ADD NEW ITEMS - item count must stay EXACTLY the same
2. ⛔ NEVER DUPLICATE items when moving - remove from old position FIRST
3. ⛔ After moving, the OLD position must be EMPTY (show floor/wall)
4. Products must look IDENTICAL to reference images
5. Output the ENTIRE room, same dimensions, same perspective

🚫🚫🚫 WALL & FLOOR COLOR PRESERVATION - ABSOLUTE REQUIREMENT 🚫🚫🚫
⛔ DO NOT CHANGE THE WALL COLOR - walls must remain EXACTLY the same color as input
⛔ DO NOT CHANGE THE FLOOR COLOR - flooring must remain EXACTLY the same color/material as input
⛔ DO NOT add paint, wallpaper, or any wall treatment that wasn't there
⛔ DO NOT change flooring material, color, or texture
- If walls are white → output walls MUST be white
- If walls are grey → output walls MUST be grey
- If floor is wooden → output floor MUST be the SAME wooden color
- The room's color scheme is FIXED - you are ONLY repositioning furniture

FAILURE CONDITIONS (you WILL fail if you do these):
- Leaving a copy of a moved item at its original position
- Having more items after the edit than before
- Not clearing the original position when moving
- Changing the wall color or floor color

🚨🚨🚨 CRITICAL OUTPUT REQUIREMENTS 🚨🚨🚨
- Output image MUST be EXACTLY {width}x{height} pixels (width={width}, height={height})
- DO NOT swap width and height - orientation must match input EXACTLY
- The aspect ratio MUST remain identical to the input image
- Generate at MAXIMUM quality, photorealistic, with natural lighting
- DO NOT crop, rotate, or change the image dimensions in ANY way"""

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
            log_gemini_usage(response, "edit_with_instructions", "gemini-3-pro-image-preview", session_id=session_id)

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

        # Run with timeout and retry logic
        loop = asyncio.get_event_loop()
        max_retries = 3
        result = None

        for attempt in range(max_retries):
            try:
                logger.info(f"[{session_id}] Edit attempt {attempt + 1}/{max_retries}")
                result = await asyncio.wait_for(loop.run_in_executor(None, _run_edit), timeout=90)
                if result:
                    break
                else:
                    logger.warning(f"[{session_id}] Attempt {attempt + 1} returned no image, retrying...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)  # Brief delay before retry
            except asyncio.TimeoutError:
                logger.warning(f"[{session_id}] Attempt {attempt + 1} timed out after 90s")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
            except Exception as retry_error:
                logger.warning(f"[{session_id}] Attempt {attempt + 1} failed: {retry_error}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)

        if result:
            # Handle dimension issues - Gemini sometimes returns different dimensions
            result_w, result_h = result.size
            if result.size != (width, height):
                logger.warning(f"[{session_id}] Gemini returned {result_w}x{result_h} but input was {width}x{height}")
                # Resize with high quality interpolation to match original
                result = result.resize((width, height), Image.LANCZOS)
                logger.info(f"[{session_id}] Resized to {width}x{height}")

            # Convert to base64
            result_buffer = io.BytesIO()
            result.convert("RGB").save(result_buffer, format="PNG", optimize=False)
            result_buffer.seek(0)
            result_bytes = result_buffer.getvalue()
            result_b64 = f"data:image/png;base64,{base64.b64encode(result_bytes).decode()}"

            # Log output hash to debug consecutive edit issues
            output_hash = hashlib.md5(result_bytes).hexdigest()[:12]
            logger.info(f"[{session_id}] Edit with instructions completed successfully, output hash: {output_hash}")

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


@router.get("/api-usage")
async def get_api_usage(hours: int = 24, db: AsyncSession = Depends(get_db)):
    """
    Get API usage statistics from database.

    Args:
        hours: Number of hours to look back (default 24 for today)

    Returns:
        Usage summary with token counts by operation and provider
    """
    from datetime import timedelta

    from sqlalchemy import func, select

    from database.models import ApiUsage

    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Get total stats
        total_query = select(
            func.count(ApiUsage.id).label("total_calls"),
            func.sum(ApiUsage.total_tokens).label("total_tokens"),
        ).where(ApiUsage.timestamp >= cutoff)

        total_result = await db.execute(total_query)
        total_row = total_result.fetchone()

        # Get breakdown by operation
        by_operation_query = (
            select(
                ApiUsage.operation,
                func.count(ApiUsage.id).label("calls"),
                func.sum(ApiUsage.total_tokens).label("tokens"),
            )
            .where(ApiUsage.timestamp >= cutoff)
            .group_by(ApiUsage.operation)
        )

        op_result = await db.execute(by_operation_query)
        by_operation = [{"operation": r.operation, "calls": r.calls, "tokens": r.tokens or 0} for r in op_result.fetchall()]

        # Get breakdown by provider
        by_provider_query = (
            select(
                ApiUsage.provider,
                func.count(ApiUsage.id).label("calls"),
                func.sum(ApiUsage.total_tokens).label("tokens"),
            )
            .where(ApiUsage.timestamp >= cutoff)
            .group_by(ApiUsage.provider)
        )

        provider_result = await db.execute(by_provider_query)
        by_provider = [{"provider": r.provider, "calls": r.calls, "tokens": r.tokens or 0} for r in provider_result.fetchall()]

        # Get breakdown by model
        by_model_query = (
            select(
                ApiUsage.model,
                func.count(ApiUsage.id).label("calls"),
                func.sum(ApiUsage.total_tokens).label("tokens"),
            )
            .where(ApiUsage.timestamp >= cutoff)
            .group_by(ApiUsage.model)
            .order_by(func.count(ApiUsage.id).desc())
        )
        model_result = await db.execute(by_model_query)
        by_model = [{"model": r.model, "calls": r.calls, "tokens": r.tokens or 0} for r in model_result.fetchall()]

        # Get detailed log of individual calls (most recent 200)
        # Resolve user via multiple paths:
        # 1. ApiUsage.user_id -> User (direct)
        # 2. ApiUsage.session_id -> ChatSession.user_id -> User
        # 3. ApiUsage.session_id -> HomeStylingSession.user_id -> User
        # 4. ApiUsage.session_id -> Project.id -> Project.user_id -> User
        from sqlalchemy.orm import aliased

        from database.models import ChatSession, HomeStylingSession, User

        DirectUser = aliased(User, name="direct_user")
        ChatSessionUser = aliased(User, name="chat_session_user")
        HSSessionUser = aliased(User, name="hs_session_user")
        ProjectUser = aliased(User, name="project_user")

        detail_query = (
            select(
                ApiUsage.timestamp,
                ApiUsage.provider,
                ApiUsage.model,
                ApiUsage.operation,
                ApiUsage.prompt_tokens,
                ApiUsage.completion_tokens,
                ApiUsage.total_tokens,
                ApiUsage.estimated_cost,
                ApiUsage.session_id,
                func.coalesce(DirectUser.email, ChatSessionUser.email, HSSessionUser.email, ProjectUser.email).label(
                    "user_email"
                ),
            )
            .outerjoin(DirectUser, ApiUsage.user_id == DirectUser.id)
            .outerjoin(ChatSession, ApiUsage.session_id == ChatSession.id)
            .outerjoin(ChatSessionUser, ChatSession.user_id == ChatSessionUser.id)
            .outerjoin(HomeStylingSession, ApiUsage.session_id == HomeStylingSession.id)
            .outerjoin(HSSessionUser, HomeStylingSession.user_id == HSSessionUser.id)
            .outerjoin(Project, ApiUsage.session_id == Project.id)
            .outerjoin(ProjectUser, Project.user_id == ProjectUser.id)
            .where(ApiUsage.timestamp >= cutoff)
            .order_by(ApiUsage.timestamp.desc())
            .limit(200)
        )
        detail_result = await db.execute(detail_query)
        detailed_log = [
            {
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "user": r.user_email or "anonymous",
                "provider": r.provider,
                "model": r.model,
                "operation": r.operation,
                "prompt_tokens": r.prompt_tokens or 0,
                "completion_tokens": r.completion_tokens or 0,
                "total_tokens": r.total_tokens or 0,
                "estimated_cost": r.estimated_cost or 0,
                "session_id": r.session_id,
            }
            for r in detail_result.fetchall()
        ]

        return {
            "status": "success",
            "period_hours": hours,
            "usage": {
                "total_api_calls": total_row.total_calls or 0,
                "total_tokens": total_row.total_tokens or 0,
                "by_operation": sorted(by_operation, key=lambda x: x["calls"], reverse=True),
                "by_provider": by_provider,
                "by_model": by_model,
                "detailed_log": detailed_log,
            },
        }
    except Exception as e:
        logger.error(f"Error getting API usage: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get API usage: {str(e)}")


# =============================================================================
# Floor Tile Visualization
# =============================================================================

from schemas.floor_tiles import ChangeFloorTileRequest, ChangeFloorTileResponse


@router.post("/change-floor-tile", response_model=ChangeFloorTileResponse)
async def change_floor_tile(request: ChangeFloorTileRequest, db: AsyncSession = Depends(get_db)):
    """
    Change floor tile in a room visualization using AI-powered rendering.

    Takes a room visualization image and applies a floor tile pattern
    by passing both the room image and the tile swatch to Gemini.
    The AI uses the tile swatch as a reference to accurately apply
    the tile pattern to all visible floor surfaces.
    """
    import time

    start_time = time.time()

    try:
        logger.info(f"[FloorTile API] Changing floor tile using tile ID {request.tile_id}")

        # Fetch tile from database
        query = select(FloorTile).where(FloorTile.id == request.tile_id)
        result = await db.execute(query)
        tile = result.scalar_one_or_none()

        if not tile:
            logger.error(f"[FloorTile API] Tile {request.tile_id} not found")
            return ChangeFloorTileResponse(
                success=False,
                error_message=f"Floor tile with ID {request.tile_id} not found",
                processing_time=time.time() - start_time,
            )

        tile_name = tile.name
        tile_size = tile.size
        tile_finish = tile.finish or "matte"
        tile_look = tile.look

        logger.info(f"[FloorTile API] Applying tile: {tile_name} ({tile_size}, {tile_finish}, look={tile_look})")

        # Strip data URL prefix if present
        room_image = request.room_image
        if room_image.startswith("data:"):
            room_image = room_image.split(",", 1)[1]

        # Get tile swatch image — prefer swatch_data, fall back to image_data
        swatch_image = tile.swatch_data or tile.image_data
        if not swatch_image:
            logger.error(f"[FloorTile API] Tile {tile.id} has no swatch or image data")
            return ChangeFloorTileResponse(
                success=False,
                error_message=f"Floor tile {tile.id} has no image data",
                processing_time=time.time() - start_time,
                tile_name=tile_name,
                tile_size=tile_size,
            )
        if swatch_image.startswith("data:"):
            swatch_image = swatch_image.split(",", 1)[1]

        # Build size description for prompt
        size_desc = tile_size
        if tile.size_width_mm and tile.size_height_mm:
            size_desc = f"{tile.size_width_mm}x{tile.size_height_mm} mm"

        # Call the Google AI service
        result_image = await google_ai_service.change_floor_tile(
            room_image=room_image,
            swatch_image=swatch_image,
            tile_name=tile_name,
            tile_size=size_desc,
            tile_finish=tile_finish,
            tile_look=tile_look,
            tile_width_mm=tile.size_width_mm,
            tile_height_mm=tile.size_height_mm,
            user_id=request.user_id,
            session_id=request.session_id,
        )

        processing_time = time.time() - start_time

        if result_image:
            logger.info(f"[FloorTile API] Successfully applied tile in {processing_time:.2f}s")
            return ChangeFloorTileResponse(
                success=True,
                rendered_image=result_image,
                processing_time=processing_time,
                tile_name=tile_name,
                tile_size=tile_size,
            )
        else:
            logger.error("[FloorTile API] Failed to generate floor tile visualization")
            return ChangeFloorTileResponse(
                success=False,
                error_message="Failed to generate floor tile visualization. Please try again.",
                processing_time=processing_time,
                tile_name=tile_name,
                tile_size=tile_size,
            )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"[FloorTile API] Error: {e}", exc_info=True)
        return ChangeFloorTileResponse(
            success=False,
            error_message=f"Error applying floor tile: {str(e)}",
            processing_time=processing_time,
        )


# =============================================================================
# Combined Surface Visualization (wall color/texture + floor tile in one call)
# =============================================================================


class ApplySurfacesRequest(BaseModel):
    """Request to apply multiple surface changes in a single Gemini call."""

    room_image: str
    wall_color_name: Optional[str] = None
    wall_color_code: Optional[str] = None
    wall_color_hex: Optional[str] = None
    texture_variant_id: Optional[int] = None
    tile_id: Optional[int] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ApplySurfacesResponse(BaseModel):
    success: bool
    rendered_image: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    surfaces_applied: List[str] = []


@router.post("/apply-surfaces", response_model=ApplySurfacesResponse)
async def apply_surfaces(request: ApplySurfacesRequest, db: AsyncSession = Depends(get_db)):
    """
    Apply wall color/texture and/or floor tile in a single Gemini API call.
    Used for surface-only changes (no furniture products).
    """
    import time

    start_time = time.time()
    surfaces_applied = []

    try:
        has_wall_color = bool(request.wall_color_name or request.wall_color_hex)
        has_texture = bool(request.texture_variant_id)
        has_tile = bool(request.tile_id)

        if not has_wall_color and not has_texture and not has_tile:
            return ApplySurfacesResponse(
                success=False,
                error_message="At least one surface change (wall color, texture, or tile) must be specified.",
                processing_time=time.time() - start_time,
            )

        logger.info(
            f"[ApplySurfaces] Combined surface call: wall_color={has_wall_color}, "
            f"texture_variant_id={request.texture_variant_id}, tile_id={request.tile_id}"
        )

        # Strip data URL prefix if present
        room_image = request.room_image
        if room_image.startswith("data:"):
            room_image = room_image.split(",", 1)[1]

        # Build wall color dict
        wall_color = None
        if has_wall_color and not has_texture:  # Texture overrides wall color
            wall_color = {
                "name": request.wall_color_name or "Custom",
                "code": request.wall_color_code or "",
                "hex_value": request.wall_color_hex or "",
            }
            surfaces_applied.append(f"wall_color:{request.wall_color_name}")

        # Fetch texture swatch from DB
        texture_image = None
        texture_name = None
        texture_type = None
        if has_texture:
            from database.models import WallTexture, WallTextureVariant

            variant_query = select(WallTextureVariant).where(WallTextureVariant.id == request.texture_variant_id)
            variant_result = await db.execute(variant_query)
            variant = variant_result.scalar_one_or_none()
            if variant:
                texture_image = variant.swatch_data or variant.image_data
                if texture_image and texture_image.startswith("data:"):
                    texture_image = texture_image.split(",", 1)[1]
                parent_query = select(WallTexture).where(WallTexture.id == variant.texture_id)
                parent_result = await db.execute(parent_query)
                parent = parent_result.scalar_one_or_none()
                texture_name = parent.name if parent else "texture"
                texture_type = parent.texture_type if parent else "textured"
                surfaces_applied.append(f"texture:{texture_name}")
            else:
                logger.warning(f"[ApplySurfaces] Texture variant {request.texture_variant_id} not found")

        # Fetch floor tile swatch from DB
        tile_swatch_image = None
        tile_name = None
        tile_size = None
        tile_finish = None
        tile_look = None
        tile_width_mm = None
        tile_height_mm = None
        if has_tile:
            tile_query = select(FloorTile).where(FloorTile.id == request.tile_id)
            tile_result = await db.execute(tile_query)
            tile = tile_result.scalar_one_or_none()
            if tile:
                tile_swatch_image = tile.swatch_data or tile.image_data
                if tile_swatch_image and tile_swatch_image.startswith("data:"):
                    tile_swatch_image = tile_swatch_image.split(",", 1)[1]
                tile_name = tile.name
                tile_finish = tile.finish or "standard"
                tile_look = tile.look
                tile_width_mm = tile.size_width_mm
                tile_height_mm = tile.size_height_mm
                if tile_width_mm and tile_height_mm:
                    tile_size = f"{tile_width_mm}x{tile_height_mm} mm"
                else:
                    tile_size = tile.size
                surfaces_applied.append(f"tile:{tile_name}")
            else:
                logger.warning(f"[ApplySurfaces] Floor tile {request.tile_id} not found")

        # Call the combined surface method
        result_image = await google_ai_service.apply_room_surfaces(
            room_image=room_image,
            wall_color=wall_color,
            texture_image=texture_image,
            texture_name=texture_name,
            texture_type=texture_type,
            tile_swatch_image=tile_swatch_image,
            tile_name=tile_name,
            tile_size=tile_size,
            tile_finish=tile_finish,
            tile_look=tile_look,
            tile_width_mm=tile_width_mm,
            tile_height_mm=tile_height_mm,
            user_id=request.user_id,
            session_id=request.session_id,
        )

        processing_time = time.time() - start_time

        if result_image:
            logger.info(f"[ApplySurfaces] Success in {processing_time:.2f}s, surfaces: {surfaces_applied}")
            return ApplySurfacesResponse(
                success=True,
                rendered_image=result_image,
                processing_time=processing_time,
                surfaces_applied=surfaces_applied,
            )
        else:
            logger.error("[ApplySurfaces] Failed to generate combined surface visualization")
            return ApplySurfacesResponse(
                success=False,
                error_message="Failed to apply surface changes. Please try again.",
                processing_time=processing_time,
                surfaces_applied=surfaces_applied,
            )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"[ApplySurfaces] Error: {e}", exc_info=True)
        return ApplySurfacesResponse(
            success=False,
            error_message=f"Error applying surfaces: {str(e)}",
            processing_time=processing_time,
        )
