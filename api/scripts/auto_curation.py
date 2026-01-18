"""
Auto Curation Script - Automatically generate curated looks for Omnishop.

Generates 12 curated looks (3 styles x 4 budget tiers x 1 look each) with:
- Automated product selection based on style and budget
- AI-generated visualizations using Google AI Studio
- Database persistence with review workflow

Usage:
    python auto_curation.py                      # Generate all 12 looks
    python auto_curation.py --dry-run            # Preview without saving
    python auto_curation.py --style modern       # Generate only modern style
    python auto_curation.py --tier premium       # Generate only premium tier
    python auto_curation.py --skip-visualization # Skip AI visualization
"""

import argparse
import asyncio
import base64
import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from services.google_ai_service import GoogleAIStudioService  # noqa: E402
from sqlalchemy import func, or_  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database.connection import get_db_session  # noqa: E402
from database.models import Category, CuratedLook, CuratedLookProduct, Product, ProductAttribute, ProductImage  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"/Users/sahityapandiri/Omnishop/api/scripts/auto_curation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
    ],
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

STYLE_CONFIGS = {
    "modern": {
        "style_theme": "Modern",
        "style_labels": ["modern"],
        "search_keywords": ["modern", "contemporary", "minimalist", "sleek"],
        "primary_styles": ["modern", "contemporary", "minimalist"],
        "colors": ["gray", "white", "black", "beige", "charcoal"],
        "materials": ["metal", "glass", "leather", "fabric", "chrome"],
    },
    "modern_luxury": {
        "style_theme": "Modern Luxury",
        "style_labels": ["modern_luxury"],
        "search_keywords": ["luxury", "premium", "elegant", "sophisticated"],
        "primary_styles": ["luxury", "modern", "elegant", "premium"],
        "colors": ["gold", "cream", "white", "navy", "emerald", "burgundy"],
        "materials": ["velvet", "brass", "marble", "leather", "silk"],
    },
    "indian_contemporary": {
        "style_theme": "Indian Contemporary",
        "style_labels": ["indian_contemporary"],
        "search_keywords": ["indian", "ethnic", "traditional", "handcrafted"],
        "primary_styles": ["traditional", "ethnic", "indian", "artisan"],
        "colors": ["brown", "gold", "red", "orange", "green", "terracotta"],
        "materials": ["wood", "brass", "fabric", "jute", "cotton", "cane"],
    },
}

BUDGET_TIERS = {
    "pocket_friendly": {"min": 0, "max": 199999, "target": 150000},
    "mid_tier": {"min": 200000, "max": 799999, "target": 500000},
    "premium": {"min": 800000, "max": 1499999, "target": 1100000},
    "luxury": {"min": 1500000, "max": 10000000, "target": 2000000},
}

# Budget allocation percentages for each product type (12 required products)
BUDGET_ALLOCATION = {
    "sofa": 0.25,
    "accent_chair": 0.10,
    "rugs": 0.10,
    "coffee_table": 0.08,
    "ceiling_lamp": 0.06,
    "floor_lamp": 0.05,
    "side_table": 0.06,
    "wall_art": 0.05,
    "throw": 0.04,
    "planter": 0.04,
    "bookshelf": 0.10,
    "cushion": 0.03,
}

