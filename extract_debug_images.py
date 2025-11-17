"""
Extract and save debug images from Replicate API calls
"""
import base64
import os
from PIL import Image
import io

# Create debug directory
debug_dir = "/Users/sahityapandiri/Omnishop/debug_images"
os.makedirs(debug_dir, exist_ok=True)

def save_data_uri_to_file(data_uri, filename):
    """Save a data URI to a file and return image info"""
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

    return {
        'filepath': filepath,
        'size_bytes': len(image_bytes),
        'dimensions': img.size,
        'mode': img.mode
    }

# Read the server logs to extract the data URIs
import subprocess
import re

print("Extracting debug images from latest Replicate API call...")
print("=" * 60)

# We'll trigger a new visualization to capture fresh data
# For now, let's create a simple test to get the images

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

    # Resize to SDXL dimensions
    def resize_to_sdxl_dimensions(size):
        width, height = size
        aspect_ratio = width / height
        max_dimension = 1024

        if width > height:
            new_width = max_dimension
            new_height = int(max_dimension / aspect_ratio)
        else:
            new_height = max_dimension
            new_width = int(max_dimension * aspect_ratio)

        new_width = ((new_width + 31) // 64) * 64
        new_height = ((new_height + 31) // 64) * 64

        return (new_width, new_height)

    original_size = room_image.size
    target_size = resize_to_sdxl_dimensions(original_size)

    print(f"Original room image: {original_size}")
    print(f"Target SDXL size: {target_size}")

    # Resize room image
    room_image_resized = room_image.resize(target_size, Image.Resampling.LANCZOS)

    # Save resized room image
    room_filepath = os.path.join(debug_dir, "room_image_resized.png")
    room_image_resized.save(room_filepath)
    print(f"\n✓ Saved room image: {room_filepath}")
    print(f"  Dimensions: {room_image_resized.size}")
    print(f"  Size: {os.path.getsize(room_filepath)} bytes")

    # Generate mask (using centered placement)
    products_to_place = [{'name': 'Test Sofa', 'dimensions': {'width': 84, 'height': 36}}]
    mask = await service._generate_placement_mask(
        room_image=room_image_resized,
        products_to_place=products_to_place,
        existing_furniture=[],
        user_action='add'
    )

    # Save mask
    mask_filepath = os.path.join(debug_dir, "mask_image.png")
    mask.save(mask_filepath)
    print(f"\n✓ Saved mask image: {mask_filepath}")
    print(f"  Dimensions: {mask.size}")
    print(f"  Mode: {mask.mode}")
    print(f"  Size: {os.path.getsize(mask_filepath)} bytes")

    # Generate Canny edge map
    canny_edge_image = service._generate_canny_edge_image(room_image_resized)

    # Save Canny
    canny_filepath = os.path.join(debug_dir, "canny_edge_image.png")
    canny_edge_image.save(canny_filepath)
    print(f"\n✓ Saved Canny edge image: {canny_filepath}")
    print(f"  Dimensions: {canny_edge_image.size}")
    print(f"  Mode: {canny_edge_image.mode}")
    print(f"  Size: {os.path.getsize(canny_filepath)} bytes")

    print("\n" + "=" * 60)
    print(f"All debug images saved to: {debug_dir}")
    print("=" * 60)

# Run the extraction
asyncio.run(extract_images())
