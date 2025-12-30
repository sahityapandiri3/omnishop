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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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

    async def _make_api_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated API request to Google AI Studio"""
        await self.rate_limiter.acquire()

        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}

        start_time = time.time()
        self.usage_stats["total_requests"] += 1

        try:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    self.usage_stats["successful_requests"] += 1
                    processing_time = time.time() - start_time
                    self.usage_stats["total_processing_time"] += processing_time

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

    async def analyze_room_image(self, image_data: str) -> RoomAnalysis:
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

🚨 CRITICAL - VIEWING ANGLE DETECTION (camera_view_analysis.viewing_angle):

Look at how many walls you can see and their angles:
- "corner" = You can see TWO walls meeting at a corner. Both walls are visible at angles. THIS IMAGE IS LIKELY A CORNER VIEW.
- "diagonal_left" = Camera points toward the left-back corner. The RIGHT wall is prominently visible.
- "diagonal_right" = Camera points toward the right-back corner. The LEFT wall is prominently visible.
- "straight_on" = RARE. Only if: the back wall is perfectly parallel to the image edge AND you can barely see any side walls.

⚠️ If you can clearly see TWO walls (like a window wall AND a solid wall meeting at a corner), it's "corner" NOT "straight_on".

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

            result = await self._make_api_request("models/gemini-3-pro-preview:generateContent", payload)

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
                    # Use a fallback DICT (not RoomAnalysis) since we call .get() on it below
                    logger.warning("Both JSON parsing attempts failed, using fallback")
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
                            "viewing_angle": "straight_on",
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

            result = await self._make_api_request("models/gemini-3-pro-preview:generateContent", payload)

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

    async def detect_objects_in_room(self, image_data: str) -> List[Dict[str, Any]]:
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

            result = await self._make_api_request("models/gemini-3-pro-preview:generateContent", payload)

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

            result = await self._make_api_request("models/gemini-3-pro-preview:generateContent", payload)

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

            result = await self._make_api_request("models/gemini-3-pro-preview:generateContent", payload)

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
            prompt = f"""🔍 SPACE FITNESS ANALYSIS TASK 🔍

Analyze whether the following product can realistically fit in the available space shown in the room image.

PRODUCT TO ANALYZE: {product_name}

═══════════════════════════════════════════════════════════════
⚠️ CRITICAL: PRODUCT DIMENSIONS (FROM DESCRIPTION) ⚠️
═══════════════════════════════════════════════════════════════
{f"PRODUCT DESCRIPTION: {product_description}" if product_description else "No description available - estimate from product image"}

🚨 IMPORTANT: Extract the ACTUAL dimensions from the product description above.
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
            for chunk in self.genai_client.models.generate_content_stream(
                model="gemini-3-pro-preview",  # Use Gemini 3 for analysis
                contents=contents,
                config=generate_content_config,
            ):
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.text:
                            response_text += part.text

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

    async def remove_furniture(self, image_base64: str, max_retries: int = 5) -> Optional[str]:
        """
        Remove all furniture from room image using Gemini 2.5 Flash Image model.
        Uses the simplified API pattern from Google docs with PIL Image.
        Returns: base64 encoded image with furniture removed, or None on failure
        """
        try:
            # Convert base64 to PIL Image for the new API style
            # Log input for debugging Railway issues
            original_length = len(image_base64)
            logger.info(f"Received image base64 string: {original_length} characters")

            # Remove data URL prefix if present
            if image_base64.startswith("data:image"):
                image_base64 = image_base64.split(",")[1]
                logger.info(f"After stripping data URL prefix: {len(image_base64)} characters")

            # Log preview to detect truncation
            if len(image_base64) > 100:
                logger.info(f"Base64 preview: {image_base64[:50]}...{image_base64[-50:]}")

            image_bytes = base64.b64decode(image_base64)
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

            logger.info(f"Loaded image for furniture removal (EXIF corrected): {pil_image.width}x{pil_image.height} pixels")

            prompt = """🚨 CRITICAL TASK: Remove ALL furniture and movable objects from this room image AND correct the perspective.

The output MUST be:
1. A COMPLETELY EMPTY room with ZERO furniture remaining
2. PERSPECTIVE CORRECTED like a professional architectural photo

📐 PERSPECTIVE CORRECTION (MANDATORY):
- Straighten ALL vertical lines (walls, door frames, window frames should be perfectly vertical)
- Level ALL horizontal lines (floor line, ceiling line, window sills should be horizontal)
- Correct any lens distortion or tilted camera angle
- The output should look like a professional real estate photo with proper architectural perspective
- Walls should not lean inward or outward - they should be straight and vertical

⚠️ MANDATORY REMOVALS - These items MUST be deleted from the image:
1. ALL SEATING: Sofas (including curved/sectional sofas), couches, chairs, armchairs, ottomans
2. ALL TABLES: Coffee tables, side tables, dining tables, console tables
3. ALL BEDS: Beds, mattresses, headboards
4. ALL LAMPS: Floor lamps, tripod lamps, standing lamps, table lamps, any lamp with a base on the floor
5. ALL MIRRORS: Standing mirrors, floor mirrors, full-length mirrors, leaning mirrors against walls
6. ALL PLANTS: Potted plants, planters, indoor trees
7. ALL DECOR: Vases, sculptures, frames, artwork, cushions, throws on furniture
8. 🚨 ALL FLOOR COVERINGS: Carpets, rugs, area rugs, floor mats, dhurries, runners - the BARE FLOOR must be visible

🔴 IMPORTANT: If you see ANY of these in the image, they MUST be removed:
- A curved or L-shaped sofa → REMOVE IT
- A lamp with wooden tripod legs → REMOVE IT
- A tall standing mirror leaning against wall → REMOVE IT
- Any potted plant → REMOVE IT
- ANY carpet or rug on the floor → REMOVE IT (show bare floor)
- ANY floor covering of any color/pattern → REMOVE IT

✅ KEEP ONLY (do not modify these):
- Walls, ceiling, floor (the BARE room floor - no carpets/rugs)
- Windows, doors, built-in closets
- Curtains/drapes on windows
- AC units mounted on walls
- Electrical outlets and switches
- Archways and architectural features

OUTPUT: Generate an image of the SAME room but:
1. COMPLETELY EMPTY - no furniture, no lamps, no mirrors, no plants, NO CARPETS OR RUGS
2. PERSPECTIVE CORRECTED - vertical lines straight, horizontal lines level, like a professional architectural photo

FAILURE IS NOT ACCEPTABLE: Every single piece of furniture AND floor covering MUST be removed, AND the perspective MUST be corrected. Do not leave any sofa, lamp, mirror, or carpet in the output."""

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
                        return generated_image

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

    async def generate_add_visualization(
        self, room_image: str, product_name: str, product_image: Optional[str] = None, product_color: Optional[str] = None
    ) -> str:
        """
        Generate visualization with product ADDED to room
        Returns: base64 image data

        Args:
            room_image: Base64 encoded room image
            product_name: Name of the product (may include color prefix)
            product_image: URL of product reference image
            product_color: Explicit color from product attributes (e.g., "beige", "cream", "walnut")
        """
        try:
            processed_room = self._preprocess_image(room_image)

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
🚨🚨🚨 CRITICAL INSTRUCTION - READ THIS FIRST 🚨🚨🚨
═══════════════════════════════════════════════════════════════
⛔ DO NOT ZOOM IN - THIS IS THE #1 PRIORITY ⛔
⛔ DO NOT CHANGE THE CAMERA ANGLE OR PERSPECTIVE ⛔
⛔ THE OUTPUT MUST SHOW THE EXACT SAME VIEW AS THE INPUT ⛔

The output image MUST be a WIDE SHOT showing the ENTIRE ROOM.
The camera position, angle, and field of view MUST BE IDENTICAL to the input.
If the input shows the full room, the output MUST show the full room.
Adding a small item does NOT mean zooming in on it.
The item you add should be a SMALL part of the overall image.

⛔ IF YOU ZOOM IN OR CROP THE IMAGE, YOU HAVE FAILED ⛔
═══════════════════════════════════════════════════════════════

🚫🚫🚫 CRITICAL: DO NOT ADD EXTRA FURNITURE 🚫🚫🚫
═══════════════════════════════════════════════════════════════
⛔ ADD ONLY THE ONE SPECIFIC PRODUCT LISTED BELOW ⛔
⛔ DO NOT add sofas, chairs, tables, or any other furniture ⛔
⛔ DO NOT "complete" or "design" the room ⛔
⛔ DO NOT add items you think would look nice ⛔
⛔ DO NOT add matching or complementary pieces ⛔

YOUR ONLY TASK: Add the ONE product specified below.
The room is ALREADY COMPLETE - it does NOT need more furniture.
If I ask for 1 lamp, add ONLY 1 lamp - nothing else.

⛔ ADDING ANY EXTRA FURNITURE = AUTOMATIC FAILURE ⛔
═══════════════════════════════════════════════════════════════

"""

            # Extra warning for small items like planters
            small_item_warning = ""
            if is_small_item:
                small_item_warning = f"""
🚨🚨🚨 SPECIAL WARNING FOR {product_name.upper()} 🚨🚨🚨
═══════════════════════════════════════════════════════════════
This is an ACCENT ITEM. Critical rules:
- KEEP THE EXACT SAME CAMERA ANGLE as the input image
- KEEP THE EXACT SAME ASPECT RATIO as the input image
- DO NOT ZOOM IN regardless of the item's size
- Place naturally in the room at its appropriate real-world size
- The room view must remain UNCHANGED - only ADD the item

⛔ ZOOMING IN = AUTOMATIC FAILURE ⛔
⛔ CHANGING CAMERA ANGLE = AUTOMATIC FAILURE ⛔
⛔ THE FULL ROOM MUST BE VISIBLE IN THE OUTPUT ⛔
═══════════════════════════════════════════════════════════════

"""

            # Build prompt with zoom warnings (planters and other small items all use the same structure)
            # Planter-specific placement hints are added below
            planter_placement_hint = ""
            if is_planter:
                planter_placement_hint = """
🌿 PLANTER PLACEMENT GUIDE:
- Place on the floor in an appropriate corner or beside existing furniture
- The planter should be filled with appropriate green foliage
- Add realistic shadows cast by the planter onto the floor
- Planter should be a SMALL accent piece - NOT the focus of the image

"""

            # Build explicit color instruction if color is known
            color_emphasis = ""
            if product_color:
                color_emphasis = f"""
🎨🎨🎨 CRITICAL COLOR REQUIREMENT 🎨🎨🎨
═══════════════════════════════════════════════════════════════
THE PRODUCT COLOR IS: **{product_color.upper()}**
- YOU MUST render this product in {product_color.upper()} color
- DO NOT change the color to grey, white, or any other color
- DO NOT "adapt" the color to match the room
- The exact shade/tone from the reference image MUST be preserved
- If the reference shows {product_color}, output MUST show {product_color}
═══════════════════════════════════════════════════════════════

"""

            prompt = f"""{zoom_warning}{small_item_warning}{planter_placement_hint}{color_emphasis}ADD the following product to this room in an appropriate location WITHOUT removing any existing furniture:

Product to add: {product_name} (COLOR: {product_color if product_color else 'see reference image'})

🚨🚨🚨 ABSOLUTE REQUIREMENT - ROOM DIMENSIONS 🚨🚨🚨
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

