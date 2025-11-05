# Search & Recommendation Engine Improvements

## Executive Summary
Complete overhaul of the recommendation engine to eliminate false positives and implement accurate attribute-based product filtering using Gemini AI for attribute extraction.

## Current Issues Identified

### Critical Problems:
1. **No Attribute Extraction**: Color/material matching returns hardcoded values (0.7 and 0.6)
2. **False Positives**: Products shown that don't match user query attributes
3. **Placeholder Scoring**: Material and color matching functions are not implemented
4. **Missing Data**: ProductAttribute table exists but is empty
5. **Text-Only Filtering**: No structured attribute data, relies on name/description search

### Impact:
- User searches "red leather sofa" → Shows all sofas (blue, fabric, etc.)
- User searches "modern glass table" → Shows traditional wood tables
- Recommendation quality is poor
- User trust and conversion rates suffer

## Solution Architecture

### Technology Choices:
- **Primary Engine**: Gemini 2.0 Flash (vision + text)
- **Cost**: Free tier 1,500/day, then ~$1.50 per 1,000 products (vs $20-30 for ChatGPT Vision)
- **Accuracy**: 85-95% for furniture attributes
- **Speed**: 2-5 seconds per product

### Architecture Components:
```
┌─────────────────────────────────────────────────────────────┐
│                    User Query                                │
│              "red leather sofa"                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         NLP Processor (Existing)                             │
│  Extracts: colors=[red], materials=[leather],                │
│            furniture_types=[sofa]                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         Recommendation Engine (Enhanced)                     │
│                                                              │
│  1. Strict Attribute Filter (NEW)                           │
│     ├─ JOIN ProductAttribute WHERE color='red'              │
│     ├─ JOIN ProductAttribute WHERE material='leather'       │
│     └─ Only products with BOTH attributes pass              │
│                                                              │
│  2. Keyword Matching (Existing)                             │
│     └─ Product name contains 'sofa'                         │
│                                                              │
│  3. Multi-Algorithm Scoring (Enhanced)                      │
│     ├─ Keyword relevance: 30% (was 40%)                     │
│     ├─ Color match: 15% (was placeholder 70%)               │
│     ├─ Material match: 15% (was placeholder 60%)            │
│     ├─ Style match: 15% (was 20%)                           │
│     ├─ Size match: 10% (NEW)                                │
│     ├─ Texture match: 5% (NEW)                              │
│     ├─ Pattern match: 5% (NEW)                              │
│     └─ Description: 5% (was 20%)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Results: ONLY red leather sofas                 │
│              (Zero false positives)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Attribute Extraction Service

**File**: `api/services/attribute_extraction_service.py` (~450 lines)

### Core Components:

#### 1.1 Image-Based Extraction (Primary)
```python
async def extract_attributes_from_image(image_url: str) -> AttributeExtractionResult:
    """
    Extract product attributes using Gemini 2.0 Flash Vision

    Returns:
    {
        "furniture_type": "sofa",
        "colors": {
            "primary": "red",
            "secondary": "burgundy",
            "accent": null
        },
        "materials": {
            "primary": "leather",
            "secondary": "wood",
            "fabric_type": "genuine leather"
        },
        "style": "modern",
        "dimensions": {
            "width": "84 inches",
            "depth": "36 inches",
            "height": "33 inches"
        },
        "texture": "smooth",
        "pattern": "solid",
        "confidence_scores": {
            "furniture_type": 0.95,
            "colors": 0.88,
            "materials": 0.90,
            "style": 0.82
        }
    }
    """
```

**Implementation Details**:
- Model: `gemini-2.0-flash-exp`
- Response format: `application/json`
- Prompt engineering: Detailed instructions for furniture attribute extraction
- Retry logic: 3 attempts with exponential backoff
- Rate limiting: Respect 30 req/min free tier limit

#### 1.2 Text-Based Extraction (Fallback)
```python
async def extract_attributes_from_text(name: str, description: str) -> AttributeExtractionResult:
    """
    Extract attributes from product name and description using NLP + regex

    Patterns:
    - Color: regex for color words + NLP color detection
    - Material: keyword matching (leather, wood, metal, fabric, etc.)
    - Dimensions: regex for measurements (84" W x 36" D x 33" H)
    - Style: keyword matching (modern, traditional, rustic, etc.)
    """
```

#### 1.3 Attribute Merging
```python
def merge_attributes(image_attrs: dict, text_attrs: dict) -> dict:
    """
    Combine image and text extraction results

    Priority:
    1. Image attributes (higher confidence) preferred
    2. Text attributes fill gaps where image extraction failed
    3. Conflict resolution: Choose higher confidence score
    4. Validation: Ensure consistency (e.g., "leather sofa" not "wood sofa")
    """
```

#### 1.4 Database Storage
```python
async def store_attributes(product_id: int, attributes: dict, db: AsyncSession):
    """
    Save extracted attributes to ProductAttribute table

    Schema:
    - product_id: Foreign key to Product
    - attribute_name: 'color_primary', 'material_primary', 'style', etc.
    - attribute_value: 'red', 'leather', 'modern'
    - attribute_type: 'text', 'number', 'json'
    - confidence_score: 0.0 to 1.0
    - extraction_method: 'gemini_vision', 'text_nlp', 'merged'
    - created_at: timestamp
    """
```

### 1.5 Rate Limiting & Error Handling
- Implement queue system for Gemini API calls
- Handle rate limit errors (429) with exponential backoff
- Log failed extractions for manual review
- Fallback to text extraction if image extraction fails
- Continue processing even if individual products fail

---

## Phase 2: Migration Script

**File**: `scripts/migrate_extract_attributes.py` (~300 lines)

### Features:

#### 2.1 Batch Processing
```python
# Process products in batches of 50
# Rate limit: 30 requests/min (Gemini free tier)
# Estimated time: 10,000 products = ~6-8 hours

async def migrate_products(batch_size: int = 50, resume: bool = False):
    """
    1. Load all products from database
    2. Filter: Only products with images
    3. Filter: Skip products that already have attributes (if resume=True)
    4. Process in batches with rate limiting
    5. Save checkpoint every 100 products
    6. Generate summary report
    """
```

#### 2.2 Progress Tracking
```python
# Save state to migration_state.json:
{
    "last_processed_product_id": 1234,
    "total_processed": 5000,
    "successful": 4750,
    "failed": 250,
    "start_time": "2025-01-15T10:00:00",
    "estimated_completion": "2025-01-15T16:30:00"
}
```

#### 2.3 Error Logging
```python
# Save failed products to migration_errors.csv:
product_id,product_name,error_type,error_message,timestamp
1234,"Modern Sofa",api_error,"Rate limit exceeded",2025-01-15T10:15:00
```

#### 2.4 CLI Interface
```bash
# Dry run (test on 10 products)
python scripts/migrate_extract_attributes.py --dry-run --limit 10

# Resume from last checkpoint
python scripts/migrate_extract_attributes.py --resume

# Full migration
python scripts/migrate_extract_attributes.py --batch-size 50

# Retry failed products
python scripts/migrate_extract_attributes.py --retry-failed
```

#### 2.5 Statistics & Reporting
```python
# Generate migration report:
{
    "total_products": 10000,
    "processed": 10000,
    "successful": 9200,
    "failed": 800,
    "success_rate": "92%",
    "avg_confidence_score": 0.87,
    "avg_extraction_time": "3.2 seconds",
    "attributes_extracted": {
        "furniture_type": 9200,
        "color_primary": 8800,
        "material_primary": 8900,
        "style": 8500,
        "dimensions": 7200
    },
    "cost": "$4.50"
}
```

---

## Phase 3: Scraping Pipeline Integration

**File**: `scrapers/pipelines.py` (add ~120 lines)

### New Pipeline Stage:

```python
class AttributeExtractionPipeline:
    """
    Extract attributes for newly scraped products
    Runs AFTER product is scraped, BEFORE DB save
    """

    async def process_item(self, item, spider):
        """
        1. Get first product image URL
        2. Call attribute_extraction_service.extract_attributes_from_image()
        3. Call attribute_extraction_service.extract_attributes_from_text()
        4. Merge results
        5. Add attributes to item['attributes']
        6. Continue pipeline (don't fail if extraction fails)
        """

        try:
            # Extract from image
            if item.get('images'):
                image_attrs = await extract_attributes_from_image(item['images'][0])

            # Extract from text
            text_attrs = await extract_attributes_from_text(
                item['name'],
                item['description']
            )

            # Merge
            item['attributes'] = merge_attributes(image_attrs, text_attrs)

            logger.info(f"Extracted attributes for {item['name']}")

        except Exception as e:
            logger.error(f"Attribute extraction failed for {item['name']}: {e}")
            item['attributes'] = {}  # Empty attributes, don't fail scraping

        return item
```

### Pipeline Order:
```python
ITEM_PIPELINES = {
    'scrapers.pipelines.DuplicateCheckPipeline': 100,
    'scrapers.pipelines.PriceValidationPipeline': 200,
    'scrapers.pipelines.AttributeExtractionPipeline': 300,  # NEW
    'scrapers.pipelines.DatabaseStoragePipeline': 400,
}
```

---

## Phase 4: Recommendation Engine Overhaul

**File**: `api/services/recommendation_engine.py`

### 4A: Replace Placeholder Functions

#### Current (Line 794-798):
```python
def _calculate_color_match(self, product: Product, preferred_colors: List[str]) -> float:
    # This would analyze product images and descriptions for color
    # For now, return a simulated score
    return 0.7  # placeholder ❌
