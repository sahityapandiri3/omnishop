# Visualization Context & UX Bugs

**Date:** 2025-10-15
**Status:** 🔴 **NEW CRITICAL ISSUES - 2 Bugs Identified**
**Priority:** HIGH - Impacts core user experience and context understanding

---

## Bug #8: Text-Based Movement Places Wrong Product ❌

**Severity:** CRITICAL
**User Impact:** User asks to move placed coffee table → System places random side table instead

### Evidence
**User Report:**
> "I visualize coffee table, it is placed in the center. So I send a text 'place it on the side next to the sofa'. It should understand the instruction and place the product (here it means previously placed product) on the side. What it does not is place a random side table that is not the product in question in the space asked."

### Current Behavior
```
Step 1: User adds coffee table → Coffee table placed in center
Step 2: User says "place it on the side next to the sofa"
Expected: Move the SAME coffee table to the side
Actual: System adds a RANDOM side table (different product)
```

### Root Cause Analysis

**Location:** Multiple files - conversation context, action parsing, product tracking

**Issue 1: Context Loss**
The system doesn't track WHICH product was just placed. When user says "place it", system doesn't know "it" refers to the last placed product.

**Issue 2: Keyword Misinterpretation**
System sees "side" → Searches for "side table" instead of understanding "side" as a position.

**Issue 3: No Product Reference Tracking**
```python
# api/services/conversation_context.py
# Current: Only stores product list, not "active" product
placed_products = [product1, product2, product3]

# Missing: Reference to last placed product
last_placed_product = None  # MISSING
```

**Issue 4: Pronoun Resolution Not Implemented**
System doesn't understand:
- "it" = last placed product
- "the table" = last placed table
- "that" = previously mentioned item

### Proposed Fix

**Fix Strategy: Context-Aware Product Tracking + Pronoun Resolution**

#### Part 1: Track Last Placed Product
```python
# api/services/conversation_context.py

@dataclass
class ConversationContext:
    placed_products: List[Dict[str, Any]]
    last_placed_product: Optional[Dict[str, Any]] = None  # NEW
    last_action: Optional[str] = None  # NEW: "add", "replace", "move"
    last_action_timestamp: Optional[datetime] = None  # NEW

def store_visualization(
    self,
    session_id: str,
    rendered_image: str,
    products: List[Dict[str, Any]],
    action: str = "add"
):
    """Store visualization with context tracking"""
    context = self.get_or_create_context(session_id)

    # Update placed products
    context.placed_products = products

    # NEW: Track last placed product
    if products and len(products) > 0:
        context.last_placed_product = products[-1]  # Last product in list
        context.last_action = action
        context.last_action_timestamp = datetime.now()

    context.last_visualization_image = rendered_image
```

#### Part 2: Pronoun Resolution System
```python
# api/services/nlp_processor.py

def resolve_product_reference(
    self,
    text: str,
    last_placed_product: Optional[Dict[str, Any]],
    placed_products: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Resolve pronouns/references to actual products"""
    text_lower = text.lower()

    # Pronouns that reference last placed product
    immediate_references = ["it", "this", "that", "the item", "the product"]
    if any(ref in text_lower for ref in immediate_references):
        if last_placed_product:
            return last_placed_product

    # Specific product type references
    # "the table" → Find last placed table
    product_types = ["table", "chair", "sofa", "lamp", "bed", "cabinet"]
    for product_type in product_types:
        if f"the {product_type}" in text_lower or f"that {product_type}" in text_lower:
            # Find last placed product of this type
            for product in reversed(placed_products):
                product_name = product.get('name', '').lower()
                if product_type in product_name:
                    return product

    return None
```

#### Part 3: Position vs Product Keyword Disambiguation
```python
# api/services/chatgpt_service.py - System prompt addition

POSITION_KEYWORDS = {
    "side": "position on the side",
    "corner": "position in corner",
    "center": "position in center",
    "left": "position on left",
    "right": "position on right",
    "front": "position in front",
    "back": "position in back"
}

# When parsing user intent, distinguish:
# "place it on the side" → POSITION instruction (move last product to side)
# "add a side table" → PRODUCT request (new product)

def parse_placement_instruction(text: str, context: Dict) -> Dict:
    """Parse whether user wants to move existing or add new product"""
    text_lower = text.lower()

    # Check for movement verbs + pronouns → MOVE EXISTING
    movement_patterns = [
        r'(place|move|put|shift|relocate)\s+(it|this|that|the\s+\w+)\s+(on|to|at|in)',
        r'(can you|could you)?\s*(place|move|put)\s+(it|this|that)'
    ]

    for pattern in movement_patterns:
        if re.search(pattern, text_lower):
            return {
                "action": "move_existing",
                "product": "last_placed",
                "position": extract_position_from_text(text_lower)
            }

    # Check for "add" / "show me" → ADD NEW
    addition_patterns = [r'add a', r'show me', r'suggest', r'recommend']
    for pattern in addition_patterns:
        if re.search(pattern, text_lower):
            return {
                "action": "add_new",
                "product_type": extract_product_type(text_lower),
                "position": extract_position_from_text(text_lower)
            }

    return {"action": "unclear"}
```

