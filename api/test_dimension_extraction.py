#!/usr/bin/env python3
"""
Test script to verify dimension extraction from product descriptions
"""
import sys
import os

# Add parent directory to path for api imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.cloud_inpainting_service import CloudInpaintingService

def test_dimension_extraction():
    """Test dimension extraction with various description formats"""

    service = CloudInpaintingService()

    # Test cases with different dimension formats
    test_cases = [
        {
            "name": "Case 1: Standard WxDxH format",
            "product_name": "Green Velvet Sofa",
            "description": "Beautiful green velvet sofa measuring 84\"W x 36\"D x 36\"H. Perfect for modern living rooms.",
            "expected": "dimensions 84 inches wide by 36 inches deep by 36 inches high"
        },
        {
            "name": "Case 2: Width/Depth/Height labels",
            "product_name": "Brown Leather Chair",
            "description": "Luxurious brown leather chair. Width: 32 inches, Depth: 34 inches, Height: 40 inches. Handcrafted.",
            "expected": "dimensions 32 inches wide by 34 inches deep by 40 inches high"
        },
        {
            "name": "Case 3: Dimensions prefix",
            "product_name": "Modern Coffee Table",
            "description": "Modern rectangular coffee table. Dimensions: 48 x 24 x 18. Made of solid oak.",
            "expected": "dimensions 48 inches wide by 24 inches deep by 18 inches high"
        },
        {
            "name": "Case 4: Simple WxD format",
            "product_name": "Round Dining Table",
            "description": "Round dining table, 60 x 60 inches, seats 6 people comfortably.",
            "expected": "dimensions 60 inches wide by 60 inches deep"
        },
        {
            "name": "Case 5: No dimensions (fallback to furniture type)",
            "product_name": "Classic Sofa",
            "description": "Classic sofa with tufted back. Made from premium fabric. Available in multiple colors.",
            "expected": "typical sofa dimensions"
        },
        {
            "name": "Case 6: No dimensions, unknown furniture type",
            "product_name": "Decorative Item",
            "description": "Beautiful decorative piece for your home.",
            "expected": None
        }
    ]

    print("=" * 80)
    print("DIMENSION EXTRACTION TEST")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for test in test_cases:
        print(f"\n{test['name']}")
        print("-" * 80)
        print(f"Product: {test['product_name']}")
        print(f"Description: {test['description']}")
        print()

        # Extract dimensions
        result = service._extract_dimensions_from_description(
            test['description'],
            test['product_name']
        )

        print(f"Expected: {test['expected']}")
        print(f"Got:      {result}")

        # Check if result matches expectation
        if test['expected'] is None:
            if result is None:
                print("✓ PASS")
                passed += 1
            else:
                print("✗ FAIL (Expected None)")
                failed += 1
        elif result and test['expected'] in result:
            print("✓ PASS")
            passed += 1
        else:
            print("✗ FAIL")
            failed += 1

    # Test color extraction
    print("\n" + "=" * 80)
    print("COLOR EXTRACTION TEST")
    print("=" * 80)

    color_tests = [
        ("Green Velvet Sofa", "green"),
        ("Sage Living Room Chair", "sage"),
        ("Brown Leather Ottoman", "brown"),
        ("Navy Blue Accent Chair", "navy"),
        ("Classic Neutral Sofa", None)
    ]

    for product_name, expected_color in color_tests:
        result = service._extract_color_descriptor(product_name)
        status = "✓ PASS" if result == expected_color else "✗ FAIL"
        print(f"\n{product_name}: {result} (expected: {expected_color}) {status}")
        if result == expected_color:
            passed += 1
        else:
            failed += 1

    # Test material extraction
    print("\n" + "=" * 80)
    print("MATERIAL EXTRACTION TEST")
    print("=" * 80)

    material_tests = [
        ("Green Velvet Sofa", "velvet"),
        ("Brown Leather Ottoman", "leather"),
        ("Wooden Coffee Table", "wooden"),
        ("Wicker Patio Chair", "wicker"),
        ("Classic Neutral Sofa", None)
    ]

    for product_name, expected_material in material_tests:
        result = service._extract_material_descriptor(product_name)
        status = "✓ PASS" if result == expected_material else "✗ FAIL"
        print(f"\n{product_name}: {result} (expected: {expected_material}) {status}")
        if result == expected_material:
            passed += 1
        else:
            failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    print()

    if failed == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"⚠️  {failed} TEST(S) FAILED")

    return failed == 0

if __name__ == "__main__":
    success = test_dimension_extraction()
    sys.exit(0 if success else 1)
