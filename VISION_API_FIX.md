# FIX 5: ChatGPT Vision API Integration for Enhanced Product Prompt Generation

## Problem Statement

**Issue**: Local keyword extraction has fundamental limitations
- Only detects colors/materials explicitly mentioned in product name
- Cannot analyze actual product images to extract visual details
- Misses nuanced color descriptions (e.g., "sage green" vs "green")
- Cannot identify textures, styles, or design details from images
- Limited dimension extraction relies on regex patterns in descriptions

**Example Failures**:
- Product: "Green Velvet Sofa" → Local extraction finds "green" and "velvet"
- Actual product image: Shows "sage green with subtle gray undertones"
- Result: Prompt uses generic "green" instead of accurate "sage green"

**Root Cause Analysis**:
From test logs and PRODUCT_VISUALIZATION_FIXES.md:
```
Local Extraction Method (FIX 2):
- Color: Keyword matching from product name (40+ color dictionary)
- Material: Keyword matching from product name (25+ material dictionary)
- Limitations: Cannot see actual product, relies on text alone

Result: Generic prompts that don't capture true product appearance
```

## Solution: ChatGPT Vision API Integration with Fallback

**Implementation**: Use GPT-4o Vision API to analyze product images directly

### How It Works:
1. **Vision API Analysis** (Primary): Sends product image URL to GPT-4o for detailed visual analysis
2. **Structured Extraction**: Requests JSON response with exact_color, material, texture, style, design_details, dimensions
3. **Fallback Mechanism**: If Vision API fails/times out, falls back to local keyword extraction (FIX 2 & FIX 3)
4. **Enhanced Prompt Generation**: Builds detailed prompts using Vision API insights

## Technical Implementation

### 1. New Method: Vision API Product Analysis
**File**: `api/services/cloud_inpainting_service.py:756-897`

```python
async def _generate_product_prompt_with_vision(
    self,
    product_image_url: str,
    product_name: str,
    product_description: str
) -> Optional[Dict[str, Any]]:
    """
    Use ChatGPT Vision API to analyze product image and generate enhanced prompt

    Args:
        product_image_url: URL of the product image
        product_name: Product name from database
        product_description: Product description from database

    Returns:
        Dict with extracted attributes: {
            "exact_color": str,
            "material": str,
            "texture": str,
            "style": str,
            "design_details": str,
            "dimensions": str,
            "enhanced_prompt": str
        }
    """
    try:
        logger.info(f"Calling ChatGPT Vision API for product analysis: {product_name}")

        # Import openai client from settings
        import openai
        client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,
            max_retries=2
        )

        # Build Vision API prompt requesting detailed product analysis
        vision_prompt = f"""Analyze this furniture product image carefully and extract the following details:

Product Name: {product_name}
Product Description: {product_description}

Please provide a detailed analysis in JSON format:

1. EXACT COLOR: Identify the precise color(s) visible in the image (not just from the name)
   - Main color (e.g., "sage green", "navy blue", "charcoal gray")
   - Secondary colors if applicable
   - Color undertones (warm/cool)

2. MATERIAL: Identify materials from visual texture cues
   - Upholstery material (e.g., "velvet", "leather", "linen", "cotton")
   - Frame material (e.g., "wood", "metal", "wicker")
   - Visible material qualities (e.g., "tufted", "smooth", "woven")

3. TEXTURE: Describe visible surface texture
   - Surface finish (e.g., "plush velvet", "smooth leather", "textured fabric")
   - Pattern details if visible

4. STYLE: Classify the design style
   - Primary style (e.g., "modern", "mid-century", "traditional", "contemporary")
   - Design era or aesthetic

5. DESIGN DETAILS: Specific visual characteristics
   - Arm style (e.g., "rolled arms", "track arms", "no arms")
   - Leg style (e.g., "tapered wooden legs", "metal hairpin legs", "no visible legs")
   - Cushion type (e.g., "loose cushions", "tight back", "tufted")
   - Special features (e.g., "nailhead trim", "button tufting", "pleated skirt")

6. DIMENSIONS: Extract from description or estimate from visual proportions
   - Width, Depth, Height in inches
   - Overall size classification (small/medium/large)

Return ONLY valid JSON in this exact format:
{{
  "exact_color": "primary color with descriptive terms",
  "secondary_colors": ["color1", "color2"],
  "material": "primary material",
  "material_details": "additional material information",
  "texture": "surface texture description",
  "style": "design style classification",
  "design_details": "specific design characteristics",
  "dimensions": "extracted or estimated dimensions",
  "size_category": "small/medium/large",
  "enhanced_prompt": "A concise prompt combining all visual details for AI image generation"
}}"""

        # Prepare messages with image
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": vision_prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": product_image_url,
                            "detail": "high"
                        }
                    }
                ]
            }
        ]

        # Call ChatGPT Vision API with timeout
        start_time = time.time()
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.openai_model,  # gpt-4-vision-preview or gpt-4o
                messages=messages,
                max_tokens=1000,
                temperature=0.3,  # Low temperature for factual analysis
                response_format={"type": "json_object"}
            ),
            timeout=30.0
        )

        response_time = time.time() - start_time

        # Extract response content
        response_content = response.choices[0].message.content if response.choices else None
        if not response_content:
            logger.warning("ChatGPT Vision API returned empty response")
            return None

        # Parse JSON response
        import json
        result = json.loads(response_content)

        logger.info(f"ChatGPT Vision API analysis completed in {response_time:.2f}s")
        logger.info(f"Extracted color: {result.get('exact_color')}, material: {result.get('material')}, style: {result.get('style')}")

        return result

    except asyncio.TimeoutError:
        logger.warning("ChatGPT Vision API timeout - falling back to local extraction")
        return None
    except Exception as e:
        logger.warning(f"ChatGPT Vision API failed: {e} - falling back to local extraction")
        return None
```

