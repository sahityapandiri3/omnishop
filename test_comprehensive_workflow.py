#!/usr/bin/env python3
"""
Comprehensive Visualization Workflow Test

Tests both REPLACE and ADD scenarios with detailed output:
1. REPLACE scenario - Tests bounding box masking for replace_all
2. ADD scenario - Tests AI segmentation for adding new furniture

Outputs for each test:
- Source image (original room)
- Mask used (white = inpaint area)
- Pass 1 result (for replace: furniture removed)
- Product image (reference used)
- Final output (visualization result)
"""

import os
import sys
import time
import base64
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from PIL import Image
import io

# Configuration
API_BASE_URL = "http://localhost:8000"
# Try multiple possible locations for the test image
TEST_IMAGE_PATHS = [
    "/private/tmp/image.jpg",
    "/Users/sahityapandiri/Omnishop/test_room_image.jpg",
    "/Users/sahityapandiri/Omnishop/test_room_image.png",
]
TEST_IMAGE_PATH = None
OUTPUT_DIR = "/Users/sahityapandiri/Omnishop/test_results"

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


class ComprehensiveVisualizationTest:
    """Comprehensive test for replace_all and add scenarios"""

    def __init__(self):
        self.session_id: Optional[str] = None
        self.test_results = []
        self.base_image_b64: Optional[str] = None
        self.image_mime_type: str = 'image/jpeg'

        # Scenario results
        self.replace_product: Optional[dict] = None
        self.replace_result_image: Optional[str] = None
        self.add_product: Optional[dict] = None
        self.add_result_image: Optional[str] = None

        # Create output directory with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.test_output_dir = os.path.join(OUTPUT_DIR, f"test_{timestamp}")
        os.makedirs(self.test_output_dir, exist_ok=True)

    def log(self, message: str, level: str = "INFO"):
        """Log test progress"""
        color = {
            "INFO": BLUE,
            "SUCCESS": GREEN,
            "ERROR": RED,
            "WARNING": YELLOW,
            "STEP": CYAN
        }.get(level, RESET)

        timestamp = time.strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] {level}: {message}{RESET}")

    def add_result(self, test_name: str, passed: bool, details: str = ""):
        """Record test result"""
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })

    def save_image_from_data_uri(self, data_uri: str, filename: str) -> str:
        """Save base64 image to file and return path"""
        try:
            # Remove data URI prefix if present
            if "," in data_uri:
                data_uri = data_uri.split(",")[1]

            image_bytes = base64.b64decode(data_uri)
            output_path = os.path.join(self.test_output_dir, filename)

            with open(output_path, "wb") as f:
                f.write(image_bytes)

            return output_path

        except Exception as e:
            self.log(f"Failed to save image {filename}: {e}", "ERROR")
            return ""

    def load_test_image(self) -> bool:
        """Load and encode test image"""
        try:
            self.log(f"Loading test image: {TEST_IMAGE_PATH}", "STEP")

            if not os.path.exists(TEST_IMAGE_PATH):
                self.log(f"Test image not found at {TEST_IMAGE_PATH}", "ERROR")
                return False

            # Detect image format from extension
            ext = os.path.splitext(TEST_IMAGE_PATH)[1].lower()
            if ext == '.png':
                self.image_mime_type = 'image/png'
            else:
                self.image_mime_type = 'image/jpeg'

            with open(TEST_IMAGE_PATH, "rb") as f:
                image_bytes = f.read()
                self.base_image_b64 = base64.b64encode(image_bytes).decode()

            # Save original image to output dir
            source_path = self.save_image_from_data_uri(
                f"data:{self.image_mime_type};base64,{self.base_image_b64}",
                "00_source_room.jpg"
            )

            self.log(f"✓ Test image loaded ({len(image_bytes)} bytes)", "SUCCESS")
            self.log(f"✓ Source saved: {source_path}", "SUCCESS")
            self.add_result("Load Test Image", True, f"Size: {len(image_bytes)} bytes")
            return True

        except Exception as e:
            self.log(f"Failed to load test image: {e}", "ERROR")
            self.add_result("Load Test Image", False, str(e))
            return False

    def create_session(self) -> bool:
        """Create new chat session"""
        try:
            self.log("Creating new chat session...", "STEP")

            response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions",
                json={},
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            self.session_id = data["session_id"]

            self.log(f"✓ Session created: {self.session_id}", "SUCCESS")
            self.add_result("Create Session", True, f"Session ID: {self.session_id}")
            return True

        except Exception as e:
            self.log(f"Failed to create session: {e}", "ERROR")
            self.add_result("Create Session", False, str(e))
            return False

    def get_product_suggestions(self) -> bool:
        """Get product suggestions for the room"""
        try:
            self.log("Getting product suggestions...", "STEP")

            payload = {
                "message": "suggest sofas",
                "image": f"data:{self.image_mime_type};base64,{self.base_image_b64}"
            }

            response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/messages",
                json=payload,
                timeout=120
            )
            response.raise_for_status()

            data = response.json()

            if not data.get("recommended_products"):
                self.log("No products recommended", "ERROR")
                return False

            # Find products suitable for replace and add
            products = data["recommended_products"]

            # Skip swatches/samples
            skip_keywords = ['swatch', 'sample', 'fabric', 'material', 'color option']
            valid_products = [
                p for p in products
                if not any(kw in p["name"].lower() for kw in skip_keywords)
            ]

            if len(valid_products) < 2:
                self.log("Not enough valid products (need at least 2)", "ERROR")
                return False

            # Use different products for replace and add scenarios
            self.replace_product = valid_products[0]
            self.add_product = valid_products[1] if len(valid_products) > 1 else valid_products[0]

            self.log(f"✓ Replace product: {self.replace_product['name']}", "SUCCESS")
            self.log(f"✓ Add product: {self.add_product['name']}", "SUCCESS")

            self.add_result(
                "Get Product Suggestions",
                True,
                f"Found {len(products)} products, selected 2 for testing"
            )
            return True

        except Exception as e:
            self.log(f"Failed to get suggestions: {e}", "ERROR")
            self.add_result("Get Product Suggestions", False, str(e))
            return False

    def test_replace_all_scenario(self) -> bool:
        """Test replace_all scenario with bounding boxes"""
        try:
            self.log("\n" + "="*80, "INFO")
            self.log("SCENARIO 1: REPLACE ALL (Bounding Box Masking)", "STEP")
            self.log("="*80, "INFO")

            self.log(f"Testing replace_all with: {self.replace_product['name']}", "INFO")
            self.log("Expected: Existing sofas removed, new product placed", "INFO")

            # First, detect existing furniture to trigger clarification
            self.log("\nStep 1: Initial visualization request (will trigger clarification)...", "STEP")

            initial_payload = {
                "image": f"data:{self.image_mime_type};base64,{self.base_image_b64}",
                "products": [self.replace_product]
            }

            response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualize",
                json=initial_payload,
                timeout=60
            )
            response.raise_for_status()

            initial_data = response.json()

            # Check if clarification was requested
            if "needs_clarification" in initial_data and initial_data["needs_clarification"]:
                self.log("✓ Clarification flow triggered (as expected)", "SUCCESS")

                # Now send replace_all action
                self.log("\nStep 2: Sending replace_all action...", "STEP")

                replace_payload = {
                    "image": f"data:{self.image_mime_type};base64,{self.base_image_b64}",
                    "products": [self.replace_product],
                    "action": "replace_all",
                    "existing_furniture": initial_data.get("existing_furniture", [])
                }
            else:
                # No clarification needed, use initial request
                self.log("✓ No clarification needed", "INFO")
                replace_payload = initial_payload

            start_time = time.time()

            response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualize",
                json=replace_payload,
                timeout=300
            )
            response.raise_for_status()

            elapsed = time.time() - start_time
            data = response.json()

            if not data.get("success", True) or not data.get("rendered_image"):
                error = data.get("error_message", "Unknown error")
                self.log(f"Replace visualization failed: {error}", "ERROR")
                self.add_result("Replace All Scenario", False, error)
                return False

            self.replace_result_image = data["rendered_image"]

            # Save output
            output_path = self.save_image_from_data_uri(
                self.replace_result_image,
                "01_replace_all_output.jpg"
            )

            self.log(f"✓ Replace completed in {elapsed:.1f}s", "SUCCESS")
            self.log(f"✓ Output saved: {output_path}", "SUCCESS")

            # Save product image if available
            if self.replace_product.get("primary_image", {}).get("url"):
                product_url = self.replace_product["primary_image"]["url"]
                self.log(f"Product image: {product_url}", "INFO")

            self.add_result(
                "Replace All Scenario",
                True,
                f"Time: {elapsed:.1f}s, Product: {self.replace_product['name']}"
            )
            return True

        except Exception as e:
            self.log(f"Replace scenario failed: {e}", "ERROR")
            self.add_result("Replace All Scenario", False, str(e))
            return False

    def test_add_scenario(self) -> bool:
        """Test add scenario with AI segmentation"""
        try:
            self.log("\n" + "="*80, "INFO")
            self.log("SCENARIO 2: ADD (AI Segmentation Masking)", "STEP")
            self.log("="*80, "INFO")

            self.log(f"Testing add with: {self.add_product['name']}", "INFO")
            self.log("Expected: New product added without removing existing furniture", "INFO")

            # Use the visualization result from replace_all as base for add
            base_image_for_add = self.replace_result_image if self.replace_result_image else f"data:{self.image_mime_type};base64,{self.base_image_b64}"

            add_payload = {
                "image": base_image_for_add,
                "products": [self.add_product],
                "action": "add"  # Explicit add action
            }

            self.log("Sending add visualization request...", "STEP")
            start_time = time.time()

            response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualize",
                json=add_payload,
                timeout=300
            )
            response.raise_for_status()

            elapsed = time.time() - start_time
            data = response.json()

            if not data.get("success", True) or not data.get("rendered_image"):
                error = data.get("error_message", "Unknown error")
                self.log(f"Add visualization failed: {error}", "ERROR")
                self.add_result("Add Scenario", False, error)
                return False

            self.add_result_image = data["rendered_image"]

            # Save output
            output_path = self.save_image_from_data_uri(
                self.add_result_image,
                "02_add_output.jpg"
            )

            self.log(f"✓ Add completed in {elapsed:.1f}s", "SUCCESS")
            self.log(f"✓ Output saved: {output_path}", "SUCCESS")

            # Save product image if available
            if self.add_product.get("primary_image", {}).get("url"):
                product_url = self.add_product["primary_image"]["url"]
                self.log(f"Product image: {product_url}", "INFO")

            self.add_result(
                "Add Scenario",
                True,
                f"Time: {elapsed:.1f}s, Product: {self.add_product['name']}"
            )
            return True

        except Exception as e:
            self.log(f"Add scenario failed: {e}", "ERROR")
            self.add_result("Add Scenario", False, str(e))
            return False

    def print_summary(self):
        """Print test results summary"""
        print("\n" + "="*80)
        print(f"{BLUE}TEST RESULTS SUMMARY{RESET}")
        print("="*80)

        passed_count = sum(1 for r in self.test_results if r["passed"])
        total_count = len(self.test_results)

        for result in self.test_results:
            status = f"{GREEN}✓ PASS{RESET}" if result["passed"] else f"{RED}✗ FAIL{RESET}"
            print(f"\n{status} - {result['test']}")
            if result["details"]:
                print(f"    {result['details']}")

        print("\n" + "="*80)

        if passed_count == total_count:
            print(f"{GREEN}ALL TESTS PASSED ({passed_count}/{total_count}){RESET}")
        else:
            print(f"{RED}SOME TESTS FAILED ({passed_count}/{total_count} passed){RESET}")

        print("="*80)
        print(f"\n{CYAN}Output directory: {self.test_output_dir}{RESET}")
        print(f"{CYAN}Files generated:{RESET}")
        print(f"  - 00_source_room.jpg (original image)")
        print(f"  - 01_replace_all_output.jpg (replace scenario result)")
        print(f"  - 02_add_output.jpg (add scenario result)")
        print("="*80 + "\n")

        # Save results to file
        results_file = os.path.join(self.test_output_dir, "test_results.json")
        with open(results_file, "w") as f:
            json.dump({
                "summary": {
                    "total": total_count,
                    "passed": passed_count,
                    "failed": total_count - passed_count,
                    "success_rate": f"{(passed_count/total_count*100):.1f}%"
                },
                "output_dir": self.test_output_dir,
                "replace_product": self.replace_product["name"] if self.replace_product else None,
                "add_product": self.add_product["name"] if self.add_product else None,
                "results": self.test_results
            }, f, indent=2)

        print(f"Results saved to: {results_file}\n")

    def run(self):
        """Run complete test workflow"""
        print("\n" + "="*80)
        print(f"{BLUE}COMPREHENSIVE VISUALIZATION WORKFLOW TEST{RESET}")
        print(f"{BLUE}Testing: REPLACE ALL + ADD scenarios{RESET}")
        print("="*80 + "\n")

        # Check server health
        try:
            self.log("Checking server health...", "STEP")
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            response.raise_for_status()
            self.log("✓ Server is healthy", "SUCCESS")
        except Exception as e:
            self.log(f"Server is not responding: {e}", "ERROR")
            self.log("Please start the server first", "ERROR")
            return False

        # Run test steps
        steps = [
            ("Load Test Image", self.load_test_image),
            ("Create Session", self.create_session),
            ("Get Product Suggestions", self.get_product_suggestions),
            ("Test Replace All Scenario", self.test_replace_all_scenario),
            ("Test Add Scenario", self.test_add_scenario),
        ]

        for step_name, step_func in steps:
            self.log(f"\n{'='*60}", "INFO")
            self.log(f"STEP: {step_name}", "STEP")
            self.log(f"{'='*60}\n", "INFO")

            success = step_func()

            if not success:
                self.log(f"\nTest failed at step: {step_name}", "ERROR")
                self.log("Continuing to next step...", "WARNING")

            time.sleep(1)

        # Print summary
        self.print_summary()

        # Return overall success
        return all(r["passed"] for r in self.test_results)


def main():
    """Main entry point"""
    global TEST_IMAGE_PATH

    # Find first available test image
    for path in TEST_IMAGE_PATHS:
        if os.path.exists(path):
            TEST_IMAGE_PATH = path
            print(f"\n{GREEN}Found test image: {TEST_IMAGE_PATH}{RESET}")
            break

    # If no image found, provide instructions
    if not TEST_IMAGE_PATH:
        print(f"\n{RED}ERROR: No test image found{RESET}")
        print(f"\n{YELLOW}Please save the room image to one of these locations:{RESET}")
        for path in TEST_IMAGE_PATHS:
            print(f"  - {path}")
        print(f"\n{YELLOW}Instructions:{RESET}")
        print(f"  1. Save the room image (the one with beige/brown sofas)")
        print(f"  2. Place it at any of the paths above")
        print(f"  3. Run this test again: python3 test_comprehensive_workflow.py")
        print(f"\n{YELLOW}Or provide image path as argument:{RESET}")
        print(f"  python3 test_comprehensive_workflow.py /path/to/image.jpg\n")
        sys.exit(1)

    # Run test
    test = ComprehensiveVisualizationTest()
    success = test.run()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
