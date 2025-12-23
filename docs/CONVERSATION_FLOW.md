# Omni AI Stylist - Conversation Flow & State Management

## Overview

This document describes the complete flow of parameters from user input to product display for all use cases in the Omni AI Stylist system.

---

## 1. CONVERSATION STATES

| State | Meaning | Products Shown? | Next Possible States |
|-------|---------|-----------------|---------------------|
| `INITIAL` | First message, no context yet | No | GATHERING_*, DIRECT_SEARCH, DIRECT_SEARCH_GATHERING |
| `GATHERING_USAGE` | Asking what room/purpose | No | GATHERING_STYLE |
| `GATHERING_STYLE` | Asking style preference | No | GATHERING_BUDGET |
| `GATHERING_BUDGET` | Asking budget | No | GATHERING_SCOPE, READY_TO_RECOMMEND |
| `GATHERING_SCOPE` | Asking what categories needed | No | READY_TO_RECOMMEND |
| `DIRECT_SEARCH` | User asked for specific product, has all info | **YES** | BROWSING, READY_TO_RECOMMEND |
| `DIRECT_SEARCH_GATHERING` | User asked for specific product, needs more info (budget/style) | No | READY_TO_RECOMMEND |
| `READY_TO_RECOMMEND` | All info gathered, showing products | **YES** | BROWSING |
| `BROWSING` | User is browsing/filtering products | **YES** | READY_TO_RECOMMEND |

### State Transition Rules

```
INITIAL
  ├─► DIRECT_SEARCH (if user asks for specific product with enough info)
  ├─► DIRECT_SEARCH_GATHERING (if user asks for specific product, needs budget/style)
  └─► GATHERING_USAGE (guided flow starts)

GATHERING_USAGE → GATHERING_STYLE → GATHERING_BUDGET → GATHERING_SCOPE → READY_TO_RECOMMEND

DIRECT_SEARCH_GATHERING → READY_TO_RECOMMEND (after user provides budget/style or declines)

READY_TO_RECOMMEND ↔ BROWSING (user can filter/browse)
```

---

## 2. KEY PARAMETERS

### Backend Parameters (chat.py)

| Parameter | Type | Purpose |
|-----------|------|---------|
| `conversation_state` | string | Current flow state |
| `selected_categories_response` | List[CategoryRecommendation] | Categories to show |
| `products_by_category` | Dict[str, List[dict]] | Products grouped by category |
| `direct_search_result` | dict | Extracted info from direct search |
| `omni_prefs` | UserPreferencesData | Persisted user preferences |
| `size_keywords_for_search` | List[str] | Size/type keywords (e.g., "sectional") |

### Frontend Parameters

| Parameter | Location | Purpose |
|-----------|----------|---------|
| `selectedCategories` | DesignPage state | Categories from API |
| `productsByCategory` | DesignPage state | Products from API |
| `hasCategoryProducts` | ProductDiscoveryPanel | Count of products (triggers display) |

---

## 3. USE CASES - DETAILED FLOW

---

### USE CASE 1: Direct Search with Budget Decline

**User Flow:** "find me sectional sofas" → "no budget"

#### Message 1: "find me sectional sofas"

**Step 1: Backend - Direct Search Detection** (`chat.py:450-600`)
```python
direct_search_result = detect_direct_search(message)
# Returns:
{
    "is_direct_search": True,
    "detected_categories": ["sofas"],
    "extracted_sizes": ["sectional"],      # ← Type attribute extracted
    "extracted_styles": [],
    "extracted_colors": [],
    "extracted_materials": [],
    "confidence": 0.9
}
```

**Step 2: Backend - Category Attribute Persistence** (`chat.py:519-546`)
```python
# "sectional" is stored for later retrieval
conversation_context_manager.update_omni_preferences(
    session_id,
    category_attributes={"seating_type": "sectional"}
)
```

**Step 3: Backend - State Determination** (`chat.py:1270-1280`)
```python
# No budget provided → needs gathering
conversation_state = "DIRECT_SEARCH_GATHERING"
```

**Step 4: Backend - Category Setup** (`chat.py:1797-1810`)
```python
selected_categories_response = [
    CategoryRecommendation(
        category_id="sofas",
        display_name="Sectional Sofas",
        priority=1
    )
]
```

**Step 5: Backend - Products Cleared** (`chat.py:2163-2170`)
```python
# State is DIRECT_SEARCH_GATHERING → clear products
products_by_category = None
# BUT keep selected_categories_response (line 2171-2176)
```

