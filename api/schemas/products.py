"""
Pydantic schemas for product-related API endpoints
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ProductImageSchema(BaseModel):
    """Product image schema"""
    id: int
    product_id: int
    original_url: str
    thumbnail_url: Optional[str] = None
    medium_url: Optional[str] = None
    large_url: Optional[str] = None
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    display_order: int = 0
    is_primary: bool = False

    class Config:
        from_attributes = True


class ProductAttributeSchema(BaseModel):
    """Product attribute schema"""
    id: int
    product_id: int
    attribute_name: str
    attribute_value: str
    attribute_type: str = "text"

    class Config:
        from_attributes = True


class CategorySchema(BaseModel):
    """Category schema"""
    id: int
    name: str
    slug: str
    parent_id: Optional[int] = None
    description: Optional[str] = None
    product_count: Optional[int] = 0

    class Config:
        from_attributes = True


class ProductSchema(BaseModel):
    """Complete product schema"""
    id: int
    external_id: str
    name: str
    description: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    currency: str = "USD"
    brand: Optional[str] = None
    model: Optional[str] = None
    sku: Optional[str] = None
    source_website: str
    source_url: str
    is_available: bool = True
    is_on_sale: bool = False
    stock_status: str = "in_stock"
    category_id: Optional[int] = None
    category: Optional[CategorySchema] = None
    images: List[ProductImageSchema] = []
    attributes: List[ProductAttributeSchema] = []
    scraped_at: datetime
    last_updated: datetime

    class Config:
        from_attributes = True


class ProductSummarySchema(BaseModel):
    """Simplified product schema for listings"""
    id: int
    name: str
    price: float
    original_price: Optional[float] = None
    currency: str = "USD"
    brand: Optional[str] = None
    source_website: str
    is_available: bool = True
    is_on_sale: bool = False
    primary_image: Optional[ProductImageSchema] = None
    category: Optional[CategorySchema] = None

    class Config:
        from_attributes = True


class SortField(str, Enum):
    """Available sort fields"""
    price = "price"
    name = "name"
    created_at = "created_at"
    popularity = "popularity"


class SortDirection(str, Enum):
    """Sort directions"""
    asc = "asc"
    desc = "desc"


class ProductFilters(BaseModel):
    """Product filtering parameters"""
    category_id: Optional[int] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    brand: Optional[List[str]] = None
    source_website: Optional[List[str]] = None
    is_available: Optional[bool] = None
    is_on_sale: Optional[bool] = None
    search: Optional[str] = Field(None, max_length=200)

    @validator('max_price')
    def validate_price_range(cls, v, values):
        if v is not None and 'min_price' in values and values['min_price'] is not None:
            if v < values['min_price']:
                raise ValueError('max_price must be greater than min_price')
        return v


class ProductQuery(BaseModel):
    """Product query parameters"""
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)
    sort_by: SortField = SortField.created_at
    sort_direction: SortDirection = SortDirection.desc
    filters: Optional[ProductFilters] = None


class PaginatedResponse(BaseModel):
    """Paginated response schema"""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class ProductSearchResponse(PaginatedResponse):
    """Product search response"""
    items: List[ProductSummarySchema]
    query: Optional[str] = None
    filters_applied: Optional[Dict[str, Any]] = None


class ProductDetailResponse(BaseModel):
    """Single product detail response"""
    product: ProductSchema
    related_products: List[ProductSummarySchema] = []


class ProductRecommendationRequest(BaseModel):
    """Product recommendation request"""
    style_preferences: Optional[Dict[str, Any]] = None
    price_range: Optional[Dict[str, float]] = None
    room_type: Optional[str] = None
    categories: Optional[List[str]] = None
    limit: int = Field(10, ge=1, le=50)


class ProductStatsResponse(BaseModel):
    """Product statistics response"""
    total_products: int
    by_source: Dict[str, int]
    by_category: Dict[str, int]
    price_ranges: Dict[str, int]
    availability: Dict[str, int]