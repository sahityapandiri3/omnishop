# ChatGPT Design Analysis & Keyword Extraction - How It Works

## Summary

**YES, ChatGPT IS doing design analysis and passing keywords for search!**

The system uses a TWO-TIER approach for product recommendations:

### Tier 1: ChatGPT Design Analysis (Style, Colors, Materials)
ChatGPT analyzes user messages for:
- **Style preferences**: modern, traditional, scandinavian, etc.
- **Color schemes**: preferred colors, accent colors, temperature
- **Materials**: wood, fabric, metal, glass, etc.
- **Functional requirements**: seating capacity, storage needs
- **Budget indicators**: budget/mid-range/luxury

### Tier 2: Local Keyword Extraction (Furniture Types)
A local function extracts furniture TYPE keywords:
- **Product types**: sofa, chair, table, bed, lamp, etc.
- **Synonyms**: sofa = [sofa, couch, sectional, loveseat]

---

## Flow Diagram

```
User: "I want a modern sofa for my living room"
         |
         v
┌────────────────────────────────┐
│ 1. ChatGPT Analysis            │
│    (chatgpt_service.py:261)    │
├────────────────────────────────┤
│ Analyzes:                      │
│ ✓ Style: "modern"              │
│ ✓ Colors: ["neutral", "gray"]  │
│ ✓ Materials: ["fabric", "wood"]│
│ ✓ Room: "living_room"          │
└────────────────────────────────┘
         |
         v
┌────────────────────────────────┐
│ 2. Local Keyword Extraction    │
│    (chat.py:705)               │
├────────────────────────────────┤
│ Extracts furniture types:      │
│ ✓ "sofa" found in message      │
│ ✓ Returns ALL synonyms:        │
│   ['sofa', 'sofas', 'couch',   │
│    'couches', 'sectional',     │
│    'sectionals', 'loveseat']   │
└────────────────────────────────┘
         |
         v
┌────────────────────────────────┐
│ 3. Recommendation Engine       │
│    (recommendation_engine.py)  │
├────────────────────────────────┤
│ Searches products WHERE:       │
│ ✓ name/description matches     │
│   keywords (sofa, couch, etc.) │
│ ✓ style matches "modern"       │
│ ✓ colors match preferences     │
│ ✓ materials match preferences  │
└────────────────────────────────┘
         |
         v
    Product Results
```

---

## Code Locations

### 1. ChatGPT Design Analysis
**File**: `/Users/sahityapandiri/Omnishop/api/services/chatgpt_service.py`

**Method**: `analyze_user_input()` (Line 261)

**What it does**:
- Sends user message + image to ChatGPT
- Uses structured system prompt requesting JSON response
- Returns:
  - `design_analysis`: style, colors, space analysis
  - `product_matching_criteria`: filtering keywords, materials
  - `user_friendly_response`: conversational text

**Example ChatGPT Output**:
```json
{
  "design_analysis": {
    "style_preferences": {
      "primary_style": "modern",
      "style_keywords": ["clean", "simple", "functional"]
    },
    "color_scheme": {
      "preferred_colors": ["white", "light gray", "natural wood"]
    }
  },
  "product_matching_criteria": {
    "filtering_keywords": {
      "include_terms": ["modern", "contemporary"],
      "material_preferences": ["wood", "metal"]
    }
  }
}
```

### 2. Local Keyword Extraction
**File**: `/Users/sahityapandiri/Omnishop/api/routers/chat.py`

**Method**: `_extract_product_keywords()` (Line 705)

**What it does**:
- Scans user message for furniture type keywords
- Uses hardcoded synonym groups
- If "sofa" found → returns ALL sofa synonyms
- If "chair" found → returns ALL chair synonyms

