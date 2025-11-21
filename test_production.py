#!/usr/bin/env python3
"""Test production API for sofa search"""
import requests
import json

# Test production API
print("🔍 Testing Production API...")
print("=" * 60)

# Step 1: Create session
print("\n1. Creating session...")
response = requests.post(
    "https://omnishop-production.up.railway.app/api/chat/sessions",
    headers={"Content-Type": "application/json"},
    json={}
)
session_data = response.json()
session_id = session_data.get("session_id")
print(f"   ✓ Session created: {session_id}")

# Step 2: Search for sofa
print("\n2. Searching for 'sofa'...")
response = requests.post(
    f"https://omnishop-production.up.railway.app/api/chat/sessions/{session_id}/messages",
    headers={"Content-Type": "application/json"},
    json={"message": "I need a sofa for my living room"},
    timeout=30
)

data = response.json()

# Step 3: Check results
products = data.get("recommended_products", [])
message_content = data.get("message", {}).get("content", "")
confidence = data.get("analysis", {}).get("confidence_scores", {}).get("overall_analysis", 0)

print(f"\n📊 Results:")
print(f"   Products returned: {len(products)}")
print(f"   Confidence score: {confidence}%")
print(f"   Response message: {message_content[:100]}...")

if len(products) > 0:
    print(f"\n✅ SUCCESS! Production search is working!")
    print(f"\n   First product: {products[0].get('name', 'Unknown')}")
    print(f"   Price: ₹{products[0].get('price', 0)}")
else:
    print(f"\n❌ ISSUE: No products returned")
    print(f"\nPossible causes:")
    print(f"   1. OpenAI API key not set on Railway")
    print(f"   2. Railway still deploying (wait 2-3 minutes)")
    print(f"   3. Database connection issue")

    # Check if it's a timeout
    if confidence < 60:
        print(f"\n⚠️  Low confidence score ({confidence}%) indicates API timeout/failure")
        print(f"   This usually means OPENAI_API_KEY is missing or invalid")

print("\n" + "=" * 60)