**Step 6: API Response**
```json
{
    "message": {"content": "Let's find some sectional sofas. What's your budget?"},
    "conversation_state": "DIRECT_SEARCH_GATHERING",
    "selected_categories": [{"category_id": "sofas", "display_name": "Sectional Sofas"}],
    "products_by_category": null,
    "follow_up_question": null
}
```

**Step 7: Frontend - ChatPanel** (`ChatPanel.tsx:255-288`)
```typescript
const hasCategoryData = response.selected_categories && response.products_by_category;
// = true && null = false
// onProductRecommendations NOT called (or called with null products)
```

**Step 8: Frontend - ProductDiscoveryPanel** (`ProductDiscoveryPanel.tsx:269-274`)
```typescript
const hasCategoryProducts = selectedCategories && productsByCategory
    ? Object.values(productsByCategory).reduce(...)
    : 0;
// = 0 → Shows "No Products Yet"
```

**Result: ✓ Correct - No products shown while gathering budget**

---

#### Message 2: "no budget"

**Step 1: Backend - ChatGPT Analysis**
```python
# ChatGPT returns:
analysis.conversation_state = "BROWSING"  # or "READY_TO_RECOMMEND"
analysis.detected_category = "sectional_sofas"
```

**Step 2: Backend - State Override** (`chat.py:1396-1412`)
```python
# User declined budget → set to READY_TO_RECOMMEND
conversation_state = "READY_TO_RECOMMEND"
```

**Step 3: Backend - Retrieve Persisted Attributes** (`chat.py:1950-1957`)
```python
# Retrieve the "sectional" we saved earlier
omni_prefs = conversation_context_manager.get_omni_preferences(session_id)
cat_attrs = omni_prefs.category_attributes  # {"seating_type": "sectional"}
size_keywords_for_search = ["sectional"]
```

**Step 4: Backend - Fetch Products** (`chat.py:1979-1991`)
```python
products_by_category = await _get_category_based_recommendations(
    selected_categories_response,  # [sofas]
    db,
    size_keywords=size_keywords_for_search,  # ["sectional"]
    ...
)
# Returns: {"sofas": [61 products, sectional ones prioritized at top]}
```

**Step 5: Backend - Product Scoring** (`chat.py:5006-5021`)
```python
# Products with "sectional" in name/type get score -10 (best)
# Other products get score 100 (shown after sectional)
```

**Step 6: API Response**
```json
{
    "message": {"content": "Here are some stunning sectional sofas!"},
    "conversation_state": "READY_TO_RECOMMEND",
    "selected_categories": [{"category_id": "sofas", "product_count": 61}],
    "products_by_category": {
        "sofas": [
            {"name": "Lore Sofa L-Shaped Sectional", "style_score": -10},
            {"name": "Kenzo Sectional Sofa", "style_score": -10},
            // ... more sectional sofas with score -10
            {"name": "Bari Sofa", "style_score": 100},
            // ... other sofas with score 100
        ]
    }
}
```

**Step 7: Frontend - ChatPanel** (`ChatPanel.tsx:255-288`)
```typescript
const hasCategoryData = response.selected_categories && response.products_by_category;
// = true && true = true

onProductRecommendations({
    selected_categories: [...],
    products_by_category: {"sofas": [61 products]}
});
```

**Step 8: Frontend - DesignPage** (`page.tsx:756-768`)
```typescript
setSelectedCategories(response.selected_categories);
setProductsByCategory(response.products_by_category);
```

**Step 9: Frontend - ProductDiscoveryPanel** (`ProductDiscoveryPanel.tsx:269-274`)
```typescript
const hasCategoryProducts = Object.values(productsByCategory)
    .reduce((sum, prods) => sum + prods.length, 0);
// = 61 → Shows products
```

**Result: ✓ Products displayed with sectional sofas at top**

---

### USE CASE 2: Direct Search with Full Info

**User Flow:** "show me modern red 3-seater sofas under 50000"

#### Single Message Flow

**Step 1: Backend - Direct Search Detection**
```python
direct_search_result = {
    "is_direct_search": True,
    "detected_categories": ["sofas"],
    "extracted_sizes": ["3 seater"],
    "extracted_styles": ["modern"],
    "extracted_colors": ["red"],
    "has_budget": True  # triggers DIRECT_SEARCH, not DIRECT_SEARCH_GATHERING
}
```

**Step 2: Backend - State Determination**
```python
# Has budget info → direct search with all info
conversation_state = "DIRECT_SEARCH"
```

