"""
Pytest configuration and fixtures for Omnishop API tests.
"""
import pytest
import asyncio
from typing import Generator
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_product():
    """Create a mock product for testing."""
    product = MagicMock()
    product.id = 1
    product.name = "Test Modern Sofa"
    product.description = "A comfortable modern sofa with clean lines"
    product.brand = "TestBrand"
    product.price = 50000.0
    product.currency = "INR"
    product.category_id = 1
    product.source_website = "teststore"
    product.is_available = True
    product.primary_style = "modern"
    product.secondary_style = "minimalist"
    product.embedding = None
    product.embedding_text = None
    product.attributes = []
    product.images = []
    return product


@pytest.fixture
def mock_product_with_embedding(mock_product):
    """Create a mock product with embedding."""
    import json
    mock_product.embedding = json.dumps([0.1] * 768)
    mock_product.embedding_text = "Test Modern Sofa\nA comfortable modern sofa"
    return mock_product


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_embedding():
    """Create a sample 768-dimension embedding."""
    import random
    random.seed(42)
    return [random.uniform(-1, 1) for _ in range(768)]


@pytest.fixture
def sample_style_result():
    """Create a sample style classification result."""
    return {
        "primary_style": "modern",
        "secondary_style": "minimalist",
        "confidence": 0.85,
        "reasoning": "Clean lines and neutral colors indicate modern style"
    }


# Test data fixtures

SAMPLE_PRODUCTS = [
    {
        "id": 1,
        "name": "Modern Gray Sofa",
        "description": "A sleek modern sofa in gray fabric with clean lines",
        "primary_style": "modern",
        "category": "sofas",
        "price": 45000
    },
    {
        "id": 2,
        "name": "Scandinavian Oak Chair",
        "description": "Light oak dining chair with Nordic design, hygge inspired",
        "primary_style": "scandinavian",
        "category": "chairs",
        "price": 12000
    },
    {
        "id": 3,
        "name": "Bohemian Rattan Armchair",
        "description": "Boho style armchair with woven rattan and macrame details",
        "primary_style": "boho",
        "category": "chairs",
        "price": 18000
    },
    {
        "id": 4,
        "name": "Industrial Metal Coffee Table",
        "description": "Iron pipe frame coffee table with reclaimed wood top",
        "primary_style": "industrial",
        "category": "tables",
        "price": 22000
    },
    {
        "id": 5,
        "name": "Minimalist White Bookshelf",
        "description": "Ultra clean bookshelf with simple geometric lines",
        "primary_style": "minimalist",
        "category": "storage",
        "price": 15000
    }
]


@pytest.fixture
def sample_products():
    """Return sample product data for testing."""
    return SAMPLE_PRODUCTS


# Search test cases

SEARCH_TEST_CASES = [
    {
        "query": "cozy sofa",
        "expected_match_ids": [1],  # Modern Gray Sofa (semantically similar to comfortable)
        "expected_styles": ["modern", "scandinavian"]
    },
    {
        "query": "wooden nordic furniture",
        "expected_match_ids": [2],  # Scandinavian Oak Chair
        "expected_styles": ["scandinavian", "japandi"]
    },
    {
        "query": "natural textured decor",
        "expected_match_ids": [3],  # Bohemian Rattan Armchair
        "expected_styles": ["boho", "eclectic"]
    }
]


@pytest.fixture
def search_test_cases():
    """Return search test cases for quality evaluation."""
    return SEARCH_TEST_CASES
