# Omnishop UI V2 - Requirements and Implementation Plan

## Overview
This document outlines the requirements and implementation plan for Omnishop's next-generation user interface, focusing on an intuitive, conversational approach to interior design visualization.

---

## Wireframes

### 1. Landing Page Wireframe

```
┌────────────────────────────────────────────────────────────────┐
│  [OMNISHOP LOGO]                                    [Sign In]  │
└────────────────────────────────────────────────────────────────┘
│                                                                │
│                    ┌─────────────────┐                         │
│                    │   Hero Image    │                         │
│                    │  (Room Visual)  │                         │
│                    └─────────────────┘                         │
│                                                                │
│            Visualize Furniture in Your Space                   │
│            Before You Buy                                      │
│                                                                │
│     Chat with our AI to find perfect pieces for your room     │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐   │
│   │                                                      │   │
│   │        📸  Drag & drop your room image here         │   │
│   │              or click to browse                      │   │
│   │                                                      │   │
│   │         [Accepted formats: JPG, PNG, WEBP]          │   │
│   │              [Max size: 10MB]                        │   │
│   │                                                      │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                                │
│        [  Upload & Continue  ]   [  Upload Later  ]           │
│                                                                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 2. Main Application Screen - Desktop Layout (1280px+)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  [🏠 OMNISHOP]         Dashboard                           [👤 Profile] [⚙️ Settings]  │
├──────────────────┬──────────────────────────────────┬───────────────────────────────────┤
│                  │                                  │                                   │
│ CHAT INTERFACE   │   PRODUCT DISCOVERY              │   CANVAS & VISUALIZATION          │
│ (25%)            │   (50%)                          │   (25%)                           │
│                  │                                  │                                   │
│ ┌──────────────┐ │ ┌──────────────────────────────┐ │ ┌───────────────────────────────┐ │
│ │ 💬 Design    │ │ │ Search: "modern sofa"    🔍  │ │ │ Your Canvas         [Clear]   │ │
│ │ Assistant    │ │ │                              │ │ │ 3 items added                 │ │
│ └──────────────┘ │ │ Sort: [Relevance ▼] Filters▼│ │ └───────────────────────────────┘ │
│                  │ └──────────────────────────────┘ │                                   │
│ ┌──────────────┐ │                                  │ ┌───────────────────────────────┐ │
│ │ AI: Hi! I'm  │ │ ┌────────┬────────┬────────┐   │ │ 📷 Room Image                 │ │
│ │ here to help │ │ │┌──────┐│┌──────┐│┌──────┐│   │ │ ┌─────────────────────────┐   │ │
│ │ you design   │ │ ││ Img  │││ Img  │││ Img  ││   │ │ │                         │   │ │
│ │ your space!  │ │ │└──────┘│└──────┘│└──────┘│   │ │ │   [Room Preview]        │   │ │
│ └──────────────┘ │ │ Sofa   │ Chair  │ Table  │   │ │ │                         │   │ │
│                  │ │ $599   │ $299   │ $399   │   │ │ └─────────────────────────┘   │ │
│ ┌──────────────┐ │ │ [○]Add │ [●]Add │ [○]Add │   │ │ [Change Image]                │ │
│ │ User: I need │ │ │westelm │westelm │westelm │   │ │                               │ │
│ │ modern sofa  │ │ └────────┴────────┴────────┘   │ └───────────────────────────────┘ │
│ └──────────────┘ │                                  │                                   │
│                  │ ┌────────┬────────┬────────┐   │ ┌───────────────────────────────┐ │
│ ┌──────────────┐ │ │┌──────┐│┌──────┐│┌──────┐│   │ │ Products in Canvas [Grid▼]   │ │
│ │ AI: Found 12 │ │ ││ Img  │││ Img  │││ Img  ││   │ │                               │ │
│ │ modern sofas │ │ │└──────┘│└──────┘│└──────┘│   │ │ ┌───┐ ┌───┐ ┌───┐            │ │
│ │ for you!     │ │ │ Lamp   │ Rug    │ Mirror │   │ │ │So │ │Ch │ │Ta │            │ │
│ └──────────────┘ │ │ $129   │ $199   │ $89    │   │ │ │fa │ │air│ │ble│            │ │
│                  │ │ [○]Add │ [○]Add │ [○]Add │   │ │ │[X]│ │[X]│ │[X]│            │ │
│      ⋮           │ │orangetr│pelican │westelm │   │ │ └───┘ └───┘ └───┘            │ │
│                  │ └────────┴────────┴────────┘   │ │ $599  $299  $399              │ │
│ ┌──────────────┐ │                                  │ └───────────────────────────────┘ │
│ │ [Type msg..] │ │                                  │                                   │
│ │        [Send]│ │ [Load More Products...]          │ ┌───────────────────────────────┐ │
│ └──────────────┘ │                                  │ │                               │ │
│                  │                                  │ │   [ 🎨 VISUALIZE ROOM ]      │ │
│                  │                                  │ │                               │ │
│                  │                                  │ └───────────────────────────────┘ │
└──────────────────┴──────────────────────────────────┴───────────────────────────────────┘
```

### 3. Panel 2 - Product Card Detailed View

```
┌─────────────────────────────────────────────────────────┐
│ ┌───────────────────────────────────────────────────┐   │
│ │                                                   │   │
│ │           [Product Image - 300x300px]            │   │
│ │                                                   │   │
│ └───────────────────────────────────────────────────┘   │
│                                                         │
│ [SOFA] Modern Minimalist 3-Seater Sofa                 │
│                                                         │
│ ₹45,999  [westelm.com 🔗]                              │
│                                                         │
│ ⭐⭐⭐⭐☆ (4.2) · 124 reviews                           │
│                                                         │
│ Color: Gray | Material: Linen                          │
│ Dimensions: 84" W x 36" D x 32" H                      │
│                                                         │
│ [◯ Select]              [+ Add to Canvas]              │
│                         (disabled - select first)      │
└─────────────────────────────────────────────────────────┘
```

### 4. Panel 3 - After Visualization (Click-to-Move Mode)

