"""
One-time script to regenerate a curated look visualization with higher quality.
"""
import asyncio
import base64
import sys

sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from services.google_ai_service import GoogleAIStudioService

from database.connection import get_db_session
from database.models import CuratedLook, CuratedLookProduct, Product, ProductAttribute, ProductImage


async def regenerate_look(look_id: int):
    """Regenerate visualization for a curated look from the original room image."""

    google_ai = GoogleAIStudioService()

    with get_db_session() as db:
        # Get the curated look
        look = db.query(CuratedLook).filter(CuratedLook.id == look_id).first()
        if not look:
            print(f"Look {look_id} not found")
            return

        print(f"Regenerating: {look.title}")
        print(f"Room image size: {len(look.room_image)} bytes")

        # Get products with their images and dimensions
        look_products = db.query(CuratedLookProduct).filter(CuratedLookProduct.curated_look_id == look_id).all()

        products_data = []
        for lp in look_products:
            product = db.query(Product).filter(Product.id == lp.product_id).first()
            if not product:
                continue

            # Get product image
            images = db.query(ProductImage).filter(ProductImage.product_id == product.id).limit(3).all()
            image_urls = [img.original_url for img in images]

            # Get dimensions
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

            products_data.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "full_name": product.name,
                    "quantity": lp.quantity or 1,
                    "image_url": image_urls[0] if image_urls else None,
                    "images": image_urls,
                    "dimensions": dimensions,
                    "furniture_type": lp.product_type or "furniture",
                }
            )

        print(f"Products: {len(products_data)}")
        for p in products_data:
            dim_str = f" ({p['dimensions']})" if p["dimensions"] else ""
            print(f"  - {p['name'][:50]}{dim_str}")

        # Regenerate visualization from scratch using the original room image
        print("\nRegenerating visualization...")

        result = await google_ai.generate_add_multiple_visualization(
            room_image=look.room_image,  # Original clean room image
            products=products_data,
            existing_products=[],  # No existing products - fresh start
            workflow_id=f"regenerate-{look_id}",
        )

        if result:
            print(f"Success! New image size: {len(result)} bytes")

            # Update the database
            look.visualization_image = result
            db.commit()
            print("Saved to database")

            # Also save to file for inspection
            output_path = f"/tmp/regenerated_look_{look_id}.jpg"
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(result))
            print(f"Saved to {output_path}")
        else:
            print("Failed to generate visualization")


if __name__ == "__main__":
    look_id = int(sys.argv[1]) if len(sys.argv) > 1 else 31
    asyncio.run(regenerate_look(look_id))
