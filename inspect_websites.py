#!/usr/bin/env python3
"""
Quick script to inspect website HTML structure for selector updates
"""
import requests
from bs4 import BeautifulSoup

def inspect_page(url, site_name):
    print(f"\n{'='*60}")
    print(f"Inspecting: {site_name}")
    print(f"URL: {url}")
    print(f"{'='*60}\n")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        print(f"Status Code: {response.status_code}")
        print(f"Final URL: {response.url}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find product links
            print("\n--- Product Links ---")
            product_links = soup.find_all('a', href=lambda x: x and '/product' in x)
            print(f"Found {len(product_links)} product links")
            if product_links:
                for i, link in enumerate(product_links[:5]):
                    href = link.get('href')
                    if not href.startswith('http'):
                        href = requests.compat.urljoin(url, href)
                    print(f"{i+1}. {href}")
                    print(f"   Classes: {link.get('class')}")

            # Check page title
            title = soup.find('title')
            if title:
                print(f"\nPage Title: {title.string}")

            # Check for navigation/menu links to find collections
            print("\n--- Navigation Links ---")
            nav_links = soup.find_all('a', href=True)
            collection_links = [a.get('href') for a in nav_links if 'shop' in a.get('href', '').lower() or 'collection' in a.get('href', '').lower() or 'category' in a.get('href', '').lower()]
            collection_links = list(set(collection_links))[:10]
            for link in collection_links:
                print(f"  - {link}")

        else:
            print(f"Failed to fetch page")

    except Exception as e:
        print(f"Error: {e}")

def inspect_product_page(url, site_name):
    print(f"\n{'='*60}")
    print(f"Inspecting PRODUCT PAGE: {site_name}")
    print(f"URL: {url}")
    print(f"{'='*60}\n")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Product title
            print("\n--- Product Title ---")
            for selector in ['h1', '.product-title', '.product__title', '.product-single__title']:
                title = soup.select_one(selector)
                if title:
                    print(f"Found with '{selector}': {title.get_text(strip=True)[:100]}")
                    print(f"  Element: <{title.name}> class={title.get('class')}")

            # Product price
            print("\n--- Product Price ---")
            for selector in ['.price', '.product-price', '.money', '[itemprop="price"]']:
                prices = soup.select(selector)
                if prices:
                    print(f"Found {len(prices)} with '{selector}':")
                    for p in prices[:3]:
                        print(f"  {p.get_text(strip=True)} (class={p.get('class')})")

            # Product images
            print("\n--- Product Images ---")
            imgs = soup.find_all('img', src=lambda x: x and ('product' in x.lower() or 'cdn' in x.lower()))
            print(f"Found {len(imgs)} product images")
            if imgs:
                print(f"  Example: {imgs[0].get('src')[:80]}")
                print(f"  Classes: {imgs[0].get('class')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    # Inspect Pelican Essentials homepage
    inspect_page('https://www.pelicanessentials.com/', 'Pelican Essentials - Homepage')

    # Inspect a Pelican product page
    inspect_product_page('https://www.pelicanessentials.com/products/slumbr-sleeper-sofa-sofa-cum-bed-7-feet', 'Pelican Essentials - Product')

    # Inspect Sage Living homepage
    inspect_page('https://www.sageliving.in/', 'Sage Living - Homepage')

    # Try to find a Sage Living product
    print("\n" + "="*60)
    print("Searching for Sage Living shop page...")
    print("="*60)
    inspect_page('https://www.sageliving.in/shop/', 'Sage Living - Shop Page')
