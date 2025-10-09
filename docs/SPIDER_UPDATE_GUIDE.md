# Spider Update Guide: How to Update CSS Selectors for Web Scraping

## Overview

This guide provides step-by-step instructions for updating the Scrapy spiders to work with current website structures. Modern e-commerce websites frequently update their HTML structure, requiring periodic updates to spider selectors.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Understanding the Spider Structure](#understanding-the-spider-structure)
3. [Inspecting Website Structure](#inspecting-website-structure)
4. [Updating Selectors](#updating-selectors)
5. [Testing Your Changes](#testing-your-changes)
6. [Common Issues and Solutions](#common-issues-and-solutions)

---

## Prerequisites

### Tools You'll Need

1. **Modern Web Browser** (Chrome/Firefox recommended)
   - Built-in Developer Tools for inspecting HTML

2. **Scrapy Shell** for testing selectors
   ```bash
   source venv/bin/activate
   scrapy shell "https://example.com"
   ```

3. **Optional but Recommended:**
   - **SelectorGadget** (Chrome extension) - Visual CSS selector tool
   - **Scrapy-Splash** - For JavaScript-heavy websites

### Knowledge Requirements

- Basic understanding of HTML/CSS
- CSS selector syntax
- XPath (optional but helpful)

---

## Understanding the Spider Structure

### Spider Files Location

```
/Users/sahityapandiri/Omnishop/scrapers/spiders/
├── base_spider.py          # Base class with common methods
├── westelm_spider.py       # West Elm spider
└── orangetree_spider.py    # Orange Tree spider
```

### Key Methods to Update

Each spider has several extraction methods that need CSS selectors:

1. **`parse(self, response)`** - Extracts product links from category pages
2. **`parse_product(self, response)`** - Extracts data from product pages
3. **`extract_product_name()`** - Product title
4. **`extract_product_price()`** - Product pricing
5. **`extract_product_description()`** - Product description
6. **`extract_product_images()`** - Product images
7. **`extract_product_attributes()`** - Dimensions, materials, etc.

---

## Inspecting Website Structure

### Step 1: Open the Website in Your Browser

For West Elm:
```
https://www.westelm.com/shop/furniture/sofas-sectionals/
```

For Orange Tree:
```
https://www.orangetree.com/living-room/
```

### Step 2: Open Browser Developer Tools

- **Chrome/Firefox**: Press `F12` or `Ctrl+Shift+I` (Windows/Linux) / `Cmd+Option+I` (Mac)
- **Safari**: Enable developer tools in Preferences → Advanced → Show Develop menu, then press `Cmd+Option+I`

### Step 3: Inspect Product Elements

#### For Category Pages (Product Listings):

1. **Right-click on a product card** → "Inspect Element"
2. Look for the parent container that wraps each product
3. Identify patterns in class names or data attributes

**What to look for:**
```html
<!-- Example structure -->
<div class="product-grid">
    <div class="product-card" data-product-id="12345">
        <a href="/products/modern-sofa" class="product-link">
            <img src="sofa.jpg" />
            <h3 class="product-name">Modern Sofa</h3>
            <span class="product-price">$899</span>
        </a>
    </div>
</div>
```

**Extract patterns:**
- Product link selector: `.product-link::attr(href)` or `a.product-card-link::attr(href)`
- Product card: `.product-card` or `[data-product-id]`

#### For Product Detail Pages:

1. Navigate to an individual product page
2. Inspect key elements:
   - Product title (usually an `<h1>`)
   - Price (often in a `<span>` or `<div>` with "price" in the class)
   - Images (look for image gallery or carousel)
   - Description (usually in a section with "description" or "details")
   - Attributes (dimensions, materials, often in a table or list)

### Step 4: Test Selectors in Browser Console

You can test CSS selectors directly in the browser console:

```javascript
// Test if selector finds elements
document.querySelectorAll('.product-card')

// Test specific selector
document.querySelector('.product-name')?.textContent

// Get all product links
[...document.querySelectorAll('.product-link')].map(a => a.href)
```

### Step 5: Use Scrapy Shell for Advanced Testing

```bash
# Activate virtual environment
source venv/bin/activate

# Open Scrapy shell (may need custom headers to avoid 403)
scrapy shell -s USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" "https://www.westelm.com/shop/furniture/sofas-sectionals/"
```

**Test selectors in Scrapy shell:**
```python
# CSS selector
response.css('.product-card a::attr(href)').getall()

# XPath
response.xpath('//a[@class="product-link"]/@href').getall()

# Extract text
response.css('.product-name::text').get()
```

---

## Updating Selectors

### Example: Updating West Elm Spider

Let's say you found the current structure uses:
- Product links: `a.product-tile-link::attr(href)` (old)
- Actual structure: `a[data-testid="product-card-link"]::attr(href)` (new)

#### File: `scrapers/spiders/westelm_spider.py`

**Before:**
```python
def parse(self, response):
    """Parse category pages and extract product links"""
    self.logger.info(f"Parsing category page: {response.url}")

    # Extract product links from category page
    product_links = response.css('a.product-tile-link::attr(href)').getall()
```

**After:**
```python
def parse(self, response):
    """Parse category pages and extract product links"""
    self.logger.info(f"Parsing category page: {response.url}")

    # Extract product links from category page (updated selector)
    product_links = response.css('a[data-testid="product-card-link"]::attr(href)').getall()

    # Fallback to alternative selectors if primary fails
    if not product_links:
        product_links = response.css('a.product-tile::attr(href)').getall()
    if not product_links:
        product_links = response.css('div.product-grid a::attr(href)').getall()
```

### Updating Multiple Selectors with Fallbacks

**Best Practice:** Use multiple fallback selectors to make spiders more resilient

```python
def extract_product_name(self, response) -> Optional[str]:
    """Extract product name with multiple fallback selectors"""
    selectors = [
        'h1[data-testid="product-title"]::text',      # Primary
        'h1.product-name::text',                       # Fallback 1
        'div.product-details h1::text',                # Fallback 2
        'meta[property="og:title"]::attr(content)',    # Fallback 3 (meta tag)
    ]

    for selector in selectors:
        name = self.extract_text(response.css(selector))
        if name:
            self.logger.debug(f"Found product name with selector: {selector}")
            return self.clean_text(name)

    self.logger.warning(f"Could not find product name for {response.url}")
    return None
```

### Updating Image Selectors

```python
def extract_product_images(self, response) -> List[str]:
    """Extract product image URLs with multiple strategies"""
    image_urls = []

    # Strategy 1: Look for data attributes (common in modern sites)
    data_images = response.css('img[data-src]::attr(data-src)').getall()
    image_urls.extend(data_images)

    # Strategy 2: Regular src attribute
    if not image_urls:
        src_images = response.css('.product-images img::attr(src)').getall()
        image_urls.extend(src_images)

    # Strategy 3: Background images in div elements
    if not image_urls:
        bg_images = response.css('[style*="background-image"]::attr(style)').getall()
        for style in bg_images:
            # Extract URL from background-image: url('...')
            import re
            match = re.search(r'url\(["\']?([^"\')]+)["\']?\)', style)
            if match:
                image_urls.append(match.group(1))

    # Strategy 4: JSON-LD structured data
    if not image_urls:
        scripts = response.css('script[type="application/ld+json"]::text').getall()
        for script in scripts:
            try:
                import json
                data = json.loads(script)
                if 'image' in data:
                    imgs = data['image'] if isinstance(data['image'], list) else [data['image']]
                    image_urls.extend(imgs)
            except:
                pass

    # Clean and deduplicate
    cleaned_urls = []
    for url in image_urls:
        if url and url not in cleaned_urls:
            full_url = urljoin(response.url, url)
            cleaned_urls.append(full_url)

    return cleaned_urls[:10]  # Limit to first 10 images
```

---

## Testing Your Changes

### Step 1: Test in Scrapy Shell

```bash
source venv/bin/activate

# Test with the updated spider
scrapy shell -s USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" "https://www.westelm.com/products/modern-sofa/"
```

**In the shell:**
```python
# Import your spider
from scrapers.spiders.westelm_spider import WestElmSpider

# Create spider instance
spider = WestElmSpider()

# Test extraction methods
name = spider.extract_product_name(response)
print(f"Product Name: {name}")

price = spider.extract_product_price(response)
print(f"Price: ${price}")

images = spider.extract_product_images(response)
print(f"Found {len(images)} images")
```

### Step 2: Run Limited Test Scrape

```bash
# Scrape just 3 products, no database storage
scrapy crawl westelm \
    -s ITEM_PIPELINES={} \
    -s CLOSESPIDER_ITEMCOUNT=3 \
    -s DOWNLOAD_DELAY=2 \
    -o test_westelm.json

# Check the output
cat test_westelm.json | python -m json.tool
```

### Step 3: Validate Output

Check the JSON output for:
- ✅ Product names are present and correct
- ✅ Prices are extracted as numbers
- ✅ Images URLs are valid
- ✅ Descriptions are meaningful
- ✅ No null/empty required fields

### Step 4: Run Full Test with Database

```bash
# Run with database pipeline, limited items
source venv/bin/activate
python scripts/run_scraping.py spider westelm --delay 2
```

Check database:
```sql
SELECT COUNT(*) FROM products WHERE source_website = 'westelm.com';
SELECT name, price, brand FROM products WHERE source_website = 'westelm.com' LIMIT 5;
```

---

## Common Issues and Solutions

### Issue 1: 403 Forbidden Error

**Symptoms:** Spider gets blocked immediately

**Solutions:**

1. **Add realistic headers:**
```python
# In spider class
custom_settings = {
    **BaseProductSpider.custom_settings,
    'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'DOWNLOAD_DELAY': 3,
    'RANDOMIZE_DOWNLOAD_DELAY': 1.0,
}
```

2. **Rotate user agents:**
```bash
pip install scrapy-user-agents
```

3. **Use proxies** (for production):
```python
'DOWNLOADER_MIDDLEWARES': {
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
}
```

### Issue 2: Empty Results (JavaScript Rendering)

**Symptoms:** Spider runs but extracts no data

**Diagnosis:**
```python
# In scrapy shell
len(response.body)  # Should be > 0
'<div id="root"></div>' in response.text  # If True, likely React/Vue SPA
```

**Solutions:**

1. **Use Scrapy-Splash** (recommended):
```bash
# Install
pip install scrapy-splash

# Run Splash in Docker
docker run -p 8050:8050 scrapinghub/splash

# Update settings
SPLASH_URL = 'http://localhost:8050'
DOWNLOADER_MIDDLEWARES = {
    'scrapy_splash.SplashCookiesMiddleware': 723,
    'scrapy_splash.SplashMiddleware': 725,
    'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
}
```

2. **Use Selenium** (alternative):
```bash
pip install selenium scrapy-selenium
```

### Issue 3: Selector Returns Empty List

**Symptoms:** `response.css('selector').getall()` returns `[]`

**Debug steps:**

1. **Check if element exists:**
```python
# In scrapy shell
print(response.text)  # View raw HTML
```

2. **Try different selector types:**
```python
# CSS
response.css('.product-name::text').get()

# XPath
response.xpath('//h1[@class="product-name"]/text()').get()

# Attribute selectors
response.css('[data-product-name]::attr(data-product-name)').get()
```

3. **Look for dynamic class names:**
```html
<!-- Some sites use generated class names -->
<div class="Product__Title-sc-1h74qkv-0 dRzKFW">Product Name</div>
```

**Solution:** Use more generic selectors or data attributes

### Issue 4: Price Extraction Fails

**Common price formats:**
```html
<span class="price">$899.99</span>
<div class="price-box" data-price="899.99">$899.99</div>
<script>{"price": 899.99}</script>
```

**Robust price extraction:**
```python
def extract_product_price(self, response) -> Optional[float]:
    # Try data attribute first
    price_attr = response.css('[data-price]::attr(data-price)').get()
    if price_attr:
        return float(price_attr)

    # Try visible price text
    price_text = response.css('.price::text, .product-price::text').get()
    if price_text:
        return self.extract_price(price_text)  # Uses regex to extract number

    # Try JSON-LD
    scripts = response.css('script[type="application/ld+json"]::text').getall()
    for script in scripts:
        try:
            data = json.loads(script)
            if 'offers' in data:
                return float(data['offers'].get('price', 0))
        except:
            pass

    return None
```

### Issue 5: Images Not Downloading

**Check:**
1. Image URLs are absolute (not relative)
2. Images pipeline is enabled
3. `IMAGES_STORE` path exists and is writable

**Fix relative URLs:**
```python
from urllib.parse import urljoin

full_url = urljoin(response.url, relative_url)
```

---

## Advanced Techniques

### Using JSON-LD for Reliable Data

Many modern sites include structured data:

```python
def extract_from_json_ld(self, response) -> dict:
    """Extract product data from JSON-LD structured data"""
    scripts = response.css('script[type="application/ld+json"]::text').getall()

    for script in scripts:
        try:
            data = json.loads(script)
            if data.get('@type') == 'Product':
                return {
                    'name': data.get('name'),
                    'price': float(data.get('offers', {}).get('price', 0)),
                    'description': data.get('description'),
                    'image': data.get('image'),
                    'brand': data.get('brand', {}).get('name'),
                    'sku': data.get('sku'),
                }
        except Exception as e:
            self.logger.debug(f"Failed to parse JSON-LD: {e}")

    return {}
```

### Using API Endpoints Instead of Scraping HTML

Sometimes websites load data via API:

```python
import json

def start_requests(self):
    """Use API endpoint instead of HTML pages"""
    api_url = "https://www.example.com/api/products?category=sofas"
    yield scrapy.Request(api_url, callback=self.parse_api)

def parse_api(self, response):
    """Parse JSON API response"""
    data = json.loads(response.text)

    for product in data['products']:
        yield self.create_product_item(
            response=response,
            name=product['name'],
            price=product['price'],
            external_id=product['id'],
            description=product['description'],
            # ...
        )
```

---

## Checklist for Spider Updates

- [ ] Inspected website in browser developer tools
- [ ] Identified current HTML structure
- [ ] Updated category page selectors (`parse` method)
- [ ] Updated product page selectors (all `extract_*` methods)
- [ ] Added fallback selectors for resilience
- [ ] Tested in Scrapy shell
- [ ] Ran limited test scrape (3-5 products)
- [ ] Validated output quality
- [ ] Tested with database pipeline
- [ ] Documented changes in code comments
- [ ] Updated `custom_settings` if needed (delays, headers)

---

## Quick Reference: Selector Syntax

### CSS Selectors

```python
# Class
response.css('.product-name::text').get()

# ID
response.css('#product-title::text').get()

# Attribute
response.css('img::attr(src)').get()
response.css('[data-price]::attr(data-price)').get()

# Multiple classes
response.css('.product.featured::text').get()

# Descendant
response.css('.product-card .price::text').get()

# Direct child
response.css('.product-card > h3::text').get()

# Get all matches
response.css('.product-link::attr(href)').getall()
```

### XPath

```python
# By class
response.xpath('//div[@class="product-name"]/text()').get()

# By attribute
response.xpath('//img/@src').get()

# Contains text
response.xpath('//a[contains(text(), "Add to Cart")]/@href').get()

# Multiple conditions
response.xpath('//div[@class="price" and @data-sale="true"]/text()').get()
```

---

## Contact & Support

For issues or questions:
1. Check Scrapy documentation: https://docs.scrapy.org/
2. Review spider logs in `logs/scraping.log`
3. Use `self.logger.debug()` to add debug output

## Next Steps

After updating the spiders:
1. Run batch scraping: `python scripts/run_scraping.py batch`
2. Monitor `scraping_logs` table in database for stats
3. Set up scheduled scraping with cron jobs (see `utils/scraping_manager.py`)