**Step 3: Backend - Products Fetched Immediately**
```python
# State is DIRECT_SEARCH (in READY_TO_RECOMMEND list)
# Products are fetched with all filters applied
products_by_category = await _get_category_based_recommendations(
    categories,
    style_attributes={
        "style_keywords": ["modern", "3 seater"],
        "colors": ["red"]
    },
    size_keywords=["3 seater"]
)
```

**Step 4: API Response**
```json
{
    "conversation_state": "DIRECT_SEARCH",
    "selected_categories": [{"category_id": "sofas"}],
    "products_by_category": {"sofas": [filtered products]},
    "total_budget": 50000
}
```

**Result: ✓ Products shown immediately (no gathering needed)**

---

### USE CASE 3: Guided Flow (Room Image Upload)

**User Flow:** Upload room image → "modern style" → "50000 budget" → "just sofas"

#### Message 1: Room Image Upload

**Backend Flow:**
```python
# Image analyzed by Gemini
room_analysis = analyze_room_image(image)
# Returns detected style, existing furniture, etc.

conversation_state = "GATHERING_STYLE"
products_by_category = None
```

**API Response:**
```json
{
    "conversation_state": "GATHERING_STYLE",
    "products_by_category": null,
    "message": {"content": "Beautiful room! What style are you going for?"}
}
```

#### Message 2: "modern style"

**Backend Flow:**
```python
omni_prefs.overall_style = "modern"
conversation_state = "GATHERING_BUDGET"
products_by_category = None
```

#### Message 3: "50000 budget"

**Backend Flow:**
```python
omni_prefs.budget_total = 50000
conversation_state = "GATHERING_SCOPE"
products_by_category = None
```

#### Message 4: "just sofas"

**Backend Flow:**
```python
omni_prefs.scope = ["sofas"]
conversation_state = "READY_TO_RECOMMEND"

# NOW fetch products
products_by_category = await _get_category_based_recommendations(
    categories=[sofas],
    style_attributes={"style_keywords": ["modern"]},
    budget=50000
)
```

**API Response:**
```json
{
    "conversation_state": "READY_TO_RECOMMEND",
    "products_by_category": {"sofas": [products within budget, modern style prioritized]}
}
```

**Result: ✓ Products shown after all info gathered**

---

### USE CASE 4: Generic Category Search

**User Flow:** "I need lighting" → "floor lamps"

#### Message 1: "I need lighting"

**Backend Flow:**
```python
direct_search_result = {
    "is_direct_search": True,
    "detected_categories": ["lighting"],  # Generic category
    "is_generic_category": True  # Triggers subcategory question
}

conversation_state = "DIRECT_SEARCH_GATHERING"
follow_up_question = "What type of lighting? (floor lamps, table lamps, chandeliers)"
```

**API Response:**
```json
{
    "conversation_state": "DIRECT_SEARCH_GATHERING",
    "products_by_category": null,
    "message": {"content": "What type of lighting? Floor lamps, table lamps, or chandeliers?"}
}
```

#### Message 2: "floor lamps"

**Backend Flow:**
```python
# Specific category now known
detected_categories = ["lamps"]
conversation_state = "READY_TO_RECOMMEND"
products_by_category = {"lamps": [floor lamp products]}
```

**Result: ✓ Products shown after subcategory specified**

---

## 4. CRITICAL CHECKPOINTS

### When Products ARE Shown

Products are included in API response when ALL conditions are met:

1. `conversation_state` is in: `["READY_TO_RECOMMEND", "DIRECT_SEARCH", "BROWSING"]`
2. `selected_categories_response` is not None/empty
3. Code reaches product fetch block (line 1913-1998)
4. Code does NOT reach clearing block (line 2163-2170)

### When Products are CLEARED

Products are set to `None` when:

1. `conversation_state` is in: `["GATHERING_USAGE", "GATHERING_STYLE", "GATHERING_BUDGET", "GATHERING_SCOPE", "DIRECT_SEARCH_GATHERING"]`
2. Line 2170: `products_by_category = None`

### Frontend Display Conditions

```typescript
// ProductDiscoveryPanel.tsx
const hasCategoryProducts = selectedCategories && productsByCategory
    ? Object.values(productsByCategory).reduce((sum, prods) => sum + (prods?.length || 0), 0)
    : 0;

if (products.length === 0 && !hasCategoryProducts) {
    // Show "No Products Yet"
}
```

---

## 5. PARAMETER PERSISTENCE

