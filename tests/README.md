# Omnishop Test Suite

Comprehensive test suite for the Omnishop interior design AI application.

## Overview

This test suite includes:
- **Unit Tests**: Tests for individual functions and classes
- **Integration Tests**: Tests for module interactions and complete workflows
- **Regression Tests**: Tests to ensure fixed bugs don't reappear

## Test Structure

```
tests/
├── unit/                       # Unit tests for individual modules
│   ├── test_nlp_processor.py  # NLP processor tests
│   ├── test_recommendation_engine.py  # Recommendation engine tests
│   └── test_google_ai_service.py      # Google AI service tests
├── integration/                # Integration tests
│   └── test_chat_flow.py      # Complete conversation flow tests
├── regression/                 # Regression tests
│   └── test_fixed_issues.py   # Tests for Issues 1-22
├── conftest.py                 # Shared fixtures and configuration
└── requirements-test.txt       # Testing dependencies
```

## Installation

Install testing dependencies:

```bash
pip install -r tests/requirements-test.txt
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test categories

**Unit tests only:**
```bash
pytest tests/unit -v -m unit
```

**Integration tests only:**
```bash
pytest tests/integration -v -m integration
```

**Regression tests only:**
```bash
pytest tests/regression -v -m regression
```

**Specific test file:**
```bash
pytest tests/unit/test_nlp_processor.py -v
```

**Specific test function:**
```bash
pytest tests/unit/test_nlp_processor.py::TestIntentClassification::test_browse_products_intent -v
```

### Run with coverage

```bash
pytest --cov=api --cov-report=html --cov-report=term-missing
```

View HTML coverage report:
```bash
open htmlcov/index.html
```

## Test Markers

Tests are organized with pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.regression` - Regression tests
- `@pytest.mark.slow` - Tests that take a long time
- `@pytest.mark.asyncio` - Async tests
- `@pytest.mark.database` - Tests requiring database
- `@pytest.mark.api` - Tests requiring API access

### Run specific markers

```bash
# Run only fast unit tests
pytest -m "unit and not slow"

# Run all regression tests
pytest -m regression

# Run integration tests excluding slow ones
pytest -m "integration and not slow"
```

## Fixtures

Shared test fixtures are defined in `conftest.py`:

- `db_session` - Async database session for testing
- `mock_openai_client` - Mocked OpenAI client
- `mock_google_ai_client` - Mocked Google AI client
- `sample_product_data` - Sample product data
- `sample_base64_image` - Sample base64 encoded image
- `sample_visualization_request` - Sample visualization request

## Writing Tests

### Unit Test Example

```python
import pytest
from api.services.nlp_processor import design_nlp_processor

class TestIntentClassification:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_browse_products_intent(self):
        """Test detection of product browsing intent"""
        text = "Show me some sofas"
        result = await design_nlp_processor.classify_intent(text)

        assert result.primary_intent == "browse_products"
        assert result.confidence_score > 0.5
```

### Integration Test Example

```python
import pytest
from api.services.nlp_processor import design_nlp_processor
from api.services.recommendation_engine import recommendation_engine

class TestProductBrowsingFlow:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_flow(self, db_session):
        """Test complete product browsing flow"""
        # Step 1: Classify intent
        intent = await design_nlp_processor.classify_intent("Show me sofas")
        assert intent.primary_intent == "browse_products"

        # Step 2: Get recommendations
        # ... test continues
```

### Regression Test Example

```python
import pytest
from api.services.nlp_processor import design_nlp_processor

class TestIssue21_RemoveAllFurnitureCommand:
    """Issue 21: 'Remove all furniture' returns product list"""

    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_remove_all_commands(self):
        """Test that removal commands trigger modification intent"""
        text = "remove all furniture from the latest image"
        result = await design_nlp_processor.classify_intent(text)

        assert result.primary_intent == "image_modification"
```

## Coverage Requirements

The test suite enforces a minimum of **70% code coverage** for the `api/` directory.

Current coverage status is displayed at the end of each test run.

## Continuous Integration

Tests are automatically run via GitHub Actions on:
- Every push to `main` or `develop` branches
- Every pull request to `main` or `develop` branches

See `.github/workflows/tests.yml` for CI configuration.

## Pre-commit Hooks

Install pre-commit hooks to run tests before committing:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

Pre-commit hooks will:
1. Format code with Black
2. Sort imports with isort
3. Lint code with flake8
4. Run type checking with mypy
5. Run unit tests
6. Check for security issues with bandit

## Regression Test Coverage

The test suite includes regression tests for all 22 documented issues:

- ✅ Issue 1: Incorrect product recommendations for flower vases
- ✅ Issue 9: Compound keyword detection (floor lamp vs table lamp)
- ✅ Issue 10: Text-based visualization edits trigger product recommendations
- ✅ Issue 15: Spatial instructions not honored (ottoman placement)
- ✅ Issue 16: Clarification option 'b' incorrectly replaces furniture
- ✅ Issue 17: Only 1 ottoman shown when database has 10
- ✅ Issue 18: No product suggestions for planters
- ✅ Issue 21: "Remove all furniture" returns product list
- ✅ Issue 22: Furniture replacement logic regression

See `tests/regression/test_fixed_issues.py` for details.

## Troubleshooting

### Tests fail with database errors

Make sure you have PostgreSQL running or the tests will use an in-memory SQLite database by default.

### Tests fail with import errors

Make sure you've installed all dependencies:
```bash
pip install -r requirements.txt
pip install -r tests/requirements-test.txt
```

### Tests fail with API errors

Mock API calls are used in tests, so you shouldn't need actual API keys. If tests fail with API errors, check that mocks are properly configured.

### Slow test execution

Run only fast tests:
```bash
pytest -m "not slow"
```

Or run tests in parallel:
```bash
pip install pytest-xdist
pytest -n auto
```

## Contributing

When adding new features:

1. Write unit tests for new functions/classes
2. Write integration tests for new workflows
3. Ensure all tests pass: `pytest`
4. Ensure coverage remains above 70%: `pytest --cov=api`
5. Run pre-commit hooks: `pre-commit run --all-files`

When fixing bugs:

1. Add a regression test in `tests/regression/test_fixed_issues.py`
2. Document the issue in `test_issues.md`
3. Ensure the regression test fails before the fix
4. Ensure the regression test passes after the fix

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Pre-commit Documentation](https://pre-commit.com/)
