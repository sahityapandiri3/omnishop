# Workflow Implementation Plan

## Current Status
- Test file `test_replace_scenario.py` expects 3-step furniture detection/visualization workflow
- Current API has 3-mode visualization system that doesn't match test expectations
- Schemas have been updated to support the workflow
- Backup of current chat.py created: `api/routers/chat.py.backup`

## Required Workflow

### Step 1: Initial Request
**Trigger**: `image + message + NO selected_product_id + NO user_action`
**Actions**:
1. ChatGPT analyzes image + message → `analysis`
2. Gemini detects all furniture in room → `detected_furniture` list
3. Get product recommendations from DB based on analysis
**Returns**: `recommended_products`, `detected_furniture`

### Step 2: Furniture Detection & Choice
**Trigger**: `selected_product_id + NO user_action` (message contains "visualize")
**Actions**:
1. Get product details from DB
2. Determine product furniture type (e.g., "sofa", "chair", "table")
3. Gemini checks if similar furniture type exists in image
4. If exists: return options to ADD or REPLACE
5. If not exists: return option to ADD only
**Returns**: `similar_furniture_items`, `action_options` ["add"] or ["add", "replace"], `requires_action_choice=True/False`

### Step 3: Generate Visualization
**Trigger**: `selected_product_id + user_action` ("add" or "replace")
**Actions**:
1. Get product details and image from DB
2. Get stored room image from conversation context
3. Call Gemini with appropriate prompt:
   - **ADD**: "Add {product_name} to this room in an appropriate location without removing any existing furniture"
   - **REPLACE**: "Replace the existing {furniture_type} in this room with {product_name}"
4. Return generated visualization image
**Returns**: `image_url` (visualization)

## Implementation Tasks

### 1. Add Functions to `google_ai_service.py`

```python
async def detect_furniture_in_image(image_data: str) -> List[Dict[str, Any]]:
    """
    Detect all furniture items in the image
    Returns: [{"furniture_type": "sofa", "confidence": 0.95}, ...]
    """
    # Use Gemini 2.0 Flash to analyze image and list all furniture
    # Prompt: "List all furniture items visible in this room image.
    #          For each item, provide: furniture_type and confidence (0-1)"
    pass

async def check_furniture_exists(image_data: str, furniture_type: str) -> Tuple[bool, List[Dict]]:
    """
    Check if specific furniture type exists in image
    Returns: (exists: bool, matching_items: List[Dict])
    """
    # Use Gemini to check if furniture_type (e.g., "sofa") exists
    # Return matching furniture items if found
    pass

async def generate_add_visualization(room_image: str, product_name: str, product_image: str) -> str:
    """
    Generate visualization with product ADDED to room
    Returns: base64 image data
    """
    # Use Gemini Imagen to generate visualization
    # Prompt: "Add {product_name} to this room in an appropriate location..."
    pass

async def generate_replace_visualization(room_image: str, product_name: str,
                                        furniture_type: str, product_image: str) -> str:
    """
    Generate visualization with furniture REPLACED
    Returns: base64 image data
    """
    # Use Gemini Imagen to generate visualization
    # Prompt: "Replace the existing {furniture_type} with {product_name}..."
    pass
```

### 2. Update `chat.py` send_message endpoint

Replace the current complex logic (lines 61-250) with:

