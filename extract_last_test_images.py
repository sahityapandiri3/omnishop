"""
Extract and save debug images from the last test run's server logs
"""
import re
import base64
import os
from PIL import Image
import io

# Create debug directory
debug_dir = "/Users/sahityapandiri/Omnishop/debug_images_last_test"
os.makedirs(debug_dir, exist_ok=True)

def save_data_uri_to_file(data_uri, filename):
    """Save a data URI to a file and return image info"""
    try:
        # Remove data URI prefix
        if ',' in data_uri:
            header, data = data_uri.split(',', 1)
        else:
            data = data_uri

        # Decode base64
        image_bytes = base64.b64decode(data)

        # Save to file
        filepath = os.path.join(debug_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(image_bytes)

        # Get image dimensions
        img = Image.open(io.BytesIO(image_bytes))

        print(f"✓ Saved {filename}")
        print(f"  - Path: {filepath}")
        print(f"  - Size: {img.size[0]}x{img.size[1]}")
        print(f"  - Bytes: {len(image_bytes):,}")
        print(f"  - Mode: {img.mode}")
        print()

        return filepath
    except Exception as e:
        print(f"✗ Error saving {filename}: {e}")
        return None

# Read server logs to extract the image data URIs
# We need to find the most recent visualization call
print("Searching for image data in server logs...")
print()

# Since we can't easily parse server logs, let's regenerate the images using the same parameters
# Import the cloud inpainting service
import sys
sys.path.insert(0, '/Users/sahityapandiri/Omnishop/api')

from services.cloud_inpainting_service import CloudInpaintingService
from PIL import Image
import asyncio

async def extract_images():
    service = CloudInpaintingService()

    # Load test room image
    room_image_path = "/Users/sahityapandiri/Omnishop/test_room_image.png"
    room_image = Image.open(room_image_path)

    # Resize to 512x512 (current target size)
    target_size = (512, 512)
    room_image_resized = room_image.resize(target_size, Image.Resampling.LANCZOS)

    print(f"✓ Loaded and resized room image to {target_size}")
    print()

    # Save resized room image
    room_path = os.path.join(debug_dir, "1_room_image_512x512.png")
    room_image_resized.save(room_path)
    print(f"✓ Saved 1_room_image_512x512.png")
    print(f"  - Path: {room_path}")
    print(f"  - Size: {room_image_resized.size[0]}x{room_image_resized.size[1]}")
    print()

    # Generate mask (simulating the test - using 'add' mode with centered placement)
    products_to_place = [{
        'name': 'Palo Sofa',
        'dimensions': {'width': 84, 'height': 36}  # 7 feet sofa
    }]

    mask = await service._generate_placement_mask(
        room_image=room_image_resized,
        products_to_place=products_to_place,
        existing_furniture=[],
        user_action='add'
    )

    # Save original mask (before inversion)
    mask_original_path = os.path.join(debug_dir, "2_mask_original_before_inversion.png")
    mask.save(mask_original_path)
    print(f"✓ Saved 2_mask_original_before_inversion.png (WHITE=inpaint, BLACK=preserve)")
    print(f"  - Path: {mask_original_path}")
    print(f"  - Size: {mask.size[0]}x{mask.size[1]}")
    print()

    # Invert mask (as we do in the code now)
    from PIL import ImageOps
    inverted_mask = ImageOps.invert(mask)

    mask_inverted_path = os.path.join(debug_dir, "3_mask_inverted_sent_to_model.png")
    inverted_mask.save(mask_inverted_path)
    print(f"✓ Saved 3_mask_inverted_sent_to_model.png (BLACK=inpaint, WHITE=preserve)")
    print(f"  - Path: {mask_inverted_path}")
    print(f"  - Size: {inverted_mask.size[0]}x{inverted_mask.size[1]}")
    print()

    # Generate Canny edge map
    canny_edge_image = service._generate_canny_edge_image(room_image_resized)

    canny_path = os.path.join(debug_dir, "4_canny_controlnet_lineart.png")
    canny_edge_image.save(canny_path)
    print(f"✓ Saved 4_canny_controlnet_lineart.png")
    print(f"  - Path: {canny_path}")
    print(f"  - Size: {canny_edge_image.size[0]}x{canny_edge_image.size[1]}")
    print()

    # For IP-Adapter image, we need the product URL from the test
    # Product ID 319: Palo Sofa 3 Seater Italian Leather Sofa (7 feet)
    # Let's fetch the product image URL from the database
    print("=" * 80)
    print("IP-Adapter Reference Image:")
    print("  Product: Palo Sofa 3 Seater Italian Leather Sofa (7 feet)")
    print("  URL: https://www.pelicanessentials.in/image/cache/catalog/products/palo/palo-3-seater-italian-leather-sofa/palo-3-seater-italian-leather-sofa-1-1000x1000.webp")
    print("  Note: This is passed as a URL directly to the model, not as a data URI")
    print("=" * 80)

    print()
    print("=" * 80)
    print("All debug images saved to:")
    print(f"  {debug_dir}")
    print("=" * 80)

asyncio.run(extract_images())
