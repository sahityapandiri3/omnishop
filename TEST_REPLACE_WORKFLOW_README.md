# Replace Workflow Test - README

## Overview
Automated test for the furniture replacement workflow using Google Gemini 2.5 Flash Image.

## Test File
`test_replace_workflow.py`

## What This Test Does

### Test 1: Basic Replace Workflow
1. Creates a chat session
2. Uploads a room image with a selected product ID
3. Verifies furniture detection using Gemini 2.0 Flash Exp
4. Checks that Add/Replace action options are presented
5. Sends letter "B" to trigger REPLACE action
6. Verifies Gemini 2.5 Flash Image generates visualization
7. Saves the output image for manual inspection

### Test 2: Replace with Specific Product
1. Fetches available products from database
2. Finds a sofa/couch product (or uses first product)
3. Runs complete replace workflow with that product
4. Saves visualization with product name in filename

## Prerequisites

### 1. Servers Running
```bash
# Backend (in /api directory)
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (in /frontend directory)
npm run dev
```

### 2. Test Room Image
You need a room image with furniture (preferably with a sofa). Save it as:
```
test_room_image.png
```

**Good test images have:**
- Clear view of furniture (especially sofas, chairs, tables)
- Good lighting
- Minimal clutter
- At least 1 piece of furniture that can be replaced

**Recommended sources:**
- Interior design websites
- Stock photo sites
- Your own room photos

### 3. Database with Products
Ensure your database has at least one product:
```bash
# Check products
curl http://localhost:8000/api/products?page=1&size=10
```

## How to Run

### Quick Start
```bash
# Make sure you're in the Omnishop directory
cd /Users/sahityapandiri/Omnishop

# Place your test image
# (copy a room image and name it test_room_image.png)

# Run the test
python3 test_replace_workflow.py
```

### Expected Output
```
================================================================================
🧪 REPLACE WORKFLOW TEST - Gemini 2.5 Flash Image
================================================================================

📝 Step 1: Creating chat session...
✅ Session created: abc-123-def

🖼️  Step 2: Loading test room image...
✅ Image loaded (123456 characters)

📤 Step 3: Sending product selection with image...
   - Message: 'I want to replace my sofa with this one'
   - Product ID: 1
   - Including room image for furniture detection
✅ Message sent successfully

🔍 Step 4: Verifying furniture detection and action options...
   - Detected furniture: 3 items
     1. sofa at center-left
     2. coffee_table at center
     3. lamp at right-foreground

   - Action options available:
     A. ADD - Add furniture to the room alongside existing furniture
     B. REPLACE - Replace 1 existing furniture item(s)
        Found 1 existing item(s) to replace

   - Requires action choice: True
✅ Furniture detection and action options verified

🔤 Step 5: Sending letter 'B' to trigger REPLACE...
✅ Replace choice sent successfully

🎨 Step 6: Verifying Gemini visualization generation...
   - Response: Great choice! I've generated a visualization replacing existing furniture in your room using AI....

💾 Saving visualization image...
✅ Visualization saved to: test_results/replace_visualization_gemini.png
   - Size: 234567 bytes

🤖 Step 7: Verifying Gemini was used...
✅ Response indicates AI-generated visualization

================================================================================
✅ REPLACE WORKFLOW TEST COMPLETED SUCCESSFULLY!
================================================================================

Test Summary:
  - Session ID: abc-123-def
  - Furniture detected: 3 items
  - Action chosen: REPLACE
  - Visualization method: Gemini 2.5 Flash Image
  - Output saved: test_results/replace_visualization_gemini.png

Next steps:
  1. Open the saved image to verify quality
  2. Check if existing furniture was removed
  3. Verify new furniture placement
```

## Output Files

Test results are saved in:
```
test_results/
├── replace_visualization_gemini.png       # Basic test output
└── replace_ProductName_gemini.png         # Product-specific test output
```

## Verification Checklist

After running the test, manually verify:

### ✅ Furniture Detection
- [ ] Correct number of furniture items detected
- [ ] Furniture types correctly identified
- [ ] Positions accurately described

### ✅ Action Options
- [ ] Both Add and Replace options available (if similar furniture exists)
- [ ] Replace option shows correct count of items to replace
- [ ] Options formatted as "A" and "B"

### ✅ Gemini Visualization
- [ ] Image generated successfully (not the original)
- [ ] Existing furniture appears removed
- [ ] New furniture placed at similar location
- [ ] Realistic lighting and shadows
- [ ] Product matches reference image
- [ ] Room elements preserved (walls, floor, windows)

### ✅ Quality Metrics
- [ ] Processing time < 30 seconds
- [ ] Image quality is photorealistic
- [ ] No artifacts or distortions
- [ ] Proper perspective and scale

## Troubleshooting

### Test image not found
```
⚠️  Test image not found: test_room_image.png
```
**Solution:** Place a room image at the project root and name it `test_room_image.png`

### No products in database
```
⚠️  No products found in database
```
**Solution:** Run scrapers to populate database or use test data

### Replace option not available
```
⚠️  REPLACE option not available - skipping replace test
```
**Reason:** No similar furniture detected in the room
**Solution:** Use a room image with more furniture, or try a different product type

### Furniture detection fails
```
❌ No action options returned
```
**Solution:**
- Check that Gemini 2.0 Flash Exp API is working
- Verify image quality (should show furniture clearly)
- Check server logs for errors

### Visualization fails
```
❌ No visualization image returned
```
**Solution:**
- Check that Gemini 2.5 Flash Image API is working
- Verify Google AI API key is set
- Check server logs for detailed error messages
- Ensure product has a valid image URL

## Test Customization

### Use Different Product ID
Edit `test_replace_workflow.py` line 56:
```python
"selected_product_id": "123"  # Change to your product ID
```

### Use Different Image
Change the image path in line 8:
```python
TEST_IMAGE_PATH = "my_custom_room.png"
```

### Adjust Timeouts
The test uses default HTTP timeout of 200 seconds. To change:
```python
# In test file, around line 115
async with session.post(..., timeout=aiohttp.ClientTimeout(total=300)) as response:
```

## Integration with CI/CD

To run this test in automated pipelines:

```bash
# Run with error handling
python3 test_replace_workflow.py && echo "✅ Test passed" || echo "❌ Test failed"

# Check exit code
python3 test_replace_workflow.py
if [ $? -eq 0 ]; then
    echo "Replace workflow test PASSED"
else
    echo "Replace workflow test FAILED"
    exit 1
fi
```

## Related Tests

- `test_complete_visualization_workflow.py` - Full visualization workflow test
- `test_comprehensive_workflow.py` - Comprehensive system test
- Individual unit tests in `api/tests/`

## Support

If you encounter issues:
1. Check server logs: `tail -f api/logs/app.log`
2. Verify API connectivity: `curl http://localhost:8000/health`
3. Test Gemini API: `python3 -c "from api.services.google_ai_service import google_ai_service; import asyncio; asyncio.run(google_ai_service.health_check())"`