```python
@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: str,
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    # Verify session, store image, save user message (keep existing code)

    # Get ChatGPT analysis
    conversational_response, analysis = await chatgpt_service.analyze_user_input(...)

    # Save assistant message (keep existing code)

    # Initialize response fields
    recommended_products = []
    detected_furniture = None
    similar_furniture_items = None
    action_options = None
    requires_action_choice = False
    visualization_image = None

    # STEP 1: Initial request (image + message, no product selected)
    if request.image and request.message and not request.selected_product_id and not request.user_action:
        # Get furniture detection
        detected_furniture = await google_ai_service.detect_furniture_in_image(request.image)

        # Get product recommendations
        if analysis:
            recommended_products = await _get_product_recommendations(analysis, db, ...)

    # STEP 2: Visualize request (product selected, no action yet)
    elif request.selected_product_id and not request.user_action:
        # Get product from DB
        product = await db.get(Product, int(request.selected_product_id))
        if not product:
            raise HTTPException(404, "Product not found")

        # Determine furniture type from product name
        furniture_type = _extract_furniture_type(product.name)

        # Check if furniture exists in stored image
        stored_image = conversation_context_manager.get_image(session_id)
        if stored_image:
            exists, matching_items = await google_ai_service.check_furniture_exists(
                stored_image, furniture_type
            )

            similar_furniture_items = matching_items if exists else []

            if exists and matching_items:
                action_options = ["add", "replace"]
                requires_action_choice = True
            else:
                action_options = ["add"]
                requires_action_choice = False

    # STEP 3: Action execution (product selected + action specified)
    elif request.selected_product_id and request.user_action:
        # Get product from DB with images
        product_query = select(Product).options(selectinload(Product.images))\\
                                      .where(Product.id == int(request.selected_product_id))
        result = await db.execute(product_query)
        product = result.scalar_one_or_none()

        if not product:
            raise HTTPException(404, "Product not found")

        # Get product image
        product_image_url = None
        if product.images:
            primary_img = next((img for img in product.images if img.is_primary), product.images[0])
            product_image_url = primary_img.original_url

        # Get stored room image
        room_image = conversation_context_manager.get_image(session_id)
        if not room_image:
            raise HTTPException(400, "No room image found in conversation")

        # Generate visualization based on action
        furniture_type = _extract_furniture_type(product.name)

        if request.user_action == "add":
            visualization_image = await google_ai_service.generate_add_visualization(
                room_image=room_image,
                product_name=product.name,
                product_image=product_image_url
            )
        elif request.user_action == "replace":
            visualization_image = await google_ai_service.generate_replace_visualization(
                room_image=room_image,
                product_name=product.name,
                furniture_type=furniture_type,
                product_image=product_image_url
            )
        else:
            raise HTTPException(400, f"Invalid action: {request.user_action}")

    # Create response
    message_schema = ChatMessageSchema(
        id=assistant_message_id,
        type=MessageType.assistant,
        content=conversational_response,
        timestamp=assistant_message.timestamp,
        session_id=session_id,
        products=recommended_products,
        image_url=visualization_image
    )

    return ChatMessageResponse(
        message=message_schema,
        analysis=analysis,
        recommended_products=recommended_products,
        detected_furniture=detected_furniture,
        similar_furniture_items=similar_furniture_items,
        requires_action_choice=requires_action_choice,
        action_options=action_options
    )
```

### 3. Add Helper Function

```python
def _extract_furniture_type(product_name: str) -> str:
    """Extract furniture type from product name"""
    name_lower = product_name.lower()

    if 'sofa' in name_lower or 'couch' in name_lower:
        return 'sofa'
    elif 'chair' in name_lower or 'armchair' in name_lower:
        return 'chair'
    elif 'table' in name_lower:
        if 'coffee' in name_lower or 'center' in name_lower:
            return 'coffee table'
        elif 'dining' in name_lower:
            return 'dining table'
        return 'table'
    elif 'bed' in name_lower:
        return 'bed'
    elif 'lamp' in name_lower:
        return 'lamp'
    else:
        # Default: extract first word
        return name_lower.split()[0]
```

## Testing

After implementation, run:
```bash
python3 test_replace_scenario.py
```

Expected results:
- Step 1: Receives products + detected_furniture list
- Step 2: Receives similar_furniture_items + action_options + requires_action_choice
- Step 3: Receives visualization image

## Files to Modify
1. `/Users/sahityapandiri/Omnishop/api/services/google_ai_service.py` - Add 4 new functions
2. `/Users/sahityapandiri/Omnishop/api/routers/chat.py` - Replace send_message logic
3. Test with `/Users/sahityapandiri/Omnishop/test_replace_scenario.py`
