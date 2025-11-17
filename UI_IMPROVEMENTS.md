# UI Improvement Plan: Interactive Furniture Visualization

## Overview
Transform the current checkbox-based product selection into an intuitive, two-panel workspace with conversation, filtering, and interactive drag-and-drop visualization.

---

## Architecture: Two-Panel Layout

```
┌──────────────────────────────────────────────────────────────┐
│ Panel 1 (Left 35-40%)        │ Panel 2 (Right 60-65%)        │
│ Conversation & Products       │ Visualization Canvas          │
├───────────────────────────────┼───────────────────────────────┤
│ [CONVERSATION]                │ BEFORE VISUALIZATION:         │
│ User: Show me sofas           │ ┌───────────────────────────┐ │
│ AI: Here are sofas...         │ │ Drop products here        │ │
│ [Input + Photo Upload]        │ │                           │ │
│                               │ │   ◉ Sofa (dropped)        │ │
│ [FILTERS]                     │ │   ◉ Table (dropped)       │ │
│ Website: [chips]              │ │                           │ │
│ Price: [slider]               │ │   [Visualize Button]      │ │
│ □ In Stock                    │ └───────────────────────────┘ │
│                               │                               │
│ [PRODUCT GRID]                │ AFTER VISUALIZATION:          │
│ Showing 12 of 30              │ ┌───────────────────────────┐ │
│ [Draggable products...]       │ │ [AI Generated Image]      │ │
│                               │ │                           │ │
│                               │ │ ◯ Sofa (draggable marker) │ │
│                               │ │ ◯ Table (draggable marker)│ │
│                               │ │                           │ │
│                               │ │ [Regenerate] [Undo][Redo] │ │
│                               │ └───────────────────────────┘ │
└───────────────────────────────┴───────────────────────────────┘
```

---

## Panel 1: Conversation, Filters & Products (Left)

### Section A: Conversation Module (Top - ~300-400px)
**Purpose:** Users chat with AI, upload room images, provide requirements

**Features:**
- Chat message thread (scrollable)
  - User messages (right-aligned, blue)
  - AI responses (left-aligned, gray)
  - Image thumbnails when uploaded
  - Auto-scroll to latest message
- Text input with send button
- Photo upload button for room images
- Follow-up conversations:
  - "Show me similar sofas"
  - "I want something cheaper"
  - "What about modern style?"
  - AI updates product recommendations dynamically

### Section B: Product Filters (Middle - ~120-150px, collapsible)
**Purpose:** Refine displayed product recommendations

**Features:**
- **Website Filter:** Chip toggles
  - westelm.com
  - orangetree.com
  - pelicanessentials.com
- **Price Range Slider:** ₹ min - max with live values
- **Availability Toggle:** "In Stock Only" checkbox
- **Results Counter:** "Showing X of Y products"
- **Clear Filters:** Reset button when filters active

### Section C: Product Grid (Bottom - flex: 1, scrollable)
**Purpose:** Display filtered products, drag to canvas

**Features:**
- 2-3 column responsive grid
- Product cards show:
  - Thumbnail image
  - Product name (truncated)
  - Price + website badge
  - Drag handle icon
- **Draggable:** Drag products from here to Panel 2
- Infinite scroll for large lists (>30 items)

---

## Panel 2: Visualization Canvas (Right)

### State 1: Pre-Visualization (Product Selection Stage)

**Visual:**
```
┌─────────────────────────────────┐
│  Drop Zone                      │
│  "Drag products here"           │
│                                 │
│  ◉ Modern Sofa                  │
│     ₹45,000 | westelm.com      │
│                                 │
│  ◉ Coffee Table                 │
│     ₹12,000 | orangetree.com   │
│                                 │
│  [ Visualize 2 Products ]       │
└─────────────────────────────────┘
```

**Features:**
1. **Drop Zone:** Accept products dragged from Panel 1
2. **Product Chips:** Show dropped products as removable chips/cards
   - Display: Product thumbnail + name + price
   - Remove: X button on each chip