```

#### New Implementation:
```python
async def _calculate_color_match(
    self,
    product: Product,
    preferred_colors: List[str],
    db: AsyncSession
) -> float:
    """
    Query ProductAttribute for color and calculate match score

    Returns:
    - 1.0: Exact match (primary color matches)
    - 0.8: Secondary match (secondary/accent color matches)
    - 0.5: Color family match (red vs burgundy)
    - 0.0: No match
    """
    if not preferred_colors:
        return 1.0  # No preference = all colors acceptable

    # Query product colors from ProductAttribute
    result = await db.execute(
        select(ProductAttribute)
        .where(
            ProductAttribute.product_id == product.id,
            ProductAttribute.attribute_name.in_(['color_primary', 'color_secondary'])
        )
    )
    product_colors = [attr.attribute_value.lower() for attr in result.scalars().all()]

    if not product_colors:
        return 0.0  # No color data = exclude if user specified color

    # Exact match
    for user_color in preferred_colors:
        if user_color.lower() in product_colors:
            return 1.0

    # Color family match (red, burgundy, crimson, maroon)
    color_families = self._get_color_families()
    for user_color in preferred_colors:
        user_family = color_families.get(user_color.lower(), [])
        for product_color in product_colors:
            if product_color in user_family:
                return 0.5

    return 0.0
```

#### Current (Line 800-804):
```python
def _calculate_material_match(self, product: Product, preferred_materials: List[str]) -> float:
    # This would analyze product descriptions for materials
    # For now, return a simulated score
    return 0.6  # placeholder ❌
```

#### New Implementation:
```python
async def _calculate_material_match(
    self,
    product: Product,
    preferred_materials: List[str],
    db: AsyncSession
) -> float:
    """
    Query ProductAttribute for material and calculate match score

    Returns:
    - 1.0: Exact match (primary material matches)
    - 0.7: Compatible materials (leather + wood for leather sofa with wood legs)
    - 0.0: No match
    """
    if not preferred_materials:
        return 1.0  # No preference = all materials acceptable

    # Query product materials
    result = await db.execute(
        select(ProductAttribute)
        .where(
            ProductAttribute.product_id == product.id,
            ProductAttribute.attribute_name.in_(['material_primary', 'material_secondary'])
        )
    )
    product_materials = [attr.attribute_value.lower() for attr in result.scalars().all()]

    if not product_materials:
        return 0.0  # No material data = exclude

    # Exact match
    for user_material in preferred_materials:
        if user_material.lower() in product_materials:
            return 1.0

    # Compatible materials
    # e.g., user wants "leather", product is "leather + wood" = compatible
    compatible_scores = []
    for user_material in preferred_materials:
        for product_material in product_materials:
            if user_material.lower() in product_material or product_material in user_material.lower():
                compatible_scores.append(0.7)

    return max(compatible_scores) if compatible_scores else 0.0
```

### 4B: New Scoring Functions

#### Size Matching:
```python
async def _calculate_size_match(
    self,
    product: Product,
    room_dimensions: Dict[str, float],
    db: AsyncSession
) -> float:
    """
    Match product dimensions to room size

    Returns:
    - 1.0: Product fits comfortably (uses <30% of room dimension)
    - 0.7: Tight fit (uses 30-50% of room dimension)
    - 0.3: Very tight (uses 50-70%)
    - 0.0: Too large (uses >70%)
    """
    if not room_dimensions:
        return 1.0  # No room size specified

    # Query product dimensions
    result = await db.execute(
        select(ProductAttribute)
        .where(
            ProductAttribute.product_id == product.id,
            ProductAttribute.attribute_name.in_(['width', 'depth', 'height'])
        )
    )

    dimensions = {attr.attribute_name: float(attr.attribute_value)
                  for attr in result.scalars().all()}

    if not dimensions:
        return 0.8  # No dimension data, assume average size

    # Calculate fit score
    # ... implementation details ...
```

#### Texture Matching:
```python
async def _calculate_texture_match(
    self,
    product: Product,
    preferred_textures: List[str],
    db: AsyncSession
) -> float:
    """
    Match texture preferences (smooth, rough, woven, etc.)

    Returns:
    - 1.0: Exact match
    - 0.0: No match
    """
```

#### Pattern Matching:
```python
async def _calculate_pattern_match(
    self,
    product: Product,
    preferred_patterns: List[str],
    db: AsyncSession
) -> float:
    """
    Match pattern preferences (solid, striped, floral, geometric, etc.)

    Returns:
    - 1.0: Exact match
    - 0.0: No match
    """
```

### 4C: Strict Attribute Filtering

**Location**: Before scoring phase (lines 210-330)

```python
async def get_recommendations(
    self,
    request: RecommendationRequest,
    db: AsyncSession
) -> List[Product]:
    """
    Enhanced recommendation with strict attribute filtering
    """

    # Start with base query
    query = select(Product).where(Product.is_available == True)

    # STRICT FILTERING: Only products with matching attributes
    if request.strict_attribute_match:

        # Color filtering
        if request.user_colors:
            # Build subquery for products WITH matching colors
            color_subquery = (
                select(ProductAttribute.product_id)
                .where(
                    ProductAttribute.attribute_name.in_(['color_primary', 'color_secondary']),
                    ProductAttribute.attribute_value.in_(request.user_colors)
                )
            )
            query = query.where(Product.id.in_(color_subquery))

        # Material filtering
        if request.user_materials:
            # Build subquery for products WITH matching materials
            material_subquery = (
                select(ProductAttribute.product_id)
                .where(
                    ProductAttribute.attribute_name.in_(['material_primary', 'material_secondary']),
                    ProductAttribute.attribute_value.in_(request.user_materials)
                )
            )
            query = query.where(Product.id.in_(material_subquery))

        # Style filtering
        if request.user_styles:
            style_subquery = (
                select(ProductAttribute.product_id)
                .where(
                    ProductAttribute.attribute_name == 'style',
                    ProductAttribute.attribute_value.in_(request.user_styles)
                )
            )
            query = query.where(Product.id.in_(style_subquery))

        # Texture filtering
        if request.user_textures:
            texture_subquery = (
                select(ProductAttribute.product_id)
                .where(
                    ProductAttribute.attribute_name == 'texture',
                    ProductAttribute.attribute_value.in_(request.user_textures)
                )
            )
            query = query.where(Product.id.in_(texture_subquery))

    # Execute query to get candidates
    result = await db.execute(query)
    candidates = result.scalars().all()

    logger.info(f"Strict filtering: {len(candidates)} products match attribute criteria")

    # If no products match, return empty list (ZERO false positives)
    if not candidates:
        return []

    # Continue with scoring...
