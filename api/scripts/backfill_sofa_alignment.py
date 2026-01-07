"""
Backfill script to extract sofa alignment (left/right) from product names.

This script:
1. Finds all sectional/L-shape sofas
2. Extracts alignment from product name
3. Stores as ProductAttribute with attribute_name='sofa_alignment'
4. Regenerates embeddings for updated products

Usage:
    python -m scripts.backfill_sofa_alignment [--dry-run] [--regenerate-embeddings]
"""
import argparse
import asyncio
import logging
import re
import sys
from datetime import datetime
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from sqlalchemy import and_, or_, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from core.config import settings  # noqa: E402
from database.models import Product, ProductAttribute  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_alignment_from_text(text: str) -> Optional[str]:
    """
    Extract sofa alignment from product name or description.

    Returns:
        'left', 'right', 'reversible', or None
    """
    if not text:
        return None

    text_lower = text.lower()

    # Check for reversible first (higher priority)
    reversible_patterns = [
        r"\breversible\b",
        r"\binterchangeable\b",
        r"\bconvertible.*(?:left|right)\b",  # "convertible to left or right"
    ]
    for pattern in reversible_patterns:
        if re.search(pattern, text_lower):
            return "reversible"

    # Check for right alignment
    right_patterns = [
        r"\bright[\s-]*align",  # "right aligned", "right-aligned"
        r"\bright[\s-]*facing\b",  # "right facing"
        r"\bright[\s-]*arm\b",  # "right arm"
        r"\bright[\s-]*chaise\b",  # "right chaise"
        r"\brhs\b",  # "RHS"
        r"\bright[\s-]*corner\b",  # "right corner"
        r"\bright[\s-]*hand\b",  # "right hand"
        r"\bright[\s-]*longchair\b",  # "right longchair"
        r"\bright[\s-]*sectional\b",  # "right sectional"
        r"\bright[\s-]*l[\s-]*shape",  # "right L-shape"
        r"\bl[\s-]*shape[d]?[\s-]*right\b",  # "L-shaped right"
    ]
    for pattern in right_patterns:
        if re.search(pattern, text_lower):
            return "right"

    # Check for left alignment
    left_patterns = [
        r"\bleft[\s-]*align",  # "left aligned", "left-aligned"
        r"\bleft[\s-]*facing\b",  # "left facing"
        r"\bleft[\s-]*arm\b",  # "left arm"
        r"\bleft[\s-]*chaise\b",  # "left chaise"
        r"\blhs\b",  # "LHS"
        r"\bleft[\s-]*corner\b",  # "left corner"
        r"\bleft[\s-]*hand\b",  # "left hand"
        r"\bleft[\s-]*longchair\b",  # "left longchair"
        r"\bleft[\s-]*sectional\b",  # "left sectional"
        r"\bleft[\s-]*l[\s-]*shape",  # "left L-shape"
        r"\bl[\s-]*shape[d]?[\s-]*left\b",  # "L-shaped left"
    ]
    for pattern in left_patterns:
        if re.search(pattern, text_lower):
            return "left"

    return None


def extract_alignment_from_specifications(attributes: dict) -> Optional[str]:
    """
    Extract sofa alignment from product specifications/attributes.

    Looks for common specification keys like 'configuration', 'orientation',
    'chaise position', 'arm position', etc.

    Args:
        attributes: Product attributes dict from specifications

    Returns:
        'left', 'right', 'reversible', or None
    """
    if not attributes:
        return None

    # Keys that might contain alignment info
    alignment_keys = [
        "configuration",
        "orientation",
        "chaise_position",
        "chaise position",
        "arm_position",
        "arm position",
        "facing",
        "direction",
        "type",
        "sofa_type",
        "sofa type",
        "shape",
        "layout",
        "seating_configuration",
        "seating configuration",
        "corner_type",
        "corner type",
        "aligned",
    ]

    for key in attributes:
        key_lower = key.lower()
        # Check if this key might contain alignment info
        if any(ak in key_lower for ak in alignment_keys) or "align" in key_lower or "facing" in key_lower:
            value = attributes[key].lower()

            # Check for reversible
            if "reversible" in value or "interchangeable" in value:
                return "reversible"

            # Check for right
            if re.search(r"\bright\b", value):
                return "right"

            # Check for left
            if re.search(r"\bleft\b", value):
                return "left"

    return None


def is_sectional_sofa(name: str, description: str = None) -> bool:
    """Check if product is a sectional/L-shape sofa."""
    text = f"{name} {description or ''}".lower()

    sectional_patterns = [
        r"\bl[\s-]*shape",  # "L-shape", "L shape"
        r"\bsectional\b",  # "sectional"
        r"\bcorner\s+sofa\b",  # "corner sofa"
        r"\bmodular\s+sofa\b",  # "modular sofa"
        r"\bchaise\b",  # has chaise
    ]

    # Must also be a sofa
    is_sofa = bool(re.search(r"\bsofa\b|\bcouch\b|\bsettee\b", text))

    if not is_sofa:
        return False

    for pattern in sectional_patterns:
        if re.search(pattern, text):
            return True

    return False