#### Part 4: Integration with Chat Router
```python
# api/routers/chat.py - Movement action handling

if user_intent == "move_existing_product":
    # Resolve which product to move
    product_to_move = nlp_processor.resolve_product_reference(
        user_message,
        context.last_placed_product,
        context.placed_products
    )

    if not product_to_move:
        return {
            "message": "I'm not sure which product you'd like to move. Could you clarify?",
            "clarification_needed": True
        }

    # Extract new position
    new_position = extract_position_from_text(user_message)

    # Perform movement (two-pass inpainting)
    # Step 1: Remove from old position
    cleaned_image = await remove_product_from_scene(
        base_image=context.last_visualization_image,
        product=product_to_move
    )

    # Step 2: Add at new position
    moved_result = await add_product_to_scene(
        base_image=cleaned_image,
        product=product_to_move,
        position=new_position
    )

    # Update context
    conversation_context_manager.update_product_position(
        session_id,
        product_to_move['id'],
        new_position
    )
```

### Testing Plan
1. Add coffee table → Says "place it on the side" → SAME coffee table moves to side
2. Add lamp → Says "move that lamp to the corner" → SAME lamp moves to corner
3. Add chair → Says "can you put the chair near the window" → SAME chair moves
4. Add table + chair → Says "move the table to the left" → Only table moves (not chair)

---

## Bug #9: No Undo Button ❌

**Severity:** HIGH
**User Impact:** Cannot revert to previous visualization state - must start over

### Evidence
**User Request:**
> "Additionally, introduce an undo button. The purpose of this button is to move to the previous state."

### Current Behavior
```
User: Adds coffee table
User: Adds lamp
User: Doesn't like lamp placement
Current: No way to undo - must refresh and start over
Expected: Click "Undo" button → Reverts to state with just coffee table
```

### Proposed Fix

**Fix Strategy: Visualization History Stack + Undo/Redo System**

#### Part 1: History Stack Data Structure
```python
# api/services/conversation_context.py

@dataclass
class VisualizationState:
    """Single visualization state snapshot"""
    rendered_image: str  # Base64 image
    placed_products: List[Dict[str, Any]]  # Products in scene
    action_description: str  # "Added yellow sofa", "Replaced chair", "Moved lamp"
    timestamp: datetime
    action_type: str  # "add", "replace", "move", "remove"

@dataclass
class ConversationContext:
    # Existing fields...
    placed_products: List[Dict[str, Any]]
    last_visualization_image: str

    # NEW: History stack
    visualization_history: List[VisualizationState] = field(default_factory=list)
    current_history_index: int = -1  # Points to current state in history
    max_history_size: int = 20  # Keep last 20 states

def push_visualization_state(
    self,
    session_id: str,
    rendered_image: str,
    products: List[Dict[str, Any]],
    action_description: str,
    action_type: str
):
    """Push new state to history stack"""
    context = self.get_or_create_context(session_id)

    # Create new state
    new_state = VisualizationState(
        rendered_image=rendered_image,
        placed_products=products.copy(),
        action_description=action_description,
        timestamp=datetime.now(),
        action_type=action_type
    )

    # If we're in the middle of history (after undos), discard forward history
    if context.current_history_index < len(context.visualization_history) - 1:
        context.visualization_history = context.visualization_history[:context.current_history_index + 1]

    # Add new state
    context.visualization_history.append(new_state)
    context.current_history_index = len(context.visualization_history) - 1

    # Limit history size
    if len(context.visualization_history) > context.max_history_size:
        context.visualization_history.pop(0)
        context.current_history_index -= 1

    logger.info(f"Pushed state: {action_description} (index: {context.current_history_index})")

def undo_last_action(self, session_id: str) -> Optional[VisualizationState]:
    """Undo to previous state"""
    context = self.get_or_create_context(session_id)

    if context.current_history_index <= 0:
        logger.info("Cannot undo: at beginning of history")
        return None

    # Move back one state
    context.current_history_index -= 1
    previous_state = context.visualization_history[context.current_history_index]

    # Restore state
    context.last_visualization_image = previous_state.rendered_image
    context.placed_products = previous_state.placed_products.copy()

    logger.info(f"Undid to state: {previous_state.action_description}")
    return previous_state

def redo_last_action(self, session_id: str) -> Optional[VisualizationState]:
    """Redo previously undone action"""
    context = self.get_or_create_context(session_id)

    if context.current_history_index >= len(context.visualization_history) - 1:
        logger.info("Cannot redo: at end of history")
        return None

    # Move forward one state
    context.current_history_index += 1
    next_state = context.visualization_history[context.current_history_index]

    # Restore state
    context.last_visualization_image = next_state.rendered_image
    context.placed_products = next_state.placed_products.copy()

    logger.info(f"Redid to state: {next_state.action_description}")
    return next_state

def get_history_summary(self, session_id: str) -> List[Dict[str, Any]]:
    """Get summary of visualization history for UI"""
    context = self.get_or_create_context(session_id)

    return [
        {
            "index": i,
            "description": state.action_description,
            "timestamp": state.timestamp.isoformat(),
            "action_type": state.action_type,
            "is_current": i == context.current_history_index
        }
        for i, state in enumerate(context.visualization_history)
    ]
```

