"""
Playwright-based scraper for Urban Ladder - Fixed version
Uses longer timeouts and extracts from JSON-LD schema
"""
import asyncio
import json
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page

# Category URLs for Urban Ladder
CATEGORY_URLS = {
    'sofas_seating': [
        ('https://www.urbanladder.com/sofas', 'Sofa'),
        ('https://www.urbanladder.com/3-seater-sofas', 'Sofa'),
        ('https://www.urbanladder.com/2-seater-sofas', 'Sofa'),
        ('https://www.urbanladder.com/l-shaped-sofas', 'Sectional Sofa'),
        ('https://www.urbanladder.com/sofa-cum-beds', 'Sofa Cum Bed'),
        ('https://www.urbanladder.com/recliners', 'Recliner'),
        ('https://www.urbanladder.com/accent-chairs', 'Accent Chair'),
        ('https://www.urbanladder.com/lounge-chairs', 'Lounge Chair'),
        ('https://www.urbanladder.com/arm-chairs', 'Armchair'),
        ('https://www.urbanladder.com/ottomans-and-poufs', 'Ottoman'),
        ('https://www.urbanladder.com/benches', 'Bench'),
    ],
    'living_room': [
        ('https://www.urbanladder.com/coffee-tables', 'Coffee Table'),
        ('https://www.urbanladder.com/side-and-end-tables', 'Side Table'),
        ('https://www.urbanladder.com/console-tables', 'Console Table'),
        ('https://www.urbanladder.com/tv-units', 'TV Unit'),
        ('https://www.urbanladder.com/shoe-racks', 'Shoe Rack'),
        ('https://www.urbanladder.com/cabinets-and-sideboards', 'Cabinet'),
        ('https://www.urbanladder.com/bookshelves', 'Bookshelf'),
        ('https://www.urbanladder.com/display-units', 'Display Unit'),
        ('https://www.urbanladder.com/wall-shelves', 'Wall Shelf'),
    ],
    'bedroom': [
        ('https://www.urbanladder.com/beds', 'Bed'),
        ('https://www.urbanladder.com/king-size-beds', 'Bed'),
        ('https://www.urbanladder.com/queen-size-beds', 'Bed'),
        ('https://www.urbanladder.com/wardrobes', 'Wardrobe'),
        ('https://www.urbanladder.com/chest-of-drawers', 'Chest of Drawers'),
        ('https://www.urbanladder.com/bedside-tables', 'Nightstand'),
        ('https://www.urbanladder.com/dressing-tables', 'Dresser'),
    ],
    'dining': [
        ('https://www.urbanladder.com/dining-table-sets', 'Dining Table'),
        ('https://www.urbanladder.com/dining-tables', 'Dining Table'),
        ('https://www.urbanladder.com/dining-chairs', 'Dining Chair'),
        ('https://www.urbanladder.com/bar-cabinets', 'Bar Cabinet'),
        ('https://www.urbanladder.com/bar-stools', 'Bar Stool'),
        ('https://www.urbanladder.com/crockery-units', 'Crockery Unit'),
    ],
    'study_office': [
        ('https://www.urbanladder.com/study-tables', 'Study Table'),
        ('https://www.urbanladder.com/computer-tables', 'Desk'),
        ('https://www.urbanladder.com/office-chairs', 'Office Chair'),
    ],
    'decor': [
        ('https://www.urbanladder.com/mirrors', 'Mirror'),
        ('https://www.urbanladder.com/vases', 'Vase'),
        ('https://www.urbanladder.com/wall-decor', 'Wall Decor'),
        ('https://www.urbanladder.com/clocks', 'Clock'),
        ('https://www.urbanladder.com/photo-frames', 'Photo Frame'),
        ('https://www.urbanladder.com/planters', 'Planter'),
        ('https://www.urbanladder.com/showpieces', 'Showpiece'),
        ('https://www.urbanladder.com/candle-holders', 'Candle Holder'),
    ],
    'wall_art': [
        ('https://www.urbanladder.com/wall-art', 'Wall Art'),
        ('https://www.urbanladder.com/canvas-art', 'Wall Art'),
        ('https://www.urbanladder.com/metal-wall-art', 'Wall Art'),
    ],
    'furnishing': [
        ('https://www.urbanladder.com/rugs-and-carpets', 'Rug'),
        ('https://www.urbanladder.com/curtains', 'Curtain'),
        ('https://www.urbanladder.com/cushion-covers', 'Cushion Cover'),
        ('https://www.urbanladder.com/throws-and-blankets', 'Throw'),
    ],
    'lighting': [
        ('https://www.urbanladder.com/floor-lamps', 'Floor Lamp'),
        ('https://www.urbanladder.com/table-lamps', 'Table Lamp'),
        ('https://www.urbanladder.com/ceiling-lights', 'Ceiling Light'),
        ('https://www.urbanladder.com/wall-lights', 'Wall Light'),
        ('https://www.urbanladder.com/chandeliers', 'Chandelier'),
        ('https://www.urbanladder.com/pendant-lights', 'Pendant Light'),
    ],
}


def generate_external_id(url: str) -> str:
    """Generate a unique external ID from URL"""
    match = re.search(r'/product/([^/?]+)', url)
    if match:
        return f"ul_{match.group(1)[:32]}"
    return hashlib.md5(url.encode()).hexdigest()[:16]


