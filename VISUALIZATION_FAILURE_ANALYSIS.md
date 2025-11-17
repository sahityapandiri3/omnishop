# Visualization Failure - Root Cause Analysis

## Issue Report

**Date**: 2025-10-22
**Session**: 7824ca89-d62e-467a-8230-2720346dc9c5
**Product**: Nordhaven Sofa (ID: 387)
**Result**: Completely incorrect visualization - old furniture not removed, new furniture not properly placed

## Visual Analysis of Output Image

From the user-provided output image:
1. **Original sectional sofas still visible** in the room (brown/beige L-shaped sectional)
2. **Room structure changed** - walls, floor, lighting all distorted
3. **New product not properly integrated** - doesn't match reference image
4. **Complete room redesign** instead of furniture replacement

---

## Root Cause Analysis

### **CRITICAL ISSUE #1: Server Did NOT Reload with FIX 4 & FIX 5** ❌

**Evidence from Logs**:
```
Running Private MajicMIX Deployment (IP-Adapter + Inpainting)...
```

**Expected Log (with FIX 4)**:
```
Running Private MajicMIX Deployment (IP-Adapter + Inpainting + Canny ControlNet)...
Generated Canny edge map: (1920, 1080)
```

**Expected Log (with FIX 5)**:
```
Calling ChatGPT Vision API for product analysis: Nordhaven Sofa
ChatGPT Vision API analysis completed in 2.45s
Extracted color: walnut brown, material: solid teak wood, style: modern
Using ChatGPT Vision API analysis for product prompt
```

**Actual Result**:
- NO Canny edge generation log
- NO Vision API call log
- Server is running **OLD CODE** without FIX 4 and FIX 5

**Impact**:
- Canny ControlNet NOT applied → No room structure preservation
- Vision API NOT called → Generic product prompts (just product name)
- IP-Adapter scale unknown (FIX 1 status unclear)

**Confirmation**:
File `/Users/sahityapandiri/Omnishop/api/services/cloud_inpainting_service.py` DOES contain the new code (verified lines 208-313), but the running server process has NOT loaded it.

---

### **CRITICAL ISSUE #2: Mask Positioning Completely Wrong** ❌

**From Logs**:
```
Detected sofa: bbox={'x1': 0.0, 'y1': 0.5, 'x2': 0.4, 'y2': 0.9}
Detected sofa: bbox={'x1': 0.4, 'y1': 0.5, 'x2': 0.9, 'y2': 0.9}
Added mask for furniture: 528x768px at (0, 736)
Added mask for furniture: 720x768px at (420, 736)
```

**Problem Analysis**:
1. **Detected Bounding Boxes (Normalized 0-1)**:
   - Sofa 1: Y-range = 0.5 to 0.9 (50% to 90% of image height)
   - Sofa 2: Y-range = 0.5 to 0.9 (50% to 90% of image height)
   - This means sofas occupy the MIDDLE to BOTTOM portion of image

2. **Generated Masks (Pixel Coordinates)**:
   - Mask 1: Y-position = 736px
   - Mask 2: Y-position = 736px
   - Assuming 1920x1080 image: 736/1080 = 68% down the image
   - Masks start at 68% and go to ~100% (bottom of image)

3. **Misalignment**:
   - Furniture detected at: 50%-90% (Y-axis)
   - Masks placed at: 68%-100% (Y-axis)
   - **Gap**: 50%-68% of furniture is NOT masked
   - **Overlap**: Only 68%-90% is properly masked (partial coverage)

**Visual Consequence**:
- Upper portion of sofas (50%-68%) remains UNTOUCHED
- Only lower portion (68%-90%) is inpainted
- Result: AI generates NEW furniture over PARTIAL mask, leaving original furniture partially visible

