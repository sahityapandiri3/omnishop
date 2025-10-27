"""
Automated Test: Replace All Workflow
Tests the complete two-pass inpainting workflow:
1. Pass 1: Remove existing furniture from base image
2. Pass 2: Place new sofa in the cleaned image
"""
import asyncio
import base64
import json
import sys
from pathlib import Path

# Add api directory to path
sys.path.insert(0, str(Path(__file__).parent / "api"))

from api.services.cloud_inpainting_service import cloud_inpainting_service
from PIL import Image


def load_image_as_base64(image_path: str) -> str:
    """Load image and convert to base64 data URI"""
    with open(image_path, 'rb') as f:
        img_data = f.read()
    base64_str = base64.b64encode(img_data).decode('utf-8')
    return f"data:image/png;base64,{base64_str}"


async def test_replace_all_workflow():
    """Test the complete replace_all workflow"""
    print("=" * 80)
    print("AUTOMATED TEST: Replace All Workflow")
    print("=" * 80)

    # Step 1: Load base room image with existing sofas
    print("\n[1] Loading base room image...")
    base_image_path = input("Enter path to room image with sofas: ").strip()
    if not Path(base_image_path).exists():
        print(f"❌ Error: File not found: {base_image_path}")
        return

    base_image = load_image_as_base64(base_image_path)
    print(f"✅ Loaded base image: {Path(base_image_path).name}")

    # Step 2: Define new sofa product
    print("\n[2] Setting up new sofa product...")
    new_sofa = {
        "id": 401,
        "name": "Lumo Sofa  3 Seater  Polyfill cushions (7.5 feet)",
        "full_name": "Lumo Sofa  3 Seater  Polyfill cushions (7.5 feet)",
        "image_url": "https://example.com/sofa.jpg",  # Replace with actual URL
        "description": "Modern 3-seater sofa with polyfill cushions"
    }
    print(f"✅ Product: {new_sofa['name']}")

    # Step 3: Define existing furniture (detected sofas)
    print("\n[3] Defining existing furniture to remove...")
    existing_furniture = [
        {
            "object_type": "sofa",
            "bounding_box": {
                "x1": 0.0,
                "y1": 0.4,
                "x2": 0.5,
                "y2": 0.9
            },
            "confidence": 0.95
        },
        {
            "object_type": "sofa",
            "bounding_box": {
                "x1": 0.5,
                "y1": 0.5,
                "x2": 1.0,
                "y2": 0.9
            },
            "confidence": 0.93
        }
    ]
    print(f"✅ Defined {len(existing_furniture)} existing sofas to remove")

    # Step 4: Run replace_all workflow
    print("\n[4] Running replace_all workflow...")
    print("    This will take ~90-120 seconds (two Replicate API calls)")
    print("    Pass 1: Removing existing sofas...")
    print("    Pass 2: Placing new sofa...")
    print()

    try:
        result = await cloud_inpainting_service.inpaint_furniture(
            base_image=base_image,
            products_to_place=[new_sofa],
            existing_furniture=existing_furniture,
            user_action="replace_all"
        )

        # Step 5: Check result
        print("\n[5] Checking result...")
        if result.success:
            print("✅ Visualization completed successfully!")
            print(f"   Processing time: {result.processing_time:.2f}s")
            print(f"   Confidence score: {result.confidence_score}")

            # Save result
            output_path = "test_result_replace_all.png"

            # Decode base64 and save
            if result.rendered_image.startswith("data:image"):
                img_data = result.rendered_image.split(",")[1]
            else:
                img_data = result.rendered_image

            img_bytes = base64.b64decode(img_data)
            with open(output_path, 'wb') as f:
                f.write(img_bytes)

            print(f"✅ Result saved to: {output_path}")

            # Open result
            img = Image.open(output_path)
            print(f"   Image size: {img.size}")
            print("\n🎉 TEST PASSED!")

        else:
            print(f"❌ Visualization failed!")
            print(f"   Error: {result.error_message}")
            print("\n❌ TEST FAILED!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("\n❌ TEST FAILED!")


async def test_step_by_step():
    """Test Pass 1 and Pass 2 separately for debugging"""
    print("=" * 80)
    print("STEP-BY-STEP TEST: Two-Pass Workflow")
    print("=" * 80)

    # Load base image
    print("\n[1] Loading base room image...")
    base_image_path = input("Enter path to room image: ").strip()
    if not Path(base_image_path).exists():
        print(f"❌ Error: File not found: {base_image_path}")
        return

    base_image = load_image_as_base64(base_image_path)

    # Define existing furniture
    existing_furniture = [
        {
            "object_type": "sofa",
            "bounding_box": {"x1": 0.0, "y1": 0.4, "x2": 0.5, "y2": 0.9}
        },
        {
            "object_type": "sofa",
            "bounding_box": {"x1": 0.5, "y1": 0.5, "x2": 1.0, "y2": 0.9}
        }
    ]

    # Step 1: Test removal only
    print("\n[PASS 1] Testing furniture removal...")
    removal_result = await cloud_inpainting_service._remove_existing_furniture(
        room_image=cloud_inpainting_service._decode_base64_image(base_image),
        furniture_to_remove=existing_furniture,
        remove_all=True
    )

    if removal_result and removal_result.success:
        print("✅ Pass 1 successful!")

        # Save cleaned image
        cleaned_path = "test_pass1_cleaned.png"
        img_data = removal_result.rendered_image.split(",")[1] if "," in removal_result.rendered_image else removal_result.rendered_image
        with open(cleaned_path, 'wb') as f:
            f.write(base64.b64decode(img_data))
        print(f"✅ Cleaned image saved: {cleaned_path}")

    else:
        print("❌ Pass 1 failed!")
        return

    print("\n✅ STEP-BY-STEP TEST COMPLETE!")
    print("   Check test_pass1_cleaned.png to verify furniture removal")


if __name__ == "__main__":
    import sys

    print("\nSelect test mode:")
    print("1. Full workflow test (replace_all)")
    print("2. Step-by-step test (Pass 1 only)")

    choice = input("\nEnter choice (1 or 2): ").strip()

    if choice == "1":
        asyncio.run(test_replace_all_workflow())
    elif choice == "2":
        asyncio.run(test_step_by_step())
    else:
        print("Invalid choice!")
