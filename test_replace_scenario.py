"""
Automated Test for Replace Scenario
Tests the complete 3-step workflow and captures all intermediate results
"""
import asyncio
import aiohttp
import json
import base64
from pathlib import Path
from datetime import datetime
import os


API_BASE_URL = "http://localhost:8000"
TEST_IMAGE_PATH = "/Users/sahityapandiri/Omnishop/test_room_image.png"


def create_test_folder():
    """Create timestamped folder for test results"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_path = Path(f"/Users/sahityapandiri/Omnishop/test_results/replace_scenario_{timestamp}")
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def save_image(base64_data: str, filepath: Path):
    """Save base64 image to file"""
    if base64_data and base64_data.startswith('data:image'):
        # Remove data URL prefix
        base64_data = base64_data.split(',', 1)[1]

    image_bytes = base64.b64decode(base64_data)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    print(f"✓ Saved: {filepath.name}")


def save_json(data: dict, filepath: Path):
    """Save JSON data to file"""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✓ Saved: {filepath.name}")


def load_test_image():
    """Load test image as base64"""
    with open(TEST_IMAGE_PATH, 'rb') as f:
        image_bytes = f.read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:image/png;base64,{base64_image}"


async def test_replace_workflow():
    """
    Test the complete replace scenario workflow:
    1. Initial request: Get product recommendations
    2. Visualize request: Get ADD/REPLACE options
    3. Replace action: Generate visualization
    """
    print("\n" + "="*80)
    print("🧪 REPLACE SCENARIO TEST - Starting")
    print("="*80 + "\n")

    # Create results folder
    results_folder = create_test_folder()
    print(f"📁 Results folder: {results_folder}\n")

    # Load test image
    print("📷 Loading test image...")
    base64_image = load_test_image()
    print(f"✓ Loaded image from: {TEST_IMAGE_PATH}\n")

    # Save original test image
    save_image(base64_image, results_folder / "00_original_room_image.png")

    async with aiohttp.ClientSession() as session:

        # =================================================================
        # STEP 0: Create Chat Session
        # =================================================================
        print("─" * 80)
        print("STEP 0: Create Chat Session")
        print("─" * 80)

        async with session.post(
            f"{API_BASE_URL}/api/chat/sessions",
            json={}
        ) as response:
            session_data = await response.json()
            chat_session_id = session_data.get('session_id')
            print(f"✓ Created chat session: {chat_session_id}\n")

        # =================================================================
        # STEP 1: Initial Request - Get Product Recommendations
        # =================================================================
        print("─" * 80)
        print("STEP 1: Initial Request - Get Product Recommendations")
        print("─" * 80)

        step1_payload = {
            "message": "I want to replace the sofa in this room with a modern leather sofa",
            "image": base64_image
        }

        print("Sending initial request...")
        async with session.post(
            f"{API_BASE_URL}/api/chat/sessions/{chat_session_id}/messages",
            json=step1_payload
        ) as response:
            step1_data = await response.json()
            save_json(step1_data, results_folder / "01_step1_product_recommendations.json")

            print(f"Status: {response.status}")
            message_content = step1_data.get('message', {}).get('content', '')
            print(f"Response text preview: {message_content[:200]}...")

            # Extract recommendations
            recommendations = step1_data.get('recommended_products', [])
            print(f"\n✓ Received {len(recommendations)} product recommendations")

            if not recommendations:
                print("❌ ERROR: No product recommendations received!")
                return

            # Select a sectional or L-shaped sofa for better replacement testing
            selected_product = None

            # First try: Look for sectional or L-shaped sofas
            for product in recommendations:
                name_lower = product.get('name', '').lower()
                if 'swatch' in name_lower or 'sample' in name_lower:
                    continue
                if 'sectional' in name_lower or 'l-shaped' in name_lower:
                    selected_product = product
                    print(f"✓ Found sectional: {product.get('name')}")
                    break

            # Second try: Look for 2-seater sofas
            if not selected_product:
                for product in recommendations:
                    name_lower = product.get('name', '').lower()
                    if 'swatch' in name_lower or 'sample' in name_lower:
                        continue
                    if '2 seater' in name_lower or 'two seater' in name_lower:
                        selected_product = product
                        print(f"✓ Found 2-seater: {product.get('name')}")
                        break

            # Last resort: Take first non-swatch product
            if not selected_product:
                for product in recommendations:
                    name_lower = product.get('name', '').lower()
                    if 'swatch' in name_lower or 'sample' in name_lower:
                        print(f"⏭️  Skipping: {product.get('name')} (swatch/sample)")
                        continue
                    selected_product = product
                    break

            if not selected_product:
                print("❌ ERROR: No actual furniture products found (all are swatches)!")
                return
            selected_product_id = selected_product['id']
            print(f"\n📦 Selected Product:")
            print(f"   ID: {selected_product_id}")
            print(f"   Name: {selected_product['name']}")
            print(f"   Price: ${selected_product['price']}")

            # Save selected product info
            save_json(selected_product, results_folder / "02_selected_product.json")

        print("\n✓ STEP 1 COMPLETE\n")

        # =================================================================
        # STEP 2: Visualize Request - Get ADD/REPLACE Options
        # =================================================================
        print("─" * 80)
        print("STEP 2: Visualize Request - Detect Furniture & Get Options")
        print("─" * 80)

        step2_payload = {
            "message": "visualize",
            "image": base64_image,
            "selected_product_id": str(selected_product_id)
        }

        print("Sending visualize request...")
        async with session.post(
            f"{API_BASE_URL}/api/chat/sessions/{chat_session_id}/messages",
            json=step2_payload
        ) as response:
            step2_data = await response.json()
            save_json(step2_data, results_folder / "03_step2_furniture_detection.json")

            print(f"Status: {response.status}")
            print(f"Response text: {step2_data.get('content', '')[:200]}...")

            # Extract furniture detection results
            detected_furniture = step2_data.get('detected_furniture') or []
            similar_furniture = step2_data.get('similar_furniture_items') or []
            action_options = step2_data.get('action_options', [])
            requires_choice = step2_data.get('requires_action_choice', False)

            print(f"\n🔍 Furniture Detection Results:")
            print(f"   Detected furniture items: {len(detected_furniture)}")
            for item in detected_furniture:
                print(f"   - {item.get('furniture_type')}: confidence {item.get('confidence')}")

            print(f"\n🎯 Similar Furniture Items: {len(similar_furniture)}")
            for item in similar_furniture:
                print(f"   - {item.get('furniture_type')}")

            print(f"\n⚡ Action Options: {action_options}")
            print(f"   Requires choice: {requires_choice}")

            if not requires_choice:
                print("⚠️  WARNING: No action choice required - may indicate detection issue")

        print("\n✓ STEP 2 COMPLETE\n")

        # Small delay to ensure visualization is ready
        await asyncio.sleep(1)

        # =================================================================
        # STEP 3: Replace Action - Generate Visualization
        # =================================================================
        print("─" * 80)
        print("STEP 3: Replace Action - Generate Visualization")
        print("─" * 80)

        step3_payload = {
            "message": "replace",
            "image": base64_image,
            "selected_product_id": str(selected_product_id),
            "user_action": "replace"
        }

        print("Sending replace action request...")
        async with session.post(
            f"{API_BASE_URL}/api/chat/sessions/{chat_session_id}/messages",
            json=step3_payload
        ) as response:
            step3_data = await response.json()
            save_json(step3_data, results_folder / "04_step3_visualization_result.json")

            print(f"Status: {response.status}")
            message_content = step3_data.get('message', {}).get('content', '')
            print(f"Response text: {message_content[:200]}...")

            # Extract and save visualization image
            visualization_image = step3_data.get('message', {}).get('image_url')

            if visualization_image:
                print("\n🎨 Visualization Generated!")
                save_image(visualization_image, results_folder / "05_final_visualization.png")

                # Also check for any debug images in the response
                if 'debug_images' in step3_data:
                    debug_images = step3_data['debug_images']
                    print(f"\n🐛 Debug Images: {len(debug_images)}")
                    for idx, debug_img in enumerate(debug_images):
                        if 'image' in debug_img:
                            filename = debug_img.get('label', f'debug_{idx}').replace(' ', '_').lower()
                            save_image(debug_img['image'], results_folder / f"06_debug_{filename}.png")
            else:
                print("❌ ERROR: No visualization image received!")
                print(f"Response keys: {list(step3_data.keys())}")

        print("\n✓ STEP 3 COMPLETE\n")

    # =================================================================
    # FINAL SUMMARY
    # =================================================================
    print("="*80)
    print("✅ TEST COMPLETE")
    print("="*80)
    print(f"\n📁 All results saved to: {results_folder}")
    print("\n📄 Files created:")
    for file in sorted(results_folder.glob('*')):
        size_kb = file.stat().st_size / 1024
        print(f"   {file.name} ({size_kb:.1f} KB)")
    print("\n")


if __name__ == "__main__":
    try:
        asyncio.run(test_replace_workflow())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
