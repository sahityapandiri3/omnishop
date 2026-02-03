"""
Scrape Asian Paints interior textures using Playwright.

This script:
1. Visits the main textures page and loads all products via "Load More"
2. Gets unique parent texture URLs (one per texture family)
3. Visits each product page to extract ALL color variants from data-skucode
4. Constructs image URLs directly from SKU (predictable pattern)

Key insight: Image URLs follow a predictable pattern based on SKU:
- TNB* (exterior): /room-shots/exterior-texture-room-shots-asian-paints-{SKU}.jpeg
- TXT* (interior): /room-shots/interior-texture-room-shots-asian-paints-{SKU}.jpg
- IMP* (infinitex): /wall-shots/{SKU}.png
- Others (IDC, LIC, etc.): /wall-shots/{SKU}.jpg

Usage:
    python -m scripts.scrape_asian_paints_textures
"""

import asyncio
import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from playwright.async_api import async_playwright

# Texture type mapping based on name patterns
TEXTURE_TYPE_KEYWORDS = {
    "marble": "marble",
    "velvet": "velvet",
    "stone": "stone",
    "concrete": "concrete",
    "3d": "3d",
    "tile": "wall_tile",
    "stucco": "stucco",
    "rust": "rust",
    "metallic": "metallic",
}


def detect_texture_type(name: str) -> str:
    """Detect texture type from name."""
    name_lower = name.lower()
    for keyword, type_val in TEXTURE_TYPE_KEYWORDS.items():
        if keyword in name_lower:
            return type_val
    return "other"


def extract_base_name(full_name: str, url: str) -> str:
    """Extract the base texture name (without variant code)."""
    # Remove code from name like "Metallics Bandhej TNB1002CMB1007" -> "Metallics Bandhej"
    clean_name = re.sub(r"\s*[A-Z]{2,3}\d+CMB\d+\s*", "", full_name, flags=re.IGNORECASE).strip()

    if not clean_name or len(clean_name) < 3:
        # Extract from URL: metallics-bandhej-tnb1002cmb1007.html -> Metallics Bandhej
        url_name = url.split("/")[-1].replace(".html", "")
        url_name = re.sub(r"-[a-z]{2,3}\d+cmb\d+$", "", url_name, flags=re.IGNORECASE)
        clean_name = url_name.replace("-", " ").title()

    return clean_name


def extract_sku_from_url(url: str) -> Optional[str]:
    """Extract SKU code from URL (e.g., TNB1002CMB1007)."""
    match = re.search(r"([A-Z]{2,3}\d+CMB\d+)", url, re.IGNORECASE)
    return match.group(1).upper() if match else None


def construct_image_urls(sku: str) -> List[str]:
    """
    Construct possible image URLs directly from SKU code.

    This is the key fix - instead of scraping DOM for images (which often fails),
    we construct URLs directly since they follow predictable patterns.

    URL patterns vary by SKU prefix:
    - TNB* (exterior metallics): /room-shots/exterior-texture-room-shots-asian-paints-{SKU}.jpeg
    - TXT* (interior textures): /room-shots/interior-texture-room-shots-asian-paints-{SKU}.jpg
    - IMP* (infinitex impressions): /wall-shots/{SKU}.png
    - IDC, LIC, LXE, MSC, NIC (standard interior): /wall-shots/{SKU}.jpg

    Returns list of URL options to try in order.
    """
    sku_upper = sku.upper()
    base_url = "https://static.asianpaints.com/content/dam/asian_paints/textures"

    # Build list of URLs to try based on SKU prefix
    if sku_upper.startswith("TNB"):
        # Exterior metallics - room-shots with "exterior-texture" naming
        return [
            f"{base_url}/room-shots/exterior-texture-room-shots-asian-paints-{sku_upper}.jpeg",
            f"{base_url}/room-shots/exterior-texture-room-shots-asian-paints-{sku_upper}.jpg",
            f"{base_url}/wall-shots/{sku_upper}.jpg",
            f"{base_url}/wall-shots/{sku_upper}.png",
        ]
    elif sku_upper.startswith("TXT"):
        # Interior textures - room-shots with "interior-texture" naming
        return [
            f"{base_url}/room-shots/interior-texture-room-shots-asian-paints-{sku_upper}.jpg",
            f"{base_url}/room-shots/interior-texture-room-shots-asian-paints-{sku_upper}.jpeg",
            f"{base_url}/wall-shots/{sku_upper}.jpg",
            f"{base_url}/wall-shots/{sku_upper}.png",
        ]
    elif sku_upper.startswith("IMP"):
        # Infinitex impressions - wall-shots with PNG extension
        return [
            f"{base_url}/wall-shots/{sku_upper}.png",
            f"{base_url}/wall-shots/{sku_upper}.jpg",
            f"{base_url}/room-shots/interior-texture-room-shots-asian-paints-{sku_upper}.jpg",
        ]
    else:
        # Standard interior textures (IDC, LIC, LXE, MSC, NIC, etc.)
        return [
            f"{base_url}/wall-shots/{sku_upper}.jpg",
            f"{base_url}/wall-shots/{sku_upper}.png",
            f"{base_url}/room-shots/interior-texture-room-shots-asian-paints-{sku_upper}.jpg",
            f"{base_url}/room-shots/exterior-texture-room-shots-asian-paints-{sku_upper}.jpeg",
        ]


