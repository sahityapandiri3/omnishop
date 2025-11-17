"""
Shared pytest fixtures and configuration for all tests
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from typing import Generator, AsyncGenerator

# Add the parent directory to the path so we can import from api
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path is set
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def test_db_url():
    """Database URL for testing"""
    return "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
async def test_engine(test_db_url):
    """Create async engine for tests"""
    engine = create_async_engine(
        test_db_url,
        poolclass=NullPool,
        echo=False
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing without API calls"""
    mock = Mock()
    mock.chat = Mock()
    mock.chat.completions = Mock()
    mock.chat.completions.create = AsyncMock()
    return mock


@pytest.fixture
def mock_google_ai_client():
    """Mock Google AI client for testing without API calls"""
    mock = Mock()
    mock.models = Mock()
    mock.models.generate_content_stream = Mock(return_value=[])
    return mock


@pytest.fixture
def sample_product_data():
    """Sample product data for testing"""
    return {
        "id": 1,
        "name": "Modern Coffee Table",
        "description": "A sleek modern coffee table with glass top",
        "price": 15000,
        "currency": "INR",
        "brand": "Test Brand",
        "source_website": "test.com",
        "source_url": "https://test.com/product/1",
        "is_available": True,
        "is_on_sale": False
    }


@pytest.fixture
def sample_chat_message():
    """Sample chat message for testing"""
    return {
        "message": "I need center tables for my living room",
        "image": None
    }


@pytest.fixture
def sample_design_analysis():
    """Sample design analysis result for testing"""
    return {
        "design_analysis": {
            "style_preferences": {
                "primary_style": "modern",
                "secondary_styles": ["contemporary"],
                "style_keywords": ["minimalist", "sleek"]
            },
            "color_scheme": {
                "preferred_colors": ["white", "gray"],
                "accent_colors": ["black"]
            }
        },
        "product_matching_criteria": {
            "product_types": ["table"],
            "categories": ["coffee_table", "center_table"],
            "search_terms": ["center table", "coffee table"]
        }
    }


@pytest.fixture
def sample_base64_image():
    """Sample base64 encoded image for testing"""
    # 1x1 transparent PNG
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@pytest.fixture
def sample_visualization_request():
    """Sample visualization request for testing"""
    return {
        "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "products": [
            {
                "id": 1,
                "name": "Modern Coffee Table",
                "price": 15000,
                "image_url": "https://example.com/table.jpg"
            }
        ],
        "analysis": {
            "design_analysis": {
                "style_preferences": {"primary_style": "modern"}
            }
        }
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests"""
    # This prevents state leakage between tests
    yield
    # Add cleanup code here if needed


@pytest.fixture
def mock_conversation_context():
    """Mock conversation context manager"""
    mock = Mock()
    mock.get_conversation_context = Mock(return_value=[])
    mock.store_conversation_context = Mock()
    mock.get_last_visualization = Mock(return_value=None)
    mock.get_placed_products = Mock(return_value=[])
    mock.store_visualization = Mock()
    mock.store_image = Mock()
    return mock