#### Part 2: API Endpoints for Undo/Redo
```python
# api/routers/chat.py

@router.post("/sessions/{session_id}/undo")
async def undo_visualization(
    session_id: str,
    current_user = Depends(get_current_user)
):
    """Undo last visualization action"""
    try:
        previous_state = conversation_context_manager.undo_last_action(session_id)

        if not previous_state:
            return {
                "success": False,
                "message": "Cannot undo: already at the beginning",
                "can_undo": False,
                "can_redo": True
            }

        # Check if can undo/redo more
        context = conversation_context_manager.get_or_create_context(session_id)
        can_undo = context.current_history_index > 0
        can_redo = context.current_history_index < len(context.visualization_history) - 1

        return {
            "success": True,
            "message": f"Undid action: {previous_state.action_description}",
            "rendered_image": previous_state.rendered_image,
            "placed_products": previous_state.placed_products,
            "can_undo": can_undo,
            "can_redo": can_redo,
            "action_description": previous_state.action_description
        }

    except Exception as e:
        logger.error(f"Error in undo: {e}")
        return {"success": False, "message": str(e)}

@router.post("/sessions/{session_id}/redo")
async def redo_visualization(
    session_id: str,
    current_user = Depends(get_current_user)
):
    """Redo previously undone action"""
    try:
        next_state = conversation_context_manager.redo_last_action(session_id)

        if not next_state:
            return {
                "success": False,
                "message": "Cannot redo: already at the latest state",
                "can_undo": True,
                "can_redo": False
            }

        # Check if can undo/redo more
        context = conversation_context_manager.get_or_create_context(session_id)
        can_undo = context.current_history_index > 0
        can_redo = context.current_history_index < len(context.visualization_history) - 1

        return {
            "success": True,
            "message": f"Redid action: {next_state.action_description}",
            "rendered_image": next_state.rendered_image,
            "placed_products": next_state.placed_products,
            "can_undo": can_undo,
            "can_redo": can_redo,
            "action_description": next_state.action_description
        }

    except Exception as e:
        logger.error(f"Error in redo: {e}")
        return {"success": False, "message": str(e)}

@router.get("/sessions/{session_id}/history")
async def get_visualization_history(
    session_id: str,
    current_user = Depends(get_current_user)
):
    """Get visualization history timeline"""
    try:
        history = conversation_context_manager.get_history_summary(session_id)

        return {
            "success": True,
            "history": history,
            "total_states": len(history)
        }

    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return {"success": False, "message": str(e)}
```

