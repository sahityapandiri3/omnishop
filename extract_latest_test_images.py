#!/usr/bin/env python3
"""
Extract and decode all input images from the latest visualization test
"""
import base64
import io
import sys
import os
from PIL import Image
import cv2
import numpy as np

# Add API directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from services.cloud_inpainting_service import CloudInpaintingService

def decode_base64_image(base64_string):
    """Decode base64 string to PIL Image"""
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    image_bytes = base64.b64decode(base64_string)
    return Image.open(io.BytesIO(image_bytes))

def generate_canny_edge_image(image):
    """Generate Canny edge detection image"""
    img_array = np.array(image)
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.4)
    edges = cv2.Canny(blurred, 50, 150)
    return Image.fromarray(edges)

def generate_placement_mask(room_image, product_name="Node Sofa  5 Seater Corner Sofa (8x8 feet)"):
    """Generate centered placement mask"""
    width, height = room_image.size
    mask = Image.new('L', (width, height), color=0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)

    # Use typical sofa dimensions
    pixels_per_inch = width / 144  # 12ft room
    furn_width = int(84 * pixels_per_inch)  # 84 inches
    furn_height = int(30 * pixels_per_inch * 0.7)

    # Clamp
    furn_width = max(int(width * 0.15), min(furn_width, int(width * 0.45)))
    furn_height = max(int(height * 0.15), min(furn_height, int(height * 0.45)))

    # Add padding
    mask_width = int(furn_width * 1.1)
    mask_height = int(furn_height * 1.1)

    # Center placement
    center_x = width // 2
    center_y = int(height * 0.6)

    x1 = center_x - mask_width // 2
    y1 = center_y - mask_height // 2
    x2 = center_x + mask_width // 2
    y2 = center_y + mask_height // 2

    # Draw white rectangle (255 = inpaint)
    draw.rectangle([x1, y1, x2, y2], fill=255)

    return mask

def main():
    # Create output directory
    output_dir = "/Users/sahityapandiri/Omnishop/debug_images_latest_test"
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 80)
    print("EXTRACTING IMAGES FROM LATEST TEST")
    print("=" * 80)

    # Load the test room image
    test_image_path = "/Users/sahityapandiri/Omnishop/test_room_image.png"
    print(f"\nLoading test image: {test_image_path}")

    with open(test_image_path, 'rb') as f:
        image_bytes = f.read()

    # Decode to PIL Image
    original_room_image = Image.open(io.BytesIO(image_bytes))
    print(f"Original image size: {original_room_image.size}")

    # Step 1: Resize to 512x512 (as done in cloud_inpainting_service.py)
    target_size = (512, 512)
    room_image = original_room_image.resize(target_size, Image.Resampling.LANCZOS)
    print(f"Resized to: {room_image.size}")

    # Save room image
    room_path = os.path.join(output_dir, "1_room_image_512x512.png")
    room_image.save(room_path)
    print(f"✓ Saved: {room_path}")

    # Step 2: Generate placement mask
    mask = generate_placement_mask(room_image)
    print(f"Generated mask: {mask.size}, mode={mask.mode}")

    mask_path = os.path.join(output_dir, "2_mask_white_inpaint.png")
    mask.save(mask_path)
    print(f"✓ Saved: {mask_path}")

    # Step 3: Generate Canny edge map
    canny_edge_image = generate_canny_edge_image(room_image)
    print(f"Generated Canny edges: {canny_edge_image.size}")

    canny_path = os.path.join(output_dir, "3_canny_controlnet_lineart.png")
    canny_edge_image.save(canny_path)
    print(f"✓ Saved: {canny_path}")

    # Step 4: Product reference URL (from test logs)
    # This would be the Node Sofa 5 Seater from the test
    print("\n" + "=" * 80)
    print("IP-ADAPTER REFERENCE IMAGE")
    print("=" * 80)
    print("Product: Node Sofa  5 Seater Corner Sofa (8x8 feet)")
    print("URL: (Available in product database - ID: 312)")

    # Print image dimensions
    print("\n" + "=" * 80)
    print("IMAGE DIMENSIONS SENT TO MODEL")
    print("=" * 80)
    print(f"Room image:    {room_image.size} ({os.path.getsize(room_path):,} bytes)")
    print(f"Mask image:    {mask.size} ({os.path.getsize(mask_path):,} bytes)")
    print(f"Canny image:   {canny_edge_image.size} ({os.path.getsize(canny_path):,} bytes)")

    # Print file locations
    print("\n" + "=" * 80)
    print("SAVED FILES")
    print("=" * 80)
    print(f"Directory: {output_dir}")
    print(f"  1. {room_path}")
    print(f"  2. {mask_path}")
    print(f"  3. {canny_path}")

    print("\n✓ All images extracted successfully!")
    print(f"\nYou can view these images at: {output_dir}")

if __name__ == "__main__":
    main()
