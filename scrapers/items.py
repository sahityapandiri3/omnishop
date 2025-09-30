"""
Scrapy items for product data
"""
import scrapy
from scrapy import Field
from itemloaders.processors import TakeFirst, MapCompose, Join
import re


def clean_text(value):
    """Clean text by removing extra whitespace and special characters"""
    if value:
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', value.strip())
        # Remove special characters that might cause issues
        cleaned = re.sub(r'[^\w\s\-.,()/$%]', '', cleaned)
        return cleaned
    return value


def clean_price(value):
    """Extract numeric price from text"""
    if value:
        # Remove currency symbols and extract number
        price_match = re.search(r'[\d,]+\.?\d*', str(value).replace(',', ''))
        if price_match:
            return float(price_match.group())
    return None


def clean_url(value):
    """Clean and validate URL"""
    if value:
        value = value.strip()
        if not value.startswith(('http://', 'https://')):
            return None
        return value
    return None


class ProductItem(scrapy.Item):
    """Main product item"""
    # Basic product information
    external_id = Field(
        output_processor=TakeFirst()
    )
    name = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    description = Field(
        input_processor=MapCompose(clean_text),
        output_processor=Join('\n')
    )

    # Pricing
    price = Field(
        input_processor=MapCompose(clean_price),
        output_processor=TakeFirst()
    )
    original_price = Field(
        input_processor=MapCompose(clean_price),
        output_processor=TakeFirst()
    )
    currency = Field(
        output_processor=TakeFirst()
    )

    # Product details
    brand = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    model = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    sku = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    # Categorization
    category = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    subcategory = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    # Source information
    source_website = Field(
        output_processor=TakeFirst()
    )
    source_url = Field(
        input_processor=MapCompose(clean_url),
        output_processor=TakeFirst()
    )

    # Images
    image_urls = Field()
    images = Field()

    # Availability
    is_available = Field(
        output_processor=TakeFirst()
    )
    is_on_sale = Field(
        output_processor=TakeFirst()
    )
    stock_status = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

    # Additional attributes (dimensions, materials, etc.)
    attributes = Field()

    # Metadata
    scraped_at = Field(
        output_processor=TakeFirst()
    )


class CategoryItem(scrapy.Item):
    """Category item for organizing products"""
    name = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    slug = Field(
        output_processor=TakeFirst()
    )
    parent_category = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    description = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    source_website = Field(
        output_processor=TakeFirst()
    )


class ImageItem(scrapy.Item):
    """Image item for product images"""
    original_url = Field(
        input_processor=MapCompose(clean_url),
        output_processor=TakeFirst()
    )
    alt_text = Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    display_order = Field(
        output_processor=TakeFirst()
    )
    is_primary = Field(
        output_processor=TakeFirst()
    )