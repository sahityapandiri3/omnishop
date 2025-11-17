#!/usr/bin/env python3
"""Test center table search - to understand why wicker center table returns 0"""

import requests
import json

API_BASE = "http://localhost:8000"

# Create session
session_resp = requests.post(f"{API_BASE}/api/chat/sessions", json={})
session_id = session_resp.json()["session_id"]
print(f"Session created: {session_id}")

# Test simple center table search (no material specified)
print("\n" + "="*60)
print("Testing: 'show me center table'")
print("="*60)

response = requests.post(
    f"{API_BASE}/api/chat/sessions/{session_id}/messages",
    json={"message": "show me center table"},
    timeout=60
)

data = response.json()
products = data.get("recommended_products", [])
ai_response = data.get("response", "")

print(f"\n📝 AI Response:")
print(ai_response)

print(f"\n📦 Products Recommended: {len(products)}")
if products:
    for i, p in enumerate(products[:10]):
        print(f"   {i+1}. {p['name']} - ${p.get('price', 'N/A')}")
        # Check if any mention wicker
        if 'wicker' in p['name'].lower() or 'wicker' in str(p.get('description', '')).lower():
            print(f"       ✅ WICKER PRODUCT FOUND!")
else:
    print("   ❌ No products found!")
    print("   This explains why 'wicker center table' returns 0")
    print("   The search doesn't find center tables at all!")
