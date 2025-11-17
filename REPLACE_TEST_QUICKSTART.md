# Replace Workflow Test - Quick Start Guide

## What You Need

1. **A room image with furniture** - Save as `test_room_image.png`
2. **Backend server running** - Port 8000
3. **Products in database** - At least one product

## Run the Test

```bash
# Step 1: Make sure you have a test image
# Place a room image (with sofa/furniture) as test_room_image.png

# Step 2: Run the test
python3 test_replace_workflow.py
```

## What the Test Does

1. ✅ Creates chat session
2. ✅ Uploads room image with product selection
3. ✅ Detects furniture using Gemini 2.0 Flash Exp
4. ✅ Presents Add/Replace options (A/B)
5. ✅ Sends letter "B" to trigger REPLACE
6. ✅ Generates visualization using **Gemini 2.5 Flash Image**
7. ✅ Saves output to `test_results/replace_visualization_gemini.png`

## Expected Flow

```
User: [Uploads room image + selects product ID]
System: Detects 3 furniture items
        - sofa at center-left
        - coffee_table at center
        - lamp at right

System: Presents options:
        A. ADD - Add furniture alongside existing
        B. REPLACE - Replace 1 existing sofa

User: Types "B"
System: ✨ Generates visualization using Gemini
        - Removes old sofa
        - Places new sofa at same location
        - Preserves all other room elements

Result: New image saved with replaced furniture!
```

## Test Output

The test will save:
- `test_results/replace_visualization_gemini.png` - Generated visualization
- Console output showing all test steps

## Verification

Open the generated image and check:
- [ ] Old furniture removed
- [ ] New furniture placed correctly
- [ ] Room walls/floor preserved
- [ ] Realistic lighting
- [ ] Proper scale and perspective

## Full Documentation

See `TEST_REPLACE_WORKFLOW_README.md` for detailed information.
