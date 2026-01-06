"""
Playwright-based scraper for Pepperfry - Fixed version
Extracts product URLs from JSON-LD schema data instead of DOM selectors
"""
import asyncio
import json
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page

# Category URLs for Pepperfry
CATEGORY_URLS = {
    'sofas_seating': [
        ('https://www.pepperfry.com/category/sofas.html', 'Sofa'),
        ('https://www.pepperfry.com/category/sectional-sofas.html', 'Sectional Sofa'),
        ('https://www.pepperfry.com/category/recliners.html', 'Recliner'),
        ('https://www.pepperfry.com/category/sofa-cum-beds.html', 'Sofa Cum Bed'),
        ('https://www.pepperfry.com/category/accent-chairs.html', 'Accent Chair'),
        ('https://www.pepperfry.com/category/lounge-chairs.html', 'Lounge Chair'),
        ('https://www.pepperfry.com/category/arm-chairs.html', 'Armchair'),
        ('https://www.pepperfry.com/category/ottomans-poufs.html', 'Ottoman'),
        ('https://www.pepperfry.com/category/benches.html', 'Bench'),
    ],
    'living_room': [
        ('https://www.pepperfry.com/category/coffee-tables.html', 'Coffee Table'),
        ('https://www.pepperfry.com/category/centre-tables.html', 'Center Table'),
        ('https://www.pepperfry.com/category/side-tables.html', 'Side Table'),
        ('https://www.pepperfry.com/category/console-tables.html', 'Console Table'),
        ('https://www.pepperfry.com/category/tv-units.html', 'TV Unit'),
        ('https://www.pepperfry.com/category/shoe-racks.html', 'Shoe Rack'),
        ('https://www.pepperfry.com/category/cabinets.html', 'Cabinet'),
        ('https://www.pepperfry.com/category/bookshelves.html', 'Bookshelf'),
        ('https://www.pepperfry.com/category/display-units.html', 'Display Unit'),
        ('https://www.pepperfry.com/category/wall-shelves.html', 'Wall Shelf'),
    ],
    'bedroom': [
        ('https://www.pepperfry.com/category/beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/king-size-beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/queen-size-beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/wardrobes.html', 'Wardrobe'),
        ('https://www.pepperfry.com/category/chest-of-drawers.html', 'Chest of Drawers'),
        ('https://www.pepperfry.com/category/bedside-tables.html', 'Nightstand'),
        ('https://www.pepperfry.com/category/dressing-tables.html', 'Dresser'),
    ],
    'dining': [
        ('https://www.pepperfry.com/category/dining-sets.html', 'Dining Table'),
        ('https://www.pepperfry.com/category/dining-tables.html', 'Dining Table'),
        ('https://www.pepperfry.com/category/dining-chairs.html', 'Dining Chair'),
        ('https://www.pepperfry.com/category/bar-cabinets.html', 'Bar Cabinet'),
        ('https://www.pepperfry.com/category/bar-stools.html', 'Bar Stool'),
        ('https://www.pepperfry.com/category/crockery-units.html', 'Crockery Unit'),
    ],
    'study_office': [
        ('https://www.pepperfry.com/category/study-tables.html', 'Study Table'),
        ('https://www.pepperfry.com/category/computer-tables.html', 'Desk'),
        ('https://www.pepperfry.com/category/office-chairs.html', 'Office Chair'),
    ],
    'decor': [
        ('https://www.pepperfry.com/category/mirrors.html', 'Mirror'),
        ('https://www.pepperfry.com/category/vases.html', 'Vase'),
        ('https://www.pepperfry.com/category/wall-decor.html', 'Wall Decor'),
        ('https://www.pepperfry.com/category/clocks.html', 'Clock'),
        ('https://www.pepperfry.com/category/photo-frames.html', 'Photo Frame'),
        ('https://www.pepperfry.com/category/planters.html', 'Planter'),
        ('https://www.pepperfry.com/category/showpieces.html', 'Showpiece'),
        ('https://www.pepperfry.com/category/candle-holders.html', 'Candle Holder'),
    ],
    'wall_art': [
        ('https://www.pepperfry.com/category/wall-art.html', 'Wall Art'),
        ('https://www.pepperfry.com/category/canvas-paintings.html', 'Wall Art'),
        ('https://www.pepperfry.com/category/metal-wall-art.html', 'Wall Art'),
    ],
    'furnishing': [
        ('https://www.pepperfry.com/category/rugs.html', 'Rug'),
        ('https://www.pepperfry.com/category/carpets.html', 'Carpet'),
        ('https://www.pepperfry.com/category/curtains.html', 'Curtain'),
        ('https://www.pepperfry.com/category/cushion-covers.html', 'Cushion Cover'),
        ('https://www.pepperfry.com/category/throws.html', 'Throw'),
    ],
    'lighting': [
        ('https://www.pepperfry.com/category/floor-lamps.html', 'Floor Lamp'),
        ('https://www.pepperfry.com/category/table-lamps.html', 'Table Lamp'),
        ('https://www.pepperfry.com/category/ceiling-lights.html', 'Ceiling Light'),
        ('https://www.pepperfry.com/category/wall-lights.html', 'Wall Light'),
        ('https://www.pepperfry.com/category/chandeliers.html', 'Chandelier'),
        ('https://www.pepperfry.com/category/pendant-lights.html', 'Pendant Light'),
    ],
}


