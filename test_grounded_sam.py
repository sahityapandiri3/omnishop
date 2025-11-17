"""
Test Lang-Segment-Anything API integration in isolation
(tmappdev/lang-segment-anything - improved detection for interior scenes)
"""
import asyncio
import os
import replicate
from PIL import Image
import base64
import io

# Test configuration
# Using tmappdev/lang-segment-anything model (latest version: 891411c3)
LANG_SEGMENT_ANYTHING_VERSION = "891411c38a6ed2d44c004b7b9e44217df7a5b07848f29ddefd2e28bc7cbf93bc"
REPLICATE_API_KEY = os.environ.get("REPLICATE_API_TOKEN", "")

def image_to_data_uri(image: Image.Image) -> str:
    """Convert PIL Image to data URI"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"

async def test_lang_segment_anything():
    """Test Lang-Segment-Anything API call"""
    print("\n" + "="*60)
    print("TESTING LANG-SEGMENT-ANYTHING INTEGRATION")
    print("="*60)

    # Set API key
    import os
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_KEY
    replicate.api_token = REPLICATE_API_KEY

    # Load test image
    print("\n1. Loading test image...")
    test_image_path = "/Users/sahityapandiri/Omnishop/test_room_image.png"
    try:
        room_image = Image.open(test_image_path)
        print(f"   ✓ Loaded image: {room_image.size}")
        print(f"   ✓ Using ORIGINAL size (no resize)")
    except Exception as e:
        print(f"   ✗ Failed to load image: {e}")
        return

    # Convert to data URI
    print("\n2. Converting image to data URI...")
    try:
        room_data_uri = image_to_data_uri(room_image)
        print(f"   ✓ Data URI created ({len(room_data_uri)} chars)")
    except Exception as e:
        print(f"   ✗ Failed to convert image: {e}")
        return

    # Test Lang-Segment-Anything API call
    print("\n3. Testing Lang-Segment-Anything API call...")
    print(f"   Model version: {LANG_SEGMENT_ANYTHING_VERSION}")
    print(f"   Text Prompt: 'sofa'")

    try:
        # Create prediction
        print("\n   Creating prediction...")
        prediction = await asyncio.to_thread(
            replicate.predictions.create,
            version=LANG_SEGMENT_ANYTHING_VERSION,
            input={
                "image": room_data_uri,
                "text_prompt": "sofa"
            }
        )

        prediction_id = prediction.id
        print(f"   ✓ Prediction created: {prediction_id}")
        print(f"   Status: {prediction.status}")

        # Poll for completion
        print("\n   Polling for completion...")
        import time
        start_time = time.time()
        timeout = 180.0
        poll_interval = 2.0

        while time.time() - start_time < timeout:
            prediction = await asyncio.to_thread(
                replicate.predictions.get,
                prediction_id
            )

            elapsed = time.time() - start_time
            print(f"   [{elapsed:.1f}s] Status: {prediction.status}")

            if prediction.status == "succeeded":
                print(f"\n   ✓ SUCCESS after {elapsed:.1f}s")

                # Show output
                output = prediction.output
                print(f"\n   Output type: {type(output)}")
                if isinstance(output, list):
                    print(f"   Output list length: {len(output)}")
                    if len(output) > 0:
                        print(f"   First output: {output[0][:100]}...")
                elif isinstance(output, str):
                    print(f"   Output string: {output[:100]}...")

                return True

            elif prediction.status == "failed":
                error_msg = getattr(prediction, 'error', 'Unknown error')
                print(f"\n   ✗ FAILED: {error_msg}")
                return False

            elif prediction.status == "canceled":
                print(f"\n   ✗ CANCELED")
                return False

            await asyncio.sleep(poll_interval)

        print(f"\n   ✗ TIMEOUT after {timeout}s")
        return False

    except Exception as e:
        print(f"\n   ✗ API call failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_lang_segment_anything())

    print("\n" + "="*60)
    if success:
        print("✓ LANG-SEGMENT-ANYTHING TEST PASSED")
    else:
        print("✗ LANG-SEGMENT-ANYTHING TEST FAILED")
    print("="*60 + "\n")
