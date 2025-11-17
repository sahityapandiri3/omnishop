# Testing Quick Start Guide

## ✅ Status: Test Framework is Ready!

All test dependencies are installed and pre-commit hooks are active.

---

## 🚀 Running Tests Manually

### Run All Tests
```bash
/Users/sahityapandiri/Library/Python/3.9/bin/pytest
```

### Run by Category
```bash
# Unit tests (fast - run during development)
/Users/sahityapandiri/Library/Python/3.9/bin/pytest tests/unit -v -m unit

# Regression tests (verify no bugs return)
/Users/sahityapandiri/Library/Python/3.9/bin/pytest tests/regression -v -m regression

# Integration tests (full workflows)
/Users/sahityapandiri/Library/Python/3.9/bin/pytest tests/integration -v -m integration
```

### Run with Coverage
```bash
/Users/sahityapandiri/Library/Python/3.9/bin/pytest --cov=api --cov-report=html --cov-report=term-missing
open htmlcov/index.html  # View coverage report
```

### Run Specific Tests
```bash
# Run specific file
/Users/sahityapandiri/Library/Python/3.9/bin/pytest tests/unit/test_nlp_processor.py -v

# Run specific test
/Users/sahityapandiri/Library/Python/3.9/bin/pytest tests/unit/test_nlp_processor.py::TestIntentClassification::test_browse_products_intent -v
```

---

## 🔄 Automatic Test Execution

### ✅ ACTIVE: Pre-commit Hooks

**Status**: Installed and active!

**What happens**: Every time you run `git commit`, these checks run automatically:
1. ✓ Format code with Black
2. ✓ Sort imports with isort
3. ✓ Check code with flake8
4. ✓ Run type checking with mypy
5. ✓ Security scan with bandit
6. ✓ Run unit tests

**How to bypass** (not recommended):
```bash
git commit --no-verify
```

**Test hooks manually**:
```bash
/Users/sahityapandiri/Library/Python/3.9/bin/pre-commit run --all-files
```

### ⚠️ NOT YET ACTIVE: GitHub Actions CI/CD

**Status**: Configuration created but not pushed to GitHub yet.

**To activate**:
```bash
git add .github/workflows/tests.yml
git commit -m "Add CI/CD test pipeline"
git push
```

**What will happen after activation**:
- Every push to `main` or `develop` branches → runs all tests
- Every pull request → runs all tests + coverage report
- Test results shown in GitHub UI
- Blocks merging if tests fail

---

## 📊 Test Coverage

### Current Test Suite

- **Total Tests**: 100+ tests
- **Unit Tests**: 80+ tests (NLP, recommendations, Google AI)
- **Integration Tests**: 15+ tests (complete workflows)
- **Regression Tests**: 15+ tests (all 22 documented issues)
- **Coverage Requirement**: ≥70%

### Test Organization

```
tests/
├── unit/                       # Fast tests for individual functions
│   ├── test_nlp_processor.py
│   ├── test_recommendation_engine.py
│   └── test_google_ai_service.py
├── integration/                # Slower tests for complete workflows
│   └── test_chat_flow.py
└── regression/                 # Tests to prevent bug regressions
    └── test_fixed_issues.py
```

---

## 💡 Workflow Recommendations

### During Development

```bash
# 1. Make your code changes
vim api/services/nlp_processor.py

# 2. Run fast unit tests
/Users/sahityapandiri/Library/Python/3.9/bin/pytest tests/unit -v -m unit

# 3. If unit tests pass, run all tests
/Users/sahityapandiri/Library/Python/3.9/bin/pytest

# 4. Commit (pre-commit hooks will run automatically)
git add .
git commit -m "Your commit message"
```

### Before Pushing to GitHub

```bash
# Run full test suite with coverage
/Users/sahityapandiri/Library/Python/3.9/bin/pytest --cov=api --cov-report=term-missing

# Ensure coverage is ≥70%
# Then push
git push
```

### After Fixing a Bug

1. Add regression test in `tests/regression/test_fixed_issues.py`
2. Document issue in `test_issues.md`
3. Verify test fails before fix
4. Apply fix
5. Verify test passes after fix
6. Run all tests: `/Users/sahityapandiri/Library/Python/3.9/bin/pytest`

---

## 🔧 Troubleshooting

### Tests Fail with Import Errors

```bash
# Reinstall dependencies
python3 -m pip install -r requirements.txt
python3 -m pip install -r tests/requirements-test.txt
```

### Tests Are Too Slow

```bash
# Run only fast tests (skip slow tests)
/Users/sahityapandiri/Library/Python/3.9/bin/pytest -m "not slow"

# Or run tests in parallel
python3 -m pip install pytest-xdist
/Users/sahityapandiri/Library/Python/3.9/bin/pytest -n auto
```

### Pre-commit Hooks Are Blocking Commits

```bash
# See what failed
/Users/sahityapandiri/Library/Python/3.9/bin/pre-commit run --all-files

# Fix the issues shown, then commit again
# Or bypass (not recommended)
git commit --no-verify
```

### Coverage Is Below 70%

```bash
# See detailed coverage report
/Users/sahityapandiri/Library/Python/3.9/bin/pytest --cov=api --cov-report=html
open htmlcov/index.html

# Add tests for uncovered code
```

---

## 📚 Full Documentation

- **Comprehensive Guide**: `tests/README.md`
- **Implementation Details**: `TEST_FRAMEWORK_SUMMARY.md`
- **Issue Tracking**: `test_issues.md`

---

## 🎯 Quick Commands Cheat Sheet

```bash
# Run all tests
/Users/sahityapandiri/Library/Python/3.9/bin/pytest

# Run unit tests only
/Users/sahityapandiri/Library/Python/3.9/bin/pytest tests/unit -v -m unit

# Run with coverage
/Users/sahityapandiri/Library/Python/3.9/bin/pytest --cov=api --cov-report=html

# Test pre-commit hooks
/Users/sahityapandiri/Library/Python/3.9/bin/pre-commit run --all-files

# View coverage report
open htmlcov/index.html
```

---

## ✨ Summary

**Current Status**:
- ✅ Test framework created (100+ tests)
- ✅ Dependencies installed
- ✅ Pre-commit hooks active
- ⚠️ GitHub Actions CI/CD ready (needs push to activate)

**Next Steps**:
1. Run tests manually to verify: `/Users/sahityapandiri/Library/Python/3.9/bin/pytest`
2. Try making a commit to see pre-commit hooks in action
3. Push `.github/workflows/tests.yml` to activate CI/CD

**Support**: See `tests/README.md` for complete documentation.