#### Part 3: Frontend UI Components
```typescript
// frontend/src/components/VisualizationControls.tsx

interface VisualizationControlsProps {
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  currentAction?: string;
}

export const VisualizationControls: React.FC<VisualizationControlsProps> = ({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  currentAction
}) => {
  return (
    <div className="flex gap-2 items-center bg-white p-2 rounded-lg shadow">
      {/* Undo Button */}
      <button
        onClick={onUndo}
        disabled={!canUndo}
        className={`flex items-center gap-1 px-3 py-2 rounded ${
          canUndo
            ? 'bg-blue-500 hover:bg-blue-600 text-white'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        }`}
        title="Undo last action"
      >
        <ArrowLeftIcon className="w-4 h-4" />
        Undo
      </button>

      {/* Redo Button */}
      <button
        onClick={onRedo}
        disabled={!canRedo}
        className={`flex items-center gap-1 px-3 py-2 rounded ${
          canRedo
            ? 'bg-blue-500 hover:bg-blue-600 text-white'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        }`}
        title="Redo undone action"
      >
        Redo
        <ArrowRightIcon className="w-4 h-4" />
      </button>

      {/* Current Action Indicator */}
      {currentAction && (
        <span className="text-sm text-gray-600 ml-2">
          {currentAction}
        </span>
      )}
    </div>
  );
};
```

#### Part 4: Update Visualization Flow
```python
# api/routers/chat.py - After successful visualization

# OLD: Just store latest state
conversation_context_manager.store_visualization(...)

# NEW: Push to history stack
action_description = self._generate_action_description(
    user_action,
    products_to_place
)

conversation_context_manager.push_visualization_state(
    session_id=session_id,
    rendered_image=viz_result.rendered_image,
    products=all_tracked_products,
    action_description=action_description,  # "Added yellow sofa", "Replaced chair"
    action_type=user_action  # "add", "replace", "move"
)

# Return undo/redo state
context = conversation_context_manager.get_or_create_context(session_id)
response["can_undo"] = context.current_history_index > 0
response["can_redo"] = context.current_history_index < len(context.visualization_history) - 1
response["action_description"] = action_description
```

### Testing Plan
1. **Basic Undo/Redo**:
   - Add table → Add chair → Click Undo → Should show just table
   - Click Redo → Should show table + chair again

2. **Multiple Undo**:
   - Add 5 items → Click Undo 3 times → Should go back 3 states

3. **Undo then New Action** (branch discard):
   - Add table → Add chair → Undo → Add lamp
   - Verify: Cannot redo to chair (forward history discarded)

4. **History Timeline**:
   - Perform 10 actions → View history → Should show all 10 with descriptions

5. **History Limit**:
   - Perform 25 actions → Verify only last 20 saved

---

## Priority Fix Order

1. **Bug #9 (Undo Button)** - Week 1
   - Easier to implement (no AI interpretation needed)
   - High user value - prevents frustration
   - Foundation for Bug #8 (needs history tracking)

2. **Bug #8 (Context-Aware Movement)** - Week 2
   - Requires Bug #9's history system
   - More complex (pronoun resolution, NLP parsing)
   - High impact on UX quality

---

## Implementation Checklist

### Bug #9 (Undo Button)
- [ ] Add `VisualizationState` dataclass to conversation_context.py
- [ ] Implement `push_visualization_state()` method
- [ ] Implement `undo_last_action()` method
- [ ] Implement `redo_last_action()` method
- [ ] Implement `get_history_summary()` method
- [ ] Create `/sessions/{id}/undo` API endpoint
- [ ] Create `/sessions/{id}/redo` API endpoint
- [ ] Create `/sessions/{id}/history` API endpoint
- [ ] Update visualization flow to push states
- [ ] Build VisualizationControls React component
- [ ] Add keyboard shortcuts (Ctrl+Z / Ctrl+Y)
- [ ] Test undo/redo with 10+ actions

### Bug #8 (Context Movement)
- [ ] Add `last_placed_product` tracking to ConversationContext
- [ ] Implement `resolve_product_reference()` in NLP processor
- [ ] Add position vs product keyword disambiguation
- [ ] Update ChatGPT system prompt for movement instructions
- [ ] Create movement action handler in chat router
- [ ] Implement two-pass movement (remove + add at new position)
- [ ] Add "it", "this", "that" pronoun support
- [ ] Add "the [product]" specific reference support
- [ ] Test with coffee table movement scenario
- [ ] Test with multiple products in scene

---

## Success Metrics

**Bug #9 (Undo):**
- Users can undo/redo at least 10 actions
- Undo response time < 500ms (instant)
- 0 data loss during undo/redo
- History persists across page refresh

**Bug #8 (Context Movement):**
- 90%+ accuracy in pronoun resolution ("it", "that")
- 95%+ accuracy distinguishing position vs product keywords
- Moves correct product 95%+ of time
- Maintains product identity during movement (same product, just moved)

---

**Created:** 2025-10-15
**Last Updated:** 2025-10-15
**Status:** Documented - Ready for Implementation
**Estimated Effort:** 2-3 weeks (Bug #9: 1 week, Bug #8: 1-2 weeks)
