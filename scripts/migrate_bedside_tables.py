"""
Migration script to categorize bedside table products into Bedside Tables category.
Run with: railway run python scripts/migrate_bedside_tables.py
"""
import os
import sys

# Add the api directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from sqlalchemy import create_engine, text

def run_migration():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print(f"Connecting to database...")
    engine = create_engine(database_url)

    with engine.connect() as conn:
        # First, check current state
        print("\n=== Current state of bedside/nightstand products ===")
        result = conn.execute(text("""
            SELECT p.category_id, c.name as category_name, COUNT(*) as product_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(p.name) LIKE '%bedside%' OR LOWER(p.name) LIKE '%nightstand%' OR LOWER(p.name) LIKE '%night stand%'
            GROUP BY p.category_id, c.name
            ORDER BY product_count DESC;
        """))
        for row in result:
            print(f"  Category {row[0]} ({row[1]}): {row[2]} products")

        # Check if Bedside Tables category exists
        result = conn.execute(text("SELECT id, name FROM categories WHERE slug = 'bedside-tables';"))
        bedside_category = result.fetchone()

        if not bedside_category:
            print("\nERROR: Bedside Tables category not found!")
            print("Available categories with 'bedside' or 'nightstand':")
            result = conn.execute(text("""
                SELECT id, name, slug FROM categories
                WHERE LOWER(name) LIKE '%bedside%' OR LOWER(name) LIKE '%nightstand%'
                ORDER BY id;
            """))
            for row in result:
                print(f"  ID {row[0]}: {row[1]} (slug: {row[2]})")
            sys.exit(1)

        bedside_category_id = bedside_category[0]
        print(f"\nFound Bedside Tables category with ID: {bedside_category_id}")

        # Update products with 'bedside' or 'nightstand' in name to use the Bedside Tables category
        print("\n=== Updating products ===")
        result = conn.execute(text(f"""
            UPDATE products
            SET category_id = {bedside_category_id}
            WHERE LOWER(name) LIKE '%bedside%' OR LOWER(name) LIKE '%nightstand%' OR LOWER(name) LIKE '%night stand%';
        """))
        conn.commit()

        print(f"Updated {result.rowcount} products to Bedside Tables category")

        # Verify final state
        print("\n=== Final state of bedside/nightstand products ===")
        result = conn.execute(text("""
            SELECT p.category_id, c.name as category_name, COUNT(*) as product_count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(p.name) LIKE '%bedside%' OR LOWER(p.name) LIKE '%nightstand%' OR LOWER(p.name) LIKE '%night stand%'
            GROUP BY p.category_id, c.name
            ORDER BY product_count DESC;
        """))
        for row in result:
            print(f"  Category {row[0]} ({row[1]}): {row[2]} products")

        print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    run_migration()
