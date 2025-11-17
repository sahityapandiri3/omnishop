"""
Integration tests for Add and Replace product functionality

Tests the current implementation's ability to:
1. Add products to a room
2. Replace products in a room
3. Handle multiple products
4. Undo/redo operations
"""
import requests
import json
import time
from pathlib import Path

API_BASE_URL = "http://localhost:8000"


class TestAddReplaceIntegration:
    """Integration tests for add/replace product functionality"""

    def __init__(self):
        self.session_id = None
        self.test_room_image = None
        self.test_results = []

    def setup(self):
        """Setup test environment"""
        print("=" * 80)
        print("SETTING UP TEST ENVIRONMENT")
        print("=" * 80)

        # Create a new chat session
        print("\n1. Creating new chat session...")
        response = requests.post(f"{API_BASE_URL}/api/chat/sessions", json={})
        if response.status_code == 200:
            self.session_id = response.json()["session_id"]
            print(f"✓ Session created: {self.session_id}")
        else:
            raise Exception(f"Failed to create session: {response.text}")

        # Find a test room image
        print("\n2. Looking for test room image...")
        room_images = list(Path("/Users/sahityapandiri/Omnishop/test_results").rglob("*room*.jpg"))
        if not room_images:
            room_images = list(Path("/Users/sahityapandiri/Omnishop/test_results").rglob("*.jpg"))

        if room_images:
            self.test_room_image = str(room_images[0])
            print(f"✓ Using test image: {self.test_room_image}")
        else:
            print("⚠ No test room image found, will use URL")
            self.test_room_image = "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace"

    def test_1_add_first_product(self):
        """Test adding the first product to a room"""
        print("\n" + "=" * 80)
        print("TEST 1: ADD FIRST PRODUCT TO ROOM")
        print("=" * 80)

        # Search for a sofa
        print("\n1. Searching for sofas...")
        response = requests.post(
            f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/messages",
            json={"message": "Show me modern sofas"}
        )

        if response.status_code != 200:
            print(f"✗ Search failed: {response.text}")
            self.test_results.append(("Add First Product - Search", False, response.text))
            return False

        data = response.json()
        products = data.get("products", [])

        if not products:
            print("✗ No products found")
            self.test_results.append(("Add First Product - Search", False, "No products found"))
            return False

        print(f"✓ Found {len(products)} sofas")
        first_product = products[0]
        print(f"  - Selected: {first_product.get('name', 'Unknown')}")

        # Visualize the product
        print("\n2. Adding product to room...")
        viz_response = requests.post(
            f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualize",
            json={
                "room_image_path": self.test_room_image,
                "product_id": first_product["id"],
                "product_name": first_product.get("name", "Sofa"),
                "product_image_url": first_product.get("primary_image_url", "")
            }
        )

        if viz_response.status_code != 200:
            print(f"✗ Visualization failed: {viz_response.text}")
            self.test_results.append(("Add First Product - Visualize", False, viz_response.text))
            return False

        viz_data = viz_response.json()

        if not viz_data.get("visualization"):
            print("✗ No visualization data returned")
            self.test_results.append(("Add First Product - Visualize", False, "No visualization data"))
            return False

        rendered_image = viz_data["visualization"].get("rendered_image")
        print(f"✓ Product added successfully")
        print(f"  - Rendered image: {rendered_image}")
        print(f"  - Can undo: {viz_data.get('can_undo', False)}")
        print(f"  - Can redo: {viz_data.get('can_redo', False)}")

        self.test_results.append(("Add First Product", True, "Success"))
        return True

    def test_2_add_second_product(self):
        """Test adding a second product to the same room"""
        print("\n" + "=" * 80)
        print("TEST 2: ADD SECOND PRODUCT TO SAME ROOM")
        print("=" * 80)

        # Search for a center table
        print("\n1. Searching for center tables...")
        response = requests.post(
            f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/messages",
            json={"message": "Show me center tables"}
        )

        if response.status_code != 200:
            print(f"✗ Search failed: {response.text}")
            self.test_results.append(("Add Second Product - Search", False, response.text))
            return False

        data = response.json()
        products = data.get("products", [])

        if not products:
            print("✗ No products found")
            self.test_results.append(("Add Second Product - Search", False, "No products found"))
            return False

        print(f"✓ Found {len(products)} center tables")
        second_product = products[0]
        print(f"  - Selected: {second_product.get('name', 'Unknown')}")

        # Get current session state to find room image
        print("\n2. Getting current visualization state...")
        session_response = requests.get(f"{API_BASE_URL}/api/chat/sessions/{self.session_id}")

        if session_response.status_code != 200:
            print(f"✗ Failed to get session: {session_response.text}")
            self.test_results.append(("Add Second Product - Get State", False, session_response.text))
            return False

        # Visualize the second product
        print("\n3. Adding second product to room...")
        viz_response = requests.post(
            f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualize",
            json={
                "room_image_path": self.test_room_image,
                "product_id": second_product["id"],
                "product_name": second_product.get("name", "Center Table"),
                "product_image_url": second_product.get("primary_image_url", "")
            }
        )

        if viz_response.status_code != 200:
            print(f"✗ Visualization failed: {viz_response.text}")
            self.test_results.append(("Add Second Product - Visualize", False, viz_response.text))
            return False

        viz_data = viz_response.json()

        if not viz_data.get("visualization"):
            print("✗ No visualization data returned")
            self.test_results.append(("Add Second Product - Visualize", False, "No visualization data"))
            return False

        rendered_image = viz_data["visualization"].get("rendered_image")
        print(f"✓ Second product added successfully")
        print(f"  - Rendered image: {rendered_image}")
        print(f"  - Can undo: {viz_data.get('can_undo', False)}")
        print(f"  - Can redo: {viz_data.get('can_redo', False)}")

        self.test_results.append(("Add Second Product", True, "Success"))
        return True

    def test_3_replace_product(self):
        """Test replacing an existing product"""
        print("\n" + "=" * 80)
        print("TEST 3: REPLACE EXISTING PRODUCT")
        print("=" * 80)

        # Search for a different sofa
        print("\n1. Searching for replacement sofa...")
        response = requests.post(
            f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/messages",
            json={"message": "Show me leather sofas"}
        )

        if response.status_code != 200:
            print(f"✗ Search failed: {response.text}")
            self.test_results.append(("Replace Product - Search", False, response.text))
            return False

        data = response.json()
        products = data.get("products", [])

        if not products:
            print("✗ No replacement products found")
            self.test_results.append(("Replace Product - Search", False, "No products found"))
            return False

        print(f"✓ Found {len(products)} leather sofas")
        replacement_product = products[0]
        print(f"  - Selected: {replacement_product.get('name', 'Unknown')}")

        # Replace the existing sofa
        print("\n2. Replacing existing sofa with new one...")
        viz_response = requests.post(
            f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualize",
            json={
                "room_image_path": self.test_room_image,
                "product_id": replacement_product["id"],
                "product_name": replacement_product.get("name", "Leather Sofa"),
                "product_image_url": replacement_product.get("primary_image_url", ""),
                "detected_furniture_type": "sofa"  # This should trigger replacement
            }
        )

        if viz_response.status_code != 200:
            print(f"✗ Replacement failed: {viz_response.text}")
            self.test_results.append(("Replace Product - Visualize", False, viz_response.text))
            return False

        viz_data = viz_response.json()

        if not viz_data.get("visualization"):
            print("✗ No visualization data returned")
            self.test_results.append(("Replace Product - Visualize", False, "No visualization data"))
            return False

        rendered_image = viz_data["visualization"].get("rendered_image")
        print(f"✓ Product replaced successfully")
        print(f"  - Rendered image: {rendered_image}")
        print(f"  - Can undo: {viz_data.get('can_undo', False)}")
        print(f"  - Can redo: {viz_data.get('can_redo', False)}")

        self.test_results.append(("Replace Product", True, "Success"))
        return True

    def test_4_undo_operation(self):
        """Test undo functionality"""
        print("\n" + "=" * 80)
        print("TEST 4: UNDO LAST OPERATION")
        print("=" * 80)

        print("\n1. Performing undo...")
        undo_response = requests.post(
            f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualization/undo"
        )

        if undo_response.status_code != 200:
            print(f"✗ Undo failed: {undo_response.text}")
            self.test_results.append(("Undo Operation", False, undo_response.text))
            return False

        undo_data = undo_response.json()

        if not undo_data.get("visualization"):
            print("✗ No visualization data returned after undo")
            self.test_results.append(("Undo Operation", False, "No visualization data"))
            return False

        print(f"✓ Undo successful")
        print(f"  - Restored image: {undo_data['visualization'].get('rendered_image')}")
        print(f"  - Can undo: {undo_data.get('can_undo', False)}")
        print(f"  - Can redo: {undo_data.get('can_redo', False)}")

        self.test_results.append(("Undo Operation", True, "Success"))
        return True

    def test_5_redo_operation(self):
        """Test redo functionality"""
        print("\n" + "=" * 80)
        print("TEST 5: REDO LAST OPERATION")
        print("=" * 80)

        print("\n1. Performing redo...")
        redo_response = requests.post(
            f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualization/redo"
        )

        if redo_response.status_code != 200:
            print(f"✗ Redo failed: {redo_response.text}")
            self.test_results.append(("Redo Operation", False, redo_response.text))
            return False

        redo_data = redo_response.json()

        if not redo_data.get("visualization"):
            print("✗ No visualization data returned after redo")
            self.test_results.append(("Redo Operation", False, "No visualization data"))
            return False

        print(f"✓ Redo successful")
        print(f"  - Restored image: {redo_data['visualization'].get('rendered_image')}")
        print(f"  - Can undo: {redo_data.get('can_undo', False)}")
        print(f"  - Can redo: {redo_data.get('can_redo', False)}")

        self.test_results.append(("Redo Operation", True, "Success"))
        return True

    def test_6_multiple_products_scene(self):
        """Test adding multiple different products to create a full scene"""
        print("\n" + "=" * 80)
        print("TEST 6: CREATE MULTI-PRODUCT SCENE")
        print("=" * 80)

        products_to_add = [
            ("lamp", "table lamp"),
            ("rug", "area rug"),
            ("chair", "accent chair")
        ]

        for keyword, description in products_to_add:
            print(f"\n--- Adding {description} ---")

            # Search for product
            print(f"1. Searching for {description}...")
            response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/messages",
                json={"message": f"Show me {description}"}
            )

            if response.status_code != 200:
                print(f"✗ Search failed: {response.text}")
                continue

            data = response.json()
            products = data.get("products", [])

            if not products:
                print(f"✗ No {description} found")
                continue

            product = products[0]
            print(f"✓ Found: {product.get('name', 'Unknown')}")

            # Add to visualization
            print(f"2. Adding {description} to scene...")
            viz_response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualize",
                json={
                    "room_image_path": self.test_room_image,
                    "product_id": product["id"],
                    "product_name": product.get("name", description),
                    "product_image_url": product.get("primary_image_url", "")
                }
            )

            if viz_response.status_code == 200:
                print(f"✓ {description.capitalize()} added to scene")
            else:
                print(f"✗ Failed to add {description}: {viz_response.text}")

            time.sleep(1)  # Brief pause between operations

        self.test_results.append(("Multi-Product Scene", True, "Completed"))
        return True

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests

        print(f"\nTotal Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")

        print("\nDetailed Results:")
        for test_name, success, message in self.test_results:
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"  {status}: {test_name}")
            if not success:
                print(f"    Error: {message}")

    def run_all_tests(self):
        """Run all integration tests"""
        try:
            self.setup()

            # Run tests in sequence
            self.test_1_add_first_product()
            time.sleep(2)

            self.test_2_add_second_product()
            time.sleep(2)

            self.test_3_replace_product()
            time.sleep(2)

            self.test_4_undo_operation()
            time.sleep(1)

            self.test_5_redo_operation()
            time.sleep(1)

            self.test_6_multiple_products_scene()

            self.print_summary()

        except Exception as e:
            print(f"\n✗ Test suite failed with error: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("Starting Add/Replace Integration Tests")
    print("Ensure the backend server is running on http://localhost:8000")
    print()

    tester = TestAddReplaceIntegration()
    tester.run_all_tests()