```

### 4D: Fix Category Filtering

**Location**: Line 333-341

```python
# ENABLE room-based category filtering (currently disabled)
if request.room_context and request.room_context.get("room_type"):
    room_type = request.room_context["room_type"]
    room_categories = self._get_room_categories(room_type)

    if room_categories:
        query = query.where(Product.category_id.in_(room_categories))
        logger.info(f"Filtered to {len(room_categories)} categories for {room_type}")
```

**Fix the relationship issue** by ensuring:
1. Category table has proper room_type mappings
2. Products have valid category_id foreign keys
3. Add migration to populate missing category relationships

### 4E: Update Scoring Weights

**Location**: Lines 364-413

```python
async def _content_based_filtering(
    self,
    candidates: List[Product],
    request: RecommendationRequest,
    db: AsyncSession
) -> List[Tuple[Product, float]]:
    """
    Enhanced scoring with real attribute matching
    """
    scored_products = []

    for product in candidates:
        score = 0.0

        # Keyword relevance (30% - reduced from 40%)
        if request.product_keywords:
            keyword_match = self._calculate_keyword_relevance(product, request.product_keywords)
            score += keyword_match * 0.30

        # Color match (15% - was placeholder)
        if request.user_colors:
            color_match = await self._calculate_color_match(product, request.user_colors, db)
            score += color_match * 0.15

        # Material match (15% - was placeholder)
        if request.user_materials:
            material_match = await self._calculate_material_match(product, request.user_materials, db)
            score += material_match * 0.15

        # Style match (15% - reduced from 20%)
        if request.style_preferences:
            style_match = self._calculate_style_similarity(
                request.style_preferences,
                self._extract_product_style(product)
            )
            score += style_match * 0.15

        # Size match (10% - NEW)
        if request.user_dimensions:
            size_match = await self._calculate_size_match(product, request.user_dimensions, db)
            score += size_match * 0.10

        # Texture match (5% - NEW)
        if request.user_textures:
            texture_match = await self._calculate_texture_match(product, request.user_textures, db)
            score += texture_match * 0.05

        # Pattern match (5% - NEW)
        if request.user_patterns:
            pattern_match = await self._calculate_pattern_match(product, request.user_patterns, db)
            score += pattern_match * 0.05

        # Description similarity (5% - reduced from 20%)
        if request.product_keywords:
            desc_match = self._calculate_description_similarity(product, request.product_keywords)
            score += desc_match * 0.05

        scored_products.append((product, min(score, 1.0)))

    return scored_products
```

---

## Phase 5: Query Processing Updates

**File**: `api/routers/chat.py` - Function `_get_product_recommendations()` (lines 1007-1184)

### Changes:

```python
async def _get_product_recommendations(
    analysis: Any,
    user_message: str,
    db: AsyncSession,
    limit: int = 20
) -> List[dict]:
    """
    Enhanced with attribute extraction from user query
    """

    # Extract style context FIRST (for keyword expansion)
    primary_style = None
    style_preferences = []

    if hasattr(analysis, 'design_analysis') and analysis.design_analysis:
        design_analysis = analysis.design_analysis
        if isinstance(design_analysis, dict):
            style_prefs = design_analysis.get('style_preferences', {})
            if isinstance(style_prefs, dict):
                primary_style = style_prefs.get('primary_style', '')
                secondary_styles = style_prefs.get('secondary_styles', [])
                if primary_style:
                    style_preferences.append(primary_style)
                if secondary_styles:
                    style_preferences.extend(secondary_styles)

    # Extract product keywords with style context
    product_keywords = _extract_product_keywords(user_message, style_context=primary_style)

    # Extract preferences using NLP processor (ENHANCED)
    preferences = design_nlp_processor.analyze_preferences(user_message)

    # NEW: Extract attributes from user query
    user_colors = preferences.get('colors', [])
    user_materials = preferences.get('materials', [])
    user_textures = preferences.get('textures', [])
    user_patterns = preferences.get('patterns', [])

    # Build recommendation request with attributes
    recommendation_request = RecommendationRequest(
        product_keywords=product_keywords,
        style_preferences=style_preferences,
        user_preferences=user_preferences,
        budget_range=budget_range,
        room_context=room_context,

        # NEW FIELDS:
        user_colors=user_colors,
        user_materials=user_materials,
        user_textures=user_textures,
        user_patterns=user_patterns,
        strict_attribute_match=True  # Enable strict filtering
    )

    logger.info(f"Recommendation request - Attributes: colors={user_colors}, "
                f"materials={user_materials}, textures={user_textures}")

    # Get recommendations with new filtering
    product_recommendations = await recommendation_engine.get_recommendations(
        request=recommendation_request,
        db=db,
        limit=limit
    )

    # Log filtering results
    logger.info(f"Attribute filtering returned {len(product_recommendations)} products")

    return product_recommendations
