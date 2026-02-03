"""
Scrape Asian Paints color catalogue using Playwright.

This script fetches color data from Asian Paints' API endpoints.

Usage:
    python -m scripts.scrape_asian_paints
"""

import asyncio
import json
import re

from playwright.async_api import async_playwright

# Map Asian Paints shade families to our database families
FAMILY_MAPPING = {
    "whites": "whites_offwhites",
    "off whites": "whites_offwhites",
    "offwhites": "whites_offwhites",
    "greys": "greys",
    "grey": "greys",
    "grays": "greys",
    "blues": "blues",
    "blue": "blues",
    "browns": "browns",
    "brown": "browns",
    "beige": "browns",
    "reds": "reds_oranges",
    "red": "reds_oranges",
    "oranges": "reds_oranges",
    "orange": "reds_oranges",
    "yellows": "yellows_greens",
    "yellow": "yellows_greens",
    "greens": "yellows_greens",
    "green": "yellows_greens",
    "purples": "purples_pinks",
    "purple": "purples_pinks",
    "pinks": "purples_pinks",
    "pink": "purples_pinks",
    "violet": "purples_pinks",
    "mauve": "purples_pinks",
}


def map_shade_family(shade_family):
    """Map Asian Paints shade family to our database family."""
    if not shade_family:
        return "greys"  # Default

    family_lower = shade_family.lower().strip()

    # Direct match
    if family_lower in FAMILY_MAPPING:
        return FAMILY_MAPPING[family_lower]

    # Partial match
    for key, value in FAMILY_MAPPING.items():
        if key in family_lower or family_lower in key:
            return value

    # Default based on color type
    return "greys"


async def scrape_colors():
    """Scrape colors from Asian Paints API."""

    all_colors = []
    captured_responses = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Intercept API responses
        async def handle_response(response):
            url = response.url
            if "jcr:content" in url and "colour-catalogue" in url:
                try:
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        data = await response.json()
                        captured_responses.append(data)
                        print(f"  Captured API response with {len(data.get('shade', []))} shades")
                except Exception as e:
                    print(f"  Error parsing response: {e}")

        page.on("response", handle_response)

        print("Navigating to colour catalogue...")
        await page.goto("https://www.asianpaints.com/catalogue/colour-catalogue.html", wait_until="load", timeout=60000)
        await page.wait_for_timeout(5000)

        # Scroll to trigger loading more colors
        print("Scrolling to load more colors...")
        for i in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            print(f"  Scroll {i+1}/5")

        # Also visit color family pages to get all colors
        family_urls = [
            "https://www.asianpaints.com/catalogue/colour-catalogue/white-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/off-white-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/grey-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/blue-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/brown-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/red-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/orange-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/yellow-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/green-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/purple-wall-colours.html",
            "https://www.asianpaints.com/catalogue/colour-catalogue/pink-wall-colours.html",
        ]

        for url in family_urls:
            print(f"\nVisiting: {url.split('/')[-1]}")
            try:
                await page.goto(url, wait_until="load", timeout=30000)
                await page.wait_for_timeout(3000)

                # Scroll to load more
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1500)
            except Exception as e:
                print(f"  Error: {e}")

        await browser.close()

    # Process captured responses
    print(f"\n\nProcessing {len(captured_responses)} API responses...")

    seen_codes = set()
    for response in captured_responses:
        shades = response.get("shade", [])
        for shade in shades:
            code = shade.get("entityCode")
            name = shade.get("entityName", "").strip()
            hex_value = shade.get("shadeHexCode", "").strip()
            shade_family = shade.get("shadeFamily", "")

            if not code or code in seen_codes:
                continue

            if not hex_value or not hex_value.startswith("#"):
                continue

            # Capitalize name properly
            if name:
                name = " ".join(word.capitalize() for word in name.split())
            else:
                name = f"Shade {code}"

            family = map_shade_family(shade_family)

            all_colors.append(
                {
                    "code": code,
                    "name": name,
                    "hex_value": hex_value.upper(),
                    "family": family,
                    "original_family": shade_family,
                }
            )
            seen_codes.add(code)

    return all_colors


async def main():
    """Main function."""
    print("=" * 60)
    print("Asian Paints Color Scraper")
    print("=" * 60)

    colors = await scrape_colors()

    print(f"\n{'='*60}")
    print(f"Total unique colors scraped: {len(colors)}")
    print(f"{'='*60}")

    # Group by family
    families = {}
    for c in colors:
        family = c["family"]
        if family not in families:
            families[family] = []
        families[family].append(c)

    print("\nColors by family:")
    for family, fcolors in sorted(families.items()):
        print(f"  {family}: {len(fcolors)} colors")

    # Save to JSON
    output_file = "/Users/sahityapandiri/Omnishop/api/scripts/asian_paints_colors.json"
    with open(output_file, "w") as f:
        json.dump(colors, f, indent=2)
    print(f"\nColors saved to: {output_file}")

    # Print sample colors
    print("\n\nSample colors from each family:")
    for family, fcolors in sorted(families.items()):
        print(f"\n  {family}:")
        for c in fcolors[:5]:
            print(f"    {c['code']} - {c['name']} ({c['hex_value']}) [from: {c.get('original_family', 'N/A')}]")


if __name__ == "__main__":
    asyncio.run(main())
