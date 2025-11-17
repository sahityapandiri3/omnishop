# Complete Visualization Workflow - Automated Test

## Overview

This automated test validates the entire furniture visualization pipeline from start to finish.

## Quick Start

### 1. Prepare Test Image

Save your room image to:
```
/Users/sahityapandiri/Omnishop/test_room_image.jpg
```

### 2. Run the Test

```bash
cd /Users/sahityapandiri/Omnishop
python3 test_complete_visualization_workflow.py
```

## What the Test Does

1. **Load Room Image** - Loads the test room image
2. **Create Session** - Creates new chat session
3. **Analyze & Suggest** - Sends "suggest sofas" prompt with image
4. **Select Product** - Automatically selects first recommended sofa
5. **Generate Visualization** - Creates visualization (1-2 minutes)
6. **Verify Quality** - Checks output meets criteria
7. **Save Results** - Saves visualization and test results

## Expected Output

The test will show colored progress messages and save:

- `test_results/visualization_XXXXXXXXXX.jpg` - Generated image
- `test_results/test_results_XXXXXXXXXX.json` - Test results

## Manual Verification Required

After the test completes, open the generated image and verify:

- [ ] Room structure preserved (walls, floor, windows)
- [ ] Original furniture completely removed
- [ ] New sofa placed correctly with proper scale
- [ ] Product matches reference image (color, material, style)

## Troubleshooting

### Test Image Not Found
```bash
cp /path/to/your/room/image.jpg /Users/sahityapandiri/Omnishop/test_room_image.jpg
```

### Server Not Running
Make sure API server is running on port 8000:
```bash
curl http://localhost:8000/health
```

### Check Server Logs
Look for these log messages to verify all fixes are active:
- "Running Private MajicMIX Deployment (IP-Adapter + Inpainting + Canny ControlNet)"
- "Generated Canny edge map"
- "Calling ChatGPT Vision API for product analysis"
- "Replicate prediction status: succeeded"

## Test Duration

Typical execution time: 2-4 minutes

- Analysis: ~30-40 seconds
- Visualization: ~90-180 seconds
- Other steps: <5 seconds
