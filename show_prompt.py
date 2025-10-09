#!/usr/bin/env python3
"""
Script to display the exact prompt sent to Google AI API for product placement visualization
"""

# Simulate the prompt structure from google_ai_service.py
def show_visualization_prompt():
    # Sample data
    products_description = [
        "Product 1: Modern Throw Pillow with Geometric Pattern",
        "Product 2: Rattan Side Table"
    ]
    products_list = '\n'.join([f"- {desc}" for desc in products_description])
    user_request = "boho style"
    lighting_conditions = "mixed"
    render_quality = "high"

    visualization_prompt = f"""⚠️ CRITICAL INSTRUCTION: THIS IS AN ADD-ONLY TASK, NOT A REDESIGN TASK ⚠️

TASK: ADD the specific products listed below to EMPTY SPACES in this room. DO NOT change anything else.

PRODUCTS TO ADD (see reference images below):
{products_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 ABSOLUTELY FORBIDDEN - YOU MUST NOT DO THESE THINGS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ❌ DO NOT change wall colors, wall textures, or wall materials
2. ❌ DO NOT change flooring colors, patterns, or materials
3. ❌ DO NOT change ceiling color or design
4. ❌ DO NOT remove ANY existing furniture, even if it looks old or doesn't match
5. ❌ DO NOT replace ANY existing furniture or decor items
6. ❌ DO NOT move or reposition ANY existing furniture
7. ❌ DO NOT change the room's lighting, windows, or doors
8. ❌ DO NOT alter the room's style or color scheme
9. ❌ DO NOT add items that are NOT in the product list above
10. ❌ DO NOT redesign, transform, or makeover the room

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ THE ONLY THING YOU ARE ALLOWED TO DO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✓ LOOK at the room image and IDENTIFY empty spaces (empty floor areas, empty sofa surfaces, empty tables, empty shelves, empty walls)
2. ✓ LOOK at the product reference images to see exact colors, patterns, and designs
3. ✓ ADD ONLY the products from the reference images to empty spaces
4. ✓ MATCH the products EXACTLY to reference images (same color, pattern, texture, design)
5. ✓ BLEND products naturally with realistic shadows and lighting

📍 WHERE TO PLACE PRODUCTS (only in EMPTY spaces):
- Throw pillows/cushions → Empty spots on existing sofas, chairs, or beds
- Small furniture items → Empty floor spaces (corners, empty walls)
- Decor items → Empty surfaces on tables, shelves, or empty wall space
- Lamps/lighting → Empty tables, empty floor corners

⚠️ IMPORTANT: If a sofa already has 3 pillows, you can add 1-2 MORE pillows. Do NOT remove the existing 3 pillows.
⚠️ IMPORTANT: If a room has a brown couch, keep the brown couch. Add new items around it or on it.

STYLE CONTEXT: {user_request if user_request else 'Place products naturally to complement the existing space'}

QUALITY REQUIREMENTS:
- Lighting: {lighting_conditions} - match the EXISTING lighting in the room
- Rendering: {render_quality} quality photorealism
- Product accuracy: EXACT match to reference images
- Shadows: Realistic shadows matching existing room lighting
- Perspective: Match the existing camera angle

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 VERIFICATION CHECKLIST (check BEFORE generating):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before you generate the output image, verify:
✓ Same wall color and texture as input image?
✓ Same flooring as input image?
✓ Same ceiling as input image?
✓ ALL existing furniture still present (not removed)?
✓ ALL existing decor still present (not moved)?
✓ Same windows and doors?
✓ Same lighting setup?
✓ Only added products from the reference images?
✓ Added products look EXACTLY like reference images?
✓ Products placed in EMPTY spaces only?

If you answered NO to ANY of these questions, you MUST revise your output.

🎯 SUCCESS CRITERIA: The output must be the EXACT SAME ROOM with ONLY the new products added to empty spaces. A person looking at the before/after should say "Oh, they just added [product name] to my room!" NOT "Oh, they redesigned my entire room!"
"""

    print("=" * 100)
    print("EXACT PROMPT SENT TO GOOGLE AI GEMINI 2.5 FLASH IMAGE MODEL")
    print("=" * 100)
    print()
    print(visualization_prompt)
    print()
    print("=" * 100)
    print("ADDITIONAL CONTEXT:")
    print("=" * 100)
    print("- Model: gemini-2.5-flash-image")
    print("- Temperature: 0.4 (for more consistent results)")
    print("- Response modalities: ['IMAGE', 'TEXT']")
    print("- Inputs sent:")
    print("  1. Text prompt (shown above)")
    print("  2. Room image (user's uploaded image)")
    print("  3. Product reference images (for each selected product)")
    print()
    print("The AI receives:")
    print("  - The room photo you uploaded")
    print("  - Photos of each selected product")
    print("  - The detailed instructions above")
    print()
    print("Expected output: Same room with only selected products added")
    print("=" * 100)

if __name__ == "__main__":
    show_visualization_prompt()