```

---

## Phase 6: Schema Updates

**File**: `api/services/recommendation_engine.py` - RecommendationRequest dataclass

```python
@dataclass
class RecommendationRequest:
    """Enhanced with attribute fields"""

    # Existing fields
    product_keywords: List[str] = None
    style_preferences: List[str] = None
    functional_requirements: List[str] = None
    budget_range: Tuple[float, float] = None
    room_context: Dict[str, Any] = None
    user_preferences: Dict[str, Any] = None

    # NEW FIELDS for attribute matching
    user_colors: List[str] = None              # e.g., ['red', 'burgundy']
    user_materials: List[str] = None           # e.g., ['leather', 'wood']
    user_textures: List[str] = None            # e.g., ['smooth', 'soft']
    user_patterns: List[str] = None            # e.g., ['solid', 'striped']
    user_dimensions: Dict[str, float] = None   # e.g., {'max_width': 84, 'max_depth': 40}
    user_styles: List[str] = None              # e.g., ['modern', 'contemporary']
    strict_attribute_match: bool = False       # Enable strict filtering
```

---

## Phase 7: Testing & Validation

**File**: `scripts/test_attribute_extraction.py` (~200 lines)

### Test Suite:

#### 7.1 Attribute Extraction Tests
```python
async def test_extraction_accuracy():
    """
    Test on 100 sample products with known attributes
    Measure accuracy of Gemini extraction
    """
    test_products = [
        {
            "id": 1,
            "name": "Modern Red Leather Sofa",
            "expected": {
                "furniture_type": "sofa",
                "color_primary": "red",
                "material_primary": "leather",
                "style": "modern"
            }
        },
        # ... 99 more
    ]

    correct = 0
    total = len(test_products)

    for product in test_products:
        extracted = await extract_attributes_from_image(product['image_url'])

        if (extracted['furniture_type'] == product['expected']['furniture_type'] and
            extracted['color_primary'] == product['expected']['color_primary'] and
            extracted['material_primary'] == product['expected']['material_primary']):
            correct += 1

    accuracy = correct / total * 100
    print(f"Extraction Accuracy: {accuracy}%")
    assert accuracy >= 85, "Accuracy below 85% threshold"
```

#### 7.2 Query Tests
```python
async def test_search_queries():
    """
    Test that attribute queries return ONLY matching products
    """
    test_cases = [
        {
            "query": "red leather sofa",
            "expected_attributes": {
                "colors": ["red"],
                "materials": ["leather"],
                "furniture_types": ["sofa"]
            },
            "max_false_positives": 0  # ZERO tolerance
        },
        {
            "query": "modern glass coffee table",
            "expected_attributes": {
                "styles": ["modern"],
                "materials": ["glass"],
                "furniture_types": ["coffee table"]
            },
            "max_false_positives": 0
        },
        {
            "query": "wooden dining chair",
            "expected_attributes": {
                "materials": ["wood", "wooden"],
                "furniture_types": ["dining chair", "chair"]
            },
            "max_false_positives": 0
        }
    ]

    for test in test_cases:
        # Make API request
        response = await chat_api.send_message(
            session_id=test_session_id,
            message=test['query']
        )

        products = response['recommended_products']

        # Verify each product matches ALL specified attributes
        false_positives = 0
        for product in products:
            # Check colors
            if test['expected_attributes'].get('colors'):
                product_colors = await get_product_attributes(product['id'], 'color')
                if not any(c in product_colors for c in test['expected_attributes']['colors']):
                    false_positives += 1
                    print(f"FALSE POSITIVE: {product['name']} - Wrong color")

            # Check materials
            if test['expected_attributes'].get('materials'):
                product_materials = await get_product_attributes(product['id'], 'material')
                if not any(m in product_materials for m in test['expected_attributes']['materials']):
                    false_positives += 1
                    print(f"FALSE POSITIVE: {product['name']} - Wrong material")

        assert false_positives == 0, f"Found {false_positives} false positives for query '{test['query']}'"
        print(f"✅ Query '{test['query']}': {len(products)} products, 0 false positives")
```

#### 7.3 Coverage Tests
```python
async def test_attribute_coverage():
    """
    Measure what % of products have extracted attributes
    """
    total_products = await db.execute(select(func.count(Product.id)))
    total = total_products.scalar()

    products_with_color = await db.execute(
        select(func.count(distinct(ProductAttribute.product_id)))
        .where(ProductAttribute.attribute_name == 'color_primary')
    )

    products_with_material = await db.execute(
        select(func.count(distinct(ProductAttribute.product_id)))
        .where(ProductAttribute.attribute_name == 'material_primary')
    )

    color_coverage = products_with_color.scalar() / total * 100
    material_coverage = products_with_material.scalar() / total * 100

    print(f"Attribute Coverage:")
    print(f"  Color: {color_coverage}%")
    print(f"  Material: {material_coverage}%")

    assert color_coverage >= 80, "Color coverage below 80%"
    assert material_coverage >= 80, "Material coverage below 80%"
