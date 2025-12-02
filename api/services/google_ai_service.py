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
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from google import genai
from google.genai import types
from PIL import Image, ImageEnhance

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
                                "text": """Analyze this interior space image and provide detailed analysis in JSON format:

{
  "room_type": "living_room/bedroom/kitchen/etc",
  "dimensions": {
    "estimated_width_ft": 12.0,
    "estimated_length_ft": 15.0,
    "estimated_height_ft": 9.0,
    "square_footage": 180.0
  },
  "lighting_conditions": "natural/artificial/mixed",
  "color_palette": ["primary_color", "secondary_color", "accent_color"],
  "existing_furniture": [
    {
      "type": "sofa",
      "position": "center-left",
      "style": "modern",
      "color": "gray",
      "condition": "good"
    }
  ],
  "architectural_features": ["windows", "fireplace", "built_ins", "etc"],
  "style_assessment": "modern/traditional/transitional/etc",
  "layout_analysis": {
    "traffic_flow": "open/restricted/balanced",
    "focal_points": ["fireplace", "tv_wall", "window"],
    "available_floor_space": "adequate/limited/spacious"
  },
  "recommendations": {
    "lighting_improvements": ["add_table_lamps", "increase_natural_light"],
    "layout_suggestions": ["create_conversation_area", "improve_flow"],
    "style_opportunities": ["add_color", "introduce_texture"]
  }
}

Provide accurate measurements and detailed observations."""
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

            result = await self._make_api_request("models/gemini-2.0-flash-exp:generateContent", payload)

            # Parse response
            content = result.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "{}")

            try:
                analysis_data = json.loads(text_response)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response, using fallback")
                analysis_data = self._create_fallback_room_analysis()

            return RoomAnalysis(
                room_type=analysis_data.get("room_type", "unknown"),
                dimensions=analysis_data.get("dimensions", {}),
                lighting_conditions=analysis_data.get("lighting_conditions", "mixed"),
                color_palette=analysis_data.get("color_palette", []),
                existing_furniture=analysis_data.get("existing_furniture", []),
                architectural_features=analysis_data.get("architectural_features", []),
                style_assessment=analysis_data.get("style_assessment", "unknown"),
                confidence_score=0.85,  # High confidence for Google AI analysis
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

            result = await self._make_api_request("models/gemini-2.0-flash-exp:generateContent", payload)

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

            result = await self._make_api_request("models/gemini-2.0-flash-exp:generateContent", payload)

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

            result = await self._make_api_request("models/gemini-2.0-flash-exp:generateContent", payload)

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

            result = await self._make_api_request("models/gemini-2.0-flash-exp:generateContent", payload)

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
                model="gemini-2.0-flash",  # Use faster model for analysis
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
        Remove all furniture from room image
        Returns: base64 encoded image with furniture removed, or None on failure
        """
        try:
            processed_image = self._preprocess_image(image_base64)

            prompt = """🚨 CRITICAL FURNITURE REMOVAL TASK 🚨

YOUR TASK: Generate an image of this EXACT SAME ROOM but with ZERO furniture or moveable items. Show ONLY the empty architectural shell.

🔴 THINK OF THIS AS: "Show me what this room looked like BEFORE any furniture was moved in" - completely empty, ready to be furnished.

═══════════════════════════════════════════════════════════════
STEP 1: IDENTIFY THE ROOM STRUCTURE (preserve exactly)
═══════════════════════════════════════════════════════════════
Look at the input image and note:
- Wall color, texture, material (keep EXACTLY the same)
- Floor color, texture, material (keep EXACTLY the same)
- Window positions, size, style (keep EXACTLY the same)
- Door positions, style (keep EXACTLY the same)
- Room dimensions and perspective (keep EXACTLY the same)
- Natural lighting direction and intensity (keep EXACTLY the same)
- Built-in ceiling lights or wall sconces (keep these ONLY)

═══════════════════════════════════════════════════════════════
STEP 2: DELETE EVERYTHING MOVEABLE (remove completely)
═══════════════════════════════════════════════════════════════
Remove EVERY SINGLE item that can be moved:

❌ FURNITURE - DELETE ALL:
• Sofas, couches, sectionals, loveseats
• ALL chairs (dining, office, accent, armchair, stool, bench)
• ALL tables (coffee, side, end, console, dining, desk)
• Beds, bed frames, mattresses, headboards
• Dressers, cabinets, shelving, bookcases, TV stands, consoles
• Ottomans, poufs, storage cubes

❌ ELECTRONICS - DELETE ALL:
• TVs (wall-mounted or on furniture)
• Computers, monitors, laptops, tablets
• Speakers, sound systems, gaming consoles

❌ LAMPS - DELETE ALL PORTABLE LIGHTS:
• Table lamps (bedside, desk, decorative) - REMOVE
• Floor lamps (arc, standing, torchiere) - REMOVE
• Portable task lights - REMOVE
✅ KEEP ONLY: Ceiling lights, recessed lights, hardwired wall sconces

❌ RUGS & TEXTILES - DELETE ALL:
• Rugs, carpets, area rugs, runners (the FLOOR underneath must be visible)
• Curtains, drapes, blinds, window treatments
• Cushions, pillows, throws, blankets, bedding

❌ DECORATIONS - DELETE ALL:
• Wall art, picture frames, paintings, posters
• Vases, sculptures, figurines, bowls, trays
• Candles, candle holders, clocks
• Plants, planters, flowers, greenery

❌ MISCELLANEOUS - DELETE ALL:
• Books, magazines, baskets, bins, containers
• Toys, games, personal items

═══════════════════════════════════════════════════════════════
STEP 3: GENERATE THE EMPTY ROOM
═══════════════════════════════════════════════════════════════
Create an image showing:
✅ SAME room structure (walls, floor, windows, doors)
✅ SAME colors and materials
✅ SAME lighting conditions and perspective
✅ COMPLETELY BARE FLOOR - not a single item on it
✅ COMPLETELY BARE WALLS (except architectural elements like baseboards)
✅ Clean, empty space ready for new furniture

The floor should be COMPLETELY VISIBLE with NO objects on it.
The walls should be CLEAN with NO decorations.
The room should look like a professional real estate photo of an EMPTY, unfurnished space.

═══════════════════════════════════════════════════════════════
⚠️ MANDATORY VERIFICATION CHECKLIST ⚠️
═══════════════════════════════════════════════════════════════
Before returning the image, verify EVERY item:

[ ] NO sofa or couch visible
[ ] NO chairs of any kind visible
[ ] NO tables of any kind visible
[ ] NO bed or mattress visible
[ ] NO lamps (table or floor) visible
[ ] NO TV or electronics visible
[ ] NO rugs or carpets on floor (floor material is visible)
[ ] NO curtains or drapes on windows
[ ] NO plants or planters visible
[ ] NO wall art or decorations visible
[ ] NO books or personal items visible
[ ] Floor is COMPLETELY EMPTY and BARE
[ ] Walls are CLEAN (only architectural elements)

🚨 IF YOU SEE ANY FURNITURE OR MOVEABLE ITEMS IN YOUR GENERATED IMAGE, YOU HAVE FAILED.

The final image must show a completely empty room - think "vacant apartment ready for new tenants" or "unfurnished model home before staging".

DO NOT leave ANY furniture behind. The room must be 100% empty."""

            # Retry loop with exponential backoff
            for attempt in range(max_retries):
                try:
                    logger.info(f"Furniture removal attempt {attempt + 1} of {max_retries}")
                    logger.info(
                        f"Sending detailed furniture removal prompt (length: {len(prompt)} chars) to Gemini 3 Pro Image (Nano Banana Pro)"
                    )

                    parts = [
                        types.Part.from_text(text=prompt),
                        types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(processed_image))),
                    ]

                    contents = [types.Content(role="user", parts=parts)]
                    generate_content_config = types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        temperature=0.7,  # Higher temperature for more aggressive furniture removal
                    )

                    logger.info(
                        "Gemini config: model=gemini-3-pro-image-preview, temperature=0.7, response_modalities=['IMAGE']"
                    )

                    # Generate furniture removal with timeout (90 seconds max per attempt)
                    import time

                    start_time = time.time()
                    timeout_seconds = 90
                    generated_image = None

                    try:
                        for chunk in self.genai_client.models.generate_content_stream(
                            model="gemini-3-pro-image-preview", contents=contents, config=generate_content_config
                        ):
                            # Check for timeout
                            if time.time() - start_time > timeout_seconds:
                                logger.error(
                                    f"Furniture removal attempt {attempt + 1} timed out after {timeout_seconds} seconds"
                                )
                                break

                            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                                for part in chunk.candidates[0].content.parts:
                                    if part.inline_data and part.inline_data.data:
                                        image_bytes = part.inline_data.data
                                        mime_type = part.inline_data.mime_type or "image/png"
                                        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                                        generated_image = f"data:{mime_type};base64,{image_base64}"
                                        logger.info(
                                            f"Furniture removal successful on attempt {attempt + 1} ({len(image_bytes)} bytes)"
                                        )
                    except Exception as stream_error:
                        logger.error(f"Furniture removal streaming error on attempt {attempt + 1}: {stream_error}")

                    if generated_image:
                        return generated_image

                    logger.warning(f"Furniture removal attempt {attempt + 1} produced no image")

                except Exception as e:
                    logger.error(f"Furniture removal attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2, 4, 8 seconds
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

    async def generate_add_visualization(self, room_image: str, product_name: str, product_image: Optional[str] = None) -> str:
        """
        Generate visualization with product ADDED to room
        Returns: base64 image data
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

            # Build prompt for ADD action
            prompt = f"""ADD the following product to this room in an appropriate location WITHOUT removing any existing furniture:

Product to add: {product_name}

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

🚫 FURNITURE YOU MUST NEVER REMOVE:
- Sofas/couches (main seating)
- Beds
- Existing accent chairs
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
- Place along a wall or centered in the room as the main seating piece

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

🪴 PLANTERS / PLANTS / VASES (DECORATIVE ITEMS):
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

🖼️ WALL ART / MIRRORS / DECORATIVE ITEMS:
- Mount on walls at appropriate eye level
- These are accent pieces - maintain the full room view
- DO NOT zoom in on decorative items

📏 SPACING:
- Maintain realistic spacing and proportions
- Side tables should be 0-6 inches from sofa's side
- Center tables should be 14-18 inches from sofa's front

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

            # Generate visualization with Gemini 3 Pro Image (Nano Banana Pro)
            generate_content_config = types.GenerateContentConfig(response_modalities=["IMAGE"], temperature=0.3)

            generated_image = None
            for chunk in self.genai_client.models.generate_content_stream(
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=generate_content_config,
            ):
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            image_bytes = part.inline_data.data
                            mime_type = part.inline_data.mime_type or "image/png"
                            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                            generated_image = f"data:{mime_type};base64,{image_base64}"
                            logger.info(f"Generated ADD visualization ({len(image_bytes)} bytes)")

            if not generated_image:
                logger.error("AI failed to generate visualization - no image returned")
                raise ValueError("AI failed to generate visualization image")

            return generated_image

        except ValueError:
            # Re-raise ValueError for proper handling
            raise
        except Exception as e:
            logger.error(f"Error generating ADD visualization: {e}")
            raise ValueError(f"Visualization generation failed: {e}")

    async def generate_replace_visualization(
        self, room_image: str, product_name: str, furniture_type: str, product_image: Optional[str] = None
    ) -> str:
        """
        Generate visualization with furniture REPLACED
        Returns: base64 image data
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

            # Build prompt for REPLACE action - simple and direct like Google AI Studio
            prompt = f"""Replace the {furniture_type} in the first image with the {product_name} shown in the second image.

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

🔦 CRITICAL LIGHTING REQUIREMENTS:
⚠️ THE REPLACEMENT PRODUCT MUST LOOK LIKE IT IS PART OF THE ROOM, NOT ADDED ON TOP OF IT ⚠️
1. ANALYZE the room's lighting: identify light sources, direction, color temperature (warm/cool)
2. MATCH lighting on the new product: highlights must come from the same direction as room lighting
3. MATCH shadow direction: product shadow must fall in the same direction as other shadows in room
4. MATCH exposure: product should NOT be brighter or darker than similar surfaces in room
5. NO "SPOTLIGHT" EFFECT: product must NOT look highlighted compared to the room
6. SEAMLESS BLEND: a viewer should NOT be able to tell the product was digitally added

Generate a photorealistic image of the room with the {product_name} replacing the {furniture_type}, with lighting that perfectly matches the room's existing lighting conditions."""

            # Build parts list
            parts = [types.Part.from_text(text=prompt)]
            parts.append(types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(processed_room))))

            # Add product reference image if available
            # IMPORTANT: Do NOT add text labels between images - this confuses the model
            # Send images directly back-to-back like Google AI Studio does
            if product_image_data:
                parts.append(
                    types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(product_image_data)))
                )

            contents = [types.Content(role="user", parts=parts)]

            # Generate visualization with Gemini 3 Pro Image (Nano Banana Pro)
            # Use temperature 0.4 to match Google AI Studio's default
            generate_content_config = types.GenerateContentConfig(response_modalities=["IMAGE"], temperature=0.4)

            generated_image = None
            for chunk in self.genai_client.models.generate_content_stream(
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=generate_content_config,
            ):
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            image_bytes = part.inline_data.data
                            mime_type = part.inline_data.mime_type or "image/png"
                            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                            generated_image = f"data:{mime_type};base64,{image_base64}"
                            logger.info(f"Generated REPLACE visualization ({len(image_bytes)} bytes)")

            if not generated_image:
                logger.error("AI failed to generate REPLACE visualization - no image returned")
                raise ValueError("AI failed to generate visualization image")

            return generated_image

        except ValueError:
            # Re-raise ValueError for proper handling
            raise
        except Exception as e:
            logger.error(f"Error generating REPLACE visualization: {e}")
            raise ValueError(f"Visualization generation failed: {e}")

    async def generate_room_visualization(self, visualization_request: VisualizationRequest) -> VisualizationResult:
        """
        Generate photorealistic room visualization using a HYBRID approach:
        1. Use AI to understand the room and identify placement locations
        2. Use AI to generate masked products
        3. Composite products onto the ORIGINAL room image (preserving 100% of original)
        """
        try:
            start_time = time.time()

            # Prepare products description for the prompt
            products_description = []
            product_images = []
            for idx, product in enumerate(visualization_request.products_to_place):
                product_name = product.get("full_name") or product.get("name", "furniture item")
                products_description.append(f"Product {idx+1}: {product_name}")

                # Download product image if available
                if product.get("image_url"):
                    try:
                        product_image_data = await self._download_image(product["image_url"])
                        if product_image_data:
                            product_images.append({"data": product_image_data, "name": product_name, "index": idx + 1})
                    except Exception as e:
                        logger.warning(f"Failed to download product image: {e}")

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
                    detailed_products.append(
                        f"""
Product {idx + 1}:
- Name: {product_name}
- Description: {product_desc}
- Placement: {user_request if user_request else 'Place naturally in appropriate location based on product type'}
- Reference Image: Provided below"""
                    )

                products_detail = "\n".join(detailed_products)

                # ULTRA-STRICT room preservation prompt
                product_count = len(visualization_request.products_to_place)

                # Create explicit product count instruction
                product_count_instruction = ""
                if product_count == 1:
                    product_count_instruction = "⚠️ PLACE EXACTLY 1 (ONE) PRODUCT - Do NOT place multiple copies. Place only ONE instance of the product."
                elif product_count == 2:
                    product_count_instruction = "⚠️ PLACE EXACTLY 2 (TWO) DIFFERENT PRODUCTS - One of each product provided, not multiple copies of the same product."
                else:
                    product_count_instruction = f"⚠️ PLACE EXACTLY {product_count} DIFFERENT PRODUCTS - One of each product provided, not multiple copies of any single product."

                visualization_prompt = f"""🔒🔒🔒 CRITICAL INSTRUCTION - READ CAREFULLY 🔒🔒🔒

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
11. 🛋️ EXISTING FURNITURE (CRITICAL FOR CONSISTENCY) - If the input image already contains furniture (sofa, table, chair, decor, etc.), you MUST preserve the EXACT appearance of that furniture:
   - DO NOT change the COLOR of existing furniture (e.g., if sofa is blue, keep it blue)
   - DO NOT change the MATERIAL or TEXTURE of existing furniture
   - DO NOT change the STYLE or DESIGN of existing furniture
   - DO NOT change the SIZE or PROPORTIONS of existing furniture
   - Keep existing furniture looking IDENTICAL to the input image
   - You are ONLY adding NEW products, NOT modifying existing ones
   - Example: If input has a blue velvet sofa, the output MUST show the same blue velvet sofa + your new products

IF THE ROOM HAS:
- White walls → Keep white walls
- Hardwood floor → Keep hardwood floor
- A window on the left → Keep window on the left
- 10ft ceiling → Keep 10ft ceiling
- Modern style → Keep modern style base
- A blue sofa → Keep the EXACT same blue sofa (same color, same style, same size)
- A gray coffee table → Keep the EXACT same gray coffee table
- Any existing furniture → Keep it IDENTICAL to the input image

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

REFERENCE IMAGE MATCHING CHECKLIST (for each product):
□ Same exact color/shade
□ Same exact material appearance
□ Same exact shape/silhouette
□ Same exact style characteristics
□ Same exact proportions

═══════════════════════════════════════════════════════════════

📏 CRITICAL SIZING INSTRUCTION:
Each product has its own real-world dimensions. You MUST honor these dimensions exactly:
1. Look at the product reference images provided - these show the actual product proportions
2. Estimate the room dimensions from the input image (walls, existing furniture, doorways)
3. Scale each product proportionally to fit the room, maintaining the product's ACTUAL aspect ratio and proportions
4. DO NOT invent or change product dimensions - use what you see in the product reference images
5. If a coffee table is 36" wide in reality, it should appear 36" wide in the room (scaled to perspective)
6. If a sofa is 84" long in reality, it should appear 84" long in the room (scaled to perspective)

PLACEMENT STRATEGY:
1. Look at the EXACT room in the input image
2. Estimate room dimensions from visual cues (walls, existing furniture, doorways, standard door height ~80")
3. Identify appropriate floor space for each product
4. Place products ON THE FLOOR of THIS room (not floating)
5. Scale products proportionally based on estimated room size AND product's actual dimensions from reference image
6. Maintain realistic proportions - a 36" coffee table should look appropriate in a 12x15 ft room
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

📍 TYPE-SPECIFIC PLACEMENT RULES:

🪑 SOFAS:
- Place along a wall or centered in the room as the main seating piece

🪑 CHAIRS (accent chair, side chair, armchair):
- Position on ONE OF THE SIDES of existing sofa (if sofa exists)
- Angle towards sofa for conversation area
- Maintain 18-30 inches spacing from sofa

🔲 CENTER TABLE / COFFEE TABLE:
- Place DIRECTLY IN FRONT OF the sofa or seating area
- Centered between sofa and opposite wall
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
- Place against longest wall
- Leave walkway space on at least one side

🌿 PLANTERS / DECOR ITEMS (vases, sculptures, decorative objects):
- Place on floor next to sofa, chair, or table
- Can be placed on existing side tables or shelves
- ⚖️ BALANCE: If placing next to sofa, position on one side; if side table is needed, place it on the OPPOSITE side
- 🚫 BLOCKING CHECK: Ensure planters do not block existing side tables or other furniture
- Avoid blocking pathways or clustering all decor on one side
- Create visual balance by distributing decor items across the room
- ✅ CORRECT: Planter on left side of sofa, side table on right side (both fully visible)

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

QUALITY CHECKS:
✓ Can you overlay the input and output and see the same walls? YES
✓ Are windows in the same position? YES
✓ Is the floor the same material? YES
✓ Is the camera angle identical? YES
✓ Did you only add products? YES
✓ Is the room structure unchanged? YES

If ANY answer is NO, you've failed the task.

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

                    # Build parts list with room image and all product images
                    parts = [types.Part.from_text(text=visualization_prompt)]

                    # Add room image
                    parts.append(
                        types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(processed_image)))
                    )

                    # Add product images as references
                    for prod_img in product_images:
                        parts.append(
                            types.Part.from_text(text=f"\nProduct {prod_img['index']} reference image ({prod_img['name']}):")
                        )
                        parts.append(
                            types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=base64.b64decode(prod_img["data"])))
                        )

                    contents = [types.Content(role="user", parts=parts)]

                    # Use response modalities for image and text generation
                    generate_content_config = types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        temperature=0.25,  # Lower temperature for better room preservation consistency
                    )

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
                                logger.info(f"Generated image with {model} ({len(image_bytes)} bytes)")

                            elif part.text:
                                transformation_description += part.text

                    # If we got here without exception, break the retry loop
                    break

                except asyncio.TimeoutError:
                    logger.error(f"TIMEOUT: Google Gemini API timed out after {time.time() - start_time:.2f}s")
                    # Return original image on timeout with clear error message
                    return VisualizationResult(
                        rendered_image=visualization_request.base_image,
                        processing_time=time.time() - start_time,
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
            generate_content_config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"], temperature=0.4)

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
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"], temperature=0.3  # Lower temperature for more consistent modifications
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
        """Build custom position instructions for Gemini prompt"""
        if not positions or len(positions) == 0:
            return "No custom positions provided. Use default placement strategy above."

        instructions = []
        instructions.append("⚠️ CRITICAL: USER HAS SPECIFIED CUSTOM POSITIONS - YOU MUST FOLLOW THESE EXACTLY:")
        instructions.append("")

        for pos in positions:
            # Find the corresponding product
            product_id = pos.get("productId") or pos.get("product_id")
            matching_product = None
            for idx, product in enumerate(products):
                if str(product.get("id")) == str(product_id):
                    matching_product = (idx + 1, product.get("full_name") or product.get("name", "unknown"))
                    break

            if matching_product:
                product_num, product_name = matching_product
                x = pos.get("x", 0.5)
                y = pos.get("y", 0.5)

                # Convert x,y percentages (0-1) to room position instructions
                horizontal = "center"
                if x < 0.33:
                    horizontal = "left side"
                elif x > 0.67:
                    horizontal = "right side"

                vertical = "middle"
                if y < 0.33:
                    vertical = "back/far"
                elif y > 0.67:
                    vertical = "front/near"

                instructions.append(f"Product {product_num} ({product_name}): Place at {horizontal} of room, {vertical} depth")
                instructions.append(f"  - Horizontal position: {int(x * 100)}% from left edge")
                instructions.append(f"  - Depth position: {int(y * 100)}% from back wall")

        instructions.append("")
        instructions.append("🔒 THESE POSITIONS ARE MANDATORY - Place products at these exact locations!")

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
                last_error = e
            except (aiohttp.ClientError, OSError) as e:
                logger.warning(f"Network error downloading image (attempt {attempt + 1}/{max_retries}): {e}")
                last_error = e
            except Exception as e:
                logger.error(f"Error downloading image from {image_url}: {e}")
                last_error = e

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

    def _create_fallback_room_analysis(self) -> RoomAnalysis:
        """Create fallback room analysis"""
        return RoomAnalysis(
            room_type="living_room",
            dimensions={"estimated_width_ft": 12, "estimated_length_ft": 15, "square_footage": 180},
            lighting_conditions="mixed",
            color_palette=["neutral", "warm_gray", "white"],
            existing_furniture=[],
            architectural_features=["windows"],
            style_assessment="contemporary",
            confidence_score=0.3,
        )

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
            await self._make_api_request("models/gemini-1.5-pro:generateContent", test_payload)
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

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None


# Global service instance
google_ai_service = GoogleAIStudioService()
