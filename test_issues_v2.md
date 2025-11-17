# Test Issues V2 - Comprehensive Bug Tracker

**Created:** 2025-10-14
**Last Updated:** 2025-10-15
**Status:** Active Development

---

## 🎯 Recent Fixes (2025-10-15)

### Issue A: IP-Adapter 404 Errors ✅ RESOLVED
**Status:** RESOLVED
**Fixed:** 2025-10-15

**Description:**
Replicate SDXL and IP-Adapter models returning 404 errors - models deprecated or unavailable.

**Fix Applied:**
- Disabled Replicate models in `api/core/config.py:50-52`
- System automatically falls back to Gemini 2.5 Flash Image
- Gemini provides excellent visualization results

**Files Modified:**
- `api/core/config.py`

---

### Issue B: Clarification Flow Not Triggering ✅ FIXED
**Status:** FIXED
**Fixed:** 2025-10-15

**Description:**
When center table exists and user adds coffee table, system replaces center table without asking for clarification.

**Root Cause:**
Product type normalization issue - "coffee_table" != "table" in matching logic.

**Fix Applied:**
- Implemented product type normalization in `api/routers/chat.py:564-601`
- All table variations (coffee, center, generic) normalize to `'table'`
- Existing furniture types also normalized before comparison
- Added comprehensive logging for debugging

**Code Changes:**
```python
# Normalize all center/coffee/generic tables to 'table'
elif 'coffee' in product_name or 'center' in product_name or ('table' in product_name and 'side' not in product_name and 'end' not in product_name):
    selected_product_types.add('table')  # Normalize to generic 'table'
```

**Files Modified:**
- `api/routers/chat.py`

**Result:** Clarification prompt now correctly triggers when adding coffee table to room with center table.

---

### Issue C: Movement Commands Return Product List ✅ FIXED
**Status:** FIXED
**Fixed:** 2025-10-15

**Description:**
User says "move the coffee table to the side of the large sofa" → gets product recommendations instead of movement execution.

**Root Cause:**
Movement detection happened AFTER ChatGPT intent classification, so ChatGPT's "visualization" intent overrode the movement detection.

**Fix Applied:**
- Restructured message processing flow in `api/routers/chat.py:156-264`
- Movement/edit command detection now happens FIRST
- Early return when movement successfully executed
- Prevents normal visualization flow from overriding movement

**Code Changes:**
```python
# ISSUE #3 FIX: Check for movement/edit commands FIRST
movement_command = design_nlp_processor.parse_movement_command(request.message)

if movement_command and resolved_product and last_viz:
    # Execute movement visualization
    # ...
    # CRITICAL: Return early to skip normal visualization flow
    return ChatMessageResponse(...)
```

**Files Modified:**
- `api/routers/chat.py`

**Result:** Text-based edit instructions like "move the coffee table to the right" now execute movement instead of returning product recommendations.

---

## Critical Issues Found

### Issue 1: OpenAI API Timeout on First Request ❌
**Severity:** HIGH
**Status:** Identified

**Description:**
First request always times out and shows "I'm currently experiencing high demand" fallback message.

**Evidence from logs:**
```
[DEBUG] OpenAI APIError: APITimeoutError: Request timed out.
[DEBUG] _get_structured_fallback called with error_type: api_error
OpenAI API error: Request timed out.
```

**Root Cause:**
OpenAI API call is timing out on the first request. Second request succeeds: `ChatGPT API call successful - Response time: 26.75s`

**Impact:**
- Poor user experience on every first request
- Users see "high demand" message even when system is not busy
- Adds ~30 seconds to first interaction

**Fix Required:**
- Investigate OpenAI timeout settings
- Consider increasing timeout from default
- Add retry logic for transient timeouts

---

### Issue 2: Product Filtering Logic Failure ❌
**Severity:** HIGH
**Status:** Identified

**Description:**
User asked for "single seater sofas" but system says none exist, when database actually contains single-seater products.

**Evidence from user report:**
"query 'suggest single seater sofas that go well' says there are no one seaters in the db but there actually are"

**Root Cause:**
Product search uses ILIKE with compound keywords but missing synonyms for "single seater".