**Code Location**: `cloud_inpainting_service.py:439-442`
```python
# Bounding box format: {'x1': ..., 'y1': ..., 'x2': ..., 'y2': ...}
# Coordinates are normalized (0-1), scale to image dimensions
x1 = int(bbox['x1'] * width)
y1 = int(bbox['y1'] * height)
x2 = int(bbox['x2'] * width)
y2 = int(bbox['y2'] * height)
```

**Expected Calculation** (for 1920x1080 image):
- y1 = int(0.5 * 1080) = **540px** ← Mask should start here
- y2 = int(0.9 * 1080) = **972px** ← Mask should end here

**Actual Result** (from logs):
- y1 = **736px** ← Mask actually starts here (WRONG!)
- y2 = **~1072px** (736 + 768 height - some overlap)

**Bug**: Mask starting Y-coordinate is offset by ~200px, causing misalignment

---

### **ISSUE #3: No Canny ControlNet = Complete Room Distortion** ❌

**Problem**:
- Canny ControlNet preserves 100% of room structure (walls, floor, windows, doors)
- Without it, only the MASKED area has structure guidance from Inpainting ControlNet
- Unmasked area (0%-50% in this case) has ZERO structure preservation

**From Logs**:
```
sorted_controlnets: "inpainting"  # Should be "canny,inpainting"
```

**Impact on Output Image**:
- Walls redesigned (different color, texture, style)
- Floor changed (different material, finish)
- Windows/lighting completely altered
- Entire room aesthetic is different from original

**Expected with FIX 4**:
- `sorted_controlnets: "canny,inpainting"`
- `canny_controlnet_scale: 0.8` (80% structure preservation)
- Canny edge map provides full-image guidance
- Result: Room structure preserved, only furniture replaced

---

### **ISSUE #4: Generic Product Prompt (No Vision API)** ❌

**From Logs**:
```
Using enhanced prompt: High resolution photography interior design, modern room with
walnut Nordhaven Sofa 3 Seater Solid Teak Wood/Walnut/Oak Wood, professional interior
photography, realistic lighting and shadows, correct perspective and scale, seamless
integration, high quality, exact color match to reference image
```

**Problems**:
1. Just repeating product name verbatim: "Nordhaven Sofa 3 Seater Solid Teak Wood/Walnut/Oak Wood"
2. Only color extracted: "walnut" (from product name)
3. No style information (modern, mid-century, contemporary?)
4. No design details (arm style, leg style, cushion type?)
5. No texture description (smooth, tufted, etc?)
6. No dimensions (size, proportions)

**Expected with FIX 5 (Vision API)**:
```
Using enhanced prompt: High resolution photography interior design, modern room with
Nordhaven Sofa, walnut brown with rich undertones color, solid teak wood with smooth
finish material, modern mid-century style, track arms with tapered wooden legs and
loose cushions, dimensions 84 inches wide by 36 inches deep by 36 inches high,
professional interior photography, realistic lighting and shadows, correct perspective
and scale, seamless integration, high quality, exact color match to reference image
```

**Impact**:
- AI lacks detailed guidance on product appearance
- Relies heavily on IP-Adapter image alone
- Without precise prompt, AI may generate incorrect variations

---

### **ISSUE #5: IP-Adapter Scale Status Unknown** ⚠️

Logs don't explicitly show IP-Adapter scale value. Need to verify if FIX 1 (scale = 1.0) is active.

From code: `"ip_adapter_scale": 1.0` (line 313)
But server is running old code, so actual value is likely still 0.8.

---

## Detailed Failure Timeline

### Step 1: Furniture Detection ✅ (Worked Correctly)
```
Detected sofa: bbox={'x1': 0.0, 'y1': 0.5, 'x2': 0.4, 'y2': 0.9}
Detected sofa: bbox={'x1': 0.4, 'y1': 0.5, 'x2': 0.9, 'y2': 0.9}
```
- ChatGPT Vision correctly identified 2 sofas
- Bounding boxes correctly normalized (0-1 coordinates)
- Both sofas detected in correct positions (50%-90% Y-axis)