```
┌─────────────────────────────────────────────────────────┐
│ Your Canvas                        [Clear] [Edit Mode▼] │
│ 3 items · Total: ₹51,297                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 🖼️  VISUALIZATION RESULT                                │
│                                                         │
│ ┌───────────────────────────────────────────────────┐   │
│ │                                                   │   │
│ │        [  Rendered Room Image  ]                 │   │
│ │                                                   │   │
│ │    ┌─────────────┐    ← Sofa (clickable)         │   │
│ │    │   [SOFA]    │                               │   │
│ │    │  Selected!  │                               │   │
│ │    └─────────────┘                               │   │
│ │                                                   │   │
│ │          [CHAIR]  ← Chair (clickable)            │   │
│ │                                                   │   │
│ │                  [TABLE] ← Table (clickable)     │   │
│ │                                                   │   │
│ └───────────────────────────────────────────────────┘   │
│                                                         │
│ 💡 Click furniture to select, then click location      │
│    to move it                                           │
│                                                         │
│ [ ◀ Undo ]  [ Redo ▶ ]  [ 🔄 Re-visualize ]           │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ Products in Canvas                      [Grid] [List ▼]│
│                                                         │
│ ✓ Modern Sofa                              [Remove]    │
│   westelm.com · ₹45,999                                │
│   Position: Center-Left                                │
│                                                         │
│ ✓ Accent Chair                             [Remove]    │
│   orangetree.com · ₹12,999                             │
│   Position: Right-Side                                 │
│                                                         │
│ ✓ Coffee Table                             [Remove]    │
│   pelican.com · ₹18,299                                │
│   Position: Center                                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 5. Mobile View Wireframe (< 768px)

```
┌─────────────────────────────┐
│ [☰]  OMNISHOP      [👤][⚙️] │
├─────────────────────────────┤
│                             │
│ [Chat] [Products] [Canvas]  │
│   ▔▔▔▔             (tabs)   │
│                             │
│ ┌─────────────────────────┐ │
│ │ 💬 Design Assistant     │ │
│ ├─────────────────────────┤ │
│ │                         │ │
│ │ AI: Hi! How can I help  │ │
│ │     you design?         │ │
│ │                         │ │
│ │        You: I need a    │ │
│ │        modern sofa      │ │
│ │                         │ │
│ │ AI: Found 12 sofas!     │ │
│ │     Check Products tab  │ │
│ │                         │ │
│ ├─────────────────────────┤ │
│ │ [Type message...]       │ │
│ │              [Send]     │ │
│ └─────────────────────────┘ │
│                             │
│ ─────────────────────────── │
│ [   🎨 VISUALIZE (3)   ]   │
│     (sticky bottom btn)     │
└─────────────────────────────┘
```

---

## External Service Integrations

### Panel 1: Chat Interface Services

#### 1. ChatGPT API (OpenAI)
- **Service**: `api/services/chatgpt_service.py`
- **Model**: GPT-4 or GPT-4o (configured via `settings.openai_model`)
- **Purpose**:
  - Natural language understanding of user design requirements
  - Conversational AI responses
  - Design analysis and product matching
  - Intent classification (search, visualize, refine)
  - Extraction of style preferences, colors, materials
- **Key Methods**:
  - `analyze_user_input()` - Process user messages and return structured analysis
  - `detect_furniture_with_bounding_boxes()` - Vision API for furniture detection
- **Rate Limiting**: 50 requests/minute (configurable)
- **Timeout**: 60 seconds per request
- **Cost**: ~$0.01-0.03 per conversation turn
- **Output Format**: Structured JSON with `product_matching_criteria`, `design_analysis`, `visualization_mode`

#### 2. GPT-4 Vision API
- **Service**: Same as ChatGPT, vision-enabled endpoint
- **Purpose**:
  - Analyze uploaded room images
  - Detect existing furniture and room layout
  - Extract spatial information (room type, dimensions, lighting)
- **Model**: `gpt-4o` with vision capabilities
- **Use Cases**:
  - Room image analysis on upload
  - Furniture detection for replacement scenarios
  - Spatial understanding for better recommendations

#### 3. File Upload Service
- **Backend**: FastAPI multipart file upload
- **Endpoint**: `POST /api/upload/room-image`
- **Processing**:
  - Image validation (JPG, PNG, WEBP formats)
  - Size limits (10MB max)
  - Base64 encoding for API transfers
  - PIL/Pillow for image preprocessing
  - Resizing to optimal dimensions (max 1024px)
- **Storage**: Temporary storage for session duration

---

### Panel 2: Product Discovery Services

#### 1. Product Database (PostgreSQL)
- **Endpoint**: `GET /api/products`
- **Purpose**: Query scraped product catalog
- **Data Sources**:
  - westelm.com
  - orangetree.com
  - pelicanessentials.com
- **Features**:
  - Full-text search by keywords
  - Filtering by price range, category, material, color, style
  - Sorting by price, relevance, popularity
  - Pagination support
- **Integration**: Receives search criteria from ChatGPT analysis in Panel 1

#### 2. Product Scraping Service (Scrapy)
- **Background Service**: Scheduled Scrapy spiders
- **Purpose**: Keep product catalog fresh and up-to-date
- **Spiders**:
  - `westelm_spider.py`
  - `orangetree_spider.py`
  - `pelican_spider.py`
- **Schedule**: Daily incremental updates
- **Data Sync**: Automatic product addition/update in PostgreSQL

#### 3. ChatGPT Integration (Indirect)
- **Data Flow**: Panel 1 → Panel 2
- **Mechanism**:
  - ChatGPT generates `product_matching_criteria` JSON
  - Panel 2 uses these criteria to filter database
  - Search terms, categories, price ranges extracted from chat
- **Example**:
  ```json
  {
    "product_types": ["sofa", "chair"],
    "categories": ["modern", "minimalist"],
    "search_terms": ["contemporary sofa", "accent chair"],
    "filtering_keywords": {
      "include_terms": ["linen", "fabric", "gray"],
      "exclude_terms": ["leather", "traditional"]
    }
  }
  ```

#### 4. Product Image CDN
- **Sources**: Direct image URLs from e-commerce websites
- **Optimization**:
  - Next.js Image component with automatic optimization
  - Lazy loading for performance
  - Responsive image sizing
- **Fallback**: Placeholder images for broken/missing links
- **Caching**: Browser cache + React Query cache (5 minutes)

---

### Panel 3: Canvas & Visualization Services

#### 1. Google Gemini 2.5 Flash (Primary Visualization Engine)
- **Service**: `api/services/google_ai_service.py`
- **Model**: `gemini-2.5-flash-preview-0514`
- **Purpose**: Generate photorealistic room visualizations with furniture placement
- **Key Methods**:
  - `generate_room_visualization()` - Main visualization generation
  - `analyze_room_image()` - Room context understanding
- **Input Requirements**:
  - Base room image (base64 encoded)
  - Product images (URLs or base64)
  - Placement instructions (natural language or coordinates)
  - User's design preferences from chat context
  - Product positions (if manually adjusted)
- **Output**:
  - Rendered visualization image (base64)
  - Quality scores and confidence metrics
  - Processing time statistics
- **Rate Limiting**: Project-based quota
- **Timeout**: 120 seconds per request
- **Cost**: ~$0.001-0.005 per visualization (much cheaper than GPT-4)

#### 2. Replicate Inpainting API (Fallback/Alternative)
- **Service**: `api/services/replicate_inpainting_service.py`
- **Models**:
  - SDXL Inpainting
  - ControlNet for precise placement
- **Purpose**: High-quality furniture inpainting for advanced scenarios
- **Use Cases**:
  - When Gemini quality is insufficient
  - For furniture replacement (removing existing items)
  - Users wanting maximum photorealism
- **Cost**: ~$0.02-0.10 per generation (more expensive)
- **Timeout**: 60-300 seconds depending on model complexity

#### 3. IP-Adapter Inpainting (Advanced Option)
- **Service**: `api/services/ip_adapter_inpainting_service.py`
- **Purpose**: Product-specific inpainting with reference images
- **Technology**: IP-Adapter + Stable Diffusion
- **Use Cases**:
  - Users wanting exact product appearance
  - High-fidelity brand-accurate visualizations
- **Deployment**: Can run locally or on cloud GPUs

#### 4. ChatGPT Vision - Furniture Detection
- **Method**: `chatgpt_service.detect_furniture_with_bounding_boxes()`
- **Purpose**:
  - Detect existing furniture in room images
  - Generate normalized bounding boxes (0-1 coordinate range)
  - Identify furniture types, positions, and sizes
- **Use Cases**:
  - Enable click-to-move functionality
  - Furniture replacement scenarios
  - Spatial understanding for placement
- **Output Example**:
  ```json
  {
    "detected_objects": [
      {
        "object_type": "sofa",
        "bounding_box": {"x1": 0.15, "y1": 0.35, "x2": 0.75, "y2": 0.85},
        "position": "center-left",
        "size": "large",
        "confidence": 0.95
      }
    ]
  }
  ```

#### 5. Canvas Manipulation Libraries
- **Fabric.js** (v5.3.0):
  - 2D canvas manipulation
  - Interactive object handling
  - Already installed in frontend
- **Konva.js + React-Konva**:
  - 2D drawing and interactions
  - Furniture marker overlays
  - Click detection and movement tracking

#### 6. Click-to-Move Implementation
- **Technology**: React state + Canvas libraries
- **Workflow**:
  1. User clicks furniture item → Select furniture (highlight)
  2. User clicks destination → Calculate new position
  3. Update furniture coordinates in state
  4. Option: Re-visualize with new positions OR move marker only
- **State Management**:
  - React Query for server state
  - Local state for furniture positions
  - Undo/redo history stack

---

### Cross-Panel Integration Flow

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Panel 1       │         │   Panel 2        │         │   Panel 3       │
│   CHAT          │         │   PRODUCTS       │         │   CANVAS        │
└─────────────────┘         └──────────────────┘         └─────────────────┘
        │                           │                             │
        ▼                           ▼                             ▼
  ChatGPT API              Product Database              Gemini 2.5 Flash
  (OpenAI)                 (PostgreSQL)                  (Google AI)
        │                           │                             │
        │                           │                             │
User: "modern sofa" ──────────────► Search products with         │
        │                    AI-generated keywords               │
        │                           │                             │
        │                           │                             │
        │      Product selected ────────────────────────────────► Add to canvas
        │                           │                             │
        │                           │                             │
        │                           │        "Visualize" clicked ─┤
        │                           │                             │
        │                           │      ┌──────────────────────┘
        │                           │      ▼
        │                           │   Gemini API Call:
        │                           │   - Room image (base64)
        │                           │   - Product images
        │                           │   - Placement instructions
        │                           │   - Design context from chat
        │                           │      │
        │      ◄───────────────────────────┘
        │      Visualization displayed
        │                           │                             │
        │                           │      User clicks furniture ─┤
        │                           │      then clicks new spot   │
        │                           │                             │
        │                           │      ┌──────────────────────┘
        │                           │      ▼
        │                           │   Update position coords
        │                           │   Re-visualize (optional)
```

