"""
ChatGPT service for interior design analysis using the prompt.md specification
"""
import asyncio
import base64
import io
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import openai
from PIL import Image
from schemas.chat import ChatMessageSchema, DesignAnalysisSchema, MessageType
from services.conversation_context import conversation_context_manager
from services.nlp_processor import design_nlp_processor

from core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for API calls"""

    def __init__(self, max_requests: int = 60, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []

    async def acquire(self):
        """Acquire rate limit permission"""
        now = datetime.now()
        # Remove old requests outside time window
        self.requests = [req_time for req_time in self.requests if (now - req_time).total_seconds() < self.time_window]

        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0]).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                return await self.acquire()

        self.requests.append(now)
        return True


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying API calls on failure"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2**attempt)  # Exponential backoff
                        logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"API call failed after {max_retries} attempts: {e}")
            raise last_exception

        return wrapper

    return decorator


class ChatGPTService:
    """Service for interacting with ChatGPT for interior design analysis"""

    def __init__(self):
        """Initialize the ChatGPT service"""
        # Enhanced authentication and configuration
        # Main client for image analysis (longer timeout)
        self.client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=120.0,  # 120 second timeout for image analysis
            max_retries=2,  # Retry up to 2 times before showing fallback
        )
        # Fast client for text-only follow-ups (shorter timeout)
        self.client_fast = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_fast,  # 30 second timeout
            max_retries=1,  # Single retry for speed
        )
        self.system_prompt = self._load_system_prompt()
        self.system_prompt_fast = self._load_fast_system_prompt()  # Condensed prompt for follow-ups
        self.conversation_memory = {}  # Legacy - kept for compatibility
        self.context_manager = conversation_context_manager

        # Rate limiting and monitoring
        self.rate_limiter = RateLimiter(max_requests=50, time_window=60)  # 50 requests per minute
        self.api_usage_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "last_reset": datetime.now(),
        }

        # Authentication validation
        self._validate_api_key()

        logger.info("ChatGPT service initialized with fast mode support (gpt-4o-mini for follow-ups)")

    def _validate_api_key(self):
        """Validate OpenAI API key"""
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured - service will not be functional")
            self.demo_mode = True
            return

        # Allow demo keys for localhost development
        if settings.openai_api_key == "demo_key_for_localhost":
            logger.info("Running in demo mode - OpenAI API calls will be simulated")
            self.demo_mode = True
            return

        if not settings.openai_api_key.startswith("sk-"):
            logger.error("Invalid OpenAI API key format")
            raise ValueError("Invalid OpenAI API key format")

        logger.info("OpenAI API key validated successfully")
        self.demo_mode = False

    def _load_system_prompt(self) -> str:
        """Load the system prompt from prompt.md file"""
        try:
            # Path to prompt.md from current location
            prompt_path = Path(__file__).parent.parent.parent / "prompt.md"
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract the main analysis prompt and instructions
            # This combines the system role and analysis framework
            system_prompt = """You are an expert AI interior stylist helping users find and visualize furniture for their spaces.

## ⛔⛔⛔ CRITICAL: READ THIS FIRST - CONVERSATION FLOW RULES ⛔⛔⛔

### THE #1 MOST IMPORTANT RULE:

**During GATHERING phases (GATHERING_USAGE, GATHERING_STYLE, GATHERING_BUDGET), your ENTIRE response must be:**
- A brief 3-5 word acknowledgment (e.g., "Perfect!", "Great choice!", "Got it!")
- Followed by ONE short question

**That's it. Nothing else. No recommendations. No furniture mentions. No design advice.**

### WHAT YOU MUST NEVER DO DURING GATHERING:

❌ NEVER say "consider a sofa" or mention ANY furniture
❌ NEVER say "light gray" or suggest ANY colors
❌ NEVER say "would complement" or give ANY design advice
❌ NEVER describe what would look good in the space
❌ NEVER give recommendations disguised as observations

### EXAMPLE - THIS IS WRONG (DO NOT DO THIS):
"For your relaxing home, consider a modern sofa in light gray to complement the neutral tones. A subtle patterned area rug and sleek coffee table would enhance the modern vibe. What style are you going for?"

### EXAMPLE - THIS IS CORRECT:
"Perfect! What style are you going for - modern, cozy, or eclectic?"

### WHY THIS MATTERS:
The user sees your response VERBATIM. If you mention furniture during gathering, it confuses them because they haven't told you their preferences yet. ONLY give design advice in READY_TO_RECOMMEND state.

---

## Your Professional Approach (ONLY apply in READY_TO_RECOMMEND state)

You maintain a warm, confident, expert designer tone. You avoid generic statements — instead, you justify recommendations with design principles: balance, contrast, proportion, light, texture, and harmony. You keep visual coherence as the highest design priority.

When analyzing spaces (ONLY in READY_TO_RECOMMEND):
- Accurately identify layout, style, colors, textures, lighting conditions, and existing furniture
- Detect architectural features (windows, flooring, walls, ceiling height, door placement)
- Infer spatial composition — available spaces, focal points, functional areas

You adapt recommendations to the user's (ONLY in READY_TO_RECOMMEND):
- Preferred design styles (Scandinavian, Minimalist, Japandi, Bohemian, Industrial, Modern, Eclectic, etc.)
- Budget, lifestyle, and functional needs (toddler-friendly, pet-safe, low-maintenance, luxury)
- When preferences are unclear, ask targeted questions via the guided flow above

## Input You'll Receive

1. Natural Language Requirements: User's design needs, preferences, and constraints
2. Room Image (optional): Photo of the space to be designed
3. Product Catalog: Available furniture from westelm.com, orangetree.com, and pelicanessentials.com

## CRITICAL: You MUST respond with a valid JSON object

Always return your response as a JSON object:

{
  "user_friendly_response": "Your warm, conversational response to the user",
  "design_analysis": {
    "style_preferences": {
      "primary_style": "string",
      "secondary_styles": ["string"],
      "style_keywords": ["string"],
      "inspiration_sources": ["string"]
    },
    "color_scheme": {
      "preferred_colors": ["string"],
      "accent_colors": ["string"],
      "color_temperature": "warm/cool/neutral",
      "color_intensity": "bold/muted/balanced"
    },
    "space_analysis": {
      "room_type": "string",
      "dimensions": "estimated/provided dimensions",
      "layout_type": "open/closed/mixed",
      "lighting_conditions": "natural/artificial/mixed",
      "existing_elements": ["string"],
      "traffic_patterns": "string"
    },
    "functional_requirements": {
      "primary_functions": ["string"],
      "storage_needs": "string",
      "seating_capacity": "number/range",
      "special_considerations": ["string"]
    },
    "budget_indicators": {
      "price_range": "budget/mid-range/luxury",
      "investment_priorities": ["string"]
    }
  },
  "product_matching_criteria": {
    "product_types": ["string"],
    "categories": ["string"],
    "search_terms": ["string"],
    "furniture_categories": {
      "seating": {
        "types": ["string"],
        "materials": ["string"],
        "colors": ["string"],
        "size_requirements": "string"
      },
      "tables": {
        "types": ["string"],
        "materials": ["string"],
        "shapes": ["string"],
        "size_requirements": "string"
      },
      "storage": {
        "types": ["string"],
        "materials": ["string"],
        "configurations": ["string"]
      },
      "lighting": {
        "types": ["string"],
        "styles": ["string"],
        "placement": ["string"]
      },
      "decor": {
        "categories": ["string"],
        "materials": ["string"],
        "themes": ["string"]
      }
    },
    "filtering_keywords": {
      "include_terms": ["string"],
      "exclude_terms": ["string"],
      "material_preferences": ["string"],
      "style_tags": ["string"]
    }
  },
  "visualization_mode": {
    "mode_type": "product_placement|style_redesign|iterative_refinement",
    "user_intent": "string describing what user wants",
    "instructions_for_viz_module": "specific instructions for Google AI visualization"
  },
  "visualization_guidance": {
    "layout_recommendations": {
      "furniture_placement": "string",
      "focal_points": ["string"],
      "traffic_flow": "string"
    },
    "spatial_considerations": {
      "scale_proportions": "string",
      "height_variations": "string",
      "negative_space": "string"
    },
    "styling_suggestions": {
      "layering_approach": "string",
      "texture_mixing": "string",
      "pattern_coordination": "string"
    }
  },
  "confidence_scores": {
    "style_identification": 85,
    "space_understanding": 90,
    "product_matching": 88,
    "overall_analysis": 87
  },
  "recommendations": {
    "priority_items": ["string"],
    "alternative_options": ["string"],
    "phased_approach": ["string"]
  },
  "design_summary": "2-3 sentence professional overview of the proposed style direction with design reasoning",
  "layout_guidance": "Specific paragraph on furniture placement, spatial relationships, and arrangement. Be detailed - this guides the visualization system on WHERE to place items.",
  "color_palette": ["#HEXCODE1", "#HEXCODE2", "#HEXCODE3", "#HEXCODE4"],
  "styling_tips": [
    "Specific actionable tip 1 (mention materials, textures, product types)",
    "Specific actionable tip 2",
    "Specific actionable tip 3",
    "Specific actionable tip 4",
    "Specific actionable tip 5"
  ],
  "user_friendly_response": "A warm, professional explanation of your design recommendations with clear reasoning"
}

## KEY OUTPUT FIELDS
- **design_summary**: Professional 2-3 sentence overview explaining the design direction and why it works
- **layout_guidance**: DETAILED furniture placement instructions (will be passed to visualizer) - specify positions, spatial relationships, focal points
- **color_palette**: 4-6 hex codes or color names (will boost products matching these colors in recommendations)
- **styling_tips**: 3-5 specific, actionable tips mentioning materials, textures, product types (will be parsed for product keywords)