async def extract_products_from_schema(page: Page) -> List[str]:
    """Extract product URLs from JSON-LD ItemList schema"""
    product_urls = []

    try:
        json_ld_elements = await page.query_selector_all('script[type="application/ld+json"]')

        for elem in json_ld_elements:
            text = await elem.inner_text()
            try:
                data = json.loads(text)

                # Handle ItemList schema
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    items = data.get('itemListElement', [])
                    for item in items:
                        if 'item' in item and isinstance(item['item'], dict):
                            url = item['item'].get('url')
                            if url:
                                product_urls.append(url)
                        elif 'url' in item:
                            product_urls.append(item['url'])

                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'ItemList':
                            for list_item in item.get('itemListElement', []):
                                if 'item' in list_item and isinstance(list_item['item'], dict):
                                    url = list_item['item'].get('url')
                                    if url:
                                        product_urls.append(url)

            except json.JSONDecodeError:
                continue

    except Exception as e:
        print(f"  Error extracting schema: {e}")

    return product_urls


async def scroll_and_collect_products(page: Page, max_scrolls: int = 15) -> List[str]:
    """Scroll and collect products from both schema and DOM"""
    product_urls = set()
    prev_count = 0
    no_change_count = 0

    for i in range(max_scrolls):
        # First try schema extraction
        schema_urls = await extract_products_from_schema(page)
        product_urls.update(schema_urls)

        # Also try DOM selectors as backup
        try:
            links = await page.query_selector_all('a[href*="/product/"]')
            for link in links:
                href = await link.get_attribute('href')
                if href and '/product/' in href:
                    if href.startswith('/'):
                        href = f'https://www.urbanladder.com{href}'
                    if not any(x in href for x in ['/compare', '/wishlist', '/cart']):
                        product_urls.add(href)
        except:
            pass

        current_count = len(product_urls)
        print(f"  Scroll {i+1}: Found {current_count} products")

        if current_count == prev_count:
            no_change_count += 1
            if no_change_count >= 3:
                print(f"  No new products after 3 scrolls, stopping")
                break
        else:
            no_change_count = 0

        prev_count = current_count

        # Scroll down
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(2)

    return list(product_urls)


async def scrape_product_page(page: Page, url: str, category: str) -> Optional[Dict]:
    """Scrape individual product page"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=45000)
        await asyncio.sleep(1)

        # Try to get JSON-LD data
        json_ld_elements = await page.query_selector_all('script[type="application/ld+json"]')
        product_data = None

        for elem in json_ld_elements:
            text = await elem.inner_text()
            try:
                data = json.loads(text)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    product_data = data
                    break
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            product_data = item
                            break
            except json.JSONDecodeError:
                continue

        if not product_data:
            return None

        # Extract name
        name = product_data.get('name')
        if not name:
            return None

        # Extract price
        price = None
        offers = product_data.get('offers', {})
        if isinstance(offers, dict):
            price = offers.get('price')
            if not price and offers.get('lowPrice'):
                price = offers.get('lowPrice')
        elif isinstance(offers, list) and offers:
            price = offers[0].get('price')

        if not price:
            return None

        # Extract other fields
        description = product_data.get('description')
        if not description:
            meta_desc = await page.query_selector('meta[name="description"]')
            if meta_desc:
                description = await meta_desc.get_attribute('content')

        image_urls = []
        images = product_data.get('image', [])
        if isinstance(images, str):
            image_urls = [images]
        elif isinstance(images, list):
            image_urls = images[:10]

        is_available = True
        if isinstance(offers, dict):
            availability = offers.get('availability', '')
            is_available = 'InStock' in str(availability)

        brand = 'Urban Ladder'
        brand_data = product_data.get('brand')
        if isinstance(brand_data, dict):
            brand = brand_data.get('name', 'Urban Ladder')
        elif isinstance(brand_data, str):
            brand = brand_data

        return {
            'name': name,
            'price': float(price) if price else None,
            'external_id': generate_external_id(url),
            'description': description,
            'brand': brand,
            'category': category,
            'source_website': 'urbanladder',
            'source_url': url,
            'scraped_at': datetime.utcnow().isoformat(),
            'image_urls': image_urls,
            'attributes': {},
            'is_available': is_available,
            'is_on_sale': False,
            'stock_status': 'in_stock' if is_available else 'out_of_stock',
            'currency': 'INR',
            'original_price': None,
            'model': None,
            'sku': product_data.get('sku'),
        }

    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


async def main():
    """Main scraping function"""
    all_products = []
    seen_urls = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        for group_name, categories in CATEGORY_URLS.items():
            print(f"\n{'='*60}")
            print(f"Scraping {group_name.upper()}")
            print(f"{'='*60}")

            for cat_url, category in categories:
                print(f"\nCategory: {category}")
                print(f"URL: {cat_url}")

                try:
                    # Navigate with longer timeout
                    await page.goto(cat_url, wait_until='domcontentloaded', timeout=90000)
                    await asyncio.sleep(3)

                    # Scroll and collect products
                    product_urls = await scroll_and_collect_products(page)

                    # Filter out already seen URLs
                    new_urls = [url for url in product_urls if url not in seen_urls]
                    print(f"  New unique products: {len(new_urls)}")

                    # Scrape each product (limit to avoid very long runs)
                    for i, url in enumerate(new_urls[:100]):
                        seen_urls.add(url)
                        print(f"  [{i+1}/{min(len(new_urls), 100)}] Scraping: {url.split('/')[-1][:50]}...")

                        product = await scrape_product_page(page, url, category)
                        if product:
                            all_products.append(product)

                        await asyncio.sleep(0.3)

                except Exception as e:
                    print(f"  Error with category {cat_url}: {e}")
                    continue

        await browser.close()

    # Save results
    output_file = '/tmp/urbanladder_products_v2.json'
    with open(output_file, 'w') as f:
        json.dump(all_products, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Scraping complete!")
    print(f"Total products scraped: {len(all_products)}")
    print(f"Output saved to: {output_file}")
    print(f"{'='*60}")

    return all_products


if __name__ == '__main__':
    asyncio.run(main())
