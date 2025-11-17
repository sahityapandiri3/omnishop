"""
Test Replace Workflow - Automated test for furniture replacement using Gemini 2.5 Flash Image
"""
import asyncio
import aiohttp
import base64
import json
from pathlib import Path
import sys

# Test configuration
API_BASE_URL = "http://localhost:8000"
TEST_IMAGE_PATH = "test_room_image.png"  # Room with existing furniture


async def load_test_image(image_path: str) -> str:
    """Load and encode test image as base64 data URI"""
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            return f"data:image/png;base64,{image_base64}"
    except FileNotFoundError:
        print(f"❌ Test image not found: {image_path}")
        print("Please ensure you have a test room image with furniture")
        sys.exit(1)


async def test_replace_workflow():
    """Test complete replace workflow with Gemini visualization"""

    print("=" * 80)
    print("🧪 REPLACE WORKFLOW TEST - Gemini 2.5 Flash Image")
    print("=" * 80)

    async with aiohttp.ClientSession() as session:

        # Step 0: Fetch available products to get a real product ID
        print("\n📦 Step 0: Fetching available products...")
        async with session.get(f"{API_BASE_URL}/api/products/?page=1&size=10") as response:
            if response.status != 200:
                print(f"❌ Failed to fetch products: {response.status}")
                error_text = await response.text()
                print(f"Error: {error_text}")
                return False

            products_data = await response.json()
            products = products_data.get("items", [])

            if not products:
                print("⚠️  No products found in database")
                return False

            # Find a sofa/couch product, or use first product
            test_product = None
            for product in products:
                name_lower = product.get("name", "").lower()
                if any(keyword in name_lower for keyword in ["sofa", "couch", "sectional"]):
                    test_product = product
                    break

            if not test_product:
                print("⚠️  No sofa products found, using first product")
                test_product = products[0]

            test_product_id = test_product.get("id")
            test_product_name = test_product.get("name")
            print(f"✅ Using product: {test_product_name} (ID: {test_product_id})")

        # Step 1: Create chat session
        print("\n📝 Step 1: Creating chat session...")
        async with session.post(f"{API_BASE_URL}/api/chat/sessions", json={}) as response:
            if response.status != 200:
                print(f"❌ Failed to create session: {response.status}")
                return False

            session_data = await response.json()
            session_id = session_data["session_id"]
            print(f"✅ Session created: {session_id}")

        # Step 2: Load test image
        print("\n🖼️  Step 2: Loading test room image...")
        test_image = await load_test_image(TEST_IMAGE_PATH)
        print(f"✅ Image loaded ({len(test_image)} characters)")

        # Step 3: Send message with image and selected product
        print("\n📤 Step 3: Sending product selection with image...")
        print(f"   - Message: 'I want to replace my sofa with this one'")
        print(f"   - Product ID: {test_product_id} ({test_product_name})")
        print("   - Including room image for furniture detection")

        message_payload = {
            "message": "I want to replace my sofa with this one",
            "image": test_image,
            "selected_product_id": str(test_product_id)
        }

        async with session.post(
            f"{API_BASE_URL}/api/chat/sessions/{session_id}/messages",
            json=message_payload
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"❌ Failed to send message: {response.status}")
                print(f"Error: {error_text}")
                return False

            message_response = await response.json()
            print(f"✅ Message sent successfully")

        # Step 4: Verify furniture detection and action options
        print("\n🔍 Step 4: Verifying furniture detection and action options...")

        detected_furniture = message_response.get("detected_furniture", [])
        action_options = message_response.get("action_options", {})
        requires_action_choice = message_response.get("requires_action_choice", False)

        print(f"   - Detected furniture: {len(detected_furniture)} items")
        for idx, furniture in enumerate(detected_furniture, 1):
            print(f"     {idx}. {furniture.get('object_type', 'unknown')} at {furniture.get('position', 'unknown')}")

        if not action_options:
            print("❌ No action options returned")
            return False

        print(f"\n   - Action options available:")
        if action_options.get('add', {}).get('available'):
            print(f"     A. ADD - {action_options['add'].get('description', 'N/A')}")
        if action_options.get('replace', {}).get('available'):
            replace_count = action_options['replace'].get('count', 0)
            print(f"     B. REPLACE - {action_options['replace'].get('description', 'N/A')}")
            print(f"        Found {replace_count} existing item(s) to replace")

        if not action_options.get('replace', {}).get('available'):
            print("⚠️  REPLACE option not available - skipping replace test")
            print("    This might mean no similar furniture was detected in the room")
            return False

        print(f"\n   - Requires action choice: {requires_action_choice}")
        print("✅ Furniture detection and action options verified")

        # Step 5: Send letter "B" to trigger REPLACE action
        print("\n🔤 Step 5: Sending letter 'B' to trigger REPLACE...")

        replace_payload = {
            "message": "B"
        }

        async with session.post(
            f"{API_BASE_URL}/api/chat/sessions/{session_id}/messages",
            json=replace_payload
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"❌ Failed to send replace choice: {response.status}")
                print(f"Error: {error_text}")
                return False

            replace_response = await response.json()
            print(f"✅ Replace choice sent successfully")

        # Step 6: Verify visualization was generated
        print("\n🎨 Step 6: Verifying Gemini visualization generation...")

        message = replace_response.get("message", {})
        visualization_image = message.get("image_url")
        response_content = message.get("content", "")

        print(f"   - Response: {response_content[:100]}...")

        if not visualization_image:
            print("❌ No visualization image returned")
            return False

        if not visualization_image.startswith("data:image"):
            print("❌ Invalid image format")
            return False

        # Save visualization for inspection
        print(f"\n💾 Saving visualization image...")
        try:
            # Extract base64 data
            image_data = visualization_image.split(',')[1]
            image_bytes = base64.b64decode(image_data)

            output_path = Path("test_results") / "replace_visualization_gemini.png"
            output_path.parent.mkdir(exist_ok=True)

            with open(output_path, 'wb') as f:
                f.write(image_bytes)

            print(f"✅ Visualization saved to: {output_path}")
            print(f"   - Size: {len(image_bytes)} bytes")
        except Exception as e:
            print(f"⚠️  Failed to save image: {e}")

        # Step 7: Verify it used Gemini (check response content)
        print("\n🤖 Step 7: Verifying Gemini was used...")

        if "AI" in response_content or "generated" in response_content.lower():
            print("✅ Response indicates AI-generated visualization")
        else:
            print("⚠️  Response doesn't clearly indicate AI generation")

        print("\n" + "=" * 80)
        print("✅ REPLACE WORKFLOW TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print("\nTest Summary:")
        print(f"  - Session ID: {session_id}")
        print(f"  - Furniture detected: {len(detected_furniture)} items")
        print(f"  - Action chosen: REPLACE")
        print(f"  - Visualization method: Gemini 2.5 Flash Image")
        print(f"  - Output saved: {output_path}")
        print("\nNext steps:")
        print("  1. Open the saved image to verify quality")
        print("  2. Check if existing furniture was removed")
        print("  3. Verify new furniture placement")

        return True


async def test_replace_with_specific_product():
    """Test replace with a specific product from database"""

    print("\n" + "=" * 80)
    print("🧪 EXTENDED TEST: Replace with Database Product")
    print("=" * 80)

    async with aiohttp.ClientSession() as session:

        # Get available products first
        print("\n📦 Fetching available products...")
        async with session.get(f"{API_BASE_URL}/api/products?page=1&size=10") as response:
            if response.status != 200:
                print(f"❌ Failed to fetch products: {response.status}")
                return False

            products_data = await response.json()
            products = products_data.get("items", [])

            if not products:
                print("⚠️  No products found in database")
                return False

            # Find a sofa/couch product
            sofa_product = None
            for product in products:
                name_lower = product.get("name", "").lower()
                if any(keyword in name_lower for keyword in ["sofa", "couch", "sectional"]):
                    sofa_product = product
                    break

            if not sofa_product:
                print("⚠️  No sofa products found, using first product")
                sofa_product = products[0]

            print(f"✅ Using product: {sofa_product.get('name')} (ID: {sofa_product.get('id')})")

        # Now run the test with this product
        print(f"\n🔄 Running replace test with product ID {sofa_product.get('id')}...")

        # Create session
        async with session.post(f"{API_BASE_URL}/api/chat/sessions", json={}) as response:
            session_data = await response.json()
            session_id = session_data["session_id"]

        # Load image
        test_image = await load_test_image(TEST_IMAGE_PATH)

        # Send with product
        message_payload = {
            "message": f"I want to replace my sofa with the {sofa_product.get('name')}",
            "image": test_image,
            "selected_product_id": str(sofa_product.get("id"))
        }

        async with session.post(
            f"{API_BASE_URL}/api/chat/sessions/{session_id}/messages",
            json=message_payload
        ) as response:
            message_response = await response.json()

        # Check for action options
        action_options = message_response.get("action_options", {})

        if action_options.get('replace', {}).get('available'):
            print("✅ Replace option available, sending 'B'...")

            async with session.post(
                f"{API_BASE_URL}/api/chat/sessions/{session_id}/messages",
                json={"message": "B"}
            ) as response:
                replace_response = await response.json()

                visualization = replace_response.get("message", {}).get("image_url")
                if visualization:
                    print("✅ Visualization generated successfully!")

                    # Save with product name
                    image_data = visualization.split(',')[1]
                    image_bytes = base64.b64decode(image_data)

                    safe_name = sofa_product.get('name', 'product').replace(' ', '_')[:30]
                    output_path = Path("test_results") / f"replace_{safe_name}_gemini.png"
                    output_path.parent.mkdir(exist_ok=True)

                    with open(output_path, 'wb') as f:
                        f.write(image_bytes)

                    print(f"💾 Saved to: {output_path}")
                    return True

        return False


async def main():
    """Run all replace workflow tests"""

    print("\n🚀 Starting Replace Workflow Tests")
    print("=" * 80)

    # Check if test image exists
    if not Path(TEST_IMAGE_PATH).exists():
        print(f"\n⚠️  Test image not found: {TEST_IMAGE_PATH}")
        print("Creating a placeholder message...")
        print("\nTo run this test, you need:")
        print("  1. A room image with furniture (preferably with a sofa)")
        print(f"  2. Save it as '{TEST_IMAGE_PATH}' in the current directory")
        print("  3. Ensure the backend is running on http://localhost:8000")
        print("  4. Database has at least one product")
        return

    # Test 1: Basic replace workflow
    success1 = await test_replace_workflow()

    if success1:
        # Test 2: Replace with specific product
        await asyncio.sleep(2)  # Brief pause between tests
        success2 = await test_replace_with_specific_product()

    print("\n" + "=" * 80)
    print("🏁 ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