**Vision API Parameters Explained**:
- **Model**: `settings.openai_model` (gpt-4-vision-preview or gpt-4o)
- **Temperature**: 0.3 (low temperature for factual, consistent analysis)
- **max_tokens**: 1000 (sufficient for detailed JSON response)
- **Timeout**: 30 seconds (prevents hanging on slow API calls)
- **max_retries**: 2 (automatically retries failed requests)
- **detail**: "high" (analyzes image at high resolution for better accuracy)
- **response_format**: JSON object (ensures structured response)

### 2. Modified Method: Integration with Fallback
**File**: `api/services/cloud_inpainting_service.py:324-390`

```python
# Extract product information
if product:
    product_name = product.get('full_name') or product.get('name', 'furniture')
    product_description = product.get('description', '')
else:
    product_name = prompt.split("with a ")[-1].split(" naturally")[0] if "with a " in prompt else "furniture"
    product_description = ''

# FIX 5: Try ChatGPT Vision API for enhanced product analysis (with fallback to local extraction)
vision_result = await self._generate_product_prompt_with_vision(
    product_image_url, product_name, product_description
)

if vision_result:
    # Use Vision API results
    logger.info("Using ChatGPT Vision API analysis for product prompt")
    exact_color = vision_result.get('exact_color', '')
    material = vision_result.get('material', '')
    texture = vision_result.get('texture', '')
    style = vision_result.get('style', '')
    design_details = vision_result.get('design_details', '')
    dimensions_str = vision_result.get('dimensions', '')

    # Build enhanced prompt from Vision API analysis
    focused_prompt = f"High resolution photography interior design, modern room with {product_name}"

    if exact_color:
        focused_prompt += f", {exact_color} color"
    if material:
        focused_prompt += f", {material} material"
    if texture:
        focused_prompt += f", {texture} texture"
    if style:
        focused_prompt += f", {style} style"
    if design_details:
        focused_prompt += f", {design_details}"
    if dimensions_str:
        focused_prompt += f", {dimensions_str}"

    focused_prompt += (
        f", professional interior photography, realistic lighting and shadows, "
        f"correct perspective and scale, seamless integration, high quality, "
        f"exact color match to reference image"
    )
else:
    # Fallback to local keyword extraction (FIX 2 & FIX 3)
    logger.info("Vision API unavailable - using local keyword extraction")

    # FIX 2: Extract color and material from product name for better matching
    color_descriptor = self._extract_color_descriptor(product_name)
    material_descriptor = self._extract_material_descriptor(product_name)

    # FIX 3: Extract dimensions from product description or use defaults
    dimensions_str = self._extract_dimensions_from_description(product_description, product_name)

    # Build enhanced product description with color, material, and dimensions
    enhanced_product_desc = product_name
    if color_descriptor:
        enhanced_product_desc = f"{color_descriptor} {enhanced_product_desc}"
    if material_descriptor and material_descriptor not in product_name.lower():
        enhanced_product_desc = f"{material_descriptor} {enhanced_product_desc}"

    # Build focused prompt for interior design with color, material, and dimensions
    focused_prompt = (
        f"High resolution photography interior design, modern room with {enhanced_product_desc}"
    )

    if dimensions_str:
        focused_prompt += f", {dimensions_str}"

    focused_prompt += (
        f", professional interior photography, realistic lighting and shadows, "
        f"correct perspective and scale, seamless integration, high quality, "
        f"exact color match to reference image"
    )

logger.info(f"Using enhanced prompt: {focused_prompt}")
logger.info(f"Product reference URL: {product_image_url}")
```

