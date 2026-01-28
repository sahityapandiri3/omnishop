#!/usr/bin/env python3
"""
Curate Indian Contemporary looks with strict style filtering.
Focuses on: cane, wood, brass, jute, textured fabrics, ethnic designs.
"""

import asyncio
import base64
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from services.google_ai_service import GoogleAIStudioService
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from database.connection import get_db_session
from database.models import Category, CuratedLook, CuratedLookProduct, Product, ProductImage

# Indian Contemporary style keywords
INDIAN_KEYWORDS = [
    "cane",
    "sheesham",
    "teak",
    "wood",
    "brass",
    "jute",
    "ethnic",
    "traditional",
    "handcraft",
    "indian",
    "rattan",
    "wicker",
    "mango wood",
    "rosewood",
    "carved",
    "inlay",
    "bone inlay",
    "mother of pearl",
]

INDIAN_STYLES = ["indian_contemporary", "traditional", "ethnic", "indian", "artisan", "rustic"]

# Styles to AVOID
AVOID_STYLES = ["modern", "contemporary", "minimalist", "scandinavian", "industrial", "modern_luxury"]

# Budget tier
PREMIUM_MIN = 800000
PREMIUM_MAX = 1500000

# Product categories with Indian Contemporary preferences
PRODUCT_SPECS = [
    {
        "type": "sofa",
        "categories": ["Sofa", "Three Seater Sofa", "Sectional Sofa"],
        "min_price": 50000,
        "max_price": 300000,
        "priority_keywords": ["wood", "cane", "teak", "sheesham", "fabric"],
    },
    {
        "type": "accent_chair",
        "categories": ["Accent Chair", "Armchair"],
        "min_price": 20000,
        "max_price": 150000,
        "quantity": 2,
        "priority_keywords": ["cane", "jute", "wood", "rattan"],
    },
    {
        "type": "coffee_table",
        "categories": ["Center Table", "Coffee Table"],
        "min_price": 30000,
        "max_price": 200000,
        "priority_keywords": ["wood", "brass", "teak", "sheesham", "carved"],
    },
    {
        "type": "side_table",
        "categories": ["Accent Table", "Side Table", "Console Table"],
        "min_price": 20000,
        "max_price": 150000,
        "priority_keywords": ["wood", "brass", "bone inlay"],
    },
    {
        "type": "cabinet",
        "categories": ["Cabinet", "Sideboard", "Bar Unit"],
        "min_price": 80000,
        "max_price": 400000,
        "priority_keywords": ["wood", "carved", "brass", "sheesham"],
    },
    {
        "type": "bookshelf",
        "categories": ["Bookshelf", "Shelves"],
        "min_price": 40000,
        "max_price": 200000,
        "priority_keywords": ["wood", "teak", "sheesham"],
    },
    {
        "type": "rugs",
        "categories": ["Rugs"],
        "min_price": 50000,
        "max_price": 400000,
        "priority_keywords": ["hand knotted", "wool", "silk", "jute", "dhurrie"],
    },
    {
        "type": "wall_art",
        "categories": ["Wall Art", "Decor & Accessories"],
        "min_price": 30000,
        "max_price": 300000,
        "priority_keywords": ["pichwai", "tanjore", "madhubani", "brass", "ethnic", "indian"],
    },
    {
        "type": "sculpture",
        "categories": ["Sculptures", "Decor & Accessories"],
        "min_price": 50000,
        "max_price": 300000,
        "priority_keywords": ["brass", "bronze", "wooden", "indian", "ganesh", "buddha"],
    },
    {
        "type": "floor_lamp",
        "categories": ["Floor Lamp", "Lamp"],
        "min_price": 15000,
        "max_price": 100000,
        "priority_keywords": ["brass", "wood", "fabric", "cotton"],
    },
    {
        "type": "chandelier",
        "categories": ["Chandelier", "Lighting"],
        "min_price": 50000,
        "max_price": 200000,
        "priority_keywords": ["brass", "crystal", "traditional"],
    },
    {
        "type": "mirror",
        "categories": ["Mirror"],
        "min_price": 30000,
        "max_price": 150000,
        "priority_keywords": ["wood", "carved", "brass", "bone inlay"],
    },
    {
        "type": "planter",
        "categories": ["Planters"],
        "min_price": 5000,
        "max_price": 30000,
        "priority_keywords": ["brass", "ceramic", "terracotta"],
    },
    {
        "type": "cushion",
        "categories": ["Cushion", "Cushion Cover"],
        "min_price": 2000,
        "max_price": 15000,
        "priority_keywords": ["embroidered", "jute", "silk", "cotton", "ethnic"],
    },
]

