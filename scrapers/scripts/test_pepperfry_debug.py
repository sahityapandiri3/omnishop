"""
Debug script to understand what Pepperfry pages contain
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        url = 'https://www.pepperfry.com/category/sofas.html'
        print(f"Loading: {url}")

        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)  # Wait for Angular

        # Get full HTML
        html = await page.content()
        print(f"\nPage HTML length: {len(html)}")

        # Check for JSON-LD scripts
        scripts_count = await page.locator('script[type="application/ld+json"]').count()
        print(f"\nJSON-LD scripts found: {scripts_count}")

        # Try to get script contents via different methods
        print("\n--- Method 1: page.evaluate ---")
        result = await page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                console.log('Found scripts:', scripts.length);
                return Array.from(scripts).map(s => {
                    return {
                        text: s.textContent ? s.textContent.substring(0, 500) : 'NO TEXT',
                        innerHTML: s.innerHTML ? s.innerHTML.substring(0, 500) : 'NO INNER'
                    };
                });
            }
        """)
        print(f"Scripts via evaluate: {len(result)}")
        for i, s in enumerate(result[:3]):
            print(f"\nScript {i}: {s['text'][:200]}...")

        # Check if ItemList is in page source
        print("\n--- Checking for ItemList in source ---")
        if 'ItemList' in html:
            print("✓ ItemList found in page source!")
            # Find the ItemList content
            import re
            match = re.search(r'"@type"\s*:\s*"ItemList"[^}]+itemListElement[^]]+\]', html)
            if match:
                print(f"ItemList snippet: {match.group(0)[:300]}...")
        else:
            print("✗ ItemList NOT found in page source")

        # Check for product cards in DOM
        print("\n--- Checking for product elements ---")
        selectors_to_try = [
            '.product-card-container',
            '.clip-product-card-wrapper',
            '[class*="product"]',
            'a[href*="/product/"]',
        ]

        for selector in selectors_to_try:
            count = await page.locator(selector).count()
            print(f"  {selector}: {count} elements")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