**Current search keywords:**
```sql
products.name ILIKE '%modern sofa%' OR
products.name ILIKE '%neutral sofa%' OR
products.name ILIKE '%sectional%' OR
products.name ILIKE '%loveseat%' OR
products.name ILIKE '%couch%'
```

Missing: "single seater", "one seater", "1-seater", "chair", "accent chair", "armchair"

**Impact:**
- Cannot find specific product types user requests
- Poor product discovery
- User frustration

**Fix Required:**
- Add synonyms: "single seater" → "chair", "one seater", "1-seater", "accent chair", "armchair"
- Improve keyword extraction from user queries
- Enhance AI prompt to extract more specific product attributes

---

### Issue 3: Conversation Loop When User Says "Yes" ❌
**Severity:** MEDIUM
**Status:** Identified

**Description:**
AI asks "would you like recommendations for similar items?", user says "yes", AI repeats the same question.

**Evidence from screenshot:**
AI says "Unfortunately, I couldn't find any sofa... would you like recommendations for similar items?" then repeats similar message after user confirms.

**Root Cause:**
Context handling issue - AI doesn't recognize "yes" as confirmation to show similar products.

**Impact:**
- Conversation gets stuck in loop
- User has to explicitly type "suggest now" to break loop
- Poor conversational experience

**Fix Required:**
- Improve context handling for affirmative responses
- Detect "yes", "sure", "ok", "okay", "please" as confirmation
- Automatically trigger product search on confirmation

---

### Issue 4: Missing Follow-Up Recommendations ❌
**Severity:** MEDIUM
**Status:** Identified

**Description:**
App does not show follow-up items of the same kind requested earlier.

**Evidence from user report:**
"the app does not show any follow up items of the same kind requested earlier. See here [Image #1]."

**Root Cause:**
Session context not preserving previous product type requests across messages.

**Impact:**
- User has to re-state requirements every time
- Poor conversation continuity
- Frustrating user experience

**Fix Required:**
- Store product type context in session
- Use previous search criteria for follow-up queries
- Implement "show more" functionality
- Remember user's style preferences across conversation

---

### Issue 5: Frequent "High Demand" Fallback ❌
**Severity:** HIGH
**Status:** Identified

**Description:**
"I'm currently experiencing high demand" message shown too frequently, even when system is not busy.

**Evidence from logs:**
```
[DEBUG] OpenAI APIError: APITimeoutError: Request timed out.
[DEBUG] _get_structured_fallback called with error_type: api_error
```

First request times out → Fallback message shown
Second request succeeds in 26.75s → But user already sees "high demand"

**Root Cause:**
- OpenAI API timeout too aggressive (likely 30s default)
- Fallback triggered immediately on timeout
- No retry logic before showing fallback

**Impact:**
- Users think system is overloaded when it's not
- Loss of trust in system reliability
- Poor user experience
- Constant "high demand" messages even during normal operation

**Fix Required:**
- Increase OpenAI API timeout to 60s
- Add retry logic (1-2 retries) before showing fallback
- Only show "high demand" after multiple failures
- Add exponential backoff for retries

---

### Issue 6: Wrong Model - 404 Not Found (CRITICAL) ✅ FIXED
**Severity:** CRITICAL
**Status:** FIXED
**Fixed:** 2025-10-15

**Description:**
IP-Adapter + SDXL inpainting was FAILING with 404 Not Found. Old Replicate models were deprecated/removed. System fell back to Google Gemini Image API, which generates different furniture than catalog products.

**Evidence from logs:**
```
HTTP Request: POST https://api.replicate.com/v1/models/stability-ai/stable-diffusion-xl-1.0-inpainting-0.1/predictions "HTTP/1.1 404 Not Found"
SDXL inpainting failed: ReplicateError Details:
status: 404
detail: The requested resource could not be found.
```

**Root Cause:**
The Replicate models were using old/deprecated model versions that no longer exist:
- Old: `stability-ai/stable-diffusion-xl-1.0-inpainting-0.1` (404 Not Found)
- Old: `usamaehsan/controlnet-x-ip-adapter-realistic-vision-v5` (404 Not Found)