async def download_image_as_base64(url: str, silent: bool = False) -> Optional[str]:
    """Download an image and convert to base64."""
    try:
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://www.asianpaints.com" + url

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
            if response.status_code == 200:
                # Verify it's actually an image (not an error page)
                content_type = response.headers.get("content-type", "")
                if "image" in content_type and len(response.content) > 5000:
                    return base64.b64encode(response.content).decode("utf-8")
                elif not silent:
                    print(f"    Not a valid image: {url[:60]}... (type: {content_type}, size: {len(response.content)})")
            elif not silent:
                print(f"    HTTP {response.status_code}: {url[:60]}...")
    except Exception as e:
        if not silent:
            print(f"    Error downloading {url[:50]}...: {e}")
    return None


async def download_with_fallbacks(url_options: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Try downloading from multiple URLs in order.

    Returns tuple of (base64_data, url_used). Returns (None, None) if all fail.
    """
    for url in url_options:
        data = await download_image_as_base64(url, silent=True)
        if data:
            return data, url

    return None, None


async def verify_image_url(url: str) -> bool:
    """Check if an image URL exists and returns valid image data."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.head(
                url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                return "image" in content_type
    except Exception:
        pass
    return False


async def extract_variants_from_page(page, url: str) -> dict:
    """
    Visit a product page to extract ALL color variants and description.

    Returns dict with:
    - variants: list of {sku, swatch_url}
    - description: product description text
    - name: product name from page
    """
    result: Dict[str, Any] = {
        "variants": [],
        "description": None,
        "name": None,
    }

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)

        # Close popups
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        page_data = await page.evaluate(
            """
            () => {
                const result = {
                    variants: [],
                    description: null,
                    name: null
                };

                // Extract ALL color variant SKUs from colorwrap/data-skucode
                const skuElements = document.querySelectorAll('[data-skucode]');
                const seen = new Set();
                for (const el of skuElements) {
                    const sku = el.dataset.skucode;
                    if (sku && sku.toUpperCase().includes('CMB') && !seen.has(sku.toUpperCase())) {
                        seen.add(sku.toUpperCase());
                        // Look for swatch image
                        const img = el.querySelector('img');
                        result.variants.push({
                            sku: sku.toUpperCase(),
                            swatchImg: img ? img.src : null
                        });
                    }
                }

                // Get product name from JSON-LD or page title
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                for (const script of scripts) {
                    try {
                        const data = JSON.parse(script.textContent);
                        if (data['@type'] === 'Product') {
                            result.name = data.name;
                            if (data.description) {
                                const desc = data.description.trim();
                                if (desc.length > 30 && !desc.includes('finalising')) {
                                    result.description = desc;
                                }
                            }
                            break;
                        }
                    } catch (e) {}
                }

                // Fallback name from h1
                if (!result.name) {
                    const h1 = document.querySelector('h1');
                    if (h1) result.name = h1.textContent.trim();
                }

                // Fallback description from data-parenttext
                if (!result.description) {
                    const moreBtn = document.querySelector('.js-moreBtn, [data-parenttext]');
                    if (moreBtn && moreBtn.dataset.parenttext) {
                        const text = moreBtn.dataset.parenttext;
                        if (text.length > 30 && !text.includes('Swatch') && !text.includes('finalising')) {
                            result.description = text;
                        }
                    }
                }

                return result;
            }
        """
        )

        result["variants"] = page_data.get("variants", [])
        result["description"] = page_data.get("description")
        result["name"] = page_data.get("name")

    except Exception as e:
        print(f"    Error extracting variants from {url[:50]}...: {e}")

    return result