⚠️ IF THE OUTPUT IMAGE HAS DIFFERENT DIMENSIONS THAN THE INPUT, YOU HAVE FAILED THE TASK ⚠️
═══════════════════════════════════════════════════════════════

🚨🚨🚨 ABSOLUTE REQUIREMENT - EXISTING FURNITURE SIZE PRESERVATION 🚨🚨🚨
═══════════════════════════════════════════════════════════════
ALL EXISTING FURNITURE MUST REMAIN THE EXACT SAME SIZE AND SCALE:
- ⚠️ NEVER make existing furniture (sofas, chairs, tables) appear larger or smaller
- ⚠️ NEVER expand the room to accommodate new items
- ⚠️ NEVER shrink existing furniture to make space for new items
- ⚠️ NEVER change the perspective to make the room appear larger
- ⚠️ The sofa that was 6 feet wide MUST still appear 6 feet wide
- ⚠️ The coffee table that was 4 feet long MUST still appear 4 feet long
- ⚠️ All proportions between existing objects MUST remain IDENTICAL

📏 TRUE SIZE REPRESENTATION:
- New furniture must be added at its REAL-WORLD proportional size
- A new 3-seater sofa should look proportional to an existing 3-seater sofa
- A new side table should look smaller than an existing dining table
- Use the existing furniture as SIZE REFERENCE for new items
- Do NOT artificially shrink new products to fit - if they don't fit, they don't fit

🚫 ROOM EXPANSION IS FORBIDDEN:
- The room boundaries (walls, floor, ceiling) are FIXED
- Do NOT push walls back to create more space
- Do NOT make the ceiling appear higher
- Do NOT extend the floor area
- The room's cubic volume must remain IDENTICAL
- If there's not enough space for the product, do NOT modify the room

⚠️ IF EXISTING FURNITURE CHANGES SIZE OR ROOM EXPANDS, YOU HAVE FAILED THE TASK ⚠️
═══════════════════════════════════════════════════════════════

🔒 CRITICAL PRESERVATION RULES:
1. KEEP ALL EXISTING FURNITURE: Do NOT remove or replace any furniture currently in the room
2. ⚠️ ESPECIALLY PRESERVE SOFAS: If there is a sofa/couch in the room, it MUST remain in the final image - NEVER remove a sofa unless explicitly told to replace it
3. FIND APPROPRIATE SPACE: Identify a suitable empty space to place the new furniture
4. PRESERVE THE ROOM: Keep the same walls, windows, floors, ceiling, lighting, and camera angle
5. NATURAL PLACEMENT: Place the product naturally where it would logically fit in this room layout
6. ROOM SIZE UNCHANGED: The room must look the EXACT same size - not bigger, not smaller

🖼️ WALL ART / PAINTINGS RULE:
- If adding wall art and room ALREADY has paintings → Place new art on a DIFFERENT wall or different position
- DO NOT replace existing paintings - ADD alongside them (gallery-style)
- Existing artwork must REMAIN VISIBLE

🚫 FURNITURE YOU MUST NEVER REMOVE:
- Sofas/couches (main seating)
- Beds
- Existing accent chairs
- Existing wall art/paintings
- Any furniture that was in the input image

✅ YOUR TASK:
- Add the {product_name} to this room
- Place it in an appropriate empty location
- Do NOT remove or replace any existing furniture
- Keep the room structure 100% identical
- Keep the room DIMENSIONS 100% identical
- Ensure the product looks naturally integrated with proper lighting and shadows

🔴🔴🔴 EXACT PRODUCT REPLICATION - MANDATORY 🔴🔴🔴
═══════════════════════════════════════════════════════════════
If a product reference image is provided, you MUST render the EXACT SAME product:

1. 🎨 EXACT COLOR - The color in output MUST match the reference image precisely
   - If reference shows light gray, render LIGHT GRAY (not dark gray, not beige)
   - If reference shows walnut wood, render WALNUT WOOD (not oak, not black)

2. 🪵 EXACT MATERIAL & TEXTURE - Replicate the exact material appearance
   - Velvet → Velvet, Leather → Leather, Wood grain → Same wood grain

3. 📐 EXACT SHAPE & DESIGN - Match the reference's silhouette and design
   - Same arm style, same leg style, same proportions

4. 🏷️ EXACT STYLE - Keep the same style character
   - Modern → Modern, Traditional → Traditional, Mid-century → Mid-century

⚠️ CRITICAL: The product in the output MUST look like the SAME EXACT product from the reference image.
❌ DO NOT generate a "similar" or "inspired by" version
❌ DO NOT change colors to "match the room better"
✅ COPY the EXACT appearance from the product reference image
═══════════════════════════════════════════════════════════════

PLACEMENT GUIDELINES:

🪑 SOFAS:
- Place DIRECTLY AGAINST the wall with MINIMAL GAP (2-4 inches max)
- ⚠️ DO NOT leave large empty space between sofa back and wall
- The sofa's back should be nearly touching the wall
- Position as the main seating piece, centered on the wall or in the room
- Real sofas sit flush against walls - replicate this realistic placement

🪑 CHAIRS (accent chair, side chair, armchair, sofa chair, dining chair, recliner):
- Position on ONE OF THE SIDES of the existing sofa (if sofa exists)
- Angle the chair towards the sofa to create a conversation area
- Maintain 18-30 inches spacing from the sofa
- Style and orient the chair based on the sofa's position and facing direction
- If no sofa exists, place along a wall or in a natural seating position

🔲 CENTER TABLE / COFFEE TABLE:
- Place DIRECTLY IN FRONT OF the sofa or seating area
- Centered between the sofa and the opposite wall/furniture
- Positioned in the "coffee table zone" (perpendicular to sofa's front face)

🔲 OTTOMAN:
- Place DIRECTLY IN FRONT OF the sofa, similar to a coffee table
- Can be centered or slightly offset based on room layout
- Should be 14-18 inches from sofa's front edge
- Ottomans are used as footrests or extra seating, NOT as sofa replacements
- ⚠️ NEVER remove or replace the sofa when adding an ottoman

🔲 SIDE TABLE / END TABLE:
- ⚠️ CRITICAL: Place DIRECTLY ADJACENT to the sofa's SIDE (at the armrest)
- ⚠️ The table must be FLUSH with the sofa's side, not in front or behind
- Position at the SAME DEPTH as the sofa (aligned with sofa's length, not width)
- Should be at ARM'S REACH from someone sitting on the sofa
- Think: "side by side" positioning, not "in front and to the side"
- ❌ INCORRECT: Placing table in front of the sofa but shifted to the side
- ✅ CORRECT: Placing table directly touching or very close to sofa's side panel/armrest

🔲 CONSOLE TABLE / ENTRYWAY TABLE / FOYER TABLE:
- ⚠️ ABSOLUTE RULE: Console tables are COMPLETELY DIFFERENT from sofas - NEVER remove a sofa when adding a console
- Console tables are NARROW, LONG tables that go AGAINST A WALL (not in front of seating)
- Place against an empty wall space, NOT in the seating area
- Typical placement: behind a sofa (against wall), in entryways, hallways, or against any bare wall
- Console tables are ACCENT furniture - they do NOT replace ANY seating furniture
- ⚠️ CRITICAL: If there is a sofa in the room, it MUST remain - console tables are ADDITIONAL furniture
- Console tables are typically 28-32 inches tall and very narrow (12-18 inches deep)

💡 LAMPS:
- Place on an existing table or directly on the floor (for floor lamps)

🛏️ BEDS:
- Place against a wall

🪴 FLOOR PLANTERS / TALL PLANTS (floor-standing decorative items):
🚨🚨🚨 CRITICAL FOR PLANTERS - DO NOT ZOOM 🚨🚨🚨
- ⚠️ ABSOLUTE RULE: The output image MUST show THE ENTIRE ROOM - NOT a close-up of the planter
- ⚠️ The planter is a TINY ACCENT piece - it should be BARELY NOTICEABLE in the image
- ⚠️ The planter should appear SMALL in the corner or edge of the image, NOT in the center
- ⚠️ NEVER zoom in, crop, or focus on the planter
- ⚠️ The camera view MUST BE IDENTICAL to the input image - same angle, same distance, same field of view
- Place in a FAR CORNER, next to furniture (against a wall), or tucked beside existing items
- The planter should occupy LESS than 5-10% of the visible image area
- Keep planters proportionally SMALL relative to furniture (floor planters are typically 2-3 feet tall MAX)
- Large/tall planters: place in a FAR CORNER of the room, NOT in the center or foreground
- 🚫 WRONG: Zooming in to show planter details - this FAILS the task
- 🚫 WRONG: Planter appearing large or prominent in the image
- ✅ CORRECT: Full room view with tiny planter visible in corner/edge
- The ENTIRE input room must be visible in the output - planter is just a small addition

💐 TABLETOP DECOR (vases, flower bunches, flower arrangements, decorative objects):
🚨🚨🚨 CRITICAL - PLACE ON TABLE SURFACES, NOT ON FLOOR 🚨🚨🚨
- ⚠️ These are SMALL tabletop items - they belong ON coffee tables, center tables, side tables, console tables, dining tables
- ⚠️ NEVER replace furniture (sofas, chairs) with decor items - ADD decor ON existing table surfaces
- ⚠️ Look for table surfaces in the room and place the decor item ON TOP of them
- Preferred surfaces: 1) Coffee/center table 2) Side table 3) Console table 4) Dining table 5) Shelf/mantel
- If no table exists: place on visible shelves, windowsills, or mantels
- Keep proportions realistic - these items are typically 10-30cm tall
- 🚫 WRONG: Replacing a sofa with a vase - this is COMPLETELY INCORRECT
- 🚫 WRONG: Placing a flower bunch on the floor
- ✅ CORRECT: A small vase sitting on the center coffee table

🗿 SCULPTURES / FIGURINES / DECORATIVE STATUES:
🚨🚨🚨 CRITICAL - PLACEMENT PRIORITY FOR SCULPTURES 🚨🚨🚨
- ⚠️ FIRST PRIORITY: Place on the CENTER TABLE / COFFEE TABLE (in front of sofa)
- ⚠️ SECOND PRIORITY: If center table is full or doesn't exist, place on a SIDE TABLE
- ⚠️ THIRD PRIORITY: If no tables available, place on console table, shelf, or mantel
- Sculptures are decorative accent pieces - they should be PROMINENTLY visible on table surfaces
- Position the sculpture facing the camera/viewer for best visual impact
- Keep proportions realistic - tabletop sculptures are typically 15-40cm tall
- 🚫 WRONG: Placing sculpture on the floor
- 🚫 WRONG: Hiding sculpture in a corner
- ✅ CORRECT: Sculpture placed centrally on the coffee table as a focal point

🖼️ WALL ART / MIRRORS / DECORATIVE ITEMS:
- Mount on walls at appropriate eye level
- These are accent pieces - maintain the full room view
- DO NOT zoom in on decorative items

📏 SPACING:
- Maintain realistic spacing and proportions
- Side tables should be 0-6 inches from sofa's side
- Center tables should be 14-18 inches from sofa's front