**Synonym Groups** (Lines 710-729):
```python
synonym_groups = {
    'sofa': ['sofa', 'sofas', 'couch', 'couches', 'sectional', 'sectionals', 'loveseat', 'loveseats'],
    'chair': ['chair', 'chairs', 'armchair', 'armchairs', 'recliner', 'recliners'],
    'table': ['table', 'tables'],
    'coffee_table': ['coffee table', 'coffee tables', 'cocktail table'],
    # ... 20+ more groups
}
```

**Example**:
- Input: "I want to replace my sofa"
- Output: `['sofa', 'sofas', 'couch', 'couches', 'sectional', 'sectionals', 'loveseat', 'loveseats']`

### 3. Recommendation Engine Search
**File**: `/Users/sahityapandiri/Omnishop/api/services/recommendation_engine.py`

**Method**: `_get_candidate_products()` (Line 200)

**What it does**:
- Receives keywords from both sources
- Searches database using PostgreSQL regex
- Filters by:
  - Product name/description contains keywords (word boundary matching)
  - Style matches ChatGPT analysis
  - Colors match preferences
  - Materials match preferences

**SQL Query** (Lines 206-214):
```python
for keyword in product_keywords:
    escaped_keyword = re.escape(keyword)
    # PostgreSQL regex with word boundaries
    keyword_conditions.append(Product.name.op('~*')(rf'\y{escaped_keyword}\y'))
    keyword_conditions.append(Product.description.op('~*')(rf'\y{escaped_keyword}\y'))
```

---

## Why Two-Tier Approach?

### ChatGPT Handles:
✓ Subjective analysis (style, aesthetics, mood)
✓ Color interpretation
✓ Material preferences
✓ Complex design concepts

### Local Keywords Handle:
✓ Fast, reliable furniture type extraction
✓ Comprehensive synonym matching
✓ No AI token cost for basic matching
✓ Consistent results (no LLM variance)

---

## Verification Test

To verify ChatGPT is working, check server logs for:

```bash
# Look for these log messages:
[DEBUG] analyze_user_input called - message: ...
[DEBUG] About to call _call_chatgpt with N messages
[DEBUG] OpenAI API call succeeded!
[DEBUG] DesignAnalysisSchema created successfully
```

Also check recommendation engine logs:
```bash
# Should see:
INFO: Filtering products by keywords: ['sofa', 'sofas', 'couch', ...]
```

---

## Current Database State

**Total Products**: 339
**Sofa Products**: 111 (confirmed via search endpoint)

**Example sofa products**:
1. SWAY LUNGO SOFA (ID: 571)
2. SPIN SOFA (ID: 561)
3. KYOTO SOFA (ID: 537)
4. CALISTA SOFA (ID: 531)
5. TAMA SOFA (ID: 530)
... 106 more

**First 20 products** (sorted by scraped_at DESC):
- CHISEL SIDE TABLE
- MUSHROOM SIDE TABLE BRASS
- FREEDOM BOOKSHELF
- HANDLE 3-PC COFFEE TABLE BRASS
- (All accessories - no sofas in first page)

**Why test selected side table instead of sofa**:
The test fetches first 10 products, which are all accessories (newest scraped).
Sofas exist but are in later pages.

---

## Recommendation

To ensure tests find sofa products, either:

### Option 1: Modify Test to Search for Sofas
```python
# Instead of fetching first 10 products:
async with session.get(f"{API_BASE_URL}/api/products/?search=sofa&page=1&size=10") as response:
    products = await response.json()
```

### Option 2: Change Product Sort Order
In `products.py`, change default sort to prioritize certain categories or names.

### Option 3: Specify Product ID
Directly use a known sofa product ID (e.g., 571, 561, 537).

---

## Conclusion

✅ **ChatGPT IS analyzing design preferences**
✅ **ChatGPT IS extracting style/color/material keywords**
✅ **Local function IS extracting furniture type keywords**
✅ **Recommendation engine IS using BOTH sets of keywords**

The system is working as designed. The test issue was purely due to pagination - sofas exist but aren't in the first page of results due to sorting by `scraped_at DESC`.
