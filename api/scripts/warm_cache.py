"""
Script to warm the stores cache after deployment

This script calls the warm-cache endpoint to pre-populate the cache
with store data, ensuring fast response times for the first user request.

Usage:
    python3 scripts/warm_cache.py [--url URL]

Options:
    --url URL    The base URL of the API (default: http://localhost:8000)

Example:
    # Local environment
    python3 scripts/warm_cache.py

    # Production environment
    python3 scripts/warm_cache.py --url https://omnishop-production.railway.app
"""
import argparse
import sys

import httpx


def warm_cache(base_url: str) -> bool:
    """
    Call the warm-cache endpoint to pre-populate the stores cache

    Args:
        base_url: The base URL of the API (e.g., http://localhost:8000)

    Returns:
        True if successful, False otherwise
    """
    url = f"{base_url.rstrip('/')}/api/stores/warm-cache"

    try:
        print(f"Warming stores cache at {url}...")

        response = httpx.post(url, timeout=30.0)
        response.raise_for_status()

        data = response.json()

        if data.get("success"):
            stores = data.get("stores", [])
            message = data.get("message", "")
            print(f"✅ {message}")
            print(f"   Cached stores: {', '.join(stores)}")
            return True
        else:
            print(f"❌ Cache warming failed: {data}")
            return False

    except httpx.HTTPError as e:
        print(f"❌ HTTP error warming cache: {e}")
        return False
    except Exception as e:
        print(f"❌ Error warming cache: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Warm the stores cache after deployment")
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="The base URL of the API (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    success = warm_cache(args.url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
