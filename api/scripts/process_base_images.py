"""
Process Base Images - Run furniture removal on base room images.

This script takes images from Base_Images folder, runs them through the
furniture removal flow using Google AI, and saves the cleaned images
to a new folder for use in auto_curation.

Usage:
    python process_base_images.py
"""

import asyncio
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/Users/sahityapandiri/Omnishop/api")

from services.google_ai_service import GoogleAIStudioService

# Paths
BASE_IMAGES_DIR = Path("/Users/sahityapandiri/Omnishop/Base_Images")
CLEAN_IMAGES_DIR = Path("/Users/sahityapandiri/Omnishop/Base_Images/cleaned")
ROOM_ANALYSIS_FILE = CLEAN_IMAGES_DIR / "room_analysis.json"


async def process_image(google_ai: GoogleAIStudioService, image_path: Path) -> dict:
    """Process a single image through furniture removal."""
    print(f"\nProcessing: {image_path.name}")

    # Read image
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()

    print(f"  Original size: {len(image_base64)} bytes")

    # Run furniture removal
    result = await google_ai.remove_furniture(
        image_base64=image_base64,
        workflow_id=f"base-image-{image_path.stem}",
    )

    if not result:
        print(f"  ERROR: Furniture removal failed")
        return None

    clean_image = result.get("image")
    room_analysis = result.get("room_analysis")

    if not clean_image:
        print(f"  ERROR: No clean image returned")
        return None

    # Strip data URI prefix if present (e.g., "data:image/png;base64,...")
    if clean_image.startswith("data:"):
        # Extract the base64 part after the comma
        clean_image = clean_image.split(",", 1)[1]

    print(f"  Clean image size: {len(clean_image)} bytes")
    print(f"  Room type: {room_analysis.get('room_type', 'unknown')}")

    # Save cleaned image
    output_path = CLEAN_IMAGES_DIR / f"{image_path.stem}_clean.jpg"
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(clean_image))

    print(f"  Saved to: {output_path.name}")

    return {
        "original": image_path.name,
        "cleaned": output_path.name,
        "room_analysis": room_analysis,
    }


async def main():
    """Process all base images."""
    print("=" * 60)
    print("Base Image Furniture Removal")
    print("=" * 60)

    # Create output directory
    CLEAN_IMAGES_DIR.mkdir(exist_ok=True)
    print(f"\nOutput directory: {CLEAN_IMAGES_DIR}")

    # Find all images
    image_paths = sorted(BASE_IMAGES_DIR.glob("*.jpg"))
    # Exclude already cleaned images
    image_paths = [p for p in image_paths if "_clean" not in p.name and p.parent == BASE_IMAGES_DIR]

    print(f"Found {len(image_paths)} images to process")

    if not image_paths:
        print("No images found!")
        return

    # Initialize Google AI service
    google_ai = GoogleAIStudioService()

    # Process each image
    results = []
    for i, image_path in enumerate(image_paths, 1):
        print(f"\n[{i}/{len(image_paths)}]", end="")
        try:
            result = await process_image(google_ai, image_path)
            if result:
                results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")

        # Add delay between API calls to avoid rate limiting
        if i < len(image_paths):
            print("  Waiting 5 seconds before next image...")
            await asyncio.sleep(5)

    # Save room analysis data
    with open(ROOM_ANALYSIS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print("COMPLETE")
    print(f"Processed: {len(results)}/{len(image_paths)} images")
    print(f"Cleaned images saved to: {CLEAN_IMAGES_DIR}")
    print(f"Room analysis saved to: {ROOM_ANALYSIS_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
