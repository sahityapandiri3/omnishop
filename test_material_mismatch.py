#!/usr/bin/env python3
"""Test material mismatch detection for various material-specific queries"""

import requests
import json

API_BASE = "http://localhost:8000"

def test_query(query, expected_material):
    """Test a material-specific query and check if fix triggers correctly"""
    print("\n" + "="*80)
    print(f"Testing: '{query}'")
    print("="*80)

    # Create session
    session_resp = requests.post(f"{API_BASE}/api/chat/sessions", json={})
    session_id = session_resp.json()["session_id"]
    print(f"Session: {session_id}")

    # Send query
    response = requests.post(
        f"{API_BASE}/api/chat/sessions/{session_id}/messages",
        json={"message": query},
        timeout=60
    )

    data = response.json()
    products = data.get("recommended_products", [])
    ai_response = data.get("response", "")

    print(f"\n📝 AI Response:")
    print(ai_response)

    print(f"\n📦 Products Recommended: {len(products)}")
    if products:
        for i, p in enumerate(products[:5]):
            print(f"   {i+1}. {p['name']} - ${p.get('price', 'N/A')}")
    else:
        print("   ❌ No products found!")

    # Check if any products contain the expected material
    material_products = []
    for p in products:
        name_lower = p['name'].lower()
        desc_lower = str(p.get('description', '')).lower() if p.get('description') else ''
        if expected_material in name_lower or expected_material in desc_lower:
            material_products.append(p)

    print(f"\n🔍 Products containing '{expected_material}': {len(material_products)}")

    # Analyze results
    if len(products) > 0 and len(material_products) == 0:
        print(f"\n✅ MATERIAL MISMATCH DETECTED (as expected)")
        print(f"   Products returned: {len(products)}")
        print(f"   Products with '{expected_material}': 0")

        # Check if AI response was adjusted
        if "don't currently have" in ai_response.lower() or "no " in ai_response.lower():
            print(f"   ✅ AI response correctly adjusted!")
        else:
            print(f"   ❌ AI response NOT adjusted - still promising {expected_material} products!")

    elif len(products) == 0:
        print(f"\n⚠️  ZERO PRODUCTS RETURNED")
        print(f"   This triggers ISSUE 18 FIX (different code path)")

    elif len(material_products) > 0:
        print(f"\n✅ MATERIAL MATCH FOUND")
        print(f"   {len(material_products)} products actually contain '{expected_material}'")

    return {
        "query": query,
        "products_count": len(products),
        "material_match_count": len(material_products),
        "ai_response": ai_response
    }

# Test Cases
print("🧪 MATERIAL MISMATCH FIX - TEST SUITE")
print("=" * 80)

results = []

# Test 1: Leather sofa (likely returns fabric sofas)
results.append(test_query("show me leather sofa", "leather"))

# Test 2: Wooden table (might return metal/glass tables)
results.append(test_query("show me wooden dining table", "wood"))

# Test 3: Wicker center table (original issue)
results.append(test_query("show me wicker center table", "wicker"))

# Test 4: Metal bed frame (might return wooden beds)
results.append(test_query("show me metal bed frame", "metal"))

# Summary
print("\n" + "="*80)
print("📊 TEST SUMMARY")
print("="*80)

for i, result in enumerate(results, 1):
    print(f"\nTest {i}: {result['query']}")
    print(f"   Products returned: {result['products_count']}")
    print(f"   Material matches: {result['material_match_count']}")

    if result['products_count'] > 0 and result['material_match_count'] == 0:
        if "don't currently have" in result['ai_response'].lower() or "no " in result['ai_response'].lower():
            print(f"   Status: ✅ FIX WORKING")
        else:
            print(f"   Status: ❌ FIX NOT WORKING")
    elif result['products_count'] == 0:
        print(f"   Status: ⚠️  ISSUE 18 FIX TRIGGERED")
    else:
        print(f"   Status: ✅ MATERIAL FOUND")

print("\n" + "="*80)