# Elegant titles for Indian Contemporary Premium
TITLES = [
    "Royal Heritage Living",
    "Artisan Craft Suite",
    "Ethnic Elegance Retreat",
    "Handwoven Heritage Home",
    "Traditional Luxe Living",
    "Brass & Wood Sanctuary",
    "Cane & Comfort Suite",
    "Heritage Fusion Lounge",
    "Vintage Indian Elegance",
    "Craftsman's Pride Living",
]

BASE_IMAGES_DIR = Path("/Users/sahityapandiri/Omnishop/Base_Images/cleaned")


def find_indian_contemporary_product(
    db: Session,
    spec: Dict,
    used_ids: Set[int],
) -> Optional[Product]:
    """Find a product matching Indian Contemporary style."""

    # Find categories
    categories = db.query(Category).filter(func.lower(Category.name).in_([c.lower() for c in spec["categories"]])).all()
    category_ids = [c.id for c in categories]

    if not category_ids:
        print(f"  No categories found for {spec['type']}")
        return None

    # Build base query
    base_query = db.query(Product).filter(
        Product.category_id.in_(category_ids),
        Product.is_available == True,
        Product.price >= spec["min_price"],
        Product.price <= spec["max_price"],
        ~Product.id.in_(used_ids) if used_ids else True,
    )

    # Priority 1: Products with indian_contemporary style
    style_query = base_query.filter(Product.primary_style.in_(INDIAN_STYLES))
    candidates = style_query.all()

    if candidates:
        # Score by keyword matches
        scored = []
        for p in candidates:
            score = 0
            name_lower = p.name.lower()
            for kw in spec.get("priority_keywords", []) + INDIAN_KEYWORDS:
                if kw.lower() in name_lower:
                    score += 10
            # Penalize if it has avoid-style keywords
            for avoid in ["modern", "minimalist", "scandinavian"]:
                if avoid in name_lower:
                    score -= 20
            scored.append((p, score))
        scored.sort(key=lambda x: (-x[1], -x[0].price))
        if scored and scored[0][1] > 0:
            return scored[0][0]

    # Priority 2: Products with Indian keywords in name
    keyword_conditions = []
    for kw in spec.get("priority_keywords", []) + INDIAN_KEYWORDS[:5]:
        keyword_conditions.append(Product.name.ilike(f"%{kw}%"))

    keyword_query = base_query.filter(or_(*keyword_conditions), ~Product.primary_style.in_(AVOID_STYLES))
    candidates = keyword_query.order_by(Product.price.desc()).limit(10).all()

    if candidates:
        return random.choice(candidates[:3]) if len(candidates) >= 3 else candidates[0]

    # Priority 3: Any product not in avoid styles
    fallback_query = (
        base_query.filter(or_(Product.primary_style.is_(None), ~Product.primary_style.in_(AVOID_STYLES)))
        .order_by(Product.price.desc())
        .limit(5)
    )
    candidates = fallback_query.all()

    if candidates:
        return candidates[0]

    return None


def get_product_image(db: Session, product_id: int) -> Optional[str]:
    """Get primary image URL for a product."""
    img = db.query(ProductImage).filter(ProductImage.product_id == product_id).order_by(ProductImage.is_primary.desc()).first()
    return img.original_url if img else None


