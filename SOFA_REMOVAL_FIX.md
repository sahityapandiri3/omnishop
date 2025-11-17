# Sofa Removal Bug Fix

**Date:** 2025-10-26
**Issue:** In the last UI test, the existing sofa was not removed during replace_all visualization

## Root Cause

The two-pass inpainting workflow had a **type mismatch** bug:

### The Bug Flow:
1. **Pass 1 (Removal):** `_remove_existing_furniture()` removes existing furniture and returns `rendered_image` as a **base64 data URI string**
2. **Line 177 (cloud_inpainting_service.py):** `working_image = removal_result.rendered_image` - stored as **string**
3. **Pass 2 (Placement):** `_run_text_only_inpainting(room_image=working_image)` - passed **string** to function
4. **Line 1417:** Function signature expects `room_image: Image.Image` - **PIL Image type!**

### Result:
- Pass 2 would fail silently due to type mismatch
- New furniture would be placed on **original image** instead of **cleaned image**
- Existing sofa was never removed

## The Fix

**File:** `api/services/cloud_inpainting_service.py`

**Lines 176-180:** Added decoding step to convert base64 string back to PIL Image

```python
if removal_result and removal_result.success:
    # CRITICAL FIX: Decode base64 string back to PIL Image for Pass 2
    logger.info(f"PASS 1 SUCCESS: Decoding cleaned image for PASS 2")
    working_image = self._decode_base64_image(removal_result.rendered_image)
    logger.info(f"PASS 1: Cleaned image decoded, size: {working_image.size}")
```

**File:** `api/services/replicate_inpainting_service.py`

**Lines 119-121:** Added clarifying comment (this service uses base64 throughout, so no conversion needed)

## Impact

### Before Fix:
- Replace_all action would show both old AND new sofas
- User would see duplicates instead of replacement
- Frustrating user experience

### After Fix:
- Pass 1 correctly removes existing furniture
- Pass 2 receives cleaned image as PIL Image
- New furniture placed on clean floor
- User sees proper replacement visualization

## Testing

Run the following test from UI:
1. Upload a room image with existing sofas
2. Select a new sofa product
3. Choose "Replace all" option
4. Verify that old sofas are removed and only new sofa appears

Expected result: Clean visualization with ONLY the new sofa, no duplicates.

## Related Files Modified
- `api/services/cloud_inpainting_service.py` (lines 176-180)
- `api/services/replicate_inpainting_service.py` (lines 119-121)