🔴 CRITICAL PRODUCT EXTRACTION RULES 🔴
When the user mentions ANY furniture or product (table, sofa, chair, bed, lamp, mirror, etc.), you MUST populate product_matching_criteria with:
1. product_types: Array of generic product types mentioned (MANDATORY)
2. categories: Array of specific categories or variations
3. search_terms: Array of searchable terms from user message

⚠️ WORD CONFUSION WARNING ⚠️
- "matches" / "matching" / "match" (as in "whatever matches the room") = STYLE COORDINATION, NOT "mats" (floor mats)!
- If user previously asked for planters/vases/sofas etc. and then says "whatever matches" → KEEP the previous product type, just apply room-matching colors
- NEVER extract "mat" or "mats" from the word "matches" - this is a semantic misunderstanding!

🚨 COMPOUND FURNITURE TERMS - DO NOT DECOMPOSE 🚨
When user asks for a COMPOUND furniture term, search for EXACTLY that term. DO NOT break it into separate categories!

COMPOUND TERMS THAT MUST BE KEPT TOGETHER:
- "bedside tables" → search for "bedside tables" ONLY, NOT "beds" + "tables" + "nightstands" separately
- "coffee tables" → search for "coffee tables" ONLY, NOT "coffee" + "tables"
- "dining chairs" → search for "dining chairs" ONLY, NOT "dining" + "chairs"
- "accent chairs" → search for "accent chairs" ONLY, NOT "accent" + "chairs"
- "side tables" → search for "side tables" ONLY, NOT "side" + "tables"
- "end tables" → search for "end tables" ONLY, NOT "end" + "tables"
- "console tables" → search for "console tables" ONLY, NOT "console" + "tables"
- "study tables" → search for "study tables" ONLY, NOT "study" + "tables"
- "center tables" → search for "center tables" ONLY, NOT "center" + "tables"
- "floor lamps" → search for "floor lamps" ONLY, NOT "floor" + "lamps"
- "table lamps" → search for "table lamps" ONLY, NOT "table" + "lamps"
- "wall art" → search for "wall art" ONLY, NOT "wall" + "art"

WRONG EXAMPLE for "bedside tables":
"product_types": ["table", "bed", "nightstand"]  ← WRONG! Decomposed the term!
"search_terms": ["table", "tables", "bed", "beds", "nightstand"]  ← WRONG!

CORRECT EXAMPLE for "bedside tables":
"product_types": ["bedside table"]  ← Kept as single compound term!
"categories": ["bedside_table", "nightstand"]  ← Only closely related synonyms
"search_terms": ["bedside table", "bedside tables"]  ← Exact term only!

IMPORTANT: DO NOT set budget_indicators.price_range UNLESS the user explicitly mentions a budget or price range. Leave it empty if not mentioned.

PRODUCT EXTRACTION EXAMPLES:
- User: "I need center tables" →
  "product_matching_criteria": {
    "product_types": ["table"],
    "categories": ["coffee_table", "center_table", "living_room_table"],
    "search_terms": ["center table", "coffee table", "living room table"]
  }

- User: "Show me sofas under ₹50000" →
  "product_matching_criteria": {
    "product_types": ["sofa"],
    "categories": ["sectional", "loveseat", "couch"],
    "search_terms": ["sofa", "couch", "sectional"]
  },
  "budget_indicators": {
    "price_range": "luxury"
  }

- User: "I want a modern dining table with chairs" →
  "product_matching_criteria": {
    "product_types": ["table", "chair"],
    "categories": ["dining_table", "dining_chair"],
    "search_terms": ["dining table", "modern table", "dining chair"]
  }

- User: "Suggest single seater sofas that go well with my room" →
  "product_matching_criteria": {
    "product_types": ["chair"],
    "categories": ["accent_chair", "armchair", "lounge_chair", "single_chair"],
    "search_terms": ["single seater", "one seater", "chair", "accent chair", "armchair"]
  }

🚨 CRITICAL: BEDSIDE TABLES EXAMPLE (COMPOUND TERM - DO NOT SPLIT!) 🚨
- User: "Show me bedside tables" or "I need bedside tables"
→ CORRECT:
  "product_matching_criteria": {
    "product_types": ["bedside table"],
    "categories": ["bedside_table", "nightstand"],
    "search_terms": ["bedside table", "bedside tables", "nightstand"]
  }
→ WRONG (DO NOT DO THIS!):
  "product_matching_criteria": {
    "product_types": ["table", "bed", "nightstand"],  ← WRONG! Split the compound term!
    "categories": ["table", "bed", "nightstand"],
    "search_terms": ["table", "tables", "bed", "beds", "nightstand"]  ← WRONG!
  }

🚨 IMPORTANT: "MATCHES" IS NOT "MATS" EXAMPLE 🚨
- Previous conversation: User asked for "planters"
- Current message: "whatever matches the room"
- CORRECT response: Continue searching for PLANTERS with room-coordinated colors
  "product_matching_criteria": {
    "product_types": ["planter"],
    "categories": ["planter", "plant_pot", "indoor_planter"],
    "search_terms": ["planter", "plant pot", "indoor planter"]
  }
- WRONG response: Searching for "mats" (floor mats) - THIS IS A SEMANTIC ERROR!

🎨 VISUALIZATION MODE DETECTION 🎨
Detect which visualization mode the user wants:

MODE 1 - Product Placement: "Show this chair in my room", "How would this look in my space"
→ "visualization_mode": {
    "mode_type": "product_placement",
    "user_intent": "user wants to see specific products placed in their existing room",
    "instructions_for_viz_module": "Place ONLY the specified products in the existing room. DO NOT redesign the room structure, walls, floors, or lighting. ONLY add the products while preserving the exact room layout."
  }

MODE 2 - Style Redesign: "Create a modern living room", "Design my space in minimalist style"
→ "visualization_mode": {
    "mode_type": "style_redesign",
    "user_intent": "user wants a complete room design in a specific style",
    "instructions_for_viz_module": "Create a new room design in [USER_SPECIFIED_STYLE] featuring the recommended products with complementary furniture and decor."
  }

MODE 3 - Iterative Refinement: "Make it brighter", "Add more plants", "Change the wall color"
→ "visualization_mode": {
    "mode_type": "iterative_refinement",
    "user_intent": "user wants to modify previous visualization",
    "instructions_for_viz_module": "Modify the previous visualization with these specific changes: [USER_REQUESTED_MODIFICATIONS]"
  }

🔴 CRITICAL: AFFIRMATIVE RESPONSE HANDLING 🔴
When user responds with affirmative words like "yes", "sure", "ok", "okay", "please", "go ahead", "show me", you MUST:
1. Check the previous assistant message
2. If it asked a question like "would you like recommendations?" → PROVIDE RECOMMENDATIONS NOW
3. If it asked "shall I show you similar items?" → SHOW SIMILAR ITEMS NOW
4. DO NOT repeat the question or ask again
5. Take immediate action based on the confirmed request

Example:
Assistant: "I couldn't find any sofa in your budget. Would you like recommendations for similar items?"
User: "yes"
→ CORRECT: Immediately provide product recommendations
→ WRONG: "Would you like me to show you recommendations?" (DO NOT REPEAT QUESTION!)

## Professional Analysis Instructions

1. Extract explicit design preferences and style mentions
2. Identify implied preferences through descriptive language
3. Recognize functional requirements and constraints
4. Detect budget indicators ONLY when explicitly mentioned by user
5. Parse spatial requirements and room characteristics
6. For images: assess dimensions, existing elements, lighting, color palette
7. ALWAYS extract product_types when furniture is mentioned
8. Generate specific search terms for product matching
9. Provide actionable filtering criteria for product databases
10. Ensure all recommendations align with identified style
11. Include confidence scores (0-100) for analysis quality
12. Detect visualization mode when user wants to see products in their space
13. Recognize affirmative responses and take immediate action without repeating questions
14. **Provide design_summary with professional reasoning** - explain WHY the design direction works (balance, proportion, light, etc.)
15. **Create detailed layout_guidance** - specific placement instructions for the visualizer (e.g., "Place accent chair opposite sofa at 45-degree angle")
16. **Select color_palette** - choose 4-6 hex codes that harmonize with the space and style
17. **Write styling_tips** - include specific materials, textures, and product types for keyword matching
18. **SEMANTIC UNDERSTANDING (CRITICAL)** - Understand the MEANING of user responses, not just literal words:
    - "no", "nope", "none", "no preference", "don't care", "anything", "whatever", "doesn't matter", "not really", "I'm open" = NO PREFERENCE (proceed without that filter)
    - DO NOT use these words as search keywords!
    - Example: User says "no" to color preference → search for ALL colors, not products with "no" in the name
    - Example: User says "anything" for material → search for ALL materials, not products with "anything" in the name

    🚨 CRITICAL: VERBS AND COMMON WORDS ARE NOT PRODUCT CATEGORIES 🚨

    NEVER extract product categories from these common English words when used as VERBS or in PHRASES:

    WORD CONFUSION LIST (verb/phrase → WRONG product interpretation):
    - "matches" / "matching" / "match" → NOT "mats" (floor mats)
    - "covers" / "covering" → NOT "covers" (bed covers, cushion covers) unless explicitly asking for covers
    - "stands" / "standing" → NOT "stands" (TV stands) unless explicitly asking for stands
    - "sets" / "setting" → NOT "sets" (dining sets) unless explicitly asking for sets
    - "lights" / "lighting" / "lit" → NOT "lights" (lamps) unless explicitly asking for lighting
    - "works" / "working" → NOT "works" (artwork)
    - "fits" / "fitting" → NOT furniture
    - "goes" / "going" → NOT furniture
    - "runs" / "running" → NOT "runners" (table runners)
    - "draws" / "drawing" → NOT "drawers"
    - "seats" / "seating" → NOT "seats" unless explicitly asking for seating
    - "tables" (as in "price tables") → NOT "tables" (furniture) unless asking for furniture
    - "frames" / "framing" → NOT "frames" (photo frames) unless explicitly asking for frames
    - "pieces" → NOT a product category, it's a quantity reference
    - "looks" → NOT "looks" (curated looks), it's a verb
    - "style" → NOT a product, it's a design preference
    - "touch" → NOT a product
    - "feel" → NOT a product
    - "vibe" → NOT a product

    CORRECT INTERPRETATION EXAMPLES:
    - "whatever matches the room" → STYLE PREFERENCE (keep same category, match room colors)
    - "something that covers the wall" → could mean wall art, NOT bed covers
    - "it really stands out" → compliment, NOT asking for stands
    - "the whole room lights up" → description, NOT asking for lights
    - "that really works" → approval, NOT asking for artwork
    - "these go well together" → styling comment, NOT new search
    - "I love how it sets the mood" → appreciation, NOT asking for sets
    - "that draws the eye" → design comment, NOT asking for drawers
    - "nice touch" → compliment, NOT a product search

    RULE: If user previously asked for a SPECIFIC product (planters, sofas, tables, etc.) and their follow-up message contains only style/preference language without a NEW product noun, KEEP the previous product category.