---

### API Rate Limits & Cost Summary

| Service | Provider | Rate Limit | Cost/Request | Timeout | Criticality |
|---------|----------|------------|--------------|---------|-------------|
| ChatGPT API | OpenAI | 50-60 req/min | $0.01-0.03 | 60s | **Critical** |
| GPT-4 Vision | OpenAI | Same as above | $0.02-0.05 | 60s | Optional |
| Gemini 2.5 Flash | Google AI | Project quota | $0.001-0.005 | 120s | **Critical** |
| Replicate Inpainting | Replicate | Account-based | $0.02-0.10 | 60-300s | Fallback |
| Product Database | Internal | Unlimited | Free | <1s | **Critical** |
| Product Scrapers | Internal | N/A | Free | Background | Background |
| Image CDN | External | N/A | Free | 5s | **Critical** |

**Monthly Cost Estimates** (for 1000 active users):
- ChatGPT: ~$200-400 (10-20 messages per user)
- Gemini Visualizations: ~$50-100 (10 visualizations per user)
- Replicate (if used): ~$100-200 (occasional use)
- **Total**: ~$350-700/month for AI services

---

## Phase 1: Core User Experience

### 1. Landing Page (Entry Screen)

#### Purpose
Onboard users and collect their room image for visualization.

#### Requirements

**Functional Requirements:**
- Display quick introduction explaining how the app helps users visualize furniture in their rooms
- Provide clear call-to-action for room image upload
- Allow users to skip upload and proceed without image initially
- Smooth transition to main application screen

**UI Components:**
- **Hero Section**: Brief intro text explaining app capabilities
  - "Visualize furniture in your space before you buy"
  - "Chat with our AI to find perfect pieces for your room"
- **Image Upload Area**:
  - Drag-and-drop zone or file picker
  - Preview of uploaded image
  - Image validation (format, size)
- **Action Buttons**:
  - "Upload & Continue" (primary button - enabled when image selected)
  - "Upload Later" (secondary button - always enabled)

**User Flow:**
```
Landing Page → Upload Image (Optional) → Main Application Screen
                     ↓
              Skip ("Upload Later")
                     ↓
              Main Application Screen (upload required before visualization)
```

---

### 2. Main Application Screen - Three Panel Layout

The main screen consists of three distinct panels working together to provide a seamless experience.

---

#### Panel 1: Conversational Chat Interface (Left Panel)

**Purpose**: Enable natural language interaction for design requirements and product discovery.

**Functional Requirements:**
- Real-time chat interface with AI assistant
- Message history persistence
- Support for text input
- Display AI responses with product recommendations
- Show typing indicators during AI processing

**UI Components:**
- **Chat Message Area**:
  - User messages (right-aligned, distinct color)
  - AI responses (left-aligned, distinct color)
  - Timestamps
  - Auto-scroll to latest message
- **Input Area**:
  - Multi-line text input field
  - Send button
  - Character counter (optional)
  - "Suggested prompts" for first-time users
- **Header**:
  - Session indicator
  - Clear conversation button
  - Help/tips icon

**Example Interactions:**
- "I need a modern sofa for my living room"
- "Show me center tables under ₹20,000"
- "I want minimalist furniture in neutral colors"

---

#### Panel 2: Product Discovery & Selection (Center Panel)

**Purpose**: Display search results, recommendations, and enable product selection for visualization.

**Functional Requirements:**
- Display product search results from chat interactions
- Show filtering and sorting options
- Enable single product selection per product type
- Allow adding selected products to canvas
- Support multiple search results simultaneously
- Clear visual indication of selected products

**UI Components:**

**Product List Section:**
- **Search Results Header**:
  - Result count
  - Active filters display
  - Sort dropdown (Price: Low to High, High to Low, Relevance, Rating)

- **Filter Panel** (Collapsible sidebar or top bar):
  - Price range slider
  - Category checkboxes
  - Material options
  - Color options
  - Style tags
  - Brand filters
  - Clear all filters button