### What Gets Persisted (UserPreferencesData)

| Field | Persisted When | Retrieved When |
|-------|---------------|----------------|
| `overall_style` | User says "modern", "minimalist", etc. | Every subsequent message |
| `budget_total` | User provides budget | Every subsequent message |
| `scope` | User specifies categories | Every subsequent message |
| `category_attributes` | Size/type extracted (e.g., "sectional") | When fetching products |
| `room_analysis_suggestions` | Room image analyzed | Auto-fill style if not specified |

### How Persistence Works

```python
# Storing (chat.py:519-546)
conversation_context_manager.update_omni_preferences(
    session_id,
    category_attributes={"seating_type": "sectional"}
)

# Retrieving (chat.py:1950-1957)
omni_prefs = conversation_context_manager.get_omni_preferences(session_id)
size_keywords = list(omni_prefs.category_attributes.values())
```

---

## 6. DEBUGGING CHECKLIST

### Backend Issues

1. **Products not fetched**: Check if `conversation_state` reaches the fetch block (line 1913)
2. **Products cleared**: Check if state is in gathering list (line 2157-2163)
3. **Wrong category**: Check `normalize_category_name()` mapping
4. **No products found**: Check database has products in that category

### Frontend Issues

1. **`onProductRecommendations` not called**: Check `hasCategoryData` condition
2. **State not updated**: Check React state updates in `handleProductRecommendations`
3. **Products not rendering**: Check `hasCategoryProducts` calculation

### Log Messages to Watch

```
[DIRECT SEARCH] Detected direct search for: sofas
[DIRECT SEARCH] Set conversation_state=DIRECT_SEARCH_GATHERING
[PERSISTED ATTRS] Retrieved size keywords: ['sectional']
[CATEGORY RECS] Type prioritization - 32 products match types ['sectional']
[OMNI FLOW] State is DIRECT_SEARCH_GATHERING - gathering, clearing products
[READY_TO_RECOMMEND PRESERVED] Keeping conversation_state=READY_TO_RECOMMEND
```

---

## 7. STATE FLOW DIAGRAM

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                      USER INPUT                          │
                    └─────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │              detect_direct_search()                      │
                    │   Extracts: categories, sizes, colors, styles, budget    │
                    └─────────────────────────────────────────────────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         │                    │                    │
                         ▼                    ▼                    ▼
                ┌─────────────┐     ┌─────────────────┐    ┌──────────────┐
                │ DIRECT_SEARCH│     │DIRECT_SEARCH_   │    │ GATHERING_*  │
                │ (has budget) │     │GATHERING        │    │ (guided flow)│
                └─────────────┘     │(needs budget)   │    └──────────────┘
                         │          └─────────────────┘              │
                         │                    │                      │
                         │                    │ User provides        │
                         │                    │ budget or declines   │
                         │                    │                      │
                         ▼                    ▼                      ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │                 READY_TO_RECOMMEND                       │
                    │   • products_by_category = fetch products               │
                    │   • Apply size/type prioritization                      │
                    │   • Apply style/color/material filters                  │
                    └─────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │                    API RESPONSE                          │
                    │   products_by_category: {category: [products...]}       │
                    └─────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │              FRONTEND: ChatPanel                         │
                    │   hasCategoryData = selected_categories &&              │
                    │                     products_by_category                │
                    │   if (hasCategoryData) → onProductRecommendations()     │
                    └─────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │              FRONTEND: DesignPage                        │
                    │   setSelectedCategories(...)                            │
                    │   setProductsByCategory(...)                            │
                    └─────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │          FRONTEND: ProductDiscoveryPanel                 │
                    │   hasCategoryProducts = sum of all products             │
                    │   if (hasCategoryProducts > 0) → SHOW PRODUCTS          │
                    │   else → "No Products Yet"                              │
                    └─────────────────────────────────────────────────────────┘
```

---

## 8. QUICK REFERENCE: When Products Show

| User Says | State | Products? | Why |
|-----------|-------|-----------|-----|
| "find me sofas" | DIRECT_SEARCH_GATHERING | No | Needs budget |
| "find me sofas" → "no budget" | READY_TO_RECOMMEND | Yes | Declined = ready |
| "find me red sofas under 50k" | DIRECT_SEARCH | Yes | Has all info |
| "I need help decorating" | GATHERING_USAGE | No | Guided flow start |
| (after guided flow complete) | READY_TO_RECOMMEND | Yes | All info gathered |
| "show me something else" | BROWSING | Yes | Still has context |
