"""
Scrape Nitco floor tiles and import directly into the database.

Fetches the listing page, extracts tile links, visits each detail page
to get specs, downloads swatch images, and inserts into floor_tiles table.

Usage:
    cd api
    python scripts/scrape_nitco_tiles.py
    python scripts/scrape_nitco_tiles.py --download-images
    python scripts/scrape_nitco_tiles.py --limit 10   # scrape only first 10 tiles
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

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

BASE_URL = "https://www.nitco.in"
LISTING_URLS = [
    "https://www.nitco.in/living-room-floor-tiles/",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}
DELAY_BETWEEN_REQUESTS = 1.0  # seconds


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch a page and return its HTML."""
    try:
        response = await client.get(url, headers=HEADERS, timeout=30.0, follow_redirects=True)
        if response.status_code == 200:
            return response.text
        else:
            logger.warning(f"HTTP {response.status_code} for {url}")
            return None
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None


async def download_image(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Download an image and return as base64 data URI."""
    if not url:
        return None
    try:
        response = await client.get(url, headers=HEADERS, timeout=30.0, follow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            b64 = base64.b64encode(response.content).decode("utf-8")
            return f"data:{content_type};base64,{b64}"
        return None
    except Exception as e:
        logger.warning(f"Error downloading image {url}: {e}")
        return None


def extract_tile_links(html: str) -> List[dict]:
    """Extract tile links and basic info from listing page."""
    soup = BeautifulSoup(html, "html.parser")
    tiles = []

    # Find all links to product-details pages
    for a_tag in soup.find_all("a", href=re.compile(r"/product-details/.*floor-tiles/")):
        href = a_tag.get("href", "")
        if not href:
            continue

        url = urljoin(BASE_URL, href)

        # Extract product code from URL (last path segment)
        parts = href.rstrip("/").split("/")
        product_code = parts[-1] if parts else None

        # Extract name from URL (second-to-last segment)
        name_slug = parts[-2] if len(parts) >= 2 else None
        name = name_slug.replace("-", " ").title() if name_slug else None

        # Try to get swatch image from listing
        img_tag = a_tag.find("img")
        listing_image = None
        if img_tag:
            listing_image = img_tag.get("src") or img_tag.get("data-src")
            if listing_image:
                listing_image = urljoin(BASE_URL, listing_image)

        tiles.append(
            {
                "url": url,
                "product_code": product_code,
                "name": name,
                "listing_image": listing_image,
            }
        )

    # Deduplicate by product_code
    seen = set()
    unique = []
    for t in tiles:
        if t["product_code"] not in seen:
            seen.add(t["product_code"])
            unique.append(t)

    return unique


def parse_detail_page(html: str, url: str, listing_info: dict) -> Optional[dict]:
    """Parse a tile detail page and extract all specs."""
    soup = BeautifulSoup(html, "html.parser")

    # Product name — try h1 first
    name = None
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
    if not name:
        name = listing_info.get("name", "Unknown")

    # Product code from URL
    product_code = listing_info.get("product_code", "")
    # Clean up the code - extract the uppercase part
    code_upper = product_code.upper()

    # Extract specs from Nitco's group-variation structure:
    #   <div class="group-variation clearfix">
    #     <div class="vari-tiles col-variation-lab">Finish</div>
    #     <div class="col-variation-val"><span>Glossy</span></div>
    #   </div>
    specs = {}
    for group in soup.find_all("div", class_="group-variation"):
        label_el = group.find("div", class_="col-variation-lab")
        value_el = group.find("div", class_="col-variation-val")
        if label_el and value_el:
            label = label_el.get_text(strip=True).lower()
            value = value_el.get_text(strip=True)
            if label and value:
                specs[label] = value

    # Also try table rows as fallback
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                if label and value and label not in specs:
                    specs[label] = value

    # Extract specific fields
    size = specs.get("size", "") or specs.get("tile size", "") or specs.get("dimensions", "")
    finish = specs.get("finish", "") or specs.get("surface finish", "")
    look = specs.get("looks like", "") or specs.get("look", "") or specs.get("design look", "")
    color = specs.get("colour", "") or specs.get("color", "")
    material = specs.get("material", "") or specs.get("body type", "") or specs.get("tile type", "")

    # Parse size into width/height
    size_width_mm = None
    size_height_mm = None
    if size:
        size_match = re.search(r"(\d+)\s*[xX×]\s*(\d+)", size)
        if size_match:
            size_width_mm = int(size_match.group(1))
            size_height_mm = int(size_match.group(2))

    # If size not found in specs, try to parse from product code
    if not size_width_mm:
        code_size_match = re.search(r"(\d{3,4})[xX](\d{3,4})", code_upper)
        if code_size_match:
            size_width_mm = int(code_size_match.group(1))
            size_height_mm = int(code_size_match.group(2))
            if not size:
                size = f"{size_width_mm}x{size_height_mm} mm"

    # Build image URLs from product code pattern
    # Nitco uses: nitcomedia/tiles/{type}/main/{CODE}.jpg
    # Strip the "NT" prefix from product code for image URLs
    image_code = code_upper
    if image_code.startswith("NT"):
        image_code = image_code[2:]

    swatch_url = f"{BASE_URL}/nitcomedia/tiles/swatch/main/{image_code}.jpg"
    looks_url = f"{BASE_URL}/nitcomedia/tiles/looks/main/{image_code}.jpg"
    scale_url = f"{BASE_URL}/nitcomedia/tiles/scale/main/{image_code}.jpg"

    # Use listing image as fallback
    image_url = listing_info.get("listing_image") or swatch_url

    return {
        "product_code": product_code,
        "name": name,
        "description": specs.get("description"),
        "size": size or "Unknown",
        "size_width_mm": size_width_mm,
        "size_height_mm": size_height_mm,
        "finish": finish or None,
        "look": look or None,
        "color": color or None,
        "material": material or None,
        "vendor": "Nitco",
        "product_url": url,
        "swatch_url": swatch_url,
        "image_url": image_url,
        "additional_images": [looks_url, scale_url],
    }


async def scrape_and_import(download_images: bool = False, limit: int = None):
    """Main scrape + import pipeline."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with httpx.AsyncClient() as client:
        # Step 1: Fetch listing pages and extract tile links
        all_tiles = []
        for listing_url in LISTING_URLS:
            logger.info(f"Fetching listing: {listing_url}")
            html = await fetch_page(client, listing_url)
            if not html:
                logger.error(f"Failed to fetch listing: {listing_url}")
                continue
            tiles = extract_tile_links(html)
            logger.info(f"Found {len(tiles)} tiles on {listing_url}")
            all_tiles.extend(tiles)

        if not all_tiles:
            logger.error("No tiles found on any listing page")
            await engine.dispose()
            return

        # Deduplicate across listings
        seen = set()
        unique_tiles = []
        for t in all_tiles:
            if t["product_code"] not in seen:
                seen.add(t["product_code"])
                unique_tiles.append(t)

        logger.info(f"Total unique tiles to scrape: {len(unique_tiles)}")

        if limit:
            unique_tiles = unique_tiles[:limit]
            logger.info(f"Limited to first {limit} tiles")

        # Step 2: Visit each detail page and extract specs
        scraped = []
        for i, tile_info in enumerate(unique_tiles):
            logger.info(f"[{i+1}/{len(unique_tiles)}] Scraping: {tile_info['name']}")
            html = await fetch_page(client, tile_info["url"])
            if not html:
                logger.warning(f"Failed to fetch detail page: {tile_info['url']}")
                continue

            tile_data = parse_detail_page(html, tile_info["url"], tile_info)
            if tile_data:
                scraped.append(tile_data)

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        logger.info(f"Successfully scraped {len(scraped)} tile detail pages")

        # Step 3: Import into database
        async with async_session() as session:
            imported = 0
            skipped = 0

            for tile_data in scraped:
                product_code = tile_data["product_code"]

                # Check if already exists
                result = await session.execute(select(FloorTile).where(FloorTile.product_code == product_code))
                if result.scalar_one_or_none():
                    logger.debug(f"Skipping existing: {product_code}")
                    skipped += 1
                    continue

                # Download images if requested
                swatch_data = None
                image_data = None
                if download_images:
                    logger.info(f"  Downloading swatch: {tile_data['swatch_url']}")
                    swatch_data = await download_image(client, tile_data["swatch_url"])
                    if tile_data["image_url"]:
                        image_data = await download_image(client, tile_data["image_url"])
                    await asyncio.sleep(0.5)

                tile = FloorTile(
                    product_code=product_code,
                    name=tile_data["name"],
                    description=tile_data.get("description"),
                    size=tile_data["size"],
                    size_width_mm=tile_data["size_width_mm"],
                    size_height_mm=tile_data["size_height_mm"],
                    finish=tile_data["finish"],
                    look=tile_data["look"],
                    color=tile_data["color"],
                    material=tile_data["material"],
                    vendor=tile_data["vendor"],
                    product_url=tile_data["product_url"],
                    swatch_data=swatch_data,
                    swatch_url=tile_data["swatch_url"],
                    image_url=tile_data["image_url"],
                    image_data=image_data,
                    additional_images=tile_data["additional_images"],
                    is_active=True,
                )
                session.add(tile)
                imported += 1

                if imported % 25 == 0:
                    await session.commit()
                    logger.info(f"  Committed {imported} tiles...")

            await session.commit()
            logger.info(f"Import complete: {imported} imported, {skipped} skipped")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Scrape Nitco tiles and import to DB")
    parser.add_argument("--download-images", action="store_true", help="Download swatch/thumbnail images as base64")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tiles to scrape")
    args = parser.parse_args()

    asyncio.run(scrape_and_import(download_images=args.download_images, limit=args.limit))


if __name__ == "__main__":
    main()
