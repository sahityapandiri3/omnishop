"""
Playwright-based scraper for Home Centre (homecentre.in)
Mid-tier furniture store
"""
import asyncio
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page

# Category URLs to scrape
CATEGORY_URLS = {
    # Living Room
    'living_room': [
        ('https://www.homecentre.in/in/en/c/livingroom-sofas', 'Sofa'),
        ('https://www.homecentre.in/in/en/c/livingroom-recliners', 'Recliner'),
        ('https://www.homecentre.in/in/en/c/livingroom-occasionalchairs', 'Accent Chair'),
        ('https://www.homecentre.in/in/en/c/livingroom-benchandstools', 'Bench'),
        ('https://www.homecentre.in/in/en/c/livingroom-ottomans', 'Ottoman'),
        ('https://www.homecentre.in/in/en/c/livingroom-tables', 'Coffee Table'),
        ('https://www.homecentre.in/in/en/c/livingroom-tvandmediaunits', 'TV Unit'),
        ('https://www.homecentre.in/in/en/c/livingroom-shelves', 'Wall Shelf'),
        ('https://www.homecentre.in/in/en/c/livingroom-shoeracks', 'Shoe Rack'),
        ('https://www.homecentre.in/in/en/c/livingroom-bookcaseandcabinets', 'Bookshelf'),
    ],
    # Bedroom
    'bedroom': [
        ('https://www.homecentre.in/in/en/c/bedroom-beds', 'Bed'),
        ('https://www.homecentre.in/in/en/c/bedroom-almirah', 'Wardrobe'),
        ('https://www.homecentre.in/in/en/c/bedroom-bedsidtables', 'Nightstand'),
        ('https://www.homecentre.in/in/en/c/bedroom-dressermirrors', 'Dresser'),
        ('https://www.homecentre.in/in/en/c/bedroom-chestofdrawers', 'Chest of Drawers'),
    ],
    # Dining
    'dining': [
        ('https://www.homecentre.in/in/en/c/diningroom-diningtables', 'Dining Table'),
        ('https://www.homecentre.in/in/en/c/diningroom-diningchairs', 'Dining Chair'),
        ('https://www.homecentre.in/in/en/c/diningroom-diningbenches', 'Bench'),
    ],
    # Decor
    'decor': [
        ('https://www.homecentre.in/in/en/c/decor-wallaccent-walldecor', 'Wall Decor'),
        ('https://www.homecentre.in/in/en/c/decor-homeaccessories-vases', 'Vase'),
        ('https://www.homecentre.in/in/en/c/decor-wallaccent-photoframes', 'Photo Frame'),
        ('https://www.homecentre.in/in/en/c/decor-homeaccessories-figurines', 'Showpiece'),
        ('https://www.homecentre.in/in/en/c/decor-homeaccessories-candleholdersandlanterns', 'Candle Holder'),
        ('https://www.homecentre.in/in/en/c/decor-homeaccessories-tableaccents', 'Table Accent'),
    ],
    # Lighting
    'lighting': [
        ('https://www.homecentre.in/in/en/c/decor-lighting-tablelamps', 'Table Lamp'),
        ('https://www.homecentre.in/in/en/c/decor-lighting-floorlamps', 'Floor Lamp'),
        ('https://www.homecentre.in/in/en/c/decor-lighting-ceilinglamps', 'Ceiling Light'),
        ('https://www.homecentre.in/in/en/c/decor-lighting-walllamps', 'Wall Light'),
        ('https://www.homecentre.in/in/en/c/decor-lighting-pendinglamps', 'Pendant Light'),
    ],
    # Furnishing
    'furnishing': [
        ('https://www.homecentre.in/in/en/c/furnishing-cushions-cushioncovers', 'Cushion Cover'),
        ('https://www.homecentre.in/in/en/c/furnishing-cushions-filledcushions', 'Cushion'),
        ('https://www.homecentre.in/in/en/c/furnishing-floorcoverings-carpets', 'Carpet'),
        ('https://www.homecentre.in/in/en/c/furnishing-floorcoverings-dhurries', 'Rug'),
        ('https://www.homecentre.in/in/en/c/furnishing-curtains-doorcurtains', 'Curtain'),
        ('https://www.homecentre.in/in/en/c/furnishing-curtains-windowcurtains', 'Curtain'),
        ('https://www.homecentre.in/in/en/c/furnishing-bedding-throws', 'Throw'),
    ],
    # Storage
    'storage': [
        ('https://www.homecentre.in/in/en/c/organisers-livingroom', 'Storage Unit'),
        ('https://www.homecentre.in/in/en/c/organisers-bedroom', 'Storage Unit'),
    ],
}


def generate_external_id(url: str) -> str:
    """Generate a unique external ID from URL"""
    return hashlib.md5(url.encode()).hexdigest()[:16]