🎯 MANDATORY FRONT ANGLE REQUIREMENT:
═══════════════════════════════════════════════════════════════
⚠️ THE PRODUCT MUST ALWAYS SHOW ITS FRONT FACE TOWARDS THE CAMERA ⚠️
- Sofas: Show the front cushions/seating area facing the camera, NOT the back
- Tables: Show the front/main side facing the camera
- Chairs: Show the front/seating side facing the camera, NOT the back
- Cabinets/Storage: Show the doors/drawers facing the camera
- Lamps: Show the shade opening or decorative front facing the camera
- All furniture: The primary viewing angle (how it appears in showrooms) must face the camera

❌ INCORRECT ANGLES:
- Showing the back of a sofa (you should see cushions, not the sofa back panel)
- Showing a chair from behind (you should see the seat, not the chair back)
- Showing a table from a sharp side angle (you should see the full tabletop)
- Placing furniture facing away from the camera view

✅ CORRECT ANGLES:
- Products oriented so their "front" (showroom display angle) faces the camera
- User should clearly see what the product looks like from its best viewing angle
- The product should appear as it would in a furniture catalog - front and center
═══════════════════════════════════════════════════════════════

🔦 CRITICAL LIGHTING REQUIREMENTS:
⚠️ THE PRODUCT MUST LOOK LIKE IT IS PART OF THE ROOM, NOT ADDED ON TOP OF IT ⚠️
1. ANALYZE the room's lighting: identify light sources, direction, color temperature (warm/cool)
2. MATCH lighting on the product: highlights must come from the same direction as room lighting
3. MATCH shadow direction: product shadow must fall in the same direction as other shadows in room
4. MATCH exposure: product should NOT be brighter or darker than similar surfaces in room
5. NO "SPOTLIGHT" EFFECT: product must NOT look highlighted compared to the room
6. SEAMLESS BLEND: a viewer should NOT be able to tell the product was digitally added

