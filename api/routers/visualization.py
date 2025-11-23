"""
Visualization API routes for spatial analysis and room rendering
"""
import base64
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.database import get_db
from database.models import Product
from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from schemas.chat import ChatMessageSchema
from services.chatgpt_service import chatgpt_service
from services.furniture_layer_service import get_furniture_layer_service
from services.google_ai_service import google_ai_service
from services.ml_recommendation_model import ml_recommendation_model
from services.recommendation_engine import RecommendationRequest, recommendation_engine
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Request model for furniture layer extraction"""

    visualization_image: str
    products: List[Dict[str, Any]]


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
async def extract_furniture_layers(session_id: str, request: ExtractLayersRequest):
    """
    Extract individual furniture pieces as separate layers from a visualization

    This endpoint uses AI to isolate each furniture piece on a transparent background,
    creating a Photoshop-like layer system for furniture position editing.

    Args:
        session_id: The session ID for this visualization
        request: Request body containing visualization_image and products

    Returns:
        base_layer: Clean room image (furniture removed)
        furniture_layers: List of individual furniture layers with positions
    """
    try:
        logger.info(f"[ExtractLayers] Starting layer extraction for session {session_id}")
        logger.info(f"[ExtractLayers] Extracting {len(request.products)} furniture pieces")

        # Get furniture layer service
        layer_service = get_furniture_layer_service()

        # Extract all layers
        result = await layer_service.extract_all_layers(
            visualization_image=request.visualization_image, products=request.products, session_id=session_id
        )

        if result.get("extraction_status") == "failed":
            logger.error(f"[ExtractLayers] Layer extraction failed: {result.get('error')}")
            raise HTTPException(status_code=500, detail=f"Layer extraction failed: {result.get('error', 'Unknown error')}")

        logger.info(f"[ExtractLayers] Successfully extracted {result.get('total_layers')} layers")

        return {
            "session_id": session_id,
            "base_layer": result.get("base_layer"),
            "furniture_layers": result.get("furniture_layers", []),
            "total_layers": result.get("total_layers", 0),
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "status": "success",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ExtractLayers] Error extracting layers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Layer extraction failed: {str(e)}")


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
        from database.models import FurniturePosition
        from sqlalchemy import delete

        # Delete existing positions for this session
        delete_stmt = delete(FurniturePosition).where(FurniturePosition.session_id == session_id)
        await db.execute(delete_stmt)

        # Insert new positions
        saved_positions = []
        for pos in positions:
            furniture_position = FurniturePosition(
                session_id=session_id,
                product_id=int(pos.get("productId")),
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
        from database.models import FurniturePosition
        from sqlalchemy import select

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
        from database.models import FurniturePosition
        from sqlalchemy import select, update

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
        from database.models import FurniturePosition
        from sqlalchemy import delete

        delete_stmt = delete(FurniturePosition).where(FurniturePosition.session_id == session_id)
        result = await db.execute(delete_stmt)
        await db.commit()

        return {
            "session_id": session_id,
            "positions_deleted": result.rowcount,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting furniture positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete positions: {str(e)}")
