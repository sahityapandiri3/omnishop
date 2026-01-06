"""
Test script to find correct product selectors on Wooden Street
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Test on solid-wood-tv-units page
        url = 'https://www.woodenstreet.com/solid-wood-tv-units'
        print(f"Testing: {url}")
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(3)

        # Scroll to load products
        print("\nScrolling to load more content...")
        for i in range(5):
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)

        # Extract product URLs from JSON-LD data
        print("\nExtracting products from JSON-LD...")
        product_urls = []
        json_ld_elements = await page.query_selector_all('script[type="application/ld+json"]')
        for elem in json_ld_elements:
            text = await elem.inner_text()
            try:
                data = json.loads(text)
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    items = data.get('itemListElement', [])
                    print(f"  Found ItemList with {len(items)} items")
                    for item in items:
                        if 'item' in item and 'url' in item['item']:
                            product_urls.append(item['item']['url'])
            except:
                pass

        print(f"\n  Product URLs from JSON-LD: {len(product_urls)}")
        for url in product_urls[:10]:
            print(f"    {url}")

        # Also check .productcard elements
        print("\n\nChecking .productcard elements...")
        cards = await page.query_selector_all('.productcard')
        print(f"  Found {len(cards)} productcard elements")

        # Find links inside product cards
        card_urls = []
        for card in cards[:5]:
            links = await card.query_selector_all('a')
            for link in links:
                href = await link.get_attribute('href')
                if href and '-' in href:
                    card_urls.append(href)
                    break  # Just get first link from each card

        print(f"  Links from product cards:")
        for url in card_urls:
            print(f"    {url}")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
