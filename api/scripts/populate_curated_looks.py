"""
Script to populate curated_looks tables with sample data.
Run with: DATABASE_URL="your_production_url" python3 scripts/populate_curated_looks.py
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def create_curated_looks():
    """Create sample curated looks for the home page."""
    session = Session()

    try:
        # Sample curated looks data
        curated_looks = [
            {
                "title": "Modern Minimalist Living",
                "style_theme": "Modern Minimalist",
                "style_description": "Clean lines, neutral tones, and carefully curated furniture pieces create a serene and sophisticated living space. Perfect for those who appreciate simplicity with a touch of elegance.",
                "room_type": "living_room",
                "is_published": True,
                "display_order": 1,
                # Product IDs: Jelly Bean Sofa, Side Coffee Table, Elara Accent Chair, Peg Side Table
                "product_ids": [7641, 1157, 9103, 20],
                "product_types": ["sofa", "coffee_table", "accent_chair", "side_table"],
            },
            {
                "title": "Contemporary Comfort",
                "style_theme": "Contemporary",
                "style_description": "Blend comfort with style in this contemporary living room setup. Featuring plush seating and elegant accent pieces that make every day feel special.",
                "room_type": "living_room",
                "is_published": True,
                "display_order": 2,
                # Product IDs: Node Sofa 1 Seater, Coffee Table - Black, Gio Accent Chair, All Gold Side Table
                "product_ids": [407, 1425, 6504, 6411],
                "product_types": ["sofa", "coffee_table", "accent_chair", "side_table"],
            },
            {
                "title": "Elegant Classic",
                "style_theme": "Classic Elegant",
                "style_description": "Timeless elegance meets modern functionality. Rich textures and sophisticated furniture pieces create a warm, inviting atmosphere.",
                "room_type": "living_room",
                "is_published": True,
                "display_order": 3,
                # Product IDs: Cael Sofa, Coffee Table - White, Lauren Accent Chair, Side Table - White Oak
                "product_ids": [459, 1422, 3978, 332],
                "product_types": ["sofa", "coffee_table", "accent_chair", "side_table"],
            },
        ]

        now = datetime.utcnow()

        for look_data in curated_looks:
            # First, verify all products exist
            product_ids = look_data["product_ids"]
            result = session.execute(text("SELECT id FROM products WHERE id = ANY(:ids)"), {"ids": product_ids})
            existing_ids = {r[0] for r in result.fetchall()}
            missing = set(product_ids) - existing_ids

            if missing:
                print(f"WARNING: Products {missing} not found for look '{look_data['title']}'. Skipping this look.")
                continue

            # Calculate total price
            result = session.execute(
                text("SELECT COALESCE(SUM(price), 0) FROM products WHERE id = ANY(:ids)"), {"ids": product_ids}
            )
            total_price = result.scalar() or 0

            # Insert curated look
            result = session.execute(
                text(
                    """
                    INSERT INTO curated_looks (title, style_theme, style_description, room_type,
                                              total_price, is_published, display_order, created_at, updated_at)
                    VALUES (:title, :style_theme, :style_description, :room_type,
                            :total_price, :is_published, :display_order, :created_at, :updated_at)
                    RETURNING id
                """
                ),
                {
                    "title": look_data["title"],
                    "style_theme": look_data["style_theme"],
                    "style_description": look_data["style_description"],
                    "room_type": look_data["room_type"],
                    "total_price": total_price,
                    "is_published": look_data["is_published"],
                    "display_order": look_data["display_order"],
                    "created_at": now,
                    "updated_at": now,
                },
            )
            look_id = result.scalar()
            print(f"Created curated look: {look_data['title']} (ID: {look_id}, Total: Rs.{total_price:,.0f})")

            # Insert curated look products
            for i, (product_id, product_type) in enumerate(zip(product_ids, look_data["product_types"])):
                session.execute(
                    text(
                        """
                        INSERT INTO curated_look_products (curated_look_id, product_id, product_type, display_order, created_at)
                        VALUES (:curated_look_id, :product_id, :product_type, :display_order, :created_at)
                    """
                    ),
                    {
                        "curated_look_id": look_id,
                        "product_id": product_id,
                        "product_type": product_type,
                        "display_order": i,
                        "created_at": now,
                    },
                )
            print(f"  Added {len(product_ids)} products to look")

        session.commit()
        print("\n✅ Successfully populated curated looks!")

        # Show summary
        result = session.execute(text("SELECT COUNT(*) FROM curated_looks"))
        look_count = result.scalar()
        result = session.execute(text("SELECT COUNT(*) FROM curated_look_products"))
        product_count = result.scalar()
        print(f"\nSummary: {look_count} curated looks with {product_count} product associations")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    create_curated_looks()