OUTPUT: One photorealistic image showing THE ENTIRE ROOM (same wide-angle view as input) with the {product_name} added naturally.
🚨 FOR PLANTERS/PLANTS: The planter must appear SMALL (5-10% of image) in a FAR CORNER - DO NOT zoom in or make it prominent!
🚨 SIZE PRESERVATION: All existing furniture MUST remain THE EXACT SAME SIZE - no enlarging, no shrinking. The room MUST NOT expand or change shape.
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
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
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
                return result_image

            generated_image = None
            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    generated_image = await asyncio.wait_for(
                        loop.run_in_executor(None, _run_generate_add), timeout=timeout_seconds
                    )
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

            return generated_image

        except ValueError:
            # Re-raise ValueError for proper handling
            raise
        except Exception as e:
            logger.error(f"Error generating ADD visualization: {e}")
            raise ValueError(f"Visualization generation failed: {e}")

    async def generate_add_multiple_visualization(self, room_image: str, products: list[dict]) -> str:
        """
        Generate visualization with MULTIPLE products added to room in a SINGLE API call.
        This is more efficient than calling generate_add_visualization multiple times.

        Args:
            room_image: Base64 encoded room image
            products: List of dicts with 'name' and optional 'image_url' keys

        Returns: base64 image data
        """
        if not products:
            return room_image

        # Calculate total items considering quantity
        total_items = sum(p.get("quantity", 1) for p in products)

        # If only one item total (single product with quantity=1), use the single product method
        # But if quantity > 1, we need the multiple method to handle placing multiple copies
        if len(products) == 1 and total_items == 1:
            return await self.generate_add_visualization(
                room_image=room_image,
                product_name=products[0].get("full_name") or products[0].get("name"),
                product_image=products[0].get("image_url"),
            )

        logger.info(f"🛒 ADD MULTIPLE: {len(products)} products, {total_items} total items to place")

        try:
            processed_room = self._preprocess_image(room_image)

            # Download all product images
            product_images_data = []
            product_entries = []  # List of (name, quantity) tuples
            total_items_to_add = 0

            for product in products:
                name = product.get("full_name") or product.get("name")
                quantity = product.get("quantity", 1)
                total_items_to_add += quantity
                product_entries.append((name, quantity))

                image_url = product.get("image_url")
                image_data = None
                if image_url:
                    try:
                        image_data = await self._download_image(image_url)
                    except Exception as e:
                        logger.warning(f"Failed to download product image for {name}: {e}")
                product_images_data.append(image_data)

            # Build product list for prompt with quantities - VERY EXPLICIT about counts
            product_list_items = []
            item_number = 1
            for name, qty in product_entries:
                if qty > 1:
                    # List each copy as a separate numbered item to make it crystal clear
                    for copy_num in range(1, qty + 1):
                        product_list_items.append(f"  {item_number}. {name} (copy {copy_num} of {qty})")
                        item_number += 1
                else:
                    product_list_items.append(f"  {item_number}. {name}")
                    item_number += 1
            product_list = "\n".join(product_list_items)

            # Also build a summary showing counts per product type
            product_summary = []
            for name, qty in product_entries:
                product_summary.append(f"   • {name}: {qty} {'copies' if qty > 1 else 'copy'}")
            product_summary_str = "\n".join(product_summary)

            logger.info(f"Product list for prompt ({total_items_to_add} items):\n{product_list}")

            # Build product names list for legacy compatibility
            product_names = [entry[0] for entry in product_entries]

            # Check if any product has quantity > 1
            has_multiple_copies = any(qty > 1 for _, qty in product_entries)
            multiple_instance_instruction = ""

            # Base instruction to prevent adding extra furniture (applies to ALL cases)
            no_extra_furniture_warning = """
🚫🚫🚫 CRITICAL: DO NOT ADD EXTRA FURNITURE 🚫🚫🚫
═══════════════════════════════════════════════════════════════════════
⛔ ADD ONLY THE SPECIFIC PRODUCTS LISTED BELOW ⛔
⛔ DO NOT add sofas, chairs, tables, or any other furniture not in the list ⛔
⛔ DO NOT "complete" or "design" the room ⛔
⛔ DO NOT add items you think would look nice ⛔
⛔ DO NOT add matching or complementary pieces not specified ⛔

YOUR ONLY TASK: Add EXACTLY the products listed below - NOTHING MORE.
The room is ALREADY COMPLETE - it does NOT need additional furniture.

⛔ ADDING ANY UNLISTED FURNITURE = AUTOMATIC FAILURE ⛔
═══════════════════════════════════════════════════════════════════════

"""

            # For single items, add explicit instruction NOT to add extras
            if total_items_to_add == 1 and not has_multiple_copies:
                single_item_name = product_entries[0][0] if product_entries else "item"
                multiple_instance_instruction = f"""{no_extra_furniture_warning}
⚠️⚠️⚠️ CRITICAL: ADD EXACTLY 1 ITEM - NO MORE, NO LESS ⚠️⚠️⚠️
═══════════════════════════════════════════════════════════════════════

🎯 YOU MUST ADD EXACTLY 1 (ONE) {single_item_name.upper()}

⛔ DO NOT:
- Add 2 or more of this item
- Create duplicates or similar-looking items
- Add any matching/complementary pieces
- Add ANY other furniture (sofas, chairs, tables, etc.)

✅ DO:
- Add ONLY 1 (ONE) single item
- Place it in ONE appropriate location
- Keep ALL existing furniture EXACTLY as it is

COUNT CHECK: Your output should have exactly 1 new {single_item_name} added.
═══════════════════════════════════════════════════════════════════════

"""
            elif has_multiple_copies:
                logger.info(f"🪑 MULTIPLE COPIES REQUESTED: {total_items_to_add} total items from {len(products)} products")
                # Build instruction for multiple copies - use the summary we already built
                multiple_instance_instruction = f"""{no_extra_furniture_warning}
🚨🚨🚨 CRITICAL: YOU MUST ADD MULTIPLE COPIES OF SOME PRODUCTS 🚨🚨🚨
═══════════════════════════════════════════════════════════════════════

⚠️ QUANTITY REQUIREMENTS - READ CAREFULLY:
{product_summary_str}

🎯 TOTAL ITEMS YOU MUST PLACE: {total_items_to_add}

⛔ FAILURE CONDITIONS (DO NOT DO THIS):
- Adding only 1 item when 2+ copies are required
- Ignoring the quantity requirements
- Placing fewer items than specified
- Adding ANY furniture not in the list above (sofas, chairs, tables, etc.)

✅ SUCCESS CONDITIONS (DO THIS):
- Count EXACTLY {total_items_to_add} separate items in your output
- For chairs with qty=2: Place BOTH chairs SIDE BY SIDE (next to each other, facing the same direction)
- For cushions with qty=2+: Place ALL cushions on the sofa or seating
- Each copy should be in a DIFFERENT location but same style/color
- DO NOT add any furniture not specified in the list

🪑 CHAIR PLACEMENT FOR MULTIPLE COPIES:
- 2 accent chairs → Place SIDE BY SIDE (next to each other, facing the same direction)
- 2+ dining chairs → Arrange evenly around the dining table

🪑 BENCH PLACEMENT:
- ⚠️ DO NOT REMOVE existing furniture - find available empty space first
- 🛋️ LIVING ROOM: Place bench ACROSS from the sofa (on the OPPOSITE side, facing the sofa)
  - Position bench so it faces the sofa, creating a conversation area
  - Maintain 3-4 feet distance from sofa
- 🛏️ BEDROOM: Place bench at the FOOT OF THE BED (next to the footrest area)
  - Position parallel to the foot of the bed
  - Can also be placed at the end of the bed facing outward
- 🚫 NEVER place directly in front of sofa blocking the coffee table area
- 🚫 NEVER remove or replace existing chairs/furniture to make room for the bench
═══════════════════════════════════════════════════════════════════════

"""
            else:
                # Multiple different products without multiple copies of any single product
                multiple_instance_instruction = f"""{no_extra_furniture_warning}
🎯 ADD EXACTLY THESE {total_items_to_add} ITEMS - NO MORE, NO LESS 🎯
═══════════════════════════════════════════════════════════════════════

Items to add:
{product_summary_str}

⛔ DO NOT add any items not in this list
⛔ DO NOT add sofas, chairs, tables, or furniture not specified
⛔ The room is ALREADY COMPLETE

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
🌿🌿🌿 PLANTER-SPECIFIC INSTRUCTION 🌿🌿🌿
═══════════════════════════════════════════════════════════════
For any planter being added:

THE ORIGINAL ASPECT RATIO AND VIEWING ANGLE OF THE IMAGE SHOULD REMAIN THE SAME.
THE EXISTING PRODUCTS IN THE ROOM SHOULD BE CLEARLY VISIBLE AND NOT CUT FROM VIEW.
THE IMAGE SHOULD NOT BE ZOOMED IN.
THE CAMERA ANGLE SHOULD BE THE SAME.
DO NOT CROP OR CUT ANY EXISTING FURNITURE FROM THE IMAGE.
═══════════════════════════════════════════════════════════════

"""

            # Build prompt for ADD MULTIPLE action
            # Use total_items_to_add which accounts for quantities (e.g., 2 products with qty=3 each = 6 items)
            prompt = f"""{multiple_instance_instruction}{planter_instruction}ADD the following items to this room in appropriate locations WITHOUT removing any existing furniture.

📦 ITEM COUNT SUMMARY (YOU MUST ADD EXACTLY THIS MANY):
{product_summary_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 TOTAL ITEMS TO PLACE: {total_items_to_add}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DETAILED LIST - ADD EACH OF THESE {total_items_to_add} ITEMS:
{product_list}

🚨🚨🚨 ABSOLUTE REQUIREMENT - ROOM DIMENSIONS 🚨🚨🚨
═══════════════════════════════════════════════════════════════
THE OUTPUT IMAGE MUST HAVE THE EXACT SAME DIMENSIONS AS THE INPUT IMAGE.
- If input is 1024x768 pixels → output MUST be 1024x768 pixels
- NEVER change the aspect ratio
- NEVER crop, resize, or alter the image dimensions in ANY way
- The room's physical proportions MUST appear IDENTICAL
- The camera angle, perspective, and field of view MUST remain UNCHANGED
- DO NOT zoom in or out
- The walls must be in the EXACT same positions

🔒 CRITICAL PRESERVATION RULES:
1. KEEP ALL EXISTING FURNITURE: Do NOT remove or replace any furniture currently in the room
2. ⚠️ ESPECIALLY PRESERVE SOFAS: If there is a sofa/couch, it MUST remain
3. FIND APPROPRIATE SPACE: Identify suitable empty spaces for each new item
4. PRESERVE THE ROOM: Keep the same walls, windows, floors, ceiling, lighting
5. NATURAL PLACEMENT: Place products naturally where they would logically fit
6. ROOM SIZE UNCHANGED: The room must look the EXACT same size
7. ⛔ DO NOT ADD EXTRA ITEMS: Only add the items listed above. Do NOT add extra copies of items already in the room unless specifically requested. If the room has 2 lamps, keep exactly 2 lamps (not 3). Count preservation is critical.

🖼️ WALL ART / PAINTINGS - CRITICAL:
- If the room ALREADY has wall art/paintings hanging → DO NOT REPLACE them
- ADD new wall art on a DIFFERENT wall or DIFFERENT position on the same wall
- Multiple paintings CAN and SHOULD coexist - this is a GALLERY-style arrangement
- The existing artwork must REMAIN VISIBLE in its original position
- New artwork should be placed on empty wall space AWAY from existing art
- Result: Room has MULTIPLE artworks visible (not one replacing another)

⚠️ ADDING MORE OF THE SAME PRODUCT:
If the room ALREADY has a chair/cushion/table and you're asked to add ANOTHER one:
- The original item MUST REMAIN in its current position
- ADD the new item in a DIFFERENT location (next to it, across from it, etc.)
- Result: 2 items of the same type in the room (NOT replacing the original)
- Example: If there's already 1 accent chair and you add 1 more → room should have 2 chairs

🔴 EXACT PRODUCT REPLICATION - CRITICAL FOR COLORS:
For each product with a reference image provided:
- EXACT COLOR matching - if the reference shows ORANGE, output MUST be ORANGE
- EXACT MATERIAL & TEXTURE
- EXACT SHAPE & DESIGN
- The products in output MUST look like the SAME EXACT products from reference images

⚠️ COLOR MATCHING IS MANDATORY:
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

🗿 SCULPTURES / FIGURINES / DECORATIVE STATUES:
- ⚠️ FIRST PRIORITY: Place on the CENTER TABLE / COFFEE TABLE (in front of sofa)
- ⚠️ SECOND PRIORITY: If center table is full or doesn't exist, place on a SIDE TABLE
- ⚠️ THIRD PRIORITY: If no tables available, place on console table, shelf, or mantel
- Sculptures should be PROMINENTLY visible on table surfaces, NOT on the floor
- Position facing the camera for best visual impact

🎯 MANDATORY FRONT ANGLE REQUIREMENT:
⚠️ ALL PRODUCTS MUST SHOW THEIR FRONT FACE TOWARDS THE CAMERA ⚠️
- Sofas: Front cushions/seating area facing camera, NOT the back
- Tables: Front/main side facing camera
- Chairs: Front/seating side facing camera, NOT the back
- Cabinets: Doors/drawers facing camera
- All furniture: Show the primary viewing angle (showroom display angle) facing the camera
❌ WRONG: Showing furniture backs or sharp side angles
✅ CORRECT: Products oriented with their "front" facing the camera view

🔄 BALANCED DISTRIBUTION - VERY IMPORTANT:
- Distribute items on BOTH SIDES of the sofa for visual balance
- If adding a floor lamp AND a planter: put one on each side of the sofa
- If adding 2 side tables: put one on each end of the sofa
- If adding multiple floor items (lamps, planters, side tables): spread them across the room
- DON'T cluster all floor items on one side - this looks cramped and unbalanced
- Example: Floor lamp on LEFT side of sofa, planter on RIGHT side of sofa

🔦 LIGHTING:
- All products must match the room's lighting direction and color temperature
- Products must look naturally integrated, not "pasted on"

OUTPUT: One photorealistic image showing THE ENTIRE ROOM with ALL {total_items_to_add} ITEMS added naturally.
⚠️ You MUST place EXACTLY {total_items_to_add} new items in the room (some products have multiple copies).
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
                qty_for_product = next((qty for n, qty in product_entries if n == name), 1)
                if image_data:
                    if qty_for_product > 1:
                        contents.append(
                            f"\n🎨 Product {i+1} reference image ({name}) - ADD {qty_for_product} COPIES, ALL must match THIS EXACT COLOR:"
                        )
                    else:
                        contents.append(f"\n🎨 Product {i+1} reference image ({name}) - must match THIS EXACT COLOR:")
                    prod_image_bytes = base64.b64decode(image_data)
                    prod_pil_image = Image.open(io.BytesIO(prod_image_bytes))
                    if prod_pil_image.mode != "RGB":
                        prod_pil_image = prod_pil_image.convert("RGB")
                    contents.append(prod_pil_image)

            # Generate visualization with Gemini 3 Pro Image
            # Use HIGH media resolution for better quality output
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.3,
            )

            # Retry configuration with timeout protection
            max_retries = 3
            timeout_seconds = 90
            num_products = len(products)

            def _run_generate_add_multiple():
                """Run the streaming generation in a thread for timeout support."""
                result_image = None
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
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
                return result_image

            generated_image = None
            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    generated_image = await asyncio.wait_for(
                        loop.run_in_executor(None, _run_generate_add_multiple), timeout=timeout_seconds
                    )
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
            processed_room = self._preprocess_image(room_image)

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
🎨🎨🎨 CRITICAL COLOR REQUIREMENT 🎨🎨🎨
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

🚨🚨🚨 ABSOLUTE REQUIREMENT - ROOM DIMENSIONS 🚨🚨🚨
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

⚠️ IF THE OUTPUT IMAGE HAS DIFFERENT DIMENSIONS THAN THE INPUT, YOU HAVE FAILED THE TASK ⚠️
═══════════════════════════════════════════════════════════════

🚨🚨🚨 ABSOLUTE REQUIREMENT - SIZE PRESERVATION 🚨🚨🚨
═══════════════════════════════════════════════════════════════
ALL OTHER FURNITURE MUST REMAIN THE EXACT SAME SIZE AND SCALE:
- ⚠️ NEVER make remaining furniture appear larger or smaller
- ⚠️ NEVER expand the room to accommodate the new item
- ⚠️ NEVER change the perspective to make the room appear larger
- ⚠️ All proportions between remaining objects MUST remain IDENTICAL

🚫 ROOM EXPANSION IS FORBIDDEN:
- The room boundaries (walls, floor, ceiling) are FIXED
- Do NOT push walls back to create more space
- Do NOT make the ceiling appear higher
- Do NOT extend the floor area
- The room's cubic volume must remain IDENTICAL

⚠️ IF REMAINING FURNITURE CHANGES SIZE OR ROOM EXPANDS, YOU HAVE FAILED THE TASK ⚠️
═══════════════════════════════════════════════════════════════

Keep everything else in the room exactly the same - the walls, floor, windows, curtains, and all other furniture and decor should remain unchanged. The room must look the EXACT same size - not bigger, not smaller.

🎯 MANDATORY FRONT ANGLE REQUIREMENT:
⚠️ THE REPLACEMENT PRODUCT MUST SHOW ITS FRONT FACE TOWARDS THE CAMERA ⚠️
- Sofas: Show front cushions/seating area facing camera, NOT the back
- Tables: Show front/main side facing camera
- Chairs: Show front/seating side facing camera, NOT the back
- The product must be oriented so its "showroom display angle" faces the camera
❌ WRONG: Replacement showing its back or side to the camera
✅ CORRECT: Replacement oriented with front facing the camera view

🔦 CRITICAL LIGHTING REQUIREMENTS:
⚠️ THE REPLACEMENT PRODUCT MUST LOOK LIKE IT IS PART OF THE ROOM, NOT ADDED ON TOP OF IT ⚠️
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
                for chunk in self.genai_client.models.generate_content_stream(
                    model="gemini-3-pro-image-preview",
                    contents=contents,
                    config=generate_content_config,
                ):
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
                return result_image

            generated_image = None
            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    generated_image = await asyncio.wait_for(
                        loop.run_in_executor(None, _run_generate_replace), timeout=timeout_seconds
                    )
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

            # Process the base image
            processed_image = self._preprocess_image(visualization_request.base_image)

            # Use user's actual request as the primary directive
            user_request = visualization_request.user_style_description.strip()

            # Use comprehensive professional prompt template
            if products_description and product_images:
                # Build detailed product list with descriptions
                detailed_products = []
                for idx, product in enumerate(visualization_request.products_to_place):
                    product_name = product.get("full_name") or product.get("name", "furniture item")
                    product_desc = product.get("description", "No description available")

                    # Extract actual dimensions from product data (from product_attributes)
                    dimensions = product.get("dimensions", {})
                    dimension_str = ""
                    if dimensions:
                        parts = []
                        if dimensions.get("width"):
                            parts.append(f"Width: {dimensions['width']} inches")
                        if dimensions.get("depth"):
                            parts.append(f"Depth: {dimensions['depth']} inches")
                        if dimensions.get("height"):
                            parts.append(f"Height: {dimensions['height']} inches")
                        if parts:
                            dimension_str = f"- 📐 ACTUAL DIMENSIONS: {', '.join(parts)}\n"

                    detailed_products.append(
                        f"""
Product {idx + 1}:
- Name: {product_name}
- Description: {product_desc}
{dimension_str}- Placement: {user_request if user_request else 'Place naturally in appropriate location based on product type'}
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
🌿🌿🌿 PLANTER-SPECIFIC INSTRUCTION 🌿🌿🌿
═══════════════════════════════════════════════════════════════
For any planter being added:

