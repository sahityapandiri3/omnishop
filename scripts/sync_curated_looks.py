#!/usr/bin/env python3
"""
Script to sync curated looks between production and local databases.

Usage:
  Export from production:
    python scripts/sync_curated_looks.py export --from-prod

  Import to local:
    python scripts/sync_curated_looks.py import --to-local

  Full sync (export from prod, import to local):
    python scripts/sync_curated_looks.py sync
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

# Configuration
PROD_API_URL = os.getenv("PROD_API_URL", "https://app.omni-shop.in")
LOCAL_API_URL = os.getenv("LOCAL_API_URL", "http://localhost:8000")
EXPORT_FILE = Path(__file__).parent / "curated_looks_export.json"


def fetch_curated_looks(api_url: str) -> list:
    """Fetch all curated looks from an API endpoint."""
    print(f"Fetching curated looks from {api_url}...")

    try:
        response = requests.get(f"{api_url}/api/curated/looks", timeout=30)
        response.raise_for_status()
        data = response.json()

        looks = data.get("looks", [])
        print(f"  Found {len(looks)} curated looks")
        return looks
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching looks: {e}")
        return []


def fetch_look_details(api_url: str, look_id: str) -> dict | None:
    """Fetch detailed information for a single curated look."""
    try:
        response = requests.get(f"{api_url}/api/curated/looks/{look_id}", timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching look {look_id}: {e}")
        return None


def export_curated_looks(api_url: str, output_file: Path) -> bool:
    """Export all curated looks from an API to a JSON file."""
    print(f"\n=== Exporting Curated Looks from {api_url} ===\n")

    # Get list of looks
    looks = fetch_curated_looks(api_url)
    if not looks:
        print("No looks found to export.")
        return False

    # Fetch full details for each look
    detailed_looks = []
    for i, look in enumerate(looks):
        look_id = look.get("look_id")
        print(f"  [{i+1}/{len(looks)}] Fetching details for: {look.get('style_theme', 'Unknown')}")

        details = fetch_look_details(api_url, look_id)
        if details:
            detailed_looks.append(details)

    # Save to file
    export_data = {
        "exported_at": datetime.now().isoformat(),
        "source_url": api_url,
        "count": len(detailed_looks),
        "looks": detailed_looks
    }

    with open(output_file, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"\nExported {len(detailed_looks)} looks to {output_file}")
    print(f"File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    return True


def import_curated_looks(api_url: str, input_file: Path) -> bool:
    """Import curated looks from a JSON file to an API."""
    print(f"\n=== Importing Curated Looks to {api_url} ===\n")

    if not input_file.exists():
        print(f"Error: Export file not found: {input_file}")
        return False

    with open(input_file, "r") as f:
        export_data = json.load(f)

    looks = export_data.get("looks", [])
    print(f"Found {len(looks)} looks in export file")
    print(f"Exported from: {export_data.get('source_url')}")
    print(f"Exported at: {export_data.get('exported_at')}")
    print()

    # First, get existing looks to avoid duplicates
    existing_looks = fetch_curated_looks(api_url)
    existing_themes = {look.get("style_theme") for look in existing_looks}

    imported = 0
    skipped = 0
    failed = 0

    for i, look in enumerate(looks):
        style_theme = look.get("style_theme", "Unknown")
        print(f"  [{i+1}/{len(looks)}] Processing: {style_theme}")

        # Skip if already exists
        if style_theme in existing_themes:
            print(f"    Skipping (already exists)")
            skipped += 1
            continue

        # Prepare the data for import (matches admin_curated router CuratedLookCreate schema)
        # The schema requires: title, style_theme, room_type, and optionally other fields
        import_data = {
            "title": look.get("style_theme"),  # Use style_theme as title
            "style_theme": look.get("style_theme"),
            "style_description": look.get("style_description"),
            "room_type": look.get("room_type", "living_room"),
            "room_image": look.get("room_image"),
            "visualization_image": look.get("visualization_image"),
            "product_ids": [p.get("id") for p in look.get("products", []) if p.get("id")],
            "is_published": True,
            "display_order": 0,
        }

        try:
            response = requests.post(
                f"{api_url}/api/admin/curated",
                json=import_data,
                timeout=60
            )

            if response.status_code in (200, 201):
                print(f"    Imported successfully")
                imported += 1
            else:
                print(f"    Failed: {response.status_code} - {response.text[:100]}")
                failed += 1
        except requests.exceptions.RequestException as e:
            print(f"    Error: {e}")
            failed += 1

    print(f"\n=== Import Summary ===")
    print(f"  Imported: {imported}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Failed: {failed}")

    return failed == 0


def main():
    parser = argparse.ArgumentParser(
        description="Sync curated looks between production and local databases"
    )
    parser.add_argument(
        "action",
        choices=["export", "import", "sync", "list"],
        help="Action to perform"
    )
    parser.add_argument(
        "--from-prod",
        action="store_true",
        help="Export from production (default)"
    )
    parser.add_argument(
        "--from-local",
        action="store_true",
        help="Export from local"
    )
    parser.add_argument(
        "--to-local",
        action="store_true",
        help="Import to local (default)"
    )
    parser.add_argument(
        "--to-prod",
        action="store_true",
        help="Import to production (use with caution!)"
    )
    parser.add_argument(
        "--prod-url",
        default=PROD_API_URL,
        help=f"Production API URL (default: {PROD_API_URL})"
    )
    parser.add_argument(
        "--local-url",
        default=LOCAL_API_URL,
        help=f"Local API URL (default: {LOCAL_API_URL})"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=EXPORT_FILE,
        help=f"Export/import file path (default: {EXPORT_FILE})"
    )

    args = parser.parse_args()

    if args.action == "list":
        print("\n=== Production Curated Looks ===")
        prod_looks = fetch_curated_looks(args.prod_url)
        for look in prod_looks:
            print(f"  - {look.get('style_theme', 'Unknown')} (look_id: {look.get('look_id')})")

        print("\n=== Local Curated Looks ===")
        local_looks = fetch_curated_looks(args.local_url)
        for look in local_looks:
            print(f"  - {look.get('style_theme', 'Unknown')} (look_id: {look.get('look_id')})")
        return

    if args.action == "export":
        source_url = args.local_url if args.from_local else args.prod_url
        export_curated_looks(source_url, args.file)

    elif args.action == "import":
        if args.to_prod:
            confirm = input("WARNING: You are about to import to PRODUCTION. Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                print("Aborted.")
                return
            target_url = args.prod_url
        else:
            target_url = args.local_url

        import_curated_looks(target_url, args.file)

    elif args.action == "sync":
        # Full sync: export from prod, import to local
        print("Performing full sync: Production -> Local\n")

        if export_curated_looks(args.prod_url, args.file):
            import_curated_looks(args.local_url, args.file)


if __name__ == "__main__":
    main()
