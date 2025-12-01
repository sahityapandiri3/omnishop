#!/usr/bin/env python3
"""
Recategorize all products based on product names.

This script updates the category assignments for all products by analyzing
their names and assigning more specific categories (e.g., "Three Seater Sofa"
instead of generic "Sofas").

Usage:
    python scripts/recategorize_products.py [--dry-run] [--store=storename]

Options:
    --dry-run           Show what would be changed without making actual changes
    --store=storename   Only process products from a specific store (e.g., --store=phantomhands)
"""
import sys
import re
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.connection import get_db_session
from database.models import Product, Category


def determine_category_from_name(product_name: str, current_category: str = None) -> str:
    """
    Determine the correct category based on product name.
    Applies to all stores.
    """
    name_lower = product_name.lower()

    # Ottoman detection - must come before sofa check
    if 'ottoman' in name_lower:
        return 'Ottoman'

    # Side table detection - must come before table check
    if 'side table' in name_lower or 'sidetable' in name_lower or 'end table' in name_lower:
        return 'Side Table'

    # Coffee table detection
    if 'coffee table' in name_lower:
        return 'Coffee Table'

    # Console table detection
    if 'console' in name_lower and 'table' in name_lower:
        return 'Console Table'

    # Dining table detection
    if 'dining table' in name_lower or 'dining' in name_lower and 'table' in name_lower:
        return 'Dining Table'

    # Center table detection
    if 'center table' in name_lower or 'centre table' in name_lower:
        return 'Center Table'

    # Nightstand / Bedside table
    if 'nightstand' in name_lower or 'night stand' in name_lower or 'bedside table' in name_lower or 'bedside' in name_lower:
        return 'Nightstand'

    # Sofa seater variations - categorize by seating capacity
    if 'sofa' in name_lower or 'seater' in name_lower or 'couch' in name_lower:
        if 'three seater' in name_lower or '3 seater' in name_lower or 'three-seater' in name_lower or '3-seater' in name_lower:
            return 'Three Seater Sofa'
        elif 'two seater' in name_lower or '2 seater' in name_lower or 'two-seater' in name_lower or '2-seater' in name_lower:
            return 'Two Seater Sofa'
        elif 'single seater' in name_lower or '1 seater' in name_lower or 'one seater' in name_lower or 'single-seater' in name_lower or '1-seater' in name_lower or 'one-seater' in name_lower:
            return 'Single Seater Sofa'
        elif 'sectional' in name_lower:
            return 'Sectional Sofa'
        elif 'sofa' in name_lower or 'couch' in name_lower:
            return 'Sofa'

    # Armchair detection
    if 'armchair' in name_lower or 'arm chair' in name_lower:
        return 'Armchair'

    # Lounge chair detection
    if 'lounge' in name_lower and 'chair' in name_lower:
        return 'Lounge Chair'

    # Accent chair detection
    if 'accent' in name_lower and 'chair' in name_lower:
        return 'Accent Chair'

    # Dining chair detection
    if 'dining' in name_lower and 'chair' in name_lower:
        return 'Dining Chair'

    # Office chair detection
    if 'office' in name_lower and 'chair' in name_lower:
        return 'Office Chair'

    # Rocking chair detection
    if 'rocking' in name_lower and 'chair' in name_lower:
        return 'Rocking Chair'

    # Recliner detection
    if 'recliner' in name_lower:
        return 'Recliner'

    # Generic chair
    if 'chair' in name_lower:
        return 'Chair'

    # Bench detection
    if 'bench' in name_lower:
        return 'Bench'

    # Stool detection
    if 'stool' in name_lower:
        return 'Stool'

    # Bed detection
    if 'bed' in name_lower:
        if 'king' in name_lower:
            return 'King Bed'
        elif 'queen' in name_lower:
            return 'Queen Bed'
        elif 'single' in name_lower or 'twin' in name_lower:
            return 'Single Bed'
        elif 'double' in name_lower:
            return 'Double Bed'
        return 'Bed'

    # Wardrobe / Closet detection
    if 'wardrobe' in name_lower or 'closet' in name_lower or 'armoire' in name_lower:
        return 'Wardrobe'

    # Dresser detection
    if 'dresser' in name_lower:
        return 'Dresser'

    # Chest of drawers
    if 'chest' in name_lower and 'drawer' in name_lower:
        return 'Chest of Drawers'

    # Bookshelf / Shelves detection
    if 'bookshelf' in name_lower or 'book shelf' in name_lower or 'bookcase' in name_lower:
        return 'Bookshelf'
    if 'shelf' in name_lower or 'shelves' in name_lower or 'shelving' in name_lower:
        return 'Shelves'

    # TV Unit / Media console
    if 'tv unit' in name_lower or 'tv stand' in name_lower or 'media console' in name_lower or 'entertainment' in name_lower:
        return 'TV Unit'

    # Sideboard / Buffet
    if 'sideboard' in name_lower or 'buffet' in name_lower:
        return 'Sideboard'

    # Storage / Cabinet detection
    if 'cabinet' in name_lower:
        return 'Cabinet'
    if 'storage' in name_lower:
        return 'Storage'

    # Desk detection
    if 'desk' in name_lower:
        return 'Desk'

    # Lamp detection
    if 'lamp' in name_lower or 'light' in name_lower:
        if 'floor lamp' in name_lower or 'floor light' in name_lower:
            return 'Floor Lamp'
        elif 'table lamp' in name_lower or 'desk lamp' in name_lower:
            return 'Table Lamp'
        elif 'pendant' in name_lower:
            return 'Pendant Lamp'
        elif 'wall lamp' in name_lower or 'sconce' in name_lower or 'wall light' in name_lower:
            return 'Wall Lamp'
        elif 'chandelier' in name_lower:
            return 'Chandelier'
        elif 'ceiling' in name_lower:
            return 'Ceiling Light'
        elif 'lamp' in name_lower:
            return 'Lamp'

    # Mirror detection
    if 'mirror' in name_lower:
        return 'Mirror'

    # Rug / Carpet detection
    if 'rug' in name_lower or 'carpet' in name_lower:
        return 'Rug'

    # Planter detection
    if 'planter' in name_lower or 'plant pot' in name_lower or 'flower pot' in name_lower:
        return 'Planter'

    # Vase detection
    if 'vase' in name_lower:
        return 'Vase'

    # Clock detection
    if 'clock' in name_lower:
        return 'Clock'

    # Divider detection
    if 'divider' in name_lower or 'screen' in name_lower and 'room' in name_lower:
        return 'Room Divider'

    # Curtain detection
    if 'curtain' in name_lower or 'drape' in name_lower:
        return 'Curtain'

    # Cushion / Pillow detection
    if 'cushion' in name_lower or 'pillow' in name_lower:
        return 'Cushion'

    # Throw / Blanket detection
    if 'throw' in name_lower or 'blanket' in name_lower:
        return 'Throw'

    # Table (generic) - after all specific table types
    if 'table' in name_lower:
        return 'Table'

    # Return current category if no specific match
    return current_category or 'Furniture'


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from category name"""
    slug = name.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    return slug


def get_or_create_category(session, category_name: str) -> Category:
    """Get existing category or create a new one"""
    category = session.query(Category).filter_by(name=category_name).first()

    if not category:
        slug = generate_slug(category_name)
        # Make slug unique if needed
        existing = session.query(Category).filter_by(slug=slug).first()
        if existing:
            slug = f"{slug}-{len(slug)}"

        category = Category(
            name=category_name,
            slug=slug,
            description=f"Products in the {category_name} category"
        )
        session.add(category)
        session.flush()  # Get the ID
        print(f"  [NEW CATEGORY] Created: '{category_name}' (slug: {slug})")

    return category


def recategorize_products(dry_run: bool = False, store_filter: str = None):
    """Recategorize all products based on their names"""

    print("=" * 70)
    print("Product Recategorization Script")
    print("=" * 70)

    if dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    if store_filter:
        print(f"Filtering by store: {store_filter}\n")

    with get_db_session() as session:
        # Build query
        query = session.query(Product)
        if store_filter:
            query = query.filter(Product.source_website == store_filter)

        products = query.all()

        print(f"\nFound {len(products)} products to analyze\n")

        # Track changes by store
        changes = []
        category_counts = {}
        store_stats = {}

        for product in products:
            store = product.source_website or 'unknown'
            if store not in store_stats:
                store_stats[store] = {'total': 0, 'changed': 0}
            store_stats[store]['total'] += 1

            # Get current category name
            current_category_name = product.category.name if product.category else 'None'

            # Determine new category from product name
            new_category_name = determine_category_from_name(product.name, current_category_name)

            # Track category distribution
            category_counts[new_category_name] = category_counts.get(new_category_name, 0) + 1

            # Check if category needs to change
            if new_category_name != current_category_name:
                store_stats[store]['changed'] += 1
                changes.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'store': store,
                    'old_category': current_category_name,
                    'new_category': new_category_name
                })

        # Print store statistics
        print("\nProducts by Store:")
        print("-" * 50)
        for store, stats in sorted(store_stats.items()):
            print(f"  {store}: {stats['total']} products ({stats['changed']} to be recategorized)")

        # Print category distribution
        print("\n\nCategory Distribution (after recategorization):")
        print("-" * 50)
        for cat_name, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"  {cat_name}: {count} products")

        # Print changes summary
        print(f"\n\nTotal products requiring category changes: {len(changes)}")
        print("-" * 70)

        if changes:
            # Group by store for clearer output
            changes_by_store = {}
            for change in changes:
                store = change['store']
                if store not in changes_by_store:
                    changes_by_store[store] = []
                changes_by_store[store].append(change)

            for store, store_changes in sorted(changes_by_store.items()):
                print(f"\n[{store.upper()}] - {len(store_changes)} changes:")
                for change in store_changes[:20]:  # Show first 20 per store
                    print(f"  [{change['product_id']}] {change['product_name'][:45]}...")
                    print(f"      '{change['old_category']}' -> '{change['new_category']}'")
                if len(store_changes) > 20:
                    print(f"  ... and {len(store_changes) - 20} more")

        # Apply changes if not dry run
        if not dry_run and changes:
            print("\n\nApplying changes...")
            print("-" * 50)

            for i, change in enumerate(changes):
                product = session.query(Product).get(change['product_id'])
                new_category = get_or_create_category(session, change['new_category'])
                product.category_id = new_category.id

                if (i + 1) % 100 == 0:
                    print(f"  Processed {i + 1}/{len(changes)} products...")

            session.commit()
            print(f"\n✅ Successfully updated {len(changes)} products!")

        elif dry_run and changes:
            print("\n\n*** DRY RUN - No changes were made ***")
            print("Run without --dry-run to apply these changes.")

        else:
            print("\n✅ All products are already correctly categorized!")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv

    # Check for store filter
    store_filter = None
    for arg in sys.argv:
        if arg.startswith('--store='):
            store_filter = arg.split('=')[1]

    recategorize_products(dry_run=dry_run, store_filter=store_filter)
