"""
Google AI Studio service for spatial analysis, image understanding, and visualization
"""
import asyncio
import base64
import io
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def generate_workflow_id() -> str:
    """
    Generate a unique workflow ID for tracking all API calls from a single user action.

    Use this at the start of a user-initiated flow (e.g., button click) and pass it
    through all subsequent API calls to track the complete workflow.

    Returns:
        A unique workflow ID string (UUID4 format)
    """
    return str(uuid.uuid4())


import aiohttp
from google import genai
from google.genai import types
from PIL import Image, ImageEnhance, ImageOps

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RoomAnalysis:
    """Results from room analysis"""

    room_type: str
    dimensions: Dict[str, float]
    lighting_conditions: str
    color_palette: List[str]
    existing_furniture: List[Dict[str, Any]]
    architectural_features: List[str]
    style_assessment: str
    confidence_score: float
    # Scale reference fields for perspective-aware visualization
    scale_references: Dict[str, Any] = field(default_factory=dict)
    # Camera view analysis for room-aware furniture placement
    camera_view_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize RoomAnalysis to dictionary for database storage"""
        return {
            "room_type": self.room_type,
            "dimensions": self.dimensions,
            "lighting_conditions": self.lighting_conditions,
            "color_palette": self.color_palette,
            "existing_furniture": self.existing_furniture,
            "architectural_features": self.architectural_features,
            "style_assessment": self.style_assessment,
            "confidence_score": self.confidence_score,
            "scale_references": self.scale_references,
            "camera_view_analysis": self.camera_view_analysis,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoomAnalysis":
        """Deserialize RoomAnalysis from dictionary (database retrieval)"""
        return cls(
            room_type=data.get("room_type", "unknown"),
            dimensions=data.get("dimensions", {}),
            lighting_conditions=data.get("lighting_conditions", "mixed"),
            color_palette=data.get("color_palette", []),
            existing_furniture=data.get("existing_furniture", []),
            architectural_features=data.get("architectural_features", []),
            style_assessment=data.get("style_assessment", "unknown"),
            confidence_score=data.get("confidence_score", 0.0),
            scale_references=data.get("scale_references", {}),
            camera_view_analysis=data.get("camera_view_analysis", {}),
        )


@dataclass
class SpatialAnalysis:
    """Results from spatial analysis"""

    layout_type: str
    traffic_patterns: List[str]
    focal_points: List[Dict[str, Any]]
    available_spaces: List[Dict[str, Any]]
    placement_suggestions: List[Dict[str, Any]]
    scale_recommendations: Dict[str, Any]


@dataclass
class VisualizationRequest:
    """Request for room visualization"""

    base_image: str
    products_to_place: List[Dict[str, Any]]
    placement_positions: List[Dict[str, Any]]
    lighting_conditions: str
    render_quality: str
    style_consistency: bool
    user_style_description: str = ""  # User's actual text request
    exclusive_products: bool = False  # When True, ONLY show specified products, remove any existing furniture from base image
    wall_color: Optional[Dict[str, Any]] = None  # Wall color to apply: {name, code, hex_value}
    texture_image: Optional[str] = None  # Base64 swatch image for wall texture
    texture_name: Optional[str] = None
    texture_type: Optional[str] = None
    tile_swatch_image: Optional[str] = None  # Base64 swatch image for floor tile
    tile_name: Optional[str] = None
    tile_size: Optional[str] = None
    tile_finish: Optional[str] = None
    tile_width_mm: Optional[int] = None
    tile_height_mm: Optional[int] = None


@dataclass
class VisualizationResult:
    """Result from visualization generation"""

    rendered_image: str
    processing_time: float
    quality_score: float
    placement_accuracy: float
    lighting_realism: float
    confidence_score: float


@dataclass
class SpaceFitnessResult:
    """Result from space fitness validation"""

    fits: bool  # Whether the product fits in the available space
    confidence: float  # 0.0 to 1.0 confidence in the assessment
    reason: str  # Explanation for the assessment
    suggestion: Optional[str] = None  # Alternative suggestion if doesn't fit


class VisualizationPrompts:
    """Centralized prompt components for all visualization workflows."""

    SYSTEM_INTRO = """You are a professional interior styling visualizing tool. Your job is to take user inputs and produce realistic images of their styled spaces."""

    @staticmethod
    def get_system_intro() -> str:
        """System introduction used at the start of EVERY prompt."""
        return VisualizationPrompts.SYSTEM_INTRO

    @staticmethod
    def get_room_preservation_rules() -> str:
        """Room preservation rules used by ALL workflows."""
        return """
ROOM PRESERVATION RULES (MANDATORY):
1. OUTPUT DIMENSIONS: Match input exactly (pixel-for-pixel)
2. ASPECT RATIO: No cropping or letterboxing
3. CAMERA ANGLE: Same viewing angle and perspective
4. WALLS & FLOORS: Same colors, textures, materials
5. ARCHITECTURAL FEATURES: Preserve windows, doors, columns, moldings
6. LIGHTING: Match existing room lighting
7. EXISTING FURNITURE: Keep in exact same position, size, color (unless removing)
8. NO ZOOM: Show full room view
9. NO ADDITIONS: Only add explicitly requested furniture
10. PHOTOREALISM: Output must look like a real photograph
11. NO HALLUCINATED STRUCTURES: Do NOT add, extend, or assume any walls, ceilings, floors, or architectural elements that are not visible in the input image. Only use what is shown in the base image as background.
12. VISIBLE BOUNDARIES ONLY: If the image shows a partial room view (e.g., only one wall visible), do NOT generate or assume other walls or room structures beyond what is visible.
"""

    @staticmethod
    def get_placement_guidelines() -> str:
        """Product-type specific placement rules."""
        return """
PLACEMENT GUIDELINES BY PRODUCT TYPE:

SOFAS: Against wall with minimal gap (2-4 inches), centered

CHAIRS: On sides of sofa angled for conversation, 18-30 inches spacing

CENTER/COFFEE TABLE: In front of sofa, 14-18 inches from seating

OTTOMAN: In front of sofa, 14-18 inches from front edge

SIDE/END TABLE: Adjacent to sofa armrest, at arm's reach

CONSOLE TABLE: Against empty wall, behind sofa or in entryways

STORAGE/CABINETS/BOOKSHELVES: Against wall, 36+ inches clearance in front

CURTAINS: On visible windows, above frame to floor/sill

LAMPS: Table lamps on tables, floor lamps in corners

BEDS: Headboard against wall

PLANTERS: Far corners, small (less than 5-10% of image)

CUSHIONS/PILLOWS: On sofa/chair seat or backrest

THROWS: Draped over arm or folded on seat

TABLETOP DECOR: On coffee table, side table, or console

WALL ART/MIRRORS: At eye level, alongside existing art
"""

    @staticmethod
    def get_product_accuracy_rules() -> str:
        """Rules for accurate product reproduction."""
        return """
PRODUCT ACCURACY REQUIREMENTS:

CRITICAL: Products must match reference images EXACTLY

MUST DO:
- Copy exact appearance from reference image
- Match exact color, pattern, texture, material
- Preserve product proportions and dimensions
- Show product's front face towards camera
- Scale according to provided dimensions

MUST NOT:
- Generate "similar" or "inspired by" versions
- Change colors to match room
- Alter product design or style
- Show product from back or side
"""

    @staticmethod
    def format_product_with_dimensions(product: Dict[str, Any], index: int) -> str:
        """
        Format a single product with its dimensions for prompt inclusion.

        Args:
            product: Product dict with name, dimensions, furniture_type, etc.
            index: Product index (1-based)

        Returns:
            Formatted string with product details and dimensions
        """
        name = product.get("full_name") or product.get("name", "furniture item")
        furniture_type = product.get("furniture_type", "furniture")

        # Extract dimensions from product attributes
        dimensions = product.get("dimensions", {})
        width = dimensions.get("width")
        depth = dimensions.get("depth")
        height = dimensions.get("height")

        # Build dimension string
        dim_parts = []
        if width:
            dim_parts.append(f'{width}" W')
        if depth:
            dim_parts.append(f'{depth}" D')
        if height:
            dim_parts.append(f'{height}" H')

        dim_str = " x ".join(dim_parts) if dim_parts else "dimensions not specified"

        return f"""Product {index}: {name}
- Type: {furniture_type}
- Dimensions: {dim_str}
- Reference Image: Provided below"""

    @staticmethod
    def format_products_list(products: List[Dict[str, Any]]) -> str:
        """Format multiple products with their dimensions."""
        formatted = []
        for idx, product in enumerate(products, 1):
            formatted.append(VisualizationPrompts.format_product_with_dimensions(product, idx))
        return "\n\n".join(formatted)

    @staticmethod
    def get_bulk_initial_prompt(products: List[Dict[str, Any]]) -> str:
        """
        Workflow 1: Initial/bulk visualization prompt.

        Args:
            products: List of product dicts with name, dimensions, furniture_type
        """
        product_count = len(products)
        products_description = VisualizationPrompts.format_products_list(products)

        return f"""{VisualizationPrompts.get_system_intro()}

═══════════════════════════════════════════════════════════════
 TASK: INITIAL ROOM VISUALIZATION
═══════════════════════════════════════════════════════════════

You are placing {product_count} product(s) into this room for the FIRST TIME.

PRODUCTS TO PLACE (with physical dimensions for proper scaling):
{products_description}

{VisualizationPrompts.get_room_preservation_rules()}

 DIMENSION-BASED SCALING:
- Use the provided dimensions (W x D x H in inches) to scale each product correctly
- A 84" wide sofa should appear ~7 feet wide relative to room
- A 28" wide chair should appear ~2.3 feet wide
- Maintain proportional relationships between products

{VisualizationPrompts.get_placement_guidelines()}

{VisualizationPrompts.get_product_accuracy_rules()}

YOUR TASK:
1. Analyze the room layout and identify appropriate placement zones
2. Place each product according to the placement guidelines above
3. Scale products according to their PHYSICAL DIMENSIONS provided
4. Ensure all products are visible and properly proportioned
5. Maintain photorealistic quality matching room lighting
"""

    @staticmethod
    def get_incremental_add_prompt(new_products: List[Dict[str, Any]], existing_products: List[Dict[str, Any]]) -> str:
        """
        Workflow 2: Incremental addition prompt.

        Args:
            new_products: Products being added (with dimensions)
            existing_products: Products already in room (with dimensions)
        """
        new_products_description = VisualizationPrompts.format_products_list(new_products)
        existing_description = (
            VisualizationPrompts.format_products_list(existing_products) if existing_products else "No existing products"
        )

        return f"""{VisualizationPrompts.get_system_intro()}

═══════════════════════════════════════════════════════════════
 TASK: ADD PRODUCTS TO EXISTING VISUALIZATION
═══════════════════════════════════════════════════════════════

EXISTING PRODUCTS IN ROOM (DO NOT MODIFY - keep exact position/size):
{existing_description}

NEW PRODUCTS TO ADD (with physical dimensions for proper scaling):
{new_products_description}

{VisualizationPrompts.get_room_preservation_rules()}

 CRITICAL PRESERVATION:
- ALL existing products must remain in EXACT same position, size, and appearance
- You are ONLY adding the new products listed above
- Do NOT move, resize, or alter ANY existing furniture

 DIMENSION-BASED SCALING FOR NEW PRODUCTS:
- Use the provided dimensions (W x D x H in inches) to scale each new product correctly
- New products should be proportionally correct relative to existing furniture
- Example: If existing sofa is 84" wide and new chair is 28" wide, chair should be ~1/3 sofa width

{VisualizationPrompts.get_placement_guidelines()}

{VisualizationPrompts.get_product_accuracy_rules()}

YOUR TASK:
1. Keep ALL existing products exactly as they are (pixel-perfect)
2. Find appropriate empty spaces for the new products
3. Scale new products according to their PHYSICAL DIMENSIONS
4. Place new products according to placement guidelines
5. Maintain room lighting and photorealism
"""

    @staticmethod
    def get_removal_prompt(products_to_remove: List[Dict[str, Any]], remaining_products: List[Dict[str, Any]]) -> str:
        """
        Workflow 3: Product removal prompt (supports partial quantity removal).

        Args:
            products_to_remove: Products being removed (with name, quantity, dimensions)
            remaining_products: Products that should stay (with dimensions for reference)
        """
        # Format removal list with furniture type and description for better identification
        removal_lines = []
        for product in products_to_remove:
            name = product.get("full_name") or product.get("name", "furniture item")
            qty = product.get("quantity", 1)
            # Check both furniture_type and product_type (frontend uses product_type)
            furniture_type = (product.get("furniture_type") or product.get("product_type") or "").replace("_", " ")
            dims = product.get("dimensions", {})
            dim_str = ""
            if dims:
                dim_parts = []
                if dims.get("width"):
                    dim_parts.append(f'{dims["width"]}" W')
                if dims.get("depth"):
                    dim_parts.append(f'{dims["depth"]}" D')
                if dims.get("height"):
                    dim_parts.append(f'{dims["height"]}" H')
                dim_str = f" - Size: {' x '.join(dim_parts)}" if dim_parts else ""

            # Always include furniture type - use "small decorative item" for "other"
            if furniture_type and furniture_type != "other":
                type_hint = f" [TYPE: {furniture_type}]"
            else:
                type_hint = " [TYPE: small decorative item / table decor]"

            # Build visual hints from color and material attributes
            visual_hints = []
            color_val = product.get("color")
            if color_val:
                # Clean up color - it might be a stringified list like "['Red', 'Blue']"
                # Extract just the first/primary color if so
                if isinstance(color_val, str) and color_val.startswith("["):
                    try:
                        import ast

                        color_list = ast.literal_eval(color_val)
                        if color_list and len(color_list) > 0:
                            color_val = color_list[0]  # Use first color option
                    except:
                        pass  # Keep original if parsing fails
                # Only add if it's a simple color value now
                if color_val and not color_val.startswith("["):
                    visual_hints.append(f"Color: {color_val}")
            if product.get("material"):
                visual_hints.append(f"Material: {product['material']}")

            # Also include description for additional visual identification
            description = product.get("description", "")
            if description:
                # Truncate and clean up description
                desc_clean = description[:100].strip()
                if desc_clean:
                    visual_hints.append(f"Description: {desc_clean}")

            # Format visual hint string
            visual_str = ""
            if visual_hints:
                visual_str = f"\n    Visual Appearance: {' | '.join(visual_hints)}"

            if qty > 1:
                removal_lines.append(f'- "{name}"{type_hint}{dim_str} (remove {qty} copies){visual_str}')
            else:
                removal_lines.append(f'- "{name}"{type_hint}{dim_str}{visual_str}')

        removal_list = "\n".join(removal_lines)

        # Format remaining products with furniture type to help distinguish
        remaining_list = []
        for product in remaining_products:
            name = product.get("full_name") or product.get("name", "item")
            qty = product.get("quantity", 1)
            # Check both furniture_type and product_type (frontend uses different field names)
            furniture_type = (product.get("furniture_type") or product.get("product_type") or "").replace("_", " ")
            type_hint = f" [TYPE: {furniture_type}]" if furniture_type and furniture_type not in ("other", "furniture") else ""
            if qty > 1:
                remaining_list.append(f'- "{name}"{type_hint} ({qty} copies - KEEP ALL)')
            else:
                remaining_list.append(f'- "{name}"{type_hint} (KEEP - DO NOT REMOVE)')
        remaining_description = "\n".join(remaining_list) if remaining_list else "None - room should be empty after removal"

        # Count items to remove for emphasis
        num_items_to_remove = len(products_to_remove)
        num_items_to_keep = len(remaining_products)

        # Use a simplified REMOVAL-ONLY prompt - do NOT list protected items (causes duplication)
        return f"""You are an image editor performing content-aware fill. Your task is to COMPLETELY ERASE and REMOVE a piece of furniture from this room image.

*** IMPORTANT: LOOK AT THE REFERENCE IMAGE BELOW ***
A reference image of the item to remove will be provided after the room image.
FIND the furniture in the room that matches the reference image and ERASE IT COMPLETELY.

ITEM TO REMOVE:
{removal_list}

*** HOW TO FIND THE ITEM ***
1. LOOK at the reference image provided below - it shows EXACTLY what the item looks like
2. SCAN the room image for furniture matching the reference image's shape and color
3. The item is likely a chair/sofa on one side of the room - LOOK CAREFULLY for it
4. Once found, ERASE it completely and fill with floor/wall texture

*** REMOVAL INSTRUCTIONS ***
- COMPLETELY REMOVE the item - it should be GONE from the output image
- Fill the empty space with appropriate floor/wall/background texture
- DO NOT leave any trace of the removed item
- DO NOT move or change any OTHER furniture
- DO NOT duplicate any existing furniture

*** VERIFICATION ***
Before outputting, verify:
- The specified item is COMPLETELY GONE (not just faded or partially visible)
- All OTHER furniture remains EXACTLY as before
- No furniture has been duplicated
- The empty space is filled naturally with floor/wall texture

OUTPUT: The same room image with the specified item REMOVED and its space filled with background.
"""

    @staticmethod
    def get_edit_by_instruction_prompt(
        instruction: str,
        instruction_type: str,  # "placement", "brightness", "reference"
        current_products: List[Dict[str, Any]],
        reference_image_provided: bool = False,
    ) -> str:
        """
        Workflow 4: Edit by instruction prompt.

        Args:
            instruction: User's edit instruction
            instruction_type: Type of edit ("placement", "brightness", "reference")
            current_products: Products in room (with dimensions for placement changes)
            reference_image_provided: Whether a reference image is included
        """
        # Format current products with dimensions
        products_description = (
            VisualizationPrompts.format_products_list(current_products) if current_products else "No products in room"
        )

        type_specific = ""
        if instruction_type == "placement":
            type_specific = """
PLACEMENT MODIFICATION - MOVE = RELOCATE (NOT DUPLICATE):
- When instructed to MOVE a product, you must RELOCATE it (remove from old position, place in new position)
- CRITICAL: The product must ONLY appear ONCE in the output - at the NEW position
- The OLD position must show the floor/wall/background that was behind the furniture
- Use content-aware fill to restore background where the product was removed
- Use the provided DIMENSIONS to maintain correct product scale when repositioning
- Maintain proper placement rules (sofas against walls, tables on floor, etc.)
- Products being moved should keep their exact size based on dimensions

MOVE OPERATION STEPS:
1. Identify the product to move and its current position
2. ERASE the product from its current position (restore background)
3. PLACE the same product at the new position as instructed
4. Result: Product appears ONLY at new position, old position shows room background
"""
        elif instruction_type == "brightness":
            type_specific = """
 BRIGHTNESS/LIGHTING MODIFICATION:
- Adjust room brightness as instructed
- Maintain consistent lighting across all surfaces
- Keep product colors accurate (don't wash out or darken)
- Preserve shadows and highlights naturally
- Products should remain at their current dimensions/scale
"""
        elif instruction_type == "reference":
            type_specific = """
 REFERENCE IMAGE MODIFICATION:
- Use the provided reference image as style guide
- Apply similar aesthetic, color palette, or arrangement
- Maintain current product positions unless instructed otherwise
- Keep room structure intact
- Product dimensions must remain accurate
"""

        return f"""{VisualizationPrompts.get_system_intro()}

═══════════════════════════════════════════════════════════════
 TASK: MODIFY VISUALIZATION BY INSTRUCTION
═══════════════════════════════════════════════════════════════

USER INSTRUCTION:
"{instruction}"

CURRENT PRODUCTS IN ROOM (with dimensions - preserve these sizes):
{products_description}

{type_specific}

{VisualizationPrompts.get_room_preservation_rules()}

 DIMENSION PRESERVATION:
- When moving products, maintain their EXACT scale based on provided dimensions
- A 84" wide sofa must remain 84" wide after repositioning
- Product proportions relative to room must stay correct

MODIFICATION RULES:
1. Apply ONLY the requested modification
2. Keep all other aspects unchanged
3. Products not mentioned in instruction stay in place at same scale
4. Room structure (walls, floors, windows) remains fixed
5. MOVE/RELOCATE = Remove from old position + Place at new position (NOT duplicate)
6. The output must have the SAME NUMBER of each product as the input (unless adding/removing)

{VisualizationPrompts.get_product_accuracy_rules()}

{" REFERENCE IMAGE: A reference image is provided. Use it as a style guide." if reference_image_provided else ""}

YOUR TASK:
1. Understand the user's instruction
2. Apply the modification precisely
3. Preserve product dimensions when repositioning
4. Maintain photorealism and lighting consistency
"""

    @staticmethod
    def get_wall_color_change_prompt(
        color_name: str,
        color_hex: str,
        color_description: str,
    ) -> str:
        """
        Prompt for changing wall color using Gemini's native inpainting.

        Args:
            color_name: Asian Paints color name (e.g., "Air Breeze")
            color_hex: Hex color value for reference (e.g., "#F5F5F0")
            color_description: Rich description of the color for AI matching

        Returns:
            Formatted prompt for wall color visualization
        """
        return f"""{VisualizationPrompts.get_system_intro()}

═══════════════════════════════════════════════════════════════
 TASK: CHANGE WALL COLOR
═══════════════════════════════════════════════════════════════

Using the provided room image, change ONLY the wall color.

 NEW WALL COLOR:
- Name: {color_name} (Asian Paints)
- Hex Reference: {color_hex}
- Description: {color_description}

 CRITICAL INSTRUCTIONS
═══════════════════════════════════════════════════════════════

1. PAINT ALL VISIBLE WALLS with this color:
   - Apply the color uniformly across all wall surfaces
   - Maintain realistic matte/satin paint finish
   - Preserve natural shadows and lighting on walls
   - Keep natural wall texture (not perfectly flat)

2. MUST KEEP UNCHANGED (MANDATORY):
   -  ALL FURNITURE: Exact position, size, color, style - DO NOT MODIFY
   -  FLOOR: Same material, color, texture - DO NOT MODIFY
   -  CEILING: Do NOT paint the ceiling - KEEP ORIGINAL
   -  Windows, doors, and frames - KEEP ORIGINAL
   -  All decorations, art, and accessories - KEEP ORIGINAL
   -  Lighting fixtures - KEEP ORIGINAL
   -  Architectural features (moldings, columns, etc.) - KEEP ORIGINAL

3. TECHNICAL REQUIREMENTS:
   - OUTPUT DIMENSIONS: Match input exactly (pixel-for-pixel)
   - ASPECT RATIO: No cropping or letterboxing
   - CAMERA ANGLE: Same viewing angle and perspective
   - NO ZOOM: Show full room view identical to input
   - PHOTOREALISM: Output must look like a real photograph

 COLOR MATCHING GUIDELINES:
- Match the hex color {color_hex} as closely as possible
- For light colors: maintain brightness, add subtle warmth/coolness as described
- For dark colors: ensure richness without appearing muddy
- The color description "{color_description}" provides tone guidance
- Natural room lighting should affect how the paint appears realistically
  (e.g., walls in shadow may appear slightly darker/cooler)

 VERIFICATION CHECKLIST:
Before outputting, verify:
 ALL walls are painted in the new color
 ALL furniture remains exactly as in the input
 Floor and ceiling are unchanged
 Image dimensions match input exactly
 Camera angle and perspective unchanged
 Lighting is realistic for painted walls

OUTPUT: One photorealistic image showing THE ENTIRE ROOM with walls painted in {color_name} ({color_hex}).
The room structure, furniture, and camera angle MUST be identical to the input image.
"""

    @staticmethod
    def get_wall_texture_change_prompt(
        texture_name: str,
        texture_type: str,
    ) -> str:
        """
        Prompt for applying texture to walls using Gemini.

        IMPORTANT: This prompt is used with TWO images:
        1. The room image (to modify)
        2. The texture swatch image (pattern reference)

        Args:
            texture_name: Name of the texture (e.g., "Basket", "Bandhej")
            texture_type: Type of texture finish (e.g., "marble", "velvet")

        Returns:
            Formatted prompt for wall texture visualization
        """
        return f"""{VisualizationPrompts.get_system_intro()}

═══════════════════════════════════════════════════════════════
 TASK: APPLY WALL TEXTURE
═══════════════════════════════════════════════════════════════

You are given TWO images:
1. FIRST IMAGE: A room photograph
2. SECOND IMAGE: A small texture swatch — use it ONLY as a material/color reference

TEXTURE INFO:
- Name: {texture_name}
- Type: {texture_type} finish

 CRITICAL INSTRUCTIONS
═══════════════════════════════════════════════════════════════

1. USE THE SWATCH AS A MATERIAL REFERENCE ONLY — DO NOT COPY-PASTE IT:
   - The second image is a SMALL SAMPLE showing the material's color, grain, and feel
   - DO NOT tile, repeat, stamp, or copy-paste the swatch image onto the wall
   - DO NOT create visible seams, edges, joints, grid lines, or repeating patterns on the wall
   - Instead, imagine the wall was professionally finished with {texture_name} as ONE continuous hand-applied coat
   - Extract ONLY the color palette, material feel, and surface character from the swatch
   - Then PAINT the wall freehand using those colors and that character — as if an artist rendered it fresh
   - The result should look like a real wall finish, NOT like a digital pattern was pasted on
   - Vary the tones and details organically across the wall (like real plaster or paint would look)

2. ABSOLUTELY NO TILING, REPETITION, OR SEAMS:
   - There must be ZERO visible lines, boundaries, repeating sections, or grid patterns on the wall
   - The wall must look like ONE continuous textured surface — never like tiles or wallpaper panels
   - DO NOT repeat any section of the swatch — every part of the wall should look unique
   - Think of it as venetian plaster or a hand-applied wall finish, NOT as wallpaper or tiles
   - If you see yourself creating a repeating pattern, STOP — the wall must have organic, non-repeating variation

3. APPLY TEXTURE TO THE PRIMARY WALL ONLY:
   - Apply the texture ONLY to the MAIN wall facing the camera (the largest wall in the image)
   - DO NOT apply texture to side walls, adjacent walls, return walls, or any other wall surface
   - Side walls and secondary walls must remain their ORIGINAL color/finish — do NOT change them
   - DO NOT add any new walls, partitions, or architectural elements
   - DO NOT add, remove, or modify any furniture, objects, or decorations
   - Maintain realistic perspective (texture should follow wall angles)
   - Preserve natural shadows and lighting ON the texture

4. MUST KEEP UNCHANGED (MANDATORY):
   - ALL FURNITURE: Exact position, size, color, style - DO NOT MODIFY
   - FLOOR: Same material, color, texture - DO NOT MODIFY
   - CEILING: Do NOT texture the ceiling - KEEP ORIGINAL
   - Windows, doors, and frames - KEEP ORIGINAL
   - All decorations, art, and accessories - KEEP ORIGINAL
   - Lighting fixtures - KEEP ORIGINAL
   - Architectural features (moldings, columns, etc.) - KEEP ORIGINAL

5. TECHNICAL REQUIREMENTS:
   - OUTPUT DIMENSIONS: Match FIRST IMAGE exactly (pixel-for-pixel)
   - ASPECT RATIO: No cropping or letterboxing
   - CAMERA ANGLE: Same viewing angle and perspective
   - NO ZOOM: Show full room view identical to input
   - PHOTOREALISM: Output must look like a real photograph

 TEXTURE RENDERING GUIDELINES:
- Seamless: The primary wall must be ONE continuous surface — no tiles, panels, or repeated sections
- Organic variation: Subtly vary the texture across the wall (natural, not mechanical) — every area should look unique
- Lighting: Room lighting should realistically affect how the texture appears
  (e.g., areas in shadow may show less texture detail, highlights on raised areas)
- Depth: {texture_type} textures should show realistic 3D depth and surface relief
- Scale: The texture grain should look natural for a real wall (not miniaturized or enlarged)

 VERIFICATION CHECKLIST:
Before outputting, verify:
 ONLY the primary wall (main wall facing camera) has the new texture — side/adjacent walls are UNCHANGED
 The textured wall shows a SEAMLESS, CONTINUOUS finish — no visible seams, tiles, grids, or repeated sections
 Texture color and character match the swatch reference
 ALL furniture remains exactly as in the input
 Floor and ceiling are unchanged
 Image dimensions match input exactly
 Camera angle and perspective unchanged
 Lighting is realistic on the textured wall

OUTPUT: One photorealistic image showing THE ENTIRE ROOM with ONLY the primary wall finished in {texture_name}.
Side walls and adjacent walls must keep their ORIGINAL appearance.
The primary wall must appear as ONE SEAMLESS continuous textured surface — no tiling, no seams, no repetition.
The room structure, furniture, and camera angle MUST be identical to the FIRST input image.
"""

    @staticmethod
    def get_floor_tile_change_prompt(
        tile_name: str,
        tile_size: str,
        tile_finish: str,
        tile_width_mm: int = None,
        tile_height_mm: int = None,
    ) -> str:
        """
        Prompt for applying floor tile to floor surfaces using Gemini.

        Reuses shared system intro and room preservation rules.
        IMPORTANT: This prompt is used with TWO images:
        1. The room image (to modify)
        2. The tile swatch image (pattern reference)
        """
        # Build explicit dimension description when available
        if tile_width_mm and tile_height_mm:
            size_detail = (
                f"- Dimensions: {tile_width_mm} mm wide × {tile_height_mm} mm tall "
                f"({tile_width_mm / 10:.0f} cm × {tile_height_mm / 10:.0f} cm)"
            )
        else:
            size_detail = f"- Size: {tile_size}"

        return f"""{VisualizationPrompts.get_system_intro()}

═══════════════════════════════════════════════════════════════
 TASK: APPLY FLOOR TILE
═══════════════════════════════════════════════════════════════

You are given TWO images:
1. FIRST IMAGE: A room photograph
2. SECOND IMAGE: A tile swatch/pattern to apply to the FLOOR

TILE INFO:
- Name: {tile_name}
{size_detail}
- Finish: {tile_finish}

{VisualizationPrompts.get_room_preservation_rules()}

 FLOOR-TILE-SPECIFIC INSTRUCTIONS:

1. MATCH THE TILE PATTERN EXACTLY from the SECOND IMAGE:
   - Study the pattern, colors, veining, and details in the tile swatch
   - Reproduce this EXACT pattern on ALL visible floor surfaces

2. TILE SIZING — THIS IS CRITICAL:
   - Each tile is {tile_size} in real-world dimensions
   - A standard interior door is ~2000 mm tall — use that as a scale reference
   - Replicate tiles at the correct count per meter of floor
   - Tiles closer to the camera appear larger (perspective foreshortening)
   - Tiles further away appear smaller toward the vanishing point

3. APPLY TILE TO FLOOR SURFACES ONLY:
   - Cover ALL visible floor areas with the tile pattern
   - DO NOT apply tile to walls, ceiling, or furniture surfaces
   - Add subtle grout lines between tiles (thin, natural-looking)
   - Maintain realistic perspective (tile grid follows floor plane)
   - Apply appropriate reflectivity for {tile_finish} finish type
   - Furniture legs should rest naturally on the tiled surface

4. TECHNICAL REQUIREMENTS:
   - OUTPUT DIMENSIONS: Match FIRST IMAGE exactly (pixel-for-pixel)
   - ASPECT RATIO: No cropping or letterboxing
   - CAMERA ANGLE: Same viewing angle and perspective
   - NO ZOOM: Show full room view identical to input
   - PHOTOREALISM: Output must look like a real photograph

 TILE APPLICATION GUIDELINES:
- Grout: Thin, natural grout lines forming a regular grid
- Reflectivity: {tile_finish} finish — adjust specular highlights accordingly
- Edges: Tiles at walls should appear cut naturally (partial tiles at edges)
- Shadows: Furniture and room shadows fall naturally on the tiled surface

 VERIFICATION CHECKLIST:
 ALL floor surfaces show the tile from the reference image
 Tile pattern matches the reference EXACTLY
 Tiles are at correct real-world scale ({tile_size})
 Grout lines are visible and natural
 ALL furniture, walls, and ceiling are unchanged
 Image dimensions match input exactly

OUTPUT: One photorealistic image with floor tiled using the {tile_name} pattern.
"""


def generate_color_description(name: str, hex_value: str) -> str:
    """
    Generate a descriptive color language from hex for better AI color matching.

    This converts hex values to rich descriptions that help Gemini
    understand the exact color characteristics.

    Args:
        name: Color name (e.g., "Air Breeze")
        hex_value: Hex color (e.g., "#F5F5F0")

    Returns:
        Rich description of the color
    """
    # Parse hex color
    hex_clean = hex_value.lstrip("#")
    r = int(hex_clean[0:2], 16)
    g = int(hex_clean[2:4], 16)
    b = int(hex_clean[4:6], 16)

    # Determine brightness
    brightness = (r + g + b) / 3
    if brightness > 230:
        tone = "very light, almost white"
    elif brightness > 200:
        tone = "light"
    elif brightness > 150:
        tone = "medium-light"
    elif brightness > 100:
        tone = "medium"
    elif brightness > 60:
        tone = "medium-dark"
    else:
        tone = "deep, dark"

    # Determine warmth
    if r > b + 30:
        warmth = "warm"
    elif b > r + 30:
        warmth = "cool"
    else:
        warmth = "neutral"

    # Determine undertones
    undertone = ""
    if r > g and r > b:
        if r - g > 30:
            undertone = "with red/pink undertones"
        else:
            undertone = "with peachy undertones"
    elif g > r and g > b:
        if g - r > 30:
            undertone = "with green undertones"
        else:
            undertone = "with yellow-green undertones"
    elif b > r and b > g:
        if b - r > 30:
            undertone = "with blue undertones"
        else:
            undertone = "with purple undertones"
    elif abs(r - g) < 15 and abs(g - b) < 15:
        if brightness > 180:
            undertone = "with clean neutral undertones"
        else:
            undertone = "with balanced gray undertones"

    # Build description
    parts = [tone, warmth, name.lower()]
    if undertone:
        parts.append(undertone)

    return " ".join(parts).strip()


# Dimension loading helper functions (module-level)
async def load_product_dimensions(db, product_ids: List[int]) -> Dict[int, Dict[str, float]]:
    """
    Load dimensions (width, depth, height) for products from ProductAttribute table.

    Args:
        db: Database session
        product_ids: List of product IDs to load dimensions for

    Returns:
        Dict mapping product_id -> {"width": float, "depth": float, "height": float}
    """
    from sqlalchemy import select

    from database.models import ProductAttribute

    if not product_ids:
        return {}

    # Convert all product IDs to integers (they might be strings from frontend)
    int_product_ids = []
    for pid in product_ids:
        try:
            int_product_ids.append(int(pid))
        except (ValueError, TypeError):
            pass

    if not int_product_ids:
        return {}

    dimensions = {pid: {} for pid in int_product_ids}

    result = await db.execute(
        select(ProductAttribute).where(
            ProductAttribute.product_id.in_(int_product_ids), ProductAttribute.attribute_name.in_(["width", "depth", "height"])
        )
    )
    attributes = result.scalars().all()

    for attr in attributes:
        try:
            dimensions[attr.product_id][attr.attribute_name] = float(attr.attribute_value)
        except (ValueError, TypeError):
            pass

    return dimensions


async def load_product_visual_attributes(db, product_ids: List[int]) -> Dict[int, Dict[str, str]]:
    """
    Load visual attributes (color, material) for products from ProductAttribute table.

    These attributes help Gemini visually identify products for removal operations.

    Args:
        db: Database session
        product_ids: List of product IDs to load attributes for

    Returns:
        Dict mapping product_id -> {"color": str, "material": str}
    """
    from sqlalchemy import select

    from database.models import ProductAttribute

    if not product_ids:
        return {}

    # Convert all product IDs to integers (they might be strings from frontend)
    int_product_ids = []
    for pid in product_ids:
        try:
            int_product_ids.append(int(pid))
        except (ValueError, TypeError):
            pass

    if not int_product_ids:
        return {}

    visual_attrs = {pid: {} for pid in int_product_ids}

    # Query for color and material attributes
    result = await db.execute(
        select(ProductAttribute).where(
            ProductAttribute.product_id.in_(int_product_ids),
            ProductAttribute.attribute_name.in_(["color_primary", "color", "material", "finish"]),
        )
    )
    attributes = result.scalars().all()

    for attr in attributes:
        attr_name = attr.attribute_name.lower()
        # Prioritize color_primary over color, material over finish
        if "color" in attr_name and "color" not in visual_attrs[attr.product_id]:
            visual_attrs[attr.product_id]["color"] = attr.attribute_value
        elif attr_name in ("material", "finish") and "material" not in visual_attrs[attr.product_id]:
            visual_attrs[attr.product_id]["material"] = attr.attribute_value

    return visual_attrs


def enrich_products_with_dimensions(
    products: List[Dict[str, Any]], dimensions_map: Dict[int, Dict[str, float]]
) -> List[Dict[str, Any]]:
    """
    Add dimensions to product dicts from the dimensions map.

    Args:
        products: List of product dicts (must have 'id' key)
        dimensions_map: Dict mapping product_id -> dimensions dict

    Returns:
        Products with 'dimensions' key added
    """
    for product in products:
        product_id = product.get("id")
        # Convert to int for lookup (IDs might be strings from frontend)
        try:
            int_product_id = int(product_id) if product_id else None
        except (ValueError, TypeError):
            int_product_id = None
        if int_product_id and int_product_id in dimensions_map:
            product["dimensions"] = dimensions_map[int_product_id]
        elif "dimensions" not in product:
            product["dimensions"] = {}
    return products


class GoogleAIStudioService:
    """Service for Google AI Studio integration"""

    def __init__(self):
        """Initialize Google AI Studio service"""
        self.api_key = settings.google_ai_api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.session = None
        self.rate_limiter = self._create_rate_limiter()
        self.usage_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "last_reset": datetime.now(),
        }
        # Token usage tracking - accumulates all API calls
        self.token_usage_history: List[Dict[str, Any]] = []

        self._validate_api_key()

        # Initialize Google GenAI client for Gemini 3 Pro Image / Nano Banana Pro (only if API key is configured)
        if self.api_key:
            self.genai_client = genai.Client(api_key=self.api_key)
            self.genai_configured = True

            # Debug: Log API key info (first 8 and last 4 characters for security)
            if len(self.api_key) > 12:
                masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}"
                logger.info(f"Google AI API Key loaded: {masked_key}")

            logger.info("Google GenAI Client initialized successfully for Gemini 3 Pro Image (Nano Banana Pro)")
        else:
            self.genai_configured = False
            self.genai_client = None
            logger.warning("Google AI API key not configured - image generation will not be available")

        logger.info("Google AI Studio service initialized with Gemini 3 Pro Image (Nano Banana Pro) support")

        # Track last API call usage for logging by routers
        self.last_usage_metadata = None

    def extract_usage_metadata(
        self,
        response,
        operation: str = "unknown",
        model_override: str = None,
        workflow_id: str = None,
        user_id: str = None,
        session_id: str = None,
    ) -> Dict[str, Any]:
        """
        Extract token usage metadata from Gemini API response and persist to database.

        Args:
            response: Gemini API response object
            operation: Type of operation (visualize, analyze_room, chat, etc.)
            model_override: Override model name if known
            workflow_id: Optional workflow ID to track all API calls from a single user action
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking

        Returns:
            Dictionary with token counts and model info
        """
        usage = {
            "timestamp": datetime.now().isoformat(),
            "provider": "gemini",
            "model": model_override or getattr(response, "model", "gemini-2.0-flash-exp"),
            "operation": operation,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "workflow_id": workflow_id,
            "user_id": user_id,
            "session_id": session_id,
        }

        try:
            if hasattr(response, "usage_metadata"):
                metadata = response.usage_metadata
                usage["prompt_tokens"] = getattr(metadata, "prompt_token_count", None)
                usage["completion_tokens"] = getattr(metadata, "candidates_token_count", None)
                usage["total_tokens"] = getattr(metadata, "total_token_count", None)

                # Log for debugging
                logger.info(
                    f"[Token Usage] {usage['operation']} - model={usage['model']}, "
                    f"prompt={usage['prompt_tokens']}, completion={usage['completion_tokens']}, total={usage['total_tokens']}"
                )
        except Exception as e:
            logger.warning(f"Failed to extract usage metadata: {e}")

        self.last_usage_metadata = usage
        # Append to history for cumulative tracking
        self.token_usage_history.append(usage)

        # Persist to database
        self._persist_usage_to_db(usage)

        return usage

    def _persist_usage_to_db(self, usage: Dict[str, Any]):
        """Persist usage record to database (runs in background thread)."""
        try:
            from core.database import get_sync_db_session
            from database.models import ApiUsage

            with get_sync_db_session() as db:
                record = ApiUsage(
                    timestamp=datetime.now(),
                    user_id=usage.get("user_id"),
                    session_id=usage.get("session_id") or usage.get("workflow_id"),
                    provider=usage.get("provider", "gemini"),
                    model=usage.get("model", "unknown"),
                    operation=usage.get("operation", "unknown"),
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                )
                db.add(record)
                # Commit happens automatically via context manager
            user_info = f", user={usage.get('user_id')[:8]}..." if usage.get("user_id") else ""
            session_info = f", session={usage.get('session_id')[:8]}..." if usage.get("session_id") else ""
            logger.debug(f"[API Usage] Persisted to database: {usage['operation']}{user_info}{session_info}")
        except Exception as e:
            # Don't fail the main request if logging fails
            logger.warning(f"Failed to persist API usage to database: {e}")

    def _log_streaming_operation(
        self,
        operation: str,
        model: str,
        workflow_id: str = None,
        final_chunk=None,
        user_id: str = None,
        session_id: str = None,
    ):
        """
        Log a streaming API operation to the database.

        Args:
            operation: Name of the operation
            model: Model used
            workflow_id: Optional workflow ID for tracking
            final_chunk: The final chunk from streaming response (contains usage_metadata)
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking
        """
        # Extract token counts from final chunk if available
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None

        if final_chunk and hasattr(final_chunk, "usage_metadata"):
            metadata = final_chunk.usage_metadata
            prompt_tokens = getattr(metadata, "prompt_token_count", None)
            completion_tokens = getattr(metadata, "candidates_token_count", None)
            total_tokens = getattr(metadata, "total_token_count", None)

        usage = {
            "timestamp": datetime.now().isoformat(),
            "provider": "gemini",
            "model": model,
            "operation": operation,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "workflow_id": workflow_id,
            "user_id": user_id,
            "session_id": session_id,
        }

        if total_tokens:
            logger.info(
                f"[Streaming API] {operation} - model={model}, "
                f"prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
            )
        else:
            logger.info(f"[Streaming API] {operation} - model={model} (token counts not available)")

        self.last_usage_metadata = usage
        self.token_usage_history.append(usage)
        self._persist_usage_to_db(usage)

    def get_last_usage(self) -> Optional[Dict[str, Any]]:
        """Get the usage metadata from the last API call."""
        return self.last_usage_metadata

    def get_usage_summary(self, since_hours: int = 24) -> Dict[str, Any]:
        """
        Get usage summary for the specified time period.

        Args:
            since_hours: Number of hours to look back (default 24 for today)

        Returns:
            Dictionary with usage summary statistics
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=since_hours)
        cutoff_iso = cutoff.isoformat()

        # Filter history to requested time period
        recent = [u for u in self.token_usage_history if u.get("timestamp", "") >= cutoff_iso]

        total_prompt = sum(u.get("prompt_tokens") or 0 for u in recent)
        total_completion = sum(u.get("completion_tokens") or 0 for u in recent)
        total_tokens = sum(u.get("total_tokens") or 0 for u in recent)

        # Group by operation
        by_operation = {}
        for u in recent:
            op = u.get("operation", "unknown")
            if op not in by_operation:
                by_operation[op] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            by_operation[op]["calls"] += 1
            by_operation[op]["prompt_tokens"] += u.get("prompt_tokens") or 0
            by_operation[op]["completion_tokens"] += u.get("completion_tokens") or 0
            by_operation[op]["total_tokens"] += u.get("total_tokens") or 0

        # Group by model
        by_model = {}
        for u in recent:
            model = u.get("model", "unknown")
            if model not in by_model:
                by_model[model] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            by_model[model]["calls"] += 1
            by_model[model]["prompt_tokens"] += u.get("prompt_tokens") or 0
            by_model[model]["completion_tokens"] += u.get("completion_tokens") or 0
            by_model[model]["total_tokens"] += u.get("total_tokens") or 0

        return {
            "period_hours": since_hours,
            "total_api_calls": len(recent),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "by_operation": by_operation,
            "by_model": by_model,
        }

    def clear_usage_history(self):
        """Clear the token usage history (typically done after persisting to database)."""
        self.token_usage_history = []
        logger.info("Token usage history cleared")

    def _validate_api_key(self):
        """Validate Google AI API key"""
        if not self.api_key:
            logger.warning("Google AI Studio API key not configured - service will not be functional")
            return

        logger.info("Google AI Studio API key validated")

    def _create_rate_limiter(self):
        """Create rate limiter for API calls"""

        class RateLimiter:
            def __init__(self, max_requests=30, time_window=60):
                self.max_requests = max_requests
                self.time_window = time_window
                self.requests = []

            async def acquire(self):
                now = datetime.now()
                # Remove old requests
                self.requests = [req for req in self.requests if (now - req).total_seconds() < self.time_window]

                if len(self.requests) >= self.max_requests:
                    sleep_time = self.time_window - (now - self.requests[0]).total_seconds()
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)

                self.requests.append(now)

        return RateLimiter()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=120)  # 2 minute timeout
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _make_api_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        operation: str = "unknown",
        workflow_id: str = None,
        user_id: str = None,
        session_id: str = None,
    ) -> Dict[str, Any]:
        """Make authenticated API request to Google AI Studio

        Args:
            endpoint: API endpoint path
            payload: Request payload
            operation: Operation name for usage tracking
            workflow_id: Optional workflow ID to track all API calls from a single user action
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking
        """
        await self.rate_limiter.acquire()

        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}

        start_time = time.time()
        self.usage_stats["total_requests"] += 1

        # Extract model name from endpoint (e.g., "models/gemini-3-pro-preview:generateContent" -> "gemini-3-pro-preview")
        model_name = "unknown"
        if "models/" in endpoint:
            model_name = endpoint.split("models/")[1].split(":")[0]

        try:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    self.usage_stats["successful_requests"] += 1
                    processing_time = time.time() - start_time
                    self.usage_stats["total_processing_time"] += processing_time

                    # Log usage from REST API response
                    self._log_rest_api_usage(result, operation, model_name, workflow_id, user_id, session_id)

                    logger.info(f"Google AI API request successful - Time: {processing_time:.2f}s")
                    return result
                else:
                    error_text = await response.text()
                    self.usage_stats["failed_requests"] += 1
                    logger.error(f"Google AI API error {response.status}: {error_text}")
                    raise Exception(f"API request failed: {response.status} - {error_text}")

        except Exception as e:
            self.usage_stats["failed_requests"] += 1
            logger.error(f"Google AI API request failed: {e}")
            raise

    def _log_rest_api_usage(
        self,
        result: Dict[str, Any],
        operation: str,
        model: str,
        workflow_id: str = None,
        user_id: str = None,
        session_id: str = None,
    ):
        """Log token usage from REST API response."""
        try:
            usage_metadata = result.get("usageMetadata", {})

            usage = {
                "timestamp": datetime.now().isoformat(),
                "provider": "gemini",
                "model": model,
                "operation": operation,
                "prompt_tokens": usage_metadata.get("promptTokenCount"),
                "completion_tokens": usage_metadata.get("candidatesTokenCount"),
                "total_tokens": usage_metadata.get("totalTokenCount"),
                "workflow_id": workflow_id,
                "user_id": user_id,
                "session_id": session_id,
            }

            if usage["total_tokens"]:
                logger.info(
                    f"[Token Usage] {operation} - model={model}, "
                    f"prompt={usage['prompt_tokens']}, completion={usage['completion_tokens']}, total={usage['total_tokens']}"
                )

            self.last_usage_metadata = usage
            self.token_usage_history.append(usage)
            self._persist_usage_to_db(usage)
        except Exception as e:
            logger.warning(f"Failed to log REST API usage: {e}")

    async def analyze_room_image(
        self, image_data: str, workflow_id: str = None, user_id: str = None, session_id: str = None
    ) -> RoomAnalysis:
        """Analyze room image for spatial understanding"""
        try:
            # Prepare image for analysis
            processed_image = self._preprocess_image(image_data)

            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": """Analyze this interior space image. CRITICAL: You MUST include camera_view_analysis as the FIRST field.

