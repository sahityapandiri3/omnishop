"""
Regenerate look with fewer products to avoid API failures.
Uses only key furniture pieces: sofa, chairs, coffee table, rug, and lamps.
"""
import asyncio
import base64
import sys

sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from services.google_ai_service import GoogleAIStudioService
from database.connection import get_db_session
from database.models import CuratedLook, CuratedLookProduct, Product, ProductAttribute, ProductImage

# Priority order for products - include only the most important ones
PRIORITY_TYPES = [
    "sofa",
    "accent_chair",
    "coffee_table",
    "rugs",
    "floor_lamp",
    "ceiling_lamp",
    "side_table",
    "wall_art",
]

MAX_PRODUCTS = 4  # Limit to 4 products to reduce API load


async def regenerate_look_lite(look_id: int):
    """Regenerate visualization with fewer products."""

    google_ai = GoogleAIStudioService()

    with get_db_session() as db:
        look = db.query(CuratedLook).filter(CuratedLook.id == look_id).first()
        if not look:
            print(f"Look {look_id} not found")
            return

        print(f"Regenerating (lite): {look.title}")
        print(f"Room image size: {len(look.room_image)} bytes")

        # Get products with their images and dimensions
        look_products = db.query(CuratedLookProduct).filter(
            CuratedLookProduct.curated_look_id == look_id
        ).all()

        all_products = []
        for lp in look_products:
            product = db.query(Product).filter(Product.id == lp.product_id).first()
            if not product:
                continue

            images = db.query(ProductImage).filter(
                ProductImage.product_id == product.id
            ).limit(3).all()
            image_urls = [img.original_url for img in images]

            attrs = db.query(ProductAttribute).filter(
                ProductAttribute.product_id == product.id,
                ProductAttribute.attribute_name.in_(["width", "height", "depth", "diameter"]),
            ).all()

            dimensions = {}
            for attr in attrs:
                try:
                    dimensions[attr.attribute_name] = float(attr.attribute_value)
                except:
                    pass

            all_products.append({
                "id": product.id,
                "name": product.name,
                "full_name": product.name,
                "quantity": lp.quantity or 1,
                "image_url": image_urls[0] if image_urls else None,
                "images": image_urls,
                "dimensions": dimensions,
                "furniture_type": lp.product_type or "furniture",
                "product_type": lp.product_type,
            })

        # Sort products by priority
        def get_priority(p):
            ptype = p.get("product_type", "")
            if ptype in PRIORITY_TYPES:
                return PRIORITY_TYPES.index(ptype)
            return 100

        all_products.sort(key=get_priority)

        # Take only top priority products
        products_data = all_products[:MAX_PRODUCTS]

        print(f"Using {len(products_data)} of {len(all_products)} products:")
        for p in products_data:
            print(f"  - [{p.get('product_type', 'unknown')}] {p['name'][:40]}")

        print("\nRegenerating visualization...")

        result = await google_ai.generate_add_multiple_visualization(
            room_image=look.room_image,
            products=products_data,
            existing_products=[],
            workflow_id=f"regenerate-lite-{look_id}",
        )

        if result:
            print(f"Success! New image size: {len(result)} bytes")
            look.visualization_image = result
            db.commit()
            print("Saved to database")

            output_path = f"/tmp/regenerated_look_{look_id}.jpg"
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(result))
            print(f"Saved to {output_path}")
        else:
            print("Failed to generate visualization")


if __name__ == "__main__":
    look_id = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    asyncio.run(regenerate_look_lite(look_id))
