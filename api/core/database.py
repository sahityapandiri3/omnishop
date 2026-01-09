"""
Database configuration and connection management
"""
from contextlib import asynccontextmanager, contextmanager

import databases
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from database.models import Base

# Convert postgresql:// to postgresql+asyncpg:// for async support
DATABASE_URL = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

# Sync URL for background logging (uses psycopg2)
SYNC_DATABASE_URL = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Create databases instance for FastAPI
database = databases.Database(DATABASE_URL)


async def create_tables():
    """Create all database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db_session():
    """Get async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db():
    """FastAPI dependency for database sessions"""
    async with get_db_session() as session:
        yield session


# Sync engine for background tasks (API usage logging)
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_size=2,
    max_overflow=3,
)

SyncSessionLocal = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


@contextmanager
def get_sync_db_session():
    """Get synchronous database session for background tasks"""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
