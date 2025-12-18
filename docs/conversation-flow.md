# Omni Chat - End-to-End Conversation Flow

## System Capabilities

| Feature | Supported | Notes |
|---------|-----------|-------|
| Search products by category | YES | Sofas, tables, lighting, decor, etc. |
| Filter by style/budget | YES | Modern, traditional, ₹10k-50k, etc. |
| Show product recommendations | YES | Display in product panel |
| Visualize in room image | YES | AI places products in uploaded room |
| Create custom "looks" | NO | Cannot generate curated collections on-the-fly |
| Design without products | NO | Must show actual purchasable items |

---

## Master Flow Chart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER STARTS CHAT                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │     What did user say?          │
                    └─────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        ▼                             ▼                             ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│ DIRECT SEARCH │           │ STYLE REQUEST │           │ BROWSE/CHAT   │
│               │           │               │           │               │
│ "show sofas"  │           │ "style my     │           │ "what do you  │
│ "need lamp"   │           │  living room" │           │  have?"       │
│ "find rugs"   │           │ "help design" │           │ "hi/hello"    │
└───────────────┘           └───────────────┘           └───────────────┘
        │                             │                             │
        ▼                             ▼                             ▼
   [FLOW A]                      [FLOW B]                      [FLOW C]
```

---

## FLOW A: Direct Product Search

**Trigger phrases**: "show me [product]", "I need a [product]", "suggest [product]", "find [product]"

```
┌─────────────────────────────────────────────────────────────────┐
│ User: "Show me floor lamps" / "I need a sofa" / "Suggest rugs"  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │ GPT detects category          │
                │ detected_category: "sofas"    │
                │ is_direct_search: true        │
                └───────────────────────────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │ Is it a GENERIC category?     │
                │ (lighting, seating, tables)   │
                └───────────────────────────────┘
                       │              │
                      YES            NO
                       │              │
                       ▼              │
        ┌──────────────────────┐      │
        │ ASK: Which type?     │      │
        │                      │      │
        │ "Floor lamps, table  │      │
        │  lamps, or ceiling?" │      │
        └──────────────────────┘      │
                       │              │
                       ▼              │
              User picks type         │
                       │              │
                       └──────┬───────┘
                              │
                              ▼
                ┌───────────────────────────────┐
                │ Has style OR budget context?  │
                │ (from earlier in conversation)│
                └───────────────────────────────┘
                       │              │
                      YES            NO
                       │              │
                       ▼              ▼
        ┌──────────────────┐  ┌──────────────────┐
        │                  │  │ Is it a COMPLEX  │
        │   SHOW PRODUCTS  │  │ category? (sofa, │
        │   IMMEDIATELY    │  │ dining table)    │
        │                  │  └──────────────────┘
        │ "Here are floor  │         │      │
        │  lamps for your  │        YES    NO
        │  modern space"   │         │      │
        │                  │         ▼      ▼
        │ + PRODUCTS IN    │  ┌─────────┐ ┌─────────────┐
        │   PANEL          │  │ASK style│ │SHOW PRODUCTS│
        └──────────────────┘  │question │ │immediately  │
                              └─────────┘ └─────────────┘
                                    │
                                    ▼
                              User answers
                                    │
                                    ▼
                              SHOW PRODUCTS

═══════════════════════════════════════════════════════════════════
EXPECTED OUTPUT:
- GPT Response: "Here are [category] that match your style"
- Product Panel: POPULATED with relevant products
- State: DIRECT_SEARCH or READY_TO_RECOMMEND

WRONG OUTPUT (current bugs):
- GPT Response: "I recommend a sleek arc lamp..." (advice only)
- Product Panel: EMPTY
- User has to ask again
═══════════════════════════════════════════════════════════════════
```

---

## FLOW B: Room Styling Request

**Trigger phrases**: "style my room", "help me design", "decorate my space", "I want to furnish"

```
┌─────────────────────────────────────────────────────────────────┐
│ User: "Style my living room" / "Help me design my bedroom"      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │ Does user have room image?    │
                └───────────────────────────────┘
                       │              │
                      YES            NO
                       │              │
                       ▼              │
        ┌──────────────────────┐      │
        │ START FURNITURE      │      │
        │ REMOVAL (background) │      │
        │                      │      │
        │ - Analyze perspective│      │
        │ - Transform if needed│      │
        │ - Remove furniture   │      │
        └──────────────────────┘      │
                       │              │
                       └──────┬───────┘
                              │
                              ▼
                ┌───────────────────────────────┐
                │ Already have style + budget?  │
                └───────────────────────────────┘
                       │              │
                      YES            NO
                       │              │
                       │              ▼
                       │    ┌─────────────────────────┐
                       │    │ GATHERING FLOW          │
                       │    │                         │
                       │    │ Q1: "What room type?"   │
                       │    │     → living/bedroom    │
                       │    │                         │
                       │    │ Q2: "What style?"       │
                       │    │     → modern/traditional│
                       │    │                         │
                       │    │ Q3: "What budget?"      │
                       │    │     → ₹50k / no limit   │
                       │    └─────────────────────────┘
                       │              │
                       └──────┬───────┘
                              │
                              ▼
                ┌───────────────────────────────┐
                │ SHOW PRODUCT CATEGORIES       │
                │                               │
                │ Based on room type, show:     │
                │ - Sofas (₹20k-40k)            │
                │ - Coffee Tables (₹5k-15k)    │
                │ - Lighting (₹3k-10k)         │
                │ - Decor (₹2k-8k)             │
                └───────────────────────────────┘
                              │
                              ▼
                ┌───────────────────────────────┐
                │ User browses & selects        │
                │ products from each category   │
                └───────────────────────────────┘
                              │
                              ▼
                ┌───────────────────────────────┐
                │ If room image exists:         │
                │ VISUALIZE selected products   │
                │ in the room                   │
                └───────────────────────────────┘

