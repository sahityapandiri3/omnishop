"""
Curated Styling Service for AI-driven room look generation

This service orchestrates the generation of curated room looks by:
1. Analyzing the room image to detect room type
2. Using AI to define 3 distinct style themes with product requirements
3. Querying products that match the AI-defined attributes
4. Generating visualizations for each look
"""
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from services.chatgpt_service import chatgpt_service
from services.google_ai_service import VisualizationRequest, google_ai_service
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Category, Product, ProductAttribute

logger = logging.getLogger(__name__)


@dataclass
class ProductRequirement:
    """AI-defined requirements for a product category"""

    category: str  # e.g., "sofa", "coffee_table"
    colors: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    styles: List[str] = field(default_factory=list)


@dataclass
class StyleTheme:
    """A curated style theme with product requirements"""

    theme_name: str
    theme_description: str
    color_palette: List[str]
    material_palette: List[str]
    texture_palette: List[str]
    product_requirements: Dict[str, ProductRequirement] = field(default_factory=dict)


@dataclass
class CuratedLook:
    """A complete curated look with products and visualization"""

    look_id: str
    style_theme: str
    style_description: str
    visualization_image: Optional[str] = None
    products: List[Dict[str, Any]] = field(default_factory=list)
    total_price: float = 0.0
    generation_status: str = "pending"  # pending, generating, completed, failed
    error_message: Optional[str] = None


@dataclass
class CuratedLooksResponse:
    """Response containing all curated looks"""

    session_id: str
    room_type: str
    looks: List[CuratedLook] = field(default_factory=list)
    generation_complete: bool = False