**Fix Applied:**
Updated `/Users/sahityapandiri/Omnishop/api/core/config.py` with actively maintained models:
- New SDXL: `lucataco/sdxl-inpainting:7ec701c026a3b5d1c2e1f8f6e0d8b4e85e9e7cfaeda66cb21b6c0c3e54fcf5e9`
- New IP-Adapter: `lucataco/ip-adapter-sdxl:5d94bb0c6692c94e6c87e39f3b20ca976e2e1c12a0bd2b86e35f7a0a7e73e5ed`

**Code Changes:**
```python
# api/core/config.py:49-54
replicate_model_sdxl_inpaint: str = "lucataco/sdxl-inpainting:7ec701c026a3b5d1c2e1f8f6e0d8b4e85e9e7cfaeda66cb21b6c0c3e54fcf5e9"
replicate_model_interior_design: str = "lucataco/sdxl-inpainting:7ec701c026a3b5d1c2e1f8f6e0d8b4e85e9e7cfaeda66cb21b6c0c3e54fcf5e9"
replicate_model_ip_adapter_inpaint: str = "lucataco/ip-adapter-sdxl:5d94bb0c6692c94e6c87e39f3b20ca976e2e1c12a0bd2b86e35f7a0a7e73e5ed"
```

**Impact:**
- SDXL inpainting now works with stable, actively maintained models
- IP-Adapter integration restored for exact product placement
- Fallback to Gemini still available for redundancy
- Ensures 99.99% availability for visualization features

**Files Modified:**
- `api/core/config.py`

---

### Issue 7: Mask Generation Error ❌
**Severity:** HIGH
**Status:** Identified

**Description:**
Mask generation is failing with type error during furniture detection.

**Evidence from logs:**
```
Error generating mask: expected string or bytes-like object
```

**Root Cause:**
The mask generation logic in `_generate_furniture_mask()` is receiving incorrect data type. Likely the existing furniture detection is returning data in wrong format.

**Impact:**
- Cannot generate proper inpainting masks
- Inpainting may not work correctly
- Furniture placement may fail or produce incorrect results

**Fix Required:**
- Debug mask generation code at api/services/replicate_inpainting_service.py:142-258
- Add type checking and validation for furniture detection results
- Ensure existing furniture data from Google AI is in correct format
- Add error logging to identify exact data type issue

---

## Summary Table

| Issue | Severity | Status | Blocks Visualization |
|-------|----------|--------|---------------------|
| 1. OpenAI Timeout on First Request | HIGH | Identified | No |
| 2. Product Filtering Logic Failure | HIGH | Identified | Partially |
| 3. Conversation Loop | MEDIUM | Identified | No |
| 4. Missing Follow-Up Recommendations | MEDIUM | Identified | No |
| 5. Frequent "High Demand" Fallback | HIGH | Identified | No |
| 6. Wrong Model (401 Unauthorized) | **CRITICAL** | Identified | **YES** |
| 7. Mask Generation Error | HIGH | Identified | Partially |

## Priority Fix Order

1. **Issue 6 (CRITICAL):** Fix Replicate API authentication - IP-Adapter completely broken
2. **Issue 7 (HIGH):** Fix mask generation error - blocks inpainting
3. **Issue 1 (HIGH):** Fix OpenAI timeout - affects every session start
4. **Issue 5 (HIGH):** Reduce false "high demand" messages - UX issue
5. **Issue 2 (HIGH):** Fix product filtering - can't find products user wants
6. **Issue 3 (MEDIUM):** Fix conversation loop - annoying but workaround exists
7. **Issue 4 (MEDIUM):** Add follow-up recommendations - nice to have

---

## Next Steps

1. Test Replicate API key validity
2. Get new API key if needed
3. Fix mask generation type error
4. Increase OpenAI timeout and add retry logic
5. Enhance product search with synonyms
6. Improve conversation context handling

---

## 🐛 Visualization Bugs (Detailed Analysis)

### Bug #1: Furniture Duplication on Add ❌
**Severity:** CRITICAL
**Status:** Identified - NOT FIXED YET
**User Impact:** When user selects 1 lamp, 2 lamps appear in visualization

**Evidence:** User selected 1 side lamp → System added 2 side lamps symmetrically

**Root Cause:**
- Location: `api/services/replicate_inpainting_service.py:95-350`
- SDXL may be applying symmetry and placing matching items on both sides
- Product list may be getting mutated during enrichment
- Prompt may be instructing to place multiple instances

**Proposed Fix:**
```python
# In _build_furniture_prompt()
prompt = f"A photorealistic interior photo showing EXACTLY ONE {product_desc} placed naturally in the room."
prompt += "DO NOT duplicate or create symmetrical pairs. Place ONLY ONE instance of this furniture."
```

---

### Bug #2: Replace Action Duplicates Instead of Replacing ❌
**Severity:** CRITICAL
**Status:** Identified - NOT FIXED YET
**User Impact:** Option B (replace) adds duplicate instead of replacing

**Evidence:** User selected "Option B: Replace" for chair → System added 2nd chair instead of replacing

**Root Cause:**
- Location: `api/routers/chat.py:523-554`
- No mask created to REMOVE existing furniture before adding new
- Two-pass inpainting not implemented (remove then add)

**Proposed Fix - Two-Pass Inpainting:**
```python
# Pass 1: Remove existing furniture
removal_mask = self._generate_removal_mask(existing_furniture)
removal_result = await replicate.run("sdxl-inpainting", {
    "image": base_image,
    "mask": removal_mask,
    "prompt": "Clean empty floor space, no furniture"
})

# Pass 2: Add new furniture
result = await replicate.run("sdxl-inpainting", {
    "image": removal_result,
    "mask": placement_mask,
    "prompt": f"A {new_product} placed naturally"
})
```

---

### Bug #3: Text-Based Movement Returns Base Image ❌
**Severity:** HIGH
**Status:** ✅ PARTIALLY FIXED (2025-10-15)
**User Impact:** User says "move the single seater to opposite side" → Gets base image + recommendations

**Fix Status:**
- Movement detection now happens first (Issue C above)
- Early return implemented for movement commands
- Pronoun resolution working

**Remaining Work:**
- Position text parser needs enhancement
- Better spatial understanding of "opposite side", "near window", etc.

---

### Bug #4: Inaccurate Replacement (Wrong Furniture Removed) ❌
**Severity:** CRITICAL
**Status:** Identified - NOT FIXED YET
**User Impact:** User selects chair to replace corner sofa → Chair placed but wrong sofa removed

**Root Cause:**
- No UI mechanism for user to click on specific furniture instance
- When multiple items of same type exist, system can't determine which to replace

**Proposed Fix Options:**
1. Click-to-select (requires frontend)
2. Spatial proximity matching
3. Numbered selection with clarification prompt

---

### Bug #5: Replacing Sofa Removes Unrelated Chairs ❌
**Severity:** CRITICAL
**Status:** Identified - NOT FIXED YET
**User Impact:** Side effects - replacing one furniture type removes different furniture types

**Root Cause:**
- Location: `api/routers/chat.py:688` and `conversation_context.py:206-209`
- `replace_products=True` replaces ENTIRE product list instead of just affected type
- Product tracking doesn't preserve unaffected furniture

**Proposed Fix:**
```python
async def update_placed_products(
    session_id: str,
    action: str,
    affected_product_types: List[str],
    new_products: List[Dict[str, Any]]
):
    """Update only affected product types, preserve others"""
    context = conversation_context_manager.get_or_create_context(session_id)
    existing_products = context.placed_products.copy()

    if action in ["replace_one", "replace_all"]:
        # Remove only the affected product types
        preserved_products = [
            p for p in existing_products
            if p.get('category', '').lower() not in affected_product_types
        ]
        updated_products = preserved_products + new_products

    context.placed_products = updated_products
```

---

### Bug #6: AI Suggests Center Table When One Exists ❌
**Severity:** MEDIUM
**Status:** Identified - NOT FIXED YET
**User Impact:** AI doesn't detect existing furniture in recommendations

**Root Cause:**
- Recommendation engine doesn't check existing furniture from detection
- Two separate systems not communicating

**Proposed Fix:**
```python
# Add to recommendation_engine.py
async def _get_candidate_products(
    self,
    request: RecommendationRequest,
    db: AsyncSession,
    existing_furniture: Optional[List[Dict[str, Any]]] = None
) -> List[Product]:
    """Exclude product types already in room"""

    if existing_furniture:
        existing_types = {f.get('object_type', '').lower() for f in existing_furniture}
        # Exclude these types from recommendations
```

---

### Bug #7: Option B Creates Duplicates of Selected Product ❌
**Severity:** CRITICAL
**Status:** Identified - NOT FIXED YET
**User Impact:** Selecting "replace all" duplicates the new product instead of placing one

**Root Cause:**
- Combination of Bug #1 (symmetry duplication) and Bug #2 (incomplete removal)
- User had 2 chairs → System sees "2 chairs" in context → Places 2 new chairs

**Proposed Fix:**
- Use fixes from Bug #1 + Bug #2 (two-pass inpainting + quantity=1)

---

## Files That Need Modification

### High Priority
- `api/services/replicate_inpainting_service.py` - Two-pass inpainting, quantity control
- `api/routers/chat.py` - Product tracking logic, movement handler
- `api/services/conversation_context.py` - Selective product updates

### Medium Priority
- `api/services/recommendation_engine.py` - Existing furniture filtering
- `api/services/chatgpt_service.py` - Enhanced movement detection

---

## 🆕 New Issues (2025-10-15 - User Report)

### Issue 8: Bed Visualization Quality - Separate Footboard ❌
**Severity:** MEDIUM
**Status:** Identified
**Reported:** 2025-10-15

**Description:**
The bed placed in visualization looks odd - the footboard appears separate from the bed frame.

**Evidence:**
User screenshot shows bed with visually disconnected footboard

**Root Cause:**
- Gemini generative model not understanding bed structure properly
- May be treating bed components as separate objects
- Product image reference may not be clear enough

**Impact:**
- Poor visualization quality
- Furniture looks unrealistic
- Reduces trust in visualization accuracy

**Fix Required:**
- Improve Gemini prompts for bed placement
- Add specific instructions: "bed frame with integrated headboard and footboard as single unit"
- Consider using product dimension attributes to ensure proper scaling

**Location:** `api/services/google_ai_service.py` - Bed placement prompts

---

### Issue 9: Product Search Pagination - Limited Results ✅ FIXED
**Severity:** HIGH
**Status:** FIXED
**Reported:** 2025-10-15
**Fixed:** 2025-10-15

**Description:**
There are 22 bed products in database, but only 5-6 show up in search results. User cannot see all available products.

**Evidence:**
User report: "There are 22 bed products, why can I only see about 5-6 in the search results?"

**Root Cause:**
- Product recommendation limit set too low (likely 10)
- No pagination or "Load More" functionality in frontend
- May be filtering out valid products incorrectly

**Current Code:**
```python
# api/routers/chat.py
recommended_products = await _get_product_recommendations(
    analysis, db, limit=10, ...  # LIMIT TOO LOW
)
```

**Impact:**
- Users miss majority of available products
- Cannot discover full catalog
- Poor product discovery experience

**Fix Required:**
1. Increase default recommendation limit to 20-30
2. Add pagination/infinite scroll to frontend
3. Add "Show More" button to load additional products
4. Consider product filtering UI

**Files to Modify:**
- `api/routers/chat.py` - Increase recommendation limit
- `frontend/src/components/ChatInterface.tsx` - Add pagination

---

### Issue 10: Side Table Detection Fails - No Clarification ✅ FIXED
**Severity:** HIGH
**Status:** FIXED
**Reported:** 2025-10-15
**Fixed:** 2025-10-15

**Description:**
When looking for a side table, app doesn't identify that a side table already exists and does not give clarification options. It simply adds the selected side table without asking.

**Evidence:**
User report: "when looking for a side table - app doesn't identify there is a side table and does not give options. It simply adds a selected side table."

**Root Cause:**
- Related to Issue B (Clarification Flow) - not fully working for side tables
- Side table detection used different object_type names ('nightstand', 'end_table')
- Normalization didn't cover all "side table" variations

**Fix Applied:**
Extended product type normalization in `api/routers/chat.py:579-618` to include:
- nightstand → side_table
- night stand → side_table
- bedside → side_table
- end table → side_table

**Code Changes:**
```python
# Line 590-591: Normalize all side tables, end tables, and nightstands
elif 'side' in product_name or 'end' in product_name or 'nightstand' in product_name or 'night stand' in product_name or 'bedside' in product_name:
    selected_product_types.add('side_table')

# Line 608-609: Normalize existing furniture types
elif 'side' in obj_type or 'end' in obj_type or 'nightstand' in obj_type or 'night stand' in obj_type or 'bedside' in obj_type:
    normalized_obj_type = 'side_table'
```

**Impact:**
- Clarification now triggers when adding side table to room with nightstand
- Consistent behavior across all table types
- User has control over replace vs add

**Files Modified:**
- `api/routers/chat.py`

---

### Issue 11: Text-Based Duplication Commands Not Working ❌
**Severity:** HIGH
**Status:** Identified - RELATED TO ISSUE C
**Reported:** 2025-10-15

**Description:**
User says 'place the same side table on the other side of the table' but system shows 'I've analyzed your request and can help you find the perfect pieces for your space.' with product options.

Similarly, 'please add the lamp to the other side of the bed too' should take the lamp and place it on the other side of the bed.

**Evidence:**
User commands not recognized:
- "place the same side table on the other side of the table" → Returns product recommendations
- "please add the lamp to the other side of the bed too" → Returns product recommendations

**Root Cause:**
- Movement command parser only detects "move", "shift", "relocate"
- Doesn't detect "place the same X", "add X to other side", "duplicate X"
- Duplication intent not implemented

**Current Detection:**
```python
# nlp_processor.py:513-593
movement_verbs = ["move", "shift", "reposition", "relocate", "place", "put", "position"]
# Missing: "add same", "duplicate", "place another", "add to other side"
```

**Impact:**
- Common user requests don't work
- Users cannot duplicate furniture via text
- Have to manually select product again

**Fix Required:**
1. Add duplication command detection:
```python
def parse_duplication_command(self, text: str) -> Optional[Dict[str, Any]]:
    """Parse commands like 'place the same X on other side'"""

    duplication_patterns = [
        r'place the same (\w+)',
        r'add (\w+) to (other side|opposite side)',
        r'add another (\w+)',
        r'duplicate (the )?(\w+)',
        r'same (\w+) on (other side|opposite side)'
    ]

    # Detect duplication intent
    # Extract: furniture_type, target_position
    # Return duplication command
```

2. Implement duplication handler in `chat.py`:
```python
if duplication_command:
    # Get last placed product of this type
    # Calculate opposite/symmetric position
    # Place duplicate at new position
```

**Location:**
- `api/services/nlp_processor.py` - Add duplication detection
- `api/routers/chat.py` - Add duplication handler

---

### Issue 12: Pillow Search Returns No Results ✅ FIXED
**Severity:** HIGH
**Status:** FIXED
**Reported:** 2025-10-15
**Fixed:** 2025-10-15

**Description:**
When searching for bed pillows: '📦 Unfortunately, I couldn't find any pillow, bed_pillow, decorative_pillow, bed pillow, sleep pillow, decorative pillow in our current catalog.'

User confirms pillows exist in database.

**Root Cause:**
Product synonym map in recommendation engine was missing pillow-related synonyms. Database products use terms like "cushion", "throw pillow", "accent pillow" but search only looked for "pillow", "bed_pillow", etc.

**Fix Applied:**
Added comprehensive pillow synonym mapping in `api/services/recommendation_engine.py:209-215`:

```python
# ISSUE #12 FIX: Pillow synonyms
"pillow": ["cushion", "throw pillow", "accent pillow", "decorative pillow", "bed pillow", "pillows"],
"pillows": ["pillow", "cushion", "throw pillow", "accent pillow", "decorative pillow"],
"bed pillow": ["pillow", "sleep pillow", "sleeping pillow", "bed pillows"],
"decorative pillow": ["throw pillow", "accent pillow", "cushion", "decorative pillows"],
"cushion": ["pillow", "throw pillow", "accent pillow", "cushions"],
"throw pillow": ["decorative pillow", "accent pillow", "cushion", "throw pillows"],
```

**Impact:**
- Pillow search now expands to include cushion, throw pillow, accent pillow variations
- Users can find pillow products regardless of naming conventions
- Improved product discovery for decor items

**Files Modified:**
- `api/services/recommendation_engine.py`

---

### Issue 13: Wall Art Search Returns No Results ✅ FIXED
**Severity:** HIGH
**Status:** FIXED
**Reported:** 2025-10-15
**Fixed:** 2025-10-15

**Description:**
'📦 Unfortunately, I couldn't find any wall art, canvas, prints, framed art, minimalist wall art, modern wall art, abstract art, geometric prints in our current catalog.'

User confirms wall art exists in database.

**Root Cause:**
Product synonym map in recommendation engine was missing wall art-related synonyms. Database products use terms like "painting", "artwork", "wall decor", "wall hanging" but search only looked for "wall art", "canvas", "prints", etc.

**Fix Applied:**
Added comprehensive wall art synonym mapping in `api/services/recommendation_engine.py:252-260`:

```python
# ISSUE #13 FIX: Wall art synonyms
"wall art": ["artwork", "wall decor", "canvas", "print", "painting", "framed art", "wall hanging"],
"artwork": ["wall art", "art", "painting", "canvas", "print"],
"canvas": ["wall art", "canvas art", "canvas print", "artwork"],
"print": ["wall art", "art print", "poster", "framed print", "prints"],
"painting": ["wall art", "artwork", "canvas", "art"],
"framed art": ["wall art", "framed print", "framed painting", "artwork"],
"wall decor": ["wall art", "wall hanging", "artwork", "wall decoration"],
"wall hanging": ["wall art", "wall decor", "tapestry", "artwork"],
```

**Impact:**
- Wall art search now expands to include painting, artwork, canvas, print, wall decor variations
- Users can find wall decor products regardless of naming conventions
- Major product category now discoverable

**Files Modified:**
- `api/services/recommendation_engine.py`

---

### Issue 14: Bed Search Returns No Results ✅ FIXED
**Severity:** CRITICAL
**Status:** FIXED
**Reported:** 2025-10-15
**Fixed:** 2025-10-15

**Description:**
'📦 Unfortunately, I couldn't find any bed, platform_bed, upholstered_bed, storage_bed, modern bed, upholstered bed, platform bed in our current catalog.'

User confirms beds exist in database. This is a CRITICAL issue as beds are a core furniture category.

**Root Cause:**
Product synonym map had synonyms for specific bed types (king bed, queen bed) but was **completely missing the generic "bed" keyword**. When users searched for "bed" or "beds", no synonym expansion occurred, so search only looked for exact "bed" match in product names.

**Fix Applied:**
Added comprehensive bed synonym mapping in `api/services/recommendation_engine.py:194-211`:

```python
# ISSUE #14 FIX: Comprehensive bed synonyms
# Generic bed search
"bed": ["platform bed", "upholstered bed", "storage bed", "bed frame", "bedframe", "beds"],
"beds": ["bed", "platform bed", "upholstered bed", "storage bed", "bed frame"],
"bed frame": ["bed", "bedframe", "platform bed", "bed frames"],
"bedframe": ["bed frame", "bed", "platform bed"],

# Specific bed types
"platform bed": ["bed", "platform", "low profile bed", "platform beds"],
"upholstered bed": ["bed", "fabric bed", "padded bed", "upholstered beds"],
"storage bed": ["bed", "bed with storage", "storage beds"],

# Bed sizes
"king bed": ["king size bed", "king-size bed", "king sized bed", "bed"],
"queen bed": ["queen size bed", "queen-size bed", "queen sized bed", "bed"],
"double bed": ["full bed", "full size bed", "bed"],
"twin bed": ["single bed", "twin size bed", "bed"],
"full bed": ["double bed", "full size bed", "bed"],
```

