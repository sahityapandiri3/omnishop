"""
Import scraped Asian Paints textures into the database.

Usage:
    python -m scripts.import_asian_paints_textures
"""

import asyncio
import base64
import json
import os
import re
import sys
from typing import Optional

import aiohttp

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select

from core.database import AsyncSessionLocal
from database.models import TextureType, WallColorFamily, WallTexture, WallTextureVariant

# Map texture type strings to enum values
TYPE_TO_ENUM = {
    "marble": TextureType.MARBLE,
    "velvet": TextureType.VELVET,
    "stone": TextureType.STONE,
    "concrete": TextureType.CONCRETE,
    "3d": TextureType.THREE_D,
    "wall_tile": TextureType.WALL_TILE,
    "stucco": TextureType.STUCCO,
    "rust": TextureType.RUST,
    "other": TextureType.OTHER,
}

# Map color family strings to enum values (for variant color classification)
COLOR_FAMILY_MAP = {
    "white": WallColorFamily.WHITES_OFFWHITES,
    "cream": WallColorFamily.WHITES_OFFWHITES,
    "off white": WallColorFamily.WHITES_OFFWHITES,
    "grey": WallColorFamily.GREYS,
    "gray": WallColorFamily.GREYS,
    "silver": WallColorFamily.GREYS,
    "blue": WallColorFamily.BLUES,
    "navy": WallColorFamily.BLUES,
    "brown": WallColorFamily.BROWNS,
    "beige": WallColorFamily.BROWNS,
    "tan": WallColorFamily.BROWNS,
    "yellow": WallColorFamily.YELLOWS_GREENS,
    "green": WallColorFamily.YELLOWS_GREENS,
    "olive": WallColorFamily.YELLOWS_GREENS,
    "red": WallColorFamily.REDS_ORANGES,
    "orange": WallColorFamily.REDS_ORANGES,
    "terracotta": WallColorFamily.REDS_ORANGES,
    "purple": WallColorFamily.PURPLES_PINKS,
    "pink": WallColorFamily.PURPLES_PINKS,
    "mauve": WallColorFamily.PURPLES_PINKS,
}


def detect_color_family(name: str) -> Optional[WallColorFamily]:
    """Detect color family from variant name."""
    if not name:
        return None

    name_lower = name.lower()
    for keyword, family in COLOR_FAMILY_MAP.items():
        if keyword in name_lower:
            return family

    return None


def get_full_swatch_url(swatch_url: str) -> Optional[str]:
    """Strip the .transform/... thumbnail suffix to get the full-res swatch URL.

    Asian Paints swatch URLs have a thumbnail transform appended:
      .../swatches/TNB1002CMB1007.jpeg.transform/cc-width-60-height-60/image.jpeg
    The base URL without the transform returns the full-resolution swatch:
      .../swatches/TNB1002CMB1007.jpeg
    """
    if not swatch_url:
        return None
    # Strip everything from .transform onwards
    cleaned = re.sub(r"\.transform/.+$", "", swatch_url)
    return cleaned


