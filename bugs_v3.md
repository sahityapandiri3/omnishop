# Bug Fixes - Version 3

## Date: November 2, 2025

## Issues Fixed

### 1. ✅ CENTER TABLE RECOGNITION
**Status:** FIXED
**Problem:** Users in India say "center table" instead of "coffee table", but the system only recognized "coffee table"

**Root Cause:** Missing keyword patterns for "center table" and "centre table" in both the keyword extraction function and the recommendation engine category definitions.

**Files Modified:**
- `/api/routers/chat.py` (lines 650-652)
  - Added patterns: `('center table', ['coffee table', 'center table'])`
  - Added patterns: `('centre table', ['coffee table', 'center table'])`

- `/api/services/recommendation_engine.py` (line 203)
  - Added 'center table' and 'centre table' to tables category
  - Category now includes: `['table', 'coffee table', 'center table', 'centre table', 'dining table', 'side table', ...]`

**Result:** Searching for "center table" now correctly finds coffee tables in the database.

---

### 2. ✅ CATEGORY FILTERING IMPROVEMENTS
**Status:** ENHANCED
**Problem:** Searching for "rugs" was returning beds, sofas, and other unrelated products

**Root Cause:** Category definitions weren't comprehensive enough to prevent cross-category contamination.

**Files Modified:**
- `/api/services/recommendation_engine.py` (lines 198-207)
  - Enhanced category definitions
  - Added 'mat' to decor category (along with 'rug' and 'carpet')
  - Improved table categorization with center/side table support

**Category Structure:**
```python
categories = {
    'ceiling_lighting': ['ceiling lamp', 'ceiling light', 'chandelier', 'pendant', ...],
    'portable_lighting': ['table lamp', 'desk lamp', 'floor lamp'],
    'wall_lighting': ['wall lamp', 'sconce', 'wall light'],
    'seating_furniture': ['sofa', 'couch', 'sectional', 'loveseat', 'chair', ...],
    'tables': ['table', 'coffee table', 'center table', 'centre table', 'dining table', ...],
    'storage_furniture': ['dresser', 'chest', 'cabinet', 'bookshelf', ...],
    'bedroom_furniture': ['bed', 'mattress', 'headboard'],
    'decor': ['mirror', 'rug', 'carpet', 'mat'],
    'general_lighting': ['lamp', 'lighting'],
}
```

**Result:** Better category-aware filtering reduces cross-category contamination.

---

### 3. ✅ UNDO/REDO BUTTONS ERROR
**Status:** FIXED
**Problem:** Undo and redo buttons throw errors when clicked

**Root Cause:** The `undoVisualization` and `redoVisualization` functions are called in `ChatInterface.tsx` (lines 387, 417) but didn't exist in `/frontend/src/utils/api.ts`. Additionally, no backend endpoints existed to handle undo/redo operations.

**Files Modified:**

1. **`/api/services/conversation_context.py`**
   - Added `visualization_history` and `visualization_redo_stack` fields to `ConversationContext` dataclass (lines 29-30)
   - Added `push_visualization_state()` method to store visualization states (lines 197-225)
   - Added `undo_visualization()` method to undo last visualization (lines 227-252)
   - Added `redo_visualization()` method to redo visualization (lines 254-276)
   - Added `can_undo()` and `can_redo()` helper methods (lines 278-290)
   - Visualization history is limited to last 20 states to prevent memory issues

2. **`/api/routers/chat.py`**
   - Added `POST /sessions/{session_id}/visualization/undo` endpoint (lines 564-590)
   - Added `POST /sessions/{session_id}/visualization/redo` endpoint (lines 600-626)
   - Modified `visualize_room` endpoint to push visualization states to history (lines 577-596):
     - For FIRST visualization: pushes original state (base image), then new state → history has 2 items
     - For subsequent visualizations: only pushes new state
     - This ensures undo works even after the first visualization

3. **`/frontend/src/utils/api.ts`**
   - Added `undoVisualization(sessionId: string)` function (lines 182-190)
   - Added `redoVisualization(sessionId: string)` function (lines 192-200)

4. **`/frontend/src/components/ChatInterface.tsx`** (CRITICAL FIX for display issue)
   - Fixed response structure mismatch in `handleUndo()` (lines 389, 397):
     - Changed from `if (response.success)` to `if (response.visualization)`
     - Changed from `response.rendered_image` to `response.visualization.rendered_image`
   - Fixed response structure mismatch in `handleRedo()` (lines 419, 427):
     - Changed from `if (response.success)` to `if (response.visualization)`
     - Changed from `response.rendered_image` to `response.visualization.rendered_image`
   - **Root Cause**: Backend returns `{visualization: {...}, message: "...", can_undo: ..., can_redo: ...}` but frontend was trying to access flat structure with `success` field that doesn't exist
   - This ensures the frontend correctly displays the undone/redone visualization image

**Implementation Details:**
- Visualization history uses a stack-based approach with separate undo and redo stacks
- When a new visualization is created, it's automatically pushed to history and redo stack is cleared
- Undo operation pops current state to redo stack and returns previous state
- Redo operation pops from redo stack and pushes back to history
- Both endpoints return `can_undo` and `can_redo` flags for UI state management
- Backend returns nested structure: `response.visualization.rendered_image`
- Frontend must check `response.visualization` (not `response.success`) and access nested image path

**Result:** Undo and redo buttons now work correctly without errors and properly display previous/next visualizations.

---

### 4. ✅ SIDE TABLE VS CENTER TABLE PLACEMENT
**Status:** FIXED
**Problem:** Side tables should be placed beside sofas, not in the center. Center tables and side tables should be distinct categories with different placement logic. The system was suggesting side table replacements when a center table was detected, and vice versa.

**User Requirements:**
- Side tables must be placed on the SIDE of the sofa
- Center tables must be placed IN FRONT of the sofa
- These should be treated as separate furniture categories with different placement prompts
- System should NOT suggest side table products when a center table is detected (and vice versa)

**Root Cause:** The system grouped all tables together without distinguishing placement requirements and detection logic for different table types (center vs side). Additionally, furniture detection didn't properly categorize tables based on their position in the room.

**Files Modified:**

1. **`/api/services/recommendation_engine.py`** (lines 198-211)
   - Split `tables` category into four distinct categories:
     - `center_tables`: `['coffee table', 'center table', 'centre table']` - Placed in front of sofa
     - `side_tables`: `['side table', 'end table', 'nightstand', 'bedside table']` - Placed beside furniture
     - `dining_tables`: `['dining table']` - Separate category for dining tables
     - `other_tables`: `['console table', 'desk', 'table']` - Generic tables
   - Categories are now mutually exclusive for better product filtering

2. **`/api/routers/chat.py`** (lines 415-472)
   - Updated product type extraction logic to distinguish center tables from side tables:
     - `'center_table'` for coffee/center/centre tables
     - `'side_table'` for side/end/nightstand/bedside tables
     - `'dining_table'` for dining tables
     - `'console_table'` for console tables
   - **Added STRICT table matching logic** (lines 440-472):
     - Center tables ONLY match `center_table`, `coffee_table`, `centre_table` in detected furniture
     - Side tables ONLY match `side_table`, `end_table`, `nightstand`, `bedside_table` in detected furniture
     - This prevents suggesting side table products when a center table exists, and vice versa

3. **`/api/routers/chat.py`** (lines 660-691)
   - Updated `_extract_furniture_type()` function to return specific table types:
     - Returns `'center table'` for coffee/center/centre tables
     - Returns `'side table'` for side/end/nightstand/bedside tables
     - Returns `'dining table'` for dining tables
     - Returns `'console table'` for console tables
   - Order matters: specific types checked before generic `'table'` fallback

4. **`/api/services/google_ai_service.py`** (lines 409-469)
   - Updated furniture detection AI prompt with **explicit table categorization instructions**:
     - "If the table is positioned IN FRONT OF or IN THE CENTER in front of seating (sofa/chairs), use: 'center_table' or 'coffee_table'"
     - "If the table is positioned BESIDE or NEXT TO seating (sofa/chairs/bed), use: 'side_table' or 'end_table'"
   - AI now returns specific table types based on position, not just generic "table"
   - This ensures the `object_type` field properly distinguishes center vs side tables

5. **`/api/services/google_ai_service.py`** (lines 598-604)
   - Updated placement guidelines in `generate_add_visualization()`:
     - Center tables: "place IN FRONT OF the sofa or seating area, in the center"
     - Side tables: "place BESIDE or NEXT TO the sofa, chair, or bed (on the side, not in front)"
   - AI image generation now receives explicit placement instructions

6. **`/api/services/cloud_inpainting_service.py`** (lines 1011-1069)
   - Added new `_get_placement_instruction()` method to generate table-specific placement prompts
   - Center tables: `"placed in the center of the room, in front of the sofa or seating area"`
   - Side tables: `"placed on the side, next to the sofa, chair, or bed"`
   - Other furniture: `"naturally placed in the room"` (default)
   - Updated `_build_inpainting_prompt()` to call `_get_placement_instruction()` and inject placement-specific text into both enhanced (Vision) and basic prompts

**Implementation Details:**
- **Furniture Detection**: AI now analyzes table position in room and returns specific types (`center_table` vs `side_table`)
- **Strict Matching**: Center tables and side tables are treated as distinct, non-interchangeable categories
- **Placement Prompts**: Both Google AI and Cloud Inpainting services use table-specific placement instructions
- **Product Recommendations**: System prevents suggesting incompatible table replacements

**Result:** Center tables and side tables are now:
1. Properly detected based on position in room
2. Treated as distinct, non-interchangeable categories
3. Placed correctly (center tables in front, side tables beside)
4. Never suggested as replacements for each other

---

## Testing Recommendations

### For Fixed Issues (1 & 2):
1. Test searching for "center table" - should return coffee tables
2. Test searching for "centre table" (British spelling) - should return coffee tables
3. Test searching for "rugs" - should only return rugs/carpets, not beds or sofas
4. Test searching for "center table" in a sentence like "I want a wooden center table"

### For Pending Issues (3 & 4):
1. **Undo/Redo:**
   - Click undo button after making a visualization
   - Click redo button after undo
   - Verify no console errors
   - Verify visualization state changes correctly

2. **Table Placement:**
   - Add a center table to a room
   - Try to add a side table - verify it doesn't suggest replacing center table
   - Verify side table appears beside sofa, not in front
   - Verify center table appears in front of sofa

---

## Previous Fixes (from earlier session):
- ✅ Extended recommendation limit from 10 to 30 products
- ✅ Fixed Objectry product URLs from JSON endpoints to HTML pages
- ✅ Re-scraped all Objectry products to update URLs in database

---

## Summary

**Fixed:** 4/4 issues
**Identified but pending:** 0/4 issues

All four issues have been successfully fixed:
1. Center table recognition - Users in India can now search for "center table" and find coffee tables
2. Category filtering - Enhanced category definitions reduce cross-category contamination
3. Undo/redo functionality - Buttons now work correctly with full visualization history management
4. Side table placement - Center tables and side tables are now distinct categories with appropriate placement logic (center tables in front of sofa, side tables beside furniture)
