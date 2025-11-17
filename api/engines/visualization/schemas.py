"""
Pydantic schemas for Visualization Engine
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from enum import Enum


class TransformType(str, Enum):
    """Types of transformations"""
    MOVE = "move"
    RESIZE = "resize"
    ROTATE = "rotate"
    ADD = "add"
    REMOVE = "remove"
    REPLACE = "replace"


class BoundingBox(BaseModel):
    """Bounding box for furniture in image"""
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "x1": 100,
                "y1": 150,
                "x2": 400,
                "y2": 450,
                "confidence": 0.95
            }
        }


class FurnitureObject(BaseModel):
    """Detected furniture object in room"""
    object_type: str
    bounding_box: BoundingBox
    confidence: float = Field(ge=0.0, le=1.0)
    attributes: Optional[Dict[str, Any]] = None


class RoomAnalysis(BaseModel):
    """Analysis results for a room image"""
    room_type: Optional[str] = None
    style: Optional[str] = None
    dimensions: Optional[Dict[str, float]] = None
    lighting: Optional[str] = None
    wall_color: Optional[str] = None
    floor_type: Optional[str] = None
    detected_furniture: List[FurnitureObject] = Field(default_factory=list)
    analysis_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ProductTransform(BaseModel):
    """Transformation parameters for a product"""
    position: Optional[Tuple[int, int]] = None  # (x, y) coordinates
    scale: Optional[float] = Field(default=1.0, ge=0.1, le=5.0)  # Scale factor
    rotation: Optional[float] = Field(default=0.0, ge=-180.0, le=180.0)  # Rotation in degrees


class VisualizationState(BaseModel):
    """State of a visualization (for undo/redo)"""
    rendered_image: str  # Path to rendered image
    base_image: str  # Path to original room image
    products: List[Dict[str, Any]] = Field(default_factory=list)  # Products in the scene
    transforms: Dict[str, ProductTransform] = Field(default_factory=dict)  # Product transforms
    detected_furniture: List[FurnitureObject] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class VisualizeRoomRequest(BaseModel):
    """Request to visualize a product in a room"""
    session_id: str
    room_image_path: str
    product_id: str
    product_name: str
    product_image_url: str
    placement_hint: Optional[str] = None  # "center", "left", "right", etc.
    transform: Optional[ProductTransform] = None


class TransformProductRequest(BaseModel):
    """Request to transform a product in visualization"""
    session_id: str
    product_id: str
    transform_type: TransformType
    transform: ProductTransform


class RemoveProductRequest(BaseModel):
    """Request to remove a product from visualization"""
    session_id: str
    product_id: str


class ReplaceProductRequest(BaseModel):
    """Request to replace one product with another"""
    session_id: str
    old_product_id: str
    new_product_id: str
    new_product_name: str
    new_product_image_url: str
    preserve_transform: bool = True  # Keep position/size/rotation


class VisualizationResponse(BaseModel):
    """Response from visualization operation"""
    success: bool
    rendered_image: Optional[str] = None
    message: str
    visualization_state: Optional[VisualizationState] = None
    can_undo: bool = False
    can_redo: bool = False
    processing_time: float = 0.0


class InpaintingRequest(BaseModel):
    """Request for inpainting service"""
    base_image_path: str
    product_image_url: str
    product_name: str
    target_region: Optional[BoundingBox] = None
    placement_prompt: Optional[str] = None
    furniture_context: Optional[List[FurnitureObject]] = None


class InpaintingResponse(BaseModel):
    """Response from inpainting service"""
    success: bool
    output_image_path: Optional[str] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