THE ORIGINAL ASPECT RATIO AND VIEWING ANGLE OF THE IMAGE SHOULD REMAIN THE SAME.
THE EXISTING PRODUCTS IN THE ROOM SHOULD BE CLEARLY VISIBLE AND NOT CUT FROM VIEW.
THE IMAGE SHOULD NOT BE ZOOMED IN.
THE CAMERA ANGLE SHOULD BE THE SAME.
DO NOT CROP OR CUT ANY EXISTING FURNITURE FROM THE IMAGE.
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

                    multiple_instance_instruction = f"""
🪑🪑🪑 CRITICAL: MULTIPLE INSTANCES OF SAME PRODUCT 🪑🪑🪑
═══════════════════════════════════════════════════════════════
⚠️⚠️⚠️ YOU MUST PLACE ALL NUMBERED INSTANCES - DO NOT SKIP ANY ⚠️⚠️⚠️

Products with numbered names (e.g., "Cushion Cover #1", "Cushion Cover #2", "Cushion Cover #3") are MULTIPLE COPIES of the SAME item that ALL must be placed:

{instance_details}

🚨 PLACEMENT RULES FOR MULTIPLE INSTANCES:
- EVERY numbered instance (#1, #2, #3, etc.) MUST appear in the final image
- Place each instance in a DIFFERENT but RELATED position
- For cushions/pillows: arrange on the sofa - one on each seat, or clustered decoratively
- For chairs: arrange around a table or in a conversational grouping
- For dining chairs: place around the dining table at regular intervals
- For accent chairs: place in complementary positions (e.g., flanking a fireplace or sofa)
- For side tables: place at opposite ends of a sofa or beside different seating
- Maintain consistent spacing and alignment between instances
- All instances should face logical directions (not backs to the room)

❌ WRONG: Placing only 1 cushion when 3 are requested
✅ CORRECT: Placing all 3 cushions (#1, #2, #3) on the sofa
═══════════════════════════════════════════════════════════════

"""

                # Create explicit product count instruction
                product_count_instruction = ""
                if has_multiple_instances:
                    # When we have multiple instances (e.g., Cushion Cover #1, #2, #3), we need ALL of them
                    product_count_instruction = f"⚠️ PLACE EXACTLY {product_count} ITEMS TOTAL - This includes multiple copies of some products (numbered #1, #2, #3, etc.). Each numbered item MUST appear in the image."
                elif product_count == 1:
                    product_count_instruction = "⚠️ PLACE EXACTLY 1 (ONE) PRODUCT - Do NOT place multiple copies. Place only ONE instance of the product."
                elif product_count == 2:
                    product_count_instruction = "⚠️ PLACE EXACTLY 2 (TWO) DIFFERENT PRODUCTS - One of each product provided."
                else:
                    product_count_instruction = f"⚠️ PLACE EXACTLY {product_count} ITEMS - One of each product listed below."

                # Create existing furniture instruction - conditional on exclusive_products mode
                # When exclusive_products=True, we ONLY want the specified products, remove any others
                if visualization_request.exclusive_products:
                    existing_furniture_instruction = f"""11. 🛋️ EXCLUSIVE PRODUCTS MODE (CRITICAL) - The output should contain ONLY the {product_count} specified product(s) listed below:
   - IGNORE any furniture visible in the input image that is NOT in the specified product list
   - REMOVE/DO NOT RENDER any existing furniture, decor, or products from the input image
   - The ONLY furniture in the output should be the {product_count} product(s) specified below
   - Think of the input image as a base room - extract ONLY the room structure (walls, floor, windows, etc.)
   - This is a FRESH START - show the empty room with ONLY the specified products
   - Example: If input has a vase but the vase is NOT in the specified products, DO NOT show the vase in output"""
                else:
                    existing_furniture_instruction = """11. 🛋️ EXISTING FURNITURE (CRITICAL FOR CONSISTENCY) - If the input image already contains furniture (sofa, table, chair, decor, etc.), you MUST preserve the EXACT appearance of that furniture:
   - DO NOT change the COLOR of existing furniture (e.g., if sofa is blue, keep it blue)
   - DO NOT change the MATERIAL or TEXTURE of existing furniture
   - DO NOT change the STYLE or DESIGN of existing furniture
   - DO NOT change the SIZE or PROPORTIONS of existing furniture
   - Keep existing furniture looking IDENTICAL to the input image
   - You are ONLY adding NEW products, NOT modifying existing ones
   - Example: If input has a blue velvet sofa, the output MUST show the same blue velvet sofa + your new products"""

                visualization_prompt = f"""{multiple_instance_instruction}{planter_instruction}🔒🔒🔒 CRITICAL INSTRUCTION - READ CAREFULLY 🔒🔒🔒

THIS IS A PRODUCT PLACEMENT TASK. YOUR GOAL: Take the EXACT room image provided and ADD {product_count} furniture product(s) to it.

{product_count_instruction}

═══════════════════════════════════════════════════════════════
⚠️ RULE #1 - NEVER BREAK THIS RULE ⚠️
═══════════════════════════════════════════════════════════════
YOU MUST USE THE EXACT ROOM FROM THE INPUT IMAGE - PIXEL-LEVEL PRESERVATION.
DO NOT create a new room.
DO NOT redesign the space.
DO NOT change ANY aspect of the room structure.
DO NOT alter floors, walls, windows, doors, or ceiling in ANY way.

🚨 CRITICAL DIMENSIONAL REQUIREMENTS 🚨
═══════════════════════════════════════════════════════════════
1. OUTPUT IMAGE DIMENSIONS: The output image MUST have the EXACT SAME width and height (in pixels) as the input image
2. ASPECT RATIO: The aspect ratio of the output MUST be IDENTICAL to the input image
3. ROOM PROPORTIONS: The room's length and width proportions MUST remain unchanged
4. IMAGE RESOLUTION: Match the exact resolution of the input - do NOT resize or crop
5. NO DIMENSIONAL CHANGES: The room's physical dimensions (length, width, height) MUST stay the same

⚠️ VERIFICATION CHECK:
- If input image is 1024x768 pixels → output MUST be 1024x768 pixels
- If input room appears 15ft x 12ft → output room MUST appear 15ft x 12ft
- If input has 16:9 aspect ratio → output MUST have 16:9 aspect ratio

THE INPUT IMAGE SHOWS THE USER'S ACTUAL ROOM.
YOU ARE ADDING PRODUCTS TO THEIR REAL SPACE.
TREAT THE INPUT IMAGE AS SACRED - IT CANNOT BE MODIFIED.

═══════════════════════════════════════════════════════════════
⚠️ WHAT MUST STAY IDENTICAL (100% PRESERVATION REQUIRED) ⚠️
═══════════════════════════════════════════════════════════════
🚨 CRITICAL: FLOOR MUST NOT CHANGE - If the input shows solid flooring, output MUST show solid flooring. If input shows checkered floor, output MUST show checkered floor. NEVER change floor patterns or materials.

1. FLOOR (MOST CRITICAL) - EXACT SAME material, color, pattern, texture, reflections, grain - DO NOT CHANGE under any circumstances
2. WALLS - Same position, color, texture, material - walls cannot move or change
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
- White walls → Keep white walls
- Hardwood floor → Keep hardwood floor
- A window on the left → Keep window on the left
- 10ft ceiling → Keep 10ft ceiling
- Modern style → Keep modern style base

═══════════════════════════════════════════════════════════════
✅ YOUR ONLY TASK - PRODUCT PLACEMENT ONLY
═══════════════════════════════════════════════════════════════
You are placing {product_count} products into the room:
{products_detail}

🔴🔴🔴 EXACT PRODUCT REPLICATION - HIGHEST PRIORITY 🔴🔴🔴
═══════════════════════════════════════════════════════════════
For EACH product reference image provided, you MUST render the EXACT SAME product:

1. 🎨 EXACT COLOR - Copy the PRECISE color from the reference image
   - If the reference sofa is light gray, render LIGHT GRAY (not dark gray, not beige, not white)
   - If the reference table is dark walnut wood, render DARK WALNUT WOOD (not oak, not pine, not black)
   - If the reference rug is beige/cream, render BEIGE/CREAM (not brown, not white, not gray)

2. 🪵 EXACT MATERIAL & TEXTURE - Match the reference image exactly
   - If reference shows velvet fabric, render VELVET (not leather, not cotton)
   - If reference shows marble top, render MARBLE (not wood, not glass)
   - If reference shows brass legs, render BRASS (not chrome, not black metal)

3. 📐 EXACT SHAPE & DESIGN - Replicate the reference design precisely
   - If reference sofa has L-shaped sectional, render L-SHAPED SECTIONAL
   - If reference table has sleek rectangular design, render SLEEK RECTANGULAR
   - If reference has round legs, render ROUND LEGS (not square)
   - 🚨 UNIQUE/UNCONVENTIONAL SHAPES: If product has a unique shape (sphere, planet-like, sculptural, asymmetric),
     you MUST preserve that EXACT shape - do NOT simplify to a generic version
   - Example: A Saturn-shaped side table (sphere with ring) must remain a SPHERE with RING, not a generic round table
   - Example: A sculptural organic coffee table must keep its exact curves, not become a standard rectangle

4. 🏷️ EXACT STYLE - Match the product's style character
   - Modern minimalist → Keep modern minimalist
   - Traditional ornate → Keep traditional ornate
   - Mid-century → Keep mid-century

⚠️ CRITICAL: Look VERY CAREFULLY at each product reference image and replicate it AS-IS.
❌ DO NOT generate a "similar looking" or "inspired by" version
❌ DO NOT substitute with a different style of the same furniture type
❌ DO NOT change the color to "match the room better"
✅ DO render EXACTLY what you see in the product reference image
✅ The product in the output MUST look like the same exact product as the reference

📸 MULTIPLE REFERENCE IMAGES PER PRODUCT:
When multiple reference images are provided for a product (e.g., "1/3", "2/3", "3/3"):
- These show the SAME product from DIFFERENT ANGLES
- Use ALL images to understand the product's full 3D appearance
- Study each angle: front view, side view, detail shots, in-room shots
- Combine information from ALL reference images to render accurately
- The first image is usually the primary/front view
- Additional images show details, materials, proportions from other angles
- 🎯 Your rendered product should match what someone would see looking at the ACTUAL product

REFERENCE IMAGE MATCHING CHECKLIST (for each product):
□ Same exact color/shade
□ Same exact material appearance
□ Same exact shape/silhouette (ESPECIALLY important for unique designs!)
□ Same exact style characteristics
□ Same exact proportions
□ Same distinctive features (spheres stay spheres, rings stay rings, curves stay curves)

🚨 UNIQUE PRODUCT DESIGNS - SPECIAL ATTENTION:
Side tables, lamps, and decor often have UNCONVENTIONAL shapes (spheres, planets, sculptural forms).
You MUST preserve these unique shapes - do NOT convert them to generic furniture.
If you see a product that looks like a planet with a ring → RENDER a planet with a ring
If you see a product with an organic sculptural shape → RENDER that exact sculptural shape

═══════════════════════════════════════════════════════════════

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
10. ⚖️ SPATIAL BALANCE: Distribute products evenly across the room to create visual balance
   - If a planter/lamp/decor is placed on one side of the sofa, place a side table on the OTHER side
   - Avoid clustering all products on one side of the room
   - Create symmetry and balance in the overall layout

🎯 CUSTOM POSITION OVERRIDE (IF PROVIDED):
{self._build_custom_position_instructions(visualization_request.placement_positions, visualization_request.products_to_place)}

⚠️ CRITICAL: DO NOT BLOCK EXISTING FURNITURE
═══════════════════════════════════════════════════════════════
BEFORE placing any new product, you MUST:
1. 🔍 ANALYZE THE SCENE: Identify ALL existing furniture already in the room
2. 🚫 NEVER BLOCK: Do NOT place new furniture in front of existing furniture
3. 🎯 FIND EMPTY SPACES: Look for empty floor areas where nothing exists
4. 👁️ MAINTAIN SIGHT LINES: Every piece of furniture should be fully visible
5. 📐 RESPECT BOUNDARIES: New furniture should not obstruct the view of any existing item

SPECIFIC BLOCKING PREVENTION RULES:
- If a planter/decor item exists next to the sofa, do NOT place a side table in front of it
- If a side table exists, do NOT place planters/decor items in front of it
- New items should be placed in DIFFERENT locations, not overlapping with existing items
- When multiple items exist on one side, place new items on the OPPOSITE side
- Think: "Can I see the full outline of every existing furniture piece after adding this new one?"

❌ WRONG: Side table placed in front of planter → blocks planter view
✅ CORRECT: Side table on opposite side of sofa → both planter and table fully visible
═══════════════════════════════════════════════════════════════

📍 TYPE-SPECIFIC PLACEMENT RULES (ROOM-GEOMETRY AWARE):

🛋️ SOFAS & SECTIONALS (CRITICAL - READ CAREFULLY):
- ALWAYS place DIRECTLY AGAINST a SOLID wall with MINIMAL GAP (2-4 inches max from wall)
- ⚠️ DO NOT leave large empty space between sofa back and wall - sofas sit FLUSH against walls
- 🚨 NEVER place against WINDOWS, GLASS DOORS, or SLIDING DOORS - only solid walls!
- For STRAIGHT-ON camera views: place against the back wall (if solid), centered, TOUCHING the wall
- For DIAGONAL camera views: place against the PRIMARY SOLID WALL (not windows/glass), FLUSH to wall
- For CORNER camera views: place against one of the visible SOLID walls, NOT in the corner intersection
- Orientation: Sofa should be PARALLEL to the wall it's against
- Distance from wall: 0-6 inches (touching or nearly touching)
- 🚫 NEVER place sofas diagonally across room corners
- 🚫 NEVER float a sofa in the geometric center of a diagonal shot
- 🚫 NEVER place sofas in front of floor-to-ceiling windows or glass doors
- ✅ Place where a real interior designer would place it based on room layout
- ✅ Position sofas to FACE windows (for the view), not AGAINST windows

🪑 CHAIRS (accent chair, side chair, armchair):
- Position on ONE OF THE SIDES of existing sofa (if sofa exists)
- Angle towards sofa for conversation area
- Maintain 18-30 inches spacing from sofa
- For diagonal views, position relative to where the sofa is (against the primary wall)

🪑 BENCHES (bench, ottoman bench, entryway bench, storage bench):
- ⚠️ CRITICAL: DO NOT REMOVE any existing furniture (chairs, tables, etc.) when adding a bench
- 🛋️ LIVING ROOM PLACEMENT:
  - Place bench ACROSS from the sofa (on the OPPOSITE side, facing the sofa)
  - Position so the bench faces the sofa, creating a conversation area
  - Maintain 3-4 feet distance from sofa
  - The bench should be on the far side of the room relative to the sofa
- 🛏️ BEDROOM PLACEMENT:
  - Place bench at the FOOT OF THE BED (next to the footrest area)
  - Position parallel to the foot of the bed
  - Can be placed at the end of the bed facing outward
- Can also be positioned near entryways or windows as accent seating (if not living room/bedroom)
- 🚫 NEVER place bench directly in front of sofa blocking the coffee table area
- 🚫 NEVER remove or replace existing chairs/furniture to make room for the bench
- ✅ CORRECT (Living Room): Bench across from sofa, facing it at conversation distance
- ✅ CORRECT (Bedroom): Bench at foot of bed, parallel to the bed frame

🔲 CENTER TABLE / COFFEE TABLE:
- Place DIRECTLY IN FRONT OF the sofa or seating area
- For diagonal/corner views: position relative to where the sofa is placed (against primary wall)
- The table should be centered on the seating arrangement, not the image center
- Perpendicular to sofa's front face
- Distance: 14-18 inches from sofa's front

🔲 SIDE TABLE / END TABLE:
- ⚠️ CRITICAL: Place DIRECTLY ADJACENT to sofa's SIDE (at armrest)
- ⚠️ Table must be FLUSH with sofa's side, not in front or behind
- Position at SAME DEPTH as sofa (aligned with sofa's length, not width)
- Should be at ARM'S REACH from someone sitting on sofa
- Distance: 0-6 inches from sofa's side
- ⚖️ BALANCE: If planter/lamp/decor exists on one side, place side table on the OPPOSITE side
- 🚫 BLOCKING CHECK: Before placing, ensure you are NOT blocking any existing planter, lamp, or decor item
- ❌ INCORRECT: Placing in front of sofa but shifted to the side
- ❌ INCORRECT: Placing in front of an existing planter next to the sofa
- ✅ CORRECT: Directly touching or very close to sofa's side panel/armrest on the EMPTY side

📚 STORAGE (bookshelf, cabinet, dresser):
- Place against walls, not blocking pathways
- Leave space for doors to open

💡 LAMPS:
- Place on existing tables or floor
- Near seating areas for task lighting

🛏️ BEDS:
- Place AGAINST a wall - the headboard should touch a wall
- For diagonal/corner views: place against the primary wall, not floating
- Leave walkway space on at least one side
- 🚫 NEVER place beds diagonally or floating in the room center

🌿 PLANTERS (tall floor-standing plants):
- Place on floor next to sofa, chair, or in corners
- ⚖️ BALANCE: If placing next to sofa, position on one side; if side table is needed, place it on the OPPOSITE side
- 🚫 BLOCKING CHECK: Ensure planters do not block existing side tables or other furniture

🖼️ WALL ART / WALL HANGINGS / TAPESTRY / PAINTINGS:
🚨🚨🚨 CRITICAL - MOUNT ON WALL, NOT ON FLOOR 🚨🚨🚨
- ⚠️ Wall art MUST be hung ON THE WALL - NEVER placed on the floor as a rug/carpet
- ⚠️ Position on a wall, typically above a sofa, console, bed headboard, or as a focal point
- ⚠️ Height: Center of artwork should be at eye level (~57-60 inches from floor) or slightly above furniture
- ⚠️ If above sofa: bottom of art should be 6-12 inches above sofa back
- ⚠️ For tapestries with tassels/fringe: these are WALL HANGINGS, not rugs - hang on wall
- 🚫 NEVER place wall art flat on the floor - it is NOT a rug or carpet
- 🚫 NEVER confuse wall tapestries with floor rugs - check product name/type carefully
- ✅ CORRECT: Wall art hanging vertically on a wall surface
- ❌ WRONG: Wall art laid flat on the floor as a carpet

🧶 RUGS / CARPETS / AREA RUGS:
- Place FLAT ON THE FLOOR under furniture arrangements
- Rugs go UNDER coffee tables, seating areas, or dining tables
- For living rooms: rug should be large enough for front legs of sofa/chairs to rest on it
- 🚫 Do NOT confuse wall art/tapestries with rugs - check product name/description
- Wall art has "wall", "painting", "art", "tapestry", "hanging" in name → goes on WALL
- Rugs have "rug", "carpet", "floor mat", "area rug" in name → goes on FLOOR

🛋️ CUSHION COVERS / THROW PILLOWS (CRITICAL FOR MULTIPLE QUANTITIES):
- Place ON THE SOFA or chairs - cushions go ON seating, not on the floor
- When multiple cushion covers are requested (e.g., #1, #2, #3), ALL must be visible
- Arrange cushions decoratively on the sofa: corners, along the back, or clustered
- For 2 cushions: place one at each end of the sofa
- For 3 cushions: two at corners + one in the middle, or all three clustered to one side
- For 4+ cushions: distribute evenly across the sofa back
- Each numbered cushion (#1, #2, #3) is a SEPARATE item that MUST appear
- 🚨 If "Cushion Cover #1", "#2", "#3" are listed, you MUST show 3 cushions on the sofa
- ❌ WRONG: Showing only 1 cushion when 3 are requested
- ✅ CORRECT: Showing all 3 cushions arranged on the sofa

💐 TABLETOP DECOR (vases, flower bunches, sculptures, decorative objects, small decor pieces):
- ⚠️ CRITICAL: These are SMALL items that go ON TABLE SURFACES, not on the floor!
- Place ON center tables, coffee tables, side tables, console tables, or dining tables
- NEVER replace furniture like sofas/chairs - these items SIT ON existing surfaces
- If no table exists in the room, place on shelves, windowsills, or mantels
- Preferred placement priority: 1) Center/coffee table 2) Side table 3) Console table 4) Dining table 5) Shelf
- Scale appropriately - these are typically 10-30cm items, not floor-standing pieces
- ❌ WRONG: Replacing a sofa with a flower vase
- ✅ CORRECT: Placing a flower vase on the center table in front of the sofa

IMPORTANT FOR MULTIPLE PRODUCTS ({product_count} products):
- When placing {product_count} products, the room STILL stays the same
- MORE products does NOT mean redesigning the room
- Each product gets placed in the EXISTING space
- The walls, floor, windows stay IDENTICAL even with {product_count} products
- Think: "I'm adding furniture to a photo, not creating a new photo"

═══════════════════════════════════════════════════════════════
🎯 EXPECTED OUTPUT
═══════════════════════════════════════════════════════════════
Generate ONE image that shows:
- THE EXACT SAME ROOM from the input (100% preserved)
- WITH {product_count} new furniture products placed inside it
- Products sitting naturally on the floor
- Products appropriately spaced and arranged
- Everything else IDENTICAL to input image

🚨🚨🚨 CRITICAL: FULL ROOM VIEW - NO ZOOM 🚨🚨🚨
═══════════════════════════════════════════════════════════════
⚠️ DO NOT zoom in on the new product(s)
⚠️ DO NOT crop or focus on the area where products are placed
⚠️ DO NOT highlight or emphasize the new product(s)
⚠️ SHOW THE ENTIRE ROOM exactly as it appears in the input image
⚠️ The new product should be visible BUT the image should show the FULL ROOM context
⚠️ Camera position, angle, and field of view MUST be IDENTICAL to input
⚠️ If input shows a wide room view, output MUST show the same wide room view
⚠️ The product is just ONE element in the scene - NOT the focal point
═══════════════════════════════════════════════════════════════

QUALITY CHECKS:
✓ Can you overlay the input and output and see the same walls? YES
✓ Are windows in the same position? YES
✓ Is the floor the same material? YES
✓ Is the camera angle identical? YES
✓ Did you only add products? YES
✓ Is the room structure unchanged? YES
✓ Does the output show the FULL ROOM (not zoomed in on product)? YES
✓ Are ALL products showing their FRONT FACE to the camera? YES

If ANY answer is NO, you've failed the task.

🎯 MANDATORY FRONT ANGLE REQUIREMENT 🎯
═══════════════════════════════════════════════════════════════
⚠️ ALL PRODUCTS MUST SHOW THEIR FRONT FACE TOWARDS THE CAMERA ⚠️

This is MANDATORY - products must be oriented correctly:
- Sofas: Show front cushions/seating area facing camera, NOT the back panel
- Tables: Show the front/main side facing camera, NOT a sharp side angle
- Chairs: Show front/seating side facing camera, NOT the chair back
- Cabinets/Storage: Show doors/drawers facing camera
- Lamps: Show the decorative front/shade facing camera
- Beds: Show the headboard and side where you'd get in, NOT just the footboard

❌ INCORRECT ORIENTATIONS (FAILURES):
- Sofa showing its back (you see the back panel, not cushions)
- Chair showing its back (you see the chair back, not the seat)
- Table at a sharp side angle (can't see the tabletop properly)
- Any furniture "facing away" from the camera

✅ CORRECT ORIENTATIONS (REQUIRED):
- All products oriented with their "showroom display angle" facing camera
- User can clearly see what each product looks like from its primary view
- Products appear as they would in a furniture catalog - front and center
═══════════════════════════════════════════════════════════════

🔦 LIGHTING & REALISM - MOST CRITICAL FOR NATURAL APPEARANCE 🔦
═══════════════════════════════════════════════════════════════
⚠️ THE PRODUCTS MUST LOOK LIKE THEY ARE PART OF THE ROOM, NOT ADDED ON TOP OF IT ⚠️

LIGHTING ANALYSIS (DO THIS FIRST):
1. 🔍 IDENTIFY LIGHT SOURCES: Look at the input image and identify ALL light sources:
   - Windows (natural daylight direction, intensity, color temperature)
   - Artificial lights (lamps, ceiling lights, their warm/cool tone)
   - Ambient light (reflected light from walls, floor)
2. 🌡️ DETERMINE COLOR TEMPERATURE: Is the room warm (yellowish), cool (bluish), or neutral?
3. 💡 NOTE LIGHT DIRECTION: Where are shadows falling? This tells you the primary light direction.
4. 🌫️ ASSESS AMBIENT LIGHTING: How much fill light is in the shadows?

APPLY MATCHING LIGHTING TO PRODUCTS:
1. ☀️ SAME LIGHT DIRECTION: Product highlights MUST come from the same direction as room highlights
2. 🎨 SAME COLOR TEMPERATURE: If room has warm lighting, products must have warm highlights
3. 🌑 MATCHING SHADOWS: Product shadows must fall in the SAME DIRECTION as existing shadows in room
4. 💫 CONSISTENT EXPOSURE: Products should NOT be brighter or darker than similar surfaces in the room
5. 🪞 APPROPRIATE REFLECTIONS: Glossy products should reflect the room's lighting, not different lighting

SHADOW REQUIREMENTS:
- Products MUST cast shadows that match the room's shadow direction and softness
- Shadow color must match existing shadows (not pure black, usually tinted by ambient light)
- Shadow length and angle must be consistent with other objects in the room
- Contact shadows (where product meets floor) must be present and realistic

⚠️ CRITICAL: PRODUCTS MUST NOT LOOK "HIGHLIGHTED" OR "SPOTLIT"
- Do NOT render products with studio lighting if the room has natural daylight
- Do NOT make products appear brighter than their surroundings
- Do NOT add artificial highlights that don't match the room's light sources
- Products should blend seamlessly - a viewer should NOT be able to tell they were added

🎨 PHOTOREALISTIC BLENDING REQUIREMENTS:
1. NATURAL INTEGRATION: Products must look like real physical objects photographed IN THIS ROOM, NOT pasted cutouts or digitally added
2. LIGHTING CONSISTENCY: Product highlights and shadows MUST match the room's lighting direction, intensity, and color exactly
3. FLOOR CONTACT: Products must have realistic contact shadows and ground connection - NO floating
4. PERSPECTIVE MATCHING: Products must follow the exact same perspective and vanishing points as the room
5. COLOR HARMONY: Product colors should be influenced by the room's ambient lighting (e.g., warm room = warmer product tones)
6. DEPTH AND DIMENSION: Products should have proper depth cues and look three-dimensional in the space
7. MATERIAL REALISM: Reflections, textures, and material properties must look authentic in THIS room's specific lighting
8. ATMOSPHERE MATCHING: Products should have the same depth-of-field, focus, grain, and atmospheric effects as the room
9. EXPOSURE MATCHING: Products should have the same exposure level as the rest of the room - not brighter, not darker

⚠️ AVOID THESE COMMON MISTAKES (WILL MAKE PRODUCTS LOOK FAKE):
- ❌ Do NOT make products look like flat cutouts or stickers
- ❌ Do NOT place products floating above the floor
- ❌ Do NOT ignore the room's lighting when rendering products
- ❌ Do NOT use different lighting conditions for products vs. room (THIS IS THE MAIN ISSUE TO AVOID)
- ❌ Do NOT create harsh, unrealistic edges around products
- ❌ Do NOT forget shadows and reflections
- ❌ Do NOT make products appear "highlighted" or "spotlit" compared to the room
- ❌ Do NOT render products with neutral/studio lighting if room has warm/cool lighting
- ❌ Do NOT make product shadows go in a different direction than room shadows

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

                    # Use response modalities for image and text generation
                    # Use HIGH media resolution for better quality output
                    generate_content_config = types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        temperature=0.25,  # Lower temperature for better room preservation consistency
                    )

                    # Stream response with timeout protection
                    # Use a helper to wrap the streaming loop with asyncio timeout
                    visualization_timeout = 90  # 1.5 minutes max per attempt (with retries)
                    stream_start_time = time.time()

                    for chunk in self.genai_client.models.generate_content_stream(
                        model=model,
                        contents=contents,
                        config=generate_content_config,
                    ):
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

            # Process the base image
            processed_image = self._preprocess_image(base_image)

            # Build transformation prompt with strong room preservation
            visualization_prompt = f"""IMPORTANT: Use the EXACT room shown in this image as your base. Do NOT create a new room.

