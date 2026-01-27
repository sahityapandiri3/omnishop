"""
Generate visualizations for luxury curated looks (IDs 171-188).
"""
import asyncio
import base64
import sys
import time
from datetime import datetime

sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from services.google_ai_service import GoogleAIStudioService

from database.connection import get_db_session
from database.models import CuratedLook, CuratedLookProduct, Product, ProductAttribute, ProductImage

# Priority order for products
PRIORITY_TYPES = [
    "large_sofa",
    "single_seat",
    "carpet",
    "chandelier",
    "floor_lamp",
    "accent_chair",
    "side_table",
    "storage",
    "bar_cabinet",
    "bench",
    "wall_accent",
    "table_decor",
    "table_lamp",
]

MAX_PRODUCTS = 8  # Limit products per visualization


async def generate_visualization_for_look(look_id: int, google_ai: GoogleAIStudioService):
    """Generate visualization for a single look."""

    with get_db_session() as db:
        look = db.query(CuratedLook).filter(CuratedLook.id == look_id).first()
        if not look:
            print(f"Look {look_id} not found")
            return False

        if not look.room_image:
            print(f"Look {look_id} has no room image")
            return False

        print(f"\n{'='*60}")
        print(f"Processing: {look.title} (ID: {look_id})")
        print(f"Room image size: {len(look.room_image)} bytes")

        # Get products with their images and dimensions
        look_products = db.query(CuratedLookProduct).filter(CuratedLookProduct.curated_look_id == look_id).all()

        all_products = []
        for lp in look_products:
            product = db.query(Product).filter(Product.id == lp.product_id).first()
            if not product:
                continue

            images = db.query(ProductImage).filter(ProductImage.product_id == product.id).limit(3).all()
            image_urls = [img.original_url for img in images]

            attrs = (
                db.query(ProductAttribute)
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
                except:
                    pass

            all_products.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "full_name": product.name,
                    "quantity": lp.quantity or 1,
                    "image_url": image_urls[0] if image_urls else None,
                    "images": image_urls,
                    "dimensions": dimensions,
                    "furniture_type": lp.product_type or "furniture",
                    "product_type": lp.product_type,
                }
            )

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
            print(f"  - [{p.get('product_type', 'unknown')}] {p['name'][:50]}...")

        print("\nGenerating visualization...")

        try:
            result = await google_ai.generate_add_multiple_visualization(
                room_image=look.room_image,
                products=products_data,
                existing_products=[],
                workflow_id=f"luxury-viz-{look_id}-{datetime.now().timestamp()}",
            )

            if result:
                print(f"Success! New image size: {len(result)} bytes")
                look.visualization_image = result
                db.commit()

                # Save to file for preview
                output_path = f"/tmp/luxury_look_{look_id}.jpg"
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(result))
                print(f"Saved to {output_path}")
                return True
            else:
                print("Failed - no result returned")
                return False

        except Exception as e:
            print(f"Error: {e}")
            return False


async def main():
    """Generate visualizations for all luxury looks."""
    google_ai = GoogleAIStudioService()

    look_ids = list(range(171, 189))  # IDs 171-188

    print(f"Starting visualization generation for {len(look_ids)} looks")
    print(f"Start time: {datetime.now()}")

    success_count = 0
    failed_ids = []

    for look_id in look_ids:
        try:
            success = await generate_visualization_for_look(look_id, google_ai)
            if success:
                success_count += 1
            else:
                failed_ids.append(look_id)

            # Rate limiting - wait between requests
            print("Waiting 5 seconds before next request...")
            await asyncio.sleep(5)

        except Exception as e:
            print(f"Error processing look {look_id}: {e}")
            failed_ids.append(look_id)

    print(f"\n{'='*60}")
    print(f"COMPLETED")
    print(f"Success: {success_count}/{len(look_ids)}")
    if failed_ids:
        print(f"Failed IDs: {failed_ids}")
    print(f"End time: {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())