═══════════════════════════════════════════════════════════════════
EXPECTED OUTPUT:
- GPT Response: "For your modern living room, I suggest these categories"
- Product Panel: POPULATED with categorized products
- State: READY_TO_RECOMMEND

WRONG OUTPUT (current bugs):
- GPT Response: "I'll put together a cohesive look for you!"
- Product Panel: EMPTY (we can't "create looks")
- User confused about what to do next
═══════════════════════════════════════════════════════════════════
```

---

## FLOW C: Browse/General Chat

**Trigger phrases**: "hello", "what can you do", "show me everything", general questions

```
┌─────────────────────────────────────────────────────────────────┐
│ User: "Hi" / "What do you have?" / "Help me"                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │ Is it a greeting/general?     │
                └───────────────────────────────┘
                       │              │
                    GREETING      QUESTION
                       │              │
                       ▼              ▼
        ┌──────────────────┐  ┌──────────────────┐
        │ "Hi! I'm Omni,   │  │ "What are you    │
        │  your AI stylist.│  │  looking for?    │
        │  What room are   │  │  A specific      │
        │  you working on?"│  │  product or help │
        │                  │  │  styling a room?"│
        └──────────────────┘  └──────────────────┘
                       │              │
                       └──────┬───────┘
                              │
                              ▼
                    User provides direction
                              │
                              ▼
                    Route to FLOW A or FLOW B
```

---

## State Machine Summary

```
                              ┌─────────┐
                              │ INITIAL │
                              └────┬────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  DIRECT_SEARCH  │      │ GATHERING_STYLE │      │    BROWSING     │
│                 │      │        │        │      │                 │
│ User asked for  │      │        ▼        │      │ User exploring  │
│ specific product│      │ GATHERING_BUDGET│      │                 │
└────────┬────────┘      │        │        │      └────────┬────────┘
         │               │        ▼        │               │
         │               │ GATHERING_SCOPE │               │
         │               └────────┬────────┘               │
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                                  ▼
                       ┌───────────────────┐
                       │ READY_TO_RECOMMEND│
                       │                   │
                       │ ✓ Show products   │
                       │ ✓ Panel populated │
                       │ ✓ User can select │
                       └───────────────────┘
```

---

## Decision Logic: When to Show Products

```
SHOW PRODUCTS IMMEDIATELY when:
├── detected_category is set (GPT understood what user wants)
├── AND (has_style OR has_budget OR is_simple_category)
│
├── Examples that SHOULD show products:
│   ├── "show me floor lamps" → YES (simple category)
│   ├── "I need a modern sofa" → YES (has style)
│   ├── "sofas under 50k" → YES (has budget)
│   └── "accent chairs" → YES (specific category)

ASK QUESTIONS FIRST when:
├── detected_category is set
├── AND no_style AND no_budget AND is_complex_category
│
├── Examples that need questions:
│   ├── "I need a sofa" (no style/budget) → Ask style
│   └── "show me lighting" (generic) → Ask which type

NEVER DO:
├── "I recommend X..." without showing actual products
├── "I'll create a look..." (we can't do this)
├── "Would you like suggestions?" (just show them)
└── Multiple question rounds when context exists
```

---

## GPT Response Rules

### ALWAYS include with response:
```json
{
  "detected_category": "floor_lamps",     // Set when category identified
  "is_direct_search": true,               // Set when user wants specific product
  "conversation_state": "READY_TO_RECOMMEND"  // When products should show
}
```

### Response templates:

**Direct Search (products should show):**
> "Here are floor lamps that would complement your modern living room."
> [Products appear in panel]

**Gathering (need more info):**
> "I'd love to help! What style are you going for - modern, traditional, or something else?"
> [No products yet]

**WRONG responses to avoid:**
> ❌ "I recommend a sleek arc lamp with metallic finish..." (advice without products)
> ❌ "I'll put together a stylish look for you!" (can't create looks)
> ❌ "Would you like me to suggest some options?" (just show them!)

---

## Implementation Fixes Needed

| Issue | Current Behavior | Expected Behavior | Fix |
|-------|------------------|-------------------|-----|
| Advice without products | "I recommend X..." | Show X in panel | Ensure detected_category → products |
| Promise looks | "I'll create a look" | Show product categories | Update GPT prompt |
| Unnecessary questions | "Would you like...?" | Just show products | Skip if has context |
| Empty panel | GPT talks, panel empty | Panel populated | Check state machine |
