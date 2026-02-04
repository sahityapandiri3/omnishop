"""
Import Nitco floor tiles into the database.

Reads spider output (JSONL) and populates the floor_tiles table.
Also downloads and base64-encodes swatch images for AI visualization.

Usage:
    cd api
    python scripts/import_nitco_tiles.py --input scripts/nitco_tiles_output.jsonl
    python scripts/import_nitco_tiles.py --input scripts/nitco_tiles_output.jsonl --download-images
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
from pathlib import Path

import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from database.models import FloorTile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def download_and_encode_image(url: str, client: httpx.AsyncClient) -> str | None:
    """Download an image and return it as a base64 data URI."""
    if not url:
        return None
    try:
        response = await client.get(url, timeout=30.0)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "image/jpeg")
            if ";" in content_type:
                content_type = content_type.split(";")[0].strip()
            b64 = base64.b64encode(response.content).decode("utf-8")
            return f"data:{content_type};base64,{b64}"
        else:
            logger.warning(f"Failed to download {url}: HTTP {response.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Error downloading {url}: {e}")
        return None


async def import_tiles(input_path: str, download_images: bool = False):
    """Import tiles from JSONL file into the database."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    # Convert postgres:// to postgresql+asyncpg://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Read input file
    tiles_data = []
    with open(input_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                tiles_data.append(json.loads(line))

    logger.info(f"Read {len(tiles_data)} tiles from {input_path}")

    async with httpx.AsyncClient() as http_client:
        async with async_session() as session:
            imported = 0
            skipped = 0

            for tile_data in tiles_data:
                product_code = tile_data.get("product_code")
                if not product_code:
                    logger.warning(f"Skipping tile without product_code: {tile_data.get('name')}")
                    skipped += 1
                    continue

                # Check if already exists
                result = await session.execute(select(FloorTile).where(FloorTile.product_code == product_code))
                existing = result.scalar_one_or_none()
                if existing:
                    logger.debug(f"Skipping existing tile: {product_code}")
                    skipped += 1
                    continue

                # Download images if requested
                swatch_data = None
                image_data = None
                if download_images:
                    swatch_url = tile_data.get("swatch_url")
                    image_url = tile_data.get("image_url")
                    if swatch_url:
                        swatch_data = await download_and_encode_image(swatch_url, http_client)
                    if image_url:
                        image_data = await download_and_encode_image(image_url, http_client)

                tile = FloorTile(
                    product_code=product_code,
                    name=tile_data.get("name", "Unknown"),
                    description=tile_data.get("description"),
                    size=tile_data.get("size", "Unknown"),
                    size_width_mm=tile_data.get("size_width_mm"),
                    size_height_mm=tile_data.get("size_height_mm"),
                    finish=tile_data.get("finish"),
                    look=tile_data.get("look"),
                    color=tile_data.get("color"),
                    material=tile_data.get("material"),
                    vendor=tile_data.get("vendor", "Nitco"),
                    product_url=tile_data.get("product_url"),
                    swatch_data=swatch_data,
                    swatch_url=tile_data.get("swatch_url"),
                    image_url=tile_data.get("image_url"),
                    image_data=image_data,
                    additional_images=tile_data.get("additional_images"),
                    is_active=True,
                )
                session.add(tile)
                imported += 1

                if imported % 50 == 0:
                    await session.commit()
                    logger.info(f"Committed {imported} tiles so far...")

            await session.commit()
            logger.info(f"Import complete: {imported} imported, {skipped} skipped")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Import Nitco floor tiles into database")
    parser.add_argument("--input", required=True, help="Path to JSONL file from spider output")
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="Download and base64-encode images (swatch + thumbnail)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    asyncio.run(import_tiles(args.input, args.download_images))


if __name__ == "__main__":
    main()
