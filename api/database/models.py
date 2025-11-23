"""
Database models for Omnishop scraping system
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class ScrapingStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    IN_PROGRESS = "in_progress"


class Category(Base):
    """Product categories with hierarchical structure"""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("Product", back_populates="category")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class Product(Base):
    """Main product information"""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), nullable=False, index=True)  # ID from source website
    name = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True, index=True)  # Allow NULL for enquiry-based pricing
    original_price = Column(Float, nullable=True)  # For sale items
    currency = Column(String(3), default="USD")
    brand = Column(String(100), nullable=True, index=True)
    model = Column(String(100), nullable=True)
    sku = Column(String(100), nullable=True, index=True)

    # Source information
    source_website = Column(String(50), nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Product status
    is_available = Column(Boolean, default=True, index=True)
    is_on_sale = Column(Boolean, default=False, index=True)
    stock_status = Column(String(20), default="in_stock")

    # Category relationship
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    category = relationship("Category", back_populates="products")

    # Relationships
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    attributes = relationship("ProductAttribute", back_populates="product", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_product_source_external", "source_website", "external_id"),
        Index("idx_product_price_category", "price", "category_id"),
        Index("idx_product_brand_category", "brand", "category_id"),
    )

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name[:50]}...', price={self.price})>"


class ProductImage(Base):
    """Product images with multiple sizes"""

    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    # Image URLs
    original_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text, nullable=True)
    medium_url = Column(Text, nullable=True)
    large_url = Column(Text, nullable=True)

    # Image metadata
    alt_text = Column(String(500), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_size = Column(Integer, nullable=True)  # in bytes
    file_format = Column(String(10), nullable=True)  # jpg, png, webp, etc.

    # Order for display
    display_order = Column(Integer, default=0, index=True)
    is_primary = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="images")

    def __repr__(self):
        return f"<ProductImage(id={self.id}, product_id={self.product_id}, is_primary={self.is_primary})>"


class ProductAttribute(Base):
    """Additional product attributes (dimensions, materials, etc.)"""

    __tablename__ = "product_attributes"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    attribute_name = Column(String(100), nullable=False, index=True)
    attribute_value = Column(Text, nullable=False)
    attribute_type = Column(String(20), default="text")  # text, number, boolean, json

    # Extraction metadata
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    extraction_method = Column(String(50), nullable=True)  # gemini_vision, text_nlp, merged, manual

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="attributes")

    # Indexes
    __table_args__ = (
        Index("idx_attribute_name_value", "attribute_name", "attribute_value"),
        Index("idx_attribute_product_name", "product_id", "attribute_name"),
    )

    def __repr__(self):
        return f"<ProductAttribute(product_id={self.product_id}, name='{self.attribute_name}', value='{self.attribute_value[:50]}...')>"


class ScrapingLog(Base):
    """Logs for scraping operations"""

    __tablename__ = "scraping_logs"

    id = Column(Integer, primary_key=True, index=True)
    website = Column(String(50), nullable=False, index=True)
    spider_name = Column(String(50), nullable=False)

    # Timing
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Results
    status = Column(Enum(ScrapingStatus), nullable=False, index=True)
    products_found = Column(Integer, default=0)
    products_processed = Column(Integer, default=0)
    products_saved = Column(Integer, default=0)
    images_downloaded = Column(Integer, default=0)

    # Error information
    errors_count = Column(Integer, default=0)
    error_messages = Column(JSON, nullable=True)

    # Statistics
    pages_scraped = Column(Integer, default=0)
    requests_made = Column(Integer, default=0)
    average_response_time = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<ScrapingLog(id={self.id}, website='{self.website}', status='{self.status.value}', products_saved={self.products_saved})>"


class ProductSearchView(Base):
    """Materialized view for fast product searching"""

    __tablename__ = "product_search_view"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, index=True)
    name = Column(String(500), index=True)
    description_text = Column(Text)
    price = Column(Float, index=True)
    brand = Column(String(100), index=True)
    category_name = Column(String(100), index=True)
    category_path = Column(String(500))  # Full category hierarchy
    source_website = Column(String(50), index=True)
    is_available = Column(Boolean, index=True)
    primary_image_url = Column(Text)

    # Search vectors for full-text search
    search_vector = Column(Text)  # Concatenated searchable text

    last_updated = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<ProductSearchView(product_id={self.product_id}, name='{self.name[:50]}...')>"


class ChatSession(Base):
    """Chat session for interior design conversations"""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)

    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, messages={self.message_count})>"


class ChatMessage(Base):
    """Individual chat messages"""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False, index=True)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    image_url = Column(Text, nullable=True)  # For user uploads or AI-generated images
    analysis_data = Column(JSON, nullable=True)  # Store design analysis results

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, type={self.type}, session_id={self.session_id})>"


class FurniturePosition(Base):
    """Stores custom furniture positions in visualizations"""

    __tablename__ = "furniture_positions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    # Position coordinates (0-1 range, representing percentage of canvas)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)

    # Optional dimensions (0-1 range)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)

    # Metadata
    label = Column(String(200), nullable=True)  # Product display name
    is_ai_placed = Column(Boolean, default=True)  # True if AI placed, False if user adjusted

    # Layer data for drag-and-drop editing
    layer_image_url = Column(Text, nullable=True)  # Base64 image data of isolated furniture layer
    z_index = Column(Integer, default=1, nullable=False)  # Layer stacking order (higher = on top)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("ChatSession", backref="furniture_positions")
    product = relationship("Product")

    # Indexes
    __table_args__ = (
        Index("idx_furniture_position_session", "session_id"),
        Index("idx_furniture_position_product", "product_id"),
    )

    def __repr__(self):
        return f"<FurniturePosition(id={self.id}, session_id={self.session_id}, product_id={self.product_id}, x={self.x}, y={self.y})>"