# Required products per look (12 types max)
REQUIRED_PRODUCTS = [
    {
        "type": "sofa",
        "categories": ["sofas", "three seater sofa", "sectional sofa", "sofa"],
        "search_terms": ["sofa", "couch"],
    },
    {
        "type": "accent_chair",
        "categories": ["accent chairs", "lounge chair", "armchair", "accent chair"],
        "search_terms": ["accent chair", "lounge chair", "armchair"],
        "quantity_range": (1, 2),
    },
    {
        "type": "coffee_table",
        "categories": ["coffee tables", "center table", "coffee table"],
        "search_terms": ["coffee table", "center table"],
    },
    {
        "type": "side_table",
        "categories": ["side tables", "end table", "side table"],
        "search_terms": ["side table", "end table"],
    },
    {
        "type": "wall_art",
        "categories": ["wall art", "paintings", "artwork", "wall decor"],
        "search_terms": ["wall art", "painting", "artwork"],
    },
    {
        "type": "rugs",
        "categories": ["rugs", "carpets", "floor rug", "area rug"],
        "search_terms": ["rug", "carpet"],
    },
    {
        "type": "floor_lamp",
        "categories": ["floor lamps", "standing lamp", "floor lamp"],
        "search_terms": ["floor lamp", "standing lamp"],
    },
    {
        "type": "ceiling_lamp",
        "categories": ["chandeliers", "ceiling lights", "pendant", "chandelier"],
        "search_terms": ["chandelier", "ceiling light", "pendant lamp"],
    },
    {
        "type": "throw",
        "categories": ["Throw", "throws"],  # Never use blanket for throws
        "search_terms": ["throw"],
    },
    {
        "type": "planter",
        "categories": ["planters", "pots", "plant pot", "planter"],
        "search_terms": ["planter", "pot"],
    },
    {
        "type": "bookshelf",
        "categories": ["bookshelves", "shelves", "bookshelf", "bookcase"],
        "search_terms": ["bookshelf", "shelf", "bookcase"],
    },
    {
        "type": "cushion",
        "categories": ["Cushion", "Cushion Cover", "cushions", "pillows", "throw pillow", "cushion covers"],
        "search_terms": ["cushion", "pillow"],
    },
]

# Optional products (NOT used - decor_accents and table_lamp skipped)
OPTIONAL_PRODUCTS = [
    {
        "type": "decor_accents",
        "categories": ["decor", "accents", "home decor", "decorative"],
        "search_terms": ["decor", "accent"],
    },
    {
        "type": "table_lamp",
        "categories": ["table lamps", "desk lamp", "table lamp"],
        "search_terms": ["table lamp"],
    },
]

# Base images directory (cleaned images with furniture removed)
BASE_IMAGES_DIR = Path("/Users/sahityapandiri/Omnishop/Base_Images/cleaned")
ROOM_ANALYSIS_FILE = BASE_IMAGES_DIR / "room_analysis.json"


# =============================================================================
# PRODUCT SELECTOR
# =============================================================================