USER'S DESIGN REQUEST: {user_request}

🚨 CRITICAL DIMENSIONAL REQUIREMENTS 🚨
═══════════════════════════════════════════════════════════════
1. OUTPUT IMAGE DIMENSIONS: The output image MUST have the EXACT SAME width and height (in pixels) as the input image
2. ASPECT RATIO: The aspect ratio of the output MUST be IDENTICAL to the input image
3. ROOM PROPORTIONS: The room's length and width proportions MUST remain unchanged
4. IMAGE RESOLUTION: Match the exact resolution of the input - do NOT resize or crop
5. NO DIMENSIONAL CHANGES: The room's physical dimensions (length, width, height) MUST stay the same

🔒 CRITICAL PRESERVATION RULES:
1. USE THIS EXACT ROOM: Keep the same walls, windows, doors, flooring, ceiling, and architectural features shown in the image
2. PRESERVE THE SPACE: Maintain the exact room dimensions, layout, and perspective
3. KEEP EXISTING STRUCTURE: Do not change wall colors, window positions, door locations, or ceiling design unless specifically requested
4. SAME LIGHTING SETUP: Preserve existing light sources and natural lighting from windows

✨ WHAT YOU CAN DO:
1. Add furniture and decor items as requested: {user_request}
2. Style the space according to user preferences while keeping the room structure
3. Place items naturally within THIS specific room layout
4. Ensure new items match the room's scale and perspective

