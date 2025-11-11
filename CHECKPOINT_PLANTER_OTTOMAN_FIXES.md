# Checkpoint: Planter Search & Ottoman Placement Fixes

**Date**: 2025-11-11
**Session**: Planter keyword extraction and ottoman placement debugging

---

## Summary

Fixed three critical bugs:
1. UI text incorrectly referencing "panel below" instead of right panel
2. Ottoman furniture replacing sofas instead of being placed in front
3. Planter searches returning mixed furniture categories (sofas, beds, chairs) instead of only planters

---

## Issues Fixed

### 1. UI Text Correction
**Issue**: Conversational response said "check them out in the panel below!" but products panel is on the right side.

**Fix**: Updated text in `/Users/sahityapandiri/Omnishop/api/routers/chat.py:193`
```python
# Changed from:
"check them out in the panel below!"
# To:
"check them out in the Products panel!"
```

**Status**: ✅ Complete

---

### 2. Ottoman Placement Bug
**Issue**: When adding ottoman to canvas with existing sofa, the ottoman was replacing the sofa instead of being placed in front of it.

**Root Cause**: Product name "Lumo Sofa Ottoman" was classified as 'sofa' (replaceable) instead of 'ottoman' (additive-only) because furniture type extraction checked 'sofa' before 'ottoman'.

**Fixes**:

#### 2a. Furniture Type Classification
File: `/Users/sahityapandiri/Omnishop/api/routers/chat.py:883-889`

Reordered checks to handle ottoman BEFORE sofa:
```python
def _extract_furniture_type(product_name: str) -> str:
    """Extract furniture type from product name with specific table categorization"""
    name_lower = product_name.lower()

    # Check ottoman FIRST (before sofa) to handle "Sofa Ottoman" products correctly
    if 'ottoman' in name_lower:
        return 'ottoman'
    elif 'sofa' in name_lower or 'couch' in name_lower or 'sectional' in name_lower:
        return 'sofa'
```

#### 2b. Gemini Placement Instructions
File: `/Users/sahityapandiri/Omnishop/api/services/google_ai_service.py:636-641`

Added explicit ottoman placement instructions:
```python
🔲 OTTOMAN:
- Place DIRECTLY IN FRONT OF the sofa, similar to a coffee table
- Can be centered or slightly offset based on room layout
- Should be 14-18 inches from sofa's front edge
- Ottomans are used as footrests or extra seating, NOT as sofa replacements
- ⚠️ NEVER remove or replace the sofa when adding an ottoman
```

**Status**: ✅ Complete

---

### 3. Planter Search Returns Wrong Products
**Issue**: Searching "suggest nice planters" or "suggest nice plants" returned 30 mixed products (sofas, chairs, tables, beds) instead of only planter products.

**Root Cause**: TWO-LAYER BUG:

#### Layer 1: Missing Keyword Patterns
Planter/plants keywords were not in extraction patterns.

**Fix 3a**: Added patterns to `/Users/sahityapandiri/Omnishop/api/routers/chat.py:1045-1048`
```python
('planter', ['planter', 'pot', 'plant pot', 'flower pot'], {}),
('planters', ['planter', 'pot', 'plant pot', 'flower pot'], {}),
('plants', ['planter', 'pot', 'plant pot', 'flower pot'], {}),
('plant', ['planter', 'pot', 'plant pot', 'flower pot'], {}),
```

**Fix 3b**: Added to decor category in `/Users/sahityapandiri/Omnishop/api/services/recommendation_engine.py:396`
```python
'decor': ['mirror', 'rug', 'carpet', 'mat', 'planter', 'pot', 'vase'],
```

#### Layer 2: Variable Passing Bug
Empty `product_keywords` variable passed to RecommendationRequest instead of populated `user_preferences['product_keywords']`.

**Fix 3c**: Fixed keyword retrieval in `/Users/sahityapandiri/Omnishop/api/routers/chat.py:1410-1420`
```python
# Create recommendation request
# IMPORTANT: Use keywords from user_preferences, not the local product_keywords variable
# because the fallback logic stores the final keywords in user_preferences['product_keywords']
final_product_keywords = user_preferences.get('product_keywords', product_keywords) or []

recommendation_request = RecommendationRequest(
    user_preferences=user_preferences,
    room_context=room_context,
    budget_range=budget_range,
    style_preferences=style_preferences,
    functional_requirements=functional_requirements,
    product_keywords=final_product_keywords,  # Changed from product_keywords
    max_recommendations=limit,
```

#### Layer 3: CRITICAL INDENTATION BUG
Regex fallback code was OUTSIDE the else block, causing it to ALWAYS execute and overwrite correctly extracted keywords with empty values.

**Fix 3d**: Fixed indentation in `/Users/sahityapandiri/Omnishop/api/routers/chat.py:1352-1374`

