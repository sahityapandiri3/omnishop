"""
Playwright-based scraper for Wooden Street - Decor, Furnishing, and Lighting
Only scrapes the non-furniture categories
"""
import asyncio
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page

# Only Decor, Furnishing, and Lighting categories
CATEGORY_URLS = {
    # Home Decor
    'decor': [
        ('https://www.woodenstreet.com/home-decors', 'Home Decor'),
        ('https://www.woodenstreet.com/wall-decor', 'Wall Decor'),
        ('https://www.woodenstreet.com/wall-mirrors', 'Mirror'),
        ('https://www.woodenstreet.com/wall-paintings', 'Wall Art'),
        ('https://www.woodenstreet.com/wall-arts', 'Wall Art'),
        ('https://www.woodenstreet.com/clocks', 'Clock'),
        ('https://www.woodenstreet.com/vases', 'Vase'),
        ('https://www.woodenstreet.com/table-showpiece', 'Showpiece'),
        ('https://www.woodenstreet.com/photo-frames', 'Photo Frame'),
        ('https://www.woodenstreet.com/planters', 'Planter'),
    ],
    # Furnishing
    'furnishing': [
        ('https://www.woodenstreet.com/home-furnishing', 'Home Furnishing'),
        ('https://www.woodenstreet.com/sofa-covers', 'Sofa Cover'),
        ('https://www.woodenstreet.com/cushion-covers', 'Cushion Cover'),
        ('https://www.woodenstreet.com/bed-sheets', 'Bed Sheet'),
        ('https://www.woodenstreet.com/rugs-and-carpets', 'Rug'),
        ('https://www.woodenstreet.com/table-runner', 'Table Runner'),
        ('https://www.woodenstreet.com/chair-covers', 'Chair Cover'),
        ('https://www.woodenstreet.com/curtains', 'Curtain'),
        ('https://www.woodenstreet.com/blankets', 'Blanket'),
    ],
    # Lighting
    'lighting': [
        ('https://www.woodenstreet.com/lamps', 'Lamp'),
        ('https://www.woodenstreet.com/floor-lamps', 'Floor Lamp'),
        ('https://www.woodenstreet.com/table-lamps', 'Table Lamp'),
        ('https://www.woodenstreet.com/chandeliers', 'Chandelier'),
        ('https://www.woodenstreet.com/wall-lights', 'Wall Light'),
        ('https://www.woodenstreet.com/hanging-lights', 'Hanging Light'),
        ('https://www.woodenstreet.com/ceiling-lights', 'Ceiling Light'),
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
        # Collect current product links - Wooden Street uses /product/ in URLs
        links = await page.query_selector_all('a[href*="/product/"]')
        for link in links:
            href = await link.get_attribute('href')
            if href and '/product/' in href:
                if href.startswith('/'):
                    href = f'https://www.woodenstreet.com{href}'
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

        # Extract price from offers (Wooden Street uses priceSpecification)
        price = None
        original_price = None
        offers = product_data.get('offers', {})
        if isinstance(offers, dict):
            # First check for direct price
            if offers.get('price'):
                price = offers.get('price')
            # Then check priceSpecification
            elif offers.get('priceSpecification'):
                price_spec = offers['priceSpecification']
                if isinstance(price_spec, list) and price_spec:
                    # First item is usually sale price
                    price = price_spec[0].get('price')
                    # Look for ListPrice for original
                    for spec in price_spec:
                        if spec.get('priceType') and 'ListPrice' in str(spec.get('priceType', '')):
                            original_price = spec.get('price')
                            break

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
        brand = 'Wooden Street'
        brand_data = product_data.get('brand')
        if isinstance(brand_data, dict):
            brand = brand_data.get('name', 'Wooden Street')

        # Extract attributes
        attributes = {}

        return {
            'name': name,
            'price': float(price) if price else None,
            'external_id': generate_external_id(url),
            'description': description,
            'brand': brand,
            'category': category,
            'source_website': 'woodenstreet',
            'source_url': url,
            'scraped_at': datetime.utcnow().isoformat(),
            'image_urls': image_urls,
            'attributes': attributes,
            'is_available': is_available,
            'is_on_sale': original_price is not None and original_price > price if original_price else False,
            'stock_status': 'in_stock' if is_available else 'out_of_stock',
            'currency': 'INR',
            'original_price': float(original_price) if original_price else None,
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

                        await asyncio.sleep(0.5)  # Be nice to the server

                except Exception as e:
                    print(f"  Error with category {cat_url}: {e}")
                    continue

        await browser.close()

    # Save results
    output_file = '/tmp/woodenstreet_decor_products.json'
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