Return JSON in this EXACT format (camera_view_analysis MUST be first):

{
  "camera_view_analysis": {
    "viewing_angle": "straight_on OR diagonal_left OR diagonal_right OR corner",
    "primary_wall": "back/left/right/none_visible",
    "floor_center_location": "image_center/left_of_center/right_of_center/corner_area",
    "recommended_furniture_zone": "against_back_wall/against_left_wall/against_right_wall/center_floor"
  },
  "room_type": "living_room/bedroom/kitchen/etc",
  "dimensions": {
    "estimated_width_ft": 12.0,
    "estimated_length_ft": 15.0,
    "estimated_height_ft": 9.0,
    "square_footage": 180.0
  },
  "lighting_conditions": "natural/artificial/mixed",
  "color_palette": ["primary_color", "secondary_color", "accent_color"],
  "existing_furniture": [],
  "architectural_features": ["windows", "etc"],
  "style_assessment": "modern/traditional/etc",
  "scale_references": {
    "door_visible": true,
    "window_visible": true,
    "camera_perspective": {
      "angle": "eye_level/high_angle/low_angle"
    }
  }
}

CRITICAL - VIEWING ANGLE DETECTION (camera_view_analysis.viewing_angle):

Look at how many walls you can see and their angles:
- "corner" = You can see TWO walls meeting at a corner. Both walls are visible at angles. THIS IMAGE IS LIKELY A CORNER VIEW.
- "diagonal_left" = Camera points toward the left-back corner. The RIGHT wall is prominently visible.
- "diagonal_right" = Camera points toward the right-back corner. The LEFT wall is prominently visible.
- "straight_on" = RARE. Only if: the back wall is perfectly parallel to the image edge AND you can barely see any side walls.

NOTE: If you can clearly see TWO walls (like a window wall AND a solid wall meeting at a corner), it's "corner" NOT "straight_on".

For primary_wall: Choose the SOLID wall without windows/glass doors.
For recommended_furniture_zone: Place furniture against solid walls, NOT windows."""
                            },
                            {"inline_data": {"mime_type": "image/jpeg", "data": processed_image}},
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                    "responseMimeType": "application/json",
                },
            }

            result = await self._make_api_request(
                "models/gemini-3-pro-preview:generateContent",
                payload,
                operation="analyze_room_image",
                workflow_id=workflow_id,
                user_id=user_id,
                session_id=session_id,
            )

            # Parse response
            content = result.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "{}")

            try:
                # Clean up common JSON formatting issues from AI
                # 1. Remove trailing commas before ] or }
                import re

                cleaned_response = re.sub(r",(\s*[}\]])", r"\1", text_response)
                # 2. Remove any markdown code blocks
                cleaned_response = re.sub(r"^```json\s*", "", cleaned_response)
                cleaned_response = re.sub(r"\s*```$", "", cleaned_response)

                analysis_data = json.loads(cleaned_response)
                # Log what keys the AI actually returned
                logger.info(f"Room analysis response keys from AI: {list(analysis_data.keys())}")
                # Log the camera_view_analysis from the AI response
                logger.info(
                    f"Room analysis raw camera_view_analysis from AI: {analysis_data.get('camera_view_analysis', 'NOT FOUND IN RESPONSE')}"
                )
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                logger.warning(f"Raw response text (first 500 chars): {text_response[:500]}...")
                # Try one more time with aggressive cleanup
                try:
                    # Extract just the JSON object between { and }
                    json_match = re.search(r"\{[\s\S]*\}", text_response)
                    if json_match:
                        cleaned = re.sub(r",(\s*[}\]])", r"\1", json_match.group())
                        analysis_data = json.loads(cleaned)
                        logger.info("Successfully parsed JSON after aggressive cleanup")
                    else:
                        raise json.JSONDecodeError("No JSON object found", text_response, 0)
                except json.JSONDecodeError:
                    # Try to extract just camera_view_analysis even if full JSON is malformed
                    logger.warning("Both JSON parsing attempts failed, trying to extract camera_view_analysis")
                    extracted_viewing_angle = "straight_on"
                    try:
                        # Look for viewing_angle value in the raw text
                        angle_match = re.search(r'"viewing_angle"\s*:\s*"([^"]+)"', text_response)
                        if angle_match:
                            extracted_viewing_angle = angle_match.group(1)
                            logger.info(f"Extracted viewing_angle from malformed JSON: {extracted_viewing_angle}")
                    except Exception:
                        pass

                    analysis_data = {
                        "room_type": "unknown",
                        "dimensions": {},
                        "lighting_conditions": "mixed",
                        "color_palette": [],
                        "existing_furniture": [],
                        "architectural_features": [],
                        "style_assessment": "unknown",
                        "scale_references": {},
                        "camera_view_analysis": {
                            "viewing_angle": extracted_viewing_angle,
                            "primary_wall": "back",
                            "floor_center_location": "image_center",
                            "recommended_furniture_zone": "center_floor",
                        },
                    }

            return RoomAnalysis(
                room_type=analysis_data.get("room_type", "unknown"),
                dimensions=analysis_data.get("dimensions", {}),
                lighting_conditions=analysis_data.get("lighting_conditions", "mixed"),
                color_palette=analysis_data.get("color_palette", []),
                existing_furniture=analysis_data.get("existing_furniture", []),
                architectural_features=analysis_data.get("architectural_features", []),
                style_assessment=analysis_data.get("style_assessment", "unknown"),
                confidence_score=0.85,  # High confidence for Google AI analysis
                scale_references=analysis_data.get("scale_references", {}),
                camera_view_analysis=analysis_data.get(
                    "camera_view_analysis",
                    {
                        "viewing_angle": "straight_on",
                        "primary_wall": "back",
                        "floor_center_location": "image_center",
                        "recommended_furniture_zone": "center_floor",
                    },
                ),
            )

        except Exception as e:
            logger.error(f"Error in room analysis: {e}")
            return self._create_fallback_room_analysis()

    async def analyze_room_with_furniture(self, image_data: str) -> RoomAnalysis:
        """
        Combined room analysis AND furniture detection in ONE API call.

        This optimization combines analyze_room_image() + detect_objects_in_room()
        into a single Gemini call, saving 2-5 seconds per visualization.

        Returns RoomAnalysis with existing_furniture populated from detailed detection.
        """
        try:
            processed_image = self._preprocess_image(image_data)

            prompt = """Analyze this interior space image comprehensively. You MUST include BOTH room analysis AND detailed furniture detection.

Return JSON in this EXACT format:

{
  "camera_view_analysis": {
    "viewing_angle": "straight_on/diagonal_left/diagonal_right/corner",
    "primary_wall": "back/left/right/none_visible",
    "floor_center_location": "image_center/left_of_center/right_of_center/corner_area",
    "recommended_furniture_zone": "against_back_wall/against_left_wall/against_right_wall/center_floor"
  },
  "room_type": "living_room/bedroom/kitchen/dining_room/office/etc",
  "dimensions": {
    "estimated_width_ft": 12.0,
    "estimated_length_ft": 15.0,
    "estimated_height_ft": 9.0,
    "square_footage": 180.0
  },
  "lighting_conditions": "natural/artificial/mixed",
  "color_palette": ["primary_color", "secondary_color", "accent_color"],
  "style_assessment": "modern/traditional/minimalist/bohemian/industrial/etc",
  "architectural_features": ["windows", "doors", "fireplace", "built-in_shelves", "etc"],
  "scale_references": {
    "door_visible": true,
    "window_visible": true,
    "camera_perspective": {
      "angle": "eye_level/high_angle/low_angle"
    }
  },
  "existing_furniture": [
    {
      "object_type": "sofa",
      "position": "center-left/center/right/back-left/front-center/etc",
      "size": "small/medium/large",
      "style": "modern/traditional/etc",
      "color": "gray/beige/blue/etc",
      "material": "fabric/leather/wood/metal/etc",
      "confidence": 0.95
    }
  ]
}

 CRITICAL - VIEWING ANGLE DETECTION (camera_view_analysis.viewing_angle):
- "corner" = TWO walls visible meeting at a corner
- "diagonal_left" = Camera points toward left-back corner, RIGHT wall prominently visible
- "diagonal_right" = Camera points toward right-back corner, LEFT wall prominently visible
- "straight_on" = RARE - only if back wall is perfectly parallel and side walls barely visible

 EXISTING FURNITURE - CRITICAL:
List ALL furniture and decor objects visible in the room with detailed attributes:
- Include sofas, chairs, tables, lamps, rugs, plants, shelves, beds, dressers, etc.
- Include wall art, mirrors, curtains if visible
- For each item: object_type, position, size, style, color, material, confidence (0-1)"""

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": processed_image}},
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 3072,  # Increased for furniture list
                    "responseMimeType": "application/json",
                },
            }

            result = await self._make_api_request(
                "models/gemini-3-pro-preview:generateContent", payload, operation="analyze_room_with_furniture"
            )

            content = result.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "{}")

            try:
                import re

                cleaned_response = re.sub(r",(\s*[}\]])", r"\1", text_response)
                cleaned_response = re.sub(r"^```json\s*", "", cleaned_response)
                cleaned_response = re.sub(r"\s*```$", "", cleaned_response)
                analysis_data = json.loads(cleaned_response)

                logger.info(f"Combined room analysis response keys: {list(analysis_data.keys())}")
                furniture_count = len(analysis_data.get("existing_furniture", []))
                logger.info(f"Detected {furniture_count} furniture items in combined analysis")

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse combined analysis JSON: {e}")
                try:
                    json_match = re.search(r"\{[\s\S]*\}", text_response)
                    if json_match:
                        cleaned = re.sub(r",(\s*[}\]])", r"\1", json_match.group())
                        analysis_data = json.loads(cleaned)
                        logger.info("Successfully parsed JSON after cleanup")
                    else:
                        raise json.JSONDecodeError("No JSON object found", text_response, 0)
                except json.JSONDecodeError:
                    logger.warning("Both JSON parsing attempts failed, using fallback")
                    analysis_data = self._get_fallback_combined_analysis()

            return RoomAnalysis(
                room_type=analysis_data.get("room_type", "unknown"),
                dimensions=analysis_data.get("dimensions", {}),
                lighting_conditions=analysis_data.get("lighting_conditions", "mixed"),
                color_palette=analysis_data.get("color_palette", []),
                existing_furniture=analysis_data.get("existing_furniture", []),
                architectural_features=analysis_data.get("architectural_features", []),
                style_assessment=analysis_data.get("style_assessment", "unknown"),
                confidence_score=0.85,
                scale_references=analysis_data.get("scale_references", {}),
                camera_view_analysis=analysis_data.get(
                    "camera_view_analysis",
                    {
                        "viewing_angle": "straight_on",
                        "primary_wall": "back",
                        "floor_center_location": "image_center",
                        "recommended_furniture_zone": "center_floor",
                    },
                ),
            )

        except Exception as e:
            logger.error(f"Error in combined room analysis: {e}")
            return self._create_fallback_room_analysis()

    def _get_fallback_combined_analysis(self) -> Dict[str, Any]:
        """Fallback data for combined room analysis when JSON parsing fails"""
        return {
            "room_type": "unknown",
            "dimensions": {},
            "lighting_conditions": "mixed",
            "color_palette": [],
            "existing_furniture": [],
            "architectural_features": [],
            "style_assessment": "unknown",
            "scale_references": {},
            "camera_view_analysis": {
                "viewing_angle": "straight_on",
                "primary_wall": "back",
                "floor_center_location": "image_center",
                "recommended_furniture_zone": "center_floor",
            },
        }

    async def perform_spatial_analysis(self, room_analysis: RoomAnalysis) -> SpatialAnalysis:
        """Perform spatial analysis for furniture placement"""
        try:
            # Create spatial analysis prompt
            spatial_prompt = f"""
Based on this room analysis, provide spatial layout recommendations:

Room Type: {room_analysis.room_type}
Dimensions: {room_analysis.dimensions}
Existing Furniture: {room_analysis.existing_furniture}
Architectural Features: {room_analysis.architectural_features}

Provide detailed spatial analysis in JSON format:
{{
  "layout_type": "open/closed/mixed",
  "traffic_patterns": ["main_walkway", "secondary_path"],
  "focal_points": [
    {{"type": "window", "position": "north_wall", "importance": "high"}},
    {{"type": "fireplace", "position": "east_wall", "importance": "medium"}}
  ],
  "available_spaces": [
    {{
      "area": "center_space",
      "dimensions": {{"width": 8, "length": 6}},
      "suitable_for": ["seating_group", "coffee_table"],
      "accessibility": "high"
    }}
  ],
  "placement_suggestions": [
    {{
      "furniture_type": "sofa",
      "recommended_position": "facing_fireplace",
      "distance_from_wall": 18,
      "orientation": "perpendicular_to_window",
      "reasoning": "creates_conversation_area"
    }}
  ],
  "scale_recommendations": {{
    "sofa_length": "84-96_inches",
    "coffee_table": "48x24_inches",
    "rug_size": "8x10_feet"
  }}
}}
"""

            payload = {
                "contents": [{"parts": [{"text": spatial_prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1536, "responseMimeType": "application/json"},
            }

            result = await self._make_api_request(
                "models/gemini-3-pro-preview:generateContent", payload, operation="spatial_analysis"
            )

            content = result.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "{}")

            try:
                spatial_data = json.loads(text_response)
            except json.JSONDecodeError:
                spatial_data = self._create_fallback_spatial_analysis()

            return SpatialAnalysis(
                layout_type=spatial_data.get("layout_type", "mixed"),
                traffic_patterns=spatial_data.get("traffic_patterns", []),
                focal_points=spatial_data.get("focal_points", []),
                available_spaces=spatial_data.get("available_spaces", []),
                placement_suggestions=spatial_data.get("placement_suggestions", []),
                scale_recommendations=spatial_data.get("scale_recommendations", {}),
            )

        except Exception as e:
            logger.error(f"Error in spatial analysis: {e}")
            return self._create_fallback_spatial_analysis()

    async def detect_objects_in_room(self, image_data: str, workflow_id: str = None) -> List[Dict[str, Any]]:
        """Detect and classify objects in room image"""
        try:
            processed_image = self._preprocess_image(image_data)

            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": """Identify and locate all furniture and decor objects in this room image.

For each object, provide:
- Object type (sofa, chair, table, lamp, etc.)
- Position in room (left, center, right, foreground, background)
- Approximate size (small, medium, large)
- Style classification
- Color/material
- Condition assessment

Return results as JSON array:
[
  {
    "object_type": "sofa",
    "position": "center-left",
    "size": "large",
    "style": "modern",
    "color": "charcoal_gray",
    "material": "fabric",
    "condition": "good",
    "confidence": 0.95
  }
]"""
                            },
                            {"inline_data": {"mime_type": "image/jpeg", "data": processed_image}},
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024, "responseMimeType": "application/json"},
            }

            result = await self._make_api_request(
                "models/gemini-2.5-flash:generateContent", payload, operation="detect_objects", workflow_id=workflow_id
            )

            content = result.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "[]")

            try:
                objects = json.loads(text_response)
                return objects if isinstance(objects, list) else []
            except json.JSONDecodeError:
                logger.warning("Failed to parse object detection response")
                return []

        except Exception as e:
            logger.error(f"Error in object detection: {e}")
            return []

    async def detect_furniture_in_image(self, image_data: str) -> List[Dict[str, Any]]:
        """
        Detect all furniture items in the image
        Returns: [{"furniture_type": "sofa", "confidence": 0.95}, ...]
        """
        try:
            processed_image = self._preprocess_image(image_data)

            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": """List all furniture items visible in this room image.
For each item, provide:
- furniture_type (e.g., "sofa", "chair", "bed", "lamp", "cabinet")
- confidence (0-1 scale indicating how certain you are)

IMPORTANT FURNITURE CATEGORIZATION:

SEATING:
- For SOFAS (couch, sectional, loveseat), use: "sofa"
- For CHAIRS (accent chair, side chair, armchair, sofa chair, dining chair, recliner), use: "chair" or be specific like "accent_chair", "armchair", etc.
- Keep sofas and chairs SEPARATE - they are different categories

TABLES (NOT lamps):
- If the table is positioned IN FRONT OF or IN THE CENTER in front of seating (sofa/chairs), use: "center_table" or "coffee_table"
- If the table is positioned BESIDE or NEXT TO seating (sofa/chairs/bed), use: "side_table" or "end_table"
- For dining tables, use: "dining_table"
- For console tables against walls, use: "console_table"
- CRITICAL: Do NOT confuse table lamps with tables - they are LAMPS, not tables!

LIGHTING:
- For table lamps, desk lamps, floor lamps: use "lamp" or specific type like "table_lamp", "floor_lamp"
- For ceiling lights, chandeliers, pendants: use "chandelier" or "ceiling_lamp"
- For wall lights: use "wall_lamp" or "sconce"
- CRITICAL: Lamps are LIGHTING, NOT tables or furniture!

Return results as JSON array:
[
  {
    "furniture_type": "sofa",
    "confidence": 0.95
  },
  {
    "furniture_type": "center_table",
    "confidence": 0.88
  },
  {
    "furniture_type": "side_table",
    "confidence": 0.85
  }
]

IMPORTANT: Only include actual furniture pieces. Do not include decorative items, walls, windows, or structural elements.
CRITICAL: Distinguish between center_table (in front of seating) and side_table (beside seating) based on position."""
                            },
                            {"inline_data": {"mime_type": "image/jpeg", "data": processed_image}},
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024, "responseMimeType": "application/json"},
            }

            result = await self._make_api_request(
                "models/gemini-3-pro-preview:generateContent", payload, operation="detect_furniture"
            )

            content = result.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "[]")

            try:
                furniture_list = json.loads(text_response)
                return furniture_list if isinstance(furniture_list, list) else []
            except json.JSONDecodeError:
                logger.warning("Failed to parse furniture detection response")
                return []

        except Exception as e:
            logger.error(f"Error in furniture detection: {e}")
            return []

    async def check_furniture_exists(self, image_data: str, furniture_type: str) -> Tuple[bool, List[Dict]]:
        """
        Check if specific furniture type exists in image
        Returns: (exists: bool, matching_items: List[Dict])
        """
        try:
            processed_image = self._preprocess_image(image_data)

            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"""Analyze this room image and determine if there is a "{furniture_type}" (or similar furniture) present.

Return a JSON response with:
- exists: true/false (whether the furniture type exists)
- matching_items: array of matching furniture items with details

Example response:
{{
  "exists": true,
  "matching_items": [
    {{
      "furniture_type": "sofa",
      "position": "center-left",
      "description": "Gray sectional sofa with chaise",
      "confidence": 0.95
    }}
  ]
}}

If the furniture type does NOT exist, return:
{{
  "exists": false,
  "matching_items": []
}}

Furniture type to look for: {furniture_type}

Be flexible with matching - for example:
- "sofa" matches: sofa, couch, sectional, loveseat (but NOT chairs)
- "chair" matches: chair, armchair, dining chair, accent chair, side chair, sofa chair, recliner (but NOT sofas)
- "table" matches: coffee table, side table, end table (but NOT table lamps - those are lamps!)
- "lamp" matches: table lamp, desk lamp, floor lamp, wall lamp (but NOT tables with lamps on them!)

CRITICAL: Keep sofas, chairs, tables, and lamps SEPARATE:
- Sofas are larger seating pieces (couch, sectional)
- Chairs are individual seating pieces (accent chair, armchair, side chair)
- Tables are surfaces for placing items (coffee table, side table, dining table)
- Lamps are lighting fixtures (table lamp, floor lamp, ceiling lamp) - NOT tables!"""
                            },
                            {"inline_data": {"mime_type": "image/jpeg", "data": processed_image}},
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512, "responseMimeType": "application/json"},
            }

            result = await self._make_api_request(
                "models/gemini-3-pro-preview:generateContent", payload, operation="check_furniture_exists"
            )

            content = result.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "{}")

            try:
                response_data = json.loads(text_response)
                exists = response_data.get("exists", False)
                matching_items = response_data.get("matching_items", [])
                return (exists, matching_items)
            except json.JSONDecodeError:
                logger.warning("Failed to parse furniture existence check response")
                return (False, [])

        except Exception as e:
            logger.error(f"Error checking furniture existence: {e}")
            return (False, [])

    async def validate_space_fitness(
        self,
        room_image: str,
        product_name: str,
        product_image: Optional[str] = None,
        product_description: Optional[str] = None,
    ) -> SpaceFitnessResult:
        """
        Validate if a product can fit in the available space in the room.
        Uses Gemini to analyze both the room space and product dimensions.

        Returns:
            SpaceFitnessResult with fits (bool), confidence, reason, and optional suggestion
        """
        try:
            processed_room = self._preprocess_image(room_image)

            # Download product image if URL provided
            product_image_data = None
            if product_image:
                try:
                    product_image_data = await self._download_image(product_image)
                except Exception as e:
                    logger.warning(f"Failed to download product image for space validation: {e}")

            # Build prompt for space fitness validation
            # IMPORTANT: Product description contains actual dimensions - prioritize these over image estimation
            prompt = f""" SPACE FITNESS ANALYSIS TASK

Analyze whether the following product can realistically fit in the available space shown in the room image.

PRODUCT TO ANALYZE: {product_name}

═══════════════════════════════════════════════════════════════
 CRITICAL: PRODUCT DIMENSIONS (FROM DESCRIPTION)
═══════════════════════════════════════════════════════════════
{f"PRODUCT DESCRIPTION: {product_description}" if product_description else "No description available - estimate from product image"}

 IMPORTANT: Extract the ACTUAL dimensions from the product description above.
Look for measurements like:
- Height, Width, Depth/Length (in inches, cm, feet, etc.)
- Diameter (for round items)
- Overall dimensions (L x W x H)
- Size specifications

If dimensions are found in the description, USE THESE EXACT MEASUREMENTS.
Only estimate from the product image if NO dimensions are provided in the description.

═══════════════════════════════════════════════════════════════
STEP 1: EXTRACT PRODUCT DIMENSIONS
═══════════════════════════════════════════════════════════════
1. FIRST: Search the product description for any dimension/size information
2. Extract exact measurements (e.g., "24 inches tall", "60cm x 40cm", "2 feet wide")
3. Convert all measurements to a consistent unit (inches or cm) for comparison
4. If no dimensions in description, estimate from the product image as a fallback

═══════════════════════════════════════════════════════════════
STEP 2: ANALYZE THE ROOM SPACE
═══════════════════════════════════════════════════════════════
1. Identify existing furniture and their approximate sizes
2. Estimate the room dimensions using visual cues:
   - Standard door heights (~80 inches / 6.6 feet)
   - Standard ceiling heights (~8-10 feet)
   - Standard furniture sizes (sofas ~84-96", coffee tables ~48", etc.)
3. Identify available empty floor spaces and measure them approximately
4. Note any spatial constraints (narrow pathways, corners, tight spaces)

═══════════════════════════════════════════════════════════════
STEP 3: COMPARE DIMENSIONS AND DETERMINE FITNESS
═══════════════════════════════════════════════════════════════
Using the ACTUAL product dimensions (from description):
1. Is there enough floor space for this product's footprint?
2. Will the product height fit without looking oversized for the space?
3. Can the product be placed without blocking pathways or existing furniture?
4. Is there a logical placement spot for this type of product?
5. Would the product look proportionally appropriate in this space?

BE STRICT about large items:
- If a product is 6+ feet tall and the room appears small/crowded, it likely won't fit well
- If a product's footprint is larger than the available floor space, it doesn't fit
- Consider the visual weight - a large item in a small space will look cramped

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT (respond in valid JSON only):
═══════════════════════════════════════════════════════════════
{{
    "fits": true/false,
    "confidence": 0.0-1.0,
    "reason": "Brief explanation of why the product does or doesn't fit",
    "product_dimensions_found": "The exact dimensions extracted from description (or 'estimated from image' if none found)",
    "available_space_estimate": "Estimated available space in the room",
    "suggestion": "If doesn't fit, suggest an alternative (e.g., 'Consider a smaller planter under 24 inches' or 'This 72-inch cabinet is too large for the available 48-inch wall space')"
}}

RESPOND WITH JSON ONLY - NO OTHER TEXT."""

            # Build parts list
            parts = [types.Part.from_text(text=prompt)]
            parts.append(types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(processed_room))))

            # Add product reference image if available
            if product_image_data:
                parts.append(types.Part.from_text(text=f"\nProduct reference image ({product_name}):"))
                parts.append(
                    types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(product_image_data)))
                )

            contents = [types.Content(role="user", parts=parts)]

            # Use text-only response for analysis
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["TEXT"],
                temperature=0.2,  # Low temperature for consistent analysis
            )

            response_text = ""
            final_chunk = None  # Capture final chunk for usage_metadata
            for chunk in self.genai_client.models.generate_content_stream(
                model="gemini-3-pro-preview",  # Use Gemini 3 for analysis
                contents=contents,
                config=generate_content_config,
            ):
                final_chunk = chunk  # Always keep reference to last chunk
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.text:
                            response_text += part.text

            # Log with token tracking from final chunk
            self._log_streaming_operation("validate_space_fitness", "gemini-3-pro-preview", final_chunk=final_chunk)

            # Parse JSON response
            try:
                # Clean up response - remove markdown code blocks if present
                cleaned_response = response_text.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.startswith("```"):
                    cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()

                result = json.loads(cleaned_response)

                fits = result.get("fits", True)
                confidence = result.get("confidence", 0.8)
                reason = result.get("reason", "Unable to determine space fitness")
                suggestion = result.get("suggestion") if not fits else None

                logger.info(f"Space fitness validation for '{product_name}': fits={fits}, confidence={confidence}")

                return SpaceFitnessResult(
                    fits=fits,
                    confidence=confidence,
                    reason=reason,
                    suggestion=suggestion,
                )

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse space fitness response: {e}. Response: {response_text[:200]}")
                # Default to allowing placement if we can't parse the response
                return SpaceFitnessResult(
                    fits=True,
                    confidence=0.5,
                    reason="Unable to analyze space fitness, proceeding with visualization",
                    suggestion=None,
                )

        except Exception as e:
            logger.error(f"Error validating space fitness: {e}")
            # On error, allow visualization to proceed (fail open)
            return SpaceFitnessResult(
                fits=True,
                confidence=0.3,
                reason="Space fitness validation failed, proceeding with visualization",
                suggestion=None,
            )

    async def validate_furniture_removed(self, image_base64: str) -> Dict[str, Any]:
        """
        Validate that furniture was successfully removed from the image.
        Used to verify furniture removal was successful.
        Returns: dict with 'has_furniture' boolean and 'detected_items' list
        """
        try:
            # Remove data URL prefix if present
            if image_base64.startswith("data:image"):
                image_base64 = image_base64.split(",")[1]

            image_bytes = base64.b64decode(image_base64)
            pil_image = Image.open(io.BytesIO(image_bytes))

            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            prompt = """Analyze this room image and detect ANY furniture or movable objects.

IMPORTANT: Be very strict and thorough. Look for:
1. SEATING: Sofas, couches, sectionals, chairs, armchairs, ottomans, recliners
2. TABLES: Coffee tables, side tables, dining tables, console tables
3. BEDS: Beds, mattresses, headboards
4. LAMPS: Floor lamps, standing lamps, table lamps
5. PLANTS: Potted plants, indoor trees
6. FLOOR COVERINGS: Carpets, rugs, mats

Respond in JSON format:
{
  "has_furniture": true/false,
  "has_sofa": true/false,
  "has_carpet": true/false,
  "detected_items": ["list of detected items"],
  "confidence": 0.0-1.0
}

