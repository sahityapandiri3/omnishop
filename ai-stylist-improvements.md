# GPT as Single Source of Truth for Intent Detection

## Overview
Refactor the Omnishop conversation flow to make GPT the authoritative source for intent detection, with two clear flows based on `is_direct_search` flag.

## Architecture Changes

### Flow 1: Generic Styling (`is_direct_search: false`)
1. User uploads image or asks for styling help
2. GPT detects generic styling intent
3. Ask preference mode: "Do you have style preferences, or would you like me to choose for you?"
4. If user has preferences → Gather: style, budget
5. If "you choose" → Use room analysis to auto-fill attributes
6. Move to READY_TO_RECOMMEND

### Flow 2: Category Search (`is_direct_search: true`)
1. User asks for specific category (e.g., "I need a sofa", "show me rugs")
2. GPT detects category and sets `is_direct_search: true`
3. **Simple categories** (decor, planters, wall_art, vases, candles): Show products immediately, no follow-up
4. **Complex categories** (sofa, dining_table, coffee_table, etc.):
   - Ask preference mode: "Do you have preferences, or should I choose for you?"
   - If preferences → Gather 2-3 category-specific attributes
   - If "you choose" → Use room analysis to auto-fill attributes
5. Move to READY_TO_RECOMMEND with filled attributes

## Implementation Plan

### Step 1: Create Category Attributes Configuration
**File**: `/api/config/category_attributes.py`

### Step 2: Update GPT Response Schema
**File**: `/api/engines/recommendation/schemas.py`

### Step 3: Update GPT System Prompt
**File**: `/api/services/chatgpt_service.py`

### Step 4: Update Conversation Context Manager
**File**: `/api/services/conversation_context.py`

### Step 5: Update Chat Router
**File**: `/api/routers/chat.py`

## Files to Modify

1. **NEW**: `/api/config/category_attributes.py` - Category attribute definitions
2. `/api/engines/recommendation/schemas.py` - Add new fields to DesignAnalysisSchema
3. `/api/services/chatgpt_service.py` - Update GPT prompt with intent detection rules
4. `/api/services/conversation_context.py` - Add new fields and reset method
5. `/api/routers/chat.py` - Update state logic to trust GPT, add fallback

## Key Behaviors

1. **GPT is primary** - Always use GPT's `is_direct_search` first
2. **Fallback is secondary** - Only use `_detect_direct_search_query()` if GPT doesn't return intent
3. **Simple categories are fast** - No questions, immediate product display
4. **"You choose" uses room analysis** - Auto-fill attributes from image analysis
5. **Reset on intent change** - Clear category-specific attributes when user changes intent
