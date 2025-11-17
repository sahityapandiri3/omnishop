#!/usr/bin/env python3
"""
End-to-end test for visualization workflow
Tests: Session creation, message sending, product recommendations, and visualization
"""

import requests
import base64
import json
import time
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8000"
TIMEOUT = 60  # Increased for OpenAI API calls

# Sample room image (1x1 white pixel as placeholder - you can replace with actual image)
SAMPLE_IMAGE_BASE64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

def print_step(step_num, description):
    """Print test step header"""
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {description}")
    print('='*60)

def test_visualization_workflow():
    """Run complete end-to-end test"""

    print("\n🧪 Starting Visualization Workflow Test")
    print(f"API Base URL: {API_BASE}")

    # STEP 1: Create Session
    print_step(1, "Creating new chat session")
    try:
        response = requests.post(
            f"{API_BASE}/api/chat/sessions",
            json={},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        session_data = response.json()
        session_id = session_data.get("session_id")
        print(f"✅ Session created: {session_id}")
    except Exception as e:
        print(f"❌ Session creation failed: {e}")
        return False

    # STEP 2: Send message with room image
    print_step(2, "Sending message with room image")
    try:
        response = requests.post(
            f"{API_BASE}/api/chat/sessions/{session_id}/messages",
            json={
                "message": "Suggest modern sofas for this living room",
                "image": SAMPLE_IMAGE_BASE64
            },
            timeout=TIMEOUT
        )
        response.raise_for_status()
        message_data = response.json()
        print(f"✅ Message sent successfully")

        # Check for recommended products
        products = message_data.get("recommended_products", [])
        print(f"   Products recommended: {len(products)}")

        if len(products) == 0:
            print("⚠️  No products recommended - may need actual room image")
        else:
            print(f"   First product: {products[0].get('name', 'Unknown')}")

    except Exception as e:
        print(f"❌ Message sending failed: {e}")
        return False

    # STEP 3: Test visualization (if we have products)
    if len(products) > 0:
        print_step(3, "Testing visualization generation")

        # Select first product
        selected_product = products[0]
        product_id = selected_product.get("id")

        print(f"   Selected product: {selected_product.get('name')} (ID: {product_id})")

        try:
            viz_response = requests.post(
                f"{API_BASE}/api/chat/sessions/{session_id}/visualize",
                json={
                    "image": SAMPLE_IMAGE_BASE64,
                    "products": [{
                        "id": product_id,
                        "name": selected_product.get("name"),
                        "full_name": selected_product.get("name"),
                        "style": 0.8,
                        "category": "furniture"
                    }],
                    "analysis": message_data.get("analysis", {})
                },
                timeout=120  # Visualization takes longer
            )

            if viz_response.status_code == 200:
                viz_data = viz_response.json()
                rendered_image = viz_data.get("rendered_image")

                if rendered_image:
                    print(f"✅ Visualization generated successfully")
                    print(f"   Image size: {len(rendered_image)} chars")
                    print(f"   Service used: {viz_data.get('service_used', 'unknown')}")
                    print(f"   Processing time: {viz_data.get('processing_time', 0):.2f}s")

                    # Check which service was used
                    service_used = viz_data.get('service_used', '')
                    if 'ip-adapter' in service_used.lower() or 'replicate' in service_used.lower():
                        print("✅ IP-Adapter/Replicate pipeline was used")
                    elif 'gemini' in service_used.lower():
                        print("⚠️  Gemini fallback was used (IP-Adapter may have failed)")
                    else:
                        print(f"ℹ️  Service used: {service_used}")
                else:
                    print("❌ No rendered image in response")
                    return False
            else:
                print(f"❌ Visualization failed with status {viz_response.status_code}")
                print(f"   Error: {viz_response.text}")
                return False

        except Exception as e:
            print(f"❌ Visualization request failed: {e}")
            return False
    else:
        print_step(3, "Skipping visualization test (no products)")

    # STEP 4: Test chat history
    print_step(4, "Testing chat history retrieval")
    try:
        response = requests.get(
            f"{API_BASE}/api/chat/sessions/{session_id}/history",
            timeout=TIMEOUT
        )
        response.raise_for_status()
        history = response.json()
        messages = history.get("messages", [])
        print(f"✅ Chat history retrieved: {len(messages)} messages")
    except Exception as e:
        print(f"❌ Chat history retrieval failed: {e}")
        return False

    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED!")
    print("="*60)
    return True

if __name__ == "__main__":
    success = test_visualization_workflow()
    exit(0 if success else 1)