QUALITY REQUIREMENTS:
- Lighting: {lighting_conditions} - match existing lighting in the image
- Rendering: {render_quality} quality photorealism
- Perspective: Maintain the exact camera angle and viewpoint from the input image

🎯 RESULT: The output must show THE SAME ROOM from the input image, just with design changes applied to furniture/decor."""

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

            # Stream response
            for chunk in self.genai_client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
            ):
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
    ) -> VisualizationResult:
        """
        Generate iterative visualization by modifying an existing generated image
        Used when user requests changes to a previously generated visualization (e.g., "place the lamp in the corner")

        ISSUE 11 FIX: Now accepts placed_products to maintain product persistence across modifications
        """
        try:
            start_time = time.time()

            # Process the base image (existing visualization)
            processed_image = self._preprocess_image(base_image)

            # ISSUE 11 FIX: Build list of existing products to preserve
            existing_products_description = ""
            if placed_products and len(placed_products) > 0:
                existing_products_description = "\n\n🔒 CRITICAL: PRESERVE THESE EXISTING PRODUCTS:\n"
                existing_products_description += "The room already contains these products from previous visualizations:\n"
                for idx, product in enumerate(placed_products, 1):
                    product_name = product.get("full_name") or product.get("name", "furniture item")
                    existing_products_description += f"  {idx}. {product_name}\n"
                existing_products_description += "\n⚠️ IMPORTANT: These products MUST remain visible in the output."
                existing_products_description += "\n⚠️ DO NOT remove or replace these products unless specifically requested."
                existing_products_description += (
                    f"\n⚠️ The modification '{modification_request}' should ONLY affect what is specifically mentioned."
                )
                existing_products_description += "\n⚠️ All other furniture and products must stay exactly as shown."

            # Build iterative modification prompt with room and product preservation
            visualization_prompt = f"""IMPORTANT: This is the EXACT room to modify. Keep the same room structure, walls, windows, flooring, and perspective.

MODIFICATION REQUEST: {modification_request}
{existing_products_description}

🚨 CRITICAL DIMENSIONAL REQUIREMENTS 🚨
═══════════════════════════════════════════════════════════════
1. OUTPUT IMAGE DIMENSIONS: The output image MUST have the EXACT SAME width and height (in pixels) as the input image
2. ASPECT RATIO: The aspect ratio of the output MUST be IDENTICAL to the input image
3. ROOM PROPORTIONS: The room's length and width proportions MUST remain unchanged
4. IMAGE RESOLUTION: Match the exact resolution of the input - do NOT resize or crop
5. NO DIMENSIONAL CHANGES: The room's physical dimensions (length, width, height) MUST stay the same

🔒 CRITICAL PRESERVATION RULES:
1. USE THIS EXACT ROOM: Keep the same walls, windows, doors, flooring, ceiling shown in this image
2. PRESERVE ROOM STRUCTURE: Do not change the room layout, dimensions, or architectural features
3. KEEP CAMERA ANGLE: Maintain the exact perspective and viewpoint
4. SAME BASE SPACE: This must remain the SAME physical room, just with the requested modification
5. KEEP ALL EXISTING PRODUCTS: All furniture and products currently in the room must remain visible (unless removal is specifically requested)

✅ APPLY ONLY THIS MODIFICATION:
- User request: {modification_request}
- Change ONLY what is specifically mentioned
- Keep ALL other elements exactly as shown (especially existing products)
- If repositioning items, move only what is specifically mentioned
- If adding new items, place them naturally without removing existing items

EXAMPLES OF CORRECT MODIFICATIONS:
- "place the lamp at the far corner" → Move ONLY the lamp to corner, keep ALL other furniture exactly where it is
- "add more pillows" → Add 2-3 pillows to THIS room, keep ALL existing furniture unchanged
- "make it brighter" → Increase lighting, keep ALL furniture and products in their positions
- "move the table to the center" → Move ONLY the table, keep everything else in exact positions

QUALITY REQUIREMENTS:
- Lighting: {lighting_conditions} - maintain existing light sources
- Rendering: {render_quality} quality photorealism
- Consistency: The room must look like the SAME physical space with the SAME products

🔦 CRITICAL LIGHTING REQUIREMENTS:
⚠️ ALL PRODUCTS MUST LOOK LIKE THEY ARE PART OF THE ROOM, NOT ADDED ON TOP OF IT ⚠️
1. ANALYZE the room's lighting: identify light sources, direction, color temperature (warm/cool)
2. MATCH lighting on products: highlights must come from the same direction as room lighting
3. MATCH shadow direction: product shadows must fall in the same direction as other shadows in room
4. MATCH exposure: products should NOT be brighter or darker than similar surfaces in room
5. NO "SPOTLIGHT" EFFECT: products must NOT look highlighted compared to the room
6. SEAMLESS BLEND: a viewer should NOT be able to tell products were digitally added