```

#### 7.4 Performance Tests
```python
async def test_query_performance():
    """
    Measure response time for attribute-filtered queries
    """
    import time

    queries = [
        "red leather sofa",
        "modern glass table",
        "wooden chair"
    ]

    for query in queries:
        start = time.time()

        response = await chat_api.send_message(
            session_id=test_session_id,
            message=query
        )

        elapsed = time.time() - start

        print(f"Query '{query}': {elapsed:.2f}s, {len(response['recommended_products'])} results")

        # Should be under 5 seconds
        assert elapsed < 5.0, f"Query took {elapsed}s (> 5s threshold)"
```

### Success Criteria:
- ✅ Extraction accuracy ≥ 85%
- ✅ Zero false positives for attribute queries
- ✅ Attribute coverage ≥ 80% of products
- ✅ Query response time < 5 seconds
- ✅ Migration completes without errors
- ✅ Cost < $10 for 5,000 products

---

## Implementation Timeline

### Week 1: Foundation
- **Day 1-2**: Create attribute extraction service
- **Day 3**: Test extraction on 100 sample products
- **Day 4**: Create migration script
- **Day 5**: Run dry-run migration (1,000 products)

### Week 2: Integration
- **Day 1-2**: Update recommendation engine (scoring functions)
- **Day 3**: Update chat router (query processing)
- **Day 4**: Add strict filtering logic
- **Day 5**: Integration testing

### Week 3: Migration & Testing
- **Day 1-3**: Run full migration (all products)
- **Day 4**: Create and run test suite
- **Day 5**: Fix any issues, validate results

### Week 4: Production
- **Day 1**: Integrate into scraping pipeline
- **Day 2-3**: Monitor production performance
- **Day 4**: Optimize based on real usage
- **Day 5**: Documentation and handoff

---

## File Changes Summary

### New Files (3):
1. **`api/services/attribute_extraction_service.py`** (~450 lines)
   - Image-based extraction (Gemini Vision)
   - Text-based extraction (NLP + regex)
   - Attribute merging logic
   - Database storage functions
   - Rate limiting and error handling

2. **`scripts/migrate_extract_attributes.py`** (~300 lines)
   - Batch processing engine
   - Progress tracking and resume capability
   - Error logging and reporting
   - CLI interface
   - Statistics generation

3. **`scripts/test_attribute_extraction.py`** (~200 lines)
   - Extraction accuracy tests
   - Query validation tests
   - Coverage tests
   - Performance tests
   - False positive detection

### Modified Files (3):
1. **`api/services/recommendation_engine.py`** (+250 lines, modify ~100 lines)
   - Replace `_calculate_color_match()` (remove placeholder)
   - Replace `_calculate_material_match()` (remove placeholder)
   - Add `_calculate_size_match()` (NEW)
   - Add `_calculate_texture_match()` (NEW)
   - Add `_calculate_pattern_match()` (NEW)
   - Add strict attribute filtering logic (before scoring)
   - Fix category relationship filtering (line 333-341)
   - Update scoring weights (line 364-413)
   - Add new fields to RecommendationRequest dataclass

2. **`scrapers/pipelines.py`** (+120 lines)
   - Create AttributeExtractionPipeline class
   - Integrate with existing pipeline stages
   - Add error handling for extraction failures
   - Configure pipeline order

3. **`api/routers/chat.py`** (+50 lines modifications)
   - Update `_get_product_recommendations()` function
   - Add attribute extraction from user query
   - Pass attributes to recommendation engine
   - Enable strict_attribute_match flag
   - Add logging for filtered results

---

## Cost Analysis

### Gemini API Costs:
- **Free Tier**: 1,500 requests/day
- **Paid Tier**: ~$0.0015 per image analysis

### Migration Cost (One-Time):
| Products | Cost (Free Tier) | Cost (Paid Tier) |
|----------|------------------|------------------|
| 1,500 | $0 | $2.25 |
| 5,000 | $0 (use over 4 days) | $7.50 |
| 10,000 | $0 (use over 7 days) | $15.00 |
| 50,000 | $0 (use over 34 days) | $75.00 |

### Ongoing Costs (Per 1,000 New Products):
- **Scraping with Gemini**: ~$1.50
- **ChatGPT Vision (alternative)**: ~$20-30
- **Savings**: ~90%

### Total Expected Cost:
- One-time migration (10,000 products): **$0-15**
- Monthly new products (500/month): **$0.75/month**
- **Annual cost**: ~$9/year

Compare to ChatGPT Vision:
- Migration (10,000): $200-300
- Monthly (500): $10-15/month
- Annual: $120-180/year

**Cost savings with Gemini: ~$100-170/year**

---

## Risk Mitigation

### Risk 1: Low Extraction Accuracy
**Mitigation**:
- Test on 100 products before full migration
- Implement confidence scoring
- Fall back to text extraction
- Manual review of low-confidence extractions

### Risk 2: API Rate Limiting
**Mitigation**:
- Implement queue system with rate limiting
- Use free tier strategically (1,500/day = 45,000/month)
- Exponential backoff on 429 errors
- Resume capability in migration script

### Risk 3: Migration Failures
**Mitigation**:
- Checkpoint system (save progress every 100 products)
- Resume from last checkpoint
- Log all failures to CSV for retry
- Dry-run mode for testing

### Risk 4: Empty Search Results
**Mitigation**:
- If strict filtering returns 0 results, relax constraints
- Show message: "No exact matches found. Showing similar products..."
- Fall back to keyword-only matching
- Log zero-result queries for analysis

### Risk 5: Inconsistent Attribute Data
**Mitigation**:
- Validate extracted attributes against expected values
- Implement attribute normalization (e.g., "red" = "crimson" = "burgundy")
- Manual review of unusual values
- Confidence scoring to identify uncertain extractions

---

## Monitoring & Metrics

### Key Metrics to Track:

#### Extraction Quality:
- Extraction success rate
- Average confidence score
- Failed extractions (by error type)
- Extraction time (avg, p50, p95)

#### Search Quality:
- False positive rate (target: 0%)
- Zero-result queries (should be rare)
- Average products per query
- User satisfaction (click-through rate)

#### Performance:
- Query response time
- Database query performance
- API latency
- Cache hit rate

#### Cost:
- Gemini API requests per day
- Cost per product extraction
- Total monthly cost
- Cost per recommendation request

### Logging:
```python
logger.info(f"Attribute extraction: product_id={product_id}, "
            f"success={success}, confidence={confidence_score}, "
            f"time={extraction_time}s, method={extraction_method}")

