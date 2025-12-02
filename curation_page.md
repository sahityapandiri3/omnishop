# Curated Styling Feature - Implementation Plan

## Overview

Add a "Curated Styling" page between store selection and the design studio. Users see 3 AI-generated complete room looks with distinct style themes, can browse products in each look, add to a real cart, and optionally proceed to manual styling.

## User Flow

```
Homepage (/) → Store Selection (/store-select) → Curated Styling (/curated) → [Optional] Design Studio (/design)
```

## Requirements Summary

- **3 curated looks** with distinct style themes (Modern, Traditional, Minimalist, etc.)
- **Room-type specific products**:
  - Living Room: Sofa, Center table, Carpet, Side table, Planters, Lounge chairs, Chandelier, Lighting
  - Bedroom: Bed, Side tables, Table lamp/Standing lamp, Optional carpet
- **Look detail view**: Click look → See products, prices, add to cart, product links
- **Real cart**: Basic cart page (no checkout), persists in session
- **"Style by yourself"** button → Navigate to existing 3-panel design studio

---

## Architecture

### New Files to Create

| Layer | File | Purpose |
|-------|------|---------|
| Backend Service | `/api/services/curated_styling_service.py` | Orchestrates room analysis, style theme generation, product selection, visualization |
| Backend Router | `/api/routers/curated.py` | API endpoint for generating curated looks |
| Frontend Page | `/frontend/src/app/curated/page.tsx` | Curated styling page with 3 look cards |
| Frontend Component | `/frontend/src/components/curated/CuratedLookCard.tsx` | Individual look preview card |
| Frontend Component | `/frontend/src/components/curated/LookDetailModal.tsx` | Expanded look with products |
| Frontend Context | `/frontend/src/context/CartContext.tsx` | Cart state management |
| Frontend Component | `/frontend/src/components/cart/CartIcon.tsx` | Header cart icon with badge |
| Frontend Component | `/frontend/src/components/cart/CartPanel.tsx` | Slide-out cart panel |

### Files to Modify

| File | Change |
|------|--------|
| `/api/main.py` | Register curated router |
| `/frontend/src/app/store-select/page.tsx` | Change navigation from `/design` to `/curated` |
| `/frontend/src/app/layout.tsx` | Wrap with `CartProvider` |
| `/frontend/src/utils/api.ts` | Add `generateCuratedLooks()` API function |

---

## Backend Implementation

### 1. API Endpoint: `POST /api/curated/generate`

**Request:**
```json
{
  "room_image": "base64...",
  "selected_stores": ["phantomhands", "westelm"]
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "room_type": "living_room",
  "looks": [
    {
      "look_id": "uuid",
      "style_theme": "Modern Elegance",
      "style_description": "Clean lines with warm accents",
      "visualization_image": "base64...",
      "products": [
        {
          "id": 123,
          "name": "Aria 3-Seater Sofa",
          "price": 45000,
          "image_url": "https://...",
          "source_website": "phantomhands",
          "source_url": "https://...",
          "product_type": "sofa"
        }
      ],
      "total_price": 125000,
      "generation_status": "completed"
    }
  ],
  "generation_complete": true
}
```

### 2. Curated Styling Service Logic

```python
class CuratedStylingService:
    ROOM_PRODUCTS = {
        "living_room": {
            "primary": ["sofa"],
            "secondary": ["coffee table", "center table", "floor rug"],
            "accent": ["side table", "planter", "floor lamp", "lounge chair"],
            "optional": ["chandelier", "ceiling lamp"]
        },
        "bedroom": {
            "primary": ["bed"],
            "secondary": ["nightstand", "side table"],
            "accent": ["table lamp", "floor lamp", "floor rug"],
            "optional": ["dresser"]
        }
    }

    async def generate_curated_looks(self, room_image, selected_stores, db):
        # 1. Detect room type using google_ai_service.analyze_room_image()
        # 2. Generate 3 style themes using ChatGPT
        # 3. For each theme: AI-driven product selection + visualization
        # 4. Return all 3 looks
```

### 3. AI-Driven Product Selection Algorithm (Optimized for Speed)

**Goal**: Fast generation of curated looks with products that complement each other.