async def scroll_and_collect_products(page: Page, max_scrolls: int = 50) -> List[str]:
    """Scroll down the page to load all products via infinite scroll"""
    product_urls = set()
    prev_count = 0
    no_change_count = 0

    for i in range(max_scrolls):
        # Find product links - Home Centre uses various selectors
        cards = await page.query_selector_all('a[href*="/p/"]')
        for card in cards:
            href = await card.get_attribute('href')
            if href and '/p/' in href:
                if not href.startswith('http'):
                    href = f'https://www.homecentre.in{href}'
                product_urls.add(href)

        current_count = len(product_urls)
        print(f"  Scroll {i+1}: Found {current_count} products")

        if current_count == prev_count:
            no_change_count += 1
            if no_change_count >= 3:
                print(f"  No new products after {no_change_count} scrolls, stopping")
                break
        else:
            no_change_count = 0

        prev_count = current_count

        # Scroll down
        await page.evaluate('window.scrollBy(0, window.innerHeight)')
        await asyncio.sleep(1.5)

    return list(product_urls)


async def extract_product_data(page: Page, url: str, category: str) -> Optional[Dict]:
    """Extract product data from product detail page using JSON-LD schema"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(2)

        # Try to extract JSON-LD schema
        scripts_content = await page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                return Array.from(scripts).map(s => s.textContent || s.innerHTML || '');
            }
        """)

        product_data = None
        for text in scripts_content:
            if not text or not text.strip():
                continue
            try:
                data = json.loads(text)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    product_data = data
                    break
            except json.JSONDecodeError:
                continue

        if not product_data:
            # Fallback: try to extract from page content
            name = await page.locator('h1').first.text_content()
            if not name:
                return None

            # Try to get price
            price_text = await page.locator('[class*="price"]').first.text_content()
            price = None
            if price_text:
                import re
                price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
                if price_match:
                    price = float(price_match.group().replace(',', ''))

            # Try to get image
            img = await page.locator('img[src*="media.landmarkshops"]').first.get_attribute('src')

            return {
                'name': name.strip() if name else None,
                'price': price,
                'currency': 'INR',
                'product_url': url,
                'image_url': img,
                'category': category,
                'source_website': 'homecentre',
                'external_id': generate_external_id(url),
                'scraped_at': datetime.now().isoformat(),
            }

        # Extract from JSON-LD
        name = product_data.get('name', '')

        # Get price from offers
        offers = product_data.get('offers', {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get('price')
        if price:
            price = float(str(price).replace(',', ''))

        # Get image
        image = product_data.get('image', '')
        if isinstance(image, list):
            image = image[0] if image else ''

        # Get description
        description = product_data.get('description', '')

        # Get SKU
        sku = product_data.get('sku', '')

        return {
            'name': name,
            'price': price,
            'currency': 'INR',
            'product_url': url,
            'image_url': image,
            'description': description,
            'category': category,
            'source_website': 'homecentre',
            'external_id': sku or generate_external_id(url),
            'scraped_at': datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"    Error extracting {url}: {e}")
        return None


async def scrape_category(page: Page, url: str, category: str, all_products: Dict[str, Dict]) -> int:
    """Scrape a single category page"""
    print(f"\nCategory: {category}")
    print(f"URL: {url}")

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(3)

        # Scroll to load all products
        product_urls = await scroll_and_collect_products(page)

        new_products = 0
        total = len(product_urls)

        for i, product_url in enumerate(product_urls):
            # Skip if already scraped
            ext_id = generate_external_id(product_url)
            if ext_id in all_products:
                continue

            print(f"  [{i+1}/{total}] Scraping: {product_url.split('/')[-2][:50]}...")

            product_data = await extract_product_data(page, product_url, category)

            if product_data and product_data.get('name') and product_data.get('price'):
                all_products[product_data['external_id']] = product_data
                new_products += 1

            # Rate limiting
            await asyncio.sleep(0.5)

        print(f"  New unique products: {new_products}")
        return new_products

    except Exception as e:
        print(f"  Error scraping category: {e}")
        return 0


async def main():
    all_products: Dict[str, Dict] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = await context.new_page()

        for section_name, categories in CATEGORY_URLS.items():
            print(f"\n{'='*60}")
            print(f"Scraping {section_name.upper()}")
            print('='*60)

            for url, category in categories:
                await scrape_category(page, url, category, all_products)
                # Save progress after each category
                with open('/tmp/homecentre_products.json', 'w') as f:
                    json.dump(list(all_products.values()), f, indent=2)

        await browser.close()

    # Final save
    output_file = '/tmp/homecentre_products.json'
    with open(output_file, 'w') as f:
        json.dump(list(all_products.values()), f, indent=2)

    print(f"\n{'='*60}")
    print(f"Scraping complete!")
    print(f"Total products scraped: {len(all_products)}")
    print(f"Output saved to: {output_file}")
    print('='*60)


if __name__ == '__main__':
    asyncio.run(main())