🎯 RESULT: Output must show THIS EXACT ROOM with ALL existing products preserved and only the requested modification applied. Same walls, same windows, same floor, same furniture, same perspective - just with the specific change requested. All products must have lighting that perfectly matches the room."""

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

            # Stream response with timeout protection
            timeout_seconds = 60  # 60 second timeout for iterative modifications
            last_chunk_time = time.time()

            try:
                for chunk in self.genai_client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                ):
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
        instructions.append("🚚 MOVE OPERATION - RELOCATE EXISTING ITEMS IN THE SCENE")
        instructions.append("=" * 70)
        instructions.append("")
        instructions.append("⚠️ CRITICAL RULES FOR THIS MOVE OPERATION:")
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

                instructions.append(f"📦 MOVE: {item_label}")
                instructions.append(
                    f"   FROM: {from_v}, {from_h} (coordinates: X={int(from_x * 100)}%, Y={int(from_y * 100)}%)"
                )
                instructions.append(f"   TO:   {to_v}, {to_h} (coordinates: X={int(to_x * 100)}%, Y={int(to_y * 100)}%)")
                instructions.append("")
                instructions.append(f"   🔍 FIND the {item_label} at the FROM location")
                instructions.append(f"   🚫 REMOVE it from that location")
                instructions.append(f"   ✅ PLACE it at the TO location")
                instructions.append(f"   ⚠️  Keep the item's appearance EXACTLY the same")
                instructions.append("")

        instructions.append("=" * 70)
        instructions.append("🛑 ABSOLUTE RESTRICTIONS:")
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
        instructions.append("🎯 USER-SPECIFIED CUSTOM POSITIONS - OVERRIDE DEFAULT PLACEMENT")
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

                instructions.append(f"📍 Product {product_num}: {product_name}")
                instructions.append(f"   → GRID CELL: {grid_cell}")
                instructions.append(f"   → Horizontal: {h_desc} (X={int(x * 100)}%)")
                instructions.append(f"   → Depth: {v_desc} (Y={int(y * 100)}%)")
                instructions.append("")

        instructions.append("=" * 60)
        instructions.append("⚠️ IMPORTANT: These positions are USER-SPECIFIED overrides!")
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

                        # Convert to base64
                        buffer = io.BytesIO()
                        image.save(buffer, format="JPEG", quality=85, optimize=True)
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
        """Preprocess image for AI analysis"""
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

            # Resize for optimal processing (max 1024px)
            max_size = 1024
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Enhance image quality
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)

            # Convert back to base64
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=90, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode()

        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return image_data

    def _preprocess_image_for_editing(self, image_data: str) -> str:
        """
        Minimal preprocessing for image editing tasks (furniture removal).
        Preserves original quality - only strips data URL prefix and ensures valid format.
        Does NOT resize or apply enhancements that could degrade editing quality.
        """
        try:
            # Remove data URL prefix if present
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]

            # Decode and validate image
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if needed (some formats like PNG with transparency need this)
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Only resize if image is extremely large (> 4096px) to avoid API limits
            # but preserve as much quality as possible
            max_size = 4096
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                logger.info(f"Resized large image from {image.width}x{image.height} to fit within {max_size}px")

            # Convert back to base64 with high quality (95%)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=95)
            return base64.b64encode(buffer.getvalue()).decode()

        except Exception as e:
            logger.error(f"Error preprocessing image for editing: {e}")
            return image_data

    async def transform_perspective_to_front(self, image_data: str, current_viewing_angle: str) -> str:
        """
        Transform a side-angle room photo to a front-angle (straight-on) view.
        Uses Gemini to regenerate the room from a straight-on perspective.

        Args:
            image_data: Base64 encoded room image
            current_viewing_angle: "diagonal_left", "diagonal_right", "corner", or "straight_on"

        Returns:
            Base64 encoded transformed image with front-angle perspective
        """
        # If already front-facing, return as-is
        if current_viewing_angle == "straight_on":
            logger.info("Image already has straight-on perspective, skipping transformation")
            return image_data

        try:
            # Convert base64 to PIL Image
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]

            image_bytes = base64.b64decode(image_data)
            pil_image = Image.open(io.BytesIO(image_bytes))

            # Apply EXIF orientation correction
            pil_image = ImageOps.exif_transpose(pil_image)

            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            logger.info(
                f"Transforming perspective from {current_viewing_angle} to front view ({pil_image.width}x{pil_image.height})"
            )

            # Build perspective transformation prompt
            angle_descriptions = {
                "diagonal_left": "a diagonal left angle (camera positioned to the right, looking left)",
                "diagonal_right": "a diagonal right angle (camera positioned to the left, looking right)",
                "corner": "a corner angle (camera in the corner, looking diagonally across the room)",
            }
            angle_desc = angle_descriptions.get(current_viewing_angle, f"a {current_viewing_angle} angle")

            prompt = f"""🎥 CRITICAL: CHANGE THE CAMERA ANGLE

Current view: {angle_desc} (you can see TWO walls meeting at a corner).

YOUR TASK: Generate this room from a COMPLETELY DIFFERENT angle - a STRAIGHT-ON FRONT VIEW.

📸 WHAT A FRONT VIEW LOOKS LIKE:
- The main wall (solid wall, NOT windows) fills the CENTER of the image
- This wall is PARALLEL to the image edges (perfectly horizontal at top and bottom)
- Side walls are barely visible - just thin slivers on left and right edges
- You should NOT see a corner clearly anymore
- Floor stretches out in front of the camera

📐 WHAT MUST CHANGE:
- The angled walls in the current image must become straight/parallel
- The corner that's currently visible should now be at the far left or right edge (barely visible)
- The perspective lines should converge toward a single vanishing point in the center

🏠 KEEP THE SAME:
- Same room, same size, same colors
- Same floor material and color
- Same window positions (but viewed from a different angle)
- Same ceiling and lighting style

⚠️ IMPORTANT: The resulting image should look VISIBLY DIFFERENT from the input - the angle is completely different!"""

            # Generate transformed image
            def _run_transform():
                response = self.genai_client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=[prompt, pil_image],
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
            transformed_image = await asyncio.wait_for(loop.run_in_executor(None, _run_transform), timeout=90)

            if transformed_image:
                logger.info(f"Successfully transformed perspective from {current_viewing_angle} to front view")
                return transformed_image
            else:
                logger.warning("Perspective transformation produced no image, returning original")
                return f"data:image/jpeg;base64,{image_data}" if not image_data.startswith("data:") else image_data

        except asyncio.TimeoutError:
            logger.error("Perspective transformation timed out after 90 seconds")
            return f"data:image/jpeg;base64,{image_data}" if not image_data.startswith("data:") else image_data
        except Exception as e:
            logger.error(f"Error transforming perspective: {e}")
            return f"data:image/jpeg;base64,{image_data}" if not image_data.startswith("data:") else image_data

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

            products_info = f"\n\n📦 PRODUCTS IN ROOM: {products_description}" if products_description else ""

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
📐 PERSPECTIVE-AWARE SCALING SYSTEM
═══════════════════════════════════════════════════════════════

🎯 ROOM CONTEXT (from analysis):
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
🚪 SCALE ANCHORS (use these to calibrate product sizes):
- Standard interior door: 80 inches tall (6.67 feet)
- Standard window: 36-48 inches wide
- Standard ceiling: 8-9 feet (96-108 inches)
- Dining chair seat height: 18 inches from floor
- Standard sofa depth: 32-40 inches
- Coffee table height: 16-18 inches
"""

        if scale_refs.get("door_visible"):
            door_percent = scale_refs.get("door_apparent_height_percent", 25)
            instruction += f"""
🚪 DOOR DETECTED: A door is visible in this image occupying ~{door_percent}% of image height.
   Use this as your PRIMARY scale reference! Scale all products relative to this door.
"""

        # Add per-product relative scaling
        instruction += """
📏 PRODUCT RELATIVE SIZING:
Instead of guessing sizes, use these RELATIVE measurements for each product:
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
🔭 PERSPECTIVE DEPTH RULES:
Objects appear smaller as they recede into the scene due to perspective:

| Position    | Apparent Scale | Description                        |
|-------------|----------------|------------------------------------|
| FOREGROUND  | 100%           | Front of image, closest to camera  |
| MIDGROUND   | 70-80%         | Center of room                     |
| BACKGROUND  | 50-60%         | Near back wall, furthest from cam  |

⚠️ CRITICAL SCALING CHECKS:
1. If a door is visible, compare product heights to the door (80" standard)
2. A sofa (typical 84-96" wide) should occupy ~40-55% of a 12-15ft wide room
3. Products placed at the BACK of room should appear SMALLER than same product in FOREGROUND
4. A coffee table should be ~1/2 to 2/3 the width of the sofa in front of it
5. Side tables should be roughly the same height as sofa armrests (~25-30")

❌ WRONG: All products same apparent size regardless of where they're placed
❌ WRONG: Sofa at back wall appears same size as if it were in foreground
❌ WRONG: Product appears larger than the door when it should be smaller
✅ CORRECT: Products scale naturally with perspective (farther = smaller apparent size)
✅ CORRECT: Product occupies correct % of room width based on actual dimensions
✅ CORRECT: Products in background appear appropriately smaller than foreground
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
🚨🚨🚨 CRITICAL - WALLS TO AVOID (WINDOWS/GLASS DOORS) 🚨🚨🚨
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
📐 ROOM GEOMETRY AWARENESS (CRITICAL FOR SIDE-ANGLE PHOTOS)
═══════════════════════════════════════════════════════════════
{walls_avoid_warning}
🎥 CAMERA VIEWING ANGLE: {viewing_angle.upper().replace('_', ' ')}
{angle_explanation}

🏠 ROOM LAYOUT:
- Primary Wall (best for large furniture): {primary_wall.upper()} wall
- Actual Floor Center: {floor_center.replace('_', ' ')}
- Recommended Furniture Zone: {recommended_zone.replace('_', ' ')}

📍 ROOM-AWARE PLACEMENT FOR EACH PRODUCT:
{products_section}

⚠️ CRITICAL RULES FOR DIAGONAL/CORNER CAMERA VIEWS:
1. SOFAS & LARGE SEATING: Place FLUSH AGAINST SOLID walls (2-4 inch gap max), NOT floating in image center
2. The "center" of the IMAGE may NOT be the "center" of the ROOM floor
3. For diagonal views, one wall is more prominent - that's where sofas go (if it's a solid wall)
4. NEVER place sofas diagonally across corners unless explicitly requested
5. Coffee tables go in front of seating, relative to where the seating actually is
6. NEVER place furniture against floor-to-ceiling windows or glass doors

🚫 DO NOT:
- Leave large gaps between sofa back and wall - sofas should be TOUCHING or nearly touching the wall
- Place a sofa in the geometric center of the image if this is a diagonal shot
- Float large furniture in what appears to be a corner in the room
- Place sofas/beds/large furniture AGAINST WINDOWS or GLASS DOORS
- Block natural light by putting furniture in front of windows
- Ignore the room's actual layout in favor of image pixel coordinates

✅ DO:
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
            await self._make_api_request("models/gemini-3-pro-preview:generateContent", test_payload)
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
            response = await self._make_api_request("generateContent", payload)

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
            response = await self._make_api_request("models/gemini-2.0-flash:generateContent", payload)

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
            result = await self._make_api_request("models/gemini-2.0-flash-exp:generateContent", payload)
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

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None


# Global service instance
google_ai_service = GoogleAIStudioService()