**Key Insight**: Single upfront AI call defines ALL requirements, then fast DB queries filter products.

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Room Analysis + Style Definition (Single AI Call)       │
│ ─────────────────────────────────────────────────────────────── │
│ Input: Room image                                               │
│ Output for EACH of 3 looks:                                     │
│   - Style theme name ("Modern Warmth")                          │
│   - Color palette (beige, warm gray, brass accents)             │
│   - Material preferences (light wood, velvet, marble)           │
│   - Texture preferences (soft, matte, natural)                  │
│   - Product requirements per category:                          │
│     • Sofa: neutral tone, modern silhouette, fabric             │
│     • Coffee table: light wood or marble, clean lines           │
│     • Rug: warm tones, textured weave                           │
│     • Lamp: brass/gold finish, sculptural                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Fast DB Queries (Parallel, using ProductAttributes)     │
│ ─────────────────────────────────────────────────────────────── │
│ For each look, query products matching AI-defined attributes:   │
│                                                                 │
│ SELECT * FROM products p                                        │
│ JOIN product_attributes pa ON p.id = pa.product_id              │
│ WHERE p.category IN ('sofa', 'three seater sofa', ...)          │
│   AND pa.color_primary IN ('beige', 'cream', 'gray')            │
│   AND pa.material_primary IN ('fabric', 'velvet', 'linen')      │
│   AND p.source_website IN (selected_stores)                     │
│ ORDER BY relevance_score DESC                                   │
│ LIMIT 1                                                         │
│                                                                 │
│ Run queries for all categories in PARALLEL                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Generate Visualizations (Parallel for 3 looks)          │
│ ─────────────────────────────────────────────────────────────── │
│ With products selected, generate room visualizations            │
│ Use existing incremental visualization for 5+ products          │
└─────────────────────────────────────────────────────────────────┘
```

**AI Prompt for Room Analysis + Style Definition:**
```
Analyze this room image and create 3 distinct interior design style themes.

For EACH theme, provide specific product requirements that will create a
cohesive, complementary look (products should work together aesthetically).

Room Type: {detected_room_type}

Return JSON:
{
  "room_type": "living_room",
  "room_analysis": {
    "current_colors": ["white walls", "wood flooring"],
    "architectural_style": "modern apartment",
    "natural_light": "good",
    "room_size": "medium"
  },
  "looks": [
    {
      "theme_name": "Modern Warmth",
      "theme_description": "Clean contemporary lines with warm, inviting tones",
      "color_palette": ["warm beige", "soft gray", "brass accents", "cream"],
      "material_palette": ["velvet", "light oak wood", "marble", "brass"],
      "texture_palette": ["soft", "smooth", "natural grain"],
      "products": {
        "sofa": {
          "colors": ["beige", "cream", "light gray"],
          "materials": ["velvet", "linen", "fabric"],
          "style": ["modern", "contemporary", "minimalist"]
        },
        "coffee_table": {
          "colors": ["white", "light wood", "marble"],
          "materials": ["marble", "oak", "wood"],
          "style": ["modern", "scandinavian"]
        },
        "rug": {
          "colors": ["beige", "cream", "warm gray"],
          "materials": ["wool", "jute", "cotton"],
          "style": ["textured", "natural"]
        },
        "floor_lamp": {
          "colors": ["brass", "gold", "black"],
          "materials": ["metal", "brass"],
          "style": ["modern", "sculptural"]
        },
        "side_table": {
          "colors": ["light wood", "white", "brass"],
          "materials": ["wood", "marble", "metal"],
          "style": ["modern", "minimalist"]
        },
        "planter": {
          "colors": ["white", "terracotta", "natural"],
          "materials": ["ceramic", "terracotta", "concrete"],
          "style": ["modern", "organic"]
        }
      }
    },
    // ... 2 more looks with different themes
  ]
}
```

**Why This is Faster:**
1. **Single AI call** defines all 3 looks with specific attributes
2. **Parallel DB queries** - filter products by attributes (no AI needed)
3. **Parallel visualization** - generate all 3 looks simultaneously
4. **Uses existing ProductAttributes** - color_primary, material_primary, style already extracted

**Estimated Time (Primary Path):**
- Step 1 (AI analysis): ~5-8 seconds
- Step 2 (DB queries): ~1-2 seconds (parallel)
- Step 3 (Visualization): ~10-15 seconds per look (parallel = ~15s total)
- **Total: ~20-25 seconds for all 3 looks**

---

### 4. Fallback: AI Selection from Shortlist

**When to trigger**: If attribute-based DB query returns 0 products for a category.

**Why this happens:**
- Not all products have complete attributes (color_primary may be NULL)
- AI-suggested attributes may be too specific (e.g., "terracotta ceramic planter")
- Limited inventory in selected stores

**Fallback Process:**
```
┌─────────────────────────────────────────────────────────────────┐
│ FALLBACK: When attribute query returns 0 results                │
│ ─────────────────────────────────────────────────────────────── │
│                                                                 │
│ Step 2b: Get Shortlist (10 products per category)               │
│ ├── Query: SELECT * FROM products                               │
│ │          WHERE category IN ('sofa', 'three seater sofa', ...) │
│ │          AND source_website IN (selected_stores)              │
│ │          AND is_available = true                              │
│ │          ORDER BY RANDOM()                                    │
│ │          LIMIT 10                                             │
│ └── Returns: 10 products with images, names, prices             │
│                                                                 │
│ Step 2c: AI Picks Best Match                                    │
│ ├── Input: 10 products + style theme requirements               │
│ ├── Prompt: "Pick the product that best matches this theme:     │
│ │            Colors: beige, cream. Materials: velvet, fabric.   │
│ │            Style: modern, contemporary"                       │
│ └── Output: Selected product ID                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Fallback AI Prompt:**
```
You are an interior stylist. From these 10 products, select the ONE
that best matches this style theme:

Theme: {theme_name}
Required colors: {colors}
Required materials: {materials}
Required style: {style_keywords}

Products:
1. [ID: 123] "Aria Sofa" - Gray fabric, modern lines - $45,000
2. [ID: 456] "Chester Sofa" - Brown leather, traditional - $65,000
... (10 products)

Return the product ID that best fits. If none fit well, pick the
most versatile/neutral option.

Response: {"selected_id": 123, "reason": "Gray fabric matches the neutral palette"}
```