async def create_indian_contemporary_look(
    db: Session,
    google_ai: GoogleAIStudioService,
    look_number: int,
    used_product_ids: Set[int],
    used_titles: Set[str],
    base_images: List[Dict],
) -> Optional[int]:
    """Create a single Indian Contemporary Premium look."""

    print(f"\n{'='*60}")
    print(f"Creating Indian Contemporary Premium Look #{look_number}")
    print(f"{'='*60}")

    selected_products = {}
    total_price = 0

    # Select products for each category
    for spec in PRODUCT_SPECS:
        quantity = spec.get("quantity", 1)
        for i in range(quantity):
            product = find_indian_contemporary_product(db, spec, used_product_ids)

            if product:
                if spec["type"] not in selected_products:
                    selected_products[spec["type"]] = []

                selected_products[spec["type"]].append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "style": product.primary_style,
                        "image_url": get_product_image(db, product.id),
                    }
                )
                used_product_ids.add(product.id)
                total_price += product.price
                print(
                    f"  + {spec['type']}: {product.name[:50]}... (₹{product.price:,.0f}) [{product.primary_style or 'unknown'}]"
                )
            else:
                print(f"  ! No product found for {spec['type']}")

    print(f"\nTotal: ₹{total_price:,.0f} (target: ₹{PREMIUM_MIN:,}-{PREMIUM_MAX:,})")

    if total_price < PREMIUM_MIN:
        print(f"  Warning: Below premium minimum")

    # Select title
    available_titles = [t for t in TITLES if t not in used_titles]
    if not available_titles:
        title = f"Indian Contemporary Suite {look_number}"
    else:
        title = random.choice(available_titles)
    used_titles.add(title)

    # Get base image
    if base_images:
        base_img = base_images[(look_number - 1) % len(base_images)]
        room_image = base_img["image"]
        room_analysis = base_img.get("room_analysis", {})
        print(f"Using base image: {base_img['name']}")
    else:
        print("No base images available!")
        return None

    # Generate visualization
    print("Generating visualization...")
    products_for_viz = []
    for ptype, products in selected_products.items():
        for p in products:
            products_for_viz.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "full_name": p["name"],
                    "quantity": 1,
                    "image_url": p["image_url"],
                    "furniture_type": ptype,
                }
            )

    try:
        viz_image = await google_ai.generate_add_multiple_visualization(
            room_image=room_image,
            products=products_for_viz,
            existing_products=[],
            workflow_id=f"indian-contemporary-{look_number}-{datetime.now().timestamp()}",
        )
        print(f"Visualization generated: {len(viz_image) if viz_image else 0} bytes")
    except Exception as e:
        print(f"Visualization failed: {e}")
        viz_image = None

    # Generate description
    sofa_name = selected_products.get("sofa", [{}])[0].get("name", "premium sofa")[:40]
    chair_name = selected_products.get("accent_chair", [{}])[0].get("name", "accent chair")[:40]

    description = (
        f"A curated Indian Contemporary living room featuring {sofa_name} "
        f"paired with {chair_name}. This collection brings together handcrafted wood, "
        f"cane, brass, and textured fabrics in warm, earthy tones."
    )

    # Save to database
    look = CuratedLook(
        title=title,
        style_theme="Indian Contemporary",
        style_description=description,
        style_labels=["indian_contemporary"],
        room_type="living_room",
        room_image=room_image,
        visualization_image=viz_image,
        room_analysis=room_analysis,
        total_price=total_price,
        budget_tier="premium",
        is_published=False,
        display_order=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(look)
    db.flush()

    # Add products
    display_order = 0
    for ptype, products in selected_products.items():
        for p in products:
            look_product = CuratedLookProduct(
                curated_look_id=look.id,
                product_id=p["id"],
                product_type=ptype,
                quantity=1,
                display_order=display_order,
                created_at=datetime.utcnow(),
            )
            db.add(look_product)
            display_order += 1

    db.commit()
    print(f"\nSaved look ID: {look.id} - {title}")

    return look.id


def load_base_images(db: Session) -> List[Dict]:
    """Load base room images."""
    images = []

    # Load from cleaned folder
    for img_path in sorted(BASE_IMAGES_DIR.glob("*_clean.jpg")):
        try:
            with open(img_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
                images.append(
                    {
                        "image": image_data,
                        "name": img_path.name,
                        "room_analysis": {},
                    }
                )
        except Exception as e:
            print(f"Failed to load {img_path}: {e}")

    # Also load from existing curated looks
    manual_looks = db.query(CuratedLook).filter(CuratedLook.id < 45, CuratedLook.room_image.isnot(None)).limit(10).all()

    for look in manual_looks:
        if look.room_image and len(look.room_image) > 1000:
            images.append(
                {
                    "image": look.room_image,
                    "name": f"curated_{look.id}",
                    "room_analysis": look.room_analysis or {},
                }
            )

    print(f"Loaded {len(images)} base images")
    return images


async def main():
    """Generate 6 Indian Contemporary Premium looks."""

    print("=" * 60)
    print("INDIAN CONTEMPORARY PREMIUM LOOK GENERATOR")
    print("=" * 60)

    google_ai = GoogleAIStudioService()

    with get_db_session() as db:
        # Load existing product IDs to avoid
        existing = (
            db.query(CuratedLookProduct.product_id)
            .join(CuratedLook, CuratedLookProduct.curated_look_id == CuratedLook.id)
            .filter(CuratedLook.id >= 45)
            .distinct()
            .all()
        )
        used_product_ids = {p[0] for p in existing}
        print(f"Avoiding {len(used_product_ids)} already-used products")

        # Load existing titles
        existing_titles = db.query(CuratedLook.title).filter(CuratedLook.id >= 45).all()
        used_titles = {t[0] for t in existing_titles}

        # Load base images
        base_images = load_base_images(db)

        # Generate 6 looks
        created_ids = []
        for i in range(1, 7):
            try:
                look_id = await create_indian_contemporary_look(db, google_ai, i, used_product_ids, used_titles, base_images)
                if look_id:
                    created_ids.append(look_id)

                # Rate limiting
                if i < 6:
                    print("\nWaiting 12 seconds for rate limiting...")
                    await asyncio.sleep(12)

            except Exception as e:
                print(f"Error creating look {i}: {e}")

        print("\n" + "=" * 60)
        print("COMPLETE")
        print(f"Created {len(created_ids)} looks: {created_ids}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