class ProductSelector:
    """Selects products for a curated look based on style and budget."""

    def __init__(
        self,
        db: Session,
        style_config: Dict,
        budget_tier: str,
        used_product_ids: Set[int],
    ):
        self.db = db
        self.style_config = style_config
        self.budget_tier = budget_tier
        self.budget_config = BUDGET_TIERS[budget_tier]
        self.used_product_ids = used_product_ids
        self.selected_product_ids: Set[int] = set()

    def select_products_for_look(self) -> Dict[str, List[Dict]]:
        """
        Select all products for a single curated look.
        Returns dict mapping product_type to list of product dicts.
        """
        selected = {}
        target_total = self.budget_config["target"]

        # Select required products
        for product_spec in REQUIRED_PRODUCTS:
            product_type = product_spec["type"]
            allocation = BUDGET_ALLOCATION.get(product_type, 0.05)
            max_price = target_total * allocation * 1.5  # Allow 50% buffer

            # Handle accent chairs (1-2 quantity)
            if product_spec.get("quantity_range"):
                quantity = random.randint(*product_spec["quantity_range"])
            else:
                quantity = 1

            products = self._select_products_for_category(product_spec, max_price_per_item=max_price, quantity=quantity)

            if products:
                selected[product_type] = products
                for p in products:
                    self.selected_product_ids.add(p["id"])
            else:
                logger.warning(
                    f"Could not find product for {product_type} in {self.style_config['style_theme']}/{self.budget_tier}"
                )

        # Skip optional products (decor_accents, table_lamp) - only use required products
        # All 12 required product types are sufficient for a complete look

        return selected

    def _select_products_for_category(self, product_spec: Dict, max_price_per_item: float, quantity: int = 1) -> List[Dict]:
        """Select products for a specific category."""
        category_names = product_spec["categories"]

        # Find matching categories
        categories = self.db.query(Category).filter(func.lower(Category.name).in_([c.lower() for c in category_names])).all()
        category_ids = [c.id for c in categories]

        if not category_ids:
            # Try slug matching
            categories = (
                self.db.query(Category)
                .filter(func.lower(Category.slug).in_([c.lower().replace(" ", "_") for c in category_names]))
                .all()
            )
            category_ids = [c.id for c in categories]

        if not category_ids:
            logger.warning(f"No categories found for: {category_names}")
            return []

        # Build base query
        query = self.db.query(Product).filter(
            Product.category_id.in_(category_ids),
            Product.is_available.is_(True),
            Product.price.isnot(None),
            Product.price > 0,
            Product.price <= max_price_per_item,
            ~Product.id.in_(self.used_product_ids),
            ~Product.id.in_(self.selected_product_ids),
        )

        # Filter by style preference (soft filter - prefer but don't require)
        primary_styles = self.style_config.get("primary_styles", [])
        if primary_styles:
            # Try with style filter first
            style_query = query.filter(
                or_(
                    func.lower(Product.primary_style).in_([s.lower() for s in primary_styles]),
                    Product.primary_style.is_(None),
                )
            )
            candidates = style_query.all()

            # Fall back to all products if no style matches
            if not candidates:
                candidates = query.all()
        else:
            candidates = query.all()

        if not candidates:
            logger.warning(f"No products found for {product_spec['type']} under ₹{max_price_per_item:,.0f}")
            # Try without price filter as fallback
            candidates = (
                self.db.query(Product)
                .filter(
                    Product.category_id.in_(category_ids),
                    Product.is_available.is_(True),
                    Product.price.isnot(None),
                    ~Product.id.in_(self.used_product_ids),
                    ~Product.id.in_(self.selected_product_ids),
                )
                .order_by(Product.price)
                .limit(20)
                .all()
            )

        if not candidates:
            return []

        # Score and select products
        scored = self._score_products(candidates)
        scored.sort(key=lambda x: x[1], reverse=True)

        # Select top candidates
        selected = []
        for product, score in scored[:quantity]:
            selected.append(self._product_to_dict(product))

        return selected

    def _score_products(self, products: List[Product]) -> List[Tuple[Product, float]]:
        """Score products based on style matching."""
        scored = []
        style_keywords = self.style_config.get("search_keywords", [])
        materials = self.style_config.get("materials", [])
        colors = self.style_config.get("colors", [])

        for product in products:
            score = 0.0

            # Style match (40%)
            if product.primary_style:
                if product.primary_style.lower() in [s.lower() for s in self.style_config.get("primary_styles", [])]:
                    score += 40

            # Name/description keyword match (30%)
            name_lower = product.name.lower()
            desc_lower = (product.description or "").lower()
            for keyword in style_keywords:
                if keyword.lower() in name_lower or keyword.lower() in desc_lower:
                    score += 10

            # Material match (15%)
            for material in materials:
                if material.lower() in name_lower or material.lower() in desc_lower:
                    score += 5

            # Color match (10%)
            for color in colors:
                if color.lower() in name_lower:
                    score += 3

            # Add randomness to avoid always picking the same products (5%)
            score += random.uniform(0, 5)

            scored.append((product, score))

        return scored

    def _product_to_dict(self, product: Product) -> Dict:
        """Convert Product to dict with all needed fields."""
        # Get images
        images = (
            self.db.query(ProductImage)
            .filter(ProductImage.product_id == product.id)
            .order_by(ProductImage.is_primary.desc())
            .limit(3)
            .all()
        )
        image_urls = [img.original_url for img in images]

        # Get dimensions
        attrs = (
            self.db.query(ProductAttribute)
            .filter(
                ProductAttribute.product_id == product.id,
                ProductAttribute.attribute_name.in_(["width", "height", "depth", "diameter"]),
            )
            .all()
        )
        dimensions = {}
        for attr in attrs:
            try:
                dimensions[attr.attribute_name] = float(attr.attribute_value)
            except (ValueError, TypeError):
                pass

        return {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "source_website": product.source_website,
            "image_url": image_urls[0] if image_urls else None,
            "images": image_urls,
            "dimensions": dimensions,
        }

    def calculate_total_price(self, selected_products: Dict[str, List[Dict]]) -> float:
        """Calculate total price of all selected products."""
        total = 0.0
        for products in selected_products.values():
            for product in products:
                total += product.get("price", 0) or 0
        return total


# =============================================================================
# LOOK GENERATOR
# =============================================================================