3. **Empty State:** "Drag products here to visualize them in your room"
4. **Visualize Button:**
   - Disabled until at least 1 product dropped
   - Shows count: "Visualize X products"
   - Primary CTA styling

---

### State 2: Post-Visualization (Repositioning Stage)

**Visual:**
```
┌─────────────────────────────────┐
│  [Generated Room Image]         │
│                                 │
│    ◯ (draggable marker - sofa) │
│                                 │
│              ◯ (marker - table) │
│                                 │
│  [ Regenerate ] [ Undo ] [ Redo]│
└─────────────────────────────────┘
```

**Features:**
1. **Visualization Image:** AI-generated room with products placed
2. **Product Markers:** Overlay draggable markers on placed products
   - Circular markers (50px) with product thumbnail
   - Semi-transparent background
   - Positioned where AI placed the product initially
   - **Draggable** to reposition
   - Hover: Show product name + price tooltip
   - Click: Select (highlight border)
   - Delete key: Remove from visualization
3. **Regenerate Button:**
   - "Regenerate with new positions"
   - Sends updated positions to AI
4. **Undo/Redo:** Navigate visualization history
5. **Add More:** Button to return to selection stage

---

## User Workflow

### Step 1: Initial Conversation
1. User opens app → Panel 1 shows conversation + empty products
2. User uploads room image via photo button
3. User types: "Show me modern sofas under ₹50,000"
4. AI responds in chat + displays 30 recommended products in grid

### Step 2: Filter & Refine
1. User expands "Filters" section
2. User adjusts price slider: ₹20,000 - ₹40,000
3. User selects website: westelm only
4. Product grid updates: "Showing 8 of 30 products"
5. User continues chat: "What about leather sofas?" (optional)

### Step 3: Select Products (State 1)
1. User drags sofa from product grid
2. User drops on Panel 2 canvas (anywhere)
3. Sofa appears as chip in drop zone
4. User drags coffee table, drops on canvas
5. "Visualize 2 Products" button activates

### Step 4: Generate Visualization
1. User clicks "Visualize 2 Products"
2. AI generates room with products at **AI-determined** appropriate locations
3. Visualization image displays in Panel 2
4. Product markers appear at AI-placed positions (State 2)

### Step 5: Reposition (Optional)
1. User drags sofa marker to new position on canvas
2. Marker moves immediately (visual feedback)
3. User drags table marker to adjust
4. User clicks "Regenerate"
5. AI creates new visualization with user-specified positions

### Step 6: Iterate
1. User can continue chatting: "The sofa looks too big"
2. Undo/redo to previous visualizations
3. Add more products and repeat
4. Start new layout with different products

---

## Implementation Plan

### Week 1: Panel 1 Structure

**New Files:**
```
frontend/src/components/workspace/
├── ProductPanel.tsx             (left panel container)
├── ConversationModule.tsx       (chat thread)
├── MessageInput.tsx             (input + photo upload)
├── ChatProductFilters.tsx       (filter controls)
└── ProductGrid.tsx              (scrollable product list)
```

**Tasks:**
1. Create ProductPanel as left sidebar (35-40% width)
2. Move existing chat logic into ConversationModule
   - Extract message rendering from ChatInterface
   - Maintain conversation state and history
3. Create MessageInput component
   - Text input with send button
   - Photo upload integration
   - Auto-resize textarea
4. Implement ChatProductFilters
   - Website chip toggles
   - Price range slider (rc-slider)
   - Stock availability toggle
5. Build ProductGrid
   - 2-3 column responsive grid
   - Product cards with drag capability
   - Infinite scroll for large lists
6. Layout: Flexbox with fixed conversation height, scrollable products

**State Management:**
```typescript
const [messages, setMessages] = useState<ChatMessage[]>([])
const [inputMessage, setInputMessage] = useState('')
const [selectedImage, setSelectedImage] = useState<string | null>(null)
const [recommendedProducts, setRecommendedProducts] = useState<Product[]>([])
const [productFilters, setProductFilters] = useState<ProductFilters>({
  websites: [],
  priceRange: [0, 100000],
  inStockOnly: false
})
```

---

### Week 2: Panel 2 - State 1 (Product Selection)

**New Files:**
```
frontend/src/components/workspace/
├── VisualizationCanvas.tsx      (canvas container)
├── ProductSelectionView.tsx     (State 1)
└── ProductChip.tsx              (dropped product display)
```

**Tasks:**
1. Create VisualizationCanvas container (right side, 60-65% width)
2. Build ProductSelectionView:
   - Drop zone with visual feedback
   - Accept drops from ProductGrid
   - Display dropped products as chips/cards
   - Remove button on each chip
3. Add "Visualize X products" button
   - Disabled when no products selected
   - Show product count
4. Handle drag-drop from Panel 1:

```typescript
// ProductGrid - Drag Start
<div
  draggable
  onDragStart={(e) => {
    e.dataTransfer.setData('application/json', JSON.stringify(product))
    e.dataTransfer.effectAllowed = 'copy'
  }}
>

// Canvas - Drop Handler
const handleDrop = (e: React.DragEvent) => {
  e.preventDefault()
  const data = e.dataTransfer.getData('application/json')
  const product = JSON.parse(data)

  // Add to selected products (no position yet)
  setSelectedProducts(prev => {
    // Prevent duplicates
    if (prev.find(p => p.id === product.id)) return prev
    return [...prev, product]
  })
}
```

---

### Week 3: Panel 2 - State 2 (Repositioning)

**New Files:**
```
frontend/src/components/workspace/
├── VisualizationView.tsx        (State 2)
├── ProductMarker.tsx            (draggable overlay)
└── CanvasControls.tsx           (action buttons)
```

**Tasks:**
1. Build VisualizationView:
   - Display AI-generated visualization image
   - Overlay product markers at AI-determined positions
2. Create ProductMarker component:
   - Circular marker (50px) with product thumbnail
   - Positioned absolutely using x, y percentages
   - Draggable within canvas bounds
   - Selected state (click, border highlight)
   - Hover tooltip (product name, price)
   - Delete on keyboard press
3. Implement marker drag logic:

```typescript
const handleDragEnd = (markerId: string, e: React.DragEvent) => {
  const rect = imageRef.current.getBoundingClientRect()
  const x = Math.max(0, Math.min(100,
    ((e.clientX - rect.left) / rect.width) * 100
  ))
  const y = Math.max(0, Math.min(100,
    ((e.clientY - rect.top) / rect.height) * 100
  ))

  updateMarkerPosition(markerId, { x, y })
}
```

4. Create CanvasControls:
   - "Regenerate" button (sends new positions to API)
   - "Add More Products" button (return to State 1)
   - Undo/Redo buttons (reuse existing logic)

---

### Week 4: API Integration & Backend

**Frontend API Updates:**
```typescript
// utils/api.ts
export async function visualizeRoom(sessionId: string, request: {
  products: Product[]
  positions?: ProductPosition[]  // Optional - null for initial
  image: string
  action: string
}) {
  const response = await fetch(
    `/api/chat/sessions/${sessionId}/visualize`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    }
  )

  return response.json()
}
```

**Backend Changes:**

