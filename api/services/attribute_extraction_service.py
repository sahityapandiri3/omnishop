"""
Attribute Extraction Service

Extracts product attributes (color, material, style, dimensions, texture, pattern)
from product images and text using Gemini AI.
"""

import asyncio
import base64
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Product, ProductAttribute

logger = logging.getLogger(__name__)


@dataclass
class AttributeExtractionResult:
    """Result from attribute extraction"""
    furniture_type: Optional[str] = None
    colors: Dict[str, Optional[str]] = field(default_factory=dict)
    materials: Dict[str, Optional[str]] = field(default_factory=dict)
    style: Optional[str] = None
    dimensions: Dict[str, Optional[float]] = field(default_factory=dict)
    texture: Optional[str] = None
    pattern: Optional[str] = None
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    extraction_method: str = "unknown"
    success: bool = False
    error_message: Optional[str] = None


class AttributeExtractionService:
    """Service for extracting product attributes using Gemini AI"""

    def __init__(self, google_ai_service):
        """
        Initialize attribute extraction service

        Args:
            google_ai_service: Instance of GoogleAIService for API calls
        """
        self.google_ai_service = google_ai_service
        self.logger = logging.getLogger(__name__)

    async def extract_attributes(
        self,
        product_id: int,
        image_url: Optional[str] = None,
        product_name: Optional[str] = None,
        product_description: Optional[str] = None
    ) -> AttributeExtractionResult:
        """
        Extract attributes from product image and/or text

        Args:
            product_id: Product ID
            image_url: URL of product image
            product_name: Product name
            product_description: Product description

        Returns:
            AttributeExtractionResult with extracted attributes
        """
        image_result = None
        text_result = None

        # Try image extraction first (higher accuracy)
        if image_url:
            try:
                image_result = await self.extract_attributes_from_image(image_url)
                self.logger.info(f"Image extraction for product {product_id}: "
                               f"success={image_result.success}, "
                               f"confidence={image_result.confidence_scores.get('overall', 0):.2f}")
            except Exception as e:
                self.logger.error(f"Image extraction failed for product {product_id}: {e}")

        # Try text extraction as fallback or supplement
        if product_name or product_description:
            try:
                text_result = await self.extract_attributes_from_text(
                    product_name or "",
                    product_description or ""
                )
                self.logger.info(f"Text extraction for product {product_id}: "
                               f"success={text_result.success}")
            except Exception as e:
                self.logger.error(f"Text extraction failed for product {product_id}: {e}")

        # Merge results
        if image_result and text_result:
            return self.merge_attributes(image_result, text_result)
        elif image_result:
            return image_result
        elif text_result:
            return text_result
        else:
            return AttributeExtractionResult(
                success=False,
                error_message="Both image and text extraction failed"
            )

    async def extract_attributes_from_image(self, image_url: str) -> AttributeExtractionResult:
        """
        Extract attributes from product image using Gemini Vision

        Args:
            image_url: URL of product image

        Returns:
            AttributeExtractionResult with extracted attributes
        """
        try:
            # Fetch image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to fetch image: HTTP {response.status}")
                    image_data = await response.read()

            # Convert to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # Create prompt for Gemini
            prompt = self._create_image_extraction_prompt()

            # Build payload for Gemini API
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 2048,
                    "responseMimeType": "application/json"
                }
            }

            # Call Gemini API
            response = await self.google_ai_service._make_api_request(
                "models/gemini-2.0-flash-exp:generateContent",
                payload
            )

            # Extract JSON response
            content = response.get("candidates", [{}])[0].get("content", {})
            text_response = content.get("parts", [{}])[0].get("text", "{}")

            # Parse JSON
            try:
                import json
                response_data = json.loads(text_response)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse Gemini response as JSON: {e}")
                response_data = {}

            # Parse response
            result = self._parse_gemini_response(response_data, "gemini_vision")
            result.success = True
            return result

        except Exception as e:
            self.logger.error(f"Image extraction error: {e}")
            return AttributeExtractionResult(
                success=False,
                error_message=str(e),
                extraction_method="gemini_vision"
            )

    async def extract_attributes_from_text(
        self,
        product_name: str,
        product_description: str
    ) -> AttributeExtractionResult:
        """
        Extract attributes from product name and description using NLP + regex

        Args:
            product_name: Product name
            product_description: Product description

        Returns:
            AttributeExtractionResult with extracted attributes
        """
        result = AttributeExtractionResult(extraction_method="text_nlp")

        text = f"{product_name} {product_description}".lower()

        try:
            # Extract furniture type
            result.furniture_type = self._extract_furniture_type(text)
            result.confidence_scores['furniture_type'] = 0.8 if result.furniture_type else 0.0

            # Extract colors
            colors = self._extract_colors(text)
            if colors:
                result.colors = {
                    'primary': colors[0] if len(colors) > 0 else None,
                    'secondary': colors[1] if len(colors) > 1 else None,
                    'accent': colors[2] if len(colors) > 2 else None
                }
                result.confidence_scores['colors'] = 0.7

            # Extract materials
            materials = self._extract_materials(text)
            if materials:
                result.materials = {
                    'primary': materials[0] if len(materials) > 0 else None,
                    'secondary': materials[1] if len(materials) > 1 else None
                }
                result.confidence_scores['materials'] = 0.75

            # Extract style
            result.style = self._extract_style(text)
            result.confidence_scores['style'] = 0.7 if result.style else 0.0

            # Extract dimensions
            result.dimensions = self._extract_dimensions(text)
            if result.dimensions:
                result.confidence_scores['dimensions'] = 0.8

            # Extract texture
            result.texture = self._extract_texture(text)
            result.confidence_scores['texture'] = 0.6 if result.texture else 0.0

            # Extract pattern
            result.pattern = self._extract_pattern(text)
            result.confidence_scores['pattern'] = 0.6 if result.pattern else 0.0

            # Calculate overall confidence
            scores = [v for v in result.confidence_scores.values() if v > 0]
            result.confidence_scores['overall'] = sum(scores) / len(scores) if scores else 0.0

            result.success = result.confidence_scores['overall'] > 0.3
            return result

        except Exception as e:
            self.logger.error(f"Text extraction error: {e}")
            result.success = False
            result.error_message = str(e)
            return result

    def merge_attributes(
        self,
        image_result: AttributeExtractionResult,
        text_result: AttributeExtractionResult
    ) -> AttributeExtractionResult:
        """
        Merge image and text extraction results

        Priority: Image attributes (higher confidence) > Text attributes (fill gaps)

        Args:
            image_result: Result from image extraction
            text_result: Result from text extraction

        Returns:
            Merged AttributeExtractionResult
        """
        merged = AttributeExtractionResult(extraction_method="merged")

        # Furniture type (prefer image)
        merged.furniture_type = image_result.furniture_type or text_result.furniture_type

        # Colors (prefer image, but fill gaps with text)
        merged.colors = {
            'primary': (image_result.colors.get('primary') or
                       text_result.colors.get('primary')),
            'secondary': (image_result.colors.get('secondary') or
                         text_result.colors.get('secondary')),
            'accent': (image_result.colors.get('accent') or
                      text_result.colors.get('accent'))
        }

        # Materials (prefer image, but fill gaps with text)
        merged.materials = {
            'primary': (image_result.materials.get('primary') or
                       text_result.materials.get('primary')),
            'secondary': (image_result.materials.get('secondary') or
                         text_result.materials.get('secondary'))
        }

        # Style (prefer image)
        merged.style = image_result.style or text_result.style

        # Dimensions (prefer text - more accurate from descriptions)
        merged.dimensions = text_result.dimensions if text_result.dimensions else image_result.dimensions

        # Texture (prefer image)
        merged.texture = image_result.texture or text_result.texture

        # Pattern (prefer image)
        merged.pattern = image_result.pattern or text_result.pattern

        # Merge confidence scores (weighted average)
        merged.confidence_scores = {}
        for key in ['furniture_type', 'colors', 'materials', 'style', 'dimensions', 'texture', 'pattern']:
            image_conf = image_result.confidence_scores.get(key, 0)
            text_conf = text_result.confidence_scores.get(key, 0)
            # Weighted: Image 70%, Text 30%
            merged.confidence_scores[key] = (image_conf * 0.7 + text_conf * 0.3)

        # Calculate overall confidence
        scores = [v for v in merged.confidence_scores.values() if v > 0]
        merged.confidence_scores['overall'] = sum(scores) / len(scores) if scores else 0.0

        merged.success = True
        return merged

    async def store_attributes(
        self,
        product_id: int,
        attributes: AttributeExtractionResult,
        db: AsyncSession
    ) -> int:
        """
        Store extracted attributes in ProductAttribute table

        Args:
            product_id: Product ID
            attributes: Extracted attributes
            db: Database session

        Returns:
            Number of attributes stored
        """
        stored_count = 0

        try:
            # Store furniture type
            if attributes.furniture_type:
                await self._store_attribute(
                    db, product_id, 'furniture_type', attributes.furniture_type,
                    'text', attributes.confidence_scores.get('furniture_type', 0.5),
                    attributes.extraction_method
                )
                stored_count += 1

            # Store colors
            if attributes.colors.get('primary'):
                await self._store_attribute(
                    db, product_id, 'color_primary', attributes.colors['primary'],
                    'text', attributes.confidence_scores.get('colors', 0.5),
                    attributes.extraction_method
                )
                stored_count += 1

            if attributes.colors.get('secondary'):
                await self._store_attribute(
                    db, product_id, 'color_secondary', attributes.colors['secondary'],
                    'text', attributes.confidence_scores.get('colors', 0.5),
                    attributes.extraction_method
                )
                stored_count += 1

            # Store materials
            if attributes.materials.get('primary'):
                await self._store_attribute(
                    db, product_id, 'material_primary', attributes.materials['primary'],
                    'text', attributes.confidence_scores.get('materials', 0.5),
                    attributes.extraction_method
                )
                stored_count += 1

            if attributes.materials.get('secondary'):
                await self._store_attribute(
                    db, product_id, 'material_secondary', attributes.materials['secondary'],
                    'text', attributes.confidence_scores.get('materials', 0.5),
                    attributes.extraction_method
                )
                stored_count += 1

            # Store style
            if attributes.style:
                await self._store_attribute(
                    db, product_id, 'style', attributes.style,
                    'text', attributes.confidence_scores.get('style', 0.5),
                    attributes.extraction_method
                )
                stored_count += 1

            # Store dimensions
            if attributes.dimensions:
                if attributes.dimensions.get('width'):
                    await self._store_attribute(
                        db, product_id, 'width', str(attributes.dimensions['width']),
                        'number', attributes.confidence_scores.get('dimensions', 0.5),
                        attributes.extraction_method
                    )
                    stored_count += 1

                if attributes.dimensions.get('depth'):
                    await self._store_attribute(
                        db, product_id, 'depth', str(attributes.dimensions['depth']),
                        'number', attributes.confidence_scores.get('dimensions', 0.5),
                        attributes.extraction_method
                    )
                    stored_count += 1

                if attributes.dimensions.get('height'):
                    await self._store_attribute(
                        db, product_id, 'height', str(attributes.dimensions['height']),
                        'number', attributes.confidence_scores.get('dimensions', 0.5),
                        attributes.extraction_method
                    )
                    stored_count += 1

            # Store texture
            if attributes.texture:
                await self._store_attribute(
                    db, product_id, 'texture', attributes.texture,
                    'text', attributes.confidence_scores.get('texture', 0.5),
                    attributes.extraction_method
                )
                stored_count += 1

            # Store pattern
            if attributes.pattern:
                await self._store_attribute(
                    db, product_id, 'pattern', attributes.pattern,
                    'text', attributes.confidence_scores.get('pattern', 0.5),
                    attributes.extraction_method
                )
                stored_count += 1

            await db.commit()
            self.logger.info(f"Stored {stored_count} attributes for product {product_id}")
            return stored_count

        except Exception as e:
            self.logger.error(f"Error storing attributes for product {product_id}: {e}")
            await db.rollback()
            raise

    async def _store_attribute(
        self,
        db: AsyncSession,
        product_id: int,
        attribute_name: str,
        attribute_value: str,
        attribute_type: str,
        confidence_score: float,
        extraction_method: str
    ):
        """Helper to store a single attribute"""
        # Check if attribute already exists
        result = await db.execute(
            select(ProductAttribute).where(
                ProductAttribute.product_id == product_id,
                ProductAttribute.attribute_name == attribute_name
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update if new confidence is higher
            if confidence_score > (existing.confidence_score or 0):
                existing.attribute_value = attribute_value
                existing.confidence_score = confidence_score
                existing.extraction_method = extraction_method
        else:
            # Create new attribute
            attr = ProductAttribute(
                product_id=product_id,
                attribute_name=attribute_name,
                attribute_value=attribute_value,
                attribute_type=attribute_type,
                confidence_score=confidence_score,
                extraction_method=extraction_method
            )
            db.add(attr)

    # ==================== Prompt Engineering ====================

    def _create_image_extraction_prompt(self) -> str:
        """Create detailed prompt for Gemini image extraction"""
        return """Analyze this furniture product image and extract the following attributes in JSON format:

1. furniture_type: The type of furniture (sofa, chair, table, bed, lamp, etc.)
2. colors: Object with primary, secondary, and accent colors (use common color names like "red", "blue", "gray", etc.)
3. materials: Object with primary and secondary materials (leather, wood, metal, fabric, glass, etc.)
4. style: Design style (modern, traditional, rustic, contemporary, industrial, mid-century, scandinavian, etc.)
5. dimensions: Estimated or visible dimensions in inches (width, depth, height)
6. texture: Surface texture (smooth, rough, woven, tufted, brushed, etc.)
7. pattern: Visual pattern (solid, striped, floral, geometric, abstract, plaid, etc.)
8. confidence_scores: Object with confidence score (0-1) for each attribute

Return ONLY valid JSON in this exact format:
{
  "furniture_type": "sofa",
  "colors": {
    "primary": "gray",
    "secondary": "white",
    "accent": null
  },
  "materials": {
    "primary": "fabric",
    "secondary": "wood"
  },
  "style": "modern",
  "dimensions": {
    "width": 84,
    "depth": 36,
    "height": 33
  },
  "texture": "woven",
  "pattern": "solid",
  "confidence_scores": {
    "furniture_type": 0.95,
    "colors": 0.90,
    "materials": 0.85,
    "style": 0.80,
    "dimensions": 0.70,
    "texture": 0.75,
    "pattern": 0.90
  }
}

Guidelines:
- Be specific and accurate
- Use common terminology
- Estimate dimensions if not clearly visible
- Set confidence lower if uncertain
- Return null for attributes that cannot be determined
"""

    def _parse_gemini_response(self, response: Dict[str, Any], method: str) -> AttributeExtractionResult:
        """Parse Gemini API response into AttributeExtractionResult"""
        try:
            result = AttributeExtractionResult(extraction_method=method)

            result.furniture_type = response.get('furniture_type')
            result.colors = response.get('colors', {})
            result.materials = response.get('materials', {})
            result.style = response.get('style')
            result.dimensions = response.get('dimensions', {})
            result.texture = response.get('texture')
            result.pattern = response.get('pattern')
            result.confidence_scores = response.get('confidence_scores', {})

            # Calculate overall confidence
            scores = [v for v in result.confidence_scores.values() if isinstance(v, (int, float)) and v > 0]
            result.confidence_scores['overall'] = sum(scores) / len(scores) if scores else 0.0

            result.success = True
            return result

        except Exception as e:
            self.logger.error(f"Error parsing Gemini response: {e}")
            return AttributeExtractionResult(
                success=False,
                error_message=str(e),
                extraction_method=method
            )

    # ==================== Text Extraction Helpers ====================

    def _extract_furniture_type(self, text: str) -> Optional[str]:
        """Extract furniture type from text"""
        furniture_types = {
            'sofa': ['sofa', 'couch', 'sectional', 'loveseat', 'settee'],
            'chair': ['chair', 'armchair', 'recliner', 'accent chair'],
            'table': ['table', 'desk'],
            'coffee table': ['coffee table', 'center table', 'cocktail table'],
            'side table': ['side table', 'end table', 'nightstand', 'bedside table'],
            'dining table': ['dining table'],
            'bed': ['bed', 'bedframe'],
            'lamp': ['lamp', 'light', 'lighting'],
            'pendant': ['pendant', 'chandelier'],
            'dresser': ['dresser', 'chest of drawers'],
            'cabinet': ['cabinet', 'cupboard'],
            'bookshelf': ['bookshelf', 'bookcase']
        }

        for furniture_type, keywords in furniture_types.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                    return furniture_type

        return None

    def _extract_colors(self, text: str) -> List[str]:
        """Extract colors from text"""
        colors = [
            'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink',
            'black', 'white', 'gray', 'grey', 'brown', 'beige', 'tan',
            'navy', 'burgundy', 'maroon', 'teal', 'turquoise', 'gold',
            'silver', 'bronze', 'cream', 'ivory', 'charcoal', 'espresso',
            'walnut', 'oak', 'mahogany', 'cherry'
        ]

        found_colors = []
        for color in colors:
            if re.search(r'\b' + re.escape(color) + r'\b', text):
                found_colors.append(color)

        return found_colors

    def _extract_materials(self, text: str) -> List[str]:
        """Extract materials from text"""
        materials = [
            'leather', 'wood', 'wooden', 'metal', 'steel', 'iron',
            'fabric', 'cotton', 'linen', 'velvet', 'polyester',
            'glass', 'marble', 'stone', 'ceramic', 'plastic',
            'wicker', 'rattan', 'bamboo', 'oak', 'pine', 'walnut',
            'mahogany', 'teak', 'brass', 'bronze', 'aluminum'
        ]

        found_materials = []
        for material in materials:
            if re.search(r'\b' + re.escape(material) + r'\b', text):
                found_materials.append(material)

        return found_materials

    def _extract_style(self, text: str) -> Optional[str]:
        """Extract design style from text"""
        styles = {
            'modern': ['modern', 'contemporary'],
            'traditional': ['traditional', 'classic'],
            'rustic': ['rustic', 'farmhouse'],
            'industrial': ['industrial'],
            'mid-century': ['mid-century', 'mid century', 'mcm'],
            'scandinavian': ['scandinavian', 'nordic'],
            'minimalist': ['minimalist', 'minimalism'],
            'bohemian': ['bohemian', 'boho']
        }

        for style, keywords in styles.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                    return style

        return None

    def _extract_dimensions(self, text: str) -> Dict[str, float]:
        """Extract dimensions from text"""
        dimensions = {}

        # Pattern: 84" W x 36" D x 33" H
        # Pattern: 84 inches wide
        # Pattern: width: 84"

        width_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:"|inches?|in)?\s*(?:w|wide|width)', text, re.IGNORECASE)
        if width_match:
            dimensions['width'] = float(width_match.group(1))

        depth_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:"|inches?|in)?\s*(?:d|deep|depth)', text, re.IGNORECASE)
        if depth_match:
            dimensions['depth'] = float(depth_match.group(1))

        height_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:"|inches?|in)?\s*(?:h|high|height)', text, re.IGNORECASE)
        if height_match:
            dimensions['height'] = float(height_match.group(1))

        return dimensions

    def _extract_texture(self, text: str) -> Optional[str]:
        """Extract texture from text"""
        textures = [
            'smooth', 'rough', 'woven', 'tufted', 'brushed',
            'polished', 'matte', 'glossy', 'textured', 'soft'
        ]

        for texture in textures:
            if re.search(r'\b' + re.escape(texture) + r'\b', text):
                return texture

        return None

    def _extract_pattern(self, text: str) -> Optional[str]:
        """Extract pattern from text"""
        patterns = [
            'solid', 'striped', 'floral', 'geometric', 'abstract',
            'plaid', 'checkered', 'dotted', 'paisley', 'chevron'
        ]

        for pattern in patterns:
            if re.search(r'\b' + re.escape(pattern) + r'\b', text):
                return pattern

        return None


# Global instance (initialized with google_ai_service)
attribute_extraction_service: Optional[AttributeExtractionService] = None


def init_attribute_extraction_service(google_ai_service):
    """Initialize global attribute extraction service"""
    global attribute_extraction_service
    attribute_extraction_service = AttributeExtractionService(google_ai_service)
    return attribute_extraction_service
