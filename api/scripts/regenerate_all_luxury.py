"""Regenerate visualizations for all 18 luxury looks."""
import asyncio
import base64
import sys
from datetime import datetime

sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from services.google_ai_service import GoogleAIStudioService

from database.connection import get_db_session
from database.models import CuratedLook, CuratedLookProduct, Product, ProductAttribute, ProductImage

PRIORITY_TYPES = [
    "large_sofa",
    "coffee_table",
    "single_seat",
    "carpet",
    "chandelier",
    "floor_lamp",
    "accent_chair",
    "side_table",
    "wall_art",
    "center_table_decor",
    "storage",
    "bar_cabinet",
    "bench",
    "wall_accent",
    "table_decor",
    "table_lamp",
]

MAX_PRODUCTS = 10


async def generate_visualization_for_look(look_id: int, google_ai: GoogleAIStudioService):
    with get_db_session() as db:
        look = db.query(CuratedLook).filter(CuratedLook.id == look_id).first()
        if not look or not look.room_image:
            print(f"Look {look_id} not found or no room image")
            return False

        print(f"\n{'='*60}")
        print(f"Processing: {look.title} (ID: {look_id})")

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

        def get_priority(p):
            ptype = p.get("product_type", "")
            return PRIORITY_TYPES.index(ptype) if ptype in PRIORITY_TYPES else 100

        all_products.sort(key=get_priority)
        products_data = all_products[:MAX_PRODUCTS]

        print(f"Using {len(products_data)} products:")
        for p in products_data:
            print(f"  - [{p.get('product_type')}] {p['name'][:45]}...")

        print("\nGenerating visualization...")

        try:
            result = await google_ai.generate_add_multiple_visualization(
                room_image=look.room_image,
                products=products_data,
                existing_products=[],
                workflow_id=f"luxury-full-{look_id}-{datetime.now().timestamp()}",
            )

            if result:
                print(f"Success! Image size: {len(result)} bytes")
                look.visualization_image = result
                db.commit()

                output_path = f"/tmp/luxury_look_{look_id}.jpg"
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(result))
                print(f"Saved to {output_path}")
                return True
            else:
                print("Failed - no result")
                return False
        except Exception as e:
            print(f"Error: {e}")
            return False


async def main():
    google_ai = GoogleAIStudioService()
    look_ids = list(range(171, 189))

    print(f"Regenerating all {len(look_ids)} luxury looks")
    print(f"Start: {datetime.now()}")

    success = 0
    failed = []

    for look_id in look_ids:
        try:
            if await generate_visualization_for_look(look_id, google_ai):
                success += 1
            else:
                failed.append(look_id)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Error on {look_id}: {e}")
            failed.append(look_id)

    print(f"\n{'='*60}")
    print(f"Done! Success: {success}/{len(look_ids)}")
    if failed:
        print(f"Failed: {failed}")
    print(f"End: {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())