- **Product Card** (for each product):
  - **Thumbnail Image**: High-quality product image (min 200x200px)
  - **Product Name**: Clear, readable title
  - **Price**: Prominently displayed with currency symbol
  - **Website Link**: "View on [Website]" button or link icon
  - **Product Type Badge**: e.g., "Sofa", "Coffee Table", "Lamp"
  - **Selection Checkbox/Radio**:
    - Radio button behavior (only one per type can be selected)
    - Visual indication when selected (highlight, border, checkmark)
  - **Add to Canvas Button**:
    - Enabled only when product is selected
    - Changes to "Remove from Canvas" if already added
    - Disabled if another product of same type already in canvas (with tooltip)

**Product Selection Rules:**
- Users can select **one product per product type** at a time
- Example: One sofa, one coffee table, one lamp, etc.
- Users can add multiple different product types to canvas
- No limit on total number of products (different types)
- Clear error messaging if user tries to add duplicate type

**Visual States:**
- Default: Normal card appearance
- Selected: Highlighted border, checkmark visible
- Added to Canvas: Badge showing "In Canvas"
- Cannot Add: Disabled with tooltip explaining why

---

#### Panel 3: Canvas & Visualization (Right Panel)

**Purpose**: Manage selected products and trigger room visualization.

**Functional Requirements:**
- Display thumbnails of all products added to canvas
- Show total count of products in canvas
- Display room image (uploaded or prompt upload)
- Provide visualization trigger
- Enable product removal from canvas
- Allow product management (view list, remove individual items)
- Support click-to-select, click-to-move furniture positioning after visualization

**UI Components:**

**Canvas Header:**
- **Title**: "Your Canvas"
- **Product Count Badge**: "X items added"
- **Clear Canvas Button**: Remove all products (with confirmation)

**Room Image Section:**
- **If Image Uploaded on Landing**:
  - Display thumbnail of room image
  - "Change Image" button (optional)

- **If No Image Uploaded**:
  - Placeholder with upload icon
  - "Upload Room Image" button (prominent, required before visualization)
  - Help text: "Upload a room image to visualize furniture placement"

**Products in Canvas Section:**
- **Grid/List View Toggle**: Switch between thumbnail grid and detailed list
- **Thumbnail Grid View**:
  - Small product thumbnails (100x100px)
  - Product type badge overlay
  - Remove icon (X button) on hover
  - Drag handle for reordering (future enhancement)

- **List View**:
  - Product name
  - Product type
  - Price
  - Small thumbnail
  - Remove button
  - Expand for details (optional)

**Visualization Controls:**
- **"Visualize" Button** (Primary CTA):
  - Large, prominent button
  - Enabled only when:
    - Room image is uploaded
    - At least one product is in canvas
  - Disabled state with tooltip explaining requirements
  - Loading state during API call

- **Visualization Status Indicator**:
  - Processing message during API call
  - Success/error feedback
  - Progress indicator (optional)

**Post-Visualization Features:**
- **Product Placement Control (Click-to-Move)**:
  - Display visualization result as main image
  - Overlay clickable product markers/bounding boxes on furniture
  - Click-to-select furniture (highlights selected item)
  - Click destination location to move selected furniture
  - Visual feedback showing selected state
  - Update position coordinates in real-time
  - Option to re-visualize with new positions or move marker only

- **Product Management**:
  - List of placed products with current coordinates
  - Remove individual products and re-visualize
  - Toggle product visibility
  - Reset to original positions
  - Undo/redo position changes

---

### 3. Responsive Layout

**Desktop (1280px+):**
```
┌─────────────────────────────────────────────────────┐
│  Header (App Logo, User Menu)                       │
├──────────┬──────────────────────┬───────────────────┤
│          │                      │                   │
│  Chat    │  Product Discovery   │   Canvas          │
│  Panel   │  & Selection         │   & Visualize     │
│  (25%)   │  (50%)               │   (25%)           │
│          │                      │                   │
│          │                      │                   │
└──────────┴──────────────────────┴───────────────────┘
```

**Tablet (768px - 1279px):**
- Collapsible chat panel (hamburger menu)
- Product panel takes center stage (60%)
- Canvas panel pinned to right (40%)

**Mobile (< 768px):**
- Tab-based navigation: Chat | Products | Canvas
- Full-width panels, swipe to switch
- Sticky visualization button at bottom

---

### 4. User Workflows

#### Workflow 1: New User with Room Image
```
1. Land on app → See intro
2. Upload room image → Click "Upload & Continue"
3. Chat: "I need a modern sofa"
4. View products in Panel 2
5. Select a sofa → Click "Add to Canvas"
6. Chat: "Show me coffee tables"
7. Select a coffee table → Click "Add to Canvas"
8. Go to Panel 3 → Click "Visualize"
9. View visualization result
10. Click furniture to select, then click new location to move
11. Remove/add more products as needed
```

#### Workflow 2: New User without Room Image
```
1. Land on app → Click "Upload Later"
2. Chat: "Show me minimalist furniture"
3. Browse and select products
4. Add products to canvas
5. Panel 3 shows "Upload Room Image" button
6. Upload image when ready
7. Click "Visualize"
8. View and adjust visualization
```

#### Workflow 3: Iterative Refinement
```
1. User has visualized room with products
2. Chat: "Show me larger sofas"
3. Remove current sofa from canvas
4. Select new sofa → Add to canvas
5. Click "Visualize" again
6. Compare new visualization
7. Adjust product positions
```

---

## Phase 2: Advanced Features

### 1. Product Swap Functionality

**Purpose**: Enable users to easily swap products of the same type without removing and re-adding.

**Functional Requirements:**
- Quick swap interface for products in canvas
- Maintain product position when swapping
- Preview swap before confirming
- Undo swap action

**UI Components:**
- **Swap Mode Toggle**: Activate swap mode for a product type
- **Swap Panel**:
  - Show alternative products of same type
  - Side-by-side comparison
  - Quick filter (price range, style)
- **Swap Button**: One-click swap with preview
- **Comparison View**: Before/after visualization (optional)

**User Flow:**
```
Canvas → Select Product → "Swap" button → View alternatives →
Select new product → Preview → Confirm swap → Auto-re-visualize
```

---

### 2. Additional Phase 2 Features (To Be Detailed)

- **Save & Share**: Save design projects, share with friends
- **History**: View past visualizations and conversations
- **Favorites**: Save favorite products for later
- **Room Templates**: Pre-designed room layouts
- **Multi-room Projects**: Manage multiple rooms in one project
- **Collaboration**: Share canvas with family/friends for input
- **AR Preview**: View products in room using AR (mobile)
- **Budget Tracker**: Track total cost of selected products
- **Style Quiz**: Automated style preference detection

---

## Detailed Implementation Plan

### Phase 1: Core Three-Panel Layout (2-3 weeks)