async def download_swatch(session: aiohttp.ClientSession, swatch_url: str) -> Optional[str]:
    """Download a swatch image and return it as a base64-encoded string."""
    full_url = get_full_swatch_url(swatch_url)
    if not full_url:
        return None
    try:
        async with session.get(full_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                image_bytes = await resp.read()
                return base64.b64encode(image_bytes).decode("utf-8")
            else:
                print(f"    Warning: Failed to download swatch (HTTP {resp.status}): {full_url}")
                return None
    except Exception as e:
        print(f"    Warning: Error downloading swatch: {e}")
        return None


async def import_textures():
    """Import textures from JSON file to database."""

    # Load scraped textures
    json_file = "/Users/sahityapandiri/Omnishop/api/scripts/asian_paints_textures.json"

    if not os.path.exists(json_file):
        print(f"Error: Texture data file not found: {json_file}")
        print("Run the scraper first: python -m scripts.scrape_asian_paints_textures")
        return

    with open(json_file, "r") as f:
        textures = json.load(f)

    print(f"Loaded {len(textures)} textures from {json_file}")

    # Deduplicate variant codes globally
    print("\nDeduplicating variants...")
    used_codes: set = set()

    for texture in textures:
        unique_variants = []
        for variant in texture.get("variants", []):
            code = variant.get("code")
            if code and code not in used_codes and variant.get("image_data"):
                used_codes.add(code)
                unique_variants.append(variant)
        texture["variants"] = unique_variants

    # Filter out textures with no valid variants
    textures = [t for t in textures if t.get("variants")]
    print(f"After deduplication: {len(textures)} textures with {len(used_codes)} unique variants")

    async with aiohttp.ClientSession() as http_session:
        async with AsyncSessionLocal() as session:
            # First, delete all existing textures and variants
            print("\nDeleting existing wall textures...")
            result = await session.execute(delete(WallTextureVariant))
            print(f"Deleted {result.rowcount} existing variants")
            result = await session.execute(delete(WallTexture))
            print(f"Deleted {result.rowcount} existing textures")

            # Insert new textures
            print("\nInserting new textures...")

            total_textures = 0
            total_variants = 0
            total_swatches = 0

            for display_order, texture_data in enumerate(textures):
                name = texture_data.get("name")
                if not name:
                    continue

                variants_with_images = texture_data.get("variants", [])
                if not variants_with_images:
                    print(f"  Skipping {name} - no variants with images")
                    continue

                # Map texture type
                type_str = texture_data.get("texture_type", "other")
                texture_type = TYPE_TO_ENUM.get(type_str, TextureType.OTHER)

                # Create texture
                texture = WallTexture(
                    name=name,
                    collection=texture_data.get("collection"),
                    texture_type=texture_type,
                    brand=texture_data.get("brand", "Asian Paints"),
                    description=texture_data.get("description"),
                    is_active=True,
                    display_order=display_order,
                )
                session.add(texture)
                await session.flush()  # Get the ID

                print(f"  Added texture: {name} (ID: {texture.id})")
                total_textures += 1

                # Add variants
                for variant_order, variant_data in enumerate(variants_with_images):
                    code = variant_data.get("code")
                    if not code:
                        code = f"{name}_{variant_order}"

                    # Detect color family from variant name
                    color_family = detect_color_family(variant_data.get("name", ""))

                    # Download swatch image (the actual texture pattern for AI visualization)
                    raw_swatch_url = variant_data.get("swatch_url")
                    swatch_data = None
                    swatch_url = None
                    if raw_swatch_url:
                        swatch_url = get_full_swatch_url(raw_swatch_url)
                        swatch_data = await download_swatch(http_session, raw_swatch_url)
                        if swatch_data:
                            total_swatches += 1

                    variant = WallTextureVariant(
                        texture_id=texture.id,
                        code=code,
                        name=variant_data.get("name"),
                        image_data=variant_data.get("image_data"),
                        image_url=variant_data.get("image_url"),
                        product_url=variant_data.get("product_url"),
                        swatch_data=swatch_data,
                        swatch_url=swatch_url,
                        color_family=color_family,
                        is_active=True,
                        display_order=variant_order,
                    )
                    session.add(variant)
                    total_variants += 1

                print(f"    Added {len(variants_with_images)} variants")

            await session.commit()

            print(f"\n{'='*50}")
            print(f"Successfully imported {total_textures} textures with {total_variants} variants!")
            print(f"Swatch images downloaded: {total_swatches}/{total_variants}")
            print(f"{'='*50}")

            # Verify by texture type
            print("\nVerification by texture type:")
            for type_name, type_enum in TYPE_TO_ENUM.items():
                result = await session.execute(select(WallTexture).where(WallTexture.texture_type == type_enum))
                count = len(result.scalars().all())
                if count > 0:
                    print(f"  {type_name}: {count} textures")


async def main():
    print("=" * 60)
    print("Asian Paints Texture Importer")
    print("=" * 60)
    await import_textures()


if __name__ == "__main__":
    asyncio.run(main())
