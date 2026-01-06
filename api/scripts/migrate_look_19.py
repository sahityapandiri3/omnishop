"""One-time script to migrate look 19 from local to production DB"""
import asyncio
import json
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from database.models import CuratedLook, CuratedLookProduct, Product
from core.database import AsyncSessionLocal

# Product IDs on production
PRODUCT_IDS = [7387, 9860, 571, 6945, 4069, 1041, 4533, 3664, 9624, 9332]

# Look data (images loaded from files)
LOOK_DATA = {
    "title": "Gilded Serenity Living Room",
    "style_theme": "Red room",
    "style_description": "A refined modern luxury living space where sculptural seating, warm metallic accents, and a statement chandelier create effortless elegance. Soft textures balance the stone fireplace and expansive windows, allowing natural light and greenery to frame the room. The result is a calm yet opulent setting—designed for intimate conversations, quiet evenings, and understated sophistication.",
    "style_labels": ["modern_luxury"],
    "room_type": "living_room",
    "is_published": True,
    "display_order": 0,
}


async def migrate_look():
    """Create the look on production"""
    # Load images from local files if they exist
    room_image = None
    viz_image = None
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    room_file = os.path.join(script_dir, 'look_19_room.txt')
    viz_file = os.path.join(script_dir, 'look_19_viz.txt')
    
    if os.path.exists(room_file):
        with open(room_file, 'r') as f:
            room_image = f.read()
    if os.path.exists(viz_file):
        with open(viz_file, 'r') as f:
            viz_image = f.read()
    
    async with AsyncSessionLocal() as session:
        # Check if look already exists
        query = select(CuratedLook).where(CuratedLook.title == LOOK_DATA["title"])
        result = await session.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Look already exists with ID {existing.id}")
            return
        
        # Calculate total price
        total_price = 0
        for product_id in PRODUCT_IDS:
            query = select(Product).where(Product.id == product_id)
            result = await session.execute(query)
            product = result.scalar_one_or_none()
            if product and product.price:
                total_price += product.price
        
        # Create the look
        look = CuratedLook(
            title=LOOK_DATA["title"],
            style_theme=LOOK_DATA["style_theme"],
            style_description=LOOK_DATA["style_description"],
            style_labels=LOOK_DATA["style_labels"],
            room_type=LOOK_DATA["room_type"],
            room_image=room_image,
            visualization_image=viz_image,
            total_price=total_price,
            is_published=LOOK_DATA["is_published"],
            display_order=LOOK_DATA["display_order"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        session.add(look)
        await session.flush()
        
        print(f"Created look with ID {look.id}")
        
        # Add products
        for i, product_id in enumerate(PRODUCT_IDS):
            look_product = CuratedLookProduct(
                curated_look_id=look.id,
                product_id=product_id,
                quantity=1,
                display_order=i,
                created_at=datetime.utcnow(),
            )
            session.add(look_product)
        
        await session.commit()
        print(f"Added {len(PRODUCT_IDS)} products to look")
        print(f"Total price: ₹{total_price:,.0f}")


if __name__ == "__main__":
    asyncio.run(migrate_look())