#### Step 1: Update Landing Page (2 days)
**File**: `frontend/src/app/page.tsx`
- Add hero section with app benefits
- Implement room image upload component
  - Drag-and-drop using react-dropzone
  - Image preview
  - File validation (JPG, PNG, WEBP, max 10MB)
- Add "Upload & Continue" and "Upload Later" buttons
- Store uploaded image in React Query state
- Implement navigation to `/design` route

**Deliverables**:
- Enhanced landing page with upload
- Image state management
- Route navigation

#### Step 2: Create Three-Panel Layout (3 days)
**New File**: `frontend/src/app/design/page.tsx`
- Create new `/design` route
- Implement responsive grid layout:
  - Desktop: 25% | 50% | 25% columns
  - Tablet: Collapsible left (hamburger), 60% center, 40% right
  - Mobile: Tab navigation between panels
- Add panel containers with proper styling
- Implement responsive behavior with Tailwind breakpoints

**Deliverables**:
- New `/design` route
- Responsive three-panel layout
- Mobile tab navigation

#### Step 3: Refactor Chat Interface for Panel 1 (2 days)
**New File**: `frontend/src/components/panels/ChatPanel.tsx`
- Extract chat logic from existing `ChatInterface.tsx`
- Remove product selection UI (move to Panel 2)
- Focus on conversational interface only
- Maintain message history and typing indicators
- Emit product recommendation events to parent

**Deliverables**:
- Standalone chat panel component
- Event emitters for product recommendations
- Clean separation of concerns

#### Step 4: Create Product Discovery Panel (4 days)
**New File**: `frontend/src/components/panels/ProductDiscoveryPanel.tsx`

**Sub-components**:
- `EnhancedProductCard.tsx`:
  - Radio button for selection (one per type)
  - "Add to Canvas" button
  - Product type badge
  - Website link
  - Price, image, details

- `ProductTypeManager.tsx`:
  - Track selected products by type
  - Enforce one-per-type rule
  - Validation and error messaging

**Features**:
- Receive product recommendations from Panel 1
- Display products in responsive grid
- Implement filtering (reuse/enhance existing FilterSidebar)
- Add sorting dropdown
- Show active filters and result count
- Handle product selection with type constraints
- Emit "add to canvas" events

**Deliverables**:
- Complete product discovery panel
- Enhanced product cards
- Type-based selection logic
- Integration with Panel 1 and Panel 3

#### Step 5: Create Canvas Panel (4 days)
**New File**: `frontend/src/components/panels/CanvasPanel.tsx`

**Sub-components**:
- `RoomImageUploader.tsx`:
  - Display uploaded image or upload button
  - Change image functionality

- `ProductCanvas.tsx`:
  - Grid/List view toggle
  - Product thumbnails with remove buttons
  - Total count and price

- `VisualizationTrigger.tsx`:
  - "Visualize" button with validation
  - Loading states
  - Error handling

**Features**:
- Display room image (from landing or upload here)
- Show products added from Panel 2
- Grid/List view for products
- Remove individual products
- Clear all functionality
- Enable "Visualize" only when valid (image + products)
- Trigger visualization API call

**Deliverables**:
- Complete canvas panel
- Room image management
- Product list management
- Visualization trigger

#### Step 6: Implement Click-to-Move Functionality (5 days)
**New File**: `frontend/src/components/visualization/VisualizationCanvas.tsx`

**Technology Stack**:
- React-Konva for canvas layer
- Furniture bounding boxes from ChatGPT Vision API

**Features**:
- Display visualization result image as background
- Overlay clickable furniture markers (from bounding boxes)
- Click handler for furniture selection
  - Highlight selected furniture
  - Show visual feedback (border, glow)
- Click handler for destination
  - Calculate new position coordinates
  - Update state with new position
  - Move marker OR re-visualize
- Undo/redo stack for position changes
- Re-visualize button

**API Integration**:
- Call `detect_furniture_with_bounding_boxes()` after initial visualization
- Get normalized coordinates for all furniture
- Create interactive markers at those positions

**Deliverables**:
- Interactive visualization canvas
- Click-to-select, click-to-move functionality
- Position tracking and undo/redo
- Re-visualization integration

#### Step 7: State Management & Cross-Panel Communication (3 days)
**New Files**:
- `frontend/src/hooks/useCanvasProducts.ts`
- `frontend/src/hooks/useRoomImage.ts`
- `frontend/src/hooks/useVisualization.ts`
- `frontend/src/hooks/useFurniturePositions.ts`

**React Query Hooks**:
- `useCanvasProducts()`:
  - Add/remove products
  - Track products by type
  - Validate type constraints

- `useRoomImage()`:
  - Upload and store room image
  - Update/replace image

- `useVisualization()`:
  - Trigger visualization API
  - Store visualization results
  - Handle loading/error states

- `useFurniturePositions()`:
  - Track furniture positions
  - Update positions on move
  - Undo/redo functionality

**Event Bus**:
- Panel 1 → Panel 2: Product recommendations
- Panel 2 → Panel 3: Add to canvas
- Panel 3 → API: Visualize with products

**Deliverables**:
- Complete state management layer
- React Query hooks
- Cross-panel event handling
- Data synchronization

#### Step 8: API Integration & Backend Updates (3 days)
**File**: `frontend/src/utils/api.ts`

**New API Functions**:
```typescript
// Canvas management
addProductToCanvas(product: Product): Promise<void>
removeProductFromCanvas(productId: string): Promise<void>
getCanvasProducts(): Promise<Product[]>

// Room image
uploadRoomImage(imageFile: File): Promise<string>
getRoomImage(): Promise<string>

// Visualization
generateVisualization(params: VisualizationParams): Promise<VisualizationResult>
updateFurniturePosition(productId: string, position: Position): Promise<void>

// Furniture detection
detectFurniture(imageData: string): Promise<FurnitureDetection[]>
```

**Backend Endpoints** (FastAPI):
- `POST /api/canvas/products` - Add product to canvas
- `DELETE /api/canvas/products/{id}` - Remove product
- `GET /api/canvas/products` - Get all canvas products
- `POST /api/visualization/generate` - Generate visualization
- `POST /api/visualization/furniture-positions` - Update positions

**Deliverables**:
- Complete API integration layer
- New backend endpoints (if needed)
- Error handling and retry logic
- Loading states

#### Step 9: Responsive Design & Mobile Optimization (2 days)
**Files**: All panel components

**Tasks**:
- Test three-panel layout on all breakpoints
- Implement mobile tab navigation
  - Tab bar with Chat | Products | Canvas
  - Swipe gestures (optional)
  - Active tab highlighting
- Optimize touch interactions
  - Larger tap targets
  - Smooth scrolling
- Add loading skeletons
- Implement empty states
- Add error boundaries

**Deliverables**:
- Fully responsive UI
- Mobile-optimized interactions
- Loading and empty states
- Error boundaries

#### Step 10: Testing, Polish & Documentation (3 days)

**Testing**:
- Unit tests for components
- Integration tests for workflows
- E2E tests with Playwright/Cypress
- Cross-browser testing
- Accessibility audit (keyboard nav, screen readers)

