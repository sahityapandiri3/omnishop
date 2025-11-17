# Inpainting + Masking Solution Options

## Problem Summary
- **Current Issue**: Replicate SDXL inpainting models return 404 (models don't exist/deprecated)
- **Current Fallback**: Gemini generative model (gemini-2.5-flash-image)
- **Why Fallback is Wrong**: Gemini is GENERATIVE (creates furniture from descriptions), not INPAINTING (places exact product images)
- **User Requirement**: Need proper inpainting + masking workflow to place exact selected products

## Solution Options

### Option 1: HuggingFace Diffusers (Local SDXL Inpainting) ⚠️ CHALLENGES
**Status**: Partially implemented in `local_inpainting_service.py`

**Pros**:
- Full control over the model
- No API rate limits or costs
- Can use exact product images

**Cons**:
- Requires downloading ~7GB SDXL model files
- Requires significant RAM (16GB+ recommended)
- Requires GPU for reasonable speed (M1/M2 Mac or CUDA GPU)
- 30-60 seconds per image on CPU, 5-10 seconds on GPU
- First run will download models automatically

**Implementation Status**:
- ✅ Service created with proper masking logic
- ✅ Dependencies added to requirements.txt
- ❌ Not yet integrated into chat router
- ❌ Model download not initiated

**Required Changes**:
1. Install dependencies: `pip install diffusers transformers accelerate torch`
2. First run will auto-download ~7GB of model weights
3. Replace Replicate calls in chat.py line 939

###Option 2: Alternative Hosted APIs (Recommended) ✅

**A. Stability AI Direct API**
- Official SDXL inpainting API from Stability AI
- Requires API key from stability.ai
- Cost: ~$0.02-0.05 per image
- Much faster than local (3-5 seconds)

**B. Hugging Face Inference API**
- Hosted SDXL inpainting
- Requires HF API token (free tier available)
- Can specify exact model: `stabilityai/stable-diffusion-xl-refiner-1.0`
- Moderate speed (10-15 seconds)

**C. Fal.ai**
- Modern AI API platform
- SDXL inpainting support
- Fast inference (3-5 seconds)
- Good free tier

### Option 3: Hybrid Approach (Quick Win) ✅ RECOMMENDED FOR NOW
Use Google's Imagen AI for inpainting instead of Gemini generative model.

**Gemini has an inpainting-capable model**: `gemini-1.5-pro-vision` with edit masks

**Changes Required**:
1. Modify `google_ai_service.py` to add inpainting method using masks
2. Use product image URLs as reference
3. Generate masks in chat.py (already have mask generation logic in replicate service)

**Pros**:
- Minimal changes to existing code
- No new API keys needed (already using Google AI)
- Fast inference
- Can use product images as visual reference

**Cons**:
- Still using Google's model (not dedicated SDXL)
- May not be as precise as dedicated inpainting models

## Recommended Implementation Plan

### Phase 1: Quick Fix (1-2 hours)
1. Implement Gemini-based inpainting with masks in `google_ai_service.py`
2. Update chat.py to use masked inpainting instead of generative
3. Test with product placement

### Phase 2: Long-term Solution (3-5 hours)
1. Sign up for Stability AI API or Fal.ai
2. Create new `stability_inpainting_service.py`
3. Implement proper inpainting + masking workflow
4. Use exact product images as reference
5. Update chat.py to use new service

### Phase 3: Local Fallback (Optional)
1. Complete local_inpainting_service.py integration
2. Use as fallback when APIs fail
3. Warn users about model download and GPU requirements

## Decision Needed
Which option should we implement first?

**My Recommendation**: Start with **Phase 1 (Gemini-based inpainting with masks)** to quickly fix the immediate issue, then move to **Phase 2 (Stability AI or Fal.ai)** for production quality.

This gives us:
- ✅ Immediate fix using existing API
- ✅ Proper masking workflow
- ✅ Product image reference capability
- ✅ Path to upgrade to dedicated SDXL later