**BEFORE** (BUGGY):
```python
if product_keywords:
    user_preferences['product_keywords'] = product_keywords
    logger.info(f"Using extracted product keywords: {product_keywords}")
else:
    import re
    furniture_pattern = r'\b(sofa|table|...)\b'

# THIS WAS OUTSIDE THE ELSE - ALWAYS RAN!
if session_id:
    context = chatgpt_service.get_conversation_context(session_id)
    # ... overwrites keywords
```

**AFTER** (FIXED):
```python
if product_keywords:
    user_preferences['product_keywords'] = product_keywords
    logger.info(f"Using extracted product keywords: {product_keywords}")
else:
    import re
    furniture_pattern = r'\b(sofa|table|...)\b'

    # NOW PROPERLY INDENTED - ONLY RUNS IN ELSE BRANCH
    if session_id:
        context = chatgpt_service.get_conversation_context(session_id)
        # ... only runs if product_keywords was empty
```

**Status**: ✅ Complete

---

## Technical Details

### Keyword Extraction Flow
The system has TWO paths for keyword extraction:

**Path 1**: ChatGPT provides `product_matching_criteria` with `product_types`
- Used for queries like "beige sofas"
- Structured output from ChatGPT analysis

**Path 2**: Fallback extraction using `_extract_product_keywords()` and regex patterns
- Used when ChatGPT doesn't provide structured keywords
- Pattern matching against known furniture types
- Used for planter searches

### The Bug Chain
1. User searches "suggest nice planters"
2. `_extract_product_keywords()` correctly extracts: `['planter', 'pot', 'plant pot', 'flower pot']`
3. Keywords stored in `user_preferences['product_keywords']`
4. **BUG**: Regex fallback code (outside else) runs and overwrites with empty values
5. Empty array passed to recommendation engine
6. Engine returns generic products without filtering

### The Fix
Proper indentation ensures regex fallback ONLY runs when `product_keywords` is empty, preserving the correctly extracted keywords.

---

## Debug Logging Added

Enhanced logging throughout the keyword extraction and recommendation pipeline:

### `/Users/sahityapandiri/Omnishop/api/routers/chat.py`
- Line 1246: Entry point logging
- Lines 1035-1056: Keyword extraction debug logs
- Lines 1407-1409: Pre-request logging with all parameters
- Lines 1431-1432: Post-request logging

### `/Users/sahityapandiri/Omnishop/api/services/recommendation_engine.py`
- Line 426: Candidate products debug logging
- Keyword filtering trace logs

---

## Files Modified

1. `/Users/sahityapandiri/Omnishop/api/routers/chat.py`
   - Line 193: UI text fix
   - Lines 883-889: Ottoman classification fix
   - Lines 1045-1048: Planter keyword patterns
   - Lines 1352-1374: CRITICAL indentation fix
   - Lines 1410-1420: Keyword variable fix
   - Multiple debug log additions

2. `/Users/sahityapandiri/Omnishop/api/services/google_ai_service.py`
   - Lines 636-641: Ottoman placement instructions

3. `/Users/sahityapandiri/Omnishop/api/services/recommendation_engine.py`
   - Line 396: Added planter to decor category
   - Line 426: Debug logging

---

## Testing

### Expected Behavior After Fixes

#### Ottoman Placement
1. Search "ottoman for living room"
2. Select ottoman product
3. Add to canvas with existing sofa
4. **Result**: Ottoman placed IN FRONT of sofa (not replacing it)

#### Planter Search
1. Search "suggest nice planters" or "suggest nice plants"
2. **Expected keywords extracted**: `['planter', 'pot', 'plant pot', 'flower pot']`
3. **Expected products**: Only planter/pot products (~11 in database)
4. **Expected log sequence**:
   ```
   [EXTRACT DEBUG] _extract_product_keywords returned: ['planter', 'pot', 'plant pot', 'flower pot']
   Using extracted product keywords: ['planter', 'pot', 'plant pot', 'flower pot']
   [PLANTER DEBUG] user_preferences['product_keywords']: ['planter', 'pot', 'plant pot', 'flower pot']
   [RECOMMENDATION DEBUG] final_product_keywords=['planter', 'pot', 'plant pot', 'flower pot']
   [CANDIDATE PRODUCTS DEBUG] request.product_keywords = ['planter', 'pot', 'plant pot', 'flower pot']
   ```

---

## Key Learnings

1. **Python Indentation Matters**: A subtle indentation error caused code to always execute, overwriting correct values
2. **Two-Path Systems Need Consistent Variables**: Path 1 and Path 2 must store results in same location for downstream consumption
3. **Order Matters in Classification**: Check more specific terms (ottoman) before general terms (sofa)
4. **Comprehensive Logging is Essential**: Multi-stage logging revealed the exact point where keywords were lost

---

## Server Status
- API server: Auto-reloaded with fixes at port 8000
- Frontend: Running at localhost:3000
- All fixes are live and ready for testing