**Polish**:
- Animations and transitions
- Micro-interactions
- Tooltips and help text
- Keyboard shortcuts
- Performance optimization

**Documentation**:
- Component documentation
- API documentation
- User guide
- Developer setup guide

**Deliverables**:
- Complete test suite
- Polished UI with animations
- Comprehensive documentation

---

### Phase 2: Product Swap & Advanced Features (1 week)

#### Step 11: Implement Product Swap Modal (3 days)
**New File**: `frontend/src/components/swap/SwapProductModal.tsx`

**Features**:
- Modal dialog for product swapping
- Show alternative products of same type
- Side-by-side comparison view
- Price and feature comparison
- Maintain position when swapping
- Preview swap before confirming

**API Integration**:
- Get similar products by type
- Swap product while keeping position

**Deliverables**:
- Swap modal component
- Comparison view
- API integration

#### Step 12: Additional Features (4 days)

**Save & Share** (2 days):
- Save design projects to database
- Share via unique URL
- Social media integration

**History** (1 day):
- View past visualizations
- Restore previous states
- Comparison view

**Budget Tracker** (1 day):
- Track total cost
- Budget vs. actual
- Price alerts

**Deliverables**:
- Save/share functionality
- History viewer
- Budget tracker

---

### Implementation Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Week 1** | 5 days | Steps 1-3: Landing page, Layout, Chat panel |
| **Week 2** | 5 days | Steps 4-5: Product panel, Canvas panel |
| **Week 3** | 5 days | Steps 6-7: Click-to-move, State management |
| **Week 4** | 3 days | Steps 8-9: API integration, Responsive design |
| **Week 4-5** | 3 days | Step 10: Testing & polish |
| **Week 6** | 5 days | Steps 11-12: Swap & advanced features |

**Total Duration**: ~5-6 weeks for complete Phase 1 & 2 implementation

---

### Component File Structure

```
frontend/src/
├── app/
│   ├── design/
│   │   └── page.tsx                    # Main three-panel layout
│   └── page.tsx                        # Enhanced landing page
│
├── components/
│   ├── panels/
│   │   ├── ChatPanel.tsx              # Panel 1: Chat interface
│   │   ├── ProductDiscoveryPanel.tsx  # Panel 2: Products
│   │   └── CanvasPanel.tsx            # Panel 3: Canvas
│   │
│   ├── products/
│   │   ├── EnhancedProductCard.tsx    # Product card with selection
│   │   ├── ProductTypeManager.tsx     # Type-based selection logic
│   │   └── ProductComparison.tsx      # Comparison view
│   │
│   ├── canvas/
│   │   ├── RoomImageUploader.tsx      # Room image management
│   │   ├── ProductCanvas.tsx          # Product list/grid
│   │   └── VisualizationTrigger.tsx   # Visualize button
│   │
│   ├── visualization/
│   │   ├── VisualizationCanvas.tsx    # Interactive canvas
│   │   ├── FurnitureMarker.tsx        # Clickable markers
│   │   └── PositionControls.tsx       # Undo/redo/re-viz
│   │
│   ├── swap/
│   │   └── SwapProductModal.tsx       # Product swap modal
│   │
│   └── layout/
│       ├── ThreePanelLayout.tsx       # Responsive layout
│       └── MobileTabNavigation.tsx    # Mobile tabs
│
├── hooks/
│   ├── useCanvasProducts.ts           # Canvas state
│   ├── useRoomImage.ts                # Room image state
│   ├── useVisualization.ts            # Visualization state
│   └── useFurniturePositions.ts       # Position tracking
│
└── utils/
    ├── api.ts                          # API client (enhanced)
    └── canvas.ts                       # Canvas utilities
```

---

## Technical Implementation Notes

### State Management
- Chat history and context
- Selected products (Panel 2)
- Canvas products (Panel 3)
- Room image data
- Visualization results
- User preferences

### API Endpoints Required
- `POST /api/chat/message` - Send chat message, get response
- `GET /api/products/search` - Search products based on criteria
- `POST /api/visualization/generate` - Generate visualization
- `POST /api/upload/room-image` - Upload room image
- `GET /api/products/{id}` - Get product details
- `POST /api/canvas/add` - Add product to canvas
- `DELETE /api/canvas/remove/{id}` - Remove product from canvas

### Performance Considerations
- Lazy load product images
- Paginate search results (infinite scroll or pagination)
- Debounce chat input
- Optimize visualization API calls
- Cache product data
- Compress room images before upload

### Accessibility Requirements
- Keyboard navigation support
- Screen reader compatibility
- High contrast mode
- Focus indicators
- Alt text for all images
- ARIA labels for interactive elements

---

## Design System Requirements

### Color Palette
- Primary: Action buttons, selected states
- Secondary: Links, secondary actions
- Neutral: Backgrounds, text, borders
- Success: Successful operations
- Error: Validation errors, failures
- Warning: Important notices

### Typography
- Headings: Clear hierarchy (H1-H6)
- Body: Readable font size (16px minimum)
- Labels: Distinct from body text
- Links: Underlined or clearly styled

### Spacing
- Consistent padding/margin scale (4px, 8px, 16px, 24px, 32px, 48px)
- Card spacing
- Panel gutters
- Element spacing

### Components
- Buttons (Primary, Secondary, Tertiary, Icon)
- Cards (Product, Image, Info)
- Input fields (Text, File upload)
- Modals/Dialogs
- Tooltips
- Loading states
- Empty states
- Error states

---

## Success Metrics

### User Engagement
- Time spent on platform
- Number of visualizations per session
- Products added to canvas per session
- Chat interactions per session

### Conversion
- Click-through rate to product websites
- Products explored after visualization
- Return user rate

### User Satisfaction
- Visualization quality ratings
- Feature usage analytics
- User feedback and NPS score

---

## Next Steps

1. **Design Phase**:
   - Create wireframes for all screens
   - Design high-fidelity mockups
   - Create interactive prototype
   - Conduct user testing

2. **Development Phase**:
   - Set up frontend framework (React/Next.js)
   - Implement three-panel layout
   - Build chat interface
   - Develop product selection UI
   - Create canvas management system
   - Integrate visualization API
   - Implement click-to-move furniture positioning

3. **Testing Phase**:
   - Unit tests for components
   - Integration tests for workflows
   - End-to-end testing
   - Performance testing
   - Accessibility audit
   - Cross-browser testing

4. **Launch Phase**:
   - Beta testing with select users
   - Gather feedback and iterate
   - Soft launch
   - Full production launch
   - Monitor analytics and user feedback

---

## Appendix

### Technology Stack Recommendations
- **Frontend**: React/Next.js, TypeScript
- **State Management**: TanStack React Query (already implemented)
- **UI Components**: Custom components with Headless UI (already implemented)
- **Styling**: Tailwind CSS (already implemented)
- **Chat**: REST API with React Query
- **Image Handling**: Sharp, Next.js Image optimization
- **Canvas Manipulation**: Fabric.js, Konva.js (already installed)
- **File Upload**: react-dropzone or native HTML5
- **API Client**: Axios (already implemented)