Be VERY strict - if you see ANY furniture at all, set has_furniture to true."""

            def _run_detect():
                response = self.genai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt, pil_image],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                # Extract and log token usage
                self.extract_usage_metadata(
                    response, operation="validate_furniture_removed", model_override="gemini-2.5-flash"
                )
                return response.text

            loop = asyncio.get_event_loop()
            response_text = await asyncio.wait_for(loop.run_in_executor(None, _run_detect), timeout=30)

            # Parse JSON response
            result = json.loads(response_text)
            logger.info(f"Furniture detection result: {result}")
            return result

        except Exception as e:
            logger.warning(f"Furniture detection failed: {e}")
            # Default to assuming furniture might still be there
            return {
                "has_furniture": True,
                "has_sofa": False,
                "has_carpet": False,
                "detected_items": ["unknown - detection failed"],
                "confidence": 0.0,
            }

    async def _apply_perspective_correction(self, image_base64: str, workflow_id: str = None) -> str:
        """
        Apply perspective/lens correction to an empty room image.
        Always straightens vertical lines regardless of viewing angle.

        Args:
            image_base64: Base64 encoded image (with or without data URL prefix)
            workflow_id: Workflow ID for tracking all API calls from a single user action

        Returns:
            Perspective-corrected image with straight vertical lines
        """
        try:
            logger.info("Applying perspective correction to straighten vertical lines")
            corrected_image = await self._straighten_vertical_lines(image_base64, workflow_id=workflow_id)
            if corrected_image:
                logger.info("Perspective correction complete")
                return corrected_image
            else:
                logger.warning("Perspective correction returned None, using original image")
                return image_base64

        except Exception as e:
            logger.warning(f"Perspective correction failed, using original image: {e}")
            return image_base64

    async def _straighten_vertical_lines(self, image_base64: str, workflow_id: str = None) -> Optional[str]:
        """
        Straighten vertical lines in a room image to correct lens distortion.
        This corrects the common issue where walls lean inward due to wide-angle lenses.

        Args:
            image_base64: Base64 encoded image
            workflow_id: Workflow ID for tracking all API calls from a single user action

        Returns:
            Image with straightened vertical lines, or None on failure
        """
        try:
            # Convert base64 to PIL Image
            image_data = image_base64
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]

            image_bytes = base64.b64decode(image_data)
            pil_image = Image.open(io.BytesIO(image_bytes))

            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            logger.info(f"Straightening vertical lines for image ({pil_image.width}x{pil_image.height})")

            prompt = """ LENS DISTORTION CORRECTION TASK

Correct the perspective distortion in this room image to make it look like a professional architectural photograph.

 WHAT TO FIX:
1. VERTICAL LINES: Make ALL vertical lines perfectly vertical (90° to the floor)
   - Wall edges should be straight up and down, not leaning inward or outward
   - Door frames, window frames should be perfectly vertical
   - Any vertical architectural elements should be straight

2. HORIZONTAL LINES: Make horizontal lines level
   - Floor line should be horizontal
   - Ceiling line should be horizontal
   - Window sills, baseboards should be level

3. LENS DISTORTION: Correct any barrel or pincushion distortion from wide-angle lenses
   - Straight lines in real life should appear straight in the image
   - Walls should not curve or bulge

 IMPORTANT:
- Do NOT change the room contents - keep everything exactly as is
- Do NOT change colors, lighting, or any visual elements
- ONLY fix the geometric distortion
- The result should look like it was taken with a professional tilt-shift lens