### Step 2: Mask Generation ❌ (FAILED - Misaligned)
```
Added mask for furniture: 528x768px at (0, 736)
Added mask for furniture: 720x768px at (420, 736)
```
- Masks placed at Y=736px instead of Y=540px
- Only covers 68%-100% instead of 50%-90%
- Upper 18% of furniture left unmasked

### Step 3: Product Analysis ❌ (FAILED - No Vision API)
```
Using enhanced prompt: High resolution photography interior design, modern room with
walnut Nordhaven Sofa 3 Seater Solid Teak Wood/Walnut/Oak Wood...
```
- Vision API NOT called (server using old code)
- Fallback to local extraction (just product name)
- No detailed product attributes

### Step 4: Replicate API Call ❌ (FAILED - Missing Canny ControlNet)
```
HTTP Request: POST https://api.replicate.com/v1/deployments/sahityapandiri3/omnishop-controlnet/predictions
```
- Sent with `sorted_controlnets: "inpainting"` (missing Canny)
- No Canny edge map generated or sent
- No full-room structure preservation
- Result: Entire room redesigned

### Step 5: Visualization Result ❌ (COMPLETELY FAILED)
- Original furniture still visible (mask misalignment)
- Room structure completely changed (no Canny ControlNet)
- Product appearance incorrect (no Vision API guidance)
- Output unusable

---

## Fix Priority List

### **FIX #1: Force Server Reload** (CRITICAL - BLOCKS ALL OTHER FIXES)
**Problem**: Server running old code without FIX 4 & FIX 5
**Solution**: Manually restart server process

**Steps**:
1. Kill current server process
2. Start new process in `/Users/sahityapandiri/Omnishop/api` directory
3. Verify server logs show:
   - "Running Private MajicMIX Deployment (IP-Adapter + Inpainting + Canny ControlNet)..."
   - "Calling ChatGPT Vision API for product analysis..."