## Key Changes Summary

| Component | Before (FIX 2) | After (FIX 5) | Purpose |
|-----------|----------------|---------------|---------|
| Color Extraction | Keyword match from name | Vision API image analysis | Precise color identification |
| Material Extraction | Keyword match from name | Vision API texture analysis | Accurate material identification |
| Style Detection | ❌ Not detected | ✅ Vision API style classification | Design aesthetic matching |
| Design Details | ❌ Not extracted | ✅ Vision API detail extraction | Specific furniture characteristics |
| Texture Analysis | ❌ Not analyzed | ✅ Vision API surface analysis | Surface finish matching |
| Fallback | N/A | ✅ Falls back to FIX 2 & 3 | Ensures system always works |

## How Vision API and Fallback Work Together

### Processing Flow:

```
[Product Image URL] + [Product Name] + [Description]
            ↓
    [Vision API Call (GPT-4o)]
            ↓
    ┌───────┴───────┐
    ↓               ↓
SUCCESS         TIMEOUT/ERROR
    ↓               ↓
[Vision Result] [Return None]
    ↓               ↓
[Use Vision     [Fallback to
 Attributes]     FIX 2 & 3]
    ↓               ↓
[Enhanced       [Local Keyword
 Prompt]         Extraction]
    ↓               ↓
    └───────┬───────┘
            ↓
    [Final Prompt]
            ↓
    [Replicate API]
```

### Vision API Response Structure:

```json
{
  "exact_color": "sage green with subtle gray undertones",
  "secondary_colors": ["gray", "cream"],
  "material": "velvet",
  "material_details": "plush velvet upholstery with smooth finish",
  "texture": "soft, plush velvet with slight sheen",
  "style": "modern mid-century",
  "design_details": "track arms, tapered wooden legs, loose seat cushions, tight tufted back",
  "dimensions": "84 inches wide by 36 inches deep by 36 inches high",
  "size_category": "large",
  "enhanced_prompt": "modern mid-century sage green velvet sofa with track arms and tapered legs"
}
```

### Example Prompt Comparison:

**Before (FIX 2 - Local Extraction)**:
```
"High resolution photography interior design, modern room with green velvet
Sage Living Green Velvet Sofa, dimensions 84 inches wide by 36 inches deep
by 36 inches high, professional interior photography, realistic lighting and
shadows, correct perspective and scale, seamless integration, high quality,
exact color match to reference image"
```

**After (FIX 5 - Vision API)**:
```
"High resolution photography interior design, modern room with Sage Living
Green Velvet Sofa, sage green with subtle gray undertones color, plush velvet
upholstery material, soft plush velvet with slight sheen texture, modern
mid-century style, track arms, tapered wooden legs, loose seat cushions,
tight tufted back, 84 inches wide by 36 inches deep by 36 inches high,
professional interior photography, realistic lighting and shadows, correct
perspective and scale, seamless integration, high quality, exact color match
to reference image"
```