def generate_external_id(url: str) -> str:
    """Generate a unique external ID from URL"""
    match = re.search(r'-(\d+)\.html$', url)
    if match:
        return f"pf_{match.group(1)}"
    return hashlib.md5(url.encode()).hexdigest()[:16]


async def extract_products_from_schema(page: Page) -> List[str]:
    """Extract product URLs from JSON-LD ItemList schema"""
    product_urls = []

    try:
        # Get all JSON-LD scripts
        json_ld_elements = await page.query_selector_all('script[type="application/ld+json"]')

        for elem in json_ld_elements:
            text = await elem.inner_text()
            try:
                data = json.loads(text)

                # Handle ItemList schema (product listing)
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    items = data.get('itemListElement', [])
                    for item in items:
                        if 'item' in item and isinstance(item['item'], dict):
                            url = item['item'].get('url')
                            if url:
                                product_urls.append(url)
                        elif 'url' in item:
                            product_urls.append(item['url'])

                # Handle array format
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


async def collect_products_with_pagination(page: Page, base_url: str, max_pages: int = 5) -> List[str]:
    """Collect product URLs from schema across pagination"""
    all_product_urls = set()

    for page_num in range(1, max_pages + 1):
        # Build paginated URL
        if page_num == 1:
            url = base_url
        else:
            if '?' in base_url:
                url = f"{base_url}&page={page_num}"
            else:
                url = f"{base_url}?page={page_num}"

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)  # Wait for content to render

            # Extract products from schema
            products = await extract_products_from_schema(page)

            if not products:
                print(f"  Page {page_num}: No products found in schema")
                break

            prev_count = len(all_product_urls)
            all_product_urls.update(products)
            new_count = len(all_product_urls) - prev_count

            print(f"  Page {page_num}: Found {len(products)} products ({new_count} new)")

            if new_count == 0:
                break

        except Exception as e:
            print(f"  Page {page_num} error: {e}")
            break

    return list(all_product_urls)


async def scrape_product_page(page: Page, url: str, category: str) -> Optional[Dict]:
    """Scrape individual product page"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(1)

        # Try to get JSON-LD product data
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
        original_price = None
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

        brand = 'Pepperfry'
        brand_data = product_data.get('brand')
        if isinstance(brand_data, dict):
            brand = brand_data.get('name', 'Pepperfry')
        elif isinstance(brand_data, str):
            brand = brand_data

        return {
            'name': name,
            'price': float(price) if price else None,
            'external_id': generate_external_id(url),
            'description': description,
            'brand': brand,
            'category': category,
            'source_website': 'pepperfry',
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
                    # Collect product URLs from schema
                    product_urls = await collect_products_with_pagination(page, cat_url)

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
    output_file = '/tmp/pepperfry_products_v2.json'
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