`api/routers/chat.py`:
```python
class ProductPosition(BaseModel):
    product_id: int
    x: float  # 0-100 percentage
    y: float  # 0-100 percentage

class VisualizationRequest(BaseModel):
    products: List[ProductForVisualization]
    positions: Optional[List[ProductPosition]] = None  # NEW
    image: Optional[str] = None
    action: str = "add"

class VisualizationResponse(BaseModel):
    rendered_image: str
    placed_products: List[PlacedProductInfo]  # NEW - AI positions

class PlacedProductInfo(BaseModel):
    product_id: int
    position: ProductPosition

@router.post("/sessions/{session_id}/visualize")
async def visualize_room(...):
    if request.positions is None:
        # First visualization - AI decides positions
        result = await google_ai_service.generate_room_visualization(
            products=request.products,
            room_image=room_image
        )

        return VisualizationResponse(
            rendered_image=result.image,
            placed_products=result.placed_products
        )
    else:
        # Regeneration with user positions
        result = await google_ai_service.generate_room_visualization(
            products=request.products,
            room_image=room_image,
            positions=request.positions
        )

        return VisualizationResponse(
            rendered_image=result.image,
            placed_products=[...]
        )
```

`api/services/google_ai_service.py`:
```python
async def generate_room_visualization(
    self,
    products: List[Product],
    room_image: str,
    positions: Optional[List[ProductPosition]] = None
) -> VisualizationResult:

    if positions:
        # User has specified positions - use them
        prompt = f"""Place these products at the specified locations:

{self._build_position_instructions(products, positions)}

Follow the position percentages as closely as possible."""
    else:
        # AI decides best placement
        prompt = f"""Place these products in appropriate locations:

{self._build_product_list(products)}

Use interior design best practices."""

    # Generate with Gemini...

def _build_position_instructions(self, products, positions):
    instructions = ""
    for pos in positions:
        product = next(p for p in products if p.id == pos.product_id)
        instructions += f"\n- {product.name}: {pos.x}% from left, {pos.y}% from top"
    return instructions
```

---

### Week 5: Polish & Responsive Design

**Tasks:**
1. **Responsive Layout:**
   - Desktop (>1200px): Side-by-side panels (35/65)
   - Tablet (768-1200px): Collapsible Panel 1, toggle button
   - Mobile (<768px): Vertical stack, tabs to switch panels

2. **Conversation UX:**
   - Auto-scroll to new messages
   - Typing indicator
   - Message timestamps
   - Retry failed messages

3. **Filter UX:**
   - Smooth animations (framer-motion)
   - Filter badges showing active filters
   - "Clear all" when filters applied

4. **Canvas UX:**
   - Grid snap (optional, toggleable)
   - Zoom controls (optional)
   - Multi-select markers (Shift+click)
   - Keyboard shortcuts (Del, Ctrl+Z, Ctrl+Y)

5. **Loading States:**
   - Skeleton loaders for products
   - Canvas loading overlay
   - Progress indicators

6. **Error Handling:**
   - "No room image uploaded" warning
   - "No products placed" message
   - Network error recovery

---

## Component Structure

```
ChatInterface.tsx (orchestrator)
└── WorkspaceLayout.tsx
    ├── ProductPanel.tsx (Panel 1)
    │   ├── ConversationModule.tsx
    │   │   ├── MessageBubble.tsx
    │   │   └── ImageThumbnail.tsx
    │   ├── MessageInput.tsx
    │   │   ├── TextInput
    │   │   └── PhotoUploadButton
    │   ├── ChatProductFilters.tsx
    │   │   ├── WebsiteChips.tsx
    │   │   ├── PriceRangeSlider.tsx
    │   │   └── StockToggle.tsx
    │   └── ProductGrid.tsx
    │       └── DraggableProductCard.tsx
    │
    └── VisualizationCanvas.tsx (Panel 2)
        ├── ProductSelectionView.tsx (State 1)
        │   ├── DropZone.tsx
        │   ├── ProductChip.tsx
        │   └── VisualizeButton.tsx
        │
        └── VisualizationView.tsx (State 2)
            ├── GeneratedImage.tsx
            ├── ProductMarker.tsx
            └── CanvasControls.tsx
                ├── RegenerateButton
                ├── AddMoreButton
                └── UndoRedoButtons
```

---

## Key State Management

