# Chat Use Cases - Omnishop AI Stylist

This document covers all implemented chat use cases for the Omnishop AI Interior Stylist (Omni).

---

## Table of Contents

1. [Conversation Flow States](#1-conversation-flow-states)
2. [User Intent Detection](#2-user-intent-detection)
3. [Direct Product Search](#3-direct-product-search)
4. [Material/Texture Detection](#4-materialtexture-detection)
5. [Color Detection](#5-color-detection)
6. [Style Detection](#6-style-detection)
7. [Budget Detection](#7-budget-detection)
8. [Size/Configuration Detection](#8-sizeconfiguration-detection)
9. [Multi-Attribute Search](#9-multi-attribute-search)
10. [Room Type Detection](#10-room-type-detection)
11. [User Declines Preferences](#11-user-declines-preferences)
12. [Returning User Flow](#12-returning-user-flow)
13. [Full Room vs Specific Category](#13-full-room-vs-specific-category)
14. [Simple vs Complex Categories](#14-simple-vs-complex-categories)
15. [Multi-Category Search](#15-multi-category-search)
16. [Accumulated Context](#16-accumulated-context)
17. [Room Image Analysis](#17-room-image-analysis)

---

## 1. Conversation Flow States

The AI maintains conversation state to guide the interaction:

### Gathering States (Information Collection)
| State | Purpose |
|-------|---------|
| `GATHERING_USAGE` | Collecting what the room is used for |
| `GATHERING_STYLE` | Collecting style preferences |
| `GATHERING_BUDGET` | Collecting budget information |
| `GATHERING_SCOPE` | Determining full room or specific category |
| `GATHERING_PREFERENCE_MODE` | User provides preferences vs Omni decides |
| `GATHERING_ATTRIBUTES` | Category-specific attributes (shape, material, etc.) |

### Action States (Product Recommendation)
| State | Purpose |
|-------|---------|
| `DIRECT_SEARCH` | User explicitly asked for specific product |
| `DIRECT_SEARCH_GATHERING` | Direct search with follow-up questions |
| `READY_TO_RECOMMEND` | All info gathered, ready to show products |
| `BROWSING` | User browsing product results |

---

## 2. User Intent Detection

### Implemented Scenarios

| User Input Pattern | Detected Intent | Result |
|-------------------|-----------------|--------|
| "Show me sofas" | Direct search | Shows sofas immediately |
| "I need a rug" | Direct search | Shows rugs immediately |
| "Style the entire room" | Full room styling | Enters gathering flow |
| "Just looking for a table" | Specific category | Focuses on tables only |
| "You choose for me" | Omni decides | Auto-selects based on room |

---

## 3. Direct Product Search

### Use Case: User explicitly requests a product category

**Examples:**
- "Show me sofas"
- "I need a dining table"
- "Suggest floor lamps"
- "Looking for wall art"

**System Behavior:**
1. Detects `is_direct_search=true`
2. Extracts `detected_category`
3. For simple categories → Shows products immediately
4. For complex categories → Asks 2-3 clarifying questions first

**Special Pattern: [Item] for [Room]**
- Input: "wall art for living room"
- Correctly identifies: category = `wall_art`, room = `living room`
- Does NOT confuse "living room" as the category

---

## 4. Material/Texture Detection

### Use Case: User specifies material preference with category

**Example:**
```
User: "I want a leather sofa"
```

**System Behavior:**
1. Extracts material: `leather`
2. Extracts category: `sofas`
3. Passes both to search algorithm
4. Returns only leather sofas

### Recognized Materials (28 total)
| Category | Materials |
|----------|-----------|
| Wood | wood, wooden, teak, sheesham, oak, walnut, mahogany |
| Fabric | leather, velvet, fabric, cotton, linen, silk, wool, upholstered |
| Metal | metal, brass, iron, steel, chrome |
| Natural | rattan, wicker, bamboo, jute, cane |
| Stone | marble, stone, ceramic, glass |
| Other | plastic, acrylic |

### More Examples
| User Input | Material | Category |
|------------|----------|----------|
| "Velvet accent chair" | velvet | accent_chairs |
| "Marble coffee table" | marble | coffee_tables |
| "Wooden dining table" | wood | dining_tables |
| "Rattan chair" | rattan | accent_chairs |
| "Brass floor lamp" | brass | floor_lamps |

---

## 5. Color Detection

### Use Case: User specifies color preference

**Example:**
```
User: "Show me blue sofas"
User: "I want something in beige"
```

**System Behavior:**
1. Extracts color from message
2. Applies as filter to product search
3. Returns products matching the color

### Recognized Colors (35 total)
| Category | Colors |
|----------|--------|
| Basic | white, black, brown, grey/gray, red, blue, green, yellow, orange, pink, purple |
| Neutral | beige, cream, ivory, tan, neutral |
| Metallic | gold, silver, bronze, copper |
| Wood tones | walnut, oak, mahogany, natural |
| Other | navy, teal, dark, light |

---

## 6. Style Detection

### Use Case: User specifies design style

**Example:**
```
User: "I like modern furniture"
User: "Looking for something minimalist"
User: "Show me bohemian decor"
```

**System Behavior:**
1. Extracts style preference
2. Stores in `overall_style` for session
3. Applies style filter to all subsequent searches

### Recognized Styles (23 total)
| Style Category | Keywords |
|----------------|----------|
| Contemporary | modern, contemporary, minimalist, sleek |
| Traditional | traditional, classic, elegant, ornate |
| Rustic | rustic, farmhouse, vintage, retro |
| Eclectic | bohemian, boho, mid-century |
| Other | industrial, scandinavian, coastal, cozy, warm, luxurious |

---

## 7. Budget Detection

### Use Case: User specifies budget constraint

**Examples:**
```
User: "Budget is 50000"
User: "Under ₹75,000"
User: "Max 1 lakh"
User: "Nothing above 25k"
```

**System Behavior:**
1. Extracts budget value using regex patterns
2. Converts to numeric (handles "lakh", "k" formats)
3. Stores as `budget_total` or `extracted_budget_max`
4. Filters products within budget range

### Supported Budget Formats
| Format | Example | Extracted Value |
|--------|---------|-----------------|
| Plain number | "50000" | 50000 |
| With ₹ symbol | "₹75,000" | 75000 |
| With "k" suffix | "25k" | 25000 |
| With "lakh" | "1 lakh" | 100000 |
| With "under/max/upto" | "under 50000" | 50000 (max) |

---

## 8. Size/Configuration Detection

### Use Case: User specifies size or seating capacity

**Examples:**
```
User: "L-shaped sofa"
User: "3-seater couch"
User: "King size bed"
User: "Compact coffee table"
```

**System Behavior:**
1. Extracts size/configuration keyword
2. Maps to search filter
3. Returns appropriately sized products

### Recognized Size Keywords
| Category | Keywords |
|----------|----------|
| General | large, small, big, compact, mini, xl |
| Bed sizes | king, queen, single, double, twin |
| Seating | single seater, 2 seater, 3 seater, 4 seater, l-shaped, sectional |

---

## 9. Multi-Attribute Search

### Use Case: User combines multiple attributes in one request

**Example:**
```
User: "I want a leather sofa in brown, modern style, under 50000"
```

**System Behavior:**
1. Extracts ALL attributes:
   - Material: leather
   - Category: sofas
   - Color: brown
   - Style: modern
   - Budget: max 50000
2. Applies combined filters to search
3. Returns products matching ALL criteria

### Complex Examples
| User Input | Extracted Attributes |
|------------|---------------------|
| "Velvet accent chair in blue, bohemian style" | material=velvet, category=accent_chairs, color=blue, style=bohemian |
| "Large wooden dining table for 6 people" | material=wood, category=dining_tables, size=large, seating=6 |
| "Minimalist white marble coffee table under 20k" | style=minimalist, color=white, material=marble, category=coffee_tables, budget_max=20000 |

---

## 10. Room Type Detection

### Use Case: User mentions room type

**Examples:**
```
User: "Designing my living room"
User: "Need furniture for bedroom"
User: "Setting up home office"
```

**System Behavior:**
1. Extracts room type from message
2. Stores as `room_type`
3. Generates relevant default categories
4. Tailors recommendations to room context

### Recognized Room Types
- Living room
- Bedroom
- Dining room
- Office / Study
- Kitchen
- Bathroom
- Balcony

---

## 11. User Declines Preferences

### Use Case: User doesn't want to provide preferences

**Examples:**
```
User: "No budget"
User: "Any style is fine"
User: "You choose"
User: "Surprise me"
User: "I'm flexible"
```

**System Behavior:**
1. Detects decline phrases
2. Sets `preference_mode=omni_decides`
3. Skips gathering questions
4. Uses room image analysis (if available) for auto-selection
5. Shows products immediately without filters

### Recognized Decline Phrases
- "no style", "no budget", "no preference"
- "any style", "any budget", "anything"
- "you choose", "you decide", "omni choose"
- "surprise me", "up to you", "your choice"
- "flexible", "open to", "don't have"

---

## 12. Returning User Flow

### Use Case: User has existing preferences from previous session

**System Behavior:**
1. Loads saved preferences (style, budget, room type)
2. Customizes welcome message: "Welcome back! I remember you were working on your [room_type]"
3. Skips questions for already-known preferences
4. Goes directly to recommendations if sufficient info exists

### Preserved Data
- Room type
- Overall style
- Budget total
- Category-specific preferences
- Previous product selections

---

## 13. Full Room vs Specific Category

### Use Case: Determining scope of styling request

**Full Room Indicators:**
- "Style the entire room"
- "Furniture and decor"
- "Complete room makeover"
- "Full living room setup"

**Specific Category Indicators:**
- "Just a sofa"
- "Only looking for lighting"
- "Need a coffee table"

**System Behavior:**
- Full room: Generates 6-9 default categories for room type
- Specific category: Focuses only on requested category

---

## 14. Simple vs Complex Categories

### Simple Categories (Show products immediately)
No follow-up questions needed:
- Wall art, Decor accents, Planters
- Vases, Candles, Photo frames
- Mirrors, Clocks, Sculptures
- Bookends, Trays, Baskets
- Artificial plants, Benches

### Complex Categories (Ask clarifying questions)
Require 2-3 attribute questions:
- Sofas (seating type, style, color)
- Dining tables (capacity, shape, material)
- Beds (size, style, headboard)
- Rugs (size, style, material)
- Curtains (style, fabric, color)

---

## 15. Multi-Category Search

### Use Case: User requests multiple product types

**Example:**
```
User: "Show me sofas and coffee tables"
User: "Need L-shaped sofas and lounge chairs"
```

**System Behavior:**
1. Detects multiple categories
2. Stores ALL categories (not just first)
3. Fetches products for each category
4. Displays in separate category sections

---

## 16. Accumulated Context

### Use Case: User provides attributes in follow-up messages

**Example:**
```
User: "Show me sofas"
[Products displayed]
User: "In green"
[Shows green sofas]
User: "Under 30000"
[Shows green sofas under 30000]
```

**System Behavior:**
1. Maintains accumulated filters across messages
2. Combines new qualifiers with existing context
3. Resets when category changes

### Tracked Accumulated Filters
- Category
- Product types
- Colors
- Materials
- Styles
- Price range
- Search terms

---

## 17. Room Image Analysis

### Use Case: User uploads room photo

**System Behavior:**
1. Analyzes room image via AI
2. Extracts:
   - Detected style (modern, traditional, etc.)
   - Color palette (4-6 dominant colors)
   - Detected materials (wood, fabric, metal, etc.)
   - Suggested categories (what furniture might be needed)
3. Uses analysis for:
   - Auto-filling preferences when `omni_decides`
   - Contextual recommendations
   - Visualization styling

---

## Future Use Cases (Planned)

### Texture Detection Enhancement
Currently implemented for materials. Future enhancements:
- Texture patterns (striped, solid, geometric)
- Finish types (matte, glossy, distressed)
- Weave patterns for fabrics

### Brand Preference
- "Show me [Brand] products"
- Filter by specific store/brand

### Negative Filters
- "No leather"
- "Nothing in black"
- "Avoid glass tables"

---

## Technical Implementation Notes

### Key Files
| File | Purpose |
|------|---------|
| `api/routers/chat.py` | Intent detection, state management, keyword extraction |
| `api/services/chatgpt_service.py` | GPT prompts, response parsing |
| `api/services/conversation_context.py` | Session state, accumulated filters |
| `api/config/category_attributes.py` | Category definitions, simple vs complex |
| `api/engines/recommendation/` | Product search and filtering |

### Attribute Extraction Functions
- `_extract_product_keywords()` - Categories from message
- `COLOR_KEYWORDS` - Color detection
- `MATERIAL_KEYWORDS` - Material detection
- `STYLE_KEYWORDS` - Style detection
- `SIZE_KEYWORDS` - Size/configuration detection
- Budget regex patterns - Budget extraction

---

*Last Updated: December 2024*