**Fallback Timing:**
- Adds ~3-5 seconds per category that needs fallback
- Typically only 1-2 categories need fallback, so +5-10 seconds total
- **Worst case: ~35 seconds** (if all categories need fallback)

**Implementation Logic:**
```python
async def get_product_for_category(category, requirements, selected_stores, db):
    # Try primary: attribute-based query
    product = await query_by_attributes(category, requirements, selected_stores, db)

    if product:
        return product

    # Fallback: get shortlist and let AI pick
    shortlist = await get_shortlist(category, selected_stores, db, limit=10)

    if not shortlist:
        return None  # No products in this category at all

    selected_id = await ai_pick_best_match(shortlist, requirements)
    return next((p for p in shortlist if p.id == selected_id), shortlist[0])
```

**Key Integration Points:**
- Reuse `google_ai_service.analyze_room_image()` for room type detection
- Reuse `recommendation_engine.get_recommendations()` for product selection
- Reuse visualization methods for generating room images
- Use `asyncio.gather()` to generate 3 looks in parallel

---

## Frontend Implementation

### 1. Curated Page (`/curated`)

**States:**
- Loading: Show skeleton cards + "Creating your curated looks..." message
- Success: Display 3 look cards in grid
- Error: Show error message with "Go Back" button

**Layout:**
```
┌─────────────────────────────────────────┐
│ Header                        [Cart 🛒] │
├─────────────────────────────────────────┤
│         Your Curated Looks              │
│   Room Type: Living Room                │
│                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  │   Modern    │ │    Cozy     │ │  Minimalist │
│  │  Elegance   │ │ Traditional │ │     Zen     │
│  │   $125K     │ │    $98K     │ │    $87K     │
│  │             │ │             │ │             │
│  │ [View] [✎]  │ │ [View] [✎]  │ │ [View] [✎]  │
│  └─────────────┘ └─────────────┘ └─────────────┘
│                                         │
│  ✎ = "Style this Look" (pre-populates)  │
│                                         │
│      [ Style by Yourself ]              │
│   (starts with empty canvas)            │
└─────────────────────────────────────────┘
```

### 2. Look Detail Modal

