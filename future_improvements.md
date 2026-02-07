# Future Improvements

## 1. Re-generate Product Embeddings with New Model

**Priority**: Low (keyword search works well without it)
**Effort**: ~1-2 hours (mostly waiting for batch processing)

### Background
We updated the embedding model from `text-embedding-004` (deprecated Jan 2026) to `gemini-embedding-001` in `api/services/embedding_service.py`. Query embeddings now use the new model, but the ~19,000 product embeddings stored in the database were generated with the old model.

### Why it matters
The two models place text in different vector spaces, so cosine similarity between a new-model query and old-model product embedding is essentially random noise. The "related products" section (semantic-only matches) returns somewhat arbitrary results. This is masked by the keyword search improvements which handle 90%+ of results.

### Steps
1. Run the batch embedding script on **staging** first (`api/services/embedding_service.py` → `batch_generate_embeddings()`)
2. Verify search quality — check that `total_related` counts are non-zero and results make sense
3. Run on **production**
4. Estimated time: ~30 min for ~19K products at 100/batch with 0.5s rate limit

### How to verify
- Search "cozy minimalist sofa" — `total_related` should show semantically similar products (e.g., loveseats, daybeds) that don't match keywords
- Compare results before/after on staging

---

## 2. Protect All Background Tasks from Garbage Collection

**Priority**: High — caused production failure (Feb 6, 2026 evening)
**Status**: Fixed for homestyling generation in commit `56db6e76`, but the same vulnerability exists in other files

### What happened
Homestyling look generation silently failed in production. `asyncio.create_task()` returns a task object, but if nothing holds a reference to it, Python's garbage collector can destroy the task before it finishes. This worked locally (shorter GC cycles, less memory pressure) but broke in production.

### The fix (applied to homestyling only)
In `api/routers/homestyling.py`, a module-level `_background_tasks` set keeps references alive until tasks complete:
```python
_background_tasks = set()

task = asyncio.create_task(_run_generation_in_background(session_id))
_background_tasks.add(task)
task.add_done_callback(_background_tasks.discard)
```

### Other files with the same vulnerability
These files use `asyncio.create_task()` without keeping a reference — they could silently fail in production:
- `api/main.py:203` — `periodic_furniture_cleanup()`
- `api/services/mask_precomputation_service.py:141,151` — segmentation and furniture removal tasks
- `api/services/google_ai_service.py:7678` — clean background task
- `api/routers/visualization.py:532` — furniture removal background task

### Fix needed
Apply the same `_background_tasks` set pattern to each of these files. For each `asyncio.create_task()` call:
1. Add a module-level `_background_tasks = set()` if not already present
2. Store the task reference: `task = asyncio.create_task(...)`
3. Add to set: `_background_tasks.add(task)`
4. Auto-remove on completion: `task.add_done_callback(_background_tasks.discard)`

### How to verify
- Trigger homestyling generation in production — should complete successfully
- Trigger mask precomputation — should not silently fail
- Check logs for "Task was destroyed but it is pending!" warnings (indicates GC issue)