logger.info(f"Recommendation query: query='{user_message}', "
            f"filters={user_colors, user_materials}, "
            f"candidates={len(candidates)}, results={len(results)}, "
            f"false_positives={false_positive_count}")
```

---

## Success Criteria

### Phase Completion Criteria:

#### Phase 1: Attribute Extraction Service ✅
- [ ] Service extracts attributes with 85%+ accuracy
- [ ] Image extraction works for 100 test products
- [ ] Text extraction fills gaps for missing image data
- [ ] Attributes stored correctly in ProductAttribute table

#### Phase 2: Migration Script ✅
- [ ] Dry-run completes without errors (1,000 products)
- [ ] Resume capability works correctly
- [ ] Error logging captures all failures
- [ ] Full migration completes (all products)
- [ ] 80%+ products have extracted attributes

#### Phase 3: Scraping Integration ✅
- [ ] New products automatically get attributes
- [ ] Scraping continues even if extraction fails
- [ ] Attributes visible in admin panel
- [ ] No impact on scraping speed

#### Phase 4: Recommendation Engine ✅
- [ ] Color matching uses real data (no placeholder)
- [ ] Material matching uses real data (no placeholder)
- [ ] Strict filtering returns only matching products
- [ ] Query tests pass with 0 false positives
- [ ] Scoring weights optimized

#### Phase 5: Query Processing ✅
- [ ] User queries extract attributes correctly
- [ ] Attributes passed to recommendation engine
- [ ] Results respect strict filtering
- [ ] Response time < 5 seconds

#### Phase 6: Testing ✅
- [ ] All test cases pass
- [ ] False positive rate = 0%
- [ ] Attribute coverage ≥ 80%
- [ ] Performance meets SLA

### Overall Success Criteria:
- ✅ **Zero false positives** for attribute queries
- ✅ **85-95% extraction accuracy**
- ✅ **80%+ attribute coverage** across products
- ✅ **<5 second response time** for queries
- ✅ **Cost < $10** for initial migration
- ✅ **No regressions** in existing functionality

---

## Rollback Plan

If issues occur in production:

### Level 1: Disable Strict Filtering
```python
# In chat.py
strict_attribute_match=False  # Fall back to old behavior
```
Impact: Returns to previous recommendation quality (with false positives)

### Level 2: Disable Attribute Scoring
```python
# In recommendation_engine.py
# Comment out new scoring functions
# Use old placeholder scores
```
Impact: Recommendations based on keywords only

### Level 3: Disable Attribute Extraction
```python
# In pipelines.py
# Remove AttributeExtractionPipeline from ITEM_PIPELINES
```
Impact: New products won't get attributes, but existing data remains

### Level 4: Full Rollback
```sql
-- Clear all extracted attributes
DELETE FROM product_attributes WHERE extraction_method = 'gemini_vision';
```
Impact: Complete revert to pre-migration state

---

## Future Enhancements

### Phase 2 Improvements (Post-Launch):
1. **Machine Learning Model**
   - Train custom model on extracted attributes
   - Improve accuracy beyond 95%
   - Reduce API costs

2. **Visual Similarity Search**
   - "Find products similar to this image"
   - Vector embeddings for visual search
   - Image-to-image recommendations

3. **Smart Attribute Suggestion**
   - Auto-suggest attributes while user types
   - "Did you mean 'burgundy' instead of 'red'?"
   - Attribute autocomplete

4. **Confidence-Based UI**
   - Show confidence scores to users
   - "90% match" badges on products
   - Filter by minimum confidence

5. **Attribute Facets**
   - Filter sidebar with extracted attributes
   - "Color: Red (45), Blue (32), Gray (28)"
   - Multi-select attribute filtering

---

## Appendix

### A. Attribute Schema

#### ProductAttribute Table Structure:
```sql
CREATE TABLE product_attributes (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    attribute_name VARCHAR(100) NOT NULL,
    attribute_value TEXT NOT NULL,
    attribute_type VARCHAR(20) DEFAULT 'text',
    confidence_score FLOAT DEFAULT 1.0,
    extraction_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_product_attributes_product_id (product_id),
    INDEX idx_product_attributes_name (attribute_name),
    INDEX idx_product_attributes_value (attribute_value),
    INDEX idx_product_attributes_composite (product_id, attribute_name)
);
```

#### Attribute Types:
- **color_primary**: Main color (e.g., "red", "blue", "gray")
- **color_secondary**: Secondary color (e.g., "white", "black")
- **color_accent**: Accent color (e.g., "gold", "silver")
- **material_primary**: Main material (e.g., "leather", "wood", "metal")
- **material_secondary**: Secondary material (e.g., "fabric", "plastic")
- **style**: Design style (e.g., "modern", "traditional", "rustic")
- **width**: Width in inches (numeric)
- **depth**: Depth in inches (numeric)
- **height**: Height in inches (numeric)
- **weight**: Weight in pounds (numeric)
- **texture**: Surface texture (e.g., "smooth", "rough", "woven")
- **pattern**: Visual pattern (e.g., "solid", "striped", "floral")
- **furniture_type**: Category (e.g., "sofa", "chair", "table")

### B. Gemini API Configuration

#### Model Selection:
- **Image Analysis**: `gemini-2.0-flash-exp`
- **Text Analysis**: `gemini-2.0-flash-exp`
- **Response Format**: `application/json`

#### Request Structure:
```json
{
  "contents": [{
    "parts": [
      {
        "text": "Extract furniture attributes from this product image. Return JSON with: furniture_type, colors (primary, secondary, accent), materials (primary, secondary), style, dimensions (width, depth, height in inches), texture, pattern. Include confidence scores for each attribute (0-1)."
      },
      {
        "inline_data": {
          "mime_type": "image/jpeg",
          "data": "<base64_encoded_image>"
        }
      }
    ]
  }],
  "generationConfig": {
    "temperature": 0.2,
    "responseMimeType": "application/json",
    "responseSchema": {
      "type": "object",
      "properties": {
        "furniture_type": {"type": "string"},
        "colors": {
          "type": "object",
          "properties": {
            "primary": {"type": "string"},
            "secondary": {"type": "string"},
            "accent": {"type": "string"}
          }
        },
        "materials": {
          "type": "object",
          "properties": {
            "primary": {"type": "string"},
            "secondary": {"type": "string"}
          }
        },
        "style": {"type": "string"},
        "dimensions": {
          "type": "object",
          "properties": {
            "width": {"type": "number"},
            "depth": {"type": "number"},
            "height": {"type": "number"}
          }
        },
        "texture": {"type": "string"},
        "pattern": {"type": "string"},
        "confidence_scores": {
          "type": "object",
          "properties": {
            "furniture_type": {"type": "number"},
            "colors": {"type": "number"},
            "materials": {"type": "number"},
            "style": {"type": "number"}
          }
        }
      }
    }
  }
}
```

### C. Color Family Mappings

For fuzzy color matching:
```python
COLOR_FAMILIES = {
    # Reds
    'red': ['red', 'crimson', 'burgundy', 'maroon', 'ruby', 'cherry', 'wine'],
    'crimson': ['red', 'crimson', 'burgundy', 'maroon'],
    'burgundy': ['burgundy', 'maroon', 'wine', 'red'],

    # Blues
    'blue': ['blue', 'navy', 'royal blue', 'cobalt', 'azure', 'turquoise'],
    'navy': ['navy', 'blue', 'dark blue', 'midnight blue'],

    # Greens
    'green': ['green', 'emerald', 'sage', 'olive', 'forest green'],
    'emerald': ['emerald', 'green', 'jade'],

    # Neutrals
    'gray': ['gray', 'grey', 'charcoal', 'slate', 'silver'],
    'beige': ['beige', 'tan', 'khaki', 'cream', 'ivory'],
    'white': ['white', 'off-white', 'cream', 'ivory'],
    'black': ['black', 'charcoal', 'ebony'],

    # Browns
    'brown': ['brown', 'chocolate', 'espresso', 'walnut', 'mahogany'],
    'tan': ['tan', 'beige', 'camel', 'khaki'],
}
```

---

## Contact & Support

For questions or issues during implementation:
- Check logs in `/tmp/attribute_extraction.log`
- Review error reports in `migration_errors.csv`
- Monitor Gemini API dashboard for rate limits
- Check database for orphaned records

---

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Status**: Ready for Implementation
