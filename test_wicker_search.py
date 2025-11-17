#!/usr/bin/env python3
"""Test wicker center table search"""

import requests
import json

API_BASE = "http://localhost:8000"

# Create session
session_resp = requests.post(f"{API_BASE}/api/chat/sessions", json={})
session_id = session_resp.json()["session_id"]
print(f"Session created: {session_id}")

# Test wicker search
print("\n" + "="*60)
print("Testing: 'show me wicker center table'")
print("="*60)

response = requests.post(
    f"{API_BASE}/api/chat/sessions/{session_id}/messages",
    json={"message": "show me wicker center table"},
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

# Check if any products contain "wicker"
wicker_products = [p for p in products if 'wicker' in p['name'].lower() or 'wicker' in p.get('description', '').lower()]
print(f"\n🔍 Products containing 'wicker': {len(wicker_products)}")

if len(wicker_products) == 0 and len(products) > 0:
    print("\n⚠️  ISSUE DETECTED:")
    print("   AI promises wicker products but none are wicker!")
    print("   AI should say: 'No wicker center tables available, but here are other center tables'")
elif len(wicker_products) == 0 and len(products) == 0:
    print("\n⚠️  ISSUE DETECTED:")
    print("   AI promises wicker products but returned ZERO products!")
    print("   AI should say: 'No wicker center tables available'")