async def scrape_textures():
    """
    Scrape textures from Asian Paints.

    Improved flow:
    1. Load main listing page, click "Load More" to get all products
    2. Group product URLs by base texture name (one URL per parent texture)
    3. Visit each product page to extract ALL color variants from data-skucode
    4. Construct image URLs directly from SKU for each variant
    """

    all_textures: Dict[str, dict] = {}  # Keyed by base texture name

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        page = await context.new_page()

        print("\n" + "=" * 60)
        print("Step 1: Loading main textures listing page")
        print("=" * 60)

        try:
            await page.goto("https://www.asianpaints.com/interior-textures.html", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)

            # Close cookie popup
            try:
                accept_btn = page.locator("#onetrust-accept-btn-handler")
                if await accept_btn.count() > 0:
                    await accept_btn.first.click(timeout=5000)
                    await page.wait_for_timeout(1000)
            except Exception:
                pass

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)

            # Click "Load More" to get all products
            print("\n  Loading all products (clicking 'Load More')...")
            load_more_clicks = 0
            max_clicks = 50
            last_product_count = 0

            while load_more_clicks < max_clicks:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)

                current_count = await page.evaluate(
                    """
                    () => document.querySelectorAll('a[href*="/interior-textures/"][href$=".html"]').length
                """
                )

                try:
                    clicked = await page.evaluate(
                        """
                        () => {
                            const btns = document.querySelectorAll('.js-load-more-btn, button[data-loadmore-on-click], .load-more-btn, [class*="load-more"]');
                            for (const btn of btns) {
                                if (btn.offsetParent !== null && !btn.disabled) {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """
                    )

                    if clicked:
                        load_more_clicks += 1
                        print(f"    Clicked Load More ({load_more_clicks}) - {current_count} products loaded")
                        await page.wait_for_timeout(2500)

                        new_count = await page.evaluate(
                            """
                            () => document.querySelectorAll('a[href*="/interior-textures/"][href$=".html"]').length
                        """
                        )
                        if new_count == last_product_count and load_more_clicks > 3:
                            print("    No new products loaded, stopping")
                            break
                        last_product_count = new_count
                    else:
                        print("    No more 'Load More' button visible")
                        break
                except Exception as e:
                    print(f"    Error clicking: {e}")
                    break

            # Extract all product URLs from listing
            print("\n" + "=" * 60)
            print("Step 2: Extracting unique parent texture URLs")
            print("=" * 60)

            product_list = await page.evaluate(
                """
                () => {
                    const results = [];
                    const seen = new Set();

                    const links = document.querySelectorAll('a[href*="/interior-textures/"][href$=".html"]');

                    for (const link of links) {
                        const href = link.href;
                        if (!href.match(/[a-z]{2,3}\\d+cmb\\d+/i)) continue;
                        if (seen.has(href)) continue;
                        seen.add(href);

                        const card = link.closest('.plp-card, .product-card, article, [class*="card"]');
                        const nameEl = card?.querySelector('h2, h3, h4, .name, .title, [class*="prodName"]');
                        let name = nameEl?.textContent?.trim() || '';

                        if (!name || name === '+more') {
                            const urlPart = href.split('/').pop().replace('.html', '');
                            name = urlPart.replace(/-/g, ' ').replace(/[a-z]{2,3}\\d+cmb\\d+$/i, '').trim();
                            name = name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                        }

                        results.push({ url: href, name: name });
                    }

                    return results;
                }
            """
            )

            print(f"  Found {len(product_list)} product URLs from listing")

            # Group by base texture name to get unique parent textures
            unique_textures: Dict[str, dict] = {}
            for product in product_list:
                base_name = extract_base_name(product["name"], product["url"])
                if base_name not in unique_textures:
                    unique_textures[base_name] = product

            print(f"  Grouped into {len(unique_textures)} unique parent textures")

            # Visit each product page to extract ALL color variants
            print("\n" + "=" * 60)
            print("Step 3: Visiting product pages to extract ALL color variants")
            print("=" * 60)

            for idx, (base_name, product) in enumerate(unique_textures.items()):
                url = product["url"]
                print(f"\n  [{idx + 1}/{len(unique_textures)}] {base_name}")
                print(f"    URL: {url[:60]}...")

                # Extract all variants from product page
                page_data = await extract_variants_from_page(page, url)

                if not page_data["variants"]:
                    print("    No variants found, skipping")
                    continue

                print(f"    Found {len(page_data['variants'])} color variants")

                # Use page name if available, otherwise use base_name
                texture_name = page_data["name"] or base_name

                # Create texture entry with all variants
                all_textures[base_name] = {
                    "name": texture_name,
                    "collection": "Asian Paints Textures",
                    "texture_type": detect_texture_type(texture_name),
                    "brand": "Asian Paints",
                    "description": page_data["description"] or f"{texture_name} texture finish for interior walls.",
                    "variants": [],
                }

                # Add each variant with constructed image URLs
                for variant in page_data["variants"]:
                    sku = variant["sku"]
                    url_options = construct_image_urls(sku)

                    all_textures[base_name]["variants"].append(
                        {
                            "code": sku,
                            "name": sku,
                            "url_options": url_options,
                            "swatch_url": variant.get("swatchImg"),
                            "product_url": url,
                            "image_url": None,
                            "image_data": None,
                        }
                    )

                # Print variant SKUs
                variant_skus = [v["sku"] for v in page_data["variants"]]
                print(f"    Variants: {', '.join(variant_skus[:5])}{'...' if len(variant_skus) > 5 else ''}")

            await browser.close()

        except Exception as e:
            print(f"  Error: {e}")
            import traceback

            traceback.print_exc()
            await browser.close()
            return []

    # Download images
    print("\n" + "=" * 60)
    print("Step 4: Downloading wall/room-shot images (trying multiple URL patterns)")
    print("=" * 60)

    total_variants = sum(len(t["variants"]) for t in all_textures.values())
    print(f"  Found {len(all_textures)} textures with {total_variants} total variants")

    downloaded = 0
    failed = 0
    failed_skus = []
    url_pattern_used = {}  # Track which URL pattern worked

    for texture_name, texture in all_textures.items():
        for variant in texture["variants"]:
            url_options = variant.get("url_options", [])

            if url_options and not variant["image_data"]:
                image_data, url_used = await download_with_fallbacks(url_options)

                if image_data:
                    variant["image_data"] = image_data
                    variant["image_url"] = url_used
                    downloaded += 1

                    # Track which pattern worked
                    pattern_idx = url_options.index(url_used) if url_used in url_options else -1
                    url_pattern_used[pattern_idx] = url_pattern_used.get(pattern_idx, 0) + 1

                    if downloaded % 20 == 0:
                        print(f"    Downloaded {downloaded} images...")
                else:
                    failed += 1
                    failed_skus.append(variant["code"])
                    print(f"    FAILED: {variant['code']} - all URL patterns failed")

    print(f"  Downloaded {downloaded} images, {failed} failed")
    print(f"  URL pattern usage: {dict(sorted(url_pattern_used.items()))}")
    if failed_skus and len(failed_skus) <= 20:
        print(f"  Failed SKUs: {', '.join(failed_skus)}")

    # Filter out textures without valid images and clean up variant data
    textures_list = []
    for texture in all_textures.values():
        # Remove internal flag
        texture.pop("has_real_desc", None)
        valid_variants = []
        for v in texture["variants"]:
            if v.get("image_data"):
                # Clean up temporary URL fields
                v.pop("url_options", None)
                v.pop("primary_url", None)
                v.pop("fallback_url", None)
                valid_variants.append(v)
        if valid_variants:
            texture["variants"] = valid_variants
            textures_list.append(texture)

    # Verify uniqueness of images using proper hash
    print("\n" + "=" * 60)
    print("Step 5: Verifying image uniqueness")
    print("=" * 60)

    import hashlib

    all_image_hashes = []
    image_sizes = []
    for texture in textures_list:
        for variant in texture["variants"]:
            if variant.get("image_data"):
                # Use SHA256 hash of full content for uniqueness check
                img_hash = hashlib.sha256(variant["image_data"].encode()).hexdigest()
                all_image_hashes.append(img_hash)
                # Also track size (base64 length is ~1.33x original)
                image_sizes.append(len(variant["image_data"]))

    unique_hashes = len(set(all_image_hashes))
    avg_size = sum(image_sizes) / len(image_sizes) if image_sizes else 0
    print(f"  Total images: {len(all_image_hashes)}")
    print(f"  Unique images: {unique_hashes}")
    print(f"  Average image size: {avg_size / 1024:.1f} KB (base64)")
    if unique_hashes < len(all_image_hashes) * 0.9:
        print("  WARNING: Many duplicate images detected!")
    else:
        print("  Image uniqueness looks good")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Scraped {len(textures_list)} textures with variants")
    total_variants = sum(len(t["variants"]) for t in textures_list)
    print(f"Total variants with images: {total_variants}")

    # Show breakdown by texture
    print("\nVariants per texture:")
    for texture in sorted(textures_list, key=lambda t: len(t["variants"]), reverse=True)[:10]:
        print(f"  {texture['name']}: {len(texture['variants'])} variants")

    return textures_list


async def main():
    """Main scraper function."""
    print("=" * 60)
    print("Asian Paints Texture Scraper (Direct URL Construction)")
    print("=" * 60)

    textures = await scrape_textures()

    if textures:
        output_file = "/Users/sahityapandiri/Omnishop/api/scripts/asian_paints_textures.json"
        with open(output_file, "w") as f:
            json.dump(textures, f, indent=2)
        print(f"\nSaved {len(textures)} textures to {output_file}")
    else:
        print("\nNo textures scraped.")


if __name__ == "__main__":
    asyncio.run(main())
