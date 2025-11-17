"""
Direct test of Gemini 2.5 Flash Image replacement
Replicates exactly what worked in Google AI Studio UI
"""
import base64
import os
from google import genai
from google.genai import types
from PIL import Image
import io

# Initialize client
client = genai.Client(api_key=os.environ.get("GOOGLE_AI_API_KEY"))

def load_image_as_base64(image_path: str, max_size: int = None) -> str:
    """Load image and optionally resize"""
    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    if max_size:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')

        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=90)
        image_bytes = buffer.getvalue()

    return base64.b64encode(image_bytes).decode()

# Test 1: Exact Google AI Studio approach (no resizing, no text between images)
print("=" * 80)
print("TEST 1: Exact Google AI Studio approach")
print("=" * 80)

room_image_base64 = load_image_as_base64(
    "/Users/sahityapandiri/Desktop/Screenshot 2025-11-01 at 2.11.13 PM.png"
)
product_image_base64 = load_image_as_base64(
    "/Users/sahityapandiri/Desktop/Screenshot 2025-11-01 at 2.11.26 PM.png"
)

prompt = """Replace the white sectional sofa in the first image with the green sectional sofa shown in the second image.

Keep everything else in the room exactly the same - the walls, floor, windows, curtains, chair, rug, and side table should remain unchanged.

Generate a photorealistic image of the room with the green sofa replacing the white one."""

# Build parts - just prompt and two images, no text between
parts = [
    types.Part.from_text(text=prompt),
    types.Part(
        inline_data=types.Blob(
            mime_type="image/jpeg",
            data=base64.b64decode(room_image_base64)
        )
    ),
    types.Part(
        inline_data=types.Blob(
            mime_type="image/jpeg",
            data=base64.b64decode(product_image_base64)
        )
    )
]

contents = [types.Content(role="user", parts=parts)]

config = types.GenerateContentConfig(
    response_modalities=["IMAGE"],
    temperature=0.4  # Slightly higher than our current 0.3
)

print("Calling Gemini 2.5 Flash Image (no resizing, no text between images)...")
try:
    result_image = None
    for chunk in client.models.generate_content_stream(
        model="gemini-2.5-flash-image",
        contents=contents,
        config=config,
    ):
        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
            for part in chunk.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    result_image = base64.b64encode(image_bytes).decode('utf-8')
                    print(f"✅ Generated image ({len(image_bytes)} bytes)")

    if result_image:
        # Save result
        with open("/Users/sahityapandiri/Omnishop/test_gemini_result_test1.png", "wb") as f:
            f.write(base64.b64decode(result_image))
        print("✅ Saved to: test_gemini_result_test1.png")
    else:
        print("❌ No image generated")

except Exception as e:
    print(f"❌ Error: {e}")

print()

# Test 2: With image resizing (like our current code)
print("=" * 80)
print("TEST 2: With image resizing (1024px room, 512px product)")
print("=" * 80)

room_image_resized = load_image_as_base64(
    "/Users/sahityapandiri/Desktop/Screenshot 2025-11-01 at 2.11.13 PM.png",
    max_size=1024
)
product_image_resized = load_image_as_base64(
    "/Users/sahityapandiri/Desktop/Screenshot 2025-11-01 at 2.11.26 PM.png",
    max_size=512
)

parts2 = [
    types.Part.from_text(text=prompt),
    types.Part(
        inline_data=types.Blob(
            mime_type="image/jpeg",
            data=base64.b64decode(room_image_resized)
        )
    ),
    types.Part(
        inline_data=types.Blob(
            mime_type="image/jpeg",
            data=base64.b64decode(product_image_resized)
        )
    )
]

contents2 = [types.Content(role="user", parts=parts2)]

print("Calling Gemini 2.5 Flash Image (with resizing)...")
try:
    result_image2 = None
    for chunk in client.models.generate_content_stream(
        model="gemini-2.5-flash-image",
        contents=contents2,
        config=config,
    ):
        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
            for part in chunk.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    result_image2 = base64.b64encode(image_bytes).decode('utf-8')
                    print(f"✅ Generated image ({len(image_bytes)} bytes)")

    if result_image2:
        # Save result
        with open("/Users/sahityapandiri/Omnishop/test_gemini_result_test2.png", "wb") as f:
            f.write(base64.b64decode(result_image2))
        print("✅ Saved to: test_gemini_result_test2.png")
    else:
        print("❌ No image generated")

except Exception as e:
    print(f"❌ Error: {e}")

print()

# Test 3: With text label between images (like our current code)
print("=" * 80)
print("TEST 3: With text label between images")
print("=" * 80)

parts3 = [
    types.Part.from_text(text=prompt),
    types.Part(
        inline_data=types.Blob(
            mime_type="image/jpeg",
            data=base64.b64decode(room_image_base64)
        )
    ),
    types.Part.from_text(text="\nProduct reference image (Green Sectional Sofa):"),
    types.Part(
        inline_data=types.Blob(
            mime_type="image/jpeg",
            data=base64.b64decode(product_image_base64)
        )
    )
]

contents3 = [types.Content(role="user", parts=parts3)]

print("Calling Gemini 2.5 Flash Image (with text label)...")
try:
    result_image3 = None
    for chunk in client.models.generate_content_stream(
        model="gemini-2.5-flash-image",
        contents=contents3,
        config=config,
    ):
        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
            for part in chunk.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    result_image3 = base64.b64encode(image_bytes).decode('utf-8')
                    print(f"✅ Generated image ({len(image_bytes)} bytes)")

    if result_image3:
        # Save result
        with open("/Users/sahityapandiri/Omnishop/test_gemini_result_test3.png", "wb") as f:
            f.write(base64.b64decode(result_image3))
        print("✅ Saved to: test_gemini_result_test3.png")
    else:
        print("❌ No image generated")

except Exception as e:
    print(f"❌ Error: {e}")

print()
print("=" * 80)
print("All tests complete! Check the generated images:")
print("  - test_gemini_result_test1.png (no resizing, no text)")
print("  - test_gemini_result_test2.png (with resizing)")
print("  - test_gemini_result_test3.png (with text label)")
print("=" * 80)