**Improvements**:
- Color: "green" → "sage green with subtle gray undertones"
- Material: "velvet" → "plush velvet upholstery"
- Texture: Not specified → "soft plush velvet with slight sheen"
- Style: Not specified → "modern mid-century"
- Design: Not specified → "track arms, tapered wooden legs, loose seat cushions, tight tufted back"

## Expected Improvements

### Color Accuracy
- **Before**: Generic color names from product title ("green", "blue", "brown")
- **After**: Precise color descriptions with undertones ("sage green with gray undertones", "navy blue with deep indigo tones")

### Material Identification
- **Before**: Single material keyword if present in name
- **After**: Detailed material description with finish details ("plush velvet upholstery", "genuine top-grain leather with distressed finish")

### Style and Design
- **Before**: No style information captured
- **After**: Design style classification + specific design details ("modern mid-century", "track arms", "tapered wooden legs")

### Visual Consistency
- **Before**: Prompts miss nuanced visual details
- **After**: Prompts include exact visual characteristics from image analysis

### Fallback Reliability
- **Before**: No fallback mechanism (local extraction was the only method)
- **After**: Graceful degradation to local extraction ensures system always works

## Integration with Existing Fixes

FIX 5 builds upon previous fixes:

1. **FIX 1 (IP-Adapter Scale 1.0)**: Vision API complements IP-Adapter by providing detailed prompt guidance
2. **FIX 2 (Color/Material Extraction)**: Used as fallback when Vision API unavailable
3. **FIX 3 (Dimension Extraction)**: Used as fallback for dimension information
4. **FIX 4 (Canny ControlNet)**: Vision API prompts guide furniture generation while Canny preserves room structure

**Combined Effect**:
- IP-Adapter (1.0): 100% visual feature matching
- Canny ControlNet (0.8): Room structure preservation
- Inpainting ControlNet (1.0): Precise furniture replacement
- Vision API Prompts: Detailed guidance for color, material, texture, style

## Testing

### Requirements:
- OpenAI API key configured in settings
- GPT-4o or gpt-4-vision-preview model access
- Backend server must reload with new code
- Internet connectivity for Vision API calls

### Verification Steps:

1. **Check Server Reload**:
   ```bash
   # Verify server has reloaded
   tail -f /path/to/server/logs
   # Look for: "Calling ChatGPT Vision API for product analysis"
   ```

2. **Test Visualization Request**:
   - Select a product with clear visual characteristics
   - Request visualization in a room
   - Monitor logs for Vision API call

3. **Check Logs for Vision API Usage**:
   ```
   INFO: Calling ChatGPT Vision API for product analysis: Green Velvet Sofa
   INFO: ChatGPT Vision API analysis completed in 2.45s
   INFO: Extracted color: sage green with subtle gray undertones, material: plush velvet, style: modern mid-century
   INFO: Using ChatGPT Vision API analysis for product prompt
   INFO: Using enhanced prompt: High resolution photography interior design, modern room with Green Velvet Sofa, sage green with subtle gray undertones color, plush velvet material...
   ```

4. **Test Fallback Mechanism**:
   - Temporarily disable OpenAI API key or simulate timeout
   - Verify fallback to local extraction occurs
   - Check logs for: "Vision API unavailable - using local keyword extraction"

5. **Compare Results**:
   - Generate visualization with Vision API (save result)
   - Disable Vision API and regenerate same product (fallback)
   - Compare color accuracy, material rendering, style consistency

### Performance Metrics:

Expected Vision API response times:
- **Success**: 2-5 seconds
- **Timeout**: 30 seconds (then falls back)
- **Total Impact**: +2-5s per visualization (acceptable for quality improvement)

### Test Cases:

1. **Standard Product with Clear Visuals**
   - Product: "Green Velvet Sofa" with high-quality image
   - Expected: Accurate color, material, style extraction