### Reference Resources
- Similar apps: Havenly, Modsy, Houzz
- Design inspiration: Dribbble, Behance
- UX patterns: Nielsen Norman Group, Material Design

---

## Canvas Panel V2 - Enhancement Issues & Solutions

### Date Implemented: 2025-11-04

This section documents enhancements made to Panel 3 (Canvas & Visualization) to improve user experience and state management.

---

### Issue #1: Room Image Section Not Collapsible

**Problem**: Room image section always visible, taking up valuable space even when users don't need to see it constantly.

**User Impact**:
- Reduced space for product list and visualization result
- Unnecessary scrolling required
- UI feels cluttered

**Solution Implemented**:
- Made room image section collapsible with expand/collapse toggle
- Defaults to **expanded** on page load
- Smooth animations on collapse/expand
- Chevron icon indicates current state (rotates on toggle)
- Preserves user's choice during session (component state)

**Technical Implementation** (`CanvasPanel.tsx` lines 228-306):
```typescript
const [isRoomImageCollapsed, setIsRoomImageCollapsed] = useState(false);

<button onClick={() => setIsRoomImageCollapsed(!isRoomImageCollapsed)}>
  <h3>Room Image</h3>
  <svg className={isRoomImageCollapsed ? '' : 'rotate-180'}>
    {/* Chevron icon */}
  </svg>
</button>

{!isRoomImageCollapsed && (
  <div className="p-4 pt-0">
    {/* Room image content */}
  </div>
)}
```

**Benefits**:
- More space for product canvas
- Better visualization result visibility
- User control over panel layout
- Cleaner interface

---

### Issue #2: No Canvas Change Tracking

**Problem**: System didn't track when canvas products differed from last visualization, leading to confusion about whether current visualization was up-to-date.

**User Impact**:
- No indication when products were added/removed after visualization
- Users couldn't tell if visualization was stale
- Unnecessary re-visualizations when nothing changed
- No feedback about canvas state vs visualization state

**Solution Implemented**:
- Added `lastVisualizedProducts` state to snapshot products used in visualization
- Added `needsRevisualization` boolean flag
- Automatic comparison on any canvas change (add/remove product)
- Visual indicators when re-visualization needed

**Technical Implementation** (`CanvasPanel.tsx` lines 46-69):
```typescript
// State tracking
const [lastVisualizedProducts, setLastVisualizedProducts] = useState<Product[]>([]);
const [needsRevisualization, setNeedsRevisualization] = useState(false);

// Automatic change detection
useEffect(() => {
  if (lastVisualizedProducts.length === 0 && !visualizationResult) {
    return; // Never visualized
  }

  // Compare current vs last visualized
  const productsChanged =
    products.length !== lastVisualizedProducts.length ||
    products.some(p => !lastVisualizedProducts.find(lp => lp.id === p.id));

  if (productsChanged) {
    setNeedsRevisualization(true);
  }
}, [products, lastVisualizedProducts, visualizationResult]);

// On successful visualization
setLastVisualizedProducts([...products]); // Snapshot
setNeedsRevisualization(false); // Reset
```

**Change Triggers**:
- Adding product to canvas → `needsRevisualization = true`
- Removing product from canvas → `needsRevisualization = true`
- Successful visualization → `needsRevisualization = false`
- Changing room image → Reset all state

**Benefits**:
- Always know if visualization is current
- Prevents unnecessary API calls
- Better user awareness of canvas state
- Foundation for future undo/redo features

---

### Issue #3: Visualize Button Lacks State Feedback

**Problem**: Visualize button only had two states (enabled/disabled), no indication when visualization was already up-to-date.

**User Impact**:
- Users would click "Visualize" even when nothing changed
- Wasted API calls and processing time
- No positive feedback when visualization matched canvas
- Confusion about button purpose

**Solution Implemented**:
- Three distinct button states with visual differentiation
- Smart state detection based on room image, products, and change tracking
- Clear visual feedback for each state

**Button States** (`CanvasPanel.tsx` lines 191-601):

**State 1: Ready to Visualize** (Primary action)
- **When**: Room image + products + (never visualized OR canvas changed)
- **Appearance**: Gradient primary/secondary colors (blue/purple)
- **Button Text**: "Visualize Room"
- **Enabled**: Yes
- **Purpose**: Ready to generate new visualization

**State 2: Up to Date** (Success state)
- **When**: Room image + products + visualization exists + no changes
- **Appearance**: Green background
- **Button Text**: "✓ Up to date"
- **Enabled**: No (disabled)
- **Purpose**: Inform user everything is current
- **Helper Text**: "Visualization matches current canvas"

**State 3: Not Ready** (Disabled state)
- **When**: No room image OR no products in canvas
- **Appearance**: Gray/neutral
- **Button Text**: "Visualize Room"
- **Enabled**: No (disabled)
- **Helper Messages**:
  - "Upload a room image to visualize" (if no image)
  - "Add products to canvas to visualize" (if no products)

**Technical Implementation**:
```typescript
const canVisualize = roomImage !== null && products.length > 0;
const isUpToDate = canVisualize && !needsRevisualization && visualizationResult !== null;
const isReady = canVisualize && (needsRevisualization || visualizationResult === null);

{isUpToDate ? (
  <button disabled className="bg-green-500">
    <CheckIcon /> Up to date
  </button>
) : isReady ? (
  <button onClick={handleVisualize} className="bg-gradient...">
    <EyeIcon /> Visualize Room
  </button>
) : (
  <button disabled className="bg-neutral-300">
    <EyeIcon /> Visualize Room
  </button>
)}
```

**Benefits**:
- Clear communication of system state
- Prevents unnecessary visualizations
- Positive reinforcement when up-to-date
- Reduces API costs
- Better user experience

---

### Issue #4: No "Outdated" Warning on Old Visualizations

**Problem**: When canvas changed after visualization, old visualization remained visible without any warning that it was outdated.

**User Impact**:
- Users confused by visualization not matching current canvas
- Might share/use incorrect visualizations
- No visual cue to re-visualize
- Misleading product placement