class CuratedStylingService:
    """Service for generating AI-curated room looks"""

    # Room-specific product categories
    ROOM_PRODUCTS = {
        "living_room": {
            "primary": ["sofa", "three seater sofa", "two seater sofa"],
            "secondary": ["coffee table", "center table", "rug", "floor rug", "carpet"],
            "accent": ["side table", "planter", "floor lamp", "lounge chair", "accent chair"],
            "optional": ["chandelier", "ceiling lamp", "table lamp"],
        },
        "bedroom": {
            "primary": ["bed", "king bed", "queen bed", "double bed"],
            "secondary": ["nightstand", "side table", "bedside table"],
            "accent": ["table lamp", "floor lamp", "floor rug", "carpet"],
            "optional": ["dresser", "wardrobe"],
        },
        "dining_room": {
            "primary": ["dining table"],
            "secondary": ["dining chair"],
            "accent": ["sideboard", "buffet", "chandelier"],
            "optional": ["floor rug", "cabinet"],
        },
        "office": {
            "primary": ["desk", "study_table", "office chair", "study_chair"],
            "secondary": ["bookshelf", "shelves"],
            "accent": ["table lamp", "floor lamp"],
            "optional": ["cabinet", "storage"],
        },
        "study": {
            "primary": ["study_table", "desk", "study_chair", "office chair"],
            "secondary": ["bookshelf", "shelves"],
            "accent": ["table lamp", "floor lamp"],
            "optional": ["cabinet", "storage"],
        },
    }

    # Category name mappings for DB queries
    # NOTE: For sofas, we EXCLUDE single seater as it's not suitable as primary seating
    # Single seaters should only be used as accent chairs
    CATEGORY_MAPPINGS = {
        "sofa": ["three seater sofa", "two seater sofa", "sectional sofa", "sofa"],  # Prioritize larger sofas first
        "three_seater_sofa": ["three seater sofa", "sectional sofa"],
        "two_seater_sofa": ["two seater sofa"],
        "single_seater_sofa": ["single seater sofa"],  # Only for accent/secondary seating
        "coffee_table": ["coffee table", "center table"],
        "center_table": ["coffee table", "center table"],
        "side_table": ["side table", "end table", "nightstand"],
        "rug": ["rug", "floor rug", "carpet"],
        "floor_rug": ["rug", "floor rug", "carpet"],
        "lamp": ["lamp", "floor lamp", "table lamp"],
        "floor_lamp": ["floor lamp", "lamp"],
        "table_lamp": ["table lamp", "lamp"],
        "chair": ["accent chair", "lounge chair", "armchair"],  # Removed generic "chair" to avoid dining chairs
        "lounge_chair": ["lounge chair", "accent chair", "armchair"],
        "accent_chair": ["accent chair", "lounge chair", "armchair", "single seater sofa"],  # Single seater can be accent
        "planter": ["planter", "vase"],
        "chandelier": ["chandelier", "ceiling light", "pendant lamp"],
        "bed": ["bed", "king bed", "queen bed", "double bed", "single bed"],
        "nightstand": ["nightstand", "bedside table", "side table"],
        "dining_table": ["dining table", "table"],
        "dining_chair": ["dining chair", "chair"],
        "desk": ["desk", "study table", "study tables", "table"],
        "office_chair": ["office chair", "study chair", "study chairs", "chair"],
        "study_table": ["study table", "study tables", "desk"],
        "study_chair": ["study chair", "study chairs", "office chair", "chair"],
        "bookshelf": ["bookshelf", "shelves", "shelf"],
    }

    def __init__(self):
        logger.info("CuratedStylingService initialized")

    async def generate_curated_looks(
        self, room_image: str, selected_stores: List[str], db: AsyncSession, num_looks: int = 3
    ) -> CuratedLooksResponse:
        """
        Generate curated room looks with AI-selected products.

        Args:
            room_image: Base64-encoded room image
            selected_stores: List of store names to filter products
            db: Database session
            num_looks: Number of looks to generate (default 3)

        Returns:
            CuratedLooksResponse with generated looks
        """
        session_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(f"Starting curated looks generation - session: {session_id}, stores: {selected_stores}")

        try:
            # Step 1: Detect room type using Google AI
            room_analysis = await google_ai_service.analyze_room_image(room_image)
            room_type = self._normalize_room_type(room_analysis.room_type)
            logger.info(f"Detected room type: {room_type}")

            # Step 2: Generate style themes with product requirements using ChatGPT
            style_themes = await self._generate_style_themes(room_image, room_type, num_looks)
            logger.info(f"Generated {len(style_themes)} style themes")

            # Step 3: For each theme, select products and generate visualization
            looks = []
            # Track products used across ALL looks to ensure each look has unique products
            globally_used_product_ids: Set[int] = set()

            for idx, theme in enumerate(style_themes):
                look_id = str(uuid.uuid4())
                look = CuratedLook(
                    look_id=look_id,
                    style_theme=theme.theme_name,
                    style_description=theme.theme_description,
                    generation_status="generating",
                )

                try:
                    # Select products for this theme, excluding products already used in other looks
                    products = await self._select_products_for_theme(
                        theme, room_type, selected_stores, db, exclude_product_ids=globally_used_product_ids
                    )
                    look.products = products
                    look.total_price = sum(p.get("price", 0) or 0 for p in products)

                    # Add these products to global exclusion set for subsequent looks
                    for p in products:
                        if p.get("id"):
                            globally_used_product_ids.add(p["id"])

                    logger.info(f"Look {idx+1}: Selected {len(products)} products, total: ₹{look.total_price:,.0f}")

                    # Generate visualization if we have products
                    if products:
                        visualization = await self._generate_look_visualization(room_image, products, theme)
                        look.visualization_image = visualization
                        look.generation_status = "completed"
                    else:
                        look.generation_status = "failed"
                        look.error_message = "No matching products found"

                except Exception as e:
                    logger.error(f"Error generating look {idx+1}: {e}")
                    look.generation_status = "failed"
                    look.error_message = str(e)

                looks.append(look)

            elapsed = time.time() - start_time
            logger.info(f"Curated looks generation completed in {elapsed:.2f}s")

            return CuratedLooksResponse(session_id=session_id, room_type=room_type, looks=looks, generation_complete=True)

        except Exception as e:
            logger.error(f"Error in generate_curated_looks: {e}", exc_info=True)
            return CuratedLooksResponse(session_id=session_id, room_type="unknown", looks=[], generation_complete=True)

    def _normalize_room_type(self, detected_type: str) -> str:
        """Normalize room type to match our category mappings"""
        detected_lower = detected_type.lower().replace(" ", "_")

        # Map variations to standard types
        room_type_map = {
            "living": "living_room",
            "living_room": "living_room",
            "lounge": "living_room",
            "family_room": "living_room",
            "bedroom": "bedroom",
            "master_bedroom": "bedroom",
            "guest_bedroom": "bedroom",
            "dining": "dining_room",
            "dining_room": "dining_room",
            "office": "office",
            "home_office": "office",
            "study": "office",
        }

        return room_type_map.get(detected_lower, "living_room")

    async def _generate_style_themes(self, room_image: str, room_type: str, num_themes: int) -> List[StyleTheme]:
        """
        Use ChatGPT to analyze room and generate distinct style themes with product requirements.

        This is the key AI call that defines what products to select for each look.
        """
        # Get product categories for this room type
        room_products = self.ROOM_PRODUCTS.get(room_type, self.ROOM_PRODUCTS["living_room"])
        all_categories = room_products["primary"] + room_products["secondary"] + room_products["accent"]

        # Build the AI prompt
        prompt = f"""Analyze this {room_type.replace('_', ' ')} image and create {num_themes} DISTINCT interior design style themes.

For EACH theme, provide specific product requirements that will create a cohesive, complementary look.
Products should work together aesthetically - like a real interior stylist would select them.

Room Type: {room_type.replace('_', ' ')}

Product Categories to Define: {', '.join(all_categories[:6])}

Return JSON with this EXACT structure:
{{
  "room_analysis": {{
    "current_colors": ["dominant wall/floor colors"],
    "architectural_style": "modern/traditional/etc",
    "natural_light": "good/moderate/limited",
    "room_size": "small/medium/large"
  }},
  "looks": [
    {{
      "theme_name": "Modern Warmth",
      "theme_description": "Clean contemporary lines with warm, inviting tones that complement the space",
      "color_palette": ["warm beige", "soft gray", "brass accents", "cream"],
      "material_palette": ["velvet", "light oak wood", "marble", "brass"],
      "texture_palette": ["soft", "smooth", "natural grain"],
      "products": {{
        "sofa": {{
          "colors": ["beige", "cream", "light gray"],
          "materials": ["velvet", "linen", "fabric"],
          "styles": ["modern", "contemporary", "minimalist"]
        }},
        "coffee_table": {{
          "colors": ["white", "light wood", "marble"],
          "materials": ["marble", "oak", "wood"],
          "styles": ["modern", "scandinavian"]
        }},
        "rug": {{
          "colors": ["beige", "cream", "warm gray"],
          "materials": ["wool", "jute", "cotton"],
          "styles": ["textured", "natural"]
        }},
        "floor_lamp": {{
          "colors": ["brass", "gold", "black"],
          "materials": ["metal", "brass"],
          "styles": ["modern", "sculptural"]
        }},
        "side_table": {{
          "colors": ["light wood", "white", "brass"],
          "materials": ["wood", "marble", "metal"],
          "styles": ["modern", "minimalist"]
        }},
        "planter": {{
          "colors": ["white", "terracotta", "natural"],
          "materials": ["ceramic", "terracotta", "concrete"],
          "styles": ["modern", "organic"]
        }}
      }}
    }}
  ]
}}

IMPORTANT RULES:
1. Each theme must be DISTINCT (e.g., Modern Warmth vs Cozy Traditional vs Minimalist Zen)
2. Products within a theme must COMPLEMENT each other aesthetically
3. Colors should create a cohesive palette across all products
4. Consider the room's existing colors and architecture
5. For "colors", use simple color terms that match product attributes (e.g., "beige", "brown", "gray", "white", "black", "blue")
6. For "materials", use common furniture materials (e.g., "wood", "metal", "fabric", "leather", "marble", "velvet", "glass")
7. For "styles", use design style terms (e.g., "modern", "contemporary", "traditional", "minimalist", "scandinavian", "industrial")
"""

        try:
            # Call ChatGPT for style theme generation
            response, _ = await chatgpt_service.analyze_user_input(
                user_message=prompt, image_data=room_image, session_id=None  # One-off analysis, no session needed
            )

            # Parse the JSON response
            themes = self._parse_style_themes_response(response)

            if not themes:
                logger.warning("Failed to parse AI response, using default themes")
                themes = self._get_default_themes(num_themes)

            return themes

        except Exception as e:
            logger.error(f"Error generating style themes: {e}")
            return self._get_default_themes(num_themes)

    def _parse_style_themes_response(self, response: str) -> List[StyleTheme]:
        """Parse ChatGPT response into StyleTheme objects"""
        try:
            # Try to extract JSON from response
            # ChatGPT might wrap JSON in markdown code blocks
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str)
            looks = data.get("looks", [])

            themes = []
            for look in looks:
                product_requirements = {}
                products = look.get("products", {})

                for category, reqs in products.items():
                    product_requirements[category] = ProductRequirement(
                        category=category,
                        colors=reqs.get("colors", []),
                        materials=reqs.get("materials", []),
                        styles=reqs.get("styles", []),
                    )

                theme = StyleTheme(
                    theme_name=look.get("theme_name", "Modern Style"),
                    theme_description=look.get("theme_description", "A contemporary look"),
                    color_palette=look.get("color_palette", []),
                    material_palette=look.get("material_palette", []),
                    texture_palette=look.get("texture_palette", []),
                    product_requirements=product_requirements,
                )
                themes.append(theme)

            return themes

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse style themes JSON: {e}")
            return []

    def _get_default_themes(self, num_themes: int) -> List[StyleTheme]:
        """Return default style themes as fallback"""
        default_themes = [
            StyleTheme(
                theme_name="Modern Elegance",
                theme_description="Clean lines with warm, sophisticated tones",
                color_palette=["beige", "cream", "gray", "brass"],
                material_palette=["velvet", "wood", "marble"],
                texture_palette=["soft", "smooth"],
                product_requirements={
                    "sofa": ProductRequirement("sofa", ["beige", "gray", "cream"], ["fabric", "velvet"], ["modern"]),
                    "coffee_table": ProductRequirement("coffee_table", ["brown", "white"], ["wood", "marble"], ["modern"]),
                    "rug": ProductRequirement("rug", ["beige", "gray"], ["wool"], ["modern"]),
                    "floor_lamp": ProductRequirement("floor_lamp", ["black", "gold"], ["metal"], ["modern"]),
                },
            ),
            StyleTheme(
                theme_name="Cozy Traditional",
                theme_description="Warm, inviting space with classic elements",
                color_palette=["brown", "cream", "burgundy", "gold"],
                material_palette=["leather", "wood", "fabric"],
                texture_palette=["textured", "plush"],
                product_requirements={
                    "sofa": ProductRequirement("sofa", ["brown", "burgundy", "cream"], ["leather", "fabric"], ["traditional"]),
                    "coffee_table": ProductRequirement("coffee_table", ["brown", "dark wood"], ["wood"], ["traditional"]),
                    "rug": ProductRequirement("rug", ["red", "brown", "cream"], ["wool"], ["traditional"]),
                    "floor_lamp": ProductRequirement("floor_lamp", ["bronze", "gold"], ["metal"], ["traditional"]),
                },
            ),
            StyleTheme(
                theme_name="Minimalist Zen",
                theme_description="Simple, calming space with natural elements",
                color_palette=["white", "light gray", "natural wood", "green"],
                material_palette=["wood", "cotton", "ceramic"],
                texture_palette=["smooth", "natural"],
                product_requirements={
                    "sofa": ProductRequirement("sofa", ["white", "light gray", "beige"], ["linen", "cotton"], ["minimalist"]),
                    "coffee_table": ProductRequirement(
                        "coffee_table", ["light wood", "white"], ["wood"], ["minimalist", "scandinavian"]
                    ),
                    "rug": ProductRequirement("rug", ["white", "natural", "beige"], ["jute", "cotton"], ["minimalist"]),
                    "planter": ProductRequirement("planter", ["white", "natural"], ["ceramic"], ["minimalist"]),
                },
            ),
        ]

        return default_themes[:num_themes]

    async def _select_products_for_theme(
        self,
        theme: StyleTheme,
        room_type: str,
        selected_stores: List[str],
        db: AsyncSession,
        exclude_product_ids: Optional[Set[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Select products that match the theme's requirements.
        Runs queries sequentially to avoid SQLAlchemy concurrency issues.

        Args:
            exclude_product_ids: Set of product IDs to exclude (already used in other looks)
        """
        room_products = self.ROOM_PRODUCTS.get(room_type, self.ROOM_PRODUCTS["living_room"])

        # Determine which categories to fill (primary + secondary + some accent)
        categories_to_fill = (
            room_products["primary"][:1]
            + room_products["secondary"][:2]  # 1 primary item
            + room_products["accent"][:2]  # 2 secondary items  # 2 accent items
        )

        # Collect successful results
        products = []
        # Start with globally excluded products + products selected in this look
        seen_ids = set(exclude_product_ids) if exclude_product_ids else set()

        # Run queries sequentially to avoid concurrent session issues
        for category in categories_to_fill:
            # Normalize category name for requirements lookup
            category_key = category.lower().replace(" ", "_")

            # Get requirements for this category (or use theme defaults)
            requirements = theme.product_requirements.get(category_key)
            if not requirements:
                # Try without underscores
                for key in theme.product_requirements:
                    if key.replace("_", " ") == category.lower() or key == category.lower():
                        requirements = theme.product_requirements[key]
                        break

            if not requirements:
                # Create default requirements from theme palette
                requirements = ProductRequirement(
                    category=category,
                    colors=theme.color_palette[:3] if theme.color_palette else ["neutral"],
                    materials=theme.material_palette[:3] if theme.material_palette else ["wood", "fabric"],
                    styles=["modern", "contemporary"],
                )

            try:
                result = await self._get_product_for_category(
                    category, requirements, selected_stores, db, exclude_product_ids=seen_ids
                )
                if result and result.get("id") not in seen_ids:
                    products.append(result)
                    seen_ids.add(result.get("id"))
            except Exception as e:
                logger.warning(f"Product query failed for {category}: {e}")
                continue

        return products

    async def _get_product_for_category(
        self,
        category: str,
        requirements: ProductRequirement,
        selected_stores: List[str],
        db: AsyncSession,
        exclude_product_ids: Optional[Set[int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single product for a category that matches requirements.

        Strategy:
        1. Try attribute-based query (fast, precise)
        2. Fallback: Get shortlist and let AI pick

        Args:
            exclude_product_ids: Set of product IDs to exclude (already used)
        """
        # Get category names to search
        category_names = self.CATEGORY_MAPPINGS.get(category.lower().replace(" ", "_"), [category])

        # Check if this is a primary sofa search - exclude single-seaters
        # Single seaters should only be used as accent pieces, not primary seating
        is_primary_sofa = category.lower() in ["sofa", "three seater sofa", "two seater sofa"]
        exclude_single_seater = is_primary_sofa

        # Try primary method: attribute-based query
        product = await self._query_by_attributes(
            category_names,
            requirements,
            selected_stores,
            db,
            exclude_single_seater=exclude_single_seater,
            exclude_product_ids=exclude_product_ids,
        )

        if product:
            return product

        # Fallback: get shortlist and pick best match
        logger.info(f"No attribute match for {category}, using fallback")
        shortlist = await self._get_product_shortlist(
            category_names,
            selected_stores,
            db,
            limit=10,
            exclude_single_seater=exclude_single_seater,
            exclude_product_ids=exclude_product_ids,
        )

        if not shortlist:
            logger.warning(f"No products found for category: {category}")
            return None

        # For now, pick the first available product from shortlist
        # TODO: Add AI-based selection from shortlist
        return shortlist[0]

    async def _query_by_attributes(
        self,
        category_names: List[str],
        requirements: ProductRequirement,
        selected_stores: List[str],
        db: AsyncSession,
        exclude_single_seater: bool = False,
        exclude_product_ids: Optional[Set[int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Query products by matching attributes (color, material, style).
        Returns the BEST matching product based on attribute score.

        The ProductAttribute model uses a name-value pattern:
        - attribute_name: "color", "material", "style", etc.
        - attribute_value: the actual value

        Args:
            exclude_product_ids: Set of product IDs to exclude (already used)
        """
        try:
            # Build base conditions
            base_conditions = [
                # Category filter
                func.lower(Category.name).in_([c.lower() for c in category_names]),
                # Availability
                Product.is_available.is_(True),
            ]

            # Store filter
            if selected_stores:
                base_conditions.append(Product.source_website.in_(selected_stores))

            # Exclude single seater sofas when searching for primary seating
            if exclude_single_seater:
                base_conditions.append(~func.lower(Category.name).like("%single seater%"))
                base_conditions.append(~func.lower(Product.name).like("%single seater%"))

            # Exclude products already used in other looks
            if exclude_product_ids:
                base_conditions.append(~Product.id.in_(exclude_product_ids))

            # Build the query - get products with their attributes
            query = (
                select(Product)
                .join(Category, Product.category_id == Category.id)
                .where(and_(*base_conditions))
                .options(
                    selectinload(Product.category),
                    selectinload(Product.images),
                    selectinload(Product.attributes),  # Load attributes for scoring
                )
                .limit(30)  # Get candidates for scoring
            )

            result = await db.execute(query)
            products = result.scalars().all()

            if not products:
                return None

            # Score each product based on how well its attributes match requirements
            scored_products = []
            for product in products:
                # Convert attributes list to dict for easier access
                attrs_dict = self._attributes_to_dict(product.attributes)
                score = self._calculate_attribute_match_score(attrs_dict, requirements)
                scored_products.append((product, score))

            # Sort by score (highest first), then by price (mid-range preferred)
            scored_products.sort(key=lambda x: (-x[1], abs((x[0].price or 0) - 50000)))

            best_product = scored_products[0][0]
            best_score = scored_products[0][1]

            logger.info(f"Selected product '{best_product.name}' with match score {best_score:.2f}")

            return self._product_to_dict(best_product)

        except Exception as e:
            logger.error(f"Error in attribute query: {e}")
            return None

    def _attributes_to_dict(self, attributes: List[ProductAttribute]) -> Dict[str, str]:
        """
        Convert ProductAttribute list to a dictionary.
        Groups by attribute_name, combining multiple values if needed.
        """
        if not attributes:
            return {}

        result = {}
        for attr in attributes:
            name = attr.attribute_name.lower()
            value = attr.attribute_value or ""

            # Map various attribute names to standard keys
            if name in ("color", "colour", "primary_color", "color_primary"):
                key = "color"
            elif name in ("material", "materials", "primary_material", "material_primary"):
                key = "material"
            elif name in ("style", "design_style", "furniture_style"):
                key = "style"
            else:
                key = name

            # Combine values if same key appears multiple times
            if key in result:
                result[key] = f"{result[key]}, {value}"
            else:
                result[key] = value

        return result

    def _calculate_attribute_match_score(self, attrs_dict: Dict[str, str], requirements: ProductRequirement) -> float:
        """
        Calculate how well a product's attributes match the requirements.
        Returns a score from 0.0 to 1.0.

        Args:
            attrs_dict: Dictionary of attribute_name -> attribute_value
            requirements: ProductRequirement with colors, materials, styles lists
        """
        if not attrs_dict:
            return 0.1  # Minimal score for products without attributes

        score = 0.0
        max_score = 0.0

        # Color match (weight: 0.4)
        if requirements.colors:
            max_score += 0.4
            color_value = attrs_dict.get("color", "").lower()
            if color_value:
                for req_color in requirements.colors:
                    if req_color.lower() in color_value or color_value in req_color.lower():
                        score += 0.4
                        break

        # Material match (weight: 0.35)
        if requirements.materials:
            max_score += 0.35
            material_value = attrs_dict.get("material", "").lower()
            if material_value:
                for req_material in requirements.materials:
                    if req_material.lower() in material_value or material_value in req_material.lower():
                        score += 0.35
                        break

        # Style match (weight: 0.25)
        if requirements.styles:
            max_score += 0.25
            style_value = attrs_dict.get("style", "").lower()
            if style_value:
                for req_style in requirements.styles:
                    if req_style.lower() in style_value or style_value in req_style.lower():
                        score += 0.25
                        break

        # Normalize score
        return score / max_score if max_score > 0 else 0.5

    async def _get_product_shortlist(
        self,
        category_names: List[str],
        selected_stores: List[str],
        db: AsyncSession,
        limit: int = 10,
        exclude_single_seater: bool = False,
        exclude_product_ids: Optional[Set[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get a shortlist of products for a category without attribute filtering.

        Args:
            exclude_product_ids: Set of product IDs to exclude (already used)
        """
        try:
            # Build base conditions
            base_conditions = [
                func.lower(Category.name).in_([c.lower() for c in category_names]),
                Product.is_available.is_(True),
            ]

            if selected_stores:
                base_conditions.append(Product.source_website.in_(selected_stores))

            # Exclude single seater sofas when searching for primary seating
            if exclude_single_seater:
                base_conditions.append(~func.lower(Category.name).like("%single seater%"))
                base_conditions.append(~func.lower(Product.name).like("%single seater%"))

            # Exclude products already used in other looks
            if exclude_product_ids:
                base_conditions.append(~Product.id.in_(exclude_product_ids))

            query = (
                select(Product)
                .join(Category, Product.category_id == Category.id)
                .where(and_(*base_conditions))
                .options(
                    selectinload(Product.category),
                    selectinload(Product.images),  # Load images for _product_to_dict
                )
                .order_by(func.random())
                .limit(limit)
            )

            result = await db.execute(query)
            products = result.scalars().all()

            return [self._product_to_dict(p) for p in products]

        except Exception as e:
            logger.error(f"Error getting shortlist: {e}")
            return []

    def _product_to_dict(self, product: Product) -> Dict[str, Any]:
        """Convert Product model to dictionary for API response"""
        # Get image URL from images relationship
        image_url = None
        if hasattr(product, "images") and product.images:
            primary_image = next((img for img in product.images if img.is_primary), None)
            if primary_image:
                image_url = primary_image.original_url or primary_image.large_url or primary_image.medium_url
            elif product.images:
                image_url = product.images[0].original_url or product.images[0].large_url

        return {
            "id": product.id,
            "name": product.name,
            "price": float(product.price) if product.price else 0,
            "image_url": image_url,
            "source_website": product.source_website,
            "source_url": product.source_url,
            "product_type": product.category.name if product.category else "furniture",
            "description": product.description,
        }

    async def _generate_look_visualization(
        self, room_image: str, products: List[Dict[str, Any]], theme: StyleTheme
    ) -> Optional[str]:
        """
        Generate a visualization of the room with the selected products.
        """
        try:
            if not products:
                return None

            # Prepare products for visualization
            products_to_place = [
                {
                    "name": p.get("name", "furniture item"),
                    "full_name": p.get("name", "furniture item"),
                    "image_url": p.get("image_url"),
                    "description": p.get("description", ""),
                }
                for p in products
            ]

            # Create visualization request
            viz_request = VisualizationRequest(
                base_image=room_image,
                products_to_place=products_to_place,
                placement_positions=[],  # Let AI determine positions
                lighting_conditions="natural",
                render_quality="high",
                style_consistency=True,
                user_style_description=f"{theme.theme_name}: {theme.theme_description}",
            )

            # Generate visualization
            result = await google_ai_service.generate_room_visualization(viz_request)

            if result and result.rendered_image:
                return result.rendered_image

            return None

        except Exception as e:
            logger.error(f"Error generating visualization: {e}")
            return None


# Global service instance
curated_styling_service = CuratedStylingService()
