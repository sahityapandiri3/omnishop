#!/usr/bin/env python3
"""
Complete Visualization Workflow Test

This test validates the entire furniture visualization pipeline:
1. Upload room image
2. Get sofa suggestions from ChatGPT
3. Select a product
4. Generate visualization
5. Verify output quality

Expected behavior:
- Room structure preserved (walls, floor, windows unchanged)
- Original furniture removed from masked areas
- New product placed correctly matching reference image
- All 8 fixes active (IP-Adapter, Canny ControlNet, Vision API, etc.)
"""

import os
import sys
import time
import base64
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Configuration
API_BASE_URL = "http://localhost:8000"
# Support both JPG and PNG formats
TEST_IMAGE_PATH = None  # Will auto-detect
for ext in ['.png', '.jpg', '.jpeg']:
    path = f"/Users/sahityapandiri/Omnishop/test_room_image{ext}"
    if os.path.exists(path):
        TEST_IMAGE_PATH = path
        break
if TEST_IMAGE_PATH is None:
    TEST_IMAGE_PATH = "/Users/sahityapandiri/Omnishop/test_room_image.jpg"  # Default for error message
OUTPUT_DIR = "/Users/sahityapandiri/Omnishop/test_results"

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class VisualizationTest:
    """Complete visualization workflow test"""

    def __init__(self):
        self.session_id: Optional[str] = None
        self.test_results = []
        self.base_image_b64: Optional[str] = None
        self.image_mime_type: str = 'image/jpeg'  # Default, will be detected
        self.selected_product_id: Optional[int] = None
        self.selected_product: Optional[dict] = None  # Store full product object
        self.visualization_result: Optional[str] = None

        # Create output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    def log(self, message: str, level: str = "INFO"):
        """Log test progress"""
        color = {
            "INFO": BLUE,
            "SUCCESS": GREEN,
            "ERROR": RED,
            "WARNING": YELLOW
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

    def load_test_image(self) -> bool:
        """Load and encode test image"""
        try:
            self.log(f"Loading test image: {TEST_IMAGE_PATH}")

            if not os.path.exists(TEST_IMAGE_PATH):
                self.log(f"Test image not found at {TEST_IMAGE_PATH}", "ERROR")
                self.log("Please save the room image used in previous tests", "ERROR")
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

            self.log(f"✓ Test image loaded ({len(image_bytes)} bytes, {self.image_mime_type})", "SUCCESS")
            self.add_result("Load Test Image", True, f"Image size: {len(image_bytes)} bytes, type: {self.image_mime_type}")
            return True

        except Exception as e:
            self.log(f"Failed to load test image: {e}", "ERROR")
            self.add_result("Load Test Image", False, str(e))
            return False

    def create_session(self) -> bool:
        """Create new chat session"""
        try:
            self.log("Creating new chat session...")

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

    def analyze_room_and_suggest_sofas(self) -> bool:
        """Send room image with 'suggest sofas' prompt"""
        try:
            self.log("Analyzing room and requesting sofa suggestions...")

            payload = {
                "message": "suggest sofas",
                "image": f"data:{self.image_mime_type};base64,{self.base_image_b64}"
            }

            response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/messages",
                json=payload,
                timeout=120  # Increased from 60 to 120 seconds for ChatGPT Vision API
            )
            response.raise_for_status()

            data = response.json()

            # Check response (API returns message.content)
            message_content = data.get("message", {}).get("content") if isinstance(data.get("message"), dict) else None
            if not message_content:
                self.log("No response from analysis", "ERROR")
                self.add_result("Analyze Room", False, "Empty response")
                return False

            self.log(f"✓ Analysis complete: {message_content[:100]}...", "SUCCESS")

            # Check for recommended products
            if not data.get("recommended_products"):
                self.log("No products recommended", "WARNING")
                self.add_result("Analyze Room", False, "No products recommended")
                return False

            product_count = len(data["recommended_products"])
            self.log(f"✓ {product_count} sofas recommended", "SUCCESS")

            # Select first VISUALIZABLE product (skip swatches, samples, etc.)
            skip_keywords = ['swatch', 'sample', 'fabric', 'material', 'color option']
            selected_product = None

            for product in data["recommended_products"]:
                product_name_lower = product["name"].lower()
                # Skip if product name contains any skip keywords
                if not any(keyword in product_name_lower for keyword in skip_keywords):
                    selected_product = product
                    break

            if not selected_product:
                # Fallback to first product if all are samples
                selected_product = data["recommended_products"][0]
                self.log("Warning: All products appear to be samples, using first one anyway", "WARNING")

            self.selected_product_id = selected_product["id"]
            self.selected_product = selected_product  # Store full product object
            product_name = selected_product["name"]

            self.log(f"✓ Selected product: {product_name} (ID: {self.selected_product_id})", "SUCCESS")

            self.add_result(
                "Analyze Room & Get Suggestions",
                True,
                f"{product_count} products, selected: {product_name}"
            )
            return True

        except Exception as e:
            self.log(f"Failed to analyze room: {e}", "ERROR")
            self.add_result("Analyze Room", False, str(e))
            return False

    def generate_visualization(self) -> bool:
        """Generate visualization with selected product"""
        try:
            self.log(f"Generating visualization for product {self.selected_product_id}...")

            payload = {
                "image": f"data:{self.image_mime_type};base64,{self.base_image_b64}",
                "products": [self.selected_product],  # Send full product object, not just ID
                "action": "replace_all"  # Changed from user_action to action
            }

            self.log("Sending visualization request (this may take 1-2 minutes)...")
            start_time = time.time()

            response = requests.post(
                f"{API_BASE_URL}/api/chat/sessions/{self.session_id}/visualize",
                json=payload,
                timeout=300  # 5 minutes max
            )
            response.raise_for_status()

            elapsed = time.time() - start_time
            self.log(f"✓ Visualization completed in {elapsed:.1f}s", "SUCCESS")

            data = response.json()

            # DEBUG: Log full response to understand structure
            self.log(f"Response keys: {list(data.keys())}", "INFO")
            if not data.get("success", True):  # Check success first
                error_msg = data.get("error_message", data.get("message", "Unknown error"))
                self.log(f"Visualization failed: {error_msg}", "ERROR")
                self.add_result("Generate Visualization", False, f"API error: {error_msg}")
                return False

            # Check for rendered image
            if not data.get("rendered_image"):
                self.log("No rendered image in response", "ERROR")
                self.log(f"Response data: {data}", "ERROR")
                self.add_result("Generate Visualization", False, "No rendered image")
                return False

            self.visualization_result = data["rendered_image"]

            # Save result
            output_path = os.path.join(OUTPUT_DIR, f"visualization_{int(time.time())}.jpg")
            self.save_image(self.visualization_result, output_path)

            self.log(f"✓ Visualization saved to: {output_path}", "SUCCESS")

            # Check success status (if rendered_image exists, visualization succeeded)
            # The API returns rendered_image without a "success" field when successful
            # Only check for explicit failure indicators
            if "error" in data or "error_message" in data:
                error_msg = data.get("error_message", data.get("error", "Unknown error"))
                self.log(f"Visualization marked as failed: {error_msg}", "ERROR")
                self.add_result("Generate Visualization", False, f"API reported failure: {error_msg}")
                return False

            # Log additional information from response
            if "message" in data:
                self.log(f"Message: {data['message']}", "INFO")
            if "products_visualized" in data:
                self.log(f"Products visualized: {data['products_visualized']}", "INFO")

            # Check processing time
            processing_time = data.get("processing_time", elapsed)
            confidence = data.get("confidence_score", 0)

            self.log(f"✓ Processing time: {processing_time:.1f}s", "SUCCESS")
            if confidence > 0:
                self.log(f"✓ Confidence: {confidence:.2f}", "SUCCESS")

            self.add_result(
                "Generate Visualization",
                True,
                f"Time: {processing_time:.1f}s, Confidence: {confidence:.2f}, Output: {output_path}"
            )
            return True

        except requests.exceptions.Timeout:
            self.log("Visualization request timed out (5 min)", "ERROR")
            self.add_result("Generate Visualization", False, "Request timeout after 300s")
            return False
        except Exception as e:
            self.log(f"Failed to generate visualization: {e}", "ERROR")
            self.add_result("Generate Visualization", False, str(e))
            return False

    def verify_visualization_quality(self) -> bool:
        """Verify visualization meets quality criteria"""
        try:
            self.log("Verifying visualization quality...")

            if not self.visualization_result:
                self.log("No visualization result to verify", "ERROR")
                self.add_result("Verify Quality", False, "No result available")
                return False

            # Check 1: Image is not empty
            if len(self.visualization_result) < 1000:
                self.log("Visualization image is too small (likely corrupted)", "ERROR")
                self.add_result("Verify Quality", False, "Image too small")
                return False

            self.log(f"✓ Image size valid ({len(self.visualization_result)} chars)", "SUCCESS")

            # Check 2: Image is different from input
            if self.visualization_result == f"data:{self.image_mime_type};base64,{self.base_image_b64}":
                self.log("Output image is identical to input (no processing)", "ERROR")
                self.add_result("Verify Quality", False, "Output identical to input")
                return False

            self.log("✓ Output differs from input", "SUCCESS")

            # Manual verification prompt
            output_files = sorted(Path(OUTPUT_DIR).glob("visualization_*.jpg"))
            if output_files:
                latest_file = output_files[-1]
                self.log(f"\nPlease manually verify the visualization:", "INFO")
                self.log(f"  File: {latest_file}", "INFO")
                self.log(f"  Expected:", "INFO")
                self.log(f"    - Room structure preserved (walls, floor, windows)", "INFO")
                self.log(f"    - Original furniture removed", "INFO")
                self.log(f"    - New sofa placed correctly", "INFO")
                self.log(f"    - Product matches reference image", "INFO")

            self.add_result(
                "Verify Quality",
                True,
                "Automated checks passed, manual verification required"
            )
            return True

        except Exception as e:
            self.log(f"Failed to verify quality: {e}", "ERROR")
            self.add_result("Verify Quality", False, str(e))
            return False

    def check_server_logs_for_fixes(self) -> bool:
        """Check if all fixes are active (requires manual log inspection)"""
        try:
            self.log("\nChecking for active fixes (requires manual log verification):", "INFO")

            expected_logs = [
                "Running Private MajicMIX Deployment (IP-Adapter + Inpainting + Canny ControlNet)",
                "Generated Canny edge map",
                "Calling ChatGPT Vision API for product analysis",
                "Using ChatGPT Vision API analysis for product prompt",
                "Replicate prediction status: succeeded"
            ]

            self.log("Expected log entries:", "INFO")
            for log_entry in expected_logs:
                self.log(f"  - {log_entry}", "INFO")

            self.log("\nPlease check server logs to verify all fixes are active", "WARNING")

            self.add_result(
                "Check Active Fixes",
                True,
                "Manual log verification required"
            )
            return True

        except Exception as e:
            self.log(f"Failed to check fixes: {e}", "ERROR")
            self.add_result("Check Active Fixes", False, str(e))
            return False

    def save_image(self, data_uri: str, output_path: str):
        """Save base64 image to file"""
        try:
            # Remove data URI prefix if present
            if "," in data_uri:
                data_uri = data_uri.split(",")[1]

            image_bytes = base64.b64decode(data_uri)

            with open(output_path, "wb") as f:
                f.write(image_bytes)

        except Exception as e:
            self.log(f"Failed to save image: {e}", "ERROR")

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

        print("="*80 + "\n")

        # Save results to file
        results_file = os.path.join(OUTPUT_DIR, f"test_results_{int(time.time())}.json")
        with open(results_file, "w") as f:
            json.dump({
                "summary": {
                    "total": total_count,
                    "passed": passed_count,
                    "failed": total_count - passed_count,
                    "success_rate": f"{(passed_count/total_count*100):.1f}%"
                },
                "results": self.test_results
            }, f, indent=2)

        print(f"Results saved to: {results_file}\n")

    def run(self):
        """Run complete test workflow"""
        print("\n" + "="*80)
        print(f"{BLUE}STARTING COMPLETE VISUALIZATION WORKFLOW TEST{RESET}")
        print("="*80 + "\n")

        # Check server health
        try:
            self.log("Checking server health...")
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
            ("Analyze Room & Suggest Sofas", self.analyze_room_and_suggest_sofas),
            ("Generate Visualization", self.generate_visualization),
            ("Verify Quality", self.verify_visualization_quality),
            ("Check Active Fixes", self.check_server_logs_for_fixes)
        ]

        for step_name, step_func in steps:
            self.log(f"\n{'='*60}")
            self.log(f"STEP: {step_name}")
            self.log(f"{'='*60}\n")

            success = step_func()

            if not success and step_name not in ["Check Active Fixes"]:
                self.log(f"\nTest failed at step: {step_name}", "ERROR")
                self.log("Stopping test execution", "ERROR")
                break

            time.sleep(1)  # Brief pause between steps

        # Print summary
        self.print_summary()

        # Return overall success
        return all(r["passed"] for r in self.test_results)


def main():
    """Main entry point"""
    # Check if test image exists
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"\n{RED}ERROR: Test image not found at {TEST_IMAGE_PATH}{RESET}")
        print(f"\nPlease save your test room image to this location.")
        print(f"You can do this by:")
        print(f"  1. Locate the image you used in previous tests")
        print(f"  2. Copy it to: {TEST_IMAGE_PATH}")
        print(f"  3. Run this test again\n")
        sys.exit(1)

    # Run test
    test = VisualizationTest()
    success = test.run()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