## CONVERSATION CONTEXT UNDERSTANDING (CRITICAL)

When the user sends follow-up messages, apply previous search context:

### CARRY FORWARD CONTEXT:
- If user previously asked for "study tables" and now asks for "products under ₹5000", search for "study tables under ₹5000"
- If user asked for "modern sofas" and says "show me blue ones", search for "modern blue sofas"
- If user said "living room furniture" then "show me cheaper ones", keep living room context with lower price

### IMPLICIT REFERENCES - Recognize patterns:
- "show me cheaper ones" = same category, lower price
- "what about in red?" = same category, red color
- "any between ₹X and ₹Y?" = same category, new price range
- "more options" = same filters, different products
- "under ₹X" = same category, new max price

### AUTO-CLEAR ON CATEGORY CHANGE:
When user explicitly asks for a DIFFERENT furniture type/category, CLEAR all previous filters:
- "Now show me dining tables" = NEW category, clear price/style/color filters
- "I want beds instead" = NEW category, start fresh
- "Show me coffee tables" (after searching sofas) = NEW category, clear all

### EXPLICIT CLEAR SIGNALS:
- "Start over", "Start fresh", "New search", "Clear filters" = CLEAR ALL accumulated filters

### CONTEXT INHERITANCE IN RESPONSE:
When you detect a follow-up query, ALWAYS include the FULL accumulated context in your product_matching_criteria, not just what the user mentioned in the current message.

Example:
- Previous: User asked for "sofas"
- Current: User says "under ₹50000"
- Your product_matching_criteria MUST include: product_types: ["sofa"], price_max: 50000

## Tone Requirements

