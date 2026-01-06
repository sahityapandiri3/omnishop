"""
Playwright-based scraper for Pepperfry furniture and home decor
Handles JavaScript pagination
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
    # Furniture - Sofas & Seating
    'sofas_seating': [
        ('https://www.pepperfry.com/category/sofas.html', 'Sofa'),
        ('https://www.pepperfry.com/category/sectional-sofas.html', 'Sectional Sofa'),
        ('https://www.pepperfry.com/category/sofa-sets.html', 'Sofa'),
        ('https://www.pepperfry.com/category/recliners.html', 'Recliner'),
        ('https://www.pepperfry.com/category/sofa-cum-beds.html', 'Sofa Cum Bed'),
        ('https://www.pepperfry.com/category/futons.html', 'Futon'),
        ('https://www.pepperfry.com/category/accent-chairs.html', 'Accent Chair'),
        ('https://www.pepperfry.com/category/lounge-chairs.html', 'Lounge Chair'),
        ('https://www.pepperfry.com/category/arm-chairs.html', 'Armchair'),
        ('https://www.pepperfry.com/category/ottomans-poufs.html', 'Ottoman'),
        ('https://www.pepperfry.com/category/benches.html', 'Bench'),
        ('https://www.pepperfry.com/category/stools.html', 'Stool'),
    ],
    # Living Room
    'living_room': [
        ('https://www.pepperfry.com/category/coffee-tables.html', 'Coffee Table'),
        ('https://www.pepperfry.com/category/centre-tables.html', 'Center Table'),
        ('https://www.pepperfry.com/category/side-tables.html', 'Side Table'),
        ('https://www.pepperfry.com/category/console-tables.html', 'Console Table'),
        ('https://www.pepperfry.com/category/nesting-tables.html', 'Nesting Table'),
        ('https://www.pepperfry.com/category/tv-units.html', 'TV Unit'),
        ('https://www.pepperfry.com/category/shoe-racks.html', 'Shoe Rack'),
        ('https://www.pepperfry.com/category/cabinets.html', 'Cabinet'),
        ('https://www.pepperfry.com/category/bookshelves.html', 'Bookshelf'),
        ('https://www.pepperfry.com/category/display-units.html', 'Display Unit'),
        ('https://www.pepperfry.com/category/wall-shelves.html', 'Wall Shelf'),
    ],
    # Bedroom
    'bedroom': [
        ('https://www.pepperfry.com/category/beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/king-size-beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/queen-size-beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/single-beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/storage-beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/upholstered-beds.html', 'Bed'),
        ('https://www.pepperfry.com/category/wardrobes.html', 'Wardrobe'),
        ('https://www.pepperfry.com/category/chest-of-drawers.html', 'Chest of Drawers'),
        ('https://www.pepperfry.com/category/bedside-tables.html', 'Nightstand'),
        ('https://www.pepperfry.com/category/dressing-tables.html', 'Dresser'),
    ],
    # Dining
    'dining': [
        ('https://www.pepperfry.com/category/dining-sets.html', 'Dining Table'),
        ('https://www.pepperfry.com/category/dining-tables.html', 'Dining Table'),
        ('https://www.pepperfry.com/category/dining-chairs.html', 'Dining Chair'),
        ('https://www.pepperfry.com/category/bar-cabinets.html', 'Bar Cabinet'),
        ('https://www.pepperfry.com/category/bar-stools.html', 'Bar Stool'),
        ('https://www.pepperfry.com/category/crockery-units.html', 'Crockery Unit'),
        ('https://www.pepperfry.com/category/sideboards.html', 'Sideboard'),
    ],
    # Study & Office
    'study_office': [
        ('https://www.pepperfry.com/category/study-tables.html', 'Study Table'),
        ('https://www.pepperfry.com/category/computer-tables.html', 'Desk'),
        ('https://www.pepperfry.com/category/office-chairs.html', 'Office Chair'),
        ('https://www.pepperfry.com/category/office-furniture.html', 'Office Furniture'),
    ],
    # Home Decor
    'decor': [
        ('https://www.pepperfry.com/category/mirrors.html', 'Mirror'),
        ('https://www.pepperfry.com/category/vases.html', 'Vase'),
        ('https://www.pepperfry.com/category/wall-decor.html', 'Wall Decor'),
        ('https://www.pepperfry.com/category/clocks.html', 'Clock'),
        ('https://www.pepperfry.com/category/photo-frames.html', 'Photo Frame'),
        ('https://www.pepperfry.com/category/planters.html', 'Planter'),
        ('https://www.pepperfry.com/category/showpieces.html', 'Showpiece'),
        ('https://www.pepperfry.com/category/sculptures.html', 'Sculpture'),
        ('https://www.pepperfry.com/category/figurines.html', 'Figurine'),
        ('https://www.pepperfry.com/category/candle-holders.html', 'Candle Holder'),
        ('https://www.pepperfry.com/category/decorative-bowls.html', 'Bowl'),
        ('https://www.pepperfry.com/category/trays.html', 'Tray'),
    ],
    # Wall Art
    'wall_art': [
        ('https://www.pepperfry.com/category/wall-art.html', 'Wall Art'),
        ('https://www.pepperfry.com/category/canvas-paintings.html', 'Wall Art'),
        ('https://www.pepperfry.com/category/metal-wall-art.html', 'Wall Art'),
        ('https://www.pepperfry.com/category/wall-hangings.html', 'Wall Art'),
    ],
    # Furnishings
    'furnishing': [
        ('https://www.pepperfry.com/category/rugs.html', 'Rug'),
        ('https://www.pepperfry.com/category/carpets.html', 'Carpet'),
        ('https://www.pepperfry.com/category/curtains.html', 'Curtain'),
        ('https://www.pepperfry.com/category/cushion-covers.html', 'Cushion Cover'),
        ('https://www.pepperfry.com/category/throws.html', 'Throw'),
        ('https://www.pepperfry.com/category/bed-sheets.html', 'Bed Sheet'),
    ],
    # Lighting
    'lighting': [
        ('https://www.pepperfry.com/category/floor-lamps.html', 'Floor Lamp'),
        ('https://www.pepperfry.com/category/table-lamps.html', 'Table Lamp'),
        ('https://www.pepperfry.com/category/ceiling-lights.html', 'Ceiling Light'),
        ('https://www.pepperfry.com/category/wall-lights.html', 'Wall Light'),
        ('https://www.pepperfry.com/category/chandeliers.html', 'Chandelier'),
        ('https://www.pepperfry.com/category/pendant-lights.html', 'Pendant Light'),
        ('https://www.pepperfry.com/category/outdoor-lights.html', 'Outdoor Light'),
    ],
}


def generate_external_id(url: str) -> str:
    """Generate a unique external ID from URL"""
    # Try to extract product ID from URL
    match = re.search(r'-(\d+)\.html$', url)
    if match:
        return f"pf_{match.group(1)}"
    return hashlib.md5(url.encode()).hexdigest()[:16]


async def collect_products_with_pagination(page: Page, max_pages: int = 10) -> List[str]:
    """Collect product URLs across pagination pages"""
    product_urls = set()

    for page_num in range(1, max_pages + 1):
        # Collect current product links
        # Pepperfry uses /product/ in URLs
        links = await page.query_selector_all('a[href*="/product/"]')
        for link in links:
            href = await link.get_attribute('href')
            if href and '/product/' in href and '.html' in href:
                if href.startswith('/'):
                    href = f'https://www.pepperfry.com{href}'
                product_urls.add(href)

        print(f"  Page {page_num}: Found {len(product_urls)} products total")

        # Try to click next page
        next_button = await page.query_selector('.clip-pager-nav:last-child:not([disabled]), a[rel="next"]')
        if next_button:
            try:
                is_disabled = await next_button.get_attribute('disabled')
                if is_disabled:
                    print(f"  No more pages")
                    break
                await next_button.click()
                await asyncio.sleep(2)
            except Exception as e:
                print(f"  Pagination ended: {e}")
                break
        else:
            # Try URL-based pagination
            current_url = page.url
            if '?page=' in current_url:
                next_url = re.sub(r'page=\d+', f'page={page_num + 1}', current_url)
            else:
                separator = '&' if '?' in current_url else '?'
                next_url = f"{current_url}{separator}page={page_num + 1}"

            try:
                await page.goto(next_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(1)

                # Check if we got new products
                new_links = await page.query_selector_all('a[href*="/product/"]')
                if not new_links:
                    print(f"  No more products on page {page_num + 1}")
                    break
            except Exception:
                break

    return list(product_urls)


async def scrape_product_page(page: Page, url: str, category: str) -> Optional[Dict]:
    """Scrape individual product page"""
    try:
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(1)

        # Try to get JSON-LD data first
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
            print(f"  No JSON-LD product data for: {url}")
            return None

        # Extract name
        name = product_data.get('name')
        if not name:
            return None

        # Extract price from offers
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
            print(f"  No price for: {name}")
            return None

        # Extract description
        description = product_data.get('description')
        if not description:
            meta_desc = await page.query_selector('meta[name="description"]')
            if meta_desc:
                description = await meta_desc.get_attribute('content')

        # Extract images
        image_urls = []
        images = product_data.get('image', [])
        if isinstance(images, str):
            image_urls = [images]
        elif isinstance(images, list):
            image_urls = images[:10]

        # Extract availability
        is_available = True
        if isinstance(offers, dict):
            availability = offers.get('availability', '')
            is_available = 'InStock' in str(availability)

        # Extract brand
        brand = 'Pepperfry'
        brand_data = product_data.get('brand')
        if isinstance(brand_data, dict):
            brand = brand_data.get('name', 'Pepperfry')
        elif isinstance(brand_data, str):
            brand = brand_data

        # Extract SKU
        sku = product_data.get('sku')

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
            'is_on_sale': original_price is not None and original_price > price if original_price else False,
            'stock_status': 'in_stock' if is_available else 'out_of_stock',
            'currency': 'INR',
            'original_price': float(original_price) if original_price else None,
            'model': None,
            'sku': sku,
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
        page = await browser.new_page()

        # Process each category group
        for group_name, categories in CATEGORY_URLS.items():
            print(f"\n{'='*60}")
            print(f"Scraping {group_name.upper()}")
            print(f"{'='*60}")

            for cat_url, category in categories:
                print(f"\nCategory: {category}")
                print(f"URL: {cat_url}")

                try:
                    # Navigate to category page
                    await page.goto(cat_url, wait_until='networkidle', timeout=60000)
                    await asyncio.sleep(2)

                    # Collect products with pagination
                    product_urls = await collect_products_with_pagination(page)

                    # Filter out already seen URLs
                    new_urls = [url for url in product_urls if url not in seen_urls]
                    print(f"  New unique products: {len(new_urls)}")

                    # Scrape each product
                    for i, url in enumerate(new_urls):
                        seen_urls.add(url)
                        print(f"  [{i+1}/{len(new_urls)}] Scraping: {url.split('/')[-1][:50]}...")

                        product = await scrape_product_page(page, url, category)
                        if product:
                            all_products.append(product)

                        await asyncio.sleep(0.5)  # Be nice to the server

                except Exception as e:
                    print(f"  Error with category {cat_url}: {e}")
                    continue

        await browser.close()

    # Save results
    output_file = '/tmp/pepperfry_products.json'
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