**Solution Implemented**:
- Amber warning banner when visualization is outdated
- Amber ring around visualization image
- Keep visualization visible (don't hide it)
- Success message when up-to-date

**Visual Indicators** (`CanvasPanel.tsx` lines 494-527):

**When Outdated** (`needsRevisualization = true`):
```typescript
{needsRevisualization && (
  <div className="bg-amber-50 border-amber-200 rounded-lg">
    <WarningIcon className="text-amber-600" />
    <p className="text-amber-800">Canvas changed - Re-visualize to update</p>
  </div>
)}

<div className={needsRevisualization ? 'ring-2 ring-amber-400' : ''}>
  <img src={visualizationResult} />
</div>
```

**When Up-to-Date** (`needsRevisualization = false`):
```typescript
{!needsRevisualization && (
  <p className="text-green-600">✓ Visualization up to date</p>
)}
```

**Warning Design**:
- **Banner Color**: Amber/yellow (warning, not error)
- **Icon**: Warning triangle with exclamation
- **Message**: "Canvas changed - Re-visualize to update"
- **Ring**: 2px amber border around image
- **Placement**: Above visualization image

**Benefits**:
- Clear warning about outdated state
- User can still see old visualization for reference
- Strong visual cue to take action
- Prevents confusion and mistakes
- Aligns with button state feedback

---

### Implementation Summary

**Files Modified**:
1. `frontend/src/components/panels/CanvasPanel.tsx` - Complete rewrite with all features

**New State Variables**:
- `isRoomImageCollapsed: boolean` - Collapse state for room image section
- `lastVisualizedProducts: Product[]` - Snapshot of products from last visualization
- `needsRevisualization: boolean` - Flag indicating canvas changes require re-viz

**New Functions**:
- `useEffect` hook for automatic change detection
- Three-state button rendering logic
- Outdated warning conditional rendering

**Lines of Code**: 623 lines (previously 524 lines)

---

### User Workflows Enhanced

**Workflow 1: Initial Visualization**
```
1. User adds products to canvas
2. Button shows: "Visualize Room" (Ready state - gradient)
3. User clicks visualize
4. After success: "✓ Up to date" (Green state)
5. Message: "Visualization matches current canvas"
```

**Workflow 2: Canvas Changes After Visualization**
```
1. User has visualized room (button shows "Up to date")
2. User adds another product
3. Immediately: needsRevisualization = true
4. Warning appears: "Canvas changed - Re-visualize to update"
5. Old visualization gets amber ring
6. Button changes: "Visualize Room" (Ready state - gradient)
7. User clicks to update
8. Warning disappears, button returns to "Up to date"
```

**Workflow 3: Remove Product After Visualization**
```
1. User has visualized room with 3 products
2. User removes 1 product
3. Warning: "Canvas changed - Re-visualize to update"
4. Old viz still visible with amber ring
5. Button: "Visualize Room" (enabled)
6. User can re-visualize or continue editing
```

**Workflow 4: Collapse Room Image for More Space**
```
1. User clicks "Room Image" section header
2. Section collapses with smooth animation
3. More space for product list and visualization
4. Click again to expand
5. State persists during session
```

---

### Testing Checklist

- [x] Room image section expands/collapses smoothly
- [x] Chevron icon rotates correctly
- [x] Adding product triggers `needsRevisualization`
- [x] Removing product triggers `needsRevisualization`
- [x] Button shows "Up to date" after successful visualization
- [x] Button shows "Ready" when canvas changes
- [x] Outdated warning appears when canvas changes
- [x] Warning disappears after re-visualization
- [x] Amber ring appears/disappears correctly
- [x] Helper messages show for each button state
- [x] Success message shows when up-to-date
- [x] Room image change resets all state

---

### Future Enhancements

**Potential Improvements**:
1. **Persist collapse state**: Remember user's preference across sessions
2. **Smart room image default**: Collapse automatically after first visualization
3. **Change summary**: Show what products changed (added/removed)
4. **Visualization diff**: Side-by-side comparison of old vs new
5. **Undo/Redo**: Revert to previous canvas states
6. **Change history**: Timeline of all canvas modifications
7. **Auto-collapse on mobile**: Automatically collapse room image on small screens

---

### Design Decisions

**Why Default to Expanded?**
- First-time users need to see room image
- Provides context for what will be visualized
- Clear call-to-action for upload if missing
- Users can collapse once familiar with workflow

**Why Show Old Visualization with Warning?**
- Users may want to compare old vs new
- Prevents jarring "disappear" experience
- Provides context for what will change
- Gentle nudge vs forceful removal

**Why Three Button States?**
- "Ready" = Call to action (gradient to draw attention)
- "Up to date" = Positive reinforcement (green = success)
- "Not ready" = Disabled but informative (gray with helper text)
- Reduces unnecessary API calls
- Clear system feedback

**Why Amber (Not Red) for Warning?**
- Outdated visualization isn't an error
- Amber suggests "caution" not "failure"
- Matches UI warning patterns
- Less alarming than red

---

### Performance Impact

**State Management Overhead**: Minimal
- Single `useEffect` for change detection
- O(n) product comparison (negligible for <100 products)
- No additional API calls

**Memory Usage**: Negligible
- `lastVisualizedProducts` stores product snapshots
- Typical size: <10 KB for 20 products
- Cleared on room image change

**Rendering Performance**: Improved
- Collapsible room image reduces DOM when collapsed
- Conditional rendering based on state
- No impact on visualization API calls

**API Cost Savings**: Significant
- Prevents duplicate visualizations when canvas unchanged
- "Up to date" state blocks unnecessary clicks
- Estimated 20-30% reduction in API calls

---

### Accessibility Enhancements

**Keyboard Navigation**:
- Room image toggle focusable and keyboard-accessible
- Enter/Space to toggle collapse
- Button states clearly announced by screen readers

**Screen Reader Support**:
- Collapse button has `aria-expanded` attribute
- Button states have descriptive labels
- Warning banner has `role="alert"`
- Success messages announced

**Visual Indicators**:
- High contrast warning colors
- Clear icon usage (warning triangle, checkmark, eye)
- Text labels on all buttons (not icon-only)
- Proper color contrast ratios

**Focus Management**:
- Focus remains on toggle button after collapse/expand
- Visualize button focus state visible
- Keyboard trap avoided in collapsible sections

---

## Canvas Panel State Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     CANVAS PANEL STATES                      │
└─────────────────────────────────────────────────────────────┘

Initial State:
- No room image
- No products
- Button: "Not Ready" (gray, disabled)
- Message: "Upload a room image to visualize"

    │
    ▼ (upload room image)

Room Image Uploaded:
- Room image exists
- No products
- Button: "Not Ready" (gray, disabled)
- Message: "Add products to canvas to visualize"

    │
    ▼ (add products)

Ready to Visualize (First Time):
- Room image exists
- Products in canvas
- No visualization yet
- needsRevisualization: false (never visualized)
- Button: "Visualize Room" (gradient, enabled)

    │
    ▼ (click visualize)

Visualizing:
- Button: "Visualizing..." (gradient, disabled)
- Spinner animation
- API call in progress

    │
    ▼ (API success)

Up to Date:
- Visualization matches canvas
- needsRevisualization: false
- Button: "✓ Up to date" (green, disabled)
- Message: "Visualization matches current canvas"

    │
    ▼ (add/remove product)

Outdated Visualization:
- Canvas changed since last viz
- needsRevisualization: true
- Old visualization visible with:
  - Amber warning banner
  - Amber ring around image
  - Message: "Canvas changed - Re-visualize to update"
- Button: "Visualize Room" (gradient, enabled)

    │
    ▼ (click visualize)

Back to "Visualizing" state...
    │
    ▼ (API success)

Back to "Up to Date" state
```

---

### Related Documentation

- See `CANVAS_PANEL_V2_FIXES.md` for detailed technical implementation
- See `frontend/src/components/panels/CanvasPanel.tsx` for complete source code
- See git commit history for incremental changes

---
