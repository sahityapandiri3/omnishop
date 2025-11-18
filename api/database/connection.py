"""
Database connection and session management
"""
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging

from core.config import settings
from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection and session management"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or settings.database_url
        self.engine = None
        self.SessionLocal = None
        self._initialize()

    def _initialize(self):
        """Initialize database engine and session factory"""
        try:
            # Create engine with connection pooling
            self.engine = create_engine(
                self.database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=settings.environment == "development"
            )

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            logger.info(f"Database connection initialized: {self.database_url}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def create_tables(self):
        """Create all database tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def drop_tables(self):
        """Drop all database tables"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with automatic cleanup"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def get_session_factory(self):
        """Get the session factory for use in other modules"""
        return self.SessionLocal

    def close(self):
        """Close database connections"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Convenience function to get database session"""
    with db_manager.get_session() as session:
        yield session


# Session factory for dependency injection
def get_session_dependency():
    """FastAPI dependency for database sessions"""
    session = db_manager.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_database():
    """Initialize database tables and indexes"""
    try:
        db_manager.create_tables()
        _create_indexes()
        _create_views()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def _create_indexes():
    """Create additional database indexes for performance"""
    with get_db_session() as session:
        # Full-text search index for products
        session.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_name_gin
            ON products USING gin(to_tsvector('english', name))
        """)

        # Full-text search index for descriptions
        session.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_description_gin
            ON products USING gin(to_tsvector('english', description))
        """)

        # Composite index for price range queries
        session.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_price_available
            ON products (price, is_available, category_id)
        """)

        session.commit()
        logger.info("Additional database indexes created")


def _create_views():
    """Create database views for optimized queries"""
    with get_db_session() as session:
        # Product search view with category hierarchy
        session.execute("""
            CREATE OR REPLACE VIEW product_search_view AS
            SELECT
                p.id,
                p.id as product_id,
                p.name,
                p.description as description_text,
                p.price,
                p.brand,
                c.name as category_name,
                COALESCE(
                    parent_c.name || ' > ' || c.name,
                    c.name
                ) as category_path,
                p.source_website,
                p.is_available,
                (
                    SELECT pi.large_url
                    FROM product_images pi
                    WHERE pi.product_id = p.id AND pi.is_primary = true
                    LIMIT 1
                ) as primary_image_url,
                to_tsvector('english', p.name || ' ' || COALESCE(p.description, '') || ' ' || COALESCE(p.brand, '')) as search_vector,
                p.last_updated
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN categories parent_c ON c.parent_id = parent_c.id
            WHERE p.is_available = true
        """)

        session.commit()
        logger.info("Database views created")