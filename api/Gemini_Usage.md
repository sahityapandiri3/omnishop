# Gemini API Usage in Omnishop

This document maps which Gemini API methods are used in the codebase.

## API Methods Overview

| Method | Purpose | Token Tracking |
|--------|---------|----------------|
| `BatchEmbedContents` | Generate embeddings for semantic search | No |
| `GenerateContent` | Text/JSON responses, image editing | Yes |
| `StreamGenerateContent` | Image generation (visualizations) | No (streaming) |

---

## 1. BatchEmbedContents (`embed_content`)

**File:** `services/embedding_service.py`

| Line | Operation | Model |
|------|-----------|-------|
| 77 | Product embedding generation | `text-embedding-004` |

**Usage:** Generates vector embeddings for products to enable semantic search.

---

## 2. GenerateContent (non-streaming)

### services/google_ai_service.py

#### Active Methods (called in user flows)

| Operation | Model | Description |
|-----------|-------|-------------|
| `remove_furniture` | gemini-3-pro-image-preview | Removes furniture + straightens lines (3 calls: analyze_room_image, remove_furniture, transform_perspective_to_front) |
| `transform_perspective_to_front` | gemini-3-pro-image-preview | Transforms corner/diagonal view to front view (called by remove_furniture when needed) |
| `remove_products_from_visualization` | gemini-3-pro-image-preview | Removes specific products from visualization |
| `generate_alternate_view` | gemini-3-pro-image-preview | Generates alternate viewing angle |

**Furniture Removal Flow (3 Gemini Calls):**
1. `analyze_room_image` (JSON) - Detects viewing angle + room style/type/dimensions
2. `remove_furniture` (IMAGE) - Removes furniture + straightens vertical lines
3. `transform_perspective_to_front` (IMAGE) - Transforms to front view if angle is not straight_on

#### Dead Code (defined but not called)

| Operation | Model | Reason |
|-----------|-------|--------|
| `validate_furniture_removed` | gemini-2.5-flash | Never called (validation disabled) |
| `inpaint_product_area` | gemini-3-pro-image-preview | SAM endpoint disabled (returns 501) |
| `_straighten_vertical_lines` | gemini-3-pro-image-preview | Now handled inside `remove_furniture` prompt |

### services/image_transformation_service.py

| Operation | Model | Status |
|-----------|-------|--------|
| Image transformation | gemini-2.0-flash-exp | Demo only (standalone_demo.py) |

### REST API Calls (`_make_api_request`)

These use HTTP directly but call the same GenerateContent endpoint:

| Operation | Model | Description |
|-----------|-------|-------------|
| `analyze_room_image` | gemini-3-pro-preview | Analyzes room for spatial understanding (also used in furniture removal for perspective detection) |
| `analyze_room_with_furniture` | gemini-3-pro-preview | Combined room + furniture analysis |
| `spatial_analysis` | gemini-3-pro-preview | Analyzes spatial layout |
| `detect_objects` | gemini-3-pro-preview | Detects objects in room |
| `detect_furniture` | gemini-3-pro-preview | Detects furniture specifically |
| `check_furniture_exists` | gemini-3-pro-preview | Checks if furniture type exists |
| `health_check` | gemini-3-pro-preview | API health check |
| `analyze_image_with_prompt` | (varies) | Custom image analysis |
| `classify_room_style` | gemini-2.0-flash | Classifies room style |
| `detect_product_positions` | gemini-2.0-flash-exp | Detects product positions in visualization |

---

## 3. StreamGenerateContent (streaming)

**File:** `services/google_ai_service.py`

### Active Methods

| Operation | Model | Description | Called From |
|-----------|-------|-------------|-------------|
| `generate_add_visualization` | gemini-3-pro-image-preview | Adds single product to room | chat.py (fallback) |
| `generate_add_multiple_visualization` | gemini-3-pro-image-preview | **Main visualization method** - handles add, replace_one, replace_all | chat.py, homestyling.py |

### Dead Code (defined but never called)

| Operation | Model | Reason |
|-----------|-------|--------|
| `generate_replace_visualization` | gemini-3-pro-image-preview | Frontend uses `generate_add_multiple_visualization` with text instruction instead |
| `generate_text_based_visualization` | gemini-3-pro-image-preview | Only in chat.py.backup |
| `generate_iterative_visualization` | gemini-3-pro-image-preview | Only in chat.py.backup |

### How "Replace" Works

The frontend sends `action: "replace_one"` or `action: "replace_all"` to the `/visualize` endpoint, which calls `generate_add_multiple_visualization` with a text instruction:

```python
# replace_one
visualization_instruction = "Replace ONE of the existing {furniture}s with the selected product."

# replace_all
visualization_instruction = "Replace ALL existing {furniture}s with the selected product."
```

**Note:** Streaming API does not return token usage metadata, so these operations are logged without token counts.

---

## Workflow Tracking

All API calls now support `workflow_id` to group calls from a single user action:

```sql
-- View workflows and their API calls
SELECT
    session_id as workflow_id,
    array_agg(operation ORDER BY timestamp) as operations,
    COUNT(*) as api_calls,
    SUM(total_tokens) as total_tokens
FROM api_usage
WHERE session_id IS NOT NULL
GROUP BY session_id
ORDER BY MIN(timestamp) DESC;
```

---

## Models Used

| Model | Use Case |
|-------|----------|
| `text-embedding-004` | Product embeddings |
| `gemini-2.0-flash` | Fast style classification |
| `gemini-2.0-flash-exp` | Fast analysis tasks |
| `gemini-2.5-flash` | Validation tasks |
| `gemini-3-pro-preview` | Room analysis (text/JSON) |
| `gemini-3-pro-image-preview` | Image generation & editing |
