"""
Playwright-based scraper for Durian furniture
Handles JavaScript infinite scroll pagination
"""
import asyncio
import json
import re
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page

# Category URLs for Living, Dining, and Bedroom
CATEGORY_URLS = {
    # Living Room
    'living': [
        ('https://www.durian.in/buy-furniture/all-sofas', 'Sofa'),
        ('https://www.durian.in/buy-furniture/sectional-sofas', 'Sectional Sofa'),
        ('https://www.durian.in/buy-furniture/premium-sofas', 'Sofa'),
        ('https://www.durian.in/buy-furniture/reclining-sofas', 'Recliner'),
        ('https://www.durian.in/buy-furniture/all-living-chairs', 'Accent Chair'),
        ('https://www.durian.in/buy-furniture/all-living-storage', 'Storage'),
        ('https://www.durian.in/buy-furniture/all-coffee-tables', 'Coffee Table'),
        ('https://www.durian.in/buy-furniture/tv-unit', 'TV Unit'),
        ('https://www.durian.in/buy-furniture/shoe-cabinet', 'Shoe Rack'),
    ],
    # Bedroom
    'bedroom': [
        ('https://www.durian.in/buy-furniture/all-beds', 'Bed'),
        ('https://www.durian.in/buy-furniture/designer-beds', 'Bed'),
        ('https://www.durian.in/buy-furniture/solid-wood-beds', 'Bed'),
        ('https://www.durian.in/buy-furniture/king-size-beds', 'King Bed'),
        ('https://www.durian.in/buy-furniture/queen-size-beds', 'Queen Bed'),
        ('https://www.durian.in/buy-furniture/hydraulic-beds', 'Bed'),
        ('https://www.durian.in/buy-furniture/upholstered-beds', 'Bed'),
        ('https://www.durian.in/buy-furniture/single-beds', 'Single Bed'),
        ('https://www.durian.in/buy-furniture/all-wardrobes', 'Wardrobe'),
        ('https://www.durian.in/buy-furniture/2-door-wardrobe', 'Wardrobe'),
        ('https://www.durian.in/buy-furniture/3-door-wardrobe', 'Wardrobe'),
        ('https://www.durian.in/buy-furniture/4-door-wardrobe', 'Wardrobe'),
        ('https://www.durian.in/buy-furniture/all-chest-of-drawers', 'Chest of Drawers'),
        ('https://www.durian.in/buy-furniture/all-bedroom-storage', 'Storage'),
        ('https://www.durian.in/buy-furniture/dressing-tables', 'Dresser'),
        ('https://www.durian.in/buy-furniture/bedside-tables', 'Nightstand'),
    ],
    # Dining
    'dining': [
        ('https://www.durian.in/buy-furniture/all-dining-sets', 'Dining Table'),
        ('https://www.durian.in/buy-furniture/4-seater-dining-set', 'Dining Table'),
        ('https://www.durian.in/buy-furniture/6-seater-dining-set', 'Dining Table'),
        ('https://www.durian.in/buy-furniture/8-seater-dining-set', 'Dining Table'),
        ('https://www.durian.in/buy-furniture/wooden-dining-set', 'Dining Table'),
        ('https://www.durian.in/buy-furniture/marble-dining-set', 'Dining Table'),
        ('https://www.durian.in/buy-furniture/glass-dining-set', 'Dining Table'),
        ('https://www.durian.in/buy-furniture/all-dining-seating', 'Dining Chair'),
        ('https://www.durian.in/buy-furniture/all-dining-storage', 'Sideboard'),
        ('https://www.durian.in/buy-furniture/bar-cabinets', 'Cabinet'),
        ('https://www.durian.in/buy-furniture/crockery-units', 'Cabinet'),
    ],
}


def generate_external_id(url: str) -> str:
    """Generate a unique external ID from URL"""
    return hashlib.md5(url.encode()).hexdigest()[:16]


async def scroll_and_collect_products(page: Page, max_scrolls: int = 30) -> List[str]:
    """Scroll down the page to load all products via infinite scroll"""
    product_urls = set()
    prev_count = 0
    no_change_count = 0

    for i in range(max_scrolls):
        # Collect current product links
        links = await page.query_selector_all('a[href*="/product/"]')
        for link in links:
            href = await link.get_attribute('href')
            if href and '/product/' in href:
                if href.startswith('/'):
                    href = f'https://www.durian.in{href}'
                product_urls.add(href)

        current_count = len(product_urls)
        print(f"  Scroll {i+1}: Found {current_count} products")

        # Check if we're getting new products
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
        await asyncio.sleep(2)  # Wait for products to load

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
            if not price and offers.get('priceSpecification'):
                price_spec = offers['priceSpecification']
                if isinstance(price_spec, list) and price_spec:
                    price = price_spec[0].get('price')

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

        # Extract attributes
        attributes = {}

        # Try to get warranty from description
        if description:
            warranty_match = re.search(r'(\d+)\s*(?:year|yr)s?\s*warranty', description, re.IGNORECASE)
            if warranty_match:
                attributes['warranty'] = warranty_match.group(0)

        return {
            'name': name,
            'price': float(price) if price else None,
            'external_id': generate_external_id(url),
            'description': description,
            'brand': 'Durian',
            'category': category,
            'source_website': 'durian',
            'source_url': url,
            'scraped_at': datetime.utcnow().isoformat(),
            'image_urls': image_urls,
            'attributes': attributes,
            'is_available': is_available,
            'is_on_sale': False,
            'stock_status': 'in_stock' if is_available else 'out_of_stock',
            'currency': 'INR',
            'original_price': original_price,
            'model': None,
            'sku': None,
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
            print(f"Scraping {group_name.upper()} categories")
            print(f"{'='*60}")

            for cat_url, category in categories:
                print(f"\nCategory: {category}")
                print(f"URL: {cat_url}")

                try:
                    # Navigate to category page
                    await page.goto(cat_url, wait_until='networkidle', timeout=60000)
                    await asyncio.sleep(2)

                    # Scroll to load all products
                    product_urls = await scroll_and_collect_products(page)

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

                        await asyncio.sleep(1)  # Be nice to the server

                except Exception as e:
                    print(f"  Error with category {cat_url}: {e}")
                    continue

        await browser.close()

    # Save results
    output_file = '/tmp/durian_products_full.json'
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