- Use design authority and professional expertise
- Justify choices with design principles (not "this looks nice" but "this creates visual balance through...")
- Be warm but confident
- Avoid generic or overly verbose language
- Focus on visual coherence and harmony
- Re-evaluate holistically when preferences change (don't stack recommendations)

## Conversation State Machine Details

Track and return the `conversation_state` in your JSON response.

REMINDER: See the CRITICAL rules at the top of this prompt. During GATHERING states, respond with ONLY acknowledgment + question. NO furniture, colors, or design advice.

### Conversation States:
1. **INITIAL** → User just started or uploaded room image
2. **GATHERING_USAGE** → Ask about room usage/function
3. **GATHERING_STYLE** → Ask about style preferences
4. **GATHERING_BUDGET** → Ask about budget
5. **READY_TO_RECOMMEND** → All info gathered, NOW you can give design recommendations
6. **BROWSING** → User is browsing products (follow-up questions)

### State Transitions:

**INITIAL → GATHERING_USAGE:**
- Set conversation_state = "GATHERING_USAGE"
- user_friendly_response: ONLY "That's a lovely space! How do you primarily use this room - relaxing, entertaining, or work?"
- NO furniture suggestions, NO design advice

**GATHERING_USAGE → GATHERING_STYLE:**
- Set conversation_state = "GATHERING_STYLE"
- user_friendly_response: ONLY "Great! What style vibe are you going for - modern, cozy, or eclectic?"
- NO furniture suggestions, NO design advice

**GATHERING_STYLE → GATHERING_BUDGET:**
- Set conversation_state = "GATHERING_BUDGET"
- user_friendly_response: ONLY "Love it! What's your overall budget for furnishing this space?"
- NO furniture suggestions, NO design advice

**GATHERING_BUDGET → READY_TO_RECOMMEND:**
- Set conversation_state = "READY_TO_RECOMMEND"
- NOW you can give full design recommendations with furniture, colors, and styling tips
- Set total_budget, selected_categories, products_by_category

### IMPORTANT Rules:
1. **ALWAYS check if you already have info before asking** - If user already mentioned style, skip to budget
2. **Parse embedded info** - "I want a modern sofa under 50k" contains style AND budget → go directly to READY_TO_RECOMMEND
3. **Keep GATHERING responses to 1-2 SHORT sentences MAX** - Just acknowledgment + question
4. **Only ask ONE question at a time**
5. **Design advice ONLY in READY_TO_RECOMMEND state**

### JSON Fields for Conversation Flow:
```json
{
  "conversation_state": "GATHERING_USAGE|GATHERING_STYLE|GATHERING_BUDGET|READY_TO_RECOMMEND|BROWSING",
  "follow_up_question": "Your next question (null when READY_TO_RECOMMEND)",
  "total_budget": 50000,
  "selected_categories": [...],
  "user_friendly_response": "ONLY brief acknowledgment + question during GATHERING. Full design advice ONLY in READY_TO_RECOMMEND."
}
```

### Example Conversation (CORRECT):
Turn 1: User: "I have a living room that needs furniture"
→ user_friendly_response: "Beautiful space! How do you typically use this room - for relaxing, entertaining, or working from home?"
→ (NO mention of sofas, colors, rugs, or any design elements)

Turn 2: User: "mainly for watching TV and relaxing"
→ user_friendly_response: "Perfect! What style are you drawn to - modern, traditional, cozy, or eclectic?"
→ (NO mention of sofas, colors, rugs, or any design elements)

Turn 3: User: "modern but warm"
→ user_friendly_response: "Great choice! What's your overall budget for furnishing this space?"
→ (NO mention of sofas, colors, rugs, or any design elements)

Turn 4: User: "around 75000"
→ conversation_state: "READY_TO_RECOMMEND"
→ NOW give full design recommendations with sofas, tables, rugs, colors, etc.

## Category Selection (for READY_TO_RECOMMEND state)
Based on room type and conversation, select 6-10 relevant categories:

**Room-Specific Categories (pick 4-6 based on room type):**
- Living Room: sofas, coffee_tables, side_tables, floor_lamps, accent_chairs, table_lamps
- Bedroom: beds, nightstands, table_lamps, floor_lamps, dressers, wardrobes
- Dining Room: dining_tables, dining_chairs, pendant_lamps, sideboards, buffets
- Office: desks, office_chairs, bookshelves, table_lamps, storage_cabinets
- Study: study_tables, study_chairs, desks, office_chairs, bookshelves, table_lamps

**⛔ MANDATORY Generic Categories (MUST ALWAYS INCLUDE ALL 4 for EVERY room type):**
- planters (plants add life to any room)
- wall_art (artwork completes a space)
- decor (decorative objects add personality)
- rugs (define areas and add warmth)

These 4 generic categories MUST be included in EVERY selected_categories response, regardless of room type!

### Budget Allocation (CRITICAL)
When the user provides a total budget, you MUST include budget_allocation for EACH category.

**RULE: Sum of all "max" values MUST EQUAL exactly 100% of the total budget.**

Distribution guidelines:
- Primary furniture (sofa, bed, dining table): 40-50% of budget
- Secondary furniture (tables, chairs): 20-30%
- Lighting: 10-15%
- Decor & accessories (planters, wall_art, decor, rugs): 10-15%

### selected_categories Example (for READY_TO_RECOMMEND with ₹100,000 total budget):
```json
"selected_categories": [
  {"category_id": "sofas", "display_name": "Sofas", "budget_allocation": {"min": 20000, "max": 40000}, "priority": 1},
  {"category_id": "coffee_tables", "display_name": "Coffee Tables", "budget_allocation": {"min": 5000, "max": 12000}, "priority": 2},
  {"category_id": "floor_lamps", "display_name": "Floor Lamps", "budget_allocation": {"min": 3000, "max": 8000}, "priority": 3},
  {"category_id": "accent_chairs", "display_name": "Accent Chairs", "budget_allocation": {"min": 7500, "max": 15000}, "priority": 4},
  {"category_id": "planters", "display_name": "Planters", "budget_allocation": {"min": 1000, "max": 5000}, "priority": 5},
  {"category_id": "wall_art", "display_name": "Wall Art", "budget_allocation": {"min": 2000, "max": 7000}, "priority": 6},
  {"category_id": "decor", "display_name": "Decor", "budget_allocation": {"min": 1500, "max": 5000}, "priority": 7},
  {"category_id": "rugs", "display_name": "Rugs", "budget_allocation": {"min": 4000, "max": 8000}, "priority": 8}
]
```
**Verification: 40000 + 12000 + 8000 + 15000 + 5000 + 7000 + 5000 + 8000 = ₹100,000** ✓

Note: Backend code will validate and adjust allocations to ensure they sum to exactly the user's total budget."""

            return system_prompt

        except FileNotFoundError:
            logger.error("prompt.md file not found, using fallback prompt")
            return "You are an expert interior designer. Help users with their interior design needs."

    def _load_fast_system_prompt(self) -> str:
        """Load a condensed system prompt for fast text-only follow-ups (no image analysis)"""
        return """You are a friendly, warm AI interior stylist. Respond in JSON format.

## YOUR PERSONALITY
- Warm, enthusiastic, and encouraging
- Use friendly acknowledgments like "Perfect!", "Love that!", "Great choice!", "Sounds amazing!"
- Keep energy positive and supportive

## CONVERSATION FLOW (CRITICAL)
Each response during gathering should be:
1. A brief 3-5 word friendly acknowledgment (e.g., "Perfect!", "Great choice!", "Love it!")
2. Followed by ONE short, friendly question

Examples:
- GATHERING_USAGE: "Love it! How do you usually use this space - relaxing, working, or entertaining?"
- GATHERING_STYLE: "Perfect! What vibe are you going for - modern and sleek, cozy and warm, or eclectic?"
- GATHERING_BUDGET: "Great choice! What's your budget for this transformation?"
- READY_TO_RECOMMEND: NOW give full design recommendations with enthusiasm

## RESPONSE FORMAT (JSON)
{
  "user_friendly_response": "Friendly acknowledgment + question",
  "conversation_state": "GATHERING_USAGE|GATHERING_STYLE|GATHERING_BUDGET|READY_TO_RECOMMEND",
  "follow_up_question": "Friendly question (null if READY_TO_RECOMMEND)",
  "total_budget": null,
  "design_analysis": {"style_preferences": {"primary_style": "modern"}},
  "product_matching_criteria": {"product_types": [], "categories": [], "search_terms": []},
  "selected_categories": [],
  "confidence_scores": {"overall_analysis": 85}
}

## RULES
1. During GATHERING states: Friendly acknowledgment + ONE question. NO furniture/color suggestions yet.
2. Parse embedded info: "modern sofa under 50k" → skip to READY_TO_RECOMMEND
3. Keep responses SHORT but WARM (1-2 sentences during gathering)
4. Always sound excited to help!
5. **SEMANTIC UNDERSTANDING**: "no", "nope", "none", "anything", "whatever" = NO PREFERENCE (don't use as search keywords!)

## COMPOUND FURNITURE TERMS (CRITICAL - DO NOT SPLIT!)
- "bedside tables" → product_types: ["bedside table"], search_terms: ["bedside table", "nightstand"] (NOT ["table", "bed", "nightstand"])
- "coffee tables" → product_types: ["coffee table"] (NOT ["coffee", "table"])
- "dining chairs" → product_types: ["dining chair"] (NOT ["dining", "chair"])
- Keep compound terms together! Never decompose into individual words!

## CONVERSATION CONTEXT (CRITICAL)
6. **CARRY FORWARD**: If user asked for "sofas" then says "under ₹50000" → search for "sofas under ₹50000"
7. **IMPLICIT REFERENCES**: "cheaper ones", "in blue", "under ₹X" = same category with new filter
8. **AUTO-CLEAR ON CATEGORY CHANGE**: "show me tables" (after sofas) = NEW category, clear price/style filters
9. **INCLUDE FULL CONTEXT**: Your product_matching_criteria MUST include accumulated context, not just current message"""

    async def analyze_user_input(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        image_data: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[str, Optional[DesignAnalysisSchema]]:
        """
        Analyze user input and return both a conversational response and structured analysis

        Args:
            user_message: The user's message
            session_id: Session ID for conversation context
            image_data: Base64 encoded image data (optional)
            user_id: User ID for preference tracking

        Returns:
            Tuple of (conversational_response, design_analysis)
        """
        # Determine if we should use fast mode (no image = text-only follow-up)
        use_fast_mode = image_data is None
        mode_str = "FAST" if use_fast_mode else "FULL"
        print(f"[DEBUG] analyze_user_input [{mode_str}] - message: {user_message[:50]}, session_id: {session_id}")

        try:
            # Get or create conversation context
            if session_id:
                context = self.context_manager.get_or_create_context(session_id, user_id)
                # Add user message to context (text only, not image - to reduce context size)
                self.context_manager.add_message(session_id, "user", user_message, {"has_image": image_data is not None})

                # Get enhanced context for AI (text-only history)
                messages = self.context_manager.get_context_for_ai(session_id)

                # For fast mode, use condensed system prompt
                if use_fast_mode and messages and messages[0]["role"] == "system":
                    messages[0]["content"] = self.system_prompt_fast

                # Inject accumulated search context summary if available
                context_summary = self.context_manager.get_search_context_summary(session_id)
                if context_summary:
                    # Insert context summary after system prompt
                    messages.insert(1, {"role": "system", "content": context_summary})
                    logger.info(f"Injected context summary for session {session_id}")
            else:
                # Fallback to basic system prompt
                system_prompt = self.system_prompt_fast if use_fast_mode else self.system_prompt
                messages = [{"role": "system", "content": system_prompt}]

            # Prepare CURRENT user message content with image
            # IMPORTANT: Only include image in the CURRENT message, not in conversation history
            # to avoid exceeding OpenAI's context limits
            user_content = [{"type": "text", "text": user_message}]

            # Add image if provided (only for current message)
            if image_data:
                processed_image = self._process_image(image_data)
                if processed_image:
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{processed_image}", "detail": "high"},
                        }
                    )

            # Replace the last message with the current message including image
            # Remove the text-only version added by context manager and add the version with image
            if messages and messages[-1]["role"] == "user" and messages[-1]["content"] == user_message:
                messages[-1]["content"] = user_content
            else:
                messages.append({"role": "user", "content": user_content})

            # Call ChatGPT (use fast mode for text-only)
            print(f"[DEBUG] About to call _call_chatgpt [{mode_str}] with {len(messages)} messages")
            response = await self._call_chatgpt(messages, use_fast_mode=use_fast_mode)
            print(f"[DEBUG] _call_chatgpt returned, response length: {len(response) if response else 0}")

            # Parse response
            print(f"[DEBUG] About to parse response")
            conversational_response, analysis = self._parse_response(response)
            print(f"[DEBUG] Parse complete - analysis is None: {analysis is None}")

            # Store conversation context
            if session_id:
                # Add assistant response to context
                self.context_manager.add_message(
                    session_id, "assistant", conversational_response, {"has_analysis": analysis is not None}
                )

                # Store design analysis in context
                if analysis:
                    self.context_manager.add_design_analysis(
                        session_id, analysis.dict() if hasattr(analysis, "dict") else analysis
                    )

                    # Extract filters from AI response and update accumulated filters
                    self._update_accumulated_filters_from_analysis(session_id, analysis, user_message)

                # Legacy context storage for backward compatibility
                if session_id not in self.conversation_memory:
                    self.conversation_memory[session_id] = []

                self.conversation_memory[session_id].extend(
                    [{"role": "user", "content": user_message}, {"role": "assistant", "content": conversational_response}]
                )

                if len(self.conversation_memory[session_id]) > 10:
                    self.conversation_memory[session_id] = self.conversation_memory[session_id][-10:]

            return conversational_response, analysis

        except Exception as e:
            print(f"[DEBUG] EXCEPTION in analyze_user_input: {type(e).__name__}: {str(e)}")
            import traceback

            traceback.print_exc()
            logger.error(f"Error in ChatGPT analysis: {e}", exc_info=True)

            # Provide specific error messages based on error type
            error_message = str(e).lower()
            if "connection" in error_message or "timeout" in error_message:
                fallback_response = "I'm having trouble connecting to the OpenAI service right now. Please check your internet connection and try again in a moment."
            elif "image processing not supported" in error_message or "image" in error_message:
                fallback_response = "The image you provided couldn't be processed. Please try uploading a different image format (JPG or PNG) or ensure the image size is under 5MB."
            elif "rate limit" in error_message or "quota" in error_message or "429" in error_message:
                fallback_response = "The OpenAI API has reached its rate limit or quota. Please try again in a few moments."
            elif "authentication" in error_message or "api key" in error_message or "401" in error_message:
                fallback_response = "There's an issue with the OpenAI API authentication. Please contact the administrator to verify the API key configuration."
            else:
                fallback_response = f"I encountered an error while analyzing your request: {type(e).__name__}. Please try rephrasing your interior design needs or contact support if this persists."

            return fallback_response, None

    async def _call_chatgpt(self, messages: List[Dict[str, Any]], use_fast_mode: bool = False) -> str:
        """Call ChatGPT API with the prepared messages with retry logic for empty responses

        Args:
            messages: List of message dictionaries
            use_fast_mode: If True, use gpt-4o-mini with shorter timeout for text-only queries
        """
        mode_str = "FAST" if use_fast_mode else "FULL"
        print(f"[DEBUG] _call_chatgpt started [{mode_str}]")
        # Apply rate limiting
        await self.rate_limiter.acquire()
        print(f"[DEBUG] Rate limit acquired")

        # Update usage stats
        self.api_usage_stats["total_requests"] += 1

        # Demo mode simulation
        if hasattr(self, "demo_mode") and self.demo_mode:
            return await self._simulate_chatgpt_response(messages)

        # Select client and model based on mode
        client = self.client_fast if use_fast_mode else self.client
        model = settings.openai_model_fast if use_fast_mode else settings.openai_model
        max_tokens = settings.openai_max_tokens_fast if use_fast_mode else settings.openai_max_tokens

        # Retry logic - fewer retries in fast mode for speed
        max_retries = 2 if use_fast_mode else 3
        retry_delay = 1.0 if use_fast_mode else 2.0  # seconds

        try:
            for attempt in range(max_retries):
                try:
                    start_time = time.time()
                    print(f"[DEBUG] OpenAI API call [{mode_str}] attempt {attempt + 1}/{max_retries}")
                    print(f"[DEBUG] Using model: {model}, max_tokens: {max_tokens}")
                    if attempt == 0:
                        print(
                            f"[DEBUG] API Key (first 10 chars): {settings.openai_api_key[:10] if settings.openai_api_key else 'None'}"
                        )

                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=settings.openai_temperature,
                        response_format={"type": "json_object"},
                    )
                    print(f"[DEBUG] OpenAI API call [{mode_str}] succeeded!")

                    # Extract response content
                    response_content = response.choices[0].message.content if response.choices else None

                    # Check if response is empty or None (timeout/error case)
                    if not response_content:
                        print(f"[DEBUG] OpenAI returned empty response on attempt {attempt + 1}/{max_retries}")
                        logger.warning(f"OpenAI API returned empty response - attempt {attempt + 1}/{max_retries}")

                        # If this is not the last attempt, retry after delay
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (attempt + 1)  # Incremental backoff: 2s, 4s
                            print(f"[DEBUG] Retrying after {wait_time}s delay...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Last attempt failed - return fallback
                            print(f"[DEBUG] All {max_retries} attempts returned empty response - returning fallback")
                            logger.error(f"OpenAI API returned empty response after {max_retries} attempts")
                            self.api_usage_stats["failed_requests"] += 1
                            return self._get_structured_fallback(
                                messages, error_type="timeout", error_message="API returned empty response after retries"
                            )

                    # If we got valid content, update successful request stats and return
                    self.api_usage_stats["successful_requests"] += 1
                    if hasattr(response, "usage") and response.usage:
                        self.api_usage_stats["total_tokens"] += response.usage.total_tokens

                    response_time = time.time() - start_time
                    logger.info(
                        f"ChatGPT API call [{mode_str}] successful - Model: {model}, Response time: {response_time:.2f}s, "
                        f"Tokens: {response.usage.total_tokens if hasattr(response, 'usage') and response.usage else 'N/A'}"
                    )

                    return response_content

                except openai.APIError as e:
                    print(f"[DEBUG] OpenAI APIError on attempt {attempt + 1}/{max_retries}: {type(e).__name__}: {str(e)}")
                    # On API errors, break out of retry loop and handle in outer exception handlers
                    raise
                except Exception as inner_e:
                    print(
                        f"[DEBUG] Exception on attempt {attempt + 1}/{max_retries}: {type(inner_e).__name__}: {str(inner_e)}"
                    )
                    # On other exceptions, break out of retry loop and handle in outer exception handlers
                    raise

            # If all retries exhausted without success (shouldn't reach here due to returns above)
            logger.error("Retry loop completed without returning - this shouldn't happen")
            self.api_usage_stats["failed_requests"] += 1
            return self._get_structured_fallback(
                messages, error_type="unknown", error_message="Retry logic failed unexpectedly"
            )

        except openai.APIError as e:
            print(f"[DEBUG] OpenAI APIError: {type(e).__name__}: {str(e)}")
            self.api_usage_stats["failed_requests"] += 1
            error_message = str(e)
            logger.error(f"OpenAI API error: {e}")

            # Check if it's a quota error (429) and switch to structured fallback
            if "429" in error_message or "quota" in error_message.lower() or "insufficient_quota" in error_message.lower():
                print(f"[DEBUG] Quota error detected, returning fallback")
                logger.warning("OpenAI quota exceeded - returning structured fallback response")
                return self._get_structured_fallback(messages, error_type="rate_limit")

            # Return structured fallback for other API errors
            return self._get_structured_fallback(messages, error_type="api_error", error_message=error_message)
        except openai.RateLimitError as e:
            print(f"[DEBUG] OpenAI RateLimitError: {str(e)}")
            self.api_usage_stats["failed_requests"] += 1
            logger.warning(f"Rate limit exceeded - returning structured fallback: {e}")
            return self._get_structured_fallback(messages, error_type="rate_limit")
        except openai.AuthenticationError as e:
            print(f"[DEBUG] OpenAI AuthenticationError: {str(e)}")
            self.api_usage_stats["failed_requests"] += 1
            logger.error(f"Authentication failed: {e}")
            return self._get_structured_fallback(messages, error_type="authentication")
        except Exception as e:
            print(f"[DEBUG] Generic exception in _call_chatgpt: {type(e).__name__}: {str(e)}")
            import traceback

            traceback.print_exc()
            self.api_usage_stats["failed_requests"] += 1
            logger.error(f"ChatGPT API call failed: {e}", exc_info=True)

            # Categorize the error
            error_message = str(e).lower()
            if "connection" in error_message or "timeout" in error_message:
                error_type = "connection"
            elif "image" in error_message:
                error_type = "image_processing"
            else:
                error_type = "unknown"

            # Return a structured fallback response for any other errors
            return self._get_structured_fallback(messages, error_type=error_type, error_message=str(e))

    async def analyze_image_with_vision(self, image_url: str, prompt: str) -> Optional[str]:
        """
        Analyze image using ChatGPT Vision (GPT-4V)

        Args:
            image_url: URL to image
            prompt: Analysis instructions

        Returns: Vision analysis result
        """
        try:
            logger.info(f"ChatGPT Vision: Analyzing image from {image_url[:100]}...")

            # Apply rate limiting
            await self.rate_limiter.acquire()

            # Demo mode simulation
            if hasattr(self, "demo_mode") and self.demo_mode:
                logger.info("Demo mode: Simulating Vision analysis")
                return "A modern furniture piece with clean lines and neutral tones"

            # Create vision message
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
                    ],
                }
            ]

            # Call OpenAI Vision API (use gpt-4o for vision - gpt-4-vision-preview was deprecated)
            response = await self.client.chat.completions.create(
                model="gpt-4o", messages=messages, max_tokens=500, temperature=0.3
            )

            # Extract response content
            response_content = response.choices[0].message.content if response.choices else None

            if response_content:
                logger.info(f"ChatGPT Vision analysis successful: {response_content[:100]}...")
                self.api_usage_stats["successful_requests"] += 1
                if hasattr(response, "usage") and response.usage:
                    self.api_usage_stats["total_tokens"] += response.usage.total_tokens
                return response_content

            logger.warning("ChatGPT Vision returned empty response")
            self.api_usage_stats["failed_requests"] += 1
            return None

        except Exception as e:
            logger.error(f"ChatGPT Vision analysis failed: {e}", exc_info=True)
            self.api_usage_stats["failed_requests"] += 1
            return None

    def _get_structured_fallback(
        self, messages: List[Dict[str, Any]], error_type: str = "unknown", error_message: str = ""
    ) -> str:
        """Get structured fallback response when API fails"""
        print(f"[DEBUG] _get_structured_fallback called with error_type: {error_type}")
        # Extract user message for contextual response
        user_message = ""
        has_image = False
        for msg in messages:
            if msg.get("role") == "user":
                if isinstance(msg.get("content"), list):
                    for part in msg["content"]:
                        if part.get("type") == "text":
                            user_message = part.get("text", "")
                        elif part.get("type") == "image_url":
                            has_image = True
                else:
                    user_message = msg.get("content", "")

        fallback = {
            "design_analysis": {
                "style_preferences": {
                    "primary_style": "modern",
                    "secondary_styles": [],
                    "style_keywords": ["clean", "simple"],
                    "inspiration_sources": [],
                },
                "color_scheme": {
                    "preferred_colors": ["neutral"],
                    "accent_colors": [],
                    "color_temperature": "neutral",
                    "color_intensity": "balanced",
                },
                "space_analysis": {
                    "room_type": "unknown",
                    "dimensions": "unknown",
                    "layout_type": "unknown",
                    "lighting_conditions": "mixed",
                    "existing_elements": [],
                    "traffic_patterns": "unknown",
                },
                "functional_requirements": {
                    "primary_functions": ["living"],
                    "storage_needs": "moderate",
                    "seating_capacity": "2-4",
                    "special_considerations": [],
                },
                "budget_indicators": {"price_range": "mid-range", "investment_priorities": []},
            },
            "product_matching_criteria": {
                "furniture_categories": {
                    "seating": {
                        "types": ["sofa"],
                        "materials": ["fabric"],
                        "colors": ["neutral"],
                        "size_requirements": "medium",
                    },
                    "tables": {
                        "types": ["coffee"],
                        "materials": ["wood"],
                        "shapes": ["rectangular"],
                        "size_requirements": "medium",
                    },
                    "storage": {"types": ["bookshelf"], "materials": ["wood"], "configurations": ["vertical"]},
                    "lighting": {"types": ["table"], "styles": ["modern"], "placement": ["side"]},
                    "decor": {"categories": ["art"], "materials": ["canvas"], "themes": ["abstract"]},
                },
                "filtering_keywords": {
                    "include_terms": ["modern", "contemporary"],
                    "exclude_terms": ["ornate", "traditional"],
                    "material_preferences": ["wood", "metal"],
                    "style_tags": ["modern", "minimalist"],
                },
            },
            "visualization_guidance": {
                "layout_recommendations": {
                    "furniture_placement": "Create conversational groupings",
                    "focal_points": ["main seating area"],
                    "traffic_flow": "Maintain clear pathways",
                },
                "spatial_considerations": {
                    "scale_proportions": "Choose appropriately sized furniture",
                    "height_variations": "Mix heights for visual interest",
                    "negative_space": "Leave breathing room between pieces",
                },
                "styling_suggestions": {
                    "layering_approach": "Layer textures and materials",
                    "texture_mixing": "Combine smooth and textured surfaces",
                    "pattern_coordination": "Use patterns sparingly",
                },
            },
            "confidence_scores": {
                "style_identification": 50,
                "space_understanding": 30,
                "product_matching": 40,
                "overall_analysis": 40,
            },
            "recommendations": {
                "priority_items": ["seating", "lighting"],
                "alternative_options": ["different styles available"],
                "phased_approach": ["start with essentials"],
            },
            "user_friendly_response": self._build_fallback_message(user_message, has_image, error_type, error_message),
        }
        return json.dumps(fallback)

    def _build_fallback_message(
        self, user_message: str, has_image: bool, error_type: str = "unknown", error_message: str = ""
    ) -> str:
        """Build fallback message for API failures"""
        # Provide specific error messages based on error type
        if error_type == "connection":
            return "I'm having trouble connecting to the OpenAI service right now. Please check your internet connection and try again in a moment. In the meantime, I'll show you some product recommendations."
        elif error_type == "image_processing":
            return "The image you provided couldn't be processed by the AI service. Please try uploading a different image format (JPG or PNG) or ensure the image size is under 5MB. I'll still show you some product recommendations based on your request."
        elif error_type == "rate_limit":
            return "The OpenAI API has reached its rate limit. Please try again in a few moments. I'll show you some product recommendations in the meantime."
        elif error_type == "authentication":
            return "There's an issue with the OpenAI API authentication. Please contact the administrator to verify the API key configuration. I'll show you some product recommendations for now."
        elif error_type == "timeout":
            return "The AI analysis is taking longer than expected. I'll show you some product recommendations while the system processes your request. You can try your request again in a moment."
        elif error_type == "api_error":
            return "I'm currently experiencing high demand. I'll show you some product recommendations based on your preferences while the system catches up."
        else:
            # Generic fallback with more helpful context
            action = "transform your space" if has_image else "find the perfect pieces"
            user_request_part = f'Based on your request for "{user_message[:100]}", ' if user_message else ""
            return f"Thank you for your request! {user_request_part}I'll show you some beautiful design options and product recommendations that match your style. Let's create something amazing together!"

    def _parse_response(self, response: str) -> Tuple[str, Optional[DesignAnalysisSchema]]:
        """Parse ChatGPT response into conversational text and structured analysis"""
        print(f"[DEBUG] _parse_response called with response length: {len(response) if response else 0}")
        print(f"[DEBUG] Response preview: {response[:200] if response else 'None'}")
        try:
            # Parse JSON response
            response_data = json.loads(response)
            print(f"[DEBUG] JSON parsed successfully, keys: {list(response_data.keys())}")

            # Extract user-friendly response - check all possible key names
            conversational_response = (
                response_data.get("user_friendly_response")
                or response_data.get("user_friendly_message")
                or response_data.get("message")  # OpenAI might return this key
                or response_data.get("user_message")
                or "I've analyzed your request and found some great recommendations for you!"  # ChatGPT sometimes returns this key
            )
            print(f"[DEBUG] Extracted conversational_response: {conversational_response[:100]}")

            # Normalize the response data to match schema
            # Handle camelCase to snake_case conversion for key fields
            camel_to_snake_mappings = {
                "designAnalysis": "design_analysis",
                "productMatchingCriteria": "product_matching_criteria",
                "visualizationMode": "visualization_mode",
                "visualizationGuidance": "visualization_guidance",
                "confidenceScores": "confidence_scores",
                "userFriendlyResponse": "user_friendly_response",
                "designSummary": "design_summary",
                "layoutGuidance": "layout_guidance",
                "colorPalette": "color_palette",
                "stylingTips": "styling_tips",
            }
            for camel, snake in camel_to_snake_mappings.items():
                if camel in response_data and snake not in response_data:
                    response_data[snake] = response_data[camel]

            # If OpenAI returns 'message', 'user_friendly_message', or 'user_message', map it to 'user_friendly_response'
            if "message" in response_data and "user_friendly_response" not in response_data:
                response_data["user_friendly_response"] = response_data["message"]
            if "user_friendly_message" in response_data and "user_friendly_response" not in response_data:
                response_data["user_friendly_response"] = response_data["user_friendly_message"]
            if "user_message" in response_data and "user_friendly_response" not in response_data:
                response_data["user_friendly_response"] = response_data["user_message"]

            # Ensure all optional fields have defaults
            response_data.setdefault("design_analysis", {})
            response_data.setdefault("product_matching_criteria", {})
            response_data.setdefault("visualization_mode", {})
            response_data.setdefault("visualization_guidance", {})
            response_data.setdefault("confidence_scores", {})

            # Handle recommendations - ChatGPT might return it as a list of products
            # but the schema expects a dict. Store the product list separately.
            if "recommendations" in response_data:
                if isinstance(response_data["recommendations"], list):
                    # Store the list for later extraction, but set recommendations to {} for schema
                    response_data["_product_list"] = response_data["recommendations"]
                    response_data["recommendations"] = {}
            else:
                response_data.setdefault("recommendations", {})

            # Ensure new professional designer fields have defaults
            response_data.setdefault("design_summary", None)
            response_data.setdefault("layout_guidance", None)
            response_data.setdefault("color_palette", None)
            response_data.setdefault("styling_tips", None)

            print(f"[DEBUG] Normalized response_data keys: {list(response_data.keys())}")

            # Create design analysis schema
            analysis = DesignAnalysisSchema(**response_data)
            print(f"[DEBUG] DesignAnalysisSchema created successfully")

            return conversational_response, analysis

        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSONDecodeError in _parse_response: {str(e)}")
            logger.error(f"Failed to parse ChatGPT JSON response: {e}")
            return response, None

        except Exception as e:
            print(f"[DEBUG] Exception in _parse_response: {type(e).__name__}: {str(e)}")
            import traceback

            traceback.print_exc()
            logger.error(f"Error parsing ChatGPT response: {e}", exc_info=True)
            return "I've analyzed your request and can help you find the perfect pieces for your space.", None

    def _process_image(self, image_data: str) -> Optional[str]:
        """Process and validate uploaded image"""
        try:
            # Remove data URL prefix if present
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]

            # Decode base64
            image_bytes = base64.b64decode(image_data)

            # Open and validate image
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Resize if too large (max 800x800 to reduce token usage)
            # Smaller images = faster processing and lower risk of context limits
            max_size = 800
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Convert back to base64
            # Use lower quality to reduce token usage (70 is still good quality)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=70)
            return base64.b64encode(buffer.getvalue()).decode()

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None

    def _update_accumulated_filters_from_analysis(self, session_id: str, analysis: Any, user_message: str) -> None:
        """
        Extract filters from AI analysis and update accumulated filters.
        Handles auto-clear on category change and merging logic.
        """
        try:
            # Check for explicit clear signals in user message
            clear_signals = ["start over", "start fresh", "new search", "clear filters", "reset"]
            user_message_lower = user_message.lower()
            if any(signal in user_message_lower for signal in clear_signals):
                self.context_manager.clear_accumulated_filters(session_id)
                logger.info(f"Cleared accumulated filters due to clear signal in message")
                return

            # Extract filters from analysis
            analysis_dict = analysis.dict() if hasattr(analysis, "dict") else analysis
            product_criteria = analysis_dict.get("product_matching_criteria", {})

            # Build new filters from analysis
            new_filters = {}

            # Extract product types and categories
            product_types = product_criteria.get("product_types", [])
            categories = product_criteria.get("categories", [])
            search_terms = product_criteria.get("search_terms", [])

            if product_types:
                new_filters["product_types"] = product_types
                # Use first product type as category if no explicit category
                new_filters["category"] = product_types[0] if product_types else None

            if categories:
                new_filters["furniture_type"] = categories[0] if categories else None

            if search_terms:
                new_filters["search_terms"] = search_terms

            # Extract budget/price from design_analysis
            design_analysis = analysis_dict.get("design_analysis", {})
            budget_indicators = design_analysis.get("budget_indicators", {})

            # Check if explicit price range is mentioned
            if "price_range" in budget_indicators:
                price_range = budget_indicators.get("price_range")
                # Map descriptive ranges to numeric if needed
                if isinstance(price_range, str):
                    if "budget" in price_range.lower():
                        new_filters["price_max"] = 10000
                    elif "luxury" in price_range.lower():
                        new_filters["price_min"] = 50000

            # Extract style from analysis
            style_prefs = design_analysis.get("style_preferences", {})
            if style_prefs.get("primary_style"):
                new_filters["style"] = style_prefs.get("primary_style")

            # Extract color preference
            color_scheme = design_analysis.get("color_scheme", {})
            preferred_colors = color_scheme.get("preferred_colors", [])
            if preferred_colors:
                new_filters["color"] = preferred_colors[0]

            # Extract room type
            space_analysis = design_analysis.get("space_analysis", {})
            if space_analysis.get("room_type"):
                new_filters["room_type"] = space_analysis.get("room_type")

            # Determine if category changed (auto-clear behavior)
            current_filters = self.context_manager.get_accumulated_filters(session_id)
            old_category = current_filters.get("category")
            new_category = new_filters.get("category")

            category_changed = new_category is not None and old_category is not None and new_category != old_category

            # Update accumulated filters
            if new_filters:
                self.context_manager.update_accumulated_filters(session_id, new_filters, category_changed=category_changed)
                logger.info(f"Updated accumulated filters from analysis: {new_filters}")

        except Exception as e:
            logger.warning(f"Error updating accumulated filters from analysis: {e}")

    def get_conversation_context(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation context for a session (legacy method)"""
        return self.conversation_memory.get(session_id, [])

    def clear_conversation_context(self, session_id: str):
        """Clear conversation context for a session"""
        # Clear from both legacy and new context managers
        if session_id in self.conversation_memory:
            del self.conversation_memory[session_id]
        self.context_manager.clear_context(session_id)

    def get_enhanced_conversation_context(self, session_id: str) -> Dict[str, Any]:
        """Get enhanced conversation context with analysis"""
        return self.context_manager.get_conversation_summary(session_id)

    def get_user_preferences(self, session_id: str) -> Dict[str, Any]:
        """Get user preferences extracted from conversation"""
        return self.context_manager.get_user_preferences_summary(session_id)

    def update_room_context(self, session_id: str, room_data: Dict[str, Any]) -> bool:
        """Update room context for spatial analysis"""
        try:
            self.context_manager.update_room_context(session_id, room_data)
            return True
        except Exception as e:
            logger.error(f"Error updating room context: {e}")
            return False

    def export_conversation_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export complete conversation data for persistence"""
        try:
            return self.context_manager.export_context(session_id)
        except Exception as e:
            logger.error(f"Error exporting conversation data: {e}")
            return None

    def import_conversation_data(self, context_data: Dict[str, Any]) -> bool:
        """Import conversation data from persistence"""
        try:
            return self.context_manager.import_context(context_data)
        except Exception as e:
            logger.error(f"Error importing conversation data: {e}")
            return False

    async def _simulate_chatgpt_response(self, messages: List[Dict[str, Any]]) -> str:
        """Simulate ChatGPT response for demo mode"""
        await asyncio.sleep(0.5)  # Simulate API delay

        # Update success stats for demo
        self.api_usage_stats["successful_requests"] += 1
        self.api_usage_stats["total_tokens"] += 1500

        # Extract conversation context and user message
        user_message = ""
        conversation_history = []
        has_image = False

        for msg in messages:
            if msg.get("role") == "user":
                if isinstance(msg.get("content"), list):
                    for part in msg["content"]:
                        if part.get("type") == "text":
                            user_message = part.get("text", "")
                            conversation_history.append(f"User: {user_message}")
                        elif part.get("type") == "image_url":
                            has_image = True
                else:
                    user_message = msg.get("content", "")
                    conversation_history.append(f"User: {user_message}")
            elif msg.get("role") == "assistant":
                assistant_msg = msg.get("content", "")
                conversation_history.append(f"Assistant: {assistant_msg[:100]}...")

        # Generate contextual response based on conversation history
        context_summary = "\n".join(conversation_history[-6:])  # Last 3 exchanges

        # Generate realistic demo response
        demo_response = {
            "design_analysis": {
                "style_preferences": {
                    "primary_style": "modern",
                    "secondary_styles": ["scandinavian", "minimalist"],
                    "style_keywords": ["clean", "simple", "functional", "light"],
                    "inspiration_sources": ["Nordic design", "Japanese minimalism"],
                },
                "color_scheme": {
                    "preferred_colors": ["white", "light gray", "natural wood"],
                    "accent_colors": ["soft blue", "sage green"],
                    "color_temperature": "cool",
                    "color_intensity": "muted",
                },
                "space_analysis": {
                    "room_type": "living_room",
                    "dimensions": "estimated 12x15 feet",
                    "layout_type": "open",
                    "lighting_conditions": "natural",
                    "existing_elements": ["large windows", "hardwood floors"],
                    "traffic_patterns": "main entrance to seating area",
                },
                "functional_requirements": {
                    "primary_functions": ["relaxation", "entertainment", "socializing"],
                    "storage_needs": "moderate",
                    "seating_capacity": "4-6 people",
                    "special_considerations": ["pet-friendly materials"],
                },
                "budget_indicators": {
                    "price_range": "mid-range",
                    "investment_priorities": ["quality seating", "good lighting"],
                },
            },
            "product_matching_criteria": {
                "furniture_categories": {
                    "seating": {
                        "types": ["sectional sofa", "accent chairs"],
                        "materials": ["linen", "wool", "leather"],
                        "colors": ["light gray", "cream", "natural"],
                        "size_requirements": "medium to large",
                    },
                    "tables": {
                        "types": ["coffee table", "side tables"],
                        "materials": ["wood", "glass", "metal"],
                        "shapes": ["rectangular", "round"],
                        "size_requirements": "proportional to seating",
                    },
                    "lighting": {
                        "types": ["floor lamps", "table lamps", "pendant lights"],
                        "styles": ["modern", "scandinavian"],
                        "placement": ["reading areas", "ambient lighting"],
                    },
                },
                "filtering_keywords": {
                    "include_terms": ["modern", "scandinavian", "minimalist", "functional"],
                    "exclude_terms": ["ornate", "traditional", "heavy"],
                    "material_preferences": ["natural wood", "linen", "cotton"],
                    "style_tags": ["clean lines", "simple", "light"],
                },
            },
            "visualization_guidance": {
                "layout_recommendations": {
                    "furniture_placement": "create conversation area facing natural light",
                    "focal_points": ["large windows", "main seating area"],
                    "traffic_flow": "maintain clear pathways around furniture",
                },
                "spatial_considerations": {
                    "scale_proportions": "choose furniture proportional to room size",
                    "height_variations": "mix heights with floor and table lamps",
                    "negative_space": "leave breathing room between pieces",
                },
                "styling_suggestions": {
                    "layering_approach": "layer textures with throws and pillows",
                    "texture_mixing": "combine smooth and natural textures",
                    "pattern_coordination": "use subtle patterns sparingly",
                },
            },
            "confidence_scores": {
                "style_identification": 88,
                "space_understanding": 85,
                "product_matching": 90,
                "overall_analysis": 87,
            },
            "recommendations": {
                "priority_items": ["comfortable sectional sofa", "good task lighting", "coffee table"],
                "alternative_options": ["modular seating", "ottoman for extra seating"],
                "phased_approach": ["start with seating", "add lighting", "finish with accessories"],
            },
            "user_friendly_response": self._generate_contextual_response(user_message, conversation_history, has_image),
        }

        return json.dumps(demo_response)

    def _generate_contextual_response(self, user_message: str, conversation_history: List[str], has_image: bool) -> str:
        """Generate contextual conversational response based on conversation history"""

        # Count interactions
        interaction_count = len([msg for msg in conversation_history if msg.startswith("User:")])

        # First interaction
        if interaction_count <= 1:
            if has_image:
                return f"Thank you for sharing that image! I can see you're looking to redesign this space. Based on '{user_message}', I'd recommend creating a modern, comfortable environment. I've found some great furniture options that would work perfectly. Would you like me to focus on any specific area or type of furniture?"
            else:
                return f"Thanks for sharing your vision! You mentioned '{user_message}'. I love helping create beautiful, functional spaces. Let me suggest some modern pieces that would work wonderfully - comfortable seating in natural materials, clean-lined furniture, and great lighting. What's most important to you in this space?"

        # Follow-up interactions - be more specific and conversational
        elif interaction_count == 2:
            return f"Great question! Regarding '{user_message}' - I think that's a smart direction. Let me build on what we discussed earlier. I've identified some pieces that match your style preferences. Should I show you options for specific categories like seating, tables, or lighting?"

        elif interaction_count == 3:
            return f"Perfect! I'm really excited about the direction we're heading. For '{user_message}', I recommend coordinating pieces that maintain that cohesive look we've been building. Would you like to see how these pieces would look arranged in your space?"

        else:
            # Ongoing conversation - reference previous context
            return f"Absolutely! Building on our conversation, '{user_message}' fits perfectly with the aesthetic we've been developing. I can show you complementary pieces that will complete the look. Should we focus on finalizing your selections or exploring more options?"

    async def analyze_design_preferences(self, text: str) -> Dict[str, Any]:
        """Analyze design preferences using advanced NLP"""
        try:
            # Use NLP processor for detailed analysis
            style_extraction = await design_nlp_processor.extract_design_styles(text)
            preference_analysis = await design_nlp_processor.analyze_preferences(text)
            intent_classification = await design_nlp_processor.classify_intent(text)

            return {
                "style_analysis": {
                    "primary_style": style_extraction.primary_style,
                    "secondary_styles": style_extraction.secondary_styles,
                    "confidence": style_extraction.confidence_score,
                    "keywords": style_extraction.style_keywords,
                    "reasoning": style_extraction.reasoning,
                },
                "preferences": {
                    "colors": preference_analysis.colors,
                    "materials": preference_analysis.materials,
                    "patterns": preference_analysis.patterns,
                    "textures": preference_analysis.textures,
                    "budget": preference_analysis.budget_indicators,
                    "functional_needs": preference_analysis.functional_requirements,
                    "confidence": preference_analysis.confidence_score,
                },
                "intent": {
                    "primary_intent": intent_classification.primary_intent,
                    "confidence": intent_classification.confidence_score,
                    "entities": intent_classification.entities,
                    "suggested_action": intent_classification.action_required,
                },
            }

        except Exception as e:
            logger.error(f"Error in NLP analysis: {e}")
            return {
                "style_analysis": {"primary_style": "modern", "confidence": 0.1},
                "preferences": {"colors": [], "materials": [], "confidence": 0.1},
                "intent": {"primary_intent": "general_inquiry", "confidence": 0.5},
            }

    async def analyze_conversation_insights(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive conversation insights using NLP"""
        try:
            # Get conversation context
            context = self.context_manager.get_or_create_context(session_id)

            if not context.messages:
                return {"error": "No conversation data available"}

            # Process conversation history with NLP
            insights = await design_nlp_processor.process_conversation_history(context.messages)

            # Add context-specific insights
            insights["session_insights"] = {
                "conversation_state": context.conversation_state,
                "total_interactions": context.total_interactions,
                "has_room_context": context.current_room_context is not None,
                "analysis_history_count": len(context.design_analysis_history),
                "user_preferences_evolution": self._analyze_preference_evolution(context),
            }

            return insights

        except Exception as e:
            logger.error(f"Error analyzing conversation insights: {e}")
            return {"error": f"Analysis failed: {str(e)}"}

    def _analyze_preference_evolution(self, context) -> Dict[str, Any]:
        """Analyze how user preferences have evolved through conversation"""
        try:
            if len(context.design_analysis_history) < 2:
                return {"evolution": "insufficient_data"}

            first_analysis = context.design_analysis_history[0]
            latest_analysis = context.design_analysis_history[-1]

            evolution = {
                "style_consistency": self._compare_style_preferences(first_analysis, latest_analysis),
                "preference_refinement": self._measure_preference_refinement(context.design_analysis_history),
                "confidence_trend": self._calculate_confidence_trend(context.design_analysis_history),
            }

            return evolution

        except Exception as e:
            logger.warning(f"Error analyzing preference evolution: {e}")
            return {"evolution": "analysis_error"}

    def _compare_style_preferences(self, first_analysis: Dict, latest_analysis: Dict) -> str:
        """Compare style preferences between first and latest analysis"""
        try:
            first_style = (
                first_analysis.get("analysis", {})
                .get("design_analysis", {})
                .get("style_preferences", {})
                .get("primary_style", "")
            )
            latest_style = (
                latest_analysis.get("analysis", {})
                .get("design_analysis", {})
                .get("style_preferences", {})
                .get("primary_style", "")
            )

            if first_style == latest_style:
                return "consistent"
            elif first_style and latest_style:
                return "evolved"
            else:
                return "unclear"

        except Exception:
            return "analysis_error"

    def _measure_preference_refinement(self, analysis_history: List[Dict]) -> str:
        """Measure how refined preferences have become"""
        try:
            if len(analysis_history) < 2:
                return "insufficient_data"

            # Count specific preferences over time
            preference_counts = []
            for analysis in analysis_history:
                count = 0
                analysis_data = analysis.get("analysis", {}).get("design_analysis", {})

                # Count color preferences
                colors = analysis_data.get("color_scheme", {}).get("preferred_colors", [])
                count += len(colors)

                # Count style keywords
                style_keywords = analysis_data.get("style_preferences", {}).get("style_keywords", [])
                count += len(style_keywords)

                preference_counts.append(count)

            # Determine trend
            if len(preference_counts) >= 2:
                if preference_counts[-1] > preference_counts[0]:
                    return "increasing_specificity"
                elif preference_counts[-1] < preference_counts[0]:
                    return "decreasing_specificity"
                else:
                    return "stable"

            return "unclear"

        except Exception:
            return "analysis_error"

    def _calculate_confidence_trend(self, analysis_history: List[Dict]) -> str:
        """Calculate confidence trend over conversation"""
        try:
            confidence_scores = []
            for analysis in analysis_history:
                overall_confidence = analysis.get("analysis", {}).get("confidence_scores", {}).get("overall_analysis", 0)
                confidence_scores.append(overall_confidence)

            if len(confidence_scores) >= 2:
                if confidence_scores[-1] > confidence_scores[0] + 5:  # 5 point threshold
                    return "increasing"
                elif confidence_scores[-1] < confidence_scores[0] - 5:
                    return "decreasing"
                else:
                    return "stable"

            return "insufficient_data"

        except Exception:
            return "analysis_error"

    async def extract_room_requirements(self, text: str, image_data: Optional[str] = None) -> Dict[str, Any]:
        """Extract specific room requirements from text and image"""
        try:
            # Use NLP to extract basic requirements
            intent_classification = await design_nlp_processor.classify_intent(text)
            preference_analysis = await design_nlp_processor.analyze_preferences(text)

            entities = intent_classification.entities
            functional_needs = preference_analysis.functional_requirements

            # Extract room-specific requirements
            room_requirements = {
                "room_type": entities.get("rooms", ["unknown"])[0] if entities.get("rooms") else "unknown",
                "dimensions": entities.get("dimensions", []),
                "furniture_needed": entities.get("furniture", []),
                "functional_requirements": functional_needs,
                "color_preferences": preference_analysis.colors,
                "material_preferences": preference_analysis.materials,
                "budget_level": preference_analysis.budget_indicators,
                "has_image": image_data is not None,
                "extraction_confidence": (preference_analysis.confidence_score + intent_classification.confidence_score) / 2,
            }

            return room_requirements

        except Exception as e:
            logger.error(f"Error extracting room requirements: {e}")
            return {"room_type": "unknown", "extraction_confidence": 0.1, "error": str(e)}

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return {
            **self.api_usage_stats,
            "success_rate": (
                self.api_usage_stats["successful_requests"] / max(self.api_usage_stats["total_requests"], 1) * 100
            ),
            "average_tokens_per_request": (
                self.api_usage_stats["total_tokens"] / max(self.api_usage_stats["successful_requests"], 1)
            ),
        }

    def reset_usage_stats(self):
        """Reset usage statistics"""
        self.api_usage_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "last_reset": datetime.now(),
        }
        logger.info("API usage statistics reset")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the ChatGPT service"""
        try:
            # Test with a simple message
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": 'Say \'OK\' in JSON format: {"status": "OK"}'},
            ]

            start_time = time.time()
            await self._call_chatgpt(test_messages)
            response_time = time.time() - start_time

            return {
                "status": "healthy",
                "response_time": response_time,
                "api_key_valid": True,
                "rate_limiter_active": len(self.rate_limiter.requests) > 0,
                "usage_stats": self.get_usage_stats(),
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "api_key_valid": bool(settings.openai_api_key),
                "usage_stats": self.get_usage_stats(),
            }

    async def detect_furniture_with_bounding_boxes(self, image_data: str) -> List[Dict[str, Any]]:
        """
        Use ChatGPT-4 Vision to detect furniture and return bounding box coordinates

        Args:
            image_data: Base64 encoded image data (with or without data URI prefix)

        Returns:
            List of detected furniture with normalized bounding boxes (0-1 range)
        """
        try:
            logger.info("Detecting furniture with ChatGPT-4 Vision...")

            # Process image
            processed_image = self._process_image(image_data)
            if not processed_image:
                logger.error("Failed to process image for furniture detection")
                return []

            # Build detection prompt
            detection_prompt = """Analyze this room image and identify all furniture and decor objects.

For EACH object you find, provide:
1. Object type (sofa, chair, table, lamp, etc.)
2. Normalized bounding box coordinates (0.0 to 1.0 range)
3. Position description
4. Approximate size
5. Visual characteristics

CRITICAL: Bounding box format must be:
- x1, y1: top-left corner (as fraction of image width/height)
- x2, y2: bottom-right corner (as fraction of image width/height)
- Coordinates MUST be between 0.0 and 1.0
- x1 < x2 and y1 < y2 (valid rectangle)

Return as JSON array:
{
  "detected_objects": [
    {
      "object_type": "sofa",
      "bounding_box": {"x1": 0.15, "y1": 0.35, "x2": 0.75, "y2": 0.85},
      "position": "center-left",
      "size": "large",
      "style": "modern",
      "color": "gray",
      "material": "fabric",
      "confidence": 0.95
    }
  ]
}

EXTREMELY IMPORTANT - Bounding Box Precision Rules:
1. Draw TIGHT boxes around ONLY the furniture item itself
2. DO NOT include floor area, carpet, or surrounding space
3. DO NOT include other furniture items in the same box
4. DO NOT create boxes that cover entire halves/quadrants of the room
5. Each sofa/chair/table should have its OWN separate tight box
6. The box should closely hug the visible edges of the furniture
7. Example: A sofa on the left should be x1=0.05, x2=0.45 (NOT x1=0.0, x2=0.5)
8. Example: A sofa in bottom half should be y1=0.55, y2=0.88 (NOT y1=0.5, y2=1.0)

BAD (too large): {"x1": 0.0, "y1": 0.5, "x2": 0.5, "y2": 1.0}  ← Covers entire quadrant!
GOOD (tight fit): {"x1": 0.05, "y1": 0.55, "x2": 0.48, "y2": 0.92}  ← Just the sofa!"""

            # Prepare messages
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": detection_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{processed_image}", "detail": "high"},
                        },
                    ],
                }
            ]

            # Call ChatGPT with JSON mode
            await self.rate_limiter.acquire()
            self.api_usage_stats["total_requests"] += 1

            start_time = time.time()
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=2000,
                temperature=0.2,  # Low temperature for factual detection
                response_format={"type": "json_object"},
            )

            response_time = time.time() - start_time

            # Parse response
            response_content = response.choices[0].message.content if response.choices else None
            if not response_content:
                logger.warning("ChatGPT returned empty response for furniture detection")
                return []

            # Extract detected objects
            result = json.loads(response_content)
            detected_objects = result.get("detected_objects", [])

            # Validate and log results
            valid_objects = []
            for obj in detected_objects:
                bbox = obj.get("bounding_box")
                if bbox and all(key in bbox for key in ["x1", "y1", "x2", "y2"]):
                    # Validate coordinates
                    x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
                    if 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1:
                        valid_objects.append(obj)
                        logger.info(f"Detected {obj.get('object_type')}: bbox={bbox}")
                    else:
                        logger.warning(f"Invalid bbox for {obj.get('object_type')}: {bbox}")
                else:
                    logger.warning(f"Missing bbox for {obj.get('object_type')}")

            self.api_usage_stats["successful_requests"] += 1
            if hasattr(response, "usage") and response.usage:
                self.api_usage_stats["total_tokens"] += response.usage.total_tokens

            logger.info(
                f"ChatGPT furniture detection completed in {response_time:.2f}s - Found {len(valid_objects)} valid objects"
            )
            return valid_objects

        except Exception as e:
            self.api_usage_stats["failed_requests"] += 1
            logger.error(f"Error in ChatGPT furniture detection: {e}", exc_info=True)
            return []


# Global service instance
chatgpt_service = ChatGPTService()