```typescript
// Main workspace state
const [workspaceState, setWorkspaceState] = useState<'selection' | 'visualization'>('selection')

// State 1: Product Selection
const [selectedProducts, setSelectedProducts] = useState<Product[]>([])

// State 2: Visualization
const [visualizationImage, setVisualizationImage] = useState<string | null>(null)
const [placedProducts, setPlacedProducts] = useState<PlacedProduct[]>([])

interface PlacedProduct {
  id: string            // unique marker ID
  product: Product      // full product data
  position: {
    x: number          // % from left (0-100)
    y: number          // % from top (0-100)
  }
}

// Conversation
const [messages, setMessages] = useState<ChatMessage[]>([])
const [roomImage, setRoomImage] = useState<string | null>(null)

// Filters
const [filters, setFilters] = useState<ProductFilters>({
  websites: [],
  priceRange: [0, 100000],
  inStockOnly: false
})
```

---

## Technical Specifications

### Panel 1 Layout
```css
.product-panel {
  width: 35%;
  min-width: 380px;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e5e7eb;
}

.conversation-module {
  height: 350px;
  overflow-y: auto;
  flex-shrink: 0;
}

.filter-section {
  padding: 16px;
  border-top: 1px solid #e5e7eb;
  border-bottom: 1px solid #e5e7eb;
}

.product-grid {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
```

### Panel 2 Layout
```css
.visualization-canvas {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

.room-image-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.canvas-controls {
  height: 60px;
  padding: 12px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 8px;
  justify-content: center;
}
```

### ProductMarker Positioning
```typescript
// Position marker using percentages
<div
  className="product-marker"
  style={{
    position: 'absolute',
    left: `${marker.position.x}%`,
    top: `${marker.position.y}%`,
    transform: 'translate(-50%, -50%)'  // Center on position
  }}
  draggable
  onDragEnd={handleDragEnd}
>
```

---

## Dependencies

```json
{
  "react-dnd": "^16.0.1",
  "react-dnd-html5-backend": "^16.0.1",
  "rc-slider": "^10.5.0",
  "framer-motion": "^10.16.4"
}
```

---

## Migration Strategy

### Phase 1: Build Alongside Existing
- Keep current ChatInterface.tsx active
- Build workspace in separate route: `/chat/workspace`
- Link: "Try New Workspace" button in old UI

### Phase 2: A/B Testing
- 50% users see new workspace
- 50% users see old checkbox UI
- Collect metrics: conversion, time-to-visualize, satisfaction

### Phase 3: Full Rollout
- Based on positive feedback, make workspace default
- Keep old UI as fallback (preference toggle)

---

## Success Metrics

- **Reduced interaction time:** From 5+ clicks to 2 main actions (drag + visualize)
- **Improved positioning accuracy:** 80% of AI placements accepted without changes
- **Higher engagement:** 40% more follow-up conversations
- **Filter usage:** 60% of users apply at least one filter
- **Repositioning usage:** 40% of users adjust at least 1 product position
- **Regeneration rate:** 25% of visualizations get regenerated with new positions
- **Visualization rate:** 25% increase in users generating visualizations

---

## Future Enhancements (Phase 2+)

### Product Swapping Panel (Deferred)
- Third panel or modal for swapping products
- "Similar products" endpoint
- One-click swap functionality

### Advanced Features
- Save/load layouts
- Multiple room images in one session
- Product comparison side-by-side
- Export visualization with product list
- Collaboration features (share layouts)
- Price breakdown for selected products

---

## Key Workflow Clarification

**IMPORTANT:** The drag-drop workflow is:
1. **Drag from Panel 1 → Drop anywhere on Panel 2** = SELECT product (not position)
2. **Click "Visualize"** = AI generates room with products at AI-determined locations
3. **Drag markers on visualization image** = REPOSITION products
4. **Click "Regenerate"** = AI creates new visualization with user positions

This allows AI to make smart initial placement decisions while giving users full control to adjust.