2. **Product with Subtle Colors**
   - Product: "Sage Living Room Chair" (not just "green")
   - Expected: Precise color identification ("sage green" not "green")

3. **Multi-Material Product**
   - Product: "Leather Sofa with Wooden Legs"
   - Expected: Multiple materials identified

4. **Complex Design Product**
   - Product: "Mid-Century Modern Tufted Chair"
   - Expected: Style + design details captured

5. **Vision API Timeout/Failure**
   - Scenario: API timeout or error
   - Expected: Graceful fallback to FIX 2 & 3 local extraction

## Files Modified

1. **`api/services/cloud_inpainting_service.py`**
   - Lines 756-897: Added `_generate_product_prompt_with_vision()` method
   - Lines 324-390: Modified `_run_ip_adapter_inpainting()` to integrate Vision API with fallback

## Dependencies

- **OpenAI Python SDK**: `openai>=1.0.0` (AsyncOpenAI client)
- **OpenAI API Key**: Must be configured in settings
- **Model Access**: GPT-4o or gpt-4-vision-preview
- **Asyncio**: For timeout management with `asyncio.wait_for()`
- **JSON**: For parsing Vision API structured responses

## Limitations and Considerations

1. **API Cost**: Vision API calls cost more than text-only API calls
   - GPT-4o Vision: ~$0.01-0.03 per image analysis
   - Cost-benefit: Improved visualization quality vs. API cost

2. **Latency**: Adds 2-5 seconds per visualization request
   - Acceptable trade-off for enhanced accuracy
   - Can be optimized with caching if same product used multiple times

3. **Fallback Behavior**: If Vision API unavailable, falls back to FIX 2 & 3
   - System continues to work but with reduced accuracy
   - Logs clearly indicate which method is used

4. **Image Quality Dependency**: Vision API accuracy depends on product image quality
   - High-resolution images: Better analysis
   - Low-quality images: May miss subtle details

5. **Rate Limits**: OpenAI API rate limits apply
   - Consider implementing rate limit handling
   - May need request queuing for high-traffic scenarios

## Rollback Plan

If Vision API integration causes issues, disable by modifying:

**File**: `api/services/cloud_inpainting_service.py:327-332`

```python
# Rollback: Skip Vision API call entirely
# vision_result = await self._generate_product_prompt_with_vision(
#     product_image_url, product_name, product_description
# )
vision_result = None  # Force fallback to local extraction

if vision_result:
    # This block will be skipped
    ...
else:
    # Always use local extraction (FIX 2 & 3)
    logger.info("Using local keyword extraction")
    ...
```

## Next Steps

1. ✅ Implement Vision API integration (COMPLETED)
2. ⏳ Wait for server reload with new code
3. ⏳ Test with real visualization request
4. ⏳ Verify Vision API returns accurate product attributes
5. ⏳ Monitor API response times and costs
6. ⏳ Compare visualization quality: Vision API vs. local extraction
7. ⏳ Fine-tune Vision API prompt if needed based on results
8. ⏳ Consider caching Vision API results for repeated product requests (optional optimization)

## Conclusion

FIX 5 addresses the limitations of local keyword extraction by leveraging ChatGPT Vision API to analyze actual product images. This multimodal approach ensures that:

- ✅ Exact colors with undertones are identified from images (not just keywords)
- ✅ Materials and textures are analyzed from visual cues
- ✅ Design styles and specific details are extracted
- ✅ Enhanced prompts provide detailed guidance to the AI inpainting model
- ✅ Fallback mechanism ensures system reliability
- ✅ Builds upon FIX 1-4 for comprehensive visualization quality improvement

**Combined Fixes Summary**:
- **FIX 1**: IP-Adapter Scale 1.0 → Exact product appearance matching
- **FIX 2**: Color/Material Extraction → Keyword-based metadata (fallback)
- **FIX 3**: Dimension Extraction → Size information (fallback)
- **FIX 4**: Canny ControlNet → Room structure preservation
- **FIX 5**: Vision API → Image-based detailed product analysis (primary)

The system now uses advanced computer vision to understand products and generate photorealistic visualizations with accurate colors, materials, textures, and styles.