class LookGenerator:
    """Generates curated looks with visualizations."""

    def __init__(self, dry_run: bool = False, skip_visualization: bool = False):
        self.dry_run = dry_run
        self.skip_visualization = skip_visualization
        self.google_ai = GoogleAIStudioService() if not skip_visualization else None
        self.used_product_ids: Set[int] = set()
        self.used_titles: Set[str] = set()
        self.base_images = []  # Will be loaded when db session is available
        self._base_images_loaded = False
        self._existing_data_loaded = False

    def _load_existing_product_ids(self, db: Session) -> Set[int]:
        """Load product IDs already used in existing looks (ID >= 45)."""
        existing = (
            db.query(CuratedLookProduct.product_id)
            .join(CuratedLook, CuratedLookProduct.curated_look_id == CuratedLook.id)
            .filter(CuratedLook.id >= 45)
            .distinct()
            .all()
        )

        product_ids = {p[0] for p in existing}
        logger.info(f"Loaded {len(product_ids)} existing product IDs to avoid duplicates")
        return product_ids

    def _load_existing_titles(self, db: Session) -> Set[str]:
        """Load titles already used in existing looks (ID >= 45)."""
        existing = db.query(CuratedLook.title).filter(CuratedLook.id >= 45).all()
        titles = {t[0] for t in existing}
        logger.info(f"Loaded {len(titles)} existing titles to avoid duplicates")
        return titles

    def _load_base_images(self, db: Session = None) -> List[Dict]:
        """Load base room images from cleaned folder AND existing manual curated looks."""
        images = []

        # Load room analysis data if available
        room_analysis_data = {}
        if ROOM_ANALYSIS_FILE.exists():
            try:
                with open(ROOM_ANALYSIS_FILE, "r") as f:
                    analysis_list = json.load(f)
                    for item in analysis_list:
                        room_analysis_data[item["cleaned"]] = item.get("room_analysis", {})
            except Exception as e:
                logger.warning(f"Could not load room analysis: {e}")

        # Load cleaned images from folder
        for img_path in sorted(BASE_IMAGES_DIR.glob("*_clean.jpg")):
            try:
                with open(img_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode()
                    images.append(
                        {
                            "image": image_data,
                            "name": img_path.name,
                            "room_analysis": room_analysis_data.get(img_path.name, {}),
                            "source": "cleaned_folder",
                        }
                    )
                    logger.info(f"Loaded cleaned base image: {img_path.name}")
            except Exception as e:
                logger.error(f"Failed to load {img_path}: {e}")

        # Load room images from existing manual curated looks (IDs < 45)
        if db:
            from database.models import CuratedLook

            manual_looks = db.query(CuratedLook).filter(CuratedLook.id < 45, CuratedLook.room_image.isnot(None)).all()

            for look in manual_looks:
                if look.room_image and len(look.room_image) > 1000:
                    images.append(
                        {
                            "image": look.room_image,
                            "name": f"curated_look_{look.id}",
                            "room_analysis": look.room_analysis or {},
                            "source": f"curated_look_{look.id}",
                        }
                    )
                    logger.info(f"Loaded base image from curated look {look.id}: {look.title[:30]}")

        if not images:
            logger.warning("No base images found!")
        else:
            logger.info(f"Total base images available: {len(images)}")

        return images

    async def generate_look(
        self,
        db: Session,
        style_key: str,
        tier_key: str,
        look_number: int = 1,
    ) -> Optional[int]:
        """Generate a single curated look."""
        # Load existing product IDs and titles to avoid duplicates
        if not self._existing_data_loaded:
            self.used_product_ids = self._load_existing_product_ids(db)
            self.used_titles = self._load_existing_titles(db)
            self._existing_data_loaded = True

        # Load base images if not already loaded
        if not self._base_images_loaded:
            self.base_images = self._load_base_images(db)
            self._base_images_loaded = True

        style_config = STYLE_CONFIGS[style_key]
        budget_config = BUDGET_TIERS[tier_key]

        logger.info(f"Generating look: {style_config['style_theme']} / {tier_key} #{look_number}")

        # Select products
        selector = ProductSelector(db, style_config, tier_key, self.used_product_ids)
        selected_products = selector.select_products_for_look()

        if not selected_products:
            logger.error("Failed to select any products")
            return None

        # Calculate totals
        total_price = selector.calculate_total_price(selected_products)
        logger.info(f"Selected {sum(len(p) for p in selected_products.values())} products, total: ₹{total_price:,.0f}")

        # Log selected products
        for ptype, products in selected_products.items():
            for p in products:
                logger.info(f"  - {ptype}: {p['name'][:50]}... (₹{p['price']:,.0f})")

        # Check budget bounds
        if total_price < budget_config["min"]:
            logger.warning(f"Total ₹{total_price:,.0f} below min ₹{budget_config['min']:,.0f}")
        elif total_price > budget_config["max"]:
            logger.warning(f"Total ₹{total_price:,.0f} above max ₹{budget_config['max']:,.0f}")

        # Select base image (round-robin)
        room_image = None
        room_analysis = None
        if self.base_images:
            image_index = (look_number - 1) % len(self.base_images)
            base_image_data = self.base_images[image_index]
            room_image = base_image_data["image"]
            room_analysis = base_image_data.get("room_analysis", {})
            logger.info(f"Using base image: {base_image_data['name']}")

        # Generate visualization
        visualization_image = None
        if not self.skip_visualization and room_image and self.google_ai:
            visualization_image = await self._generate_visualization(room_image, selected_products, style_key, tier_key)

        if self.dry_run:
            logger.info("[DRY RUN] Would save curated look to database")
            return None

        # Save to database
        look_id = self._save_to_database(
            db,
            style_config,
            tier_key,
            selected_products,
            room_image,
            visualization_image,
            room_analysis,
            total_price,
            look_number,
        )

        # Track used product IDs
        for products in selected_products.values():
            for p in products:
                self.used_product_ids.add(p["id"])

        return look_id

    async def _generate_visualization(
        self,
        room_image: str,
        selected_products: Dict[str, List[Dict]],
        style_key: str,
        tier_key: str,
    ) -> Optional[str]:
        """Generate AI visualization for the look."""
        logger.info("Generating AI visualization...")

        # Prepare products data
        products_data = []
        for ptype, products in selected_products.items():
            for product in products:
                products_data.append(
                    {
                        "id": product["id"],
                        "name": product["name"],
                        "full_name": product["name"],
                        "quantity": 1,
                        "image_url": product.get("image_url"),
                        "images": product.get("images", []),
                        "dimensions": product.get("dimensions", {}),
                        "furniture_type": ptype,
                    }
                )

        try:
            result = await self.google_ai.generate_add_multiple_visualization(
                room_image=room_image,
                products=products_data,
                existing_products=[],
                workflow_id=f"auto-curation-{style_key}-{tier_key}-{datetime.now().timestamp()}",
            )
            if result:
                logger.info(f"Visualization generated: {len(result)} bytes")
                return result
            else:
                logger.warning("Visualization generation returned None")
                return None
        except Exception as e:
            logger.error(f"Visualization failed: {e}")
            return None

    def _generate_title_and_description(
        self,
        style_config: Dict,
        tier_key: str,
        selected_products: Dict[str, List[Dict]],
    ) -> Tuple[str, str]:
        """Generate creative title and description based on selected products."""
        # Expanded title patterns (20+ per style to ensure uniqueness)
        title_patterns = {
            "modern": [
                "Urban Minimalist Studio",
                "City Chic Living",
                "Modern Starter Home",
                "Contemporary Comfort Zone",
                "Streamlined Serenity",
                "Modern Metropolitan",
                "Refined Modern Retreat",
                "Sophisticated Urban Nest",
                "Premium Contemporary",
                "Modern Masterpiece Suite",
                "Ultra Modern Penthouse",
                "Luxe Contemporary Living",
                "Clean Lines Haven",
                "Minimalist Oasis",
                "Urban Edge Living",
                "Modern Zen Retreat",
                "Contemporary Elegance",
                "Sleek City Dwelling",
                "Modern Comfort Studio",
                "Urban Simplicity Suite",
                "Sleek & Sophisticated Living",
                "Clean Lines Sanctuary",
                "Minimalist Haven",
                "Urban Elegance Retreat",
            ],
            "modern_luxury": [
                "Affordable Elegance",
                "Glam on a Budget",
                "Luxe Look for Less",
                "Velvet Dreams",
                "Golden Hour Living",
                "Opulent Comfort",
                "Grand Living Suite",
                "Prestige Collection",
                "Elite Comfort Zone",
                "Ultimate Luxury Haven",
                "Royal Living Experience",
                "Platinum Residence",
                "Gilded Glamour Suite",
                "Luxe Velvet Retreat",
                "Champagne Living",
                "Diamond Edge Home",
                "Regal Comfort Zone",
                "Opulent Oasis",
                "Majestic Modern Suite",
                "Luxe Signature Living",
                "Opulent Living Experience",
                "Luxe Comfort Sanctuary",
                "Refined Elegance Suite",
                "Premium Living Retreat",
                "Velvet & Gold Haven",
            ],
            "indian_contemporary": [
                "Desi Charm Studio",
                "Heritage Budget Living",
                "Ethnic Starter Home",
                "Artisan Heritage Home",
                "Cultural Fusion Living",
                "Modern Ethnic Retreat",
                "Handcrafted Luxury",
                "Premium Heritage Suite",
                "Ethnic Elegance Premium",
                "Royal Indian Residence",
                "Heritage Grand Suite",
                "Maharaja Living",
                "Artisan Crafted Haven",
                "Traditional Warmth Suite",
                "Ethnic Fusion Retreat",
                "Heritage Comfort Zone",
                "Cultural Elegance Home",
                "Desi Modern Oasis",
                "Handwoven Heritage Suite",
                "Contemporary Ethnic Living",
                "Heritage Meets Modern",
                "Artisan Crafted Living",
                "Ethnic Elegance Retreat",
                "Traditional Charm Suite",
                "Handcrafted Comfort Zone",
            ],
        }

        # Get style key for templates
        style_key = style_config["style_labels"][0] if style_config.get("style_labels") else "modern"
        titles = title_patterns.get(style_key, title_patterns["modern"])

        # Find a title not already used
        available_titles = [t for t in titles if t not in self.used_titles]
        if not available_titles:
            # Fallback: append tier to make unique
            tier_suffix = {"pocket_friendly": "Essentials", "mid_tier": "Collection", "premium": "Premium", "luxury": "Luxury"}
            base_title = random.choice(titles)
            title = f"{base_title} {tier_suffix.get(tier_key, '')}"
        else:
            title = random.choice(available_titles)

        # Add to used titles
        self.used_titles.add(title)

        # Generate unique description based on actual products selected
        sofa_name = ""
        if "sofa" in selected_products and selected_products["sofa"]:
            sofa_name = selected_products["sofa"][0]["name"].split("(")[0].strip()[:40]

        rug_name = ""
        if "rugs" in selected_products and selected_products["rugs"]:
            rug_name = selected_products["rugs"][0]["name"].split("(")[0].strip()[:40]

        chair_name = ""
        if "accent_chair" in selected_products and selected_products["accent_chair"]:
            chair_name = selected_products["accent_chair"][0]["name"].split("(")[0].strip()[:40]

        # Get materials and colors from style config
        materials = style_config.get("materials", [])[:2]
        colors = style_config.get("colors", [])[:3]
        style_name = style_config["style_theme"]

        # Description templates that include actual product names
        desc_templates = [
            f"A curated {style_name.lower()} living room featuring the stunning {sofa_name or 'premium sofa'} "
            f"paired with {rug_name or 'an elegant rug'}. "
            f"This collection brings together {' and '.join(materials[:2]) if materials else 'quality'} elements "
            f"in harmonious {', '.join(colors[:2]) if colors else 'neutral'} tones.",
            f"Experience {tier_key.replace('_', ' ')} luxury with this {style_name.lower()} collection "
            f"centered around the {sofa_name or 'featured sofa'}. "
            f"Complemented by {chair_name or 'accent seating'} and thoughtfully selected accessories.",
            f"This {style_name.lower()} ensemble brings together {sofa_name or 'premium seating'} "
            f"and carefully selected accent pieces including {rug_name or 'coordinated rugs'} "
            f"for a cohesive, inviting atmosphere.",
        ]

        description = random.choice(desc_templates)

        return title, description

    def _save_to_database(
        self,
        db: Session,
        style_config: Dict,
        tier_key: str,
        selected_products: Dict[str, List[Dict]],
        room_image: Optional[str],
        visualization_image: Optional[str],
        room_analysis: Optional[Dict],
        total_price: float,
        look_number: int,
    ) -> int:
        """Save curated look to database."""
        # Generate creative title and description
        title, description = self._generate_title_and_description(style_config, tier_key, selected_products)

        # Create CuratedLook
        look = CuratedLook(
            title=title,
            style_theme=style_config["style_theme"],
            style_description=description,
            style_labels=style_config["style_labels"],
            room_type="living_room",
            room_image=room_image,
            visualization_image=visualization_image,
            room_analysis=room_analysis,  # Cached room analysis for faster visualization
            total_price=total_price,
            budget_tier=tier_key,
            is_published=False,  # Requires manual review
            display_order=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(look)
        db.flush()  # Get the ID

        # Add products
        display_order = 0
        for ptype, products in selected_products.items():
            for product in products:
                look_product = CuratedLookProduct(
                    curated_look_id=look.id,
                    product_id=product["id"],
                    product_type=ptype,
                    quantity=1,
                    display_order=display_order,
                    created_at=datetime.utcnow(),
                )
                db.add(look_product)
                display_order += 1

        db.commit()
        logger.info(f"Saved curated look ID: {look.id} - {title}")

        return look.id


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Auto-generate curated looks")
    parser.add_argument(
        "--style",
        choices=list(STYLE_CONFIGS.keys()) + ["all"],
        default="all",
        help="Style to generate (default: all)",
    )
    parser.add_argument(
        "--tier",
        choices=list(BUDGET_TIERS.keys()) + ["all"],
        default="all",
        help="Budget tier to generate (default: all)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of looks per style/tier combo (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without saving to database",
    )
    parser.add_argument(
        "--skip-visualization",
        action="store_true",
        help="Skip AI visualization generation",
    )

    args = parser.parse_args()

    # Determine what to generate
    styles = [args.style] if args.style != "all" else list(STYLE_CONFIGS.keys())
    tiers = [args.tier] if args.tier != "all" else list(BUDGET_TIERS.keys())

    total_looks = len(styles) * len(tiers) * args.count
    logger.info(f"Generating {total_looks} curated looks")
    logger.info(f"Styles: {styles}")
    logger.info(f"Tiers: {tiers}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Skip visualization: {args.skip_visualization}")

    # Initialize generator
    generator = LookGenerator(
        dry_run=args.dry_run,
        skip_visualization=args.skip_visualization,
    )

    # Track results
    successful = []
    failed = []
    global_look_counter = 0  # Global counter for base image selection

    # Generate looks
    with get_db_session() as db:
        for style_key in styles:
            for tier_key in tiers:
                for i in range(args.count):
                    global_look_counter += 1
                    look_number = global_look_counter  # Use global counter for varied base images
                    try:
                        look_id = await generator.generate_look(db, style_key, tier_key, look_number)
                        if look_id:
                            successful.append(
                                {
                                    "id": look_id,
                                    "style": style_key,
                                    "tier": tier_key,
                                }
                            )
                        elif args.dry_run:
                            successful.append(
                                {
                                    "style": style_key,
                                    "tier": tier_key,
                                    "dry_run": True,
                                }
                            )

                        # Rate limiting: wait 12 seconds between looks (< 300 RPM)
                        if not args.skip_visualization and global_look_counter < total_looks:
                            logger.info("Waiting 12 seconds for rate limiting...")
                            await asyncio.sleep(12)

                    except Exception as e:
                        logger.exception(f"Failed to generate {style_key}/{tier_key}")
                        failed.append(
                            {
                                "style": style_key,
                                "tier": tier_key,
                                "error": str(e),
                            }
                        )

    # Summary
    logger.info("=" * 60)
    logger.info("GENERATION COMPLETE")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")

    if successful:
        logger.info("\nSuccessful looks:")
        for s in successful:
            if s.get("dry_run"):
                logger.info(f"  [DRY RUN] {s['style']} / {s['tier']}")
            else:
                logger.info(f"  ID {s['id']}: {s['style']} / {s['tier']}")

    if failed:
        logger.info("\nFailed looks:")
        for f in failed:
            logger.info(f"  {f['style']} / {f['tier']}: {f['error']}")


if __name__ == "__main__":
    asyncio.run(main())