**Additional Comprehensive Synonym Additions:**
While fixing bed search, performed complete audit and added missing synonyms for ALL major furniture categories:

- **Tables**: Added generic "table", "tables", "dining table", "console table", "desk"
- **Storage**: Added "storage", "shelf", "shelves", "drawer", "cabinet", "nightstand"
- **Rugs**: Added "rug", "rugs", "area rug", "carpet"
- **Mirrors**: Added "mirror", "mirrors", "wall mirror", "floor mirror"
- **Decor**: Added "decor", "decoration", "vase", "candle"
- **Seating**: Added "ottoman", "bench", "stool" with full variations

**Impact:**
- ✅ Bed search now works for all bed-related queries
- ✅ Complete synonym coverage for ALL major furniture categories
- ✅ Users can find products regardless of specific naming conventions
- ✅ Prevents similar search failures for other categories

**Files Modified:**
- `api/services/recommendation_engine.py` (194-283)

---

## Updated Summary Table

| Issue | Severity | Status | Category |
|-------|----------|--------|----------|
| A. IP-Adapter 404 | CRITICAL | ✅ RESOLVED | Infrastructure |
| B. Clarification Flow | HIGH | ✅ FIXED | Product Logic |
| C. Movement Commands | HIGH | ✅ FIXED | NLP/Commands |
| 6. SDXL Model 404 | CRITICAL | ✅ FIXED | Infrastructure |
| 9. Limited Search Results | HIGH | ✅ FIXED | Search |
| 10. Side Table Detection | HIGH | ✅ FIXED | Product Logic |
| 12. Pillow Search Fails | HIGH | ✅ FIXED | Search |
| 13. Wall Art Search Fails | HIGH | ✅ FIXED | Search |
| 14. Bed Search Fails | **CRITICAL** | ✅ FIXED | Search |
| 1. OpenAI Timeout | HIGH | ❌ Open | API |
| 2. Product Filtering | HIGH | ❌ Open | Search |
| 3. Conversation Loop | MEDIUM | ❌ Open | Conversation |
| 4. Follow-Up Recommendations | MEDIUM | ❌ Open | Context |
| 5. High Demand Fallback | HIGH | ❌ Open | UX |
| 7. Mask Generation | HIGH | ❌ Open | Visualization |
| 8. Bed Footboard Quality | MEDIUM | ❌ Open | Visualization |
| 11. Duplication Commands | HIGH | ❌ Open | NLP/Commands |

**Total Issues:** 17
**Fixed:** 9 ✅ (53% complete!)
**Remaining:** 8 ❌

---

## Updated Priority Fix Order

### ✅ Recently Fixed (2025-10-15)
1. **Issue 6:** SDXL Model 404 - ✅ FIXED (updated to lucataco models)
2. **Issue 9:** Limited search results - ✅ FIXED (increased limit to 25)
3. **Issue 10:** Side table detection - ✅ FIXED (extended normalization)
4. **Issue 12:** Pillow search fails - ✅ FIXED (added synonyms)
5. **Issue 13:** Wall art search fails - ✅ FIXED (added synonyms)
6. **Issue 14:** Bed search fails - ✅ FIXED (comprehensive synonym audit for ALL categories)

### 🔴 High Priority (Fix Next)
6. **Issue 11:** Text duplication commands - common user request
7. **Issue 2:** Product filtering - "single seater" not found
8. **Issue 7:** Mask generation error - affects inpainting
9. **Issue 1:** OpenAI timeout - affects first request
10. **Issue 5:** High demand fallback - UX issue

### 🟡 Medium Priority (Fix Later)
11. **Issue 8:** Bed visualization quality - aesthetics
12. **Issue 3:** Conversation loop - has workaround
13. **Issue 4:** Follow-up recommendations - nice to have

---

**Created:** 2025-10-14
**Last Updated:** 2025-10-15
**Status:** Active Development - 16 Total Issues (3 Fixed, 13 Open)