When user clicks a look card:
```
┌─────────────────────────────────────────┐
│                                    [X]  │
│  ┌─────────────────────────────────┐   │
│  │   Visualization Image           │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Modern Elegance                        │
│  Clean lines with warm accents          │
│                                         │
│  Products in this Look (6)              │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐          │
│  │Sofa│ │Table│ │Lamp│ │Rug │          │
│  │45K │ │12K │ │8K  │ │15K │          │
│  │[+] │ │[+] │ │[+] │ │[+] │          │
│  └────┘ └────┘ └────┘ └────┘          │
│                                         │
│  Total: $125,000    [Add All to Cart]   │
└─────────────────────────────────────────┘
```

### 3. Cart Context

```tsx
interface CartItem {
  id: number;
  name: string;
  price: number;
  image_url: string;
  source_website: string;
  source_url: string;
  quantity: number;
}

interface CartContextType {
  items: CartItem[];
  addToCart: (product) => void;
  removeFromCart: (productId) => void;
  updateQuantity: (productId, quantity) => void;
  clearCart: () => void;
  totalItems: number;
  totalPrice: number;
}
```

- Persists to `sessionStorage` as `cart` key
- Loads on mount, saves on every change

---

## Implementation Phases

### Phase 1: Backend Foundation (2-3 days)
1. Create `curated_styling_service.py` with room product mappings
2. Create `curated.py` router with `/generate` endpoint
3. Register router in `main.py`
4. Test endpoint with Postman

### Phase 2: Frontend - Curated Page (2-3 days)
1. Create `/app/curated/page.tsx` with loading/success/error states
2. Create `CuratedLookCard.tsx` component
3. Create `LookDetailModal.tsx` component
4. Add `generateCuratedLooks()` to `api.ts`
5. Update `store-select/page.tsx` navigation

### Phase 3: Cart Feature (1-2 days)
1. Create `CartContext.tsx` with sessionStorage persistence
2. Create `CartIcon.tsx` for header
3. Create `CartPanel.tsx` slide-out panel
4. Wrap app with `CartProvider` in `layout.tsx`

### Phase 4: Polish & Testing (1-2 days)
1. Loading animations and skeleton states
2. Error handling and retry logic
3. Mobile responsiveness
4. Edge case testing

---

## Critical Files to Read Before Implementation

1. **`/api/services/google_ai_service.py`** - `analyze_room_image()` and visualization methods
2. **`/api/services/recommendation_engine.py`** - `get_recommendations()` with `RecommendationRequest`
3. **`/api/routers/chat.py`** - Pattern for session management and API structure
4. **`/frontend/src/app/store-select/page.tsx`** - Current navigation to modify
5. **`/frontend/src/components/ProductDetailModal.tsx`** - Component pattern to follow

---

## Technical Considerations

1. **Batch Visualization Limit**: Max 4 products per visualization call. For 5+ products, use incremental approach (existing pattern in chat.py)

2. **Progressive Loading**: Show each look as it completes (~15s per look). First look appears quickly, others follow. Use skeleton placeholders for pending looks.

3. **Product Deduplication**: Same product shouldn't appear in multiple looks

4. **Store Filtering**: Products must come only from user's selected stores

5. **Cart vs Canvas**: Cart is separate from the design studio canvas. Users can add to cart from curated, then style manually in design studio with different products.

6. **"Style by Yourself" - Two Entry Points**:
   - **On a specific look card**: Pre-populates design studio canvas with products from that look. User can modify/swap items. Pass `selectedLookId` via URL param or sessionStorage.
   - **Standalone button** (separate from look cards): Takes user to design studio with room image loaded but **empty canvas** (no products). User starts fresh with manual product discovery via chat.

---

## UX Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Number of looks | 3 | Good variety without overwhelming |
| Style themes | Distinct per look | Each has unique aesthetic (Modern, Traditional, etc.) |
| Store filter timing | Before curated | User picks stores first |
| Cart type | Real cart (basic) | Separate from canvas, no checkout |
| Loading approach | Progressive | Better perceived performance |
| "Style by Yourself" | Two entry points | On look card → pre-populate canvas. Standalone button → empty canvas |
| Product selection | AI-driven (ChatGPT) | AI selects products that complement each other aesthetically |
| Cohesion level | Complementary | Products complement each other, not strictly matching |