async def backfill_alignments(dry_run: bool = False, regenerate_embeddings: bool = False, database_url: str = None):
    """
    Main backfill function to extract and store sofa alignments.
    """
    # Create database connection - use provided URL or fall back to settings
    import os

    database_url = database_url or os.environ.get("DATABASE_URL") or settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {
        "total_products": 0,
        "sectional_sofas": 0,
        "alignments_found": 0,
        "left": 0,
        "right": 0,
        "reversible": 0,
        "already_has_alignment": 0,
        "created": 0,
        "updated": 0,
        "found_in_name": 0,
        "found_in_specs": 0,
        "found_in_description": 0,
    }

    products_to_update_embeddings = []

    async with async_session() as session:
        # Find all sofas that might be sectional
        query = select(Product).where(
            and_(
                Product.is_available.is_(True),
                or_(
                    Product.name.ilike("%l%shape%"),
                    Product.name.ilike("%sectional%"),
                    Product.name.ilike("%corner%sofa%"),
                    Product.name.ilike("%chaise%"),
                    Product.name.ilike("%modular%sofa%"),
                    Product.name.ilike("%aligned%"),
                ),
            )
        )

        result = await session.execute(query)
        products = result.scalars().all()
        stats["total_products"] = len(products)

        logger.info(f"Found {len(products)} potential sectional sofa products")

        for product in products:
            # Check if it's actually a sectional sofa
            if not is_sectional_sofa(product.name, product.description):
                continue

            stats["sectional_sofas"] += 1

            # Extract alignment from multiple sources (priority order)
            alignment = None
            found_in = None

            # 1. Try product name first (most reliable)
            alignment = extract_alignment_from_text(product.name)
            if alignment:
                found_in = "name"

            # 2. Try existing attributes/specifications
            if not alignment:
                # Fetch existing attributes for this product
                attrs_query = select(ProductAttribute).where(ProductAttribute.product_id == product.id)
                attrs_result = await session.execute(attrs_query)
                existing_attrs = {attr.attribute_name: attr.attribute_value for attr in attrs_result.scalars().all()}
                alignment = extract_alignment_from_specifications(existing_attrs)
                if alignment:
                    found_in = "specs"

            # 3. Try product description
            if not alignment and product.description:
                alignment = extract_alignment_from_text(product.description)
                if alignment:
                    found_in = "description"

            if not alignment:
                continue

            stats["alignments_found"] += 1
            stats[alignment] += 1
            stats[f"found_in_{found_in}"] += 1

            # Check if alignment attribute already exists
            existing_query = select(ProductAttribute).where(
                and_(ProductAttribute.product_id == product.id, ProductAttribute.attribute_name == "sofa_alignment")
            )
            existing_result = await session.execute(existing_query)
            existing_attr = existing_result.scalar_one_or_none()

            if existing_attr:
                if existing_attr.attribute_value == alignment:
                    stats["already_has_alignment"] += 1
                    continue
                else:
                    # Update existing attribute
                    if not dry_run:
                        existing_attr.attribute_value = alignment
                        existing_attr.updated_at = datetime.utcnow()
                    stats["updated"] += 1
                    logger.info(f"Updated alignment for '{product.name[:60]}': {existing_attr.attribute_value} -> {alignment}")
            else:
                # Create new attribute
                if not dry_run:
                    new_attr = ProductAttribute(
                        product_id=product.id,
                        attribute_name="sofa_alignment",
                        attribute_value=alignment,
                        attribute_type="text",
                        extraction_method="backfill_script",
                        confidence_score=0.95,
                    )
                    session.add(new_attr)
                stats["created"] += 1
                logger.info(f"Added alignment '{alignment}' for '{product.name[:60]}'")

            products_to_update_embeddings.append(product.id)

        if not dry_run:
            await session.commit()
            logger.info("Committed alignment changes to database")

    # Print summary
    print("\n" + "=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)
    print(f"Total products scanned:     {stats['total_products']}")
    print(f"Sectional sofas found:      {stats['sectional_sofas']}")
    print(f"Alignments extracted:       {stats['alignments_found']}")
    print(f"  - Left aligned:           {stats['left']}")
    print(f"  - Right aligned:          {stats['right']}")
    print(f"  - Reversible:             {stats['reversible']}")
    print("Found in:")
    print(f"  - Product name:           {stats['found_in_name']}")
    print(f"  - Specifications:         {stats['found_in_specs']}")
    print(f"  - Description:            {stats['found_in_description']}")
    print(f"Already had alignment:      {stats['already_has_alignment']}")
    print(f"New alignments created:     {stats['created']}")
    print(f"Alignments updated:         {stats['updated']}")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN] No changes were made to the database.")

    # Regenerate embeddings if requested
    if regenerate_embeddings and products_to_update_embeddings and not dry_run:
        print(f"\nRegenerating embeddings for {len(products_to_update_embeddings)} products...")
        await regenerate_product_embeddings(products_to_update_embeddings, engine)

    await engine.dispose()
    return stats


async def regenerate_product_embeddings(product_ids: list, engine):
    """Regenerate embeddings for products with updated alignment."""
    try:
        from services.embedding_service import get_embedding_service

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        embedding_service = get_embedding_service()

        async with async_session() as session:
            stats = await embedding_service.batch_generate_embeddings(
                product_ids, session, progress_callback=lambda p, t: print(f"  Progress: {p}/{t}", end="\r")
            )

        print(f"\nEmbedding regeneration complete: {stats}")

    except Exception as e:
        logger.error(f"Error regenerating embeddings: {e}")
        print(f"\nWarning: Could not regenerate embeddings: {e}")
        print("You can regenerate them later using: python -m scripts.backfill_embeddings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill sofa alignment attributes")
    parser.add_argument("--dry-run", action="store_true", help="Run without making changes")
    parser.add_argument("--regenerate-embeddings", action="store_true", help="Regenerate embeddings for updated products")

    args = parser.parse_args()

    if args.dry_run:
        print("Running in DRY RUN mode - no changes will be made\n")

    asyncio.run(backfill_alignments(dry_run=args.dry_run, regenerate_embeddings=args.regenerate_embeddings))