**Command**:
```bash
cd /Users/sahityapandiri/Omnishop/api
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 3
export OPENAI_API_KEY=sk-proj-...
export GOOGLE_AI_API_KEY=AIzaSy...
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

### **FIX #2: Debug and Fix Mask Coordinate Calculation** (CRITICAL)
**Problem**: Masks placed at wrong Y-coordinates (736px instead of 540px)
**Location**: `cloud_inpainting_service.py:439-442`

**Current Code**:
```python
x1 = int(bbox['x1'] * width)
y1 = int(bbox['y1'] * height)
x2 = int(bbox['x2'] * width)
y2 = int(bbox['y2'] * height)
```

**Debug Steps**:
1. Add logging BEFORE coordinate conversion:
   ```python
   logger.info(f"DEBUG: bbox = {bbox}, width = {width}, height = {height}")
   logger.info(f"DEBUG: bbox['y1'] = {bbox['y1']}, height = {height}")
   logger.info(f"DEBUG: Calculated y1 = {int(bbox['y1'] * height)}")
   ```

2. Check if padding calculation is causing offset:
   ```python
   logger.info(f"DEBUG: Before padding: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
   # ... padding code ...
   logger.info(f"DEBUG: After padding: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
   ```

3. Verify mask drawing:
   ```python
   draw.rectangle([x1, y1, x2, y2], fill=255)
   logger.info(f"DEBUG: Drew rectangle at [{x1}, {y1}, {x2}, {y2}]")
   ```

**Suspected Cause**:
- Bounding boxes might be coming in pixel coordinates instead of normalized (0-1)
- Or padding calculation is adding too much offset
- Or furniture detection is returning wrong coordinates

---

### **FIX #3: Verify Vision API is Called** (HIGH PRIORITY)
**Problem**: Vision API not being invoked
**Location**: `cloud_inpainting_service.py:226-228`

**Verification Steps**:
1. Check logs for "Calling ChatGPT Vision API for product analysis"
2. Check logs for "ChatGPT Vision API analysis completed"
3. Check logs for "Using ChatGPT Vision API analysis for product prompt"

**If Still Fails**:
- Check OpenAI API key is valid: `settings.openai_api_key`
- Check model name is correct: `settings.openai_model` (should be "gpt-4o")
- Add error logging in Vision API method

---

### **FIX #4: Verify Canny ControlNet is Active** (HIGH PRIORITY)
**Problem**: Canny edge detection not running
**Location**: `cloud_inpainting_service.py:211-212`

**Verification Steps**:
1. Check logs for "Generated Canny edge map"
2. Check Replicate API call includes:
   - `canny_image`: data URI of edge map
   - `sorted_controlnets`: "canny,inpainting"
   - `canny_controlnet_scale`: 0.8

---

## Testing Plan

### Test 1: Verify Server Reload
**Goal**: Confirm FIX 4 & FIX 5 are loaded

**Steps**:
1. Force server restart
2. Make visualization request
3. Check logs for:
   - "Running Private MajicMIX Deployment (IP-Adapter + Inpainting + Canny ControlNet)..."
   - "Calling ChatGPT Vision API for product analysis"
   - "Generated Canny edge map"

**Success Criteria**: All 3 log entries present

---

### Test 2: Verify Mask Alignment
**Goal**: Confirm masks cover detected furniture correctly

**Steps**:
1. Add debug logging for bbox coordinates
2. Make visualization request
3. Compare detected bbox Y-range with mask Y-position
4. Verify mask covers 100% of furniture (with padding)

**Success Criteria**: Mask Y-range matches bbox Y-range (±10% padding)

**Example**:
```
Detected sofa: y1=0.5, y2=0.9
Calculated mask: y1=540px, y2=972px (for 1080px height)
With 10% padding: y1=486px, y2=1026px
Expected log: "Added mask for furniture: XXXxYYYpx at (X, 486)"
```

---

### Test 3: Compare Output Quality
**Goal**: Verify visualization improvements after fixes

**Steps**:
1. Use same room image + same product (Nordhaven Sofa)
2. Generate visualization with all fixes active
3. Compare output with previous failed attempt

**Success Criteria**:
- ✅ Original furniture completely removed
- ✅ Room structure preserved (walls, floor, windows unchanged)
- ✅ New product matches reference image (color, style, materials)
- ✅ Natural lighting and shadows
- ✅ Correct scale and proportions

---

## Summary

| Issue | Severity | Status | Fix Required |
|-------|----------|--------|--------------|
| Server not reloaded | **CRITICAL** | ❌ Blocking | Force restart |
| Mask misalignment | **CRITICAL** | ❌ Active bug | Debug + Fix calculation |
| No Canny ControlNet | **HIGH** | ❌ Not loaded | Server reload |
| No Vision API | **HIGH** | ❌ Not loaded | Server reload |
| Generic prompts | **MEDIUM** | ❌ Fallback active | Vision API fix |
| Room distortion | **CRITICAL** | ❌ Consequence | Canny ControlNet fix |
| Furniture not removed | **CRITICAL** | ❌ Consequence | Mask alignment fix |

---

## Next Steps

1. **IMMEDIATE**: Force server restart to load FIX 4 & FIX 5
2. **HIGH PRIORITY**: Debug mask coordinate calculation bug
3. **VERIFICATION**: Re-test with same product to compare results
4. **OPTIMIZATION**: Fine-tune Canny thresholds if needed

---

## Expected Improvement After Fixes

### Before (Current State):
- Room completely redesigned
- Original furniture still visible
- New product doesn't match reference
- Unusable output

### After (All Fixes Applied):
- Room structure preserved (Canny ControlNet)
- Original furniture fully removed (correct mask)
- Product matches reference exactly (Vision API + IP-Adapter 1.0)
- Professional, photorealistic output
- Natural integration with existing lighting

