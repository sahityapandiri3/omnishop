#!/usr/bin/env python3
"""Test Anthropic client initialization"""
import sys
sys.path.insert(0, '/Users/sahityapandiri/Omnishop/api')

from anthropic import Anthropic
from api.core.config import settings

print("="*60)
print("Testing Anthropic Client Initialization")
print("="*60)

print(f"\n1. Checking API key in settings...")
if hasattr(settings, 'anthropic_api_key'):
    api_key = settings.anthropic_api_key
    if api_key:
        print(f"   ✓ API key found: {api_key[:15]}...")
    else:
        print(f"   ✗ API key is empty")
        sys.exit(1)
else:
    print(f"   ✗ API key attribute not found in settings")
    sys.exit(1)

print(f"\n2. Attempting to initialize Anthropic client...")
try:
    client = Anthropic(api_key=api_key)
    print(f"   ✓ Anthropic client initialized successfully!")
    print(f"   Client type: {type(client)}")
except Exception as e:
    print(f"   ✗ Failed to initialize: {e}")
    sys.exit(1)

print(f"\n3. Testing a simple API call...")
try:
    # Test with a simple message
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}]
    )
    print(f"   ✓ API call successful!")
    print(f"   Response: {response.content[0].text}")
except Exception as e:
    print(f"   ✗ API call failed: {e}")
    sys.exit(1)

print(f"\n" + "="*60)
print("ALL TESTS PASSED - Anthropic client is working!")
print("="*60)