OUTPUT: Same image with corrected perspective - walls perfectly vertical, lines straight."""

            def _run_correction():
                response = self.genai_client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=[prompt, pil_image],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        temperature=0.2,
                    ),
                )
                # Extract and log token usage (workflow_id captured from outer scope)
                self.extract_usage_metadata(
                    response,
                    operation="straighten_vertical_lines",
                    model_override="gemini-3-pro-image-preview",
                    workflow_id=workflow_id,
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
                            image_bytes_result = part.inline_data.data
                            mime_type = getattr(part.inline_data, "mime_type", None) or "image/png"

                            if isinstance(image_bytes_result, bytes):
                                first_hex = image_bytes_result[:4].hex()
                                if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                    image_base64_result = base64.b64encode(image_bytes_result).decode("utf-8")
                                else:
                                    image_base64_result = image_bytes_result.decode("utf-8")
                                result_image = f"data:{mime_type};base64,{image_base64_result}"
                                break

                return result_image

            loop = asyncio.get_event_loop()
            corrected = await asyncio.wait_for(loop.run_in_executor(None, _run_correction), timeout=90)
            return corrected

        except asyncio.TimeoutError:
            logger.error("Vertical line straightening timed out after 90 seconds")
            return None
        except Exception as e:
            logger.error(f"Error straightening vertical lines: {e}")
            return None

    async def remove_furniture(
        self, image_base64: str, max_retries: int = 5, workflow_id: str = None, user_id: str = None, session_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Remove all furniture from room image using Gemini image model.

        This function performs 2 Gemini calls:
        1. analyze_room_image (JSON) - detect viewing angle + room style/type/dimensions
        2. remove_furniture (IMAGE) - removes furniture + straightens lines + transforms to front view (if angle is not straight_on)

        Args:
            image_base64: Base64 encoded source image
            max_retries: Number of retry attempts
            workflow_id: Optional workflow ID for tracking all API calls from a single user action
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking

        Returns: Dict with 'image' (base64) and 'room_analysis' (dict), or None on failure
        """
        try:
            # Step 1: Analyze room for viewing angle AND capture full room analysis (JSON call)
            viewing_angle = "straight_on"  # default
            room_analysis_dict = None
            try:
                room_analysis = await self.analyze_room_image(
                    image_base64, workflow_id=workflow_id, user_id=user_id, session_id=session_id
                )
                viewing_angle = room_analysis.camera_view_analysis.get("viewing_angle", "straight_on")
                # Capture full room analysis for return
                room_analysis_dict = {
                    "camera_view_analysis": room_analysis.camera_view_analysis,
                    "room_type": room_analysis.room_type,
                    "dimensions": room_analysis.dimensions,
                    "lighting_conditions": room_analysis.lighting_conditions,
                    "color_palette": room_analysis.color_palette,
                    "existing_furniture": room_analysis.existing_furniture,
                    "architectural_features": room_analysis.architectural_features,
                    "style_assessment": room_analysis.style_assessment,
                    "scale_references": room_analysis.scale_references,
                }
                logger.info(
                    f"Room analysis complete: viewing_angle={viewing_angle}, style={room_analysis.style_assessment}, workflow_id={workflow_id}"
                )
            except Exception as e:
                logger.warning(f"Room analysis failed, assuming straight_on: {e}")

            # Step 2: Remove furniture + transform perspective + straighten lines (single IMAGE call)
            # Convert base64 to PIL Image
            original_length = len(image_base64)
            logger.info(f"Received image base64 string: {original_length} characters")

            image_to_process = image_base64
            # Remove data URL prefix if present
            if image_to_process.startswith("data:image"):
                image_to_process = image_to_process.split(",")[1]
                logger.info(f"After stripping data URL prefix: {len(image_to_process)} characters")

            # Log preview to detect truncation
            if len(image_to_process) > 100:
                logger.info(f"Base64 preview: {image_to_process[:50]}...{image_to_process[-50:]}")

            image_bytes = base64.b64decode(image_to_process)
            logger.info(f"Decoded to {len(image_bytes)} bytes")

            # Validate minimum size (real images are > 1KB)
            if len(image_bytes) < 1024:
                raise ValueError(f"Image data too small ({len(image_bytes)} bytes), likely truncated in transit")

            # Check magic bytes for common image formats
            magic_bytes = image_bytes[:8].hex()
            logger.info(f"Image magic bytes: {magic_bytes}")

            # JPEG starts with FFD8FF, PNG starts with 89504E47
            if not (magic_bytes.startswith("ffd8ff") or magic_bytes.startswith("89504e47")):
                logger.warning(f"Unexpected magic bytes: {magic_bytes}. Expected JPEG (ffd8ff) or PNG (89504e47).")

            pil_image = Image.open(io.BytesIO(image_bytes))

            # Apply EXIF orientation correction (important for smartphone photos)
            # This rotates the image to its correct orientation based on EXIF metadata
            pil_image = ImageOps.exif_transpose(pil_image)

            # Convert to RGB if needed (e.g., RGBA images)
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            logger.info(
                f"Loaded image for furniture removal (EXIF corrected): {pil_image.width}x{pil_image.height} pixels, viewing_angle={viewing_angle}"
            )

            # Step 2: Remove furniture + straighten lines + transform angle (if needed)
            # Build perspective/transformation instructions based on detected viewing angle
            if viewing_angle == "straight_on":
                perspective_instruction = """PERSPECTIVE CORRECTION (MANDATORY):
- Straighten ALL vertical lines (walls, door frames, window frames should be perfectly vertical - 90 degrees to floor)
- Level ALL horizontal lines (floor line, ceiling line, window sills should be horizontal)
- Correct any lens distortion - walls should NOT lean inward or outward
- The output should look like a professional real estate photo with proper architectural perspective"""
                angle_output = "SAME CAMERA ANGLE - keep the exact same viewing angle as the input"
            else:
                # For diagonal/corner views, include transformation to front view
                angle_descriptions = {
                    "diagonal_left": "diagonal left angle (camera positioned to the right, looking left toward a corner)",
                    "diagonal_right": "diagonal right angle (camera positioned to the left, looking right toward a corner)",
                    "corner": "corner angle (camera in the corner, looking diagonally across the room)",
                }
                angle_desc = angle_descriptions.get(viewing_angle, f"{viewing_angle} angle")
                perspective_instruction = f"""CAMERA ANGLE TRANSFORMATION + PERSPECTIVE CORRECTION (MANDATORY):

CURRENT VIEW: This image is taken from {angle_desc}. You can see TWO walls meeting.

YOUR TASK - Transform to STRAIGHT-ON FRONT VIEW:
- Generate the room as if the camera moved to face the MAIN WALL directly (parallel to image edges)
- The main solid wall should fill the CENTER of the output image
- Side walls should be barely visible (thin slivers at left/right edges)
- You should NOT see a corner prominently anymore

ALSO CORRECT PERSPECTIVE:
- ALL vertical lines must be perfectly vertical (90 degrees to floor)
- ALL horizontal lines must be level
- Correct any lens distortion - walls should NOT lean inward or outward
- Output should look like a professional architectural photograph"""
                angle_output = "FRONT-FACING VIEW - camera facing main wall directly"

            prompt = f"""CRITICAL TASK: Remove ALL furniture, correct lens distortion, and transform to front view.

The output MUST be:
1. A COMPLETELY EMPTY room with ZERO furniture remaining
2. {angle_output}
3. PERSPECTIVE CORRECTED - vertical lines straight, horizontal lines level

{perspective_instruction}

MANDATORY REMOVALS - These items MUST be deleted from the image:
1. ALL SEATING: Sofas (including curved/sectional sofas), couches, chairs, armchairs, ottomans
2. ALL TABLES: Coffee tables, side tables, dining tables, console tables
3. ALL BEDS: Beds, mattresses, headboards
4. ALL LAMPS: Floor lamps, tripod lamps, standing lamps, table lamps, any lamp with a base on the floor
5. ALL CEILING LIGHTS: Chandeliers, pendant lights, ceiling fans with lights, hanging lamps, track lighting, recessed light fixtures
6. ALL MIRRORS: Standing mirrors, floor mirrors, full-length mirrors, leaning mirrors against walls
7. ALL PLANTS: Potted plants, planters, indoor trees
8. ALL DECOR: Vases, sculptures, frames, cushions, throws on furniture
9. ALL WALL ART: Paintings, posters, prints, wall hangings, framed photos, canvas art, wall decor, tapestries
10. ALL FLOOR COVERINGS: Carpets, rugs, area rugs, floor mats, dhurries, runners - the BARE FLOOR must be visible

KEEP ONLY (do not modify these):
- Walls, ceiling, floor (the BARE room floor - no carpets/rugs)
- Windows, doors, built-in closets
- Curtains/drapes on windows
- AC units mounted on walls
- Electrical outlets and switches
- Archways and architectural features

OUTPUT: Generate an image of the SAME room but:
1. COMPLETELY EMPTY - no furniture, no lamps, no ceiling lights, no mirrors, no plants, NO CARPETS OR RUGS, NO WALL ART
2. {angle_output}
3. PERSPECTIVE CORRECTED - vertical lines perfectly vertical, horizontal lines level

FAILURE IS NOT ACCEPTABLE: Every piece of furniture and ceiling light MUST be removed AND all lines MUST be straight."""

            # Retry loop with exponential backoff
            for attempt in range(max_retries):
                try:
                    logger.info(f"Furniture removal attempt {attempt + 1} of {max_retries}")
                    logger.info(
                        f"Sending furniture removal prompt to gemini-3-pro-image-preview with IMAGE output (PIL Image: {pil_image.width}x{pil_image.height})"
                    )

                    # Generate furniture removal with proper asyncio timeout (90 seconds max per attempt)
                    timeout_seconds = 90
                    generated_image = None

                    def _run_generate():
                        """Run the blocking generate_content call in a separate thread"""
                        # Use Gemini 3 Pro Image Preview - better at understanding complex removal tasks
                        # Previously used gemini-2.5-flash-image but it struggled with furniture removal
                        # response_modalities=["IMAGE"] tells the model to output an edited image
                        response = self.genai_client.models.generate_content(
                            model="gemini-3-pro-image-preview",
                            contents=[prompt, pil_image],
                            config=types.GenerateContentConfig(
                                response_modalities=["IMAGE"],
                                temperature=0.2,  # Lower temperature for more consistent removal
                            ),
                        )
                        # Extract and log token usage (workflow_id captured from outer scope)
                        self.extract_usage_metadata(
                            response,
                            operation="remove_furniture",
                            model_override="gemini-3-pro-image-preview",
                            workflow_id=workflow_id,
                            user_id=user_id,
                            session_id=session_id,
                        )

                        result_image = None
                        # Handle different response structures from Google AI SDK
                        # The SDK may return parts directly on response or nested in candidates
                        parts = None
                        if hasattr(response, "parts") and response.parts:
                            parts = response.parts
                        elif hasattr(response, "candidates") and response.candidates:
                            # New SDK structure: response.candidates[0].content.parts
                            candidate = response.candidates[0]
                            if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                                parts = candidate.content.parts

                        if parts:
                            for part in parts:
                                if hasattr(part, "text") and part.text is not None:
                                    logger.info(f"Gemini text response: {part.text[:200]}...")
                                elif hasattr(part, "inline_data") and part.inline_data is not None:
                                    image_data = part.inline_data.data
                                    mime_type = getattr(part.inline_data, "mime_type", None) or "image/png"

                                    if isinstance(image_data, bytes):
                                        # Check first bytes to determine format
                                        # Raw PNG: 89504e47, Raw JPEG: ffd8ff
                                        # Base64 PNG starts with 'iVBORw0K' (bytes: 69 56 42 4f = "iVBO")
                                        # Base64 JPEG starts with '/9j/' (bytes: 2f 39 6a 2f)
                                        first_hex = image_data[:4].hex()
                                        logger.info(f"Image data first 4 bytes hex: {first_hex}")

                                        if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                            # Raw image bytes - encode to base64
                                            logger.info("Raw image bytes detected, encoding to base64")
                                            image_base64_result = base64.b64encode(image_data).decode("utf-8")
                                        else:
                                            # Bytes are base64 string - decode to string directly
                                            logger.info("Base64 string bytes detected, using directly")
                                            image_base64_result = image_data.decode("utf-8")
                                        data_size = len(image_data)
                                    else:
                                        logger.error(f"Unexpected image data type: {type(image_data)}")
                                        continue

                                    result_image = f"data:{mime_type};base64,{image_base64_result}"
                                    logger.info(f"Furniture removal successful on attempt {attempt + 1} ({data_size} bytes)")
                        else:
                            logger.warning(f"Furniture removal response has no parts: {type(response)}")
                        return result_image

                    try:
                        # Run the blocking call in a thread with asyncio timeout
                        loop = asyncio.get_event_loop()
                        generated_image = await asyncio.wait_for(
                            loop.run_in_executor(None, _run_generate), timeout=timeout_seconds
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Furniture removal attempt {attempt + 1} timed out after {timeout_seconds} seconds (asyncio timeout)"
                        )
                        # Continue to next retry attempt
                    except Exception as stream_error:
                        error_str = str(stream_error)
                        # Check if it's a 503 (overloaded) error - retry with longer backoff
                        if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                            if attempt < max_retries - 1:
                                wait_time = 4 * (2**attempt)  # Longer backoff for 503: 4, 8, 16, 32...
                                logger.warning(
                                    f"Model overloaded (503) in furniture removal, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                                )
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                logger.error(f"Furniture removal still failing after {max_retries} retries due to 503")
                        else:
                            logger.error(f"Furniture removal streaming error on attempt {attempt + 1}: {stream_error}")

                    if generated_image:
                        # Furniture removal + perspective correction + angle transformation (if needed) all done in one call
                        logger.info(
                            f"Furniture removal successful on attempt {attempt + 1}, viewing_angle={viewing_angle}, workflow_id={workflow_id}"
                        )
                        return {"image": generated_image, "room_analysis": room_analysis_dict}

                    logger.warning(f"Furniture removal attempt {attempt + 1} produced no image")

                except Exception as e:
                    error_str = str(e)
                    # Check if it's a 503 (overloaded) error - retry with longer backoff
                    if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 4 * (2**attempt)  # Longer backoff for 503: 4, 8, 16, 32...
                            logger.warning(
                                f"Model overloaded (503) in furniture removal, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(
                                f"Furniture removal still failing after {max_retries} retries due to 503: {error_str}"
                            )
                    else:
                        logger.error(f"Furniture removal attempt {attempt + 1} failed: {e}")
                        if attempt < max_retries - 1:
                            # Exponential backoff: 2, 4, 8 seconds for non-503 errors
                            sleep_time = 2 ** (attempt + 1)
                            logger.info(f"Waiting {sleep_time}s before retry...")
                            await asyncio.sleep(sleep_time)
                    continue

            # All retries failed
            logger.error(f"Furniture removal failed after {max_retries} attempts")
            return None

        except Exception as e:
            logger.error(f"Error in furniture removal: {e}", exc_info=True)
            return None

    async def inpaint_product_area(
        self, image_base64: str, bbox: Dict[str, int], product_name: str = "furniture", max_retries: int = 3
    ) -> str:
        """
        Inpaint just the area where a specific product is located.
        This removes only ONE product, keeping all other furniture intact.

        Args:
            image_base64: Base64 encoded visualization image
            bbox: Bounding box of the product to remove {"x", "y", "width", "height"} in pixels
            product_name: Name of product being removed (for prompt context)
            max_retries: Number of retry attempts

        Returns: base64 encoded image with just that product's area inpainted
        """
        try:
            # Remove data URL prefix if present
            if image_base64.startswith("data:image"):
                image_base64 = image_base64.split(",")[1]

            image_bytes = base64.b64decode(image_base64)
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image = ImageOps.exif_transpose(pil_image)
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            img_width, img_height = pil_image.size

            # Expand bbox slightly for better inpainting context
            padding = 20
            x1 = max(0, bbox["x"] - padding)
            y1 = max(0, bbox["y"] - padding)
            x2 = min(img_width, bbox["x"] + bbox["width"] + padding)
            y2 = min(img_height, bbox["y"] + bbox["height"] + padding)

            prompt = f"""Remove ONLY the {product_name} from this specific area of the image.

CRITICAL INSTRUCTIONS:
1. ONLY modify the area around coordinates ({bbox["x"]}, {bbox["y"]}) to ({bbox["x"] + bbox["width"]}, {bbox["y"] + bbox["height"]})
2. Keep ALL other furniture and objects EXACTLY as they are
3. Fill the removed area with appropriate floor/wall texture to match surroundings
4. The result should look natural - as if the {product_name} was never there
5. DO NOT remove or modify any other furniture in the room

The area to inpaint is approximately {bbox["width"]}x{bbox["height"]} pixels starting at ({bbox["x"]}, {bbox["y"]}).
Everything outside this area must remain IDENTICAL to the input image."""

            model = "gemini-3-pro-image-preview"

            for attempt in range(max_retries):
                try:
                    # Use wait_for for Python < 3.11 compatibility
                    response = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.genai_client.models.generate_content(
                                model=model,
                                contents=[prompt, pil_image],
                                config=types.GenerateContentConfig(
                                    response_modalities=["IMAGE", "TEXT"],
                                    temperature=0.2,
                                ),
                            ),
                        ),
                        timeout=60,
                    )
                    # Extract and log token usage
                    self.extract_usage_metadata(response, operation="inpaint_removed_product", model_override=model)

                    if response.candidates:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, "inline_data") and part.inline_data:
                                image_data = part.inline_data.data
                                mime_type = part.inline_data.mime_type or "image/jpeg"

                                if isinstance(image_data, bytes):
                                    first_hex = image_data[:4].hex()
                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        image_b64 = base64.b64encode(image_data).decode("utf-8")
                                    else:
                                        image_b64 = image_data.decode("utf-8")
                                else:
                                    image_b64 = image_data

                                result = f"data:{mime_type};base64,{image_b64}"
                                logger.info(f"[Inpaint] Successfully inpainted area for {product_name}")
                                return result

                except asyncio.TimeoutError:
                    logger.warning(f"[Inpaint] Attempt {attempt + 1} timed out")
                except Exception as e:
                    logger.warning(f"[Inpaint] Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

            # Fallback: return original image if inpainting fails
            logger.warning(f"[Inpaint] All attempts failed, returning original image")
            return f"data:image/jpeg;base64,{image_base64}"

        except Exception as e:
            logger.error(f"[Inpaint] Error: {e}")
            return f"data:image/jpeg;base64,{image_base64}"

    async def remove_products_from_visualization(
        self,
        image_base64: str,
        products_to_remove: List[Dict[str, Any]],
        remaining_products: Optional[List[Dict[str, Any]]] = None,
        max_retries: int = 3,
        user_id: str = None,
        session_id: str = None,
    ) -> Optional[str]:
        """
        Remove specific products from a visualization while preserving everything else.
        Uses centralized VisualizationPrompts for consistent prompt structure.

        Args:
            image_base64: Base64 encoded visualization image
            products_to_remove: List of product dicts with name, quantity, dimensions, and image_url
            remaining_products: List of product dicts that should stay (with dimensions)
            max_retries: Number of retry attempts
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking

        Returns: base64 encoded image with products removed, or None if failed
        """
        try:
            # Extract product names for logging
            product_names = [p.get("full_name") or p.get("name", "item") for p in products_to_remove]
            logger.info(f"[RemoveProducts] Removing {len(products_to_remove)} products: {product_names}")

            # Remove data URL prefix if present
            if image_base64.startswith("data:image"):
                image_base64 = image_base64.split(",")[1]

            image_bytes = base64.b64decode(image_base64)
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image = ImageOps.exif_transpose(pil_image)
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            original_width, original_height = pil_image.size
            logger.info(f"[RemoveProducts] Original image size: {original_width}x{original_height}")

            # Use centralized prompt with dimensions
            prompt = VisualizationPrompts.get_removal_prompt(
                products_to_remove=products_to_remove, remaining_products=remaining_products or []
            )

            # Add resolution requirements
            prompt += f"""

*** IMAGE DIMENSION REQUIREMENTS ***
- Output MUST be EXACTLY {original_width}x{original_height} pixels
- DO NOT change the aspect ratio or crop the image
- The result should look like the room was photographed without the removed items ever being there.
"""

            # LOG THE FULL PROMPT FOR DEBUGGING
            logger.info(f"[RemoveProducts] ========== FULL PROMPT START ==========")
            logger.info(f"[RemoveProducts] Products to remove data: {products_to_remove}")
            logger.info(f"[RemoveProducts] PROMPT:\n{prompt}")
            logger.info(f"[RemoveProducts] ========== FULL PROMPT END ==========")

            model = "gemini-3-pro-image-preview"

            # Start with prompt and room image
            contents = [prompt, pil_image]

            # Add reference images for ALL products to remove with clear color-based labels
            # This helps Gemini visually match what to remove instead of guessing from text
            ref_images_added = 0
            ref_labels = []
            for idx, product in enumerate(products_to_remove):
                if product.get("image_url"):
                    try:
                        product_name = product.get("full_name") or product.get("name", "item")
                        color = product.get("color", "")
                        color_hint = f" (COLOR: {color})" if color else ""

                        ref_image_base64 = await self._download_image(product["image_url"])
                        if ref_image_base64:
                            ref_pil = Image.open(io.BytesIO(base64.b64decode(ref_image_base64)))
                            if ref_pil.mode != "RGB":
                                ref_pil = ref_pil.convert("RGB")

                            # Very explicit label emphasizing this is the item to DELETE
                            label = f"\n\n{'='*60}\nREFERENCE IMAGE - THIS IS THE ITEM TO DELETE:\n{'='*60}\nProduct: '{product_name}'{color_hint}\n\nFIND furniture in the room above that looks like this image.\nOnce found, COMPLETELY ERASE IT from the room image.\n{'='*60}"
                            contents.extend([label, ref_pil])
                            ref_images_added += 1
                            ref_labels.append(label)
                            logger.info(f"[RemoveProducts] Added reference image {idx + 1} for '{product_name}'{color_hint}")
                    except Exception as e:
                        logger.warning(f"[RemoveProducts] Failed to download reference image for {product.get('name')}: {e}")

            logger.info(f"[RemoveProducts] Reference image labels: {ref_labels}")
            logger.info(f"[RemoveProducts] Sending prompt + room image + {ref_images_added} reference image(s)")

            for attempt in range(max_retries):
                try:
                    logger.info(f"[RemoveProducts] Attempt {attempt + 1}/{max_retries}")

                    # Use wait_for for Python < 3.11 compatibility
                    response = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.genai_client.models.generate_content(
                                model=model,
                                contents=contents,
                                config=types.GenerateContentConfig(
                                    response_modalities=["IMAGE", "TEXT"],
                                    temperature=0.2,
                                ),
                            ),
                        ),
                        timeout=90,
                    )
                    # Extract and log token usage
                    self.extract_usage_metadata(
                        response,
                        operation="remove_products_from_visualization",
                        model_override=model,
                        user_id=user_id,
                        session_id=session_id,
                    )

                    if response.candidates:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, "inline_data") and part.inline_data:
                                image_data = part.inline_data.data

                                if isinstance(image_data, bytes):
                                    first_hex = image_data[:4].hex()
                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        image_b64 = base64.b64encode(image_data).decode("utf-8")
                                    else:
                                        image_b64 = image_data.decode("utf-8")
                                else:
                                    image_b64 = image_data

                                # Verify output dimensions
                                try:
                                    result_bytes = base64.b64decode(image_b64)
                                    result_image = Image.open(io.BytesIO(result_bytes))
                                    result_width, result_height = result_image.size
                                    logger.info(
                                        f"[RemoveProducts] Result size: {result_width}x{result_height} "
                                        f"(original: {original_width}x{original_height})"
                                    )

                                    # Resize if dimensions don't match
                                    if result_width != original_width or result_height != original_height:
                                        logger.warning(
                                            f"[RemoveProducts] Resizing output from {result_width}x{result_height} "
                                            f"to {original_width}x{original_height}"
                                        )
                                        result_image = result_image.resize(
                                            (original_width, original_height), Image.Resampling.LANCZOS
                                        )
                                        buffer = io.BytesIO()
                                        result_image.save(buffer, format="JPEG", quality=95)
                                        image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                                except Exception as resize_error:
                                    logger.warning(f"[RemoveProducts] Could not verify/resize output: {resize_error}")

                                logger.info(f"[RemoveProducts] Successfully removed products on attempt {attempt + 1}")
                                return image_b64

                except asyncio.TimeoutError:
                    logger.warning(f"[RemoveProducts] Attempt {attempt + 1} timed out")
                except Exception as e:
                    logger.warning(f"[RemoveProducts] Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

            logger.error(f"[RemoveProducts] All {max_retries} attempts failed")
            return None

        except Exception as e:
            logger.error(f"[RemoveProducts] Error: {e}", exc_info=True)
            return None

    async def generate_add_visualization(
        self,
        room_image: str,
        product_name: str,
        product_image: Optional[str] = None,
        product_color: Optional[str] = None,
        user_id: str = None,
        session_id: str = None,
    ) -> str:
        """
        Generate visualization with product ADDED to room
        Returns: base64 image data

        Args:
            room_image: Base64 encoded room image
            product_name: Name of the product (may include color prefix)
            product_image: URL of product reference image
            product_color: Explicit color from product attributes (e.g., "beige", "cream", "walnut")
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking
        """
        try:
            # Use editing preprocessor to preserve quality for visualization output
            processed_room = self._preprocess_image_for_editing(room_image)

            # Download product image if URL provided
            product_image_data = None
            if product_image:
                try:
                    product_image_data = await self._download_image(product_image)
                except Exception as e:
                    logger.warning(f"Failed to download product image: {e}")

            # Detect if product is a small item (planter, decor, etc.) that tends to cause zoom issues
            product_lower = product_name.lower()

            # Specific detection for planters
            is_planter = any(term in product_lower for term in ["planter", "plant pot", "flower pot", "pot", "succulent"])

            is_small_item = any(
                term in product_lower
                for term in [
                    "planter",
                    "plant",
                    "vase",
                    "flower",
                    "sculpture",
                    "figurine",
                    "candle",
                    "decor",
                    "decorative",
                    "accent",
                    "pot",
                    "succulent",
                ]
            )

            # Build prompt for ADD action
            # Start with absolute critical instruction about camera/zoom
            zoom_warning = """
 CRITICAL INSTRUCTION - READ THIS FIRST
═══════════════════════════════════════════════════════════════
 DO NOT ZOOM IN - THIS IS THE #1 PRIORITY
 DO NOT CHANGE THE CAMERA ANGLE OR PERSPECTIVE
 THE OUTPUT MUST SHOW THE EXACT SAME VIEW AS THE INPUT

The output image MUST be a WIDE SHOT showing the ENTIRE ROOM.
The camera position, angle, and field of view MUST BE IDENTICAL to the input.
If the input shows the full room, the output MUST show the full room.
Adding a small item does NOT mean zooming in on it.
The item you add should be a SMALL part of the overall image.

 IF YOU ZOOM IN OR CROP THE IMAGE, YOU HAVE FAILED
═══════════════════════════════════════════════════════════════

 CRITICAL: DO NOT ADD EXTRA FURNITURE
═══════════════════════════════════════════════════════════════
 ADD ONLY THE ONE SPECIFIC PRODUCT LISTED BELOW
 DO NOT add sofas, chairs, tables, or any other furniture
 DO NOT "complete" or "design" the room
 DO NOT add items you think would look nice
 DO NOT add matching or complementary pieces

YOUR ONLY TASK: Add the ONE product specified below.
The room is ALREADY COMPLETE - it does NOT need more furniture.
If I ask for 1 lamp, add ONLY 1 lamp - nothing else.

 ADDING ANY EXTRA FURNITURE = AUTOMATIC FAILURE
═══════════════════════════════════════════════════════════════

"""

            # Extra warning for small items like planters
            small_item_warning = ""
            if is_small_item:
                small_item_warning = f"""
 SPECIAL WARNING FOR {product_name.upper()}
═══════════════════════════════════════════════════════════════
This is an ACCENT ITEM. Critical rules:
- KEEP THE EXACT SAME CAMERA ANGLE as the input image
- KEEP THE EXACT SAME ASPECT RATIO as the input image
- DO NOT ZOOM IN regardless of the item's size
- Place naturally in the room at its appropriate real-world size
- The room view must remain UNCHANGED - only ADD the item

 ZOOMING IN = AUTOMATIC FAILURE
 CHANGING CAMERA ANGLE = AUTOMATIC FAILURE
 THE FULL ROOM MUST BE VISIBLE IN THE OUTPUT
═══════════════════════════════════════════════════════════════

"""

            # Build prompt with zoom warnings (planters and other small items all use the same structure)
            # Planter-specific placement hints are added below
            planter_placement_hint = ""
            if is_planter:
                planter_placement_hint = """
 PLANTER PLACEMENT GUIDE:
- Place on the floor in an appropriate corner or beside existing furniture
- The planter should be filled with appropriate green foliage
- Add realistic shadows cast by the planter onto the floor
- Planter should be a SMALL accent piece - NOT the focus of the image

"""

            # Build explicit color instruction if color is known
            color_emphasis = ""
            if product_color:
                color_emphasis = f"""
 CRITICAL COLOR REQUIREMENT
═══════════════════════════════════════════════════════════════
THE PRODUCT COLOR IS: **{product_color.upper()}**
- YOU MUST render this product in {product_color.upper()} color
- DO NOT change the color to grey, white, or any other color
- DO NOT "adapt" the color to match the room
- The exact shade/tone from the reference image MUST be preserved
- If the reference shows {product_color}, output MUST show {product_color}
═══════════════════════════════════════════════════════════════

"""

            prompt = f"""{VisualizationPrompts.get_system_intro()}

{zoom_warning}{small_item_warning}{planter_placement_hint}{color_emphasis}ADD the following product to this room in an appropriate location WITHOUT removing any existing furniture:

Product to add: {product_name} (COLOR: {product_color if product_color else 'see reference image'})

 ABSOLUTE REQUIREMENT - ROOM DIMENSIONS
═══════════════════════════════════════════════════════════════
THE OUTPUT IMAGE MUST HAVE THE EXACT SAME DIMENSIONS AS THE INPUT IMAGE.
- If input is 1024x768 pixels → output MUST be 1024x768 pixels
- If input is 800x600 pixels → output MUST be 800x600 pixels
- NEVER change the aspect ratio
- NEVER crop, resize, or alter the image dimensions in ANY way
- The room's physical proportions (length, width, height) MUST appear IDENTICAL
- The camera angle, perspective, and field of view MUST remain UNCHANGED
- DO NOT zoom in or out
- DO NOT change the viewing angle
- The walls must be in the EXACT same positions
- The floor area must appear the EXACT same size

 IF THE OUTPUT IMAGE HAS DIFFERENT DIMENSIONS THAN THE INPUT, YOU HAVE FAILED THE TASK
═══════════════════════════════════════════════════════════════

 ABSOLUTE REQUIREMENT - EXISTING FURNITURE SIZE PRESERVATION
═══════════════════════════════════════════════════════════════
ALL EXISTING FURNITURE MUST REMAIN THE EXACT SAME SIZE AND SCALE:
-  NEVER make existing furniture (sofas, chairs, tables) appear larger or smaller
-  NEVER expand the room to accommodate new items
-  NEVER shrink existing furniture to make space for new items
-  NEVER change the perspective to make the room appear larger
-  The sofa that was 6 feet wide MUST still appear 6 feet wide
-  The coffee table that was 4 feet long MUST still appear 4 feet long
-  All proportions between existing objects MUST remain IDENTICAL

 TRUE SIZE REPRESENTATION:
- New furniture must be added at its REAL-WORLD proportional size
- A new 3-seater sofa should look proportional to an existing 3-seater sofa
- A new side table should look smaller than an existing dining table
- Use the existing furniture as SIZE REFERENCE for new items
- Do NOT artificially shrink new products to fit - if they don't fit, they don't fit

 ROOM EXPANSION IS FORBIDDEN:
- The room boundaries (walls, floor, ceiling) are FIXED
- Do NOT push walls back to create more space
- Do NOT make the ceiling appear higher
- Do NOT extend the floor area
- The room's cubic volume must remain IDENTICAL
- If there's not enough space for the product, do NOT modify the room

 IF EXISTING FURNITURE CHANGES SIZE OR ROOM EXPANDS, YOU HAVE FAILED THE TASK
═══════════════════════════════════════════════════════════════

 CRITICAL PRESERVATION RULES:
1. KEEP ALL EXISTING FURNITURE: Do NOT remove, move, or replace any furniture currently in the room
2.  ESPECIALLY PRESERVE SOFAS: If there is a sofa/couch in the room, it MUST remain in its EXACT position
3.  PRESERVE EXISTING COLORS: Do NOT change the color of ANY existing furniture or decor in the room
4. PRESERVE THE ROOM: Keep the same walls, windows, floors, ceiling, lighting, and camera angle
5. ROOM SIZE UNCHANGED: The room must look the EXACT same size

 WALL & FLOOR COLOR PRESERVATION - ABSOLUTE REQUIREMENT
 DO NOT CHANGE THE WALL COLOR - walls must remain EXACTLY the same color as input
 DO NOT CHANGE THE FLOOR COLOR - flooring must remain EXACTLY the same color/material as input
 DO NOT add paint, wallpaper, or any wall treatment that wasn't there
 DO NOT change flooring material, color, or texture
- If walls are white → output walls MUST be white
- If walls are grey → output walls MUST be grey
- If floor is wooden → output floor MUST be the SAME wooden color
- The room's color scheme is FIXED - you are ONLY adding furniture - not bigger, not smaller

 PIXEL-LEVEL POSITION PRESERVATION - CRITICAL
- Every piece of existing furniture must be at the EXACT SAME PIXEL COORDINATES as in the input
- If a sofa's left edge starts at pixel X=100 in the input, it MUST start at X=100 in the output
- DO NOT shift, nudge, or adjust the position of ANY existing furniture - not even by a few pixels
- The silhouette/outline of every existing furniture piece must PERFECTLY OVERLAY the input image
- Think of it as: existing furniture is "locked in place" - you can only ADD new items around them

 PLACEMENT RESTRICTIONS - VERY IMPORTANT
1.  ONLY place new items in VISIBLE EMPTY SPACES - spaces that are clearly visible and unobstructed
2.  NEVER place furniture BEHIND other furniture (e.g., NO bookshelf behind a sofa - it would be hidden!)
3.  NEVER place items where they would be COVERED or BLOCKED by existing furniture
4.  Place items NEXT TO existing furniture (beside the sofa, not behind it)
5.  Place items in OPEN FLOOR AREAS visible to the camera
6.  Place items AGAINST VISIBLE WALLS (not walls blocked by sofas/beds)
7. Bookshelves, cabinets, and tall furniture must be placed against OPEN walls where they are FULLY VISIBLE

 WALL ART / PAINTINGS RULE:
- If adding wall art and room ALREADY has paintings → Place new art on a DIFFERENT wall or different position
- DO NOT replace existing paintings - ADD alongside them (gallery-style)
- Existing artwork must REMAIN VISIBLE

 FURNITURE YOU MUST NEVER REMOVE:
- Sofas/couches (main seating)
- Beds
- Existing accent chairs
- Existing wall art/paintings
- Any furniture that was in the input image

 YOUR TASK:
- Add the {product_name} to this room
- Place it in an appropriate empty location
- Do NOT remove or replace any existing furniture
- Keep the room structure 100% identical
- Keep the room DIMENSIONS 100% identical
- Ensure the product looks naturally integrated with proper lighting and shadows

 EXACT PRODUCT REPLICATION - MANDATORY
═══════════════════════════════════════════════════════════════
If a product reference image is provided, you MUST render the EXACT SAME product:

1.  EXACT COLOR - The color in output MUST match the reference image precisely
   - If reference shows light gray, render LIGHT GRAY (not dark gray, not beige)
   - If reference shows walnut wood, render WALNUT WOOD (not oak, not black)

2.  EXACT MATERIAL & TEXTURE - Replicate the exact material appearance
   - Velvet → Velvet, Leather → Leather, Wood grain → Same wood grain

3.  EXACT SHAPE & DESIGN - Match the reference's silhouette and design
   - Same arm style, same leg style, same proportions

4.  EXACT STYLE - Keep the same style character
   - Modern → Modern, Traditional → Traditional, Mid-century → Mid-century

 CRITICAL: The product in the output MUST look like the SAME EXACT product from the reference image.
 DO NOT generate a "similar" or "inspired by" version
 DO NOT change colors to "match the room better"
 COPY the EXACT appearance from the product reference image
═══════════════════════════════════════════════════════════════

PLACEMENT GUIDELINES:

 SOFAS:
- Place DIRECTLY AGAINST the wall with MINIMAL GAP (2-4 inches max)
-  DO NOT leave large empty space between sofa back and wall
- The sofa's back should be nearly touching the wall
- Position as the main seating piece, centered on the wall or in the room
- Real sofas sit flush against walls - replicate this realistic placement

 CHAIRS (accent chair, side chair, armchair, sofa chair, dining chair, recliner):
- Position on ONE OF THE SIDES of the existing sofa (if sofa exists)
- Angle the chair towards the sofa to create a conversation area
- Maintain 18-30 inches spacing from the sofa
- Style and orient the chair based on the sofa's position and facing direction
- If no sofa exists, place along a wall or in a natural seating position

 CENTER TABLE / COFFEE TABLE:
- Place DIRECTLY IN FRONT OF the sofa or seating area
- Centered between the sofa and the opposite wall/furniture
- Positioned in the "coffee table zone" (perpendicular to sofa's front face)

 OTTOMAN:
- Place DIRECTLY IN FRONT OF the sofa, similar to a coffee table
- Can be centered or slightly offset based on room layout
- Should be 14-18 inches from sofa's front edge
- Ottomans are used as footrests or extra seating, NOT as sofa replacements
-  NEVER remove or replace the sofa when adding an ottoman

 SIDE TABLE / END TABLE:
-  CRITICAL: Place DIRECTLY ADJACENT to the sofa's SIDE (at the armrest)
-  The table must be FLUSH with the sofa's side, not in front or behind
- Position at the SAME DEPTH as the sofa (aligned with sofa's length, not width)
- Should be at ARM'S REACH from someone sitting on the sofa
- Think: "side by side" positioning, not "in front and to the side"
-  INCORRECT: Placing table in front of the sofa but shifted to the side
-  CORRECT: Placing table directly touching or very close to sofa's side panel/armrest

 CONSOLE TABLE / ENTRYWAY TABLE / FOYER TABLE:
-  ABSOLUTE RULE: Console tables are COMPLETELY DIFFERENT from sofas - NEVER remove a sofa when adding a console
- Console tables are NARROW, LONG tables that go AGAINST A WALL (not in front of seating)
- Place against an empty wall space, NOT in the seating area
- Typical placement: behind a sofa (against wall), in entryways, hallways, or against any bare wall
- Console tables are ACCENT furniture - they do NOT replace ANY seating furniture
-  CRITICAL: If there is a sofa in the room, it MUST remain - console tables are ADDITIONAL furniture
- Console tables are typically 28-32 inches tall and very narrow (12-18 inches deep)

 LAMPS:
- Place on an existing table or directly on the floor (for floor lamps)

 BEDS:
- Place against a wall

 FLOOR PLANTERS / TALL PLANTS (floor-standing decorative items):
 CRITICAL FOR PLANTERS - DO NOT ZOOM
-  ABSOLUTE RULE: The output image MUST show THE ENTIRE ROOM - NOT a close-up of the planter
-  The planter is a TINY ACCENT piece - it should be BARELY NOTICEABLE in the image
-  The planter should appear SMALL in the corner or edge of the image, NOT in the center
-  NEVER zoom in, crop, or focus on the planter
-  The camera view MUST BE IDENTICAL to the input image - same angle, same distance, same field of view
- Place in a FAR CORNER, next to furniture (against a wall), or tucked beside existing items
- The planter should occupy LESS than 5-10% of the visible image area
- Keep planters proportionally SMALL relative to furniture (floor planters are typically 2-3 feet tall MAX)
- Large/tall planters: place in a FAR CORNER of the room, NOT in the center or foreground
-  WRONG: Zooming in to show planter details - this FAILS the task
-  WRONG: Planter appearing large or prominent in the image
-  CORRECT: Full room view with tiny planter visible in corner/edge
- The ENTIRE input room must be visible in the output - planter is just a small addition

 CUSHIONS / PILLOWS / THROW PILLOWS / DECORATIVE PILLOWS:
 CRITICAL - CUSHIONS GO ON EXISTING FURNITURE, NOT BESIDE IT
-  Cushions and pillows must be placed DIRECTLY ON the sofa/couch/chair - sitting on the seat or leaning against the backrest
-  The sofa/furniture MUST REMAIN IN ITS EXACT POSITION - do NOT move the sofa to accommodate cushions
-  Cushions are SMALL accessories (typically 16-22 inches) that sit ON furniture
- Place cushions in corners of the sofa, against armrests, or centered on seat cushions
- Arrange cushions naturally as if someone just placed them - slightly angled, varied positions
-  ABSOLUTELY FORBIDDEN: Moving, shifting, or repositioning the sofa when adding cushions
-  WRONG: Placing cushions on the floor next to the sofa
-  WRONG: Moving the sofa to a different position to "make room" for cushions
-  CORRECT: Cushions placed directly on the existing sofa, sofa stays in EXACT same position

 THROWS / BLANKETS / THROW BLANKETS:
- Place draped over the arm of a sofa/chair OR folded on the seat
- The furniture underneath MUST NOT MOVE - the throw just sits on top of it
-  WRONG: Moving furniture to accommodate a throw

 TABLETOP DECOR (vases, flower bunches, flower arrangements, decorative objects):
 CRITICAL - PLACE ON TABLE SURFACES, NOT ON FLOOR
-  These are SMALL tabletop items - they belong ON coffee tables, center tables, side tables, console tables, dining tables
-  NEVER replace furniture (sofas, chairs) with decor items - ADD decor ON existing table surfaces
-  Look for table surfaces in the room and place the decor item ON TOP of them
- Preferred surfaces: 1) Coffee/center table 2) Side table 3) Console table 4) Dining table 5) Shelf/mantel
- If no table exists: place on visible shelves, windowsills, or mantels
- Keep proportions realistic - these items are typically 10-30cm tall
-  WRONG: Replacing a sofa with a vase - this is COMPLETELY INCORRECT
-  WRONG: Placing a flower bunch on the floor
-  CORRECT: A small vase sitting on the center coffee table

 SCULPTURES / FIGURINES / DECORATIVE STATUES:
 CRITICAL - PLACEMENT PRIORITY FOR SCULPTURES
-  FIRST PRIORITY: Place on the CENTER TABLE / COFFEE TABLE (in front of sofa)
-  SECOND PRIORITY: If center table is full or doesn't exist, place on a SIDE TABLE
-  THIRD PRIORITY: If no tables available, place on console table, shelf, or mantel
- Sculptures are decorative accent pieces - they should be PROMINENTLY visible on table surfaces
- Position the sculpture facing the camera/viewer for best visual impact
- Keep proportions realistic - tabletop sculptures are typically 15-40cm tall
-  WRONG: Placing sculpture on the floor
-  WRONG: Hiding sculpture in a corner
-  CORRECT: Sculpture placed centrally on the coffee table as a focal point

 WALL ART / MIRRORS / DECORATIVE ITEMS:
- Mount on walls at appropriate eye level
- These are accent pieces - maintain the full room view
- DO NOT zoom in on decorative items

 SPACING:
- Maintain realistic spacing and proportions
- Side tables should be 0-6 inches from sofa's side
- Center tables should be 14-18 inches from sofa's front

 MANDATORY FRONT ANGLE REQUIREMENT:
═══════════════════════════════════════════════════════════════
 THE PRODUCT MUST ALWAYS SHOW ITS FRONT FACE TOWARDS THE CAMERA
- Sofas: Show the front cushions/seating area facing the camera, NOT the back
- Tables: Show the front/main side facing the camera
- Chairs: Show the front/seating side facing the camera, NOT the back
- Cabinets/Storage: Show the doors/drawers facing the camera
- Lamps: Show the shade opening or decorative front facing the camera
- All furniture: The primary viewing angle (how it appears in showrooms) must face the camera

 INCORRECT ANGLES:
- Showing the back of a sofa (you should see cushions, not the sofa back panel)
- Showing a chair from behind (you should see the seat, not the chair back)
- Showing a table from a sharp side angle (you should see the full tabletop)
- Placing furniture facing away from the camera view

 CORRECT ANGLES:
- Products oriented so their "front" (showroom display angle) faces the camera
- User should clearly see what the product looks like from its best viewing angle
- The product should appear as it would in a furniture catalog - front and center
═══════════════════════════════════════════════════════════════

 CRITICAL LIGHTING REQUIREMENTS:
 THE PRODUCT MUST LOOK LIKE IT IS PART OF THE ROOM, NOT ADDED ON TOP OF IT
1. ANALYZE the room's lighting: identify light sources, direction, color temperature (warm/cool)
2. MATCH lighting on the product: highlights must come from the same direction as room lighting
3. MATCH shadow direction: product shadow must fall in the same direction as other shadows in room
4. MATCH exposure: product should NOT be brighter or darker than similar surfaces in room
5. NO "SPOTLIGHT" EFFECT: product must NOT look highlighted compared to the room
6. SEAMLESS BLEND: a viewer should NOT be able to tell the product was digitally added

OUTPUT: One photorealistic image showing THE ENTIRE ROOM (same wide-angle view as input) with the {product_name} added naturally.
 FOR PLANTERS/PLANTS: The planter must appear SMALL (5-10% of image) in a FAR CORNER - DO NOT zoom in or make it prominent!
 SIZE PRESERVATION: All existing furniture MUST remain THE EXACT SAME SIZE - no enlarging, no shrinking. The room MUST NOT expand or change shape.
The room structure, walls, and camera angle MUST be identical to the input image. DO NOT zoom in or crop - the output MUST show the exact same room view as the input. The product should be visible but NOT dominate the image - show the full room context."""

            # Build contents list with PIL Images (same approach as furniture removal)
            contents = [prompt]

            # Add room image as PIL Image
            room_image_bytes = base64.b64decode(processed_room)
            room_pil_image = Image.open(io.BytesIO(room_image_bytes))
            # Apply EXIF orientation correction (important for smartphone photos)
            room_pil_image = ImageOps.exif_transpose(room_pil_image)
            if room_pil_image.mode != "RGB":
                room_pil_image = room_pil_image.convert("RGB")

            # Get the input image dimensions for logging
            input_width, input_height = room_pil_image.size
            logger.info(f"Input room image (EXIF corrected): {input_width}x{input_height}")

            contents.append(room_pil_image)

            # Add product reference image if available
            if product_image_data:
                contents.append(f"\nProduct reference image ({product_name}):")
                prod_image_bytes = base64.b64decode(product_image_data)
                prod_pil_image = Image.open(io.BytesIO(prod_image_bytes))
                if prod_pil_image.mode != "RGB":
                    prod_pil_image = prod_pil_image.convert("RGB")
                contents.append(prod_pil_image)

            # Generate visualization with Gemini 3 Pro Image (Nano Banana Pro)
            # Use HIGH media resolution for better quality output
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.3,
            )

            # Retry configuration with timeout protection
            max_retries = 3
            timeout_seconds = 90

            def _run_generate_add():
                """Run the streaming generation in a thread for timeout support."""
                result_image = None
                final_chunk = None  # Capture final chunk for usage_metadata
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
                    final_chunk = chunk  # Always keep reference to last chunk
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                        for part in chunk.candidates[0].content.parts:
                            if part.inline_data and part.inline_data.data:
                                image_data = part.inline_data.data
                                mime_type = part.inline_data.mime_type or "image/png"

                                # Handle both raw bytes and base64 string bytes
                                # (google-genai SDK may return either format)
                                if isinstance(image_data, bytes):
                                    first_hex = image_data[:4].hex()
                                    logger.info(f"ADD visualization first 4 bytes hex: {first_hex}")

                                    # Check if raw image bytes (PNG starts with 89504e47, JPEG with ffd8ff)
                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        # Raw image bytes - encode to base64
                                        image_base64 = base64.b64encode(image_data).decode("utf-8")
                                        logger.info("ADD: Raw image bytes detected, encoded to base64")
                                    else:
                                        # Bytes are likely base64 string - decode to string directly
                                        image_base64 = image_data.decode("utf-8")
                                        logger.info("ADD: Base64 string bytes detected, decoded directly")
                                else:
                                    # Already a string
                                    image_base64 = image_data
                                    logger.info("ADD: String data received directly")

                                result_image = f"data:{mime_type};base64,{image_base64}"
                                logger.info("Generated ADD visualization")
                return (result_image, final_chunk)  # Return tuple with final chunk for token tracking

            generated_image = None
            final_chunk = None
            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(loop.run_in_executor(None, _run_generate_add), timeout=timeout_seconds)
                    if result:
                        generated_image, final_chunk = result
                    if generated_image:
                        break
                except asyncio.TimeoutError:
                    logger.warning(f"ADD visualization attempt {attempt + 1} timed out after {timeout_seconds}s")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)  # Exponential backoff: 2, 4, 8 seconds
                        logger.info(f"Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    continue
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a 503 (overloaded) error - retry with longer backoff
                    if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 4 * (2**attempt)  # Longer backoff for 503: 4, 8, 16 seconds
                            logger.warning(
                                f"ADD visualization: Model overloaded (503), retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                    logger.error(f"ADD visualization attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        await asyncio.sleep(wait_time)
                    continue

            if not generated_image:
                logger.error(f"AI failed to generate ADD visualization after {max_retries} attempts")
                raise ValueError("AI failed to generate visualization image")

            # Log visualization operation with token tracking from final chunk
            self._log_streaming_operation(
                "generate_add_visualization",
                "gemini-3-pro-image-preview",
                final_chunk=final_chunk,
                user_id=user_id,
                session_id=session_id,
            )

            return generated_image

        except ValueError:
            # Re-raise ValueError for proper handling
            raise
        except Exception as e:
            logger.error(f"Error generating ADD visualization: {e}")
            raise ValueError(f"Visualization generation failed: {e}")

    async def generate_add_multiple_visualization(
        self,
        room_image: str,
        products: list[dict],
        existing_products: Optional[list[dict]] = None,
        workflow_id: str = None,
        user_id: str = None,
        session_id: str = None,
        wall_color: Optional[dict] = None,
        texture_image: str = None,
        texture_name: str = None,
        texture_type: str = None,
        tile_swatch_image: str = None,
        tile_name: str = None,
        tile_size: str = None,
        tile_finish: str = None,
        tile_width_mm: int = None,
        tile_height_mm: int = None,
    ) -> str:
        """
        Generate visualization with MULTIPLE products added to room in a SINGLE API call.
        This is more efficient than calling generate_add_visualization multiple times.
        Can also apply wall texture and floor tile in the same call.

        Args:
            room_image: Base64 encoded room image
            products: List of dicts with 'name' and optional 'image_url' keys (NEW products to add)
            existing_products: List of dicts for products ALREADY in the room image that must be preserved
            workflow_id: Optional workflow ID for tracking all API calls from a single user action
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking
            wall_color: Optional dict with 'name', 'code', 'hex_value' for wall color to apply
            texture_image: Base64 swatch image for wall texture
            texture_name: Name of the texture (e.g. "Basket")
            texture_type: Type of texture (e.g. "marble")
            tile_swatch_image: Base64 swatch image for floor tile
            tile_name: Name of the floor tile (e.g. "Carrara Marble")
            tile_size: Size description (e.g. "1200x1800 mm")
            tile_finish: Finish type (e.g. "Glossy")
            tile_width_mm: Tile width in millimeters
            tile_height_mm: Tile height in millimeters

        Returns: base64 image data
        """
        # Allow wall-color-only or surface-only visualization (no products)
        has_surfaces = texture_image or tile_swatch_image
        if not products and not wall_color and not has_surfaces:
            return room_image

        existing_products = existing_products or []
        products = products or []  # Ensure products is a list even if None

        # Calculate total items considering quantity
        total_items = sum(p.get("quantity", 1) for p in products)

        # If only one item total (single product with quantity=1) AND no existing products to preserve,
        # AND no wall color to apply, use the simpler single product method.
        # If there are existing products or wall color, we need the full multi-product method.
        if len(products) == 1 and total_items == 1 and not existing_products and not wall_color and not has_surfaces:
            return await self.generate_add_visualization(
                room_image=room_image,
                product_name=products[0].get("full_name") or products[0].get("name"),
                product_image=products[0].get("image_url"),
            )

        # Log what we're doing
        surface_desc = []
        if texture_image:
            surface_desc.append(f"texture={texture_name}")
        if tile_swatch_image:
            surface_desc.append(f"tile={tile_name}")
        surface_log = f" + {', '.join(surface_desc)}" if surface_desc else ""

        if not products and (wall_color or has_surfaces):
            logger.info(f" SURFACE ONLY: wall_color={wall_color.get('name') if wall_color else None}{surface_log}")
        elif wall_color or has_surfaces:
            logger.info(
                f" ADD MULTIPLE + SURFACES: {len(products)} products, {total_items} total items + wall_color={wall_color.get('name') if wall_color else None}{surface_log}"
            )
        else:
            logger.info(f" ADD MULTIPLE: {len(products)} products, {total_items} total items to place")

        try:
            import time

            timing_start = time.time()

            # Use editing preprocessor to preserve quality for visualization output
            processed_room = self._preprocess_image_for_editing(room_image)
            logger.info(f" [TIMING] Image preprocessing took {time.time() - timing_start:.2f}s")

            # Download all product images
            download_start = time.time()
            product_images_data = []
            product_entries = []  # List of (name, quantity) tuples
            total_items_to_add = 0

            for product in products:
                name = product.get("full_name") or product.get("name")
                quantity = product.get("quantity", 1)
                total_items_to_add += quantity

                # Extract dimensions for product
                dimensions = product.get("dimensions", {})
                dim_parts = []
                if dimensions.get("width"):
                    dim_parts.append(f'{dimensions["width"]}" W')
                if dimensions.get("depth"):
                    dim_parts.append(f'{dimensions["depth"]}" D')
                if dimensions.get("height"):
                    dim_parts.append(f'{dimensions["height"]}" H')
                dim_str = " x ".join(dim_parts) if dim_parts else None

                product_entries.append((name, quantity, dim_str))

                image_url = product.get("image_url")
                image_data = None
                if image_url:
                    try:
                        image_data = await self._download_image(image_url)
                        if image_data:
                            logger.info(
                                f" Downloaded product image for '{name}': {len(image_data)} bytes from {image_url[:100]}..."
                            )
                        else:
                            logger.warning(f" No image data returned for '{name}' from {image_url[:100]}...")
                    except Exception as e:
                        logger.warning(f" Failed to download product image for '{name}': {e}")
                else:
                    logger.warning(f" No image_url provided for product '{name}' - AI won't have visual reference!")
                product_images_data.append(image_data)

            logger.info(
                f" [TIMING] Product image downloads took {time.time() - download_start:.2f}s for {len(products)} products"
            )

            # Build product list for prompt with quantities and dimensions - VERY EXPLICIT about counts
            product_list_items = []
            item_number = 1
            for name, qty, dim_str in product_entries:
                dim_info = f" [{dim_str}]" if dim_str else ""
                if qty > 1:
                    # List each copy as a separate numbered item to make it crystal clear
                    for copy_num in range(1, qty + 1):
                        product_list_items.append(f"  {item_number}. {name}{dim_info} (copy {copy_num} of {qty})")
                        item_number += 1
                else:
                    product_list_items.append(f"  {item_number}. {name}{dim_info}")
                    item_number += 1
            product_list = "\n".join(product_list_items)

            # Also build a summary showing counts per product type with dimensions
            product_summary = []
            for name, qty, dim_str in product_entries:
                dim_info = f" ({dim_str})" if dim_str else ""
                product_summary.append(f"   • {name}{dim_info}: {qty} {'copies' if qty > 1 else 'copy'}")
            product_summary_str = "\n".join(product_summary)

            logger.info(f"Product list for prompt ({total_items_to_add} items):\n{product_list}")

            # Build list of EXISTING products that MUST be preserved (already in the base image)
            existing_products_list = []
            existing_products_warning = ""
            if existing_products:
                for ep in existing_products:
                    ep_name = ep.get("full_name") or ep.get("name", "Unknown product")
                    ep_qty = ep.get("quantity", 1)
                    existing_products_list.append(f"   • {ep_name}: {ep_qty} {'copies' if ep_qty > 1 else 'copy'}")
                existing_products_str = "\n".join(existing_products_list)
                existing_products_warning = f"""
 CRITICAL: PRODUCTS ALREADY IN THIS IMAGE - DO NOT REMOVE OR REPLACE
═══════════════════════════════════════════════════════════════════════════════

The following products are ALREADY RENDERED in this image and MUST stay EXACTLY as they are:
{existing_products_str}

 ABSOLUTE RULES FOR EXISTING PRODUCTS:
1. DO NOT remove any of the above products
2. DO NOT replace any of the above products with new products
3. DO NOT move any of the above products to different locations
4. DO NOT change the appearance, color, or style of existing products
5. These products MUST remain EXACTLY where they are in the image

 YOUR TASK: Add NEW products while PRESERVING ALL existing products above.

═══════════════════════════════════════════════════════════════════════════════

"""
                logger.info(
                    f"Existing products to preserve: {', '.join([ep.get('name', 'Unknown') for ep in existing_products])}"
                )

            # Build product names list for legacy compatibility
            product_names = [entry[0] for entry in product_entries]

            # Check if any product has quantity > 1
            has_multiple_copies = any(qty > 1 for _, qty, _ in product_entries)
            multiple_instance_instruction = ""

            # Base instruction to prevent adding extra furniture (applies to ALL cases)
            # Build explicit list of product names for reference
            allowed_product_names = ", ".join([entry[0] for entry in product_entries])
            no_extra_furniture_warning = f"""
 ABSOLUTELY CRITICAL: DO NOT ADD ANY EXTRA FURNITURE
═══════════════════════════════════════════════════════════════════════

 FORBIDDEN - DO NOT ADD ANY OF THESE:
- NO extra chairs (accent chairs, armchairs, dining chairs, single seaters)
- NO extra cushions or pillows beyond what's listed
- NO extra sofas or sectionals
- NO extra tables (coffee tables, side tables, dining tables)
- NO extra lamps or lighting
- NO extra plants or planters beyond what's listed
- NO extra rugs or carpets
- NO extra wall art or decorations beyond what's listed
- NO extra stools, benches, or ottomans beyond what's listed

 ONLY THESE SPECIFIC PRODUCTS ARE ALLOWED: {allowed_product_names}

 CRITICAL RULES:
1. ADD ONLY the EXACT products listed below - NOTHING ELSE
2. The room may ALREADY have furniture - DO NOT duplicate what you see
3. DO NOT "complete" or "design" the room - it's already complete
4. DO NOT add items you think would look nice or match
5. If you see similar furniture in the image, DO NOT add more of it

YOUR ONLY TASK: Add EXACTLY the products listed below - NOTHING MORE.
The room is ALREADY DESIGNED - it does NOT need additional furniture.

 ADDING ANY UNLISTED FURNITURE = AUTOMATIC FAILURE
 ADDING DUPLICATES OF EXISTING ITEMS = AUTOMATIC FAILURE
═══════════════════════════════════════════════════════════════════════

"""

            # For single items, add explicit instruction NOT to add extras
            if total_items_to_add == 1 and not has_multiple_copies:
                single_item_name = product_entries[0][0] if product_entries else "item"
                multiple_instance_instruction = f"""{no_extra_furniture_warning}
 CRITICAL: ADD EXACTLY 1 ITEM - NO MORE, NO LESS
═══════════════════════════════════════════════════════════════════════

 YOU MUST ADD EXACTLY 1 (ONE) {single_item_name.upper()}

 DO NOT:
- Add 2 or more of this item
- Create duplicates or similar-looking items
- Add any matching/complementary pieces
- Add ANY other furniture (sofas, chairs, tables, etc.)

 DO:
- Add ONLY 1 (ONE) single item
- Place it in ONE appropriate location
- Keep ALL existing furniture EXACTLY as it is

COUNT CHECK: Your output should have exactly 1 new {single_item_name} added.
═══════════════════════════════════════════════════════════════════════

"""
            elif has_multiple_copies:
                logger.info(f" MULTIPLE COPIES REQUESTED: {total_items_to_add} total items from {len(products)} products")
                # Build instruction for multiple copies - use the summary we already built
                multiple_instance_instruction = f"""{no_extra_furniture_warning}
 CRITICAL: YOU MUST ADD MULTIPLE COPIES OF SOME PRODUCTS
═══════════════════════════════════════════════════════════════════════

 QUANTITY REQUIREMENTS - READ CAREFULLY:
{product_summary_str}

 TOTAL ITEMS YOU MUST PLACE: {total_items_to_add}

 FAILURE CONDITIONS (DO NOT DO THIS):
- Adding only 1 item when 2+ copies are required
- Ignoring the quantity requirements
- Placing fewer items than specified
- Adding ANY furniture not in the list above (sofas, chairs, tables, etc.)

 SUCCESS CONDITIONS (DO THIS):
- Count EXACTLY {total_items_to_add} separate items in your output
- For chairs with qty=2: Place BOTH chairs SIDE BY SIDE (next to each other, facing the same direction)
- For cushions with qty=2+: Place ALL cushions on the sofa or seating
- Each copy should be in a DIFFERENT location but same style/color
- DO NOT add any furniture not specified in the list

 CHAIR PLACEMENT FOR MULTIPLE COPIES:
- 2 accent chairs → Place SIDE BY SIDE (next to each other, facing the same direction)
- 2+ dining chairs → Arrange evenly around the dining table

 BENCH PLACEMENT:
-  DO NOT REMOVE existing furniture - find available empty space first
-  LIVING ROOM: Place bench ACROSS from the sofa (on the OPPOSITE side, facing the sofa)
  - Position bench so it faces the sofa, creating a conversation area
  - Maintain 3-4 feet distance from sofa
-  BEDROOM: Place bench at the FOOT OF THE BED (next to the footrest area)
  - Position parallel to the foot of the bed
  - Can also be placed at the end of the bed facing outward
-  NEVER place directly in front of sofa blocking the coffee table area
-  NEVER remove or replace existing chairs/furniture to make room for the bench
═══════════════════════════════════════════════════════════════════════

"""
            else:
                # Multiple different products without multiple copies of any single product
                multiple_instance_instruction = f"""{no_extra_furniture_warning}
 ADD EXACTLY THESE {total_items_to_add} ITEMS - NO MORE, NO LESS
═══════════════════════════════════════════════════════════════════════

Items to add:
{product_summary_str}

 DO NOT add any items not in this list
 DO NOT add sofas, chairs, tables, or furniture not specified
 The room is ALREADY COMPLETE

═══════════════════════════════════════════════════════════════════════

"""

            # Check if any product is a planter
            has_planter = any(
                any(term in name.lower() for term in ["planter", "plant pot", "flower pot", "pot", "succulent"])
                for name in product_names
            )

            # Planter-specific instruction
            planter_instruction = ""
            if has_planter:
                planter_instruction = """
 PLANTER-SPECIFIC INSTRUCTION
═══════════════════════════════════════════════════════════════
For any planter being added:

THE ORIGINAL ASPECT RATIO AND VIEWING ANGLE OF THE IMAGE SHOULD REMAIN THE SAME.
THE EXISTING PRODUCTS IN THE ROOM SHOULD BE CLEARLY VISIBLE AND NOT CUT FROM VIEW.
THE IMAGE SHOULD NOT BE ZOOMED IN.
THE CAMERA ANGLE SHOULD BE THE SAME.
DO NOT CROP OR CUT ANY EXISTING FURNITURE FROM THE IMAGE.

 PLANTER PLACEMENT RULES:
-  NEVER place a planter IN FRONT OF the sofa or any seating — it blocks the view
-  NEVER place a planter in the CENTER of the room or in walkways
-  Place planters in FAR CORNERS of the room
-  Place planters BESIDE (to the LEFT or RIGHT of) sofas/chairs, NOT in front
-  Place planters against walls in empty spaces
- The planter is a SMALL accent piece — it should NOT block or obscure any furniture
═══════════════════════════════════════════════════════════════

"""

            # Build wall color instruction based on whether wall_color is provided
            # Texture overrides wall color (they are mutually exclusive for walls)
            if texture_image and texture_name:
                # Texture is being applied — skip wall color instruction, texture handles walls
                wall_color_instruction = ""
            elif wall_color:
                color_name = wall_color.get("name", "Unknown")
                color_code = wall_color.get("code", "")
                color_hex = wall_color.get("hex_value", "")
                logger.info(f" WALL COLOR REQUESTED: {color_name} ({color_code}) - {color_hex}")
                wall_color_instruction = f""" WALL COLOR CHANGE - APPLY NEW WALL COLOR
Paint ALL visible walls with the following color:

 WALL COLOR TO APPLY:
- Name: {color_name} (Asian Paints)
- Code: {color_code}
- Hex Reference: {color_hex}

 WALL COLOR APPLICATION RULES:
1. Paint ALL visible wall surfaces with this color
2. Apply the color uniformly across all walls
3. Maintain realistic matte/satin paint finish
4. Preserve natural shadows and lighting on walls
5. The color should be a close match to the hex value provided

 DO NOT change the ceiling color - ceiling remains as-is
 DO NOT change window frames, door frames, or trim
 DO NOT add textures, patterns, or wallpaper - just solid paint color"""
            else:
                wall_color_instruction = """ WALL COLOR PRESERVATION - ABSOLUTE REQUIREMENT
 DO NOT CHANGE THE WALL COLOR - walls must remain EXACTLY the same color as input
 DO NOT add paint, wallpaper, or any wall treatment that wasn't there
- If walls are white → output walls MUST be white
- If walls are grey → output walls MUST be grey
- The wall color scheme is FIXED - you are ONLY adding furniture"""

            # Build surface instructions for texture and/or floor tile
            surface_instructions = ""

            if texture_image and texture_name:
                surface_instructions += f"""
 WALL TEXTURE — APPLY TEXTURE PATTERN
A wall texture swatch image is provided AFTER the product reference images.

TEXTURE INFO:
- Name: {texture_name}
- Type: {texture_type or 'textured'} finish

WALL TEXTURE RULES:
1. Study the texture swatch pattern, colors, and details
2. Apply this EXACT pattern to ALL visible wall surfaces
3. Maintain natural scale (not too small or large)
4. Blend naturally at wall corners and edges
5. Preserve natural shadows and lighting ON the texture
6. DO NOT apply texture to ceiling, floor, or furniture
"""

            if tile_swatch_image and tile_name:
                tile_size_desc = ""
                if tile_width_mm and tile_height_mm:
                    tile_size_desc = (
                        f"{tile_width_mm} mm × {tile_height_mm} mm ({tile_width_mm/10:.0f} cm × {tile_height_mm/10:.0f} cm)"
                    )
                else:
                    tile_size_desc = tile_size or "standard size"

                surface_instructions += f"""
 FLOOR TILE — APPLY TILE PATTERN
A floor tile swatch image is provided AFTER the product reference images{' and wall texture swatch' if texture_image else ''}.

TILE INFO:
- Name: {tile_name}
- Size: {tile_size_desc}
- Finish: {tile_finish or 'standard'}

FLOOR TILE RULES:
1. Study the tile swatch pattern, colors, veining, and details
2. Apply this EXACT pattern to ALL visible FLOOR surfaces ONLY
3. Each tile is {tile_size_desc} — scale tiles correctly using door height (~2000mm) as reference
4. Add thin, natural grout lines between tiles
5. Tiles closer to camera appear larger (perspective foreshortening)
6. Apply appropriate reflectivity for {tile_finish or 'standard'} finish
7.  NEVER apply tile pattern to WALLS — tiles go ONLY on the FLOOR (horizontal ground surface)
8.  NEVER apply tile to the ceiling or any vertical surface
9. The boundary between floor and wall must remain clear — tiles stop where the wall begins
10. Furniture legs should rest naturally on the tiled surface
"""

            # Build prompt based on what we're doing
            # Surface-only case (no products): wall color, texture, and/or floor tile
            if not products and (wall_color or has_surfaces):
                # Build a combined surface-only prompt
                surface_changes_desc = []
                if wall_color and not texture_image:
                    color_name = wall_color.get("name", "Unknown")
                    color_code = wall_color.get("code", "")
                    color_hex = wall_color.get("hex_value", "")
                    surface_changes_desc.append(f"wall color to {color_name} ({color_hex})")
                if texture_image and texture_name:
                    surface_changes_desc.append(f"wall texture to {texture_name}")
                if tile_swatch_image and tile_name:
                    surface_changes_desc.append(f"floor tile to {tile_name}")
                changes_summary = " and ".join(surface_changes_desc)

                prompt = f"""{VisualizationPrompts.get_system_intro()}

 SURFACE CHANGES ONLY - NO OTHER CHANGES
Your ONLY task is to change: {changes_summary}. Do NOT make any other changes.

 ABSOLUTE REQUIREMENT - IMAGE DIMENSIONS & ROOM STRUCTURE
═══════════════════════════════════════════════════════════════
THE OUTPUT IMAGE MUST HAVE THE EXACT SAME DIMENSIONS AS THE INPUT IMAGE.
- If input is 1024x768 pixels → output MUST be 1024x768 pixels
- NEVER change the aspect ratio
- NEVER crop, resize, or alter the image dimensions in ANY way
- The camera angle, perspective, and field of view MUST remain UNCHANGED
- DO NOT zoom in or out

 ROOM STRUCTURE PRESERVATION - CRITICAL:
- DO NOT add new walls, partitions, columns, or any architectural elements
- DO NOT remove or modify existing walls, doors, windows, or structural elements
- The number of walls visible must remain EXACTLY the same
- Wall positions, angles, and proportions must be IDENTICAL to input
- Ceiling height and shape must remain UNCHANGED
- The room's physical structure is LOCKED — only surface finishes change
═══════════════════════════════════════════════════════════════

{wall_color_instruction}

{surface_instructions}

 ABSOLUTELY FORBIDDEN - DO NOT DO ANY OF THESE
═══════════════════════════════════════════════════════════════
-  DO NOT add ANY new furniture (sofas, chairs, tables, etc.)
-  DO NOT add ANY rugs or carpets
-  DO NOT add ANY decor items (plants, lamps, artwork, cushions)
-  DO NOT remove ANY existing furniture or objects
-  DO NOT move or reposition ANY existing furniture
-  DO NOT change ANY furniture colors or materials
{'' if tile_swatch_image else '-  DO NOT change the floor color or material'}
-  DO NOT paint the ceiling
-  DO NOT change window frames, door frames, or trim
-  DO NOT change the camera angle or zoom level
-  DO NOT crop or resize the image
-  DO NOT add new walls, partitions, or architectural structures
-  DO NOT apply floor tiles to walls — tiles are ONLY for floor surfaces
-  DO NOT apply wall texture to the floor — texture is ONLY for wall surfaces
═══════════════════════════════════════════════════════════════

 CRITICAL: THE ONLY CHANGES ALLOWED ARE: {changes_summary.upper()}
Everything else in the room must remain EXACTLY as it appears in the input image.
The furniture, decor, and all other elements must be IDENTICAL.

 PIXEL-PERFECT PRESERVATION:
- All furniture must be at the EXACT same pixel positions
- The room layout and composition must be IDENTICAL to input
- Output dimensions must EXACTLY match input dimensions
- The room structure (walls, ceiling, floor boundaries) must be IDENTICAL

OUTPUT: The EXACT same room with ONLY the surface changes applied.
No furniture, rugs, decor, or any other elements should be added, removed, or changed."""
            else:
                # Build prompt for ADD MULTIPLE action (with or without wall color)
                # Use total_items_to_add which accounts for quantities (e.g., 2 products with qty=3 each = 6 items)
                prompt = f"""{VisualizationPrompts.get_system_intro()}

{existing_products_warning}{multiple_instance_instruction}{planter_instruction}ADD the following items to this room in appropriate locations WITHOUT removing any existing furniture.

 ITEM COUNT SUMMARY (YOU MUST ADD EXACTLY THIS MANY):
{product_summary_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TOTAL ITEMS TO PLACE: {total_items_to_add}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DETAILED LIST - ADD EACH OF THESE {total_items_to_add} ITEMS:
{product_list}

 ABSOLUTE REQUIREMENT - ROOM DIMENSIONS & STRUCTURE
═══════════════════════════════════════════════════════════════
THE OUTPUT IMAGE MUST HAVE THE EXACT SAME DIMENSIONS AS THE INPUT IMAGE.
- If input is 1024x768 pixels → output MUST be 1024x768 pixels
- NEVER change the aspect ratio
- NEVER crop, resize, or alter the image dimensions in ANY way
- The room's physical proportions MUST appear IDENTICAL
- The camera angle, perspective, and field of view MUST remain UNCHANGED
- DO NOT zoom in or out
- The walls must be in the EXACT same positions

 ROOM STRUCTURE PRESERVATION - CRITICAL:
-  DO NOT add new walls, partitions, columns, or any architectural elements
-  DO NOT remove or modify existing walls, doors, windows, or structural elements
- The number of walls visible must remain EXACTLY the same as the input image
- Wall positions, angles, and proportions must be IDENTICAL to input
- Ceiling height and shape must remain UNCHANGED
- The room's physical structure is LOCKED — you are ONLY adding furniture

 CRITICAL PRESERVATION RULES:
1. KEEP ALL EXISTING FURNITURE: Do NOT remove, move, or replace any furniture currently in the room
2.  ESPECIALLY PRESERVE SOFAS: If there is a sofa/couch, it MUST remain in its EXACT position
3.  PRESERVE EXISTING COLORS: Do NOT change the color of ANY existing furniture or decor in the room
4. PRESERVE THE ROOM: Keep the same walls, windows, floors, ceiling, lighting
5. ROOM SIZE UNCHANGED: The room must look the EXACT same size
6.  DO NOT ADD EXTRA ITEMS: Only add the items listed above. Do NOT add extra copies of items already in the room unless specifically requested

{wall_color_instruction}

{surface_instructions}

{' FLOOR COLOR PRESERVATION - ABSOLUTE REQUIREMENT ' + chr(10) + ' DO NOT CHANGE THE FLOOR COLOR - flooring must remain EXACTLY the same color/material as input' + chr(10) + ' DO NOT change flooring material, color, or texture' + chr(10) + '- If floor is wooden → output floor MUST be the SAME wooden color' + chr(10) + '- The floor color scheme is FIXED' if not tile_swatch_image else ''}

 PIXEL-LEVEL POSITION PRESERVATION - CRITICAL
- Every piece of existing furniture must be at the EXACT SAME PIXEL COORDINATES as in the input
- If a sofa's left edge starts at pixel X=100 in the input, it MUST start at X=100 in the output
- DO NOT shift, nudge, or adjust the position of ANY existing furniture - not even by a few pixels
- The silhouette/outline of every existing furniture piece must PERFECTLY OVERLAY the input image
- Think of it as: existing furniture is "locked in place" - you can only ADD new items around them

 CUSHIONS / PILLOWS / THROWS - SPECIAL RULES:
- Cushions go DIRECTLY ON the existing sofa/chair - on the seat or against the backrest
- The sofa MUST NOT MOVE when adding cushions - cushions sit ON the furniture
-  ABSOLUTELY FORBIDDEN: Moving the sofa to accommodate cushions
-  CORRECT: Cushions placed on sofa, sofa stays in EXACT same position

 PLACEMENT RESTRICTIONS - VERY IMPORTANT
1.  ONLY place new items in VISIBLE EMPTY SPACES - spaces that are clearly visible and unobstructed
2.  NEVER place furniture BEHIND other furniture (e.g., NO bookshelf behind a sofa - it would be hidden!)
3.  NEVER place items where they would be COVERED or BLOCKED by existing furniture
4.  Place items NEXT TO existing furniture (beside the sofa, not behind it)
5.  Place items in OPEN FLOOR AREAS visible to the camera
6.  Place items AGAINST VISIBLE WALLS (not walls blocked by sofas/beds)
7.  If a space is blocked by existing furniture, DO NOT use that space
8. Bookshelves, cabinets, and tall furniture must be placed against OPEN walls where they are FULLY VISIBLE

 WALL ART / PAINTINGS - CRITICAL:
- If the room ALREADY has wall art/paintings hanging → DO NOT REPLACE them
- ADD new wall art on a DIFFERENT wall or DIFFERENT position on the same wall
- Multiple paintings CAN and SHOULD coexist - this is a GALLERY-style arrangement
- The existing artwork must REMAIN VISIBLE in its original position
- New artwork should be placed on empty wall space AWAY from existing art
- Result: Room has MULTIPLE artworks visible (not one replacing another)

 ADDING MORE OF THE SAME PRODUCT:
If the room ALREADY has a chair/cushion/table and you're asked to add ANOTHER one:
- The original item MUST REMAIN in its current position
- ADD the new item in a DIFFERENT location (next to it, across from it, etc.)
- Result: 2 items of the same type in the room (NOT replacing the original)
- Example: If there's already 1 accent chair and you add 1 more → room should have 2 chairs

 EXACT PRODUCT REPLICATION - THIS IS THE MOST CRITICAL REQUIREMENT
═══════════════════════════════════════════════════════════════════════════════

 YOU MUST COPY THE EXACT PRODUCT FROM THE REFERENCE IMAGE

For each product with a reference image provided:
1.  EXACT SHAPE/SILHOUETTE - Copy the PRECISE shape from the reference
   - If reference shows a pedestal table with teardrop glass base → output MUST have pedestal with teardrop glass base
   - If reference shows nesting tables → output MUST be nesting tables
   - DO NOT substitute with a similar-but-different furniture style!

2.  EXACT COLOR - Match the precise color/finish
   - If reference shows gold/brass metal → output MUST be gold/brass metal
   - If reference shows smoky glass → output MUST be smoky glass

3.  EXACT DESIGN DETAILS - Copy all distinctive features
   - Base style (pedestal vs legs vs frame)
   - Top shape (round vs rectangular vs oval)
   - Material combinations (metal + glass, wood + marble, etc.)

4.  ABSOLUTELY FORBIDDEN:
   - DO NOT render a "generic" version of the furniture type
   - DO NOT substitute with a different table/chair/sofa style
   - DO NOT improvise or "interpret" the design
   - The output product MUST be RECOGNIZABLE as the SAME product from the reference image

Think of it this way: If a customer ordered THIS SPECIFIC product and you deliver something different, they will return it. The reference image IS the product - copy it EXACTLY.

 COLOR MATCHING IS MANDATORY:
- If you're adding 2 copies of "Orange Cushion", BOTH must be ORANGE (same as reference)
- If you're adding 2 copies of "Red Cushion", BOTH must be RED (same as reference)
- DO NOT substitute colors or mix up which product gets which color
- Each product reference image shows the EXACT color you must replicate

PLACEMENT GUIDELINES:
- Space products appropriately - don't cluster them all in one spot
- Follow standard interior design placement rules
- Coffee tables go in front of sofas
- Side tables go next to sofas/chairs
- Accent chairs angle towards the main seating
- Lamps go on tables or as floor lamps
- Decor items go on table surfaces

 REALISTIC FURNITURE PLACEMENT — CRITICAL
═══════════════════════════════════════════════════════════════
Place furniture where a REAL INTERIOR DESIGNER would place it:

1. SOFAS & LARGE SEATING:
   - Place FLUSH AGAINST a SOLID WALL (2-4 inch gap max between sofa back and wall)
   - NEVER float a sofa in the center of the room with empty space behind it
   - The sofa back should be nearly TOUCHING the wall
   - Choose the longest unobstructed wall for sofa placement
   - If the room has a back wall visible, place the sofa against it
   - NEVER place sofas against windows or glass doors

2. BEDS:
   - Place the headboard FLUSH AGAINST a solid wall
   - NEVER float a bed in the center of the room
   - Leave walkway space on at least one side

3. COFFEE TABLES & CENTER TABLES:
   - Place in front of the sofa, centered relative to the seating arrangement
   - Maintain 14-18 inches between sofa and coffee table
   - The table should be roughly the same height as the sofa seat

4. BOOKSHELVES, CABINETS, CONSOLES:
   - Place AGAINST a wall — these are wall-hugging furniture
   - Never float storage furniture in the middle of the room

5. GENERAL DEPTH/PERSPECTIVE:
   - Furniture AGAINST the back wall should appear SMALLER (further away)
   - Furniture near the camera should appear LARGER (closer)
   - The sofa placed against the far wall should NOT dominate the foreground
   - Respect the room's depth — back wall furniture is in the background

 FORBIDDEN PLACEMENTS:
- Floating sofas/beds with visible floor behind them
- Furniture blocking walkways or doorways
- Large furniture against windows or glass doors
- Sofa placed dead-center of the image with wall gap behind
═══════════════════════════════════════════════════════════════

 SCULPTURES / FIGURINES / DECORATIVE STATUES:
-  FIRST PRIORITY: Place on the CENTER TABLE / COFFEE TABLE (in front of sofa)
-  SECOND PRIORITY: If center table is full or doesn't exist, place on a SIDE TABLE
-  THIRD PRIORITY: If no tables available, place on console table, shelf, or mantel
- Sculptures should be PROMINENTLY visible on table surfaces, NOT on the floor
- Position facing the camera for best visual impact

 MANDATORY FRONT ANGLE REQUIREMENT:
 ALL PRODUCTS MUST SHOW THEIR FRONT FACE TOWARDS THE CAMERA
- Sofas: Front cushions/seating area facing camera, NOT the back
- Tables: Front/main side facing camera
- Chairs: Front/seating side facing camera, NOT the back
- Cabinets: Doors/drawers facing camera
- All furniture: Show the primary viewing angle (showroom display angle) facing the camera
 WRONG: Showing furniture backs or sharp side angles
 CORRECT: Products oriented with their "front" facing the camera view

 BALANCED DISTRIBUTION - VERY IMPORTANT:
- Distribute items on BOTH SIDES of the sofa for visual balance
- If adding a floor lamp AND a planter: put one on each side of the sofa
- If adding 2 side tables: put one on each end of the sofa
- If adding multiple floor items (lamps, planters, side tables): spread them across the room
- DON'T cluster all floor items on one side - this looks cramped and unbalanced
- Example: Floor lamp on LEFT side of sofa, planter on RIGHT side of sofa

 LIGHTING:
- All products must match the room's lighting direction and color temperature
- Products must look naturally integrated, not "pasted on"

OUTPUT: One photorealistic image showing THE ENTIRE ROOM with ALL {total_items_to_add} ITEMS added naturally.
 You MUST place EXACTLY {total_items_to_add} new items in the room (some products have multiple copies).
The room structure, walls, and camera angle MUST be identical to the input image."""

            # Build contents list with PIL Images (same approach as furniture removal)
            contents = [prompt]

            # Add room image as PIL Image
            room_image_bytes = base64.b64decode(processed_room)
            room_pil_image = Image.open(io.BytesIO(room_image_bytes))
            # Apply EXIF orientation correction (important for smartphone photos)
            room_pil_image = ImageOps.exif_transpose(room_pil_image)
            if room_pil_image.mode != "RGB":
                room_pil_image = room_pil_image.convert("RGB")

            # Get the input image dimensions for logging
            input_width, input_height = room_pil_image.size
            logger.info(f"Input room image (MULTIPLE, EXIF corrected): {input_width}x{input_height}")

            contents.append(room_pil_image)

            # Add all product reference images as PIL Images
            for i, (name, image_data) in enumerate(zip(product_names, product_images_data)):
                # Get the quantity for this product
                qty_for_product = next((qty for n, qty, _ in product_entries if n == name), 1)
                if image_data:
                    if qty_for_product > 1:
                        contents.append(
                            f"\n Product {i+1} REFERENCE IMAGE ({name}) - COPY THIS EXACT PRODUCT {qty_for_product} TIMES:\n"
                            f" CRITICAL: Match the EXACT shape, design, color, material, and all visual details. DO NOT substitute with a different style!"
                        )
                    else:
                        contents.append(
                            f"\n Product {i+1} REFERENCE IMAGE ({name}) - COPY THIS EXACT PRODUCT:\n"
                            f" CRITICAL: Match the EXACT shape, design, color, material, and all visual details. DO NOT substitute with a different style!"
                        )
                    prod_image_bytes = base64.b64decode(image_data)
                    prod_pil_image = Image.open(io.BytesIO(prod_image_bytes))
                    if prod_pil_image.mode != "RGB":
                        prod_pil_image = prod_pil_image.convert("RGB")
                    contents.append(prod_pil_image)

            # Add wall texture swatch if provided
            if texture_image:
                contents.append("\n WALL TEXTURE REFERENCE SWATCH — Apply this pattern to ALL visible walls:")
                tex_bytes = base64.b64decode(self._preprocess_image_for_editing(texture_image))
                tex_pil = Image.open(io.BytesIO(tex_bytes)).convert("RGB")
                contents.append(tex_pil)
                logger.info("Added wall texture swatch to contents array")

            # Add floor tile swatch if provided
            if tile_swatch_image:
                contents.append("\n FLOOR TILE REFERENCE SWATCH — Apply this tile pattern to ALL visible floor surfaces:")
                tile_bytes = base64.b64decode(self._preprocess_image_for_editing(tile_swatch_image))
                tile_pil = Image.open(io.BytesIO(tile_bytes)).convert("RGB")
                contents.append(tile_pil)
                logger.info("Added floor tile swatch to contents array")

            # Generate visualization with Gemini 3 Pro Image
            # Use HIGH media resolution for better quality output
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.3,
            )

            # Retry configuration with timeout protection
            max_retries = 3  # Keep at 3 for design studio (5 retries = too long wait time)
            timeout_seconds = 90
            num_products = len(products)

            def _run_generate_add_multiple():
                """Run the streaming generation in a thread for timeout support."""
                result_image = None
                final_chunk = None  # Capture final chunk for usage_metadata
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
                    final_chunk = chunk  # Always keep reference to last chunk
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                        for part in chunk.candidates[0].content.parts:
                            if part.inline_data and part.inline_data.data:
                                image_data = part.inline_data.data
                                mime_type = part.inline_data.mime_type or "image/png"

                                # Handle both raw bytes and base64 string bytes
                                # (google-genai SDK may return either format)
                                if isinstance(image_data, bytes):
                                    first_hex = image_data[:4].hex()
                                    logger.info(f"ADD MULTIPLE visualization first 4 bytes hex: {first_hex}")

                                    # Check if raw image bytes (PNG starts with 89504e47, JPEG with ffd8ff)
                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        # Raw image bytes - encode to base64
                                        image_base64 = base64.b64encode(image_data).decode("utf-8")
                                        logger.info("ADD MULTIPLE: Raw image bytes detected, encoded to base64")
                                    else:
                                        # Bytes are likely base64 string - decode to string directly
                                        image_base64 = image_data.decode("utf-8")
                                        logger.info("ADD MULTIPLE: Base64 string bytes detected, decoded directly")
                                else:
                                    # Already a string
                                    image_base64 = image_data
                                    logger.info("ADD MULTIPLE: String data received directly")

                                result_image = f"data:{mime_type};base64,{image_base64}"
                                logger.info(f"Generated ADD MULTIPLE visualization for {num_products} products")
                return (result_image, final_chunk)  # Return tuple with final chunk for token tracking

            generated_image = None
            final_chunk = None
            gemini_start = time.time()
            logger.info(f" [TIMING] Starting Gemini API call...")
            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, _run_generate_add_multiple), timeout=timeout_seconds
                    )
                    if result:
                        generated_image, final_chunk = result
                    if generated_image:
                        break
                except asyncio.TimeoutError:
                    logger.warning(f"ADD MULTIPLE visualization attempt {attempt + 1} timed out after {timeout_seconds}s")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)  # Exponential backoff: 2, 4, 8 seconds
                        logger.info(f"Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    continue
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a 503 (overloaded) error - retry with longer backoff
                    if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 4 * (2**attempt)  # Longer backoff for 503: 4, 8, 16 seconds
                            logger.warning(
                                f"ADD MULTIPLE visualization: Model overloaded (503), retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                    logger.error(f"ADD MULTIPLE visualization attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        await asyncio.sleep(wait_time)
                    continue

            if not generated_image:
                logger.error(f"AI failed to generate ADD MULTIPLE visualization after {max_retries} attempts")
                raise ValueError("AI failed to generate visualization image")

            logger.info(f" [TIMING] Gemini API call completed in {time.time() - gemini_start:.2f}s")
            logger.info(f" [TIMING] TOTAL visualization time: {time.time() - timing_start:.2f}s")

            # Log visualization operation with token tracking from final chunk
            self._log_streaming_operation(
                "generate_add_multiple_visualization",
                "gemini-3-pro-image-preview",
                workflow_id=workflow_id,
                final_chunk=final_chunk,
                user_id=user_id,
                session_id=session_id,
            )

            # Resize output to match input dimensions if they differ
            try:
                output_b64 = generated_image
                if output_b64.startswith("data:"):
                    output_b64 = output_b64.split(",", 1)[1]

                output_bytes = base64.b64decode(output_b64)
                output_img = Image.open(io.BytesIO(output_bytes))
                output_width, output_height = output_img.size
                logger.info(
                    f"[AddMultiple] Output resolution: {output_width}x{output_height}, Input was: {input_width}x{input_height}"
                )

                if output_width != input_width or output_height != input_height:
                    logger.warning(
                        f"[AddMultiple] Output resolution mismatch! Resizing from {output_width}x{output_height} to {input_width}x{input_height}"
                    )
                    if output_img.mode != "RGB":
                        output_img = output_img.convert("RGB")
                    output_img = output_img.resize((input_width, input_height), Image.Resampling.LANCZOS)

                    buffer = io.BytesIO()
                    output_img.save(buffer, format="PNG", optimize=False)
                    buffer.seek(0)
                    resized_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    generated_image = f"data:image/png;base64,{resized_b64}"
                    logger.info(f"[AddMultiple] Resized output to match input: {input_width}x{input_height}")
            except Exception as resize_err:
                logger.warning(f"[AddMultiple] Could not verify/fix output resolution: {resize_err}")

            return generated_image

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error generating ADD MULTIPLE visualization: {e}")
            raise ValueError(f"Visualization generation failed: {e}")

    async def generate_replace_visualization(
        self,
        room_image: str,
        product_name: str,
        furniture_type: str,
        product_image: Optional[str] = None,
        product_color: Optional[str] = None,
    ) -> str:
        """
        Generate visualization with furniture REPLACED
        Returns: base64 image data

        Args:
            room_image: Base64 encoded room image
            product_name: Name of the product (may include color prefix)
            furniture_type: Type of furniture being replaced
            product_image: URL of product reference image
            product_color: Explicit color from product attributes (e.g., "beige", "cream", "walnut")
        """
        try:
            # Use editing preprocessor to preserve quality for visualization output
            processed_room = self._preprocess_image_for_editing(room_image)

            # Download product image if URL provided
            product_image_data = None
            if product_image:
                try:
                    product_image_data = await self._download_image(product_image)
                except Exception as e:
                    logger.warning(f"Failed to download product image: {e}")

            # Build explicit color instruction if color is known
            color_emphasis = ""
            if product_color:
                color_emphasis = f"""
 CRITICAL COLOR REQUIREMENT
═══════════════════════════════════════════════════════════════
THE PRODUCT COLOR IS: **{product_color.upper()}**
- YOU MUST render this product in {product_color.upper()} color
- DO NOT change the color to grey, white, or any other color
- DO NOT "adapt" the color to match the room
- The exact shade/tone from the reference image MUST be preserved
- If the reference shows {product_color}, output MUST show {product_color}
═══════════════════════════════════════════════════════════════

"""

            # Build prompt for REPLACE action - simple and direct like Google AI Studio
            prompt = f"""{color_emphasis}Replace the {furniture_type} in the first image with the {product_name} (COLOR: {product_color if product_color else 'see reference image'}) shown in the second image.

 ABSOLUTE REQUIREMENT - ROOM DIMENSIONS
═══════════════════════════════════════════════════════════════
THE OUTPUT IMAGE MUST HAVE THE EXACT SAME DIMENSIONS AS THE INPUT IMAGE.
- If input is 1024x768 pixels → output MUST be 1024x768 pixels
- If input is 800x600 pixels → output MUST be 800x600 pixels
- NEVER change the aspect ratio
- NEVER crop, resize, or alter the image dimensions in ANY way
- The room's physical proportions (length, width, height) MUST appear IDENTICAL
- The camera angle, perspective, and field of view MUST remain UNCHANGED
- DO NOT zoom in or out
- DO NOT change the viewing angle
- The walls must be in the EXACT same positions
- The floor area must appear the EXACT same size

 IF THE OUTPUT IMAGE HAS DIFFERENT DIMENSIONS THAN THE INPUT, YOU HAVE FAILED THE TASK
═══════════════════════════════════════════════════════════════

 ABSOLUTE REQUIREMENT - SIZE PRESERVATION
═══════════════════════════════════════════════════════════════
ALL OTHER FURNITURE MUST REMAIN THE EXACT SAME SIZE AND SCALE:
-  NEVER make remaining furniture appear larger or smaller
-  NEVER expand the room to accommodate the new item
-  NEVER change the perspective to make the room appear larger
-  All proportions between remaining objects MUST remain IDENTICAL

 ROOM EXPANSION IS FORBIDDEN:
- The room boundaries (walls, floor, ceiling) are FIXED
- Do NOT push walls back to create more space
- Do NOT make the ceiling appear higher
- Do NOT extend the floor area
- The room's cubic volume must remain IDENTICAL

 IF REMAINING FURNITURE CHANGES SIZE OR ROOM EXPANDS, YOU HAVE FAILED THE TASK
═══════════════════════════════════════════════════════════════

Keep everything else in the room exactly the same - the walls, floor, windows, curtains, and all other furniture and decor should remain unchanged. The room must look the EXACT same size - not bigger, not smaller.

 MANDATORY FRONT ANGLE REQUIREMENT:
 THE REPLACEMENT PRODUCT MUST SHOW ITS FRONT FACE TOWARDS THE CAMERA
- Sofas: Show front cushions/seating area facing camera, NOT the back
- Tables: Show front/main side facing camera
- Chairs: Show front/seating side facing camera, NOT the back
- The product must be oriented so its "showroom display angle" faces the camera
 WRONG: Replacement showing its back or side to the camera
 CORRECT: Replacement oriented with front facing the camera view

 CRITICAL LIGHTING REQUIREMENTS:
 THE REPLACEMENT PRODUCT MUST LOOK LIKE IT IS PART OF THE ROOM, NOT ADDED ON TOP OF IT
1. ANALYZE the room's lighting: identify light sources, direction, color temperature (warm/cool)
2. MATCH lighting on the new product: highlights must come from the same direction as room lighting
3. MATCH shadow direction: product shadow must fall in the same direction as other shadows in room
4. MATCH exposure: product should NOT be brighter or darker than similar surfaces in room
5. NO "SPOTLIGHT" EFFECT: product must NOT look highlighted compared to the room
6. SEAMLESS BLEND: a viewer should NOT be able to tell the product was digitally added

Generate a photorealistic image of the room with the {product_name} replacing the {furniture_type}, with lighting that perfectly matches the room's existing lighting conditions."""

            # Build contents list with PIL Images (same approach as furniture removal)
            contents = [prompt]

            # Add room image as PIL Image
            room_image_bytes = base64.b64decode(processed_room)
            room_pil_image = Image.open(io.BytesIO(room_image_bytes))
            # Apply EXIF orientation correction (important for smartphone photos)
            room_pil_image = ImageOps.exif_transpose(room_pil_image)
            if room_pil_image.mode != "RGB":
                room_pil_image = room_pil_image.convert("RGB")

            # Get the input image dimensions for logging
            input_width, input_height = room_pil_image.size
            logger.info(f"Input room image (REPLACE, EXIF corrected): {input_width}x{input_height}")

            contents.append(room_pil_image)

            # Add product reference image if available
            if product_image_data:
                prod_image_bytes = base64.b64decode(product_image_data)
                prod_pil_image = Image.open(io.BytesIO(prod_image_bytes))
                if prod_pil_image.mode != "RGB":
                    prod_pil_image = prod_pil_image.convert("RGB")
                contents.append(prod_pil_image)

            # Generate visualization with Gemini 3 Pro Image (Nano Banana Pro)
            # Use temperature 0.4 to match Google AI Studio's default
            # Use HIGH media resolution for better quality output
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.4,
            )

            # Retry configuration with timeout protection
            max_retries = 3
            timeout_seconds = 90

            def _run_generate_replace():
                """Run the streaming generation in a thread for timeout support."""
                result_image = None
                final_chunk = None  # Capture final chunk for usage_metadata
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
                    final_chunk = chunk  # Always keep reference to last chunk
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                        for part in chunk.candidates[0].content.parts:
                            if part.inline_data and part.inline_data.data:
                                image_data = part.inline_data.data
                                mime_type = part.inline_data.mime_type or "image/png"

                                # Handle both raw bytes and base64 string bytes
                                # (google-genai SDK may return either format)
                                if isinstance(image_data, bytes):
                                    first_hex = image_data[:4].hex()
                                    logger.info(f"REPLACE visualization first 4 bytes hex: {first_hex}")

                                    # Check if raw image bytes (PNG starts with 89504e47, JPEG with ffd8ff)
                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        # Raw image bytes - encode to base64
                                        image_base64 = base64.b64encode(image_data).decode("utf-8")
                                        logger.info("REPLACE: Raw image bytes detected, encoded to base64")
                                    else:
                                        # Bytes are likely base64 string - decode to string directly
                                        image_base64 = image_data.decode("utf-8")
                                        logger.info("REPLACE: Base64 string bytes detected, decoded directly")
                                else:
                                    # Already a string
                                    image_base64 = image_data
                                    logger.info("REPLACE: String data received directly")

                                result_image = f"data:{mime_type};base64,{image_base64}"
                                logger.info("Generated REPLACE visualization")
                return (result_image, final_chunk)  # Return tuple with final chunk for token tracking

            generated_image = None
            final_chunk = None
            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(loop.run_in_executor(None, _run_generate_replace), timeout=timeout_seconds)
                    if result:
                        generated_image, final_chunk = result
                    if generated_image:
                        break
                except asyncio.TimeoutError:
                    logger.warning(f"REPLACE visualization attempt {attempt + 1} timed out after {timeout_seconds}s")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)  # Exponential backoff: 2, 4, 8 seconds
                        logger.info(f"Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    continue
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a 503 (overloaded) error - retry with longer backoff
                    if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 4 * (2**attempt)  # Longer backoff for 503: 4, 8, 16 seconds
                            logger.warning(
                                f"REPLACE visualization: Model overloaded (503), retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                    logger.error(f"REPLACE visualization attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        await asyncio.sleep(wait_time)
                    continue

            if not generated_image:
                logger.error(f"AI failed to generate REPLACE visualization after {max_retries} attempts")
                raise ValueError("AI failed to generate visualization image")

            # Log visualization operation with token tracking from final chunk
            self._log_streaming_operation(
                "generate_replace_visualization", "gemini-3-pro-image-preview", final_chunk=final_chunk
            )

            return generated_image

        except ValueError:
            # Re-raise ValueError for proper handling
            raise
        except Exception as e:
            logger.error(f"Error generating REPLACE visualization: {e}")
            raise ValueError(f"Visualization generation failed: {e}")

    async def generate_room_visualization(
        self, visualization_request: VisualizationRequest, room_analysis: Optional[Dict[str, Any]] = None
    ) -> VisualizationResult:
        """
        Generate photorealistic room visualization using a HYBRID approach:
        1. Use AI to understand the room and identify placement locations
        2. Use AI to generate masked products
        3. Composite products onto the ORIGINAL room image (preserving 100% of original)

        Args:
            visualization_request: The visualization request with products and base image
            room_analysis: Optional room analysis dict containing dimensions and scale_references
                          for perspective-aware product scaling
        """
        try:
            start_time = time.time()

            # Prepare products description for the prompt
            products_description = []
            product_images = []
            for idx, product in enumerate(visualization_request.products_to_place):
                product_name = product.get("full_name") or product.get("name", "furniture item")
                products_description.append(f"Product {idx+1}: {product_name}")

                # Download ALL product images for better reference (up to 3 per product)
                image_urls = product.get("image_urls", [])
                if not image_urls and product.get("image_url"):
                    image_urls = [product["image_url"]]

                # Limit to 3 images per product to avoid overwhelming the model
                for img_idx, img_url in enumerate(image_urls[:3]):
                    try:
                        product_image_data = await self._download_image(img_url)
                        if product_image_data:
                            product_images.append(
                                {
                                    "data": product_image_data,
                                    "name": product_name,
                                    "index": idx + 1,
                                    "image_number": img_idx + 1,
                                    "total_images": min(len(image_urls), 3),
                                }
                            )
                    except Exception as e:
                        logger.warning(f"Failed to download product image {img_idx + 1}: {e}")

                if image_urls:
                    logger.info(
                        f"[VIZ] Product {idx+1} '{product_name}': Downloaded {min(len(image_urls), 3)} of {len(image_urls)} reference images"
                    )

            # Process the base image - use editing preprocessor to preserve quality
            processed_image = self._preprocess_image_for_editing(visualization_request.base_image)

            # Use user's actual request as the primary directive
            user_request = visualization_request.user_style_description.strip()

            # Use comprehensive professional prompt template
            if products_description and product_images:
                # Build detailed product list with descriptions and standardized dimensions
                detailed_products = []
                for idx, product in enumerate(visualization_request.products_to_place):
                    product_name = product.get("full_name") or product.get("name", "furniture item")
                    product_desc = product.get("description", "No description available")
                    furniture_type = product.get("furniture_type", "furniture")

                    # Extract actual dimensions from product data (from product_attributes)
                    # Use standardized format: W x D x H in inches
                    dimensions = product.get("dimensions", {})
                    dim_parts = []
                    if dimensions.get("width"):
                        dim_parts.append(f'{dimensions["width"]}" W')
                    if dimensions.get("depth"):
                        dim_parts.append(f'{dimensions["depth"]}" D')
                    if dimensions.get("height"):
                        dim_parts.append(f'{dimensions["height"]}" H')
                    dimension_str = " x ".join(dim_parts) if dim_parts else "dimensions not specified"

                    detailed_products.append(
                        f"""
Product {idx + 1}:
- Name: {product_name}
- Type: {furniture_type}
- PHYSICAL DIMENSIONS: {dimension_str}
- Description: {product_desc}
- Placement: {user_request if user_request else 'Place naturally in appropriate location based on product type'}
- Reference Image: Provided below"""
                    )

                products_detail = "\n".join(detailed_products)

                # ULTRA-STRICT room preservation prompt
                product_count = len(visualization_request.products_to_place)

                # Check if any product is a planter
                has_planter = any(
                    any(
                        term in (product.get("full_name") or product.get("name", "")).lower()
                        for term in ["planter", "plant pot", "flower pot", "pot", "succulent"]
                    )
                    for product in visualization_request.products_to_place
                )

                # Planter-specific instruction
                planter_instruction = ""
                if has_planter:
                    planter_instruction = """
 PLANTER-SPECIFIC INSTRUCTION
═══════════════════════════════════════════════════════════════
For any planter being added:

THE ORIGINAL ASPECT RATIO AND VIEWING ANGLE OF THE IMAGE SHOULD REMAIN THE SAME.
THE EXISTING PRODUCTS IN THE ROOM SHOULD BE CLEARLY VISIBLE AND NOT CUT FROM VIEW.
THE IMAGE SHOULD NOT BE ZOOMED IN.
THE CAMERA ANGLE SHOULD BE THE SAME.
DO NOT CROP OR CUT ANY EXISTING FURNITURE FROM THE IMAGE.

 PLANTER PLACEMENT RULES:
-  NEVER place a planter IN FRONT OF the sofa or any seating — it blocks the view
-  NEVER place a planter in the CENTER of the room or in walkways
-  Place planters in FAR CORNERS of the room
-  Place planters BESIDE (to the LEFT or RIGHT of) sofas/chairs, NOT in front
-  Place planters against walls in empty spaces
- The planter is a SMALL accent piece — it should NOT block or obscure any furniture
═══════════════════════════════════════════════════════════════

"""

                # Check if we have multiple instances of the same product (e.g., "Dining Chair #1", "Dining Chair #2")
                product_names = [
                    product.get("full_name") or product.get("name", "") for product in visualization_request.products_to_place
                ]
                has_multiple_instances = any("#" in name for name in product_names)
                multiple_instance_instruction = ""
                if has_multiple_instances:
                    # Count how many instances of each product
                    instance_counts: Dict[str, int] = {}
                    for name in product_names:
                        if "#" in name:
                            base_name = name.rsplit(" #", 1)[0]
                            instance_counts[base_name] = instance_counts.get(base_name, 0) + 1

                    instance_details = "\n".join(
                        [f"   - {name}: {count} copies (ALL {count} must appear)" for name, count in instance_counts.items()]
                    )

                    # Build explicit list of allowed product names
                    allowed_names_list = ", ".join(product_names)
                    multiple_instance_instruction = f"""
 ABSOLUTELY CRITICAL: DO NOT ADD ANY EXTRA FURNITURE
═══════════════════════════════════════════════════════════════════════

 FORBIDDEN - DO NOT ADD ANY OF THESE:
- NO extra chairs (accent chairs, armchairs, dining chairs, single seaters)
- NO extra cushions or pillows beyond what's listed below
- NO extra sofas or sectionals
- NO extra tables (coffee tables, side tables, dining tables)
- NO extra lamps or lighting beyond what's listed
- NO extra plants or planters beyond what's listed
- NO extra rugs, wall art, or decorations beyond what's listed

 ONLY THESE SPECIFIC PRODUCTS ARE ALLOWED: {allowed_names_list}

 ADDING ANY UNLISTED FURNITURE = AUTOMATIC FAILURE
 ADDING DUPLICATES OF EXISTING ITEMS = AUTOMATIC FAILURE
═══════════════════════════════════════════════════════════════════════

 CRITICAL: MULTIPLE INSTANCES OF SAME PRODUCT
═══════════════════════════════════════════════════════════════
 YOU MUST PLACE ALL NUMBERED INSTANCES - DO NOT SKIP ANY

Products with numbered names (e.g., "Cushion Cover #1", "Cushion Cover #2", "Cushion Cover #3") are MULTIPLE COPIES of the SAME item that ALL must be placed:

{instance_details}

 PLACEMENT RULES FOR MULTIPLE INSTANCES:
- EVERY numbered instance (#1, #2, #3, etc.) MUST appear in the final image
- Place each instance in a DIFFERENT but RELATED position
- For cushions/pillows: arrange on the sofa - one on each seat, or clustered decoratively
- For chairs: arrange around a table or in a conversational grouping
- For dining chairs: place around the dining table at regular intervals
- For accent chairs: place in complementary positions (e.g., flanking a fireplace or sofa)
- For side tables: place at opposite ends of a sofa or beside different seating
- Maintain consistent spacing and alignment between instances
- All instances should face logical directions (not backs to the room)

 WRONG: Placing only 1 cushion when 3 are requested
 CORRECT: Placing all 3 cushions (#1, #2, #3) on the sofa

 DO NOT add ANY furniture not in the list above
═══════════════════════════════════════════════════════════════

"""

                # Create explicit product count instruction
                product_count_instruction = ""
                if has_multiple_instances:
                    # When we have multiple instances (e.g., Cushion Cover #1, #2, #3), we need ALL of them
                    product_count_instruction = f" PLACE EXACTLY {product_count} ITEMS TOTAL - This includes multiple copies of some products (numbered #1, #2, #3, etc.). Each numbered item MUST appear in the image."
                elif product_count == 1:
                    product_count_instruction = " PLACE EXACTLY 1 (ONE) PRODUCT - Do NOT place multiple copies. Place only ONE instance of the product."
                elif product_count == 2:
                    product_count_instruction = " PLACE EXACTLY 2 (TWO) DIFFERENT PRODUCTS - One of each product provided."
                else:
                    product_count_instruction = f" PLACE EXACTLY {product_count} ITEMS - One of each product listed below."

                # Create existing furniture instruction - conditional on exclusive_products mode
                # When exclusive_products=True, we ONLY want the specified products, remove any others
                if visualization_request.exclusive_products:
                    existing_furniture_instruction = f"""11.  EXCLUSIVE PRODUCTS MODE (CRITICAL) - The output should contain ONLY the {product_count} specified product(s) listed below:
   - IGNORE any furniture visible in the input image that is NOT in the specified product list
   - REMOVE/DO NOT RENDER any existing furniture, decor, or products from the input image
   - The ONLY furniture in the output should be the {product_count} product(s) specified below
   - Think of the input image as a base room - extract ONLY the room structure (walls, floor, windows, etc.)
   - This is a FRESH START - show the empty room with ONLY the specified products
   - Example: If input has a vase but the vase is NOT in the specified products, DO NOT show the vase in output"""
                else:
                    existing_furniture_instruction = """11.  EXISTING FURNITURE (CRITICAL FOR CONSISTENCY) - If the input image already contains furniture (sofa, table, chair, decor, etc.), you MUST preserve the EXACT appearance AND position of that furniture:
   - DO NOT change the COLOR of existing furniture (e.g., if sofa is blue, keep it blue)
   - DO NOT change the MATERIAL or TEXTURE of existing furniture
   - DO NOT change the STYLE or DESIGN of existing furniture
   - DO NOT change the SIZE or PROPORTIONS of existing furniture
   - DO NOT MOVE or REPOSITION any existing furniture - keep everything in its EXACT location
   - Keep existing furniture looking IDENTICAL to the input image
   - You are ONLY adding NEW products, NOT modifying existing ones
   - Example: If input has a blue velvet sofa, the output MUST show the same blue velvet sofa in the SAME position + your new products

 PIXEL-LEVEL POSITION LOCK - MANDATORY
   - Every existing furniture piece must remain at EXACTLY THE SAME PIXEL COORDINATES
   - If a sofa's edge is at pixel X=100 in input, it MUST be at X=100 in output
   - DO NOT shift, nudge, or adjust positions - not even by a few pixels
   - The outline of existing furniture must PERFECTLY OVERLAY the input image
   - Existing furniture is "LOCKED IN PLACE" - only ADD new items around them

 CUSHIONS / PILLOWS / THROWS - SPECIAL RULES:
   - Cushions go DIRECTLY ON the sofa/chair surface - on seats or against backrests
   - The sofa MUST NOT MOVE when adding cushions - cushions sit ON the furniture
   -  ABSOLUTELY FORBIDDEN: Moving/shifting sofa to accommodate cushions
   -  CORRECT: Cushions on sofa, sofa stays in EXACT same pixel position

12.  NEW PRODUCT PLACEMENT RESTRICTIONS:
   -  ONLY place new items in VISIBLE EMPTY SPACES - spaces that are clearly visible and unobstructed
   -  NEVER place furniture BEHIND other furniture (e.g., NO bookshelf behind a sofa - it would be hidden!)
   -  NEVER place items where they would be COVERED or BLOCKED by existing furniture
   -  Place items NEXT TO existing furniture (beside the sofa, not behind it)
   -  Place items in OPEN FLOOR AREAS visible to the camera
   -  Place items AGAINST VISIBLE WALLS (not walls blocked by sofas/beds)
   - Bookshelves, cabinets, and tall furniture must be placed against OPEN walls where they are FULLY VISIBLE"""

                visualization_prompt = f"""{VisualizationPrompts.get_system_intro()}

{multiple_instance_instruction}{planter_instruction}

RULE #1 - EXACT PRODUCT REPLICATION (HIGHEST PRIORITY)
-------------------------------------------------------
You MUST render products EXACTLY as shown in reference images. This is the most important rule.

MANDATORY:
- EXACT COLOR: Copy the precise color from reference (not similar, not harmonized - EXACT)
- EXACT SHAPE: Curved sofas stay curved, tulip chairs stay tulip-shaped, unique designs stay unique
- EXACT MATERIAL: Velvet stays velvet, leather stays leather, wood grain matches reference

DO NOT:
- Convert curved/cloud sofas into traditional rectangular sofas
- Convert tulip/swivel/egg chairs into traditional armchairs
- Convert abstract art into portraits or different artwork
- Simplify unique sculptural designs into generic furniture
- Generate "similar" or "inspired by" versions

The output products must be RECOGNIZABLE as the same products from reference images.

RULE #2 - ROOM PRESERVATION
---------------------------
Add {product_count} product(s) to the EXACT room image provided.

{product_count_instruction}

PRESERVE EXACTLY:
- Room structure: walls, floors, windows, doors, ceiling unchanged
- Output dimensions: Match input resolution exactly
- Aspect ratio: No cropping or letterboxing
- Camera angle: Same perspective and viewpoint

THE INPUT IMAGE SHOWS THE USER'S ACTUAL ROOM.
YOU ARE ADDING PRODUCTS TO THEIR REAL SPACE.
TREAT THE INPUT IMAGE AS SACRED - IT CANNOT BE MODIFIED.

═══════════════════════════════════════════════════════════════
 WHAT MUST STAY IDENTICAL (100% PRESERVATION REQUIRED)
═══════════════════════════════════════════════════════════════
{' CRITICAL: FLOOR MUST NOT CHANGE - If the input shows solid flooring, output MUST show solid flooring. If input shows checkered floor, output MUST show checkered floor. NEVER change floor patterns or materials.' if not visualization_request.tile_swatch_image else ''}

1. {'FLOOR (MOST CRITICAL) - EXACT SAME material, color, pattern, texture, reflections, grain - DO NOT CHANGE under any circumstances' if not visualization_request.tile_swatch_image else 'FLOOR - Apply the provided floor tile swatch pattern (see FLOOR TILE instructions below)'}
2. {'WALLS - Same position, color, texture, material - walls cannot move or change' if not visualization_request.texture_image else 'WALLS - Apply the provided wall texture pattern (see WALL TEXTURE instructions below). Wall positions and structure must stay the same.'}
3. WINDOWS - Same size, position, style, with same light coming through - windows are fixed
4. DOORS - Same position, style, handles - doors are fixed architectural elements
5. CEILING - Same height, color, fixtures, details - ceiling structure is permanent
6. LIGHTING - Same sources, brightness, shadows on walls - preserve existing light setup
7. CAMERA ANGLE - Same perspective, height, focal length - maintain exact viewpoint
8. ROOM DIMENSIONS - Same size, proportions, layout - room size is fixed
9. ARCHITECTURAL FEATURES - Same moldings, trim, baseboards - decorative elements stay
10. BACKGROUND ELEMENTS - Same wall decorations, fixtures, outlets - all fixed elements remain
{existing_furniture_instruction}

IF THE ROOM HAS:
{'- White walls → Keep white walls' if not visualization_request.texture_image else '- Walls → Apply the provided wall texture pattern'}
{'- Hardwood floor → Keep hardwood floor' if not visualization_request.tile_swatch_image else '- Floor → Apply the provided floor tile pattern'}
- A window on the left → Keep window on the left
- 10ft ceiling → Keep 10ft ceiling
- Modern style → Keep modern style base

═══════════════════════════════════════════════════════════════
PRODUCTS TO PLACE ({product_count} items):
{products_detail}

PRODUCT MATCHING REMINDER:
- Reference images are provided below for each product
- When multiple images per product (1/3, 2/3, 3/3): use ALL angles to understand the full design
- Unique shapes (sculptural, curved, spherical) must be preserved exactly
- Output products must be recognizable as the SAME products from references

{self._build_perspective_scaling_instructions(visualization_request.products_to_place, room_analysis, visualization_request.placement_positions)}

{self._build_room_geometry_instructions(room_analysis.get("camera_view_analysis", {}) if isinstance(room_analysis, dict) else getattr(room_analysis, "camera_view_analysis", {}), visualization_request.products_to_place)}

PLACEMENT STRATEGY:
1. Look at the EXACT room in the input image
2. Use the room dimensions and scale references provided above
3. Identify appropriate floor space for each product
4. Place products ON THE FLOOR of THIS room (not floating)
5. Scale products using the RELATIVE sizing instructions above (% of room width, % of door height)
6. Products at the BACK of the room should appear SMALLER due to perspective
7. Arrange products according to type-specific placement rules (see below)
8. Ensure products don't block doorways or windows
9. Keep proper spacing between products (18-30 inches walking space)
10. SPATIAL BALANCE: Distribute products evenly, avoid clustering on one side

CUSTOM POSITION OVERRIDE (IF PROVIDED):
{self._build_custom_position_instructions(visualization_request.placement_positions, visualization_request.products_to_place)}

DO NOT BLOCK EXISTING FURNITURE:
- Identify all existing furniture before placing new items
- Never place new furniture in front of existing pieces
- Find empty floor areas for new items
- Every furniture piece should remain fully visible
- Place new items in different locations, not overlapping

TYPE-SPECIFIC PLACEMENT:

SOFAS & SECTIONALS:
- Place DIRECTLY AGAINST a SOLID wall (2-4 inches gap max)
- NEVER place against windows, glass doors, or sliding doors
- Sofa should be PARALLEL to the wall, touching or nearly touching
CHAIRS:
- Position on sides of existing sofa, angled for conversation
- 18-30 inches spacing from sofa

BENCHES:
- Living room: Place ACROSS from sofa, facing it (3-4 feet distance)
- Bedroom: Place at foot of bed, parallel to bed frame
- Never block coffee table area or remove existing furniture

CENTER/COFFEE TABLE:
- Directly in front of sofa, centered on seating arrangement
- 14-18 inches from sofa's front

SIDE/END TABLE:
- Directly adjacent to sofa armrest (0-6 inches)
- If decor exists on one side, place table on opposite side

STORAGE (bookshelf, cabinet):
- Against walls, not blocking pathways

LAMPS:
- On tables or floor, near seating areas

BEDS:
- Headboard against wall, leave walkway space on at least one side

PLANTERS:
-  NEVER place in front of the sofa or any seating — planters must NOT block furniture
-  NEVER place in the center of the room or in walkways
-  Place in FAR CORNERS of the room or BESIDE (left/right of) sofas/chairs
-  Place against walls in empty spaces
- Balance with other items on opposite side
- Planters are small accent pieces — they should not be prominent

WALL ART / PAINTINGS:
- Mount ON THE WALL, not on floor
- Above sofa: 6-12 inches above sofa back
- Eye level (57-60 inches from floor)
- Do NOT confuse with rugs - wall art goes on WALLS

RUGS / CARPETS:
- Place FLAT ON THE FLOOR under furniture
- Under coffee tables and seating areas
- Do NOT confuse with wall art - rugs go on FLOORS

CUSHIONS / PILLOWS:
- Place ON sofa/chairs, not on floor
- When multiple requested, show ALL of them
- Distribute evenly across sofa

TABLETOP DECOR (vases, sculptures):
- Place ON table surfaces (coffee table, side table, console)
- Small items (10-30cm), not floor pieces

MULTIPLE PRODUCTS NOTE:
Room stays identical regardless of product count. You are adding to an existing photo, not creating a new one.

EXPECTED OUTPUT:
Generate ONE image that shows:
- THE EXACT SAME ROOM from the input (100% preserved)
- WITH {product_count} new furniture products placed inside it
- Products sitting naturally on the floor
- Products appropriately spaced and arranged
- Everything else IDENTICAL to input image

 CRITICAL: FULL ROOM VIEW - NO ZOOM
═══════════════════════════════════════════════════════════════
 DO NOT zoom in on the new product(s)
 DO NOT crop or focus on the area where products are placed
 DO NOT highlight or emphasize the new product(s)
 SHOW THE ENTIRE ROOM exactly as it appears in the input image
 The new product should be visible BUT the image should show the FULL ROOM context
 Camera position, angle, and field of view MUST be IDENTICAL to input
 If input shows a wide room view, output MUST show the same wide room view
 The product is just ONE element in the scene - NOT the focal point
═══════════════════════════════════════════════════════════════

QUALITY CHECKS:
{' Can you overlay the input and output and see the same walls? YES' if not visualization_request.texture_image else ' Did you apply the wall texture from the swatch? YES'}
 Are windows in the same position? YES
{' Is the floor the same material? YES' if not visualization_request.tile_swatch_image else ' Did you apply the floor tile from the swatch? YES'}
 Is the camera angle identical? YES
 Did you only add products{'and apply surface changes' if visualization_request.texture_image or visualization_request.tile_swatch_image else ''}? YES
 Is the room structure unchanged? YES
 Does the output show the FULL ROOM (not zoomed in on product)? YES
 Are ALL products showing their FRONT FACE to the camera? YES

If ANY answer is NO, you've failed the task.

 MANDATORY FRONT ANGLE REQUIREMENT
═══════════════════════════════════════════════════════════════
 ALL PRODUCTS MUST SHOW THEIR FRONT FACE TOWARDS THE CAMERA

This is MANDATORY - products must be oriented correctly:
- Sofas: Show front cushions/seating area facing camera, NOT the back panel
- Tables: Show the front/main side facing camera, NOT a sharp side angle
- Chairs: Show front/seating side facing camera, NOT the chair back
- Cabinets/Storage: Show doors/drawers facing camera
- Lamps: Show the decorative front/shade facing camera
- Beds: Show the headboard and side where you'd get in, NOT just the footboard

 INCORRECT ORIENTATIONS (FAILURES):
- Sofa showing its back (you see the back panel, not cushions)
- Chair showing its back (you see the chair back, not the seat)
- Table at a sharp side angle (can't see the tabletop properly)
- Any furniture "facing away" from the camera

 CORRECT ORIENTATIONS (REQUIRED):
- All products oriented with their "showroom display angle" facing camera
- User can clearly see what each product looks like from its primary view
- Products appear as they would in a furniture catalog - front and center
═══════════════════════════════════════════════════════════════

 LIGHTING & REALISM - MOST CRITICAL FOR NATURAL APPEARANCE
═══════════════════════════════════════════════════════════════
 THE PRODUCTS MUST LOOK LIKE THEY ARE PART OF THE ROOM, NOT ADDED ON TOP OF IT

LIGHTING ANALYSIS (DO THIS FIRST):
1.  IDENTIFY LIGHT SOURCES: Look at the input image and identify ALL light sources:
   - Windows (natural daylight direction, intensity, color temperature)
   - Artificial lights (lamps, ceiling lights, their warm/cool tone)
   - Ambient light (reflected light from walls, floor)
2.  DETERMINE COLOR TEMPERATURE: Is the room warm (yellowish), cool (bluish), or neutral?
3.  NOTE LIGHT DIRECTION: Where are shadows falling? This tells you the primary light direction.
4.  ASSESS AMBIENT LIGHTING: How much fill light is in the shadows?

APPLY MATCHING LIGHTING TO PRODUCTS:
1.  SAME LIGHT DIRECTION: Product highlights MUST come from the same direction as room highlights
2.  SAME COLOR TEMPERATURE: If room has warm lighting, products must have warm highlights
3.  MATCHING SHADOWS: Product shadows must fall in the SAME DIRECTION as existing shadows in room
4.  CONSISTENT EXPOSURE: Products should NOT be brighter or darker than similar surfaces in the room
5.  APPROPRIATE REFLECTIONS: Glossy products should reflect the room's lighting, not different lighting

SHADOW REQUIREMENTS:
- Products MUST cast shadows that match the room's shadow direction and softness
- Shadow color must match existing shadows (not pure black, usually tinted by ambient light)
- Shadow length and angle must be consistent with other objects in the room
- Contact shadows (where product meets floor) must be present and realistic

 CRITICAL: PRODUCTS MUST NOT LOOK "HIGHLIGHTED" OR "SPOTLIT"
- Do NOT render products with studio lighting if the room has natural daylight
- Do NOT make products appear brighter than their surroundings
- Do NOT add artificial highlights that don't match the room's light sources
- Products should blend seamlessly - a viewer should NOT be able to tell they were added

 PHOTOREALISTIC BLENDING REQUIREMENTS:
1. NATURAL INTEGRATION: Products must look like real physical objects photographed IN THIS ROOM, NOT pasted cutouts or digitally added
2. LIGHTING CONSISTENCY: Product highlights and shadows MUST match the room's lighting direction, intensity, and color exactly
3. FLOOR CONTACT: Products must have realistic contact shadows and ground connection - NO floating
4. PERSPECTIVE MATCHING: Products must follow the exact same perspective and vanishing points as the room
5. COLOR HARMONY: Product colors should be influenced by the room's ambient lighting (e.g., warm room = warmer product tones)
6. DEPTH AND DIMENSION: Products should have proper depth cues and look three-dimensional in the space
7. MATERIAL REALISM: Reflections, textures, and material properties must look authentic in THIS room's specific lighting
8. ATMOSPHERE MATCHING: Products should have the same depth-of-field, focus, grain, and atmospheric effects as the room
9. EXPOSURE MATCHING: Products should have the same exposure level as the rest of the room - not brighter, not darker

 AVOID THESE COMMON MISTAKES (WILL MAKE PRODUCTS LOOK FAKE):
-  Do NOT make products look like flat cutouts or stickers
-  Do NOT place products floating above the floor
-  Do NOT ignore the room's lighting when rendering products
-  Do NOT use different lighting conditions for products vs. room (THIS IS THE MAIN ISSUE TO AVOID)
-  Do NOT create harsh, unrealistic edges around products
-  Do NOT forget shadows and reflections
-  Do NOT make products appear "highlighted" or "spotlit" compared to the room
-  Do NOT render products with neutral/studio lighting if room has warm/cool lighting
-  Do NOT make product shadows go in a different direction than room shadows

{self._build_wall_color_instruction(visualization_request.wall_color, visualization_request.texture_image)}

{self._build_surface_instructions(visualization_request)}

OUTPUT: One photorealistic image of THE SAME ROOM with {product_count} product(s) naturally integrated, where products look like they physically exist in the space with proper lighting, shadows, and material interactions."""

            else:
                # Fallback for text-only transformations
                visualization_prompt = f"""Transform this interior space following this design request: {user_request}

Create a photorealistic interior design visualization that addresses the user's request while maintaining realistic proportions, lighting, and materials."""

            # Use Gemini 3 Pro Image (Nano Banana Pro) with LOWER temperature for more consistent results
            model = "gemini-3-pro-image-preview"
            transformed_image = None
            transformation_description = ""

            # Retry configuration for 503 errors
            max_retries = 3
            retry_delay = 2  # Initial delay in seconds

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        logger.info(f"Retry attempt {attempt + 1}/{max_retries} for visualization")

                    logger.info(f"Using {model} with product placement approach")

                    # Build contents list with room image and product images as PIL Images
                    # (same approach as furniture removal which works with google-genai 1.41.0)
                    contents = [visualization_prompt]

                    # Add room image as PIL Image
                    room_image_bytes = base64.b64decode(processed_image)
                    room_pil_image = Image.open(io.BytesIO(room_image_bytes))
                    # Apply EXIF orientation correction (important for smartphone photos)
                    room_pil_image = ImageOps.exif_transpose(room_pil_image)
                    if room_pil_image.mode != "RGB":
                        room_pil_image = room_pil_image.convert("RGB")

                    # Get the input image dimensions for logging
                    input_width, input_height = room_pil_image.size
                    logger.info(f"Input room image (ROOM VIZ, EXIF corrected): {input_width}x{input_height}")

                    contents.append(room_pil_image)

                    # Add product images as PIL Images (multiple angles per product for accuracy)
                    for prod_img in product_images:
                        img_label = f"Product {prod_img['index']} reference image"
                        if prod_img.get("total_images", 1) > 1:
                            img_label += f" ({prod_img['image_number']}/{prod_img['total_images']}) - {prod_img['name']}"
                        else:
                            img_label += f" - {prod_img['name']}"
                        contents.append(f"\n{img_label}:")
                        prod_image_bytes = base64.b64decode(prod_img["data"])
                        prod_pil_image = Image.open(io.BytesIO(prod_image_bytes))
                        if prod_pil_image.mode != "RGB":
                            prod_pil_image = prod_pil_image.convert("RGB")
                        contents.append(prod_pil_image)

                    logger.info(f"[VIZ] Passing {len(product_images)} total reference images to model")

                    # Add wall texture swatch if provided
                    if visualization_request.texture_image:
                        contents.append("\n WALL TEXTURE REFERENCE SWATCH — Apply this pattern to ALL visible walls:")
                        tex_bytes = base64.b64decode(self._preprocess_image_for_editing(visualization_request.texture_image))
                        tex_pil = Image.open(io.BytesIO(tex_bytes)).convert("RGB")
                        contents.append(tex_pil)
                        logger.info("[VIZ] Added wall texture swatch to contents array")

                    # Add floor tile swatch if provided
                    if visualization_request.tile_swatch_image:
                        contents.append(
                            "\n FLOOR TILE REFERENCE SWATCH — Apply this tile pattern to ALL visible floor surfaces:"
                        )
                        tile_bytes = base64.b64decode(
                            self._preprocess_image_for_editing(visualization_request.tile_swatch_image)
                        )
                        tile_pil = Image.open(io.BytesIO(tile_bytes)).convert("RGB")
                        contents.append(tile_pil)
                        logger.info("[VIZ] Added floor tile swatch to contents array")

                    # Add explicit dimension requirements now that we know the input size
                    dimension_instruction = f"""

 MANDATORY OUTPUT RESOLUTION
═══════════════════════════════════════════════════════════════
 INPUT IMAGE: {input_width}x{input_height} pixels
 OUTPUT MUST BE: {input_width}x{input_height} pixels (EXACT SAME RESOLUTION)

- Generate output at EXACTLY {input_width} pixels wide and {input_height} pixels tall
- DO NOT output at a lower resolution than {input_width}x{input_height}
- DO NOT change the aspect ratio
- This is a PRODUCTION quality image - use MAXIMUM resolution
═══════════════════════════════════════════════════════════════
"""
                    contents.append(dimension_instruction)

                    # Use response modalities for image and text generation
                    generate_content_config = types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        temperature=0.25,  # Lower temperature for better room preservation consistency
                    )

                    # Stream response with timeout protection
                    # Use a helper to wrap the streaming loop with asyncio timeout
                    visualization_timeout = 90  # 1.5 minutes max per attempt (with retries)
                    stream_start_time = time.time()
                    final_chunk = None  # Capture final chunk for usage_metadata

                    for chunk in self.genai_client.models.generate_content_stream(
                        model=model,
                        contents=contents,
                        config=generate_content_config,
                    ):
                        final_chunk = chunk  # Always keep reference to last chunk
                        # Check timeout between chunks to prevent indefinite hanging
                        elapsed = time.time() - stream_start_time
                        if elapsed > visualization_timeout:
                            logger.error(f"Visualization stream timeout after {elapsed:.1f}s")
                            raise asyncio.TimeoutError(f"Visualization timed out after {visualization_timeout}s")
                        if (
                            chunk.candidates is None
                            or chunk.candidates[0].content is None
                            or chunk.candidates[0].content.parts is None
                        ):
                            continue

                        for part in chunk.candidates[0].content.parts:
                            if part.inline_data and part.inline_data.data:
                                # Extract generated image data
                                inline_data = part.inline_data
                                image_data = inline_data.data
                                mime_type = inline_data.mime_type or "image/png"

                                # Handle both raw bytes and base64 string bytes
                                # (same approach as furniture removal)
                                if isinstance(image_data, bytes):
                                    # Check first bytes to determine format
                                    # Raw PNG: 89504e47, Raw JPEG: ffd8ff
                                    first_hex = image_data[:4].hex()
                                    logger.info(f"Visualization image first 4 bytes hex: {first_hex}")

                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        # Raw image bytes - encode to base64
                                        logger.info("Raw image bytes detected, encoding to base64")
                                        image_base64 = base64.b64encode(image_data).decode("utf-8")
                                    else:
                                        # Bytes are base64 string - decode to string directly
                                        logger.info("Base64 string bytes detected, using directly")
                                        image_base64 = image_data.decode("utf-8")
                                else:
                                    # Already a string
                                    image_base64 = image_data

                                transformed_image = f"data:{mime_type};base64,{image_base64}"
                                logger.info(f"Generated image with {model} ({len(image_data)} bytes)")

                            elif part.text:
                                transformation_description += part.text

                    # Log with token tracking from final chunk
                    self._log_streaming_operation("visualize_curated_look", model, final_chunk=final_chunk)

                    # If we got here without exception, break the retry loop
                    break

                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    logger.warning(
                        f"TIMEOUT: Google Gemini API timed out after {elapsed:.2f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    # Retry on timeout with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2**attempt)  # Exponential backoff: 2, 4 seconds
                        logger.info(f"Retrying visualization in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Visualization failed after {max_retries} attempts due to timeouts")
                        # Return original image on final timeout
                        return VisualizationResult(
                            rendered_image=visualization_request.base_image,
                            processing_time=elapsed,
                            quality_score=0.0,
                            placement_accuracy=0.0,
                            lighting_realism=0.0,
                            confidence_score=0.0,
                        )
                except Exception as model_error:
                    error_str = str(model_error)
                    # Check if it's a 503 (overloaded) error - retry these
                    if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2**attempt)  # Exponential backoff
                            logger.warning(
                                f"Model overloaded (503), retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Model still overloaded after {max_retries} retries: {error_str}")
                    else:
                        logger.error(f"Model failed: {error_str}")
                    transformed_image = None
                    break  # Don't retry non-503 errors

            processing_time = time.time() - start_time

            # If no image was generated, fall back to original
            if not transformed_image:
                logger.warning("No transformed image generated, using original")
                transformed_image = visualization_request.base_image
            else:
                # Verify and fix output resolution to match input
                try:
                    # Extract base64 data from the transformed image
                    output_b64 = transformed_image
                    if output_b64.startswith("data:"):
                        output_b64 = output_b64.split(",", 1)[1]

                    output_bytes = base64.b64decode(output_b64)
                    output_img = Image.open(io.BytesIO(output_bytes))
                    output_width, output_height = output_img.size

                    logger.info(
                        f"[VIZ] Output resolution: {output_width}x{output_height}, Input was: {input_width}x{input_height}"
                    )

                    # If output is significantly different from input, resize with high quality
                    if output_width != input_width or output_height != input_height:
                        logger.warning(
                            f"[VIZ] Output resolution mismatch! Resizing from {output_width}x{output_height} to {input_width}x{input_height}"
                        )
                        if output_img.mode != "RGB":
                            output_img = output_img.convert("RGB")
                        # Use LANCZOS for high-quality upscaling/downscaling
                        output_img = output_img.resize((input_width, input_height), Image.Resampling.LANCZOS)

                        # Re-encode to base64 with high quality
                        buffer = io.BytesIO()
                        output_img.save(buffer, format="PNG", optimize=False)
                        buffer.seek(0)
                        resized_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                        transformed_image = f"data:image/png;base64,{resized_b64}"
                        logger.info(f"[VIZ] Resized output to match input: {input_width}x{input_height}")
                except Exception as resize_err:
                    logger.warning(f"[VIZ] Could not verify/fix output resolution: {resize_err}")

            if transformation_description:
                logger.info(f"AI description: {transformation_description[:150]}...")

            success = transformed_image != visualization_request.base_image
            logger.info(
                f"Generated visualization with {len(products_description)} products in {processing_time:.2f}s (success: {success})"
            )

            return VisualizationResult(
                rendered_image=transformed_image,
                processing_time=processing_time,
                quality_score=0.88 if success else 0.5,
                placement_accuracy=0.90 if success else 0.0,
                lighting_realism=0.85 if success else 0.0,
                confidence_score=0.87 if success else 0.3,
            )

        except Exception as e:
            logger.error(f"Error generating visualization: {e}", exc_info=True)
            # Return original image on error
            return VisualizationResult(
                rendered_image=visualization_request.base_image,
                processing_time=0.0,
                quality_score=0.5,
                placement_accuracy=0.0,
                lighting_realism=0.0,
                confidence_score=0.3,
            )

    async def generate_text_based_visualization(
        self, base_image: str, user_request: str, lighting_conditions: str = "mixed", render_quality: str = "high"
    ) -> VisualizationResult:
        """
        Generate room visualization based on text description (allows full transformation)
        Used when user types text requesting image transformation (e.g., "make this modern")
        """
        try:
            start_time = time.time()

            # Process the base image - use editing preprocessor to preserve quality
            processed_image = self._preprocess_image_for_editing(base_image)

            # Build transformation prompt with strong room preservation
            visualization_prompt = f"""IMPORTANT: Use the EXACT room shown in this image as your base. Do NOT create a new room.

USER'S DESIGN REQUEST: {user_request}

 CRITICAL DIMENSIONAL REQUIREMENTS
═══════════════════════════════════════════════════════════════
1. OUTPUT IMAGE DIMENSIONS: The output image MUST have the EXACT SAME width and height (in pixels) as the input image
2. ASPECT RATIO: The aspect ratio of the output MUST be IDENTICAL to the input image
3. ROOM PROPORTIONS: The room's length and width proportions MUST remain unchanged
4. IMAGE RESOLUTION: Match the exact resolution of the input - do NOT resize or crop
5. NO DIMENSIONAL CHANGES: The room's physical dimensions (length, width, height) MUST stay the same

 CRITICAL PRESERVATION RULES:
1. USE THIS EXACT ROOM: Keep the same walls, windows, doors, flooring, ceiling, and architectural features shown in the image
2. PRESERVE THE SPACE: Maintain the exact room dimensions, layout, and perspective
3. KEEP EXISTING STRUCTURE: Do not change wall colors, window positions, door locations, or ceiling design unless specifically requested
4. SAME LIGHTING SETUP: Preserve existing light sources and natural lighting from windows

 WHAT YOU CAN DO:
1. Add furniture and decor items as requested: {user_request}
2. Style the space according to user preferences while keeping the room structure
3. Place items naturally within THIS specific room layout
4. Ensure new items match the room's scale and perspective

QUALITY REQUIREMENTS:
- Lighting: {lighting_conditions} - match existing lighting in the image
- Rendering: {render_quality} quality photorealism
- Perspective: Maintain the exact camera angle and viewpoint from the input image

 RESULT: The output must show THE SAME ROOM from the input image, just with design changes applied to furniture/decor."""

            # Use Gemini 3 Pro Image (Nano Banana Pro) for generation
            model = "gemini-3-pro-image-preview"
            parts = [
                types.Part.from_text(text=visualization_prompt),
                types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(processed_image))),
            ]

            contents = [types.Content(role="user", parts=parts)]
            # Use HIGH media resolution for better quality output
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=0.4,
            )

            transformed_image = None
            transformation_description = ""
            final_chunk = None  # Capture final chunk for usage_metadata

            # Stream response
            for chunk in self.genai_client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
            ):
                final_chunk = chunk  # Always keep reference to last chunk
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue

                for part in chunk.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        # Extract generated image data
                        inline_data = part.inline_data
                        image_bytes = inline_data.data
                        mime_type = inline_data.mime_type or "image/png"

                        # Convert to base64 data URI
                        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                        transformed_image = f"data:{mime_type};base64,{image_base64}"
                        logger.info(f"Successfully generated text-based visualization ({len(image_bytes)} bytes)")

                    elif part.text:
                        transformation_description += part.text

            # Log with token tracking from final chunk
            self._log_streaming_operation("generate_text_based_visualization", model, final_chunk=final_chunk)

            processing_time = time.time() - start_time

            # If no image was generated, fall back to original
            if not transformed_image:
                logger.warning("No transformed image generated, using original")
                transformed_image = base_image

            logger.info(f"Generated text-based visualization in {processing_time:.2f}s")

            return VisualizationResult(
                rendered_image=transformed_image,
                processing_time=processing_time,
                quality_score=0.90 if transformed_image != base_image else 0.5,
                placement_accuracy=0.85 if transformed_image != base_image else 0.0,
                lighting_realism=0.88 if transformed_image != base_image else 0.0,
                confidence_score=0.87 if transformed_image != base_image else 0.3,
            )

        except Exception as e:
            logger.error(f"Error generating text-based visualization: {e}", exc_info=True)
            return VisualizationResult(
                rendered_image=base_image,
                processing_time=0.0,
                quality_score=0.5,
                placement_accuracy=0.0,
                lighting_realism=0.0,
                confidence_score=0.3,
            )

    async def generate_iterative_visualization(
        self,
        base_image: str,
        modification_request: str,
        placed_products: List[Dict[str, Any]] = None,
        lighting_conditions: str = "mixed",
        render_quality: str = "high",
        reference_image: Optional[str] = None,
    ) -> VisualizationResult:
        """
        Generate iterative visualization by modifying an existing generated image
        Used when user requests changes to a previously generated visualization (e.g., "place the lamp in the corner")

        Uses centralized VisualizationPrompts for consistent prompt structure.

        Args:
            base_image: Base64 encoded current visualization
            modification_request: User's modification instruction
            placed_products: Products currently in the room (with dimensions)
            lighting_conditions: Room lighting conditions
            render_quality: Desired render quality
            reference_image: Optional reference image for style guidance
        """
        try:
            start_time = time.time()

            # Process the base image (existing visualization) - use editing preprocessor to preserve quality
            processed_image = self._preprocess_image_for_editing(base_image)

            # Detect instruction type for appropriate prompt handling
            instruction_lower = modification_request.lower()
            if any(word in instruction_lower for word in ["move", "place", "position", "shift", "put", "reposition"]):
                instruction_type = "placement"
            elif any(word in instruction_lower for word in ["bright", "light", "dark", "dim", "lighting"]):
                instruction_type = "brightness"
            elif reference_image:
                instruction_type = "reference"
            else:
                instruction_type = "placement"  # Default to placement

            logger.info(f"[IterativeViz] Instruction type: {instruction_type}, request: {modification_request[:50]}...")

            # Use centralized prompt with dimensions
            visualization_prompt = VisualizationPrompts.get_edit_by_instruction_prompt(
                instruction=modification_request,
                instruction_type=instruction_type,
                current_products=placed_products or [],
                reference_image_provided=bool(reference_image),
            )

            # Add quality and lighting requirements
            visualization_prompt += f"""

QUALITY REQUIREMENTS:
- Lighting: {lighting_conditions} - maintain existing light sources
- Rendering: {render_quality} quality photorealism
- Consistency: The room must look like the SAME physical space with the SAME products

 CRITICAL LIGHTING REQUIREMENTS:
 ALL PRODUCTS MUST LOOK LIKE THEY ARE PART OF THE ROOM, NOT ADDED ON TOP OF IT
1. ANALYZE the room's lighting: identify light sources, direction, color temperature (warm/cool)
2. MATCH lighting on products: highlights must come from the same direction as room lighting
3. MATCH shadow direction: product shadows must fall in the same direction as other shadows in room
4. MATCH exposure: products should NOT be brighter or darker than similar surfaces in room
5. NO "SPOTLIGHT" EFFECT: products must NOT look highlighted compared to the room
6. SEAMLESS BLEND: a viewer should NOT be able to tell products were digitally added
"""

            # Use Gemini 3 Pro Image (Nano Banana Pro) for generation
            model = "gemini-3-pro-image-preview"
            parts = [
                types.Part.from_text(text=visualization_prompt),
                types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(processed_image))),
            ]

            contents = [types.Content(role="user", parts=parts)]
            # Use HIGH media resolution for better quality output
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=0.3,  # Lower temperature for more consistent modifications
            )

            transformed_image = None
            transformation_description = ""
            final_chunk = None  # Capture final chunk for usage_metadata

            # Stream response with timeout protection
            timeout_seconds = 60  # 60 second timeout for iterative modifications
            last_chunk_time = time.time()

            try:
                for chunk in self.genai_client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                ):
                    final_chunk = chunk  # Always keep reference to last chunk
                    # Check for timeout between chunks
                    if time.time() - last_chunk_time > timeout_seconds:
                        raise asyncio.TimeoutError(f"No response from Gemini API for {timeout_seconds}s")

                    last_chunk_time = time.time()

                    if (
                        chunk.candidates is None
                        or chunk.candidates[0].content is None
                        or chunk.candidates[0].content.parts is None
                    ):
                        continue

                    for part in chunk.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            # Extract generated image data
                            inline_data = part.inline_data
                            image_bytes = inline_data.data
                            mime_type = inline_data.mime_type or "image/png"

                            # Convert to base64 data URI
                            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                            transformed_image = f"data:{mime_type};base64,{image_base64}"
                            logger.info(f"Successfully generated iterative visualization ({len(image_bytes)} bytes)")

                        elif part.text:
                            transformation_description += part.text

                # Log with token tracking from final chunk
                self._log_streaming_operation("generate_iterative_visualization", model, final_chunk=final_chunk)

            except asyncio.TimeoutError as te:
                logger.error(f"TIMEOUT: {str(te)}")
                # Return original image on timeout
                return VisualizationResult(
                    rendered_image=base_image,
                    processing_time=time.time() - start_time,
                    quality_score=0.0,
                    placement_accuracy=0.0,
                    lighting_realism=0.0,
                    confidence_score=0.0,
                )
            except Exception as stream_error:
                logger.error(f"Streaming error: {str(stream_error)}")
                # Return original on any streaming error
                return VisualizationResult(
                    rendered_image=base_image,
                    processing_time=time.time() - start_time,
                    quality_score=0.0,
                    placement_accuracy=0.0,
                    lighting_realism=0.0,
                    confidence_score=0.0,
                )

            processing_time = time.time() - start_time

            # If no image was generated, fall back to original
            if not transformed_image:
                logger.warning("No modified image generated, using original")
                transformed_image = base_image

            logger.info(f"Generated iterative visualization in {processing_time:.2f}s")

            return VisualizationResult(
                rendered_image=transformed_image,
                processing_time=processing_time,
                quality_score=0.92 if transformed_image != base_image else 0.5,
                placement_accuracy=0.88 if transformed_image != base_image else 0.0,
                lighting_realism=0.90 if transformed_image != base_image else 0.0,
                confidence_score=0.89 if transformed_image != base_image else 0.3,
            )

        except Exception as e:
            logger.error(f"Error generating iterative visualization: {e}", exc_info=True)
            return VisualizationResult(
                rendered_image=base_image,
                processing_time=0.0,
                quality_score=0.5,
                placement_accuracy=0.0,
                lighting_realism=0.0,
                confidence_score=0.3,
            )

    def _build_custom_position_instructions(self, positions: list, products: list) -> str:
        """Build custom position instructions for Gemini prompt using grid-based positioning.

        Supports two modes:
        1. MOVE mode: When positions have fromX/fromY - relocate existing items in the scene
        2. PLACE mode: When positions only have x/y - place products at specific locations
        """
        if not positions or len(positions) == 0:
            return "No custom positions provided. Use default placement strategy above."

        # Check if this is a MOVE operation (positions have fromX/fromY)
        has_move_operations = any(pos.get("fromX") is not None and pos.get("fromY") is not None for pos in positions)

        if has_move_operations:
            return self._build_move_instructions(positions, products)
        else:
            return self._build_placement_instructions(positions, products)

    def _get_grid_position(self, x: float, y: float) -> tuple:
        """Convert x,y coordinates to grid cell description."""
        # X: 0-0.33=left, 0.33-0.67=center, 0.67-1=right
        # Y: 0-0.33=top/back, 0.33-0.67=middle, 0.67-1=bottom/front

        if x < 0.33:
            h_cell = "LEFT"
            h_desc = "left side"
        elif x < 0.67:
            h_cell = "CENTER"
            h_desc = "center"
        else:
            h_cell = "RIGHT"
            h_desc = "right side"

        if y < 0.33:
            v_cell = "TOP"
            v_desc = "back of room"
        elif y < 0.67:
            v_cell = "MID"
            v_desc = "middle"
        else:
            v_cell = "BOT"
            v_desc = "foreground"

        return (f"{v_cell}-{h_cell}", h_desc, v_desc)

    def _build_move_instructions(self, positions: list, products: list) -> str:
        """Build instructions for MOVING existing items in the scene."""
        instructions = []
        instructions.append("=" * 70)
        instructions.append(" MOVE OPERATION - RELOCATE EXISTING ITEMS IN THE SCENE")
        instructions.append("=" * 70)
        instructions.append("")
        instructions.append(" CRITICAL RULES FOR THIS MOVE OPERATION:")
        instructions.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        instructions.append("1. DO NOT add any new furniture or products to the scene")
        instructions.append("2. DO NOT remove any existing items (except moving them)")
        instructions.append("3. ONLY relocate the specific item(s) listed below")
        instructions.append("4. Keep ALL other items in their EXACT current positions")
        instructions.append("5. The scene should look identical EXCEPT for the moved item(s)")
        instructions.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        instructions.append("")
        instructions.append("ITEMS TO MOVE:")
        instructions.append("")

        for pos in positions:
            from_x = pos.get("fromX")
            from_y = pos.get("fromY")
            to_x = pos.get("x", 0.5)
            to_y = pos.get("y", 0.5)
            item_label = pos.get("label", "item")

            if from_x is not None and from_y is not None:
                from_grid, from_h, from_v = self._get_grid_position(from_x, from_y)
                to_grid, to_h, to_v = self._get_grid_position(to_x, to_y)

                instructions.append(f" MOVE: {item_label}")
                instructions.append(
                    f"   FROM: {from_v}, {from_h} (coordinates: X={int(from_x * 100)}%, Y={int(from_y * 100)}%)"
                )
                instructions.append(f"   TO:   {to_v}, {to_h} (coordinates: X={int(to_x * 100)}%, Y={int(to_y * 100)}%)")
                instructions.append("")
                instructions.append(f"    FIND the {item_label} at the FROM location")
                instructions.append(f"    REMOVE it from that location")
                instructions.append(f"    PLACE it at the TO location")
                instructions.append(f"     Keep the item's appearance EXACTLY the same")
                instructions.append("")

        instructions.append("=" * 70)
        instructions.append(" ABSOLUTE RESTRICTIONS:")
        instructions.append("   - NO new furniture, decor, or products may appear")
        instructions.append("   - NO existing items may disappear (except being moved)")
        instructions.append("   - NO changes to items that are NOT being moved")
        instructions.append("   - The room structure, lighting, and background stay identical")
        instructions.append("=" * 70)

        return "\n".join(instructions)

    def _build_placement_instructions(self, positions: list, products: list) -> str:
        """Build instructions for PLACING products at specific locations."""
        instructions = []
        instructions.append("=" * 60)
        instructions.append(" USER-SPECIFIED CUSTOM POSITIONS - OVERRIDE DEFAULT PLACEMENT")
        instructions.append("=" * 60)
        instructions.append("")
        instructions.append("Think of the room as a 3x3 grid (like tic-tac-toe):")
        instructions.append("┌─────────┬─────────┬─────────┐")
        instructions.append("│ TOP-LEFT│TOP-CENTER│TOP-RIGHT│  (back of room)")
        instructions.append("├─────────┼─────────┼─────────┤")
        instructions.append("│MID-LEFT │ CENTER  │MID-RIGHT│  (middle)")
        instructions.append("├─────────┼─────────┼─────────┤")
        instructions.append("│BOT-LEFT │BOT-CENTER│BOT-RIGHT│  (front/foreground)")
        instructions.append("└─────────┴─────────┴─────────┘")
        instructions.append("")
        instructions.append("PLACE EACH PRODUCT IN THE SPECIFIED GRID CELL:")
        instructions.append("")

        for pos in positions:
            # Find the corresponding product
            # Handle instance IDs like "123-1" or "123-2" for products with quantity > 1
            product_id = pos.get("productId") or pos.get("product_id")
            matching_product = None

            # First try exact match (for instance IDs like "123-1")
            for idx, product in enumerate(products):
                if str(product.get("id")) == str(product_id):
                    matching_product = (idx + 1, product.get("full_name") or product.get("name", "unknown"))
                    break

            # If no exact match, try base ID match (extract "123" from "123-1")
            if not matching_product and "-" in str(product_id):
                base_id = str(product_id).rsplit("-", 1)[0]
                for idx, product in enumerate(products):
                    if str(product.get("id")) == base_id:
                        # Use the label from position if available (includes instance info)
                        label = pos.get("label") or product.get("full_name") or product.get("name", "unknown")
                        matching_product = (idx + 1, label)
                        break

            if matching_product:
                product_num, product_name = matching_product
                x = pos.get("x", 0.5)
                y = pos.get("y", 0.5)

                grid_cell, h_desc, v_desc = self._get_grid_position(x, y)

                instructions.append(f" Product {product_num}: {product_name}")
                instructions.append(f"   → GRID CELL: {grid_cell}")
                instructions.append(f"   → Horizontal: {h_desc} (X={int(x * 100)}%)")
                instructions.append(f"   → Depth: {v_desc} (Y={int(y * 100)}%)")
                instructions.append("")

        instructions.append("=" * 60)
        instructions.append(" IMPORTANT: These positions are USER-SPECIFIED overrides!")
        instructions.append("   - Place products in the EXACT grid cells shown above")
        instructions.append("   - DO NOT reposition based on aesthetics")
        instructions.append("   - The user has intentionally chosen these positions")
        instructions.append("=" * 60)

        return "\n".join(instructions)

    async def _download_image(self, image_url: str, max_retries: int = 3) -> Optional[str]:
        """Download and preprocess product image from URL with retry logic"""
        last_error = None

        for attempt in range(max_retries):
            try:
                session = await self._get_session()
                async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        image_bytes = await response.read()
                        image = Image.open(io.BytesIO(image_bytes))

                        # Convert to RGB
                        if image.mode != "RGB":
                            image = image.convert("RGB")

                        # Resize for optimal processing (max 1024px for product images)
                        # Increased from 512px to preserve more product detail
                        max_size = 1024
                        if image.width > max_size or image.height > max_size:
                            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                        # Convert to base64 (use high quality to preserve product details)
                        buffer = io.BytesIO()
                        image.save(buffer, format="JPEG", quality=95, optimize=True)
                        return base64.b64encode(buffer.getvalue()).decode()
                    else:
                        logger.warning(f"Failed to download image from {image_url}: {response.status}")
                        last_error = f"HTTP {response.status}"
            except asyncio.TimeoutError as e:
                logger.warning(f"Timeout downloading image (attempt {attempt + 1}/{max_retries}): {image_url}")
                last_error = str(e) if str(e) else "Timeout"
            except (aiohttp.ClientError, OSError) as e:
                logger.warning(f"Network error downloading image (attempt {attempt + 1}/{max_retries}): {e}")
                last_error = str(e)
            except Exception as e:
                logger.error(f"Error downloading image from {image_url}: {e}")
                last_error = str(e)

            # Exponential backoff before retry
            if attempt < max_retries - 1:
                wait_time = (2**attempt) + (random.random() * 0.5)
                logger.info(f"Retrying image download in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

        logger.error(f"Failed to download image after {max_retries} attempts: {image_url}, last error: {last_error}")
        return None

    def _preprocess_image(self, image_data: str) -> str:
        """
        Preprocess image for AI analysis.

        OPTIMIZATION: Increased max_size to 2048 and quality to 98 for better analysis.
        The larger size helps with room detail detection and the higher quality
        preserves important visual information for accurate room analysis.
        """
        try:
            # Remove data URL prefix if present
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]

            # Decode and process image
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Resize for optimal processing (max 2048px - increased from 1024 for better quality)
            max_size = 2048
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Enhance image quality
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)

            # Convert back to base64 with high quality (98% - increased from 90%)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=98, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode()

        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return image_data

    def _preprocess_image_for_editing(self, image_data: str) -> str:
        """
        Minimal preprocessing for image editing/visualization tasks.

        CRITICAL: To prevent quality degradation on subsequent visualizations,
        this function does NOT re-encode the image. It only strips the data URL
        prefix if present and returns the raw base64 data.

        Re-encoding (even to PNG) causes cumulative quality loss because:
        1. Each decode/encode cycle can alter pixel values slightly
        2. Gemini returns images in its own format - re-encoding adds another conversion
        3. After 5-6 passes, artifacts become visible
        """
        try:
            # Only strip data URL prefix if present - do NOT re-encode
            if image_data.startswith("data:image"):
                # Extract just the base64 part after the comma
                image_data = image_data.split(",")[1]

            # Return as-is without any re-encoding
            return image_data

        except Exception as e:
            logger.error(f"Error preprocessing image for editing: {e}")
            return image_data

    # NOTE: transform_perspective_to_front is commented out - functionality moved into remove_furniture prompt
    # async def transform_perspective_to_front(self, image_data: str, current_viewing_angle: str, workflow_id: str = None) -> str:
    #     """
    #     Transform a side-angle room photo to a front-angle (straight-on) view.
    #     Uses Gemini to regenerate the room from a straight-on perspective.
    #
    #     Args:
    #         image_data: Base64 encoded room image
    #         current_viewing_angle: "diagonal_left", "diagonal_right", "corner", or "straight_on"
    #         workflow_id: Optional workflow ID for tracking all API calls from a single user action
    #
    #     Returns:
    #         Base64 encoded transformed image with front-angle perspective
    #     """
    #     # If already front-facing, return as-is
    #     if current_viewing_angle == "straight_on":
    #         logger.info("Image already has straight-on perspective, skipping transformation")
    #         return image_data
    #
    #     try:
    #         # Convert base64 to PIL Image
    #         if image_data.startswith("data:image"):
    #             image_data = image_data.split(",")[1]
    #
    #         image_bytes = base64.b64decode(image_data)
    #         pil_image = Image.open(io.BytesIO(image_bytes))
    #
    #         # Apply EXIF orientation correction
    #         pil_image = ImageOps.exif_transpose(pil_image)
    #
    #         if pil_image.mode != "RGB":
    #             pil_image = pil_image.convert("RGB")
    #
    #         logger.info(
    #             f"Transforming perspective from {current_viewing_angle} to front view ({pil_image.width}x{pil_image.height})"
    #         )
    #
    #         # Build perspective transformation prompt
    #         angle_descriptions = {
    #             "diagonal_left": "a diagonal left angle (camera positioned to the right, looking left)",
    #             "diagonal_right": "a diagonal right angle (camera positioned to the left, looking right)",
    #             "corner": "a corner angle (camera in the corner, looking diagonally across the room)",
    #         }
    #         angle_desc = angle_descriptions.get(current_viewing_angle, f"a {current_viewing_angle} angle")
    #
    #         prompt = f"""CRITICAL: CHANGE THE CAMERA ANGLE
    #
    # Current view: {angle_desc} (you can see TWO walls meeting at a corner).
    #
    # YOUR TASK: Generate this room from a COMPLETELY DIFFERENT angle - a STRAIGHT-ON FRONT VIEW.
    #
    # WHAT A FRONT VIEW LOOKS LIKE:
    # - The main wall (solid wall, NOT windows) fills the CENTER of the image
    # - This wall is PARALLEL to the image edges (perfectly horizontal at top and bottom)
    # - Side walls are barely visible - just thin slivers on left and right edges
    # - You should NOT see a corner clearly anymore
    # - Floor stretches out in front of the camera
    #
    # WHAT MUST CHANGE:
    # - The angled walls in the current image must become straight/parallel
    # - The corner that's currently visible should now be at the far left or right edge (barely visible)
    # - The perspective lines should converge toward a single vanishing point in the center
    #
    # KEEP THE SAME:
    # - Same room, same size, same colors
    # - Same floor material and color
    # - Same window positions (but viewed from a different angle)
    # - Same ceiling and lighting style
    #
    # IMPORTANT: The resulting image should look VISIBLY DIFFERENT from the input - the angle is completely different!"""
    #
    #         # Generate transformed image
    #         def _run_transform():
    #             response = self.genai_client.models.generate_content(
    #                 model="gemini-3-pro-image-preview",
    #                 contents=[prompt, pil_image],
    #                 config=types.GenerateContentConfig(
    #                     response_modalities=["IMAGE"],
    #                     temperature=0.3,
    #                 ),
    #             )
    #             # Extract and log token usage (workflow_id captured from outer scope)
    #             self.extract_usage_metadata(
    #                 response, operation="transform_perspective", model_override="gemini-3-pro-image-preview", workflow_id=workflow_id
    #             )
    #
    #             result_image = None
    #             parts = None
    #             if hasattr(response, "parts") and response.parts:
    #                 parts = response.parts
    #             elif hasattr(response, "candidates") and response.candidates:
    #                 candidate = response.candidates[0]
    #                 if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
    #                     parts = candidate.content.parts
    #
    #             if parts:
    #                 for part in parts:
    #                     if hasattr(part, "inline_data") and part.inline_data is not None:
    #                         image_bytes_result = part.inline_data.data
    #                         mime_type = getattr(part.inline_data, "mime_type", None) or "image/png"
    #
    #                         if isinstance(image_bytes_result, bytes):
    #                             first_hex = image_bytes_result[:4].hex()
    #                             if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
    #                                 image_base64_result = base64.b64encode(image_bytes_result).decode("utf-8")
    #                             else:
    #                                 image_base64_result = image_bytes_result.decode("utf-8")
    #                             result_image = f"data:{mime_type};base64,{image_base64_result}"
    #                             break
    #
    #             return result_image
    #
    #         loop = asyncio.get_event_loop()
    #         transformed_image = await asyncio.wait_for(loop.run_in_executor(None, _run_transform), timeout=90)
    #
    #         if transformed_image:
    #             logger.info(f"Successfully transformed perspective from {current_viewing_angle} to front view, workflow_id={workflow_id}")
    #             return transformed_image
    #         else:
    #             logger.warning("Perspective transformation produced no image, returning original")
    #             return f"data:image/jpeg;base64,{image_data}" if not image_data.startswith("data:") else image_data
    #
    #     except asyncio.TimeoutError:
    #         logger.error("Perspective transformation timed out after 90 seconds")
    #         return f"data:image/jpeg;base64,{image_data}" if not image_data.startswith("data:") else image_data
    #     except Exception as e:
    #         logger.error(f"Error transforming perspective: {e}")
    #         return f"data:image/jpeg;base64,{image_data}" if not image_data.startswith("data:") else image_data

    async def generate_alternate_view(
        self, visualization_image: str, target_angle: str, products_description: Optional[str] = None
    ) -> str:
        """
        Generate an alternate viewing angle of a room visualization.

        Args:
            visualization_image: The front-view visualization (base64)
            target_angle: "left", "right", or "back"
            products_description: Description of products in the room

        Returns:
            Base64 encoded image from the requested angle
        """
        try:
            # Convert base64 to PIL Image
            image_data = visualization_image
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]

            image_bytes = base64.b64decode(image_data)
            pil_image = Image.open(io.BytesIO(image_bytes))

            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            logger.info(f"Generating {target_angle} view of visualization ({pil_image.width}x{pil_image.height})")

            # Build angle-specific prompts - SIMPLE and DIRECT instructions
            # Key insight: Focus on WHAT to show, emphasize furniture stays in place
            angle_prompts = {
                "left": """TASK: Generate a LEFT SIDE VIEW of this room.

CAMERA POSITION: You are now standing at the LEFT WALL, looking toward the RIGHT WALL (90° clockwise rotation from original view).

WHAT YOU SHOULD NOW SEE:
- The RIGHT WALL of the room becomes your main background
- Windows/doors that were on the LEFT side of the original are now BEHIND the camera (not visible or barely at edge)
- The back wall from the original (where furniture may be against) is now on your RIGHT edge
- You see NEW wall space on your LEFT side (the front wall from original view)

FURNITURE RULES - THIS IS CRITICAL:
- FURNITURE DOES NOT MOVE - it stays in the EXACT same physical position in the room
- You are simply viewing the same furniture from a different angle
- A sofa that was facing you in the original is now seen from its SIDE (you see the armrest profile, not the front cushions)
- DO NOT rotate, move, or rearrange any furniture - the camera moved, NOT the furniture
- Coffee tables, rugs, and other items remain in their exact positions

MAINTAIN: Same room dimensions, wall colors, floor, ceiling, lighting style. Photorealistic quality.""",
                "right": """TASK: Generate a RIGHT SIDE VIEW of this room.

CAMERA POSITION: You are now standing at the RIGHT WALL, looking toward the LEFT WALL (90° counter-clockwise rotation from original view).

WHAT YOU SHOULD NOW SEE:
- The LEFT WALL of the room becomes your main background
- Windows/doors on the LEFT side of the original are now your CENTER BACKGROUND (prominently visible)
- Features on the RIGHT side of original are now BEHIND the camera (not visible)
- The back wall from original is now on your LEFT edge

FURNITURE RULES - THIS IS CRITICAL:
- FURNITURE DOES NOT MOVE - it stays in the EXACT same physical position in the room
- You are simply viewing the same furniture from a different angle
- A sofa that was facing you in the original is now seen from its SIDE (you see the armrest profile, not the front cushions)
- DO NOT rotate, move, or rearrange any furniture - the camera moved, NOT the furniture
- Coffee tables, rugs, and other items remain in their exact positions

MAINTAIN: Same room dimensions, wall colors, floor, ceiling, lighting style. Photorealistic quality.""",
                "back": """TASK: Generate a BACK VIEW of this room (180° turn from original).

CAMERA POSITION: You walked to the BACK of the room and turned around. Now looking at the FRONT WALL (where the entrance likely is).

WHAT YOU SHOULD NOW SEE:
- The FRONT WALL (which was behind the original camera) is now your main background
- You likely see a door or entrance since you're looking toward where people enter the room
- LEFT wall is still on your LEFT, RIGHT wall is still on your RIGHT
- The back wall (from original) is now BEHIND you, not visible

FURNITURE RULES - THIS IS CRITICAL:
- FURNITURE DOES NOT MOVE - it stays in the EXACT same physical position in the room
- Furniture that was in the BACK of the original (near the back wall) is now CLOSE TO YOU or behind the camera
- Furniture that was in the FRONT/FOREGROUND of the original is now in your BACKGROUND
- You see the BACKS of furniture items that were facing the original camera
- DO NOT rotate, move, or rearrange any furniture - the camera moved, NOT the furniture

MAINTAIN: Same room dimensions, wall colors, floor, ceiling, lighting style. Photorealistic quality.""",
            }

            if target_angle not in angle_prompts:
                raise ValueError(f"Invalid target angle: {target_angle}. Must be 'left', 'right', or 'back'")

            products_info = f"\n\n PRODUCTS IN ROOM: {products_description}" if products_description else ""

            prompt = f"""{angle_prompts[target_angle]}
{products_info}

CRITICAL REMINDERS:
1. FURNITURE STAYS IN PLACE - Only the camera viewpoint changes
2. Same room dimensions, colors, floor, ceiling
3. Photorealistic interior design photograph quality

DO NOT:
- Move or rearrange any furniture
- Rotate furniture to face the new camera angle
- Add or remove any items"""

            # Generate alternate view
            def _run_generate():
                response = self.genai_client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=[prompt, pil_image],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        temperature=0.4,
                    ),
                )
                # Extract and log token usage
                self.extract_usage_metadata(
                    response, operation="generate_alternate_view", model_override="gemini-3-pro-image-preview"
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
                            image_bytes_result = part.inline_data.data
                            mime_type = getattr(part.inline_data, "mime_type", None) or "image/png"

                            if isinstance(image_bytes_result, bytes):
                                first_hex = image_bytes_result[:4].hex()
                                if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                    image_base64_result = base64.b64encode(image_bytes_result).decode("utf-8")
                                else:
                                    image_base64_result = image_bytes_result.decode("utf-8")
                                result_image = f"data:{mime_type};base64,{image_base64_result}"
                                break

                return result_image

            loop = asyncio.get_event_loop()
            alternate_image = await asyncio.wait_for(loop.run_in_executor(None, _run_generate), timeout=90)

            if alternate_image:
                logger.info(f"Successfully generated {target_angle} view")
                return alternate_image
            else:
                raise ValueError(f"Failed to generate {target_angle} view - no image produced")

        except asyncio.TimeoutError:
            logger.error(f"Alternate view generation ({target_angle}) timed out after 90 seconds")
            raise ValueError(f"Timeout generating {target_angle} view")
        except Exception as e:
            logger.error(f"Error generating alternate view ({target_angle}): {e}")
            raise

    def _calculate_relative_scale(
        self, product_dimensions: Dict[str, Any], room_dimensions: Dict[str, float], placement_depth: str = "midground"
    ) -> Dict[str, Any]:
        """
        Convert absolute product dimensions to relative room percentages
        with perspective adjustment for realistic visualization.

        Args:
            product_dimensions: Dict with width, depth, height in inches
            room_dimensions: Dict with estimated_width_ft, estimated_length_ft, etc.
            placement_depth: "foreground", "midground", or "background"

        Returns:
            Dict with relative percentages and perspective factors
        """
        room_width_inches = room_dimensions.get("estimated_width_ft", 12) * 12
        room_depth_inches = room_dimensions.get("estimated_length_ft", 15) * 12
        room_height_inches = room_dimensions.get("estimated_height_ft", 9) * 12

        # Parse product dimensions (handle both float and string values)
        def parse_dim(val):
            if val is None:
                return 0
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0

        product_width = parse_dim(product_dimensions.get("width"))
        product_depth = parse_dim(product_dimensions.get("depth"))
        product_height = parse_dim(product_dimensions.get("height"))

        # Calculate room percentages
        width_percent = (product_width / room_width_inches) * 100 if product_width and room_width_inches else None
        depth_percent = (product_depth / room_depth_inches) * 100 if product_depth and room_depth_inches else None
        height_percent = (product_height / room_height_inches) * 100 if product_height and room_height_inches else None

        # Perspective adjustment factor based on depth
        # Objects in background appear smaller due to perspective foreshortening
        perspective_factors = {"foreground": 1.0, "midground": 0.75, "background": 0.55}
        perspective_factor = perspective_factors.get(placement_depth, 0.75)

        # Door reference (standard door is 80 inches / 6.67 feet)
        door_height_reference = 80  # inches
        height_vs_door = (product_height / door_height_reference) * 100 if product_height else None

        return {
            "width_percent": round(width_percent, 1) if width_percent else None,
            "depth_percent": round(depth_percent, 1) if depth_percent else None,
            "height_percent": round(height_percent, 1) if height_percent else None,
            "perspective_factor": perspective_factor,
            "apparent_width_percent": round(width_percent * perspective_factor, 1) if width_percent else None,
            "height_vs_door_percent": round(height_vs_door, 1) if height_vs_door else None,
            "raw_dimensions": {"width": product_width, "depth": product_depth, "height": product_height},
        }

    def _build_wall_color_instruction(self, wall_color: Optional[Dict[str, Any]], texture_image: Optional[str] = None) -> str:
        """
        Build wall color instruction for visualization prompts.

        Args:
            wall_color: Optional dict with 'name', 'code', 'hex_value' for wall color to apply
            texture_image: If provided, texture overrides wall color (they are mutually exclusive)

        Returns:
            Formatted wall color instruction string
        """
        # Texture overrides wall color for walls
        if texture_image:
            return ""
        if wall_color:
            color_name = wall_color.get("name", "Unknown")
            color_code = wall_color.get("code", "")
            color_hex = wall_color.get("hex_value", "")
            logger.info(f" WALL COLOR REQUESTED: {color_name} ({color_code}) - {color_hex}")
            return f""" WALL COLOR CHANGE - APPLY NEW WALL COLOR
Paint ALL visible walls with the following color:

 WALL COLOR TO APPLY:
- Name: {color_name} (Asian Paints)
- Code: {color_code}
- Hex: {color_hex}

 WALL COLOR RULES:
- Apply this EXACT color to ALL visible walls
- Match the hex value {color_hex} as closely as possible
- Maintain the wall's existing texture and lighting conditions
- Shadows and highlights on walls should still be visible (don't make walls flat)
- The color should look like professionally painted walls

 DO NOT change the ceiling color - ceiling remains as-is
 DO NOT change window frames, door frames, or trim
 DO NOT add textures, patterns, or wallpaper - just solid paint color"""
        else:
            return """ WALL COLOR PRESERVATION - ABSOLUTE REQUIREMENT
 DO NOT CHANGE THE WALL COLOR - walls must remain EXACTLY the same color as input
 DO NOT add paint, wallpaper, or any wall treatment that wasn't there
- If walls are white → output walls MUST be white
- If walls are grey → output walls MUST be grey
- The wall color scheme is FIXED - you are ONLY adding furniture"""

    def _build_surface_instructions(self, viz_request) -> str:
        """Build surface instructions (texture + tile) for generate_room_visualization prompts."""
        instructions = ""
        if viz_request.texture_image and viz_request.texture_name:
            instructions += f"""
 WALL TEXTURE — APPLY TO PRIMARY WALL ONLY
A wall texture swatch image is provided AFTER the product reference images.
TEXTURE INFO: {viz_request.texture_name} ({viz_request.texture_type or 'textured'} finish)
WALL TEXTURE RULES:
1. Study the texture swatch for its color palette, material feel, and surface character
2. Apply the texture ONLY to the PRIMARY wall (main wall facing the camera) — NOT side or adjacent walls
3. DO NOT tile or repeat the swatch — render the wall as one continuous hand-applied finish
4. Preserve natural shadows and lighting ON the texture
5. DO NOT apply texture to ceiling, floor, furniture, or any wall other than the primary wall
6. Side walls must keep their ORIGINAL color and finish
"""
        if viz_request.tile_swatch_image and viz_request.tile_name:
            tile_size_desc = ""
            if viz_request.tile_width_mm and viz_request.tile_height_mm:
                tile_size_desc = f"{viz_request.tile_width_mm} mm × {viz_request.tile_height_mm} mm"
            else:
                tile_size_desc = viz_request.tile_size or "standard size"
            instructions += f"""
 FLOOR TILE — APPLY TILE PATTERN
A floor tile swatch image is provided AFTER the product reference images.
TILE INFO: {viz_request.tile_name} ({tile_size_desc}, {viz_request.tile_finish or 'standard'})
FLOOR TILE RULES:
1. Apply this EXACT tile pattern to ALL visible FLOOR surfaces ONLY
2. Each tile is {tile_size_desc} — scale correctly using door height (~2000mm) as reference
3. Add thin, natural grout lines between tiles
4. Apply perspective foreshortening and appropriate reflectivity
5.  NEVER apply tile to WALLS — tiles go ONLY on the FLOOR (horizontal ground surface)
6.  NEVER apply tile to the ceiling or any vertical surface
7. The boundary between floor and wall must remain clear
"""
        return instructions

    def _build_perspective_scaling_instructions(
        self,
        products: List[Dict[str, Any]],
        room_analysis: Optional[Dict[str, Any]] = None,
        placement_positions: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Build perspective-aware scaling instructions for the visualization prompt.

        Args:
            products: List of products to place (with dimensions in product data)
            room_analysis: Dict containing room dimensions and scale_references
            placement_positions: Optional list of position dicts from VisualizationRequest

        Returns:
            Formatted instruction string for the visualization prompt
        """
        # Convert placement_positions list to dict for easier lookup
        positions_dict: Dict[int, str] = {}
        if placement_positions:
            for pos in placement_positions:
                if isinstance(pos, dict) and "product_index" in pos and "position" in pos:
                    positions_dict[pos["product_index"]] = pos["position"]
        if room_analysis is None:
            room_analysis = {}

        room_dims = room_analysis.get(
            "dimensions", {"estimated_width_ft": 12, "estimated_length_ft": 15, "estimated_height_ft": 9}
        )
        scale_refs = room_analysis.get("scale_references", {})
        camera_perspective = scale_refs.get("camera_perspective", {})

        instruction = """
PERSPECTIVE-AWARE SCALING SYSTEM

ROOM CONTEXT:
"""
        # Add room dimension context
        room_width_ft = room_dims.get("estimated_width_ft", 12)
        room_depth_ft = room_dims.get("estimated_length_ft", 15)
        room_height_ft = room_dims.get("estimated_height_ft", 9)

        instruction += f"""- Estimated room size: ~{room_width_ft}ft W × {room_depth_ft}ft D × {room_height_ft}ft H
- Room width in inches: ~{room_width_ft * 12} inches
- Room depth in inches: ~{room_depth_ft * 12} inches
"""

        # Add camera perspective context
        camera_angle = camera_perspective.get("angle", "eye_level")
        focal_length = camera_perspective.get("estimated_focal_length", "normal")
        instruction += f"""- Camera perspective: {camera_angle} angle, {focal_length} lens
"""

        # Add reference object anchors
        instruction += """
SCALE ANCHORS:
- Standard door: 80" tall
- Standard window: 36-48" wide
- Ceiling: 8-9 feet
- Sofa depth: 32-40"
- Coffee table height: 16-18"
"""

        if scale_refs.get("door_visible"):
            door_percent = scale_refs.get("door_apparent_height_percent", 25)
            instruction += f"""
DOOR DETECTED: Occupying ~{door_percent}% of image height. Use as scale reference.
"""

        # Add per-product relative scaling
        instruction += """
PRODUCT SIZING:
"""

        for i, product in enumerate(products):
            # Get product dimensions from various possible locations
            dims = product.get("dimensions", {})
            if not dims:
                # Try to get from product attributes
                dims = {}
                for attr in ["width", "depth", "height"]:
                    if attr in product:
                        dims[attr] = product[attr]

            product_name = product.get("name", f"Product {i+1}")

            # Determine placement depth based on position
            placement_depth = "midground"  # default
            if positions_dict and i in positions_dict:
                pos_str = positions_dict[i].lower()
                if "back" in pos_str or "far" in pos_str:
                    placement_depth = "background"
                elif "front" in pos_str or "foreground" in pos_str:
                    placement_depth = "foreground"

            relative = self._calculate_relative_scale(dims, room_dims, placement_depth)

            instruction += f"""
{i+1}. {product_name}:
"""
            if relative["raw_dimensions"]["width"] or relative["raw_dimensions"]["height"]:
                instruction += f"""   - Absolute dimensions: {relative['raw_dimensions']['width'] or 'N/A'}" W × {relative['raw_dimensions']['depth'] or 'N/A'}" D × {relative['raw_dimensions']['height'] or 'N/A'}" H
"""
                if relative["width_percent"]:
                    instruction += f"""   - Should occupy ~{relative['width_percent']}% of room width
"""
                if relative["height_vs_door_percent"]:
                    instruction += f"""   - Height should be ~{relative['height_vs_door_percent']}% of a standard door height (80")
"""
                instruction += f"""   - Placement depth: {placement_depth.upper()} (scale factor: {relative['perspective_factor']})
"""
            else:
                instruction += """   - No dimensions provided - estimate from product reference image
   - Use room context and other products for relative sizing
"""

        instruction += """
PERSPECTIVE DEPTH:
- FOREGROUND (100%): Front of image, closest to camera
- MIDGROUND (70-80%): Center of room
- BACKGROUND (50-60%): Near back wall, furthest from camera

SCALING CHECKS:
- Compare product heights to door (80" standard)
- Sofa (84-96" wide) should occupy ~40-55% of room width
- Products at BACK appear SMALLER than foreground
- Coffee table ~1/2 to 2/3 width of sofa
"""

        return instruction

    def _create_fallback_room_analysis(self) -> RoomAnalysis:
        """Create fallback room analysis"""
        return RoomAnalysis(
            room_type="living_room",
            dimensions={"estimated_width_ft": 12, "estimated_length_ft": 15, "estimated_height_ft": 9, "square_footage": 180},
            lighting_conditions="mixed",
            color_palette=["neutral", "warm_gray", "white"],
            existing_furniture=[],
            architectural_features=["windows"],
            style_assessment="contemporary",
            confidence_score=0.3,
            scale_references={
                "door_visible": False,
                "window_visible": True,
                "camera_perspective": {
                    "angle": "eye_level",
                    "estimated_focal_length": "normal",
                    "estimated_distance_to_back_wall_ft": 15.0,
                },
            },
            camera_view_analysis={
                "viewing_angle": "straight_on",
                "primary_wall": "back",
                "floor_center_location": "image_center",
                "recommended_furniture_zone": "center_floor",
            },
        )

    def _map_position_to_room_geometry(
        self, grid_position: str, camera_view_analysis: Dict[str, Any], furniture_type: str
    ) -> str:
        """
        Convert grid-based position to room-aware placement instruction.

        For diagonal camera angles, "CENTER" might map to "against the primary wall"
        rather than literally in the middle of the image.

        Args:
            grid_position: Grid cell like "CENTER", "TOP-LEFT", "MID-RIGHT"
            camera_view_analysis: Camera view analysis from room analysis
            furniture_type: Type of furniture being placed (sofa, coffee_table, etc.)

        Returns:
            String instruction for room-aware placement
        """
        viewing_angle = camera_view_analysis.get("viewing_angle", "straight_on")
        primary_wall = camera_view_analysis.get("primary_wall", "back")
        recommended_zone = camera_view_analysis.get("recommended_furniture_zone", "center_floor")

        # Normalize furniture type for matching
        furniture_lower = furniture_type.lower() if furniture_type else ""

        # Wall-MOUNTED items (hang ON wall, not against wall)
        wall_mounted_keywords = [
            "wall art",
            "wall hanging",
            "painting",
            "tapestry",
            "artwork",
            "wall decor",
            "canvas",
            "poster",
            "frame",
            "mirror",
        ]

        # Large furniture that should go against walls (on floor, backed to wall)
        wall_furniture_keywords = [
            "sofa",
            "couch",
            "sectional",
            "bed",
            "console",
            "tv_unit",
            "tv stand",
            "bookshelf",
            "dresser",
            "cabinet",
            "sideboard",
        ]

        # Center furniture that can be in open floor
        center_furniture_keywords = ["coffee_table", "coffee table", "ottoman", "pouf", "center table"]

        # Floor rugs/carpets (explicitly on floor, NOT wall art)
        floor_rug_keywords = ["rug", "carpet", "area rug", "floor mat", "dhurrie", "kilim"]

        # Beside-furniture items (side tables, lamps)
        beside_furniture_keywords = ["side_table", "side table", "end table", "lamp", "floor lamp", "plant", "planter"]

        is_wall_mounted = any(kw in furniture_lower for kw in wall_mounted_keywords)
        is_wall_furniture = any(kw in furniture_lower for kw in wall_furniture_keywords)
        is_center_furniture = any(kw in furniture_lower for kw in center_furniture_keywords)
        is_floor_rug = any(kw in furniture_lower for kw in floor_rug_keywords)
        is_beside_furniture = any(kw in furniture_lower for kw in beside_furniture_keywords)

        # Build placement instruction based on furniture type and camera angle

        # WALL-MOUNTED items (art, paintings, tapestries) - hang ON the wall
        if is_wall_mounted:
            return f"HANG ON THE WALL - this is wall art/decor, NOT a rug. Mount vertically on the {primary_wall} wall surface, typically above furniture (sofa, console, bed). Position at eye level or 6-12 inches above furniture back. Do NOT place on the floor - wall art goes ON walls, not ON floors."

        # FLOOR RUGS - place flat on floor
        elif is_floor_rug:
            return "Place FLAT ON THE FLOOR under the seating arrangement. The rug should be centered in the room's floor space, under or in front of the sofa/seating area. Do NOT hang on wall - rugs go ON floors."

        elif is_wall_furniture:
            if viewing_angle == "diagonal_left":
                return f"Place AGAINST the {primary_wall} wall (the main visible wall, which appears on the RIGHT side of this diagonal view). Do NOT place floating in the center or in the corner where walls meet."
            elif viewing_angle == "diagonal_right":
                return f"Place AGAINST the {primary_wall} wall (the main visible wall, which appears on the LEFT side of this diagonal view). Do NOT place floating in the center or in the corner where walls meet."
            elif viewing_angle == "corner":
                return f"Place AGAINST the {primary_wall} wall, NOT in the corner where the two walls meet. Position parallel to the wall, not diagonally."
            else:  # straight_on
                return f"Place against the back wall or in the {recommended_zone}, centered in the room's floor space."

        elif is_center_furniture:
            if viewing_angle in ["diagonal_left", "diagonal_right", "corner"]:
                return f"Place on the floor in the actual room center (which may be {camera_view_analysis.get('floor_center_location', 'slightly off from image center')}). Position in front of the main seating area, maintaining 14-18 inches clearance from the sofa."
            else:
                return f"Place centered on the floor in the {recommended_zone}, in front of the main seating arrangement."

        elif is_beside_furniture:
            return f"Place adjacent to the main seating (at the arm/end of a sofa), within arm's reach. For diagonal camera views, position relative to where the sofa would be placed against the {primary_wall} wall."

        else:
            # Default: use the recommended zone
            return f"Place appropriately in the {recommended_zone} area, following the natural room layout."

    def _build_room_geometry_instructions(self, camera_view_analysis: Dict[str, Any], products: List[Dict[str, Any]]) -> str:
        """
        Build room geometry awareness instructions for visualization prompt.

        Args:
            camera_view_analysis: Camera view analysis from room analysis
            products: List of products being placed

        Returns:
            String with room geometry instructions for Gemini
        """
        viewing_angle = camera_view_analysis.get("viewing_angle", "straight_on")
        primary_wall = camera_view_analysis.get("primary_wall", "back")
        floor_center = camera_view_analysis.get("floor_center_location", "image_center")
        recommended_zone = camera_view_analysis.get("recommended_furniture_zone", "center_floor")
        walls_to_avoid = camera_view_analysis.get("walls_to_avoid", [])

        # Build walls to avoid warning
        if walls_to_avoid:
            walls_avoid_warning = f"""
 CRITICAL - WALLS TO AVOID (WINDOWS/GLASS DOORS)
DO NOT place large furniture (sofas, beds, consoles) against these walls:
{', '.join(walls_to_avoid).upper()}

These walls have large windows, glass doors, or sliding doors.
Placing furniture against them would BLOCK the windows/doors - this is WRONG.
"""
        else:
            walls_avoid_warning = ""

        # Build angle-specific explanation
        if viewing_angle == "straight_on":
            angle_explanation = """This photo is taken STRAIGHT-ON - the camera faces a wall directly.
   - Walls appear parallel to image edges
   - The center of the image is approximately the center of the floor
   - Standard grid-based positioning works well"""
        elif viewing_angle == "diagonal_left":
            angle_explanation = f"""This photo is taken from a DIAGONAL-LEFT angle (~30-60° from straight).
   - The RIGHT side of the image shows the primary wall ({primary_wall} wall)
   - The floor center is {floor_center} (NOT necessarily at image center)
   - Large furniture should be placed against the {primary_wall} wall on the RIGHT
   - Do NOT place sofas/beds in the image center - that may be a corner"""
        elif viewing_angle == "diagonal_right":
            angle_explanation = f"""This photo is taken from a DIAGONAL-RIGHT angle (~30-60° from straight).
   - The LEFT side of the image shows the primary wall ({primary_wall} wall)
   - The floor center is {floor_center} (NOT necessarily at image center)
   - Large furniture should be placed against the {primary_wall} wall on the LEFT
   - Do NOT place sofas/beds in the image center - that may be a corner"""
        elif viewing_angle == "corner":
            angle_explanation = f"""This photo is taken from a CORNER of the room.
   - Two walls are visible at angles on left and right
   - The primary wall for furniture is: {primary_wall}
   - The floor center is {floor_center}
   - AVOID placing large furniture in the corner where walls meet
   - Place sofas/beds PARALLEL to walls, not diagonal"""
        else:
            angle_explanation = "Standard placement applies."

        # Generate per-product room-aware instructions
        product_instructions = []
        for i, product in enumerate(products):
            product_name = product.get("name", f"Product {i+1}")
            # Try to infer furniture type from name or category
            furniture_type = product_name.lower()
            if product.get("category"):
                furniture_type = f"{furniture_type} {product.get('category', '').lower()}"

            room_aware_instruction = self._map_position_to_room_geometry(
                "CENTER",  # Default position, actual position handled by custom instructions
                camera_view_analysis,
                furniture_type,
            )
            product_instructions.append(f"   {i+1}. {product_name}: {room_aware_instruction}")

        products_section = "\n".join(product_instructions) if product_instructions else "   (Follow general placement rules)"

        return f"""
 ROOM GEOMETRY AWARENESS (CRITICAL FOR SIDE-ANGLE PHOTOS)
═══════════════════════════════════════════════════════════════
{walls_avoid_warning}
 CAMERA VIEWING ANGLE: {viewing_angle.upper().replace('_', ' ')}
{angle_explanation}

 ROOM LAYOUT:
- Primary Wall (best for large furniture): {primary_wall.upper()} wall
- Actual Floor Center: {floor_center.replace('_', ' ')}
- Recommended Furniture Zone: {recommended_zone.replace('_', ' ')}

 ROOM-AWARE PLACEMENT FOR EACH PRODUCT:
{products_section}

 CRITICAL RULES FOR DIAGONAL/CORNER CAMERA VIEWS:
1. SOFAS & LARGE SEATING: Place FLUSH AGAINST SOLID walls (2-4 inch gap max), NOT floating in image center
2. The "center" of the IMAGE may NOT be the "center" of the ROOM floor
3. For diagonal views, one wall is more prominent - that's where sofas go (if it's a solid wall)
4. NEVER place sofas diagonally across corners unless explicitly requested
5. Coffee tables go in front of seating, relative to where the seating actually is
6. NEVER place furniture against floor-to-ceiling windows or glass doors

 DO NOT:
- Leave large gaps between sofa back and wall - sofas should be TOUCHING or nearly touching the wall
- Place a sofa in the geometric center of the image if this is a diagonal shot
- Float large furniture in what appears to be a corner in the room
- Place sofas/beds/large furniture AGAINST WINDOWS or GLASS DOORS
- Block natural light by putting furniture in front of windows
- Ignore the room's actual layout in favor of image pixel coordinates

 DO:
- Place furniture where a real interior designer would place it
- Put sofas FLUSH against the primary SOLID wall ({primary_wall}) with minimal gap - never against windows
- Center coffee tables relative to the seating arrangement
- Keep windows/glass doors unobstructed
- Consider the actual room geometry, not just the camera's view

═══════════════════════════════════════════════════════════════
"""

    def _create_fallback_spatial_analysis(self) -> SpatialAnalysis:
        """Create fallback spatial analysis"""
        return SpatialAnalysis(
            layout_type="open",
            traffic_patterns=["main_entrance_to_seating"],
            focal_points=[{"type": "window", "position": "main_wall", "importance": "high"}],
            available_spaces=[{"area": "center", "suitable_for": ["seating"], "accessibility": "high"}],
            placement_suggestions=[{"furniture_type": "sofa", "recommended_position": "facing_window"}],
            scale_recommendations={"sofa_length": "84_inches", "coffee_table": "48x24_inches"},
        )

    async def get_usage_statistics(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return {
            **self.usage_stats,
            "success_rate": (self.usage_stats["successful_requests"] / max(self.usage_stats["total_requests"], 1) * 100),
            "average_processing_time": (
                self.usage_stats["total_processing_time"] / max(self.usage_stats["successful_requests"], 1)
            ),
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            test_payload = {
                "contents": [{"parts": [{"text": "Test connection. Respond with 'OK'."}]}],
                "generationConfig": {"maxOutputTokens": 10},
            }

            start_time = time.time()
            await self._make_api_request("models/gemini-3-pro-preview:generateContent", test_payload, operation="health_check")
            response_time = time.time() - start_time

            return {
                "status": "healthy",
                "response_time": response_time,
                "api_key_valid": True,
                "usage_stats": await self.get_usage_statistics(),
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "api_key_valid": bool(self.api_key)}

    async def analyze_image_with_prompt(self, image: str, prompt: str) -> str:
        """
        Analyze an image with a custom prompt using Gemini Vision

        Args:
            image: Base64 encoded image data
            prompt: Custom prompt for analysis

        Returns:
            str: Gemini's text response
        """
        logger.info("[GoogleAIStudioService] Analyzing image with custom prompt")

        # Prepare image data
        image_data = self._preprocess_image(image)

        # Build request payload
        payload = {
            "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": image_data}}]}]
        }

        try:
            # Make API request
            response = await self._make_api_request("generateContent", payload, operation="analyze_image_with_prompt")

            # Extract text response
            if response and "candidates" in response:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]

            logger.warning("[GoogleAIStudioService] No valid response from Gemini")
            return ""

        except Exception as e:
            logger.error(f"[GoogleAIStudioService] Error analyzing image: {str(e)}")
            raise

    async def generate_image_with_prompt(self, base_image: str, prompt: str) -> str:
        """
        Generate/modify an image using Gemini with a custom prompt

        Note: Gemini 2.5 Flash currently doesn't directly support image generation.
        This method uses Gemini to analyze and describe the transformation,
        then returns the base image (in production, you'd use an image generation model)

        Args:
            base_image: Base64 encoded source image
            prompt: Prompt describing the desired transformation

        Returns:
            str: Base64 encoded result image

        TODO: Integrate with actual image generation/editing model (like DALL-E, Stable Diffusion, etc.)
        """
        logger.info("[GoogleAIStudioService] Generating image with prompt (placeholder)")
        logger.warning("[GoogleAIStudioService] Image generation not yet fully implemented - returning base image")

        # For now, return the base image
        # In production, this would:
        # 1. Use Gemini to understand the prompt
        # 2. Call an image generation/editing API (Replicate, DALL-E, etc.)
        # 3. Return the generated image

        # Placeholder: Just return the base image
        # TODO: Implement actual image isolation using background removal or segmentation
        return base_image

    async def change_wall_color(
        self,
        room_image: str,
        color_name: str,
        color_hex: str,
        user_id: str = None,
        session_id: str = None,
    ) -> Optional[str]:
        """
        Change wall color in a room visualization using Gemini inpainting.

        Uses Gemini's native image editing capabilities to repaint walls
        while preserving all furniture and other room elements.

        Args:
            room_image: Base64 encoded room visualization image
            color_name: Asian Paints color name (e.g., "Air Breeze")
            color_hex: Hex color value (e.g., "#F5F5F0")
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking

        Returns:
            Base64 encoded result image with new wall color, or None on failure
        """
        try:
            logger.info(f"[WallColor] Changing wall color to {color_name} ({color_hex})")

            # Use editing preprocessor to preserve quality
            processed_room = self._preprocess_image_for_editing(room_image)

            # Generate color description for better AI matching
            color_description = generate_color_description(color_name, color_hex)
            logger.info(f"[WallColor] Color description: {color_description}")

            # Build prompt
            prompt = VisualizationPrompts.get_wall_color_change_prompt(
                color_name=color_name,
                color_hex=color_hex,
                color_description=color_description,
            )

            # Build contents list with PIL Image
            contents = [prompt]

            # Add room image as PIL Image
            room_image_bytes = base64.b64decode(processed_room)
            room_pil_image = Image.open(io.BytesIO(room_image_bytes))
            # Apply EXIF orientation correction
            room_pil_image = ImageOps.exif_transpose(room_pil_image)
            if room_pil_image.mode != "RGB":
                room_pil_image = room_pil_image.convert("RGB")

            input_width, input_height = room_pil_image.size
            logger.info(f"[WallColor] Input image dimensions: {input_width}x{input_height}")

            contents.append(room_pil_image)

            # Generate visualization with Gemini 3 Pro Image
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.3,
            )

            # Retry configuration
            max_retries = 3
            timeout_seconds = 90

            def _run_wall_color_change():
                """Run the streaming generation in a thread for timeout support."""
                result_image = None
                final_chunk = None
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
                    final_chunk = chunk
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                        for part in chunk.candidates[0].content.parts:
                            if part.inline_data and part.inline_data.data:
                                image_data = part.inline_data.data
                                mime_type = part.inline_data.mime_type or "image/png"

                                # Handle both raw bytes and base64 string bytes
                                if isinstance(image_data, bytes):
                                    first_hex = image_data[:4].hex()
                                    logger.info(f"[WallColor] First 4 bytes hex: {first_hex}")

                                    # Check if raw image bytes
                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        image_base64 = base64.b64encode(image_data).decode("utf-8")
                                        logger.info("[WallColor] Raw image bytes detected, encoded to base64")
                                    else:
                                        image_base64 = image_data.decode("utf-8")
                                        logger.info("[WallColor] Base64 string bytes detected")
                                else:
                                    image_base64 = image_data
                                    logger.info("[WallColor] String data received directly")

                                result_image = f"data:{mime_type};base64,{image_base64}"
                                logger.info("[WallColor] Generated wall color visualization")
                return (result_image, final_chunk)

            generated_image = None
            final_chunk = None

            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, _run_wall_color_change), timeout=timeout_seconds
                    )
                    if result:
                        generated_image, final_chunk = result
                    if generated_image:
                        break
                except asyncio.TimeoutError:
                    logger.warning(f"[WallColor] Attempt {attempt + 1} timed out after {timeout_seconds}s")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        logger.info(f"[WallColor] Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    continue
                except Exception as e:
                    error_str = str(e)
                    if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 4 * (2**attempt)
                            logger.warning(f"[WallColor] Model overloaded, retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                    logger.error(f"[WallColor] Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        await asyncio.sleep(wait_time)
                    continue

            if not generated_image:
                logger.error(f"[WallColor] Failed to generate after {max_retries} attempts")
                return None

            # Log operation
            self._log_streaming_operation(
                "change_wall_color",
                "gemini-3-pro-image-preview",
                final_chunk=final_chunk,
                user_id=user_id,
                session_id=session_id,
            )

            logger.info(f"[WallColor] Successfully changed wall color to {color_name}")
            return generated_image

        except Exception as e:
            logger.error(f"[WallColor] Error: {e}", exc_info=True)
            return None

    async def change_wall_texture(
        self,
        room_image: str,
        texture_image: str,
        texture_name: str,
        texture_type: str,
        user_id: str = None,
        session_id: str = None,
    ) -> Optional[str]:
        """
        Change wall texture in a room visualization using Gemini with multi-image input.

        Uses Gemini's native image editing capabilities to apply a texture pattern
        to walls while preserving all furniture and other room elements.

        The key insight is passing BOTH images to Gemini:
        1. The room image (what to modify)
        2. The texture swatch (the pattern reference)

        Args:
            room_image: Base64 encoded room visualization image
            texture_image: Base64 encoded texture swatch image
            texture_name: Name of the texture (e.g., "Basket")
            texture_type: Type of texture finish (e.g., "marble")
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking

        Returns:
            Base64 encoded result image with new wall texture, or None on failure
        """
        try:
            logger.info(f"[WallTexture] Applying texture: {texture_name} ({texture_type})")

            # Use editing preprocessor to preserve quality
            processed_room = self._preprocess_image_for_editing(room_image)
            processed_texture = self._preprocess_image_for_editing(texture_image)

            # Build prompt
            prompt = VisualizationPrompts.get_wall_texture_change_prompt(
                texture_name=texture_name,
                texture_type=texture_type,
            )

            # Build contents list with PIL Images
            contents = [prompt]

            # Add room image as PIL Image (first image)
            room_image_bytes = base64.b64decode(processed_room)
            room_pil_image = Image.open(io.BytesIO(room_image_bytes))
            room_pil_image = ImageOps.exif_transpose(room_pil_image)
            if room_pil_image.mode != "RGB":
                room_pil_image = room_pil_image.convert("RGB")

            input_width, input_height = room_pil_image.size
            logger.info(f"[WallTexture] Room image dimensions: {input_width}x{input_height}")

            contents.append(room_pil_image)

            # Add texture swatch as PIL Image (second image)
            texture_image_bytes = base64.b64decode(processed_texture)
            texture_pil_image = Image.open(io.BytesIO(texture_image_bytes))
            texture_pil_image = ImageOps.exif_transpose(texture_pil_image)
            if texture_pil_image.mode != "RGB":
                texture_pil_image = texture_pil_image.convert("RGB")

            texture_width, texture_height = texture_pil_image.size
            logger.info(f"[WallTexture] Texture swatch dimensions: {texture_width}x{texture_height}")

            contents.append(texture_pil_image)

            # Generate visualization with Gemini 3 Pro Image
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.3,
            )

            # Retry configuration
            max_retries = 3
            timeout_seconds = 90

            def _run_wall_texture_change():
                """Run the streaming generation in a thread for timeout support."""
                result_image = None
                final_chunk = None
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
                    final_chunk = chunk
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                        for part in chunk.candidates[0].content.parts:
                            if part.inline_data and part.inline_data.data:
                                image_data = part.inline_data.data
                                mime_type = part.inline_data.mime_type or "image/png"

                                # Handle both raw bytes and base64 string bytes
                                if isinstance(image_data, bytes):
                                    first_hex = image_data[:4].hex()
                                    logger.info(f"[WallTexture] First 4 bytes hex: {first_hex}")

                                    # Check if raw image bytes
                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        image_base64 = base64.b64encode(image_data).decode("utf-8")
                                        logger.info("[WallTexture] Raw image bytes detected, encoded to base64")
                                    else:
                                        image_base64 = image_data.decode("utf-8")
                                        logger.info("[WallTexture] Base64 string bytes detected")
                                else:
                                    image_base64 = image_data
                                    logger.info("[WallTexture] String data received directly")

                                result_image = f"data:{mime_type};base64,{image_base64}"
                                logger.info("[WallTexture] Generated wall texture visualization")
                return (result_image, final_chunk)

            generated_image = None
            final_chunk = None

            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, _run_wall_texture_change), timeout=timeout_seconds
                    )
                    if result:
                        generated_image, final_chunk = result
                    if generated_image:
                        break
                except asyncio.TimeoutError:
                    logger.warning(f"[WallTexture] Attempt {attempt + 1} timed out after {timeout_seconds}s")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        logger.info(f"[WallTexture] Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    continue
                except Exception as e:
                    error_str = str(e)
                    if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 4 * (2**attempt)
                            logger.warning(f"[WallTexture] Model overloaded, retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                    logger.error(f"[WallTexture] Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        await asyncio.sleep(wait_time)
                    continue

            if not generated_image:
                logger.error(f"[WallTexture] Failed to generate after {max_retries} attempts")
                return None

            # Log operation
            self._log_streaming_operation(
                "change_wall_texture",
                "gemini-3-pro-image-preview",
                final_chunk=final_chunk,
                user_id=user_id,
                session_id=session_id,
            )

            # Resize output to match input dimensions if they differ
            try:
                if generated_image.startswith("data:"):
                    prefix_end = generated_image.index(",") + 1
                    raw_b64 = generated_image[prefix_end:]
                else:
                    raw_b64 = generated_image

                output_bytes = base64.b64decode(raw_b64)
                output_img = Image.open(io.BytesIO(output_bytes))
                output_width, output_height = output_img.size
                logger.info(
                    f"[WallTexture] Output resolution: {output_width}x{output_height}, Input was: {input_width}x{input_height}"
                )

                if output_width != input_width or output_height != input_height:
                    logger.warning(
                        f"[WallTexture] Output resolution mismatch! Resizing from {output_width}x{output_height} to {input_width}x{input_height}"
                    )
                    if output_img.mode != "RGB":
                        output_img = output_img.convert("RGB")
                    output_img = output_img.resize((input_width, input_height), Image.Resampling.LANCZOS)

                    buffer = io.BytesIO()
                    output_img.save(buffer, format="PNG", optimize=False)
                    buffer.seek(0)
                    resized_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    generated_image = f"data:image/png;base64,{resized_b64}"
                    logger.info(f"[WallTexture] Resized output to match input: {input_width}x{input_height}")
            except Exception as resize_err:
                logger.warning(f"[WallTexture] Could not verify/fix output resolution: {resize_err}")

            logger.info(f"[WallTexture] Successfully applied texture {texture_name}")
            return generated_image

        except Exception as e:
            logger.error(f"[WallTexture] Error: {e}", exc_info=True)
            return None

    async def classify_product_style(self, image_url: str, product_name: str, product_description: str = "") -> Dict[str, Any]:
        """
        Classify a product's design style using Gemini Vision API.

        Args:
            image_url: URL of the product image
            product_name: Name of the product
            product_description: Optional product description

        Returns:
            Dict with:
                - primary_style: Main design style (one of 11 predefined)
                - secondary_style: Optional secondary style or None
                - confidence: Confidence score 0.0-1.0
                - reasoning: Brief explanation
        """
        logger.info(f"[GoogleAIStudioService] Classifying style for: {product_name[:50]}...")

        # Download and prepare image
        try:
            image_data = await self._download_image(image_url)
            if not image_data:
                logger.warning(f"Could not download image from {image_url}")
                return self._fallback_style_classification(product_name, product_description)
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return self._fallback_style_classification(product_name, product_description)

        # Truncate description if too long
        desc_truncated = product_description[:500] if product_description else ""

        # Build classification prompt
        prompt = f"""Analyze this furniture/decor product image and classify its design style.

Product: {product_name}
Description: {desc_truncated}

Choose ONLY from these 11 styles:
1. indian_contemporary - Modern Indian design with subtle craft elements, warm tones, traditional motifs reimagined
2. modern - Clean and functional design, neutral colors, everyday modern aesthetic
3. minimalist - Ultra clean design, minimal ornamentation, simple geometric forms
4. japandi - Japanese-Scandinavian fusion with warm minimalism, natural materials
5. scandinavian - Light woods, hygge comfort, airy and bright, cozy textiles
6. mid_century_modern - 1950s-60s inspired with tapered legs, organic curves, bold accents
7. modern_luxury - Premium materials and finishes, hotel-like sophisticated feel
8. contemporary - Current trend-driven design, mixed materials, fresh aesthetic
9. boho - Relaxed bohemian style with layered textures, natural materials, patterns
10. eclectic - Intentional mix of styles, personality-driven, curated collected look
11. industrial - Raw materials like metal and wood, urban warehouse aesthetic

Return ONLY valid JSON in this exact format (no markdown):
{{"primary_style": "one_of_the_11_styles", "secondary_style": "another_style_or_null", "confidence": 0.85, "reasoning": "brief explanation"}}

IMPORTANT:
- primary_style MUST be one of the 11 styles listed above (use exact snake_case)
- secondary_style can be null or one of the 11 styles
- confidence should be 0.0 to 1.0
- Keep reasoning under 100 characters"""

        # Build request payload
        payload = {
            "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": image_data}}]}]
        }

        try:
            # Make API request using Gemini Flash for faster style classification
            response = await self._make_api_request(
                "models/gemini-2.0-flash:generateContent", payload, operation="classify_room_style"
            )

            # Extract and parse JSON response
            if response and "candidates" in response:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if parts and "text" in parts[0]:
                        text_response = parts[0]["text"].strip()

                        # Clean up response (remove markdown code blocks if present)
                        if text_response.startswith("```"):
                            lines = text_response.split("\n")
                            text_response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

                        try:
                            result = json.loads(text_response)

                            # Validate result
                            valid_styles = [
                                "indian_contemporary",
                                "modern",
                                "minimalist",
                                "japandi",
                                "scandinavian",
                                "mid_century_modern",
                                "modern_luxury",
                                "contemporary",
                                "boho",
                                "eclectic",
                                "industrial",
                            ]

                            primary = result.get("primary_style", "").lower().replace(" ", "_")
                            if primary not in valid_styles:
                                logger.warning(f"Invalid primary style: {primary}, defaulting to 'modern'")
                                primary = "modern"

                            secondary = result.get("secondary_style")
                            if secondary:
                                secondary = secondary.lower().replace(" ", "_")
                                if secondary not in valid_styles:
                                    secondary = None

                            return {
                                "primary_style": primary,
                                "secondary_style": secondary,
                                "confidence": min(1.0, max(0.0, float(result.get("confidence", 0.7)))),
                                "reasoning": result.get("reasoning", "Style classified by AI vision")[:200],
                            }

                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse style classification JSON: {e}")
                            logger.debug(f"Raw response: {text_response}")

            logger.warning("[GoogleAIStudioService] No valid response from Gemini for style classification")
            return self._fallback_style_classification(product_name, product_description)

        except Exception as e:
            logger.error(f"[GoogleAIStudioService] Error classifying product style: {str(e)}")
            return self._fallback_style_classification(product_name, product_description)

    def _fallback_style_classification(self, product_name: str, product_description: str = "") -> Dict[str, Any]:
        """
        Fallback style classification using text-based keyword matching.
        Used when image-based classification fails.
        """
        text = f"{product_name} {product_description}".lower()

        # Keyword-based style detection
        style_keywords = {
            "indian_contemporary": ["indian", "ethnic", "traditional indian", "brass", "carved", "jharokha", "mughal"],
            "minimalist": ["minimalist", "minimal", "simple", "clean lines", "understated"],
            "japandi": ["japandi", "japanese", "zen", "wabi-sabi", "tatami"],
            "scandinavian": ["scandinavian", "scandi", "nordic", "hygge", "danish", "swedish"],
            "mid_century_modern": ["mid-century", "midcentury", "retro", "vintage", "60s", "70s", "tapered legs"],
            "modern_luxury": ["luxury", "luxurious", "premium", "opulent", "elegant", "glam", "velvet"],
            "contemporary": ["contemporary", "current", "trendy"],
            "boho": ["boho", "bohemian", "macrame", "rattan", "wicker", "jute", "tribal"],
            "eclectic": ["eclectic", "mix", "mixed", "collected", "unique"],
            "industrial": ["industrial", "metal", "iron", "pipe", "loft", "warehouse", "raw"],
            "modern": ["modern", "sleek", "streamlined", "functional"],
        }

        detected_style = "modern"  # Default
        max_matches = 0

        for style, keywords in style_keywords.items():
            matches = sum(1 for kw in keywords if kw in text)
            if matches > max_matches:
                max_matches = matches
                detected_style = style

        return {
            "primary_style": detected_style,
            "secondary_style": None,
            "confidence": 0.4 if max_matches > 0 else 0.2,
            "reasoning": "Classified by text analysis (image unavailable)",
        }

    async def extract_furniture_layers(self, visualization_image: str, products: list[dict]) -> dict:
        """
        Extract furniture from visualization as separate layers for edit mode.

        Uses Gemini Vision to:
        1. Detect bounding boxes for each product in the visualization
        2. Extract each furniture piece as a layer (cropped from original)
        3. Generate clean background using existing furniture removal

        Args:
            visualization_image: Base64 encoded visualization image
            products: List of products with id and name

        Returns:
            {
                "clean_background": "data:image/...;base64,...",
                "layers": [
                    {
                        "product_id": "123",
                        "product_name": "Brass Sculpture",
                        "layer_image": "data:image/...;base64,...",
                        "bounding_box": {"x": 0.45, "y": 0.55, "width": 0.08, "height": 0.12},
                        "center": {"x": 0.49, "y": 0.61}
                    }
                ]
            }
        """
        logger.info(f"[extract_furniture_layers] Starting extraction for {len(products)} products")

        try:
            # Step 1: Detect bounding boxes for all products
            detected_positions = await self._detect_product_positions(visualization_image, products)
            logger.info(f"[extract_furniture_layers] Detected {len(detected_positions)} positions")

            # Step 2: Generate clean background (run in parallel with layer extraction)
            # Reuse existing remove_furniture method
            clean_background_task = asyncio.create_task(self.remove_furniture(visualization_image))

            # Step 3: Extract layer images for each detected position
            layers = []
            for position in detected_positions:
                try:
                    layer_image = await self._extract_single_layer(
                        visualization_image, position["bounding_box"], position["product_name"]
                    )
                    layers.append(
                        {
                            "product_id": str(position["product_id"]),
                            "product_name": position["product_name"],
                            "layer_image": layer_image,
                            "bounding_box": position["bounding_box"],
                            "center": {
                                "x": position["bounding_box"]["x"] + position["bounding_box"]["width"] / 2,
                                "y": position["bounding_box"]["y"] + position["bounding_box"]["height"] / 2,
                            },
                        }
                    )
                except Exception as e:
                    logger.warning(f"[extract_furniture_layers] Failed to extract layer for {position['product_name']}: {e}")
                    # Still include the position without a layer image
                    layers.append(
                        {
                            "product_id": str(position["product_id"]),
                            "product_name": position["product_name"],
                            "layer_image": None,
                            "bounding_box": position["bounding_box"],
                            "center": {
                                "x": position["bounding_box"]["x"] + position["bounding_box"]["width"] / 2,
                                "y": position["bounding_box"]["y"] + position["bounding_box"]["height"] / 2,
                            },
                        }
                    )

            # Wait for clean background
            clean_background = await clean_background_task

            return {"clean_background": clean_background, "layers": layers}

        except Exception as e:
            logger.error(f"[extract_furniture_layers] Error: {e}", exc_info=True)
            raise

    async def _detect_product_positions(self, visualization_image: str, products: list[dict]) -> list[dict]:
        """
        Detect bounding boxes for furniture in the visualization image.
        Simply detects all furniture and assigns to products in order.

        Returns list of:
        {
            "product_id": "123",
            "product_name": "Sofa",
            "bounding_box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
        }
        """
        logger.info(f"[_detect_product_positions] Starting detection for {len(products)} products")
        processed_image = self._preprocess_image(visualization_image)

        num_products = len(products)
        prompt = f"""Detect exactly {num_products} main furniture/decor items in this room visualization.

I need to find the positions of {num_products} items. Look for the most prominent furniture pieces.

For EACH item, provide its bounding box as percentages (0-1) where:
- x = left edge position (0 = left side of image, 1 = right side)
- y = top edge position (0 = top of image, 1 = bottom)
- width = width as fraction of image width
- height = height as fraction of image height

Return a JSON array with exactly {num_products} items:
[
  {{"item_type": "sofa", "bounding_box": {{"x": 0.1, "y": 0.4, "width": 0.4, "height": 0.25}}}},
  {{"item_type": "coffee_table", "bounding_box": {{"x": 0.3, "y": 0.6, "width": 0.2, "height": 0.1}}}}
]

RULES:
- Return EXACTLY {num_products} items
- Be accurate with bounding boxes - they should tightly fit each item
- item_type is just a description, doesn't need to match exactly
- Return ONLY valid JSON array, no other text"""

        payload = {
            "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": processed_image}}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096, "responseMimeType": "application/json"},
        }

        try:
            logger.info("[_detect_product_positions] Calling Gemini API...")
            result = await self._make_api_request(
                "models/gemini-2.0-flash-exp:generateContent", payload, operation="detect_product_positions"
            )
            logger.info(f"[_detect_product_positions] Got API response")

            content = result.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "[]")
            logger.info(f"[_detect_product_positions] Response text: {text_response[:500]}")

            detected_items = json.loads(text_response)
            if not isinstance(detected_items, list):
                detected_items = []
            logger.info(f"[_detect_product_positions] Parsed {len(detected_items)} items")

        except json.JSONDecodeError as e:
            logger.error(f"[_detect_product_positions] JSON parse error: {e}")
            return []
        except Exception as e:
            logger.error(f"[_detect_product_positions] API error: {e}")
            return []

        # Simple mapping: assign detected items to products in order
        positions = []
        for i, product in enumerate(products):
            if i < len(detected_items):
                detected = detected_items[i]
                bbox = detected.get("bounding_box", {})
                # Validate bounding box
                if all(k in bbox for k in ["x", "y", "width", "height"]):
                    positions.append({"product_id": product["id"], "product_name": product["name"], "bounding_box": bbox})
                    logger.info(f"[_detect_product_positions] Product '{product['name']}' -> bbox {bbox}")
                else:
                    logger.warning(f"[_detect_product_positions] Invalid bbox for item {i}: {bbox}")

        logger.info(f"[_detect_product_positions] Final: {len(positions)} positions")
        return positions

    async def _extract_single_layer(self, visualization_image: str, bounding_box: dict, product_name: str) -> str:
        """
        Extract a single furniture item as a cropped layer image.

        Args:
            visualization_image: Full visualization image (base64)
            bounding_box: {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
            product_name: Name of the product for context

        Returns:
            Base64 encoded cropped image with data URL prefix
        """
        # Decode the visualization image
        image_data = visualization_image
        if image_data.startswith("data:image"):
            image_data = image_data.split(",")[1]

        image_bytes = base64.b64decode(image_data)
        pil_image = Image.open(io.BytesIO(image_bytes))

        # Apply EXIF correction
        pil_image = ImageOps.exif_transpose(pil_image)

        # Convert to RGB if needed
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        width, height = pil_image.size

        # Calculate pixel coordinates from percentages
        x = int(bounding_box["x"] * width)
        y = int(bounding_box["y"] * height)
        box_width = int(bounding_box["width"] * width)
        box_height = int(bounding_box["height"] * height)

        # Add small padding (5%) to include some context
        padding_x = int(box_width * 0.05)
        padding_y = int(box_height * 0.05)

        # Ensure we don't go outside image bounds
        left = max(0, x - padding_x)
        top = max(0, y - padding_y)
        right = min(width, x + box_width + padding_x)
        bottom = min(height, y + box_height + padding_y)

        # Crop the image
        cropped = pil_image.crop((left, top, right, bottom))

        # Convert to base64
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        cropped_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        logger.info(f"[_extract_single_layer] Extracted layer for {product_name}: {cropped.width}x{cropped.height}px")

        return f"data:image/png;base64,{cropped_base64}"

    async def change_floor_tile(
        self,
        room_image: str,
        swatch_image: str,
        tile_name: str,
        tile_size: str,
        tile_finish: str,
        tile_width_mm: int = None,
        tile_height_mm: int = None,
        user_id: str = None,
        session_id: str = None,
    ) -> Optional[str]:
        """
        Change floor tile in a room visualization using Gemini with multi-image input.

        Uses the same pattern as change_wall_texture: passes both the room image
        and tile swatch to Gemini so it can apply the tile pattern to the floor.

        Args:
            room_image: Base64 encoded room visualization image
            swatch_image: Base64 encoded tile swatch image
            tile_name: Name of the tile (e.g., "Carrara Marble")
            tile_size: Tile dimensions (e.g., "1200x1800 mm")
            tile_finish: Finish type (e.g., "Glossy")
            tile_width_mm: Tile width in millimeters (e.g., 1200)
            tile_height_mm: Tile height in millimeters (e.g., 1800)
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking

        Returns:
            Base64 encoded result image with new floor tile, or None on failure
        """
        try:
            logger.info(f"[FloorTile] Applying tile: {tile_name} ({tile_size}, {tile_finish})")

            # Use editing preprocessor to preserve quality
            processed_room = self._preprocess_image_for_editing(room_image)
            processed_swatch = self._preprocess_image_for_editing(swatch_image)

            # Build prompt
            prompt = VisualizationPrompts.get_floor_tile_change_prompt(
                tile_name=tile_name,
                tile_size=tile_size,
                tile_finish=tile_finish,
                tile_width_mm=tile_width_mm,
                tile_height_mm=tile_height_mm,
            )

            # Build contents list with PIL Images
            contents = [prompt]

            # Add room image as PIL Image (first image)
            room_image_bytes = base64.b64decode(processed_room)
            room_pil_image = Image.open(io.BytesIO(room_image_bytes))
            room_pil_image = ImageOps.exif_transpose(room_pil_image)
            if room_pil_image.mode != "RGB":
                room_pil_image = room_pil_image.convert("RGB")

            input_width, input_height = room_pil_image.size
            logger.info(f"[FloorTile] Room image dimensions: {input_width}x{input_height}")

            contents.append(room_pil_image)

            # Add tile swatch as PIL Image (second image)
            swatch_image_bytes = base64.b64decode(processed_swatch)
            swatch_pil_image = Image.open(io.BytesIO(swatch_image_bytes))
            swatch_pil_image = ImageOps.exif_transpose(swatch_pil_image)
            if swatch_pil_image.mode != "RGB":
                swatch_pil_image = swatch_pil_image.convert("RGB")

            swatch_width, swatch_height = swatch_pil_image.size
            logger.info(f"[FloorTile] Swatch dimensions: {swatch_width}x{swatch_height}")

            contents.append(swatch_pil_image)

            # Generate visualization with Gemini 3 Pro Image
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.3,
            )

            # Retry configuration
            max_retries = 3
            timeout_seconds = 90

            def _run_floor_tile_change():
                """Run the streaming generation in a thread for timeout support."""
                result_image = None
                final_chunk = None
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
                    final_chunk = chunk
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                        for part in chunk.candidates[0].content.parts:
                            if part.inline_data and part.inline_data.data:
                                image_data = part.inline_data.data
                                mime_type = part.inline_data.mime_type or "image/png"

                                # Handle both raw bytes and base64 string bytes
                                if isinstance(image_data, bytes):
                                    first_hex = image_data[:4].hex()
                                    logger.info(f"[FloorTile] First 4 bytes hex: {first_hex}")

                                    if first_hex.startswith("89504e47") or first_hex.startswith("ffd8ff"):
                                        image_base64 = base64.b64encode(image_data).decode("utf-8")
                                        logger.info("[FloorTile] Raw image bytes detected, encoded to base64")
                                    else:
                                        image_base64 = image_data.decode("utf-8")
                                        logger.info("[FloorTile] Base64 string bytes detected")
                                else:
                                    image_base64 = image_data
                                    logger.info("[FloorTile] String data received directly")

                                result_image = f"data:{mime_type};base64,{image_base64}"
                                logger.info("[FloorTile] Generated floor tile visualization")
                return (result_image, final_chunk)

            generated_image = None
            final_chunk = None

            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, _run_floor_tile_change), timeout=timeout_seconds
                    )
                    if result:
                        generated_image, final_chunk = result
                    if generated_image:
                        break
                except asyncio.TimeoutError:
                    logger.warning(f"[FloorTile] Attempt {attempt + 1} timed out after {timeout_seconds}s")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        logger.info(f"[FloorTile] Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    continue
                except Exception as e:
                    error_str = str(e)
                    if "503" in error_str or "overloaded" in error_str.lower() or "UNAVAILABLE" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 4 * (2**attempt)
                            logger.warning(f"[FloorTile] Model overloaded, retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                    logger.error(f"[FloorTile] Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        await asyncio.sleep(wait_time)
                    continue

            if not generated_image:
                logger.error(f"[FloorTile] Failed to generate after {max_retries} attempts")
                return None

            # Log operation
            self._log_streaming_operation(
                "change_floor_tile",
                "gemini-3-pro-image-preview",
                final_chunk=final_chunk,
                user_id=user_id,
                session_id=session_id,
            )

            # Resize output to match input dimensions if they differ
            try:
                # Strip data URI prefix to get raw base64
                if generated_image.startswith("data:"):
                    prefix_end = generated_image.index(",") + 1
                    raw_b64 = generated_image[prefix_end:]
                else:
                    raw_b64 = generated_image

                output_bytes = base64.b64decode(raw_b64)
                output_img = Image.open(io.BytesIO(output_bytes))
                output_width, output_height = output_img.size
                logger.info(
                    f"[FloorTile] Output resolution: {output_width}x{output_height}, Input was: {input_width}x{input_height}"
                )

                if output_width != input_width or output_height != input_height:
                    logger.warning(
                        f"[FloorTile] Output resolution mismatch! Resizing from {output_width}x{output_height} to {input_width}x{input_height}"
                    )
                    if output_img.mode != "RGB":
                        output_img = output_img.convert("RGB")
                    output_img = output_img.resize((input_width, input_height), Image.Resampling.LANCZOS)

                    buffer = io.BytesIO()
                    output_img.save(buffer, format="PNG", optimize=False)
                    buffer.seek(0)
                    resized_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    generated_image = f"data:image/png;base64,{resized_b64}"
                    logger.info(f"[FloorTile] Resized output to match input: {input_width}x{input_height}")
            except Exception as resize_err:
                logger.warning(f"[FloorTile] Could not verify/fix output resolution: {resize_err}")

            logger.info(f"[FloorTile] Successfully applied tile {tile_name}")
            return generated_image

        except Exception as e:
            logger.error(f"[FloorTile] Error: {e}", exc_info=True)
            return None

    async def apply_room_surfaces(
        self,
        room_image: str,
        wall_color: Optional[dict] = None,
        texture_image: str = None,
        texture_name: str = None,
        texture_type: str = None,
        tile_swatch_image: str = None,
        tile_name: str = None,
        tile_size: str = None,
        tile_finish: str = None,
        tile_width_mm: int = None,
        tile_height_mm: int = None,
        user_id: str = None,
        session_id: str = None,
    ) -> Optional[str]:
        """
        Apply surface changes (wall color/texture + floor tile) to a room in a single Gemini call.
        This is the surface-only path — no furniture products.

        Args:
            room_image: Base64 encoded room image
            wall_color: Optional dict with 'name', 'code', 'hex_value' for wall color
            texture_image: Base64 swatch image for wall texture
            texture_name: Name of the texture
            texture_type: Type of texture
            tile_swatch_image: Base64 swatch image for floor tile
            tile_name: Name of the floor tile
            tile_size: Size description
            tile_finish: Finish type
            tile_width_mm: Tile width in mm
            tile_height_mm: Tile height in mm
            user_id: Optional user ID for tracking
            session_id: Optional session ID for tracking

        Returns: base64 image data with data URI prefix, or None on failure
        """
        logger.info(
            f"[ApplySurfaces] Combined surface call: wall_color={wall_color.get('name') if wall_color else None}, "
            f"texture={texture_name}, tile={tile_name}"
        )
        try:
            result = await self.generate_add_multiple_visualization(
                room_image=room_image,
                products=[],
                existing_products=[],
                user_id=user_id,
                session_id=session_id,
                wall_color=wall_color,
                texture_image=texture_image,
                texture_name=texture_name,
                texture_type=texture_type,
                tile_swatch_image=tile_swatch_image,
                tile_name=tile_name,
                tile_size=tile_size,
                tile_finish=tile_finish,
                tile_width_mm=tile_width_mm,
                tile_height_mm=tile_height_mm,
            )
            return result
        except Exception as e:
            logger.error(f"[ApplySurfaces] Error: {e}", exc_info=True)
            return None

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None


# Global service instance
google_ai_service = GoogleAIStudioService()
