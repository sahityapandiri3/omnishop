#!/bin/bash

echo "=== OMNISHOP REGRESSION TEST SUITE ==="
echo "Started: $(date)"
echo ""

API_URL="http://localhost:8000"
SESSION_ID=""

# Test 1: Create session
echo "Test 1: Session Creation"
RESPONSE=$(curl -s -X POST "$API_URL/api/chat/sessions" -H "Content-Type: application/json" -d '{}')
SESSION_ID=$(echo $RESPONSE | grep -o '"session_id":"[^"]*' | cut -d'"' -f4)
if [ -n "$SESSION_ID" ]; then
    echo "✅ PASS: Session created: $SESSION_ID"
else
    echo "❌ FAIL: Session creation failed"
    exit 1
fi
echo ""

# Test 14: Bed search
echo "Test 14: Bed Search (Issue 14 - CRITICAL)"
RESPONSE=$(curl -s -X POST "$API_URL/api/chat/sessions/$SESSION_ID/messages" \
    -H "Content-Type: application/json" \
    -d '{"message":"show me beds"}')
BED_COUNT=$(echo $RESPONSE | grep -o '"id":[0-9]*' | wc -l | tr -d ' ')
if [ "$BED_COUNT" -gt 5 ]; then
    echo "✅ PASS: Found $BED_COUNT bed products (expected >5)"
else
    echo "❌ FAIL: Found only $BED_COUNT bed products"
fi
echo ""

# Test 12: Pillow search
echo "Test 12: Pillow Search (Issue 12)"
RESPONSE=$(curl -s -X POST "$API_URL/api/chat/sessions/$SESSION_ID/messages" \
    -H "Content-Type: application/json" \
    -d '{"message":"show me pillows"}')
PILLOW_COUNT=$(echo $RESPONSE | grep -o '"id":[0-9]*' | wc -l | tr -d ' ')
if [ "$PILLOW_COUNT" -gt 0 ]; then
    echo "✅ PASS: Found $PILLOW_COUNT pillow products"
else
    echo "❌ FAIL: No pillow products found"
fi
echo ""

# Test 13: Wall art search  
echo "Test 13: Wall Art Search (Issue 13)"
RESPONSE=$(curl -s -X POST "$API_URL/api/chat/sessions/$SESSION_ID/messages" \
    -H "Content-Type: application/json" \
    -d '{"message":"show me wall art"}')
ART_COUNT=$(echo $RESPONSE | grep -o '"id":[0-9]*' | wc -l | tr -d ' ')
if [ "$ART_COUNT" -gt 0 ]; then
    echo "✅ PASS: Found $ART_COUNT wall art products"
else
    echo "❌ FAIL: No wall art products found"
fi
echo ""

# Test 9: Search results count
echo "Test 9: Search Results Pagination (Issue 9)"
RESPONSE=$(curl -s -X POST "$API_URL/api/chat/sessions/$SESSION_ID/messages" \
    -H "Content-Type: application/json" \
    -d '{"message":"show me sofas"}')
SOFA_COUNT=$(echo $RESPONSE | grep -o '"id":[0-9]*' | wc -l | tr -d ' ')
if [ "$SOFA_COUNT" -ge 20 ]; then
    echo "✅ PASS: Found $SOFA_COUNT sofa products (expected ≥20)"
elif [ "$SOFA_COUNT" -gt 10 ]; then
    echo "⚠️  PARTIAL: Found $SOFA_COUNT sofa products (better than before, but <20)"
else
    echo "❌ FAIL: Found only $SOFA_COUNT sofa products (expected ≥20)"
fi
echo ""

echo "=== Test Suite Completed: $(date) ==="
