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


class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class BudgetTier(enum.Enum):
    """Budget tiers for curated looks and stores"""

    POCKET_FRIENDLY = "pocket_friendly"  # Under ₹2L
    MID_TIER = "mid_tier"  # ₹2L – ₹8L
    PREMIUM = "premium"  # ₹8L – ₹15L
    LUXURY = "luxury"  # ₹15L+


class ApiProvider(enum.Enum):
    """API providers for usage tracking"""

    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ApiUsage(Base):
    """Track API usage and token consumption"""

    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(36), nullable=True, index=True)

    # API details
    provider = Column(String(20), nullable=False, index=True)  # gemini, openai, etc.
    model = Column(String(50), nullable=False, index=True)  # gemini-2.0-flash-exp, gpt-4, etc.
    operation = Column(String(50), nullable=False, index=True)  # visualize, analyze_room, chat, etc.

    # Token counts
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Cost tracking (in USD)
    estimated_cost = Column(Float, nullable=True)

    # Additional metadata (request details, error info, etc.)
    request_metadata = Column(JSON, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_api_usage_timestamp_provider", "timestamp", "provider"),
        Index("idx_api_usage_user_operation", "user_id", "operation"),
    )


class Store(Base):
    """Store information with budget tier classification"""

    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "modernquests", "josmo"
    display_name = Column(String(100), nullable=True)  # e.g., "Modern Quests", "Josmo"
    budget_tier = Column(
        String(20),  # Use String to avoid asyncpg enum issues - database has native enum
        nullable=True,
        index=True,
    )
    website_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Store(id={self.id}, name='{self.name}', tier='{self.budget_tier}')>"


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
    source_website = Column(String(50), nullable=False, index=True)  # References stores.name
    source_url = Column(Text, nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Product status
    is_available = Column(Boolean, default=True, index=True)
    is_on_sale = Column(Boolean, default=False, index=True)
    stock_status = Column(String(20), default="in_stock")

    # Vector embedding for semantic search (768 dimensions for Google text-embedding-004)
    # Stored as JSON array of floats, converted to pgvector for similarity search
    embedding = Column(Text, nullable=True)  # JSON array of 768 floats
    embedding_text = Column(Text, nullable=True)  # Text that was embedded
    embedding_updated_at = Column(DateTime, nullable=True)

    # Style classification (from Gemini Vision or NLP)
    primary_style = Column(String(50), nullable=True, index=True)  # e.g., "modern", "minimalist"
    secondary_style = Column(String(50), nullable=True)  # Optional secondary style
    style_confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    style_extraction_method = Column(String(50), nullable=True)  # "gemini_vision", "text_nlp", "manual"

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
        Index("idx_product_styles", "primary_style", "secondary_style"),
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


class User(Base):
    """User accounts for authentication and project management"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # Null for OAuth users
    auth_provider = Column(String(50), default="email")  # "email" or "google"
    google_id = Column(String(255), unique=True, nullable=True)
    name = Column(String(200), nullable=True)
    profile_image_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    role = Column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x], name="userrole"),
        default=UserRole.USER,
        nullable=False,
        index=True,
    )
    last_login = Column(DateTime, nullable=True, index=True)  # Track last login timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', auth_provider='{self.auth_provider}')>"


class UserPreferences(Base):
    """Persistent user preferences for AI stylist conversations"""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True)

    # Session context
    scope = Column(String(50), nullable=True)  # "full_room" | "specific_category"
    preference_mode = Column(String(50), nullable=True)  # "omni_decides" | "user_provides"
    target_category = Column(String(100), nullable=True)  # If scope = specific_category

    # Room-level preferences
    room_type = Column(String(100), nullable=True)  # "living room", "bedroom", etc.
    usage = Column(JSON, default=list)  # Array of usage types
    overall_style = Column(String(100), nullable=True)  # "minimalist", "modern", etc.
    budget_total = Column(Float, nullable=True)

    # Room analysis suggestions (populated from image analysis)
    room_analysis_suggestions = Column(
        JSON, default=dict
    )  # {detected_style, color_palette, detected_materials, suggested_categories}

    # Category-specific preferences
    category_preferences = Column(
        JSON, default=dict
    )  # {category: {colors, materials, textures, style_override, budget_allocation, source}}

    # Metadata
    preferences_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="preferences")

    def __repr__(self):
        return f"<UserPreferences(id={self.id}, user_id={self.user_id}, style='{self.overall_style}')>"


class ProjectStatus(enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Project(Base):
    """User design projects for saving and resuming work"""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)

    # Project status - draft or published
    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False, index=True)

    # Room data
    room_image = Column(Text, nullable=True)  # Base64 of original room
    clean_room_image = Column(Text, nullable=True)  # Base64 of furniture-removed room
    visualization_image = Column(Text, nullable=True)  # Base64 of last rendered visualization

    # Cached room analysis from upload (JSONB) - avoids redundant Gemini calls during visualization
    room_analysis = Column(JSON, nullable=True)

    # Canvas state
    canvas_products = Column(Text, nullable=True)  # JSON array of products on canvas
    visualization_history = Column(Text, nullable=True)  # JSON array of visualization history for undo/redo

    # Chat session link - for restoring chat history when project is reloaded
    chat_session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="projects")

    # Indexes
    __table_args__ = (Index("idx_project_user_updated", "user_id", "updated_at"),)

    def __repr__(self):
        return f"<Project(id={self.id}, user_id={self.user_id}, name='{self.name}')>"


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


class CuratedLook(Base):
    """Pre-curated room looks created by admin"""

    __tablename__ = "curated_looks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    style_theme = Column(String(100), nullable=False)  # "Modern", "Traditional", "Bohemian", etc.
    style_description = Column(Text, nullable=True)
    style_labels = Column(JSON, default=list)  # ["modern", "modern_luxury", "indian_contemporary"] for filtering
    room_type = Column(String(50), nullable=False, index=True)  # "living_room", "bedroom"

    # Images
    room_image = Column(Text, nullable=True)  # Base64 of original room (optional)
    visualization_image = Column(Text, nullable=True)  # Base64 of AI visualization

    # Cached room analysis from upload (JSONB) - avoids redundant Gemini calls during visualization
    room_analysis = Column(JSON, nullable=True)

    # Metadata
    total_price = Column(Float, default=0)
    budget_tier = Column(
        String(20),  # Use String to avoid asyncpg enum issues - database has native enum
        nullable=True,
        index=True,
    )
    is_published = Column(Boolean, default=False, index=True)
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    products = relationship("CuratedLookProduct", back_populates="look", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CuratedLook(id={self.id}, title='{self.title}', room_type='{self.room_type}', is_published={self.is_published})>"


class CuratedLookProduct(Base):
    """Products included in a curated look"""

    __tablename__ = "curated_look_products"

    id = Column(Integer, primary_key=True, index=True)
    curated_look_id = Column(Integer, ForeignKey("curated_looks.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    product_type = Column(String(50), nullable=True)  # "sofa", "coffee_table", "lamp", etc.
    quantity = Column(Integer, default=1, nullable=False)  # Number of this product in the look
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    look = relationship("CuratedLook", back_populates="products")
    product = relationship("Product")

    # Indexes and constraints
    __table_args__ = (Index("idx_curated_look_product", "curated_look_id", "product_id", unique=True),)

    def __repr__(self):
        return f"<CuratedLookProduct(id={self.id}, look_id={self.curated_look_id}, product_id={self.product_id})>"


class ChatLog(Base):
    """Persistent chat conversation logs for analytics and debugging"""

    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    server_type = Column(String(10), nullable=False)  # "local" or "prod"
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_chat_logs_session_created", "session_id", "created_at"),
        Index("idx_chat_logs_user_created", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<ChatLog(id={self.id}, session={self.session_id[:8]}..., user={self.user_id})>"


class HomeStylingSessionStatus(enum.Enum):
    """Status for home styling sessions"""

    PREFERENCES = "preferences"
    UPLOAD = "upload"
    TIER_SELECTION = "tier_selection"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class HomeStylingTier(enum.Enum):
    """Tier options for home styling"""

    FREE = "free"  # 1 view
    BASIC = "basic"  # 3 views
    PREMIUM = "premium"  # 6 views (coming soon)


class HomeStylingSession(Base):
    """User sessions for home styling flow"""

    __tablename__ = "homestyling_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    # Preferences
    room_type = Column(String(50), nullable=True)  # "living_room", "bedroom"
    style = Column(String(50), nullable=True)  # "modern", "modern_luxury", "indian_contemporary"
    color_palette = Column(JSON, default=list)  # ["warm", "neutral", "cool", "bold"]
    budget_tier = Column(
        String(20),  # Use String to avoid asyncpg enum issues - database has native enum
        nullable=True,
        index=True,
    )  # User's budget preference for curated looks

    # Images
    original_room_image = Column(Text, nullable=True)  # Base64 encoded
    clean_room_image = Column(Text, nullable=True)  # Furniture removed

    # Tier selection (no payment in Phase 1)
    selected_tier = Column(
        Enum(HomeStylingTier, values_callable=lambda x: [e.value for e in x], name="homestylingtier"), nullable=True
    )
    views_count = Column(Integer, default=1)  # 1, 3, or 6

    # Session status
    status = Column(
        Enum(HomeStylingSessionStatus, values_callable=lambda x: [e.value for e in x], name="homestylingsessionstatus"),
        default=HomeStylingSessionStatus.PREFERENCES,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="homestyling_sessions")
    views = relationship("HomeStylingView", back_populates="session", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_homestyling_session_user", "user_id", "created_at"),
        Index("idx_homestyling_session_status", "status", "created_at"),
    )

    def __repr__(self):
        return f"<HomeStylingSession(id={self.id[:8]}..., style='{self.style}', status='{self.status}')>"


class HomeStylingView(Base):
    """Generated visualizations for home styling sessions"""

    __tablename__ = "homestyling_views"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("homestyling_sessions.id"), nullable=False, index=True)
    curated_look_id = Column(Integer, ForeignKey("curated_looks.id"), nullable=True, index=True)

    # Generated visualization
    visualization_image = Column(Text, nullable=True)  # Base64 encoded
    view_number = Column(Integer, nullable=False)  # 1, 2, 3, etc.

    # Status
    generation_status = Column(String(20), default="pending")  # "pending", "generating", "completed", "failed"
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("HomeStylingSession", back_populates="views")
    curated_look = relationship("CuratedLook")

    # Indexes
    __table_args__ = (Index("idx_homestyling_view_session", "session_id", "view_number"),)

    def __repr__(self):
        return f"<HomeStylingView(id={self.id}, session_id={self.session_id[:8]}..., view_number={self.view_number})>"


class AnalyticsEvent(Base):
    """Analytics events for tracking user behavior"""

    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # "page_view", "preferences_selected", etc.
    session_id = Column(String(36), nullable=True, index=True)  # HomeStylingSession ID
    user_id = Column(String(36), nullable=True, index=True)
    step_name = Column(String(50), nullable=True)  # "preferences", "upload", "tier", "results"
    event_data = Column(JSON, default=dict)  # Additional event data (renamed from 'metadata' which is reserved)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index("idx_analytics_event_type_created", "event_type", "created_at"),
        Index("idx_analytics_session_created", "session_id", "created_at"),
        Index("idx_analytics_user_created", "user_id", "created_at"),
    )

    def __repr__(self):
        return f"<AnalyticsEvent(id={self.id}, event_type='{self.event_type}', session_id={self.session_id})>"


class PrecomputedMaskStatus(enum.Enum):
    """Status for background mask pre-computation jobs"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PrecomputedMask(Base):
    """
    Pre-computed segmentation masks for Edit Position feature optimization.

    These masks are generated in the background after each visualization completes,
    so when users click "Edit Position", the masks are already available for instant retrieval.

    Supports both:
    - Design studio visualizations (linked via session_id)
    - Admin curated looks (linked via curated_look_id)
    """

    __tablename__ = "precomputed_masks"

    id = Column(Integer, primary_key=True, index=True)

    # Either session_id OR curated_look_id should be set (not both)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=True, index=True)
    curated_look_id = Column(Integer, ForeignKey("curated_looks.id"), nullable=True, index=True)

    # Cache key components - used to match requests to cached data
    visualization_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of image (first 1000 chars + length)
    product_hash = Column(String(64), nullable=False, index=True)  # Hash of product IDs

    # Status tracking
    status = Column(
        Enum(PrecomputedMaskStatus, values_callable=lambda x: [e.value for e in x], name="precomputedmaskstatus"),
        default=PrecomputedMaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message = Column(Text, nullable=True)

    # Pre-computed data
    clean_background = Column(Text, nullable=True)  # Base64 clean room image (furniture removed)
    layers_data = Column(JSON, nullable=True)  # Array of layer objects with cutouts, masks, positions
    extraction_method = Column(String(50), nullable=True)  # "hybrid_gemini_sam" or "sam_direct"

    # Metadata
    image_dimensions = Column(JSON, nullable=True)  # {"width": int, "height": int}
    processing_time = Column(Float, nullable=True)  # Time taken to generate masks in seconds

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("ChatSession", backref="precomputed_masks")
    curated_look = relationship("CuratedLook", backref="precomputed_masks")

    # Indexes for efficient lookup
    __table_args__ = (
        Index("idx_precomputed_mask_session_viz", "session_id", "visualization_hash"),
        Index("idx_precomputed_mask_curated_viz", "curated_look_id", "visualization_hash"),
        Index("idx_precomputed_mask_lookup", "session_id", "visualization_hash", "product_hash"),
        Index("idx_precomputed_mask_status", "status", "created_at"),
    )

    def __repr__(self):
        if self.session_id:
            return f"<PrecomputedMask(id={self.id}, session_id={self.session_id[:8]}..., status='{self.status.value}')>"
        return f"<PrecomputedMask(id={self.id}, curated_look_id={self.curated_look_id}, status='{self.status.value}')>"
