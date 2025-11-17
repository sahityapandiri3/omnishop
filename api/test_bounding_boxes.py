#!/usr/bin/env python3
"""
Test script to verify Google AI returns bounding boxes for furniture detection
"""
import asyncio
import json
import sys
import os

# Add api directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.google_ai_service import google_ai_service
from core.config import settings

# Sample room image (base64) - using a small test image
SAMPLE_ROOM_IMAGE = "/9j/4AAQSkZJRgABAQAASABIAAD/4QEMRXhpZgAATU0AKgAAAAgAAgEyAAIAAAAUAAAAJodpAAQAAAABAAAAOgAAAAAyMDI1OjA2OjEwIDA5OjM1OjQ3AAALkAMAAg"

async def test_furniture_detection():
    """Test furniture detection with bounding boxes"""
    print("=" * 80)
    print("TESTING GOOGLE AI FURNITURE DETECTION WITH BOUNDING BOXES")
    print("=" * 80)

    # Check API key
    if not settings.google_ai_api_key:
        print("❌ ERROR: Google AI API key not configured")
        return

    print(f"✓ Google AI API key configured: {settings.google_ai_api_key[:10]}...")
    print()

    # Use the sample image from the logs (room with sofas)
    # For now, let's create a minimal test case
    print("📸 Using sample room image from recent test...")

    # NOTE: In a real test, we'd read the actual image that was tested
    # For now, this is a placeholder to demonstrate the approach
    sample_image = "data:image/jpeg;base64," + SAMPLE_ROOM_IMAGE

    print("🔍 Calling detect_objects_in_room()...")
    try:
        objects = await google_ai_service.detect_objects_in_room(sample_image)

        print(f"\n✓ Detection completed! Found {len(objects)} objects")
        print()

        # Analyze the response
        print("=" * 80)
        print("DETECTED OBJECTS:")
        print("=" * 80)

        for idx, obj in enumerate(objects, 1):
            print(f"\n{idx}. {obj.get('object_type', 'unknown').upper()}")
            print(f"   Position: {obj.get('position', 'N/A')}")
            print(f"   Size: {obj.get('size', 'N/A')}")
            print(f"   Style: {obj.get('style', 'N/A')}")
            print(f"   Color: {obj.get('color', 'N/A')}")
            print(f"   Material: {obj.get('material', 'N/A')}")

            # CHECK FOR BOUNDING BOX
            bbox = obj.get('bounding_box')
            if bbox:
                print(f"   ✓ Bounding box: {bbox}")

                # Validate bounding box
                if all(key in bbox for key in ['x1', 'y1', 'x2', 'y2']):
                    x1, y1, x2, y2 = bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']

                    # Check if coordinates are valid (non-zero and properly ordered)
                    if x1 >= x2 or y1 >= y2:
                        print(f"   ⚠️  WARNING: Invalid bounding box (x1={x1}, y1={y1}, x2={x2}, y2={y2})")
                    elif x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
                        print(f"   ⚠️  WARNING: Zero bounding box")
                    else:
                        width = x2 - x1
                        height = y2 - y1
                        print(f"   ✓ Valid bounding box! Width: {width:.2f}, Height: {height:.2f}")
                else:
                    print(f"   ⚠️  WARNING: Bounding box missing required keys")
            else:
                print(f"   ❌ ERROR: No bounding box returned!")

        print()
        print("=" * 80)
        print("SUMMARY:")
        print("=" * 80)

        objects_with_bbox = sum(1 for obj in objects if obj.get('bounding_box'))
        valid_bboxes = 0
        for obj in objects:
            bbox = obj.get('bounding_box')
            if bbox and all(key in bbox for key in ['x1', 'y1', 'x2', 'y2']):
                x1, y1, x2, y2 = bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']
                if not (x1 >= x2 or y1 >= y2 or (x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0)):
                    valid_bboxes += 1

        print(f"Total objects detected: {len(objects)}")
        print(f"Objects with bounding boxes: {objects_with_bbox}")
        print(f"Objects with VALID bounding boxes: {valid_bboxes}")

        if valid_bboxes == len(objects):
            print("\n✅ SUCCESS: All objects have valid bounding boxes!")
        elif objects_with_bbox == 0:
            print("\n❌ FAILURE: No bounding boxes returned at all")
        else:
            print(f"\n⚠️  PARTIAL SUCCESS: {valid_bboxes}/{len(objects)} objects have valid bounding boxes")

        # Print full JSON for debugging
        print()
        print("=" * 80)
        print("FULL JSON RESPONSE:")
        print("=" * 80)
        print(json.dumps(objects, indent=2))

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Close the session
        await google_ai_service.close()

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("BOUNDING BOX DETECTION TEST")
    print("=" * 80 + "\n")

    print("NOTE: This test requires a real room image.")
    print("Please update SAMPLE_ROOM_IMAGE with an actual base64 encoded image.")
    print()

    # Run the test
    asyncio.run(test_furniture_detection())
