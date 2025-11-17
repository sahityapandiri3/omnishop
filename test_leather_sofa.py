#!/usr/bin/env python3
"""Test leather sofa query - should return non-leather sofas and adjust response"""

import requests
import json

API_BASE = "http://localhost:8000"

# Create session
session_resp = requests.post(f"{API_BASE}/api/chat/sessions", json={})
session_id = session_resp.json()["session_id"]
print(f"Session created: {session_id}")

# Test leather sofa search
print("\n" + "="*60)
print("Testing: 'show me leather sofa'")
print("="*60)

response = requests.post(
    f"{API_BASE}/api/chat/sessions/{session_id}/messages",
    json={"message": "show me leather sofa"},
    timeout=90
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

# Check if any products contain "leather"
leather_products = []
for p in products:
    name_lower = p['name'].lower()
    desc_lower = str(p.get('description', '')).lower() if p.get('description') else ''
    if 'leather' in name_lower or 'leather' in desc_lower:
        leather_products.append(p)

print(f"\n🔍 Products containing 'leather': {len(leather_products)}")

# Analyze results
if len(products) > 0 and len(leather_products) == 0:
    print("\n✅ MATERIAL MISMATCH DETECTED")
    print(f"   Products returned: {len(products)} sofas")
    print(f"   Products with leather: 0")
    print(f"\n   Expected AI behavior: Should say 'no leather sofas available, but here are alternatives'")

    # Check if AI response was adjusted by the fix
    if "don't currently have" in ai_response.lower() or "no leather" in ai_response.lower():
        print(f"\n   ✅✅ FIX WORKING: AI response correctly adjusted!")
        print(f"   AI honestly says leather not available")
    else:
        print(f"\n   ❌❌ FIX NOT WORKING: AI still promising leather sofas!")
        print(f"   AI should NOT promise leather when none exist")

elif len(products) == 0:
    print(f"\n⚠️  ZERO PRODUCTS RETURNED")
    print(f"   Different code path (ISSUE 18 FIX) handles this case")

elif len(leather_products) > 0:
    print(f"\n✅ LEATHER SOFAS FOUND")
    print(f"   {len(leather_products)} products actually contain leather")
    print(f"   No fix needed - products match user request")
