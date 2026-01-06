"""
Test Pepperfry with stealth settings
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Try with more realistic browser settings
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='Asia/Kolkata',
            # Add more browser-like properties
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
        )

        page = await context.new_page()

        # Remove webdriver property
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Mock platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'MacIntel'
            });
        """)

        url = 'https://www.pepperfry.com/category/sofas.html'
        print(f"Loading: {url}")

        try:
            await page.goto(url, wait_until='networkidle', timeout=60000)
        except:
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)

        await asyncio.sleep(5)

        # Get full HTML
        html = await page.content()
        print(f"\nPage HTML length: {len(html)}")

        # Check for JSON-LD scripts
        scripts_count = await page.locator('script[type="application/ld+json"]').count()
        print(f"\nJSON-LD scripts found: {scripts_count}")

        if 'ItemList' in html:
            print("✓ ItemList found!")
        else:
            print("✗ ItemList NOT found")
            # Save the HTML for inspection
            with open('/tmp/pepperfry_page.html', 'w') as f:
                f.write(html)
            print("  HTML saved to /tmp/pepperfry_page.html")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
