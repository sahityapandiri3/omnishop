"""
Budget Allocation Helper Module

This module provides functionality to validate and adjust budget allocations
for product recommendations. It ensures that the sum of category budget
allocations equals exactly the total user budget.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Default allocation percentages by category type
# These are used when AI doesn't provide allocations or for validation
CATEGORY_ALLOCATIONS = {
    # Primary furniture (40-50% total)
    "sofas": {"percent": 0.30, "priority": 1, "type": "primary"},
    "beds": {"percent": 0.30, "priority": 1, "type": "primary"},
    "dining_tables": {"percent": 0.25, "priority": 1, "type": "primary"},
    "wardrobes": {"percent": 0.25, "priority": 1, "type": "primary"},
    # Secondary furniture (20-30% total)
    "coffee_tables": {"percent": 0.10, "priority": 2, "type": "secondary"},
    "side_tables": {"percent": 0.08, "priority": 2, "type": "secondary"},
    "accent_chairs": {"percent": 0.12, "priority": 2, "type": "secondary"},
    "dining_chairs": {"percent": 0.10, "priority": 2, "type": "secondary"},
    "study_tables": {"percent": 0.12, "priority": 2, "type": "secondary"},
    "study_chairs": {"percent": 0.08, "priority": 2, "type": "secondary"},
    "tv_units": {"percent": 0.12, "priority": 2, "type": "secondary"},
    "shoe_racks": {"percent": 0.06, "priority": 2, "type": "secondary"},
    "bookshelves": {"percent": 0.10, "priority": 2, "type": "secondary"},
    "console_tables": {"percent": 0.08, "priority": 2, "type": "secondary"},
    "bar_cabinets": {"percent": 0.10, "priority": 2, "type": "secondary"},
    "ottomans": {"percent": 0.06, "priority": 2, "type": "secondary"},
    "benches": {"percent": 0.06, "priority": 2, "type": "secondary"},
    # Lighting (10-15% total)
    "floor_lamps": {"percent": 0.06, "priority": 3, "type": "lighting"},
    "table_lamps": {"percent": 0.05, "priority": 3, "type": "lighting"},
    "pendant_lights": {"percent": 0.08, "priority": 3, "type": "lighting"},
    "ceiling_lights": {"percent": 0.08, "priority": 3, "type": "lighting"},
    "wall_lights": {"percent": 0.05, "priority": 3, "type": "lighting"},
    # Decor/accessories (10-15% total)
    "planters": {"percent": 0.04, "priority": 4, "type": "decor"},
    "wall_art": {"percent": 0.05, "priority": 4, "type": "decor"},
    "decor": {"percent": 0.04, "priority": 4, "type": "decor"},
    "rugs": {"percent": 0.08, "priority": 4, "type": "decor"},
    "mirrors": {"percent": 0.05, "priority": 4, "type": "decor"},
    "clocks": {"percent": 0.03, "priority": 4, "type": "decor"},
    "vases": {"percent": 0.03, "priority": 4, "type": "decor"},
    "cushions": {"percent": 0.03, "priority": 4, "type": "decor"},
    "throws": {"percent": 0.03, "priority": 4, "type": "decor"},
}

# Default percentage for unknown categories
DEFAULT_CATEGORY_PERCENT = 0.10


def validate_and_adjust_budget_allocations(
    total_budget: float,
    categories: List[Any],
    category_id_field: str = "category_id",
) -> List[Any]:
    """
    Validate and adjust budget allocations to ensure sum of max = total budget.

    This function takes AI-suggested budget allocations and ensures they sum
    to exactly 100% of the total budget. It handles:
    1. Scaling up if AI under-allocated
    2. Scaling down if AI over-allocated
    3. Generating defaults if AI provided no allocations

    Args:
        total_budget: The user's total budget (e.g., 50000)
        categories: List of category objects with budget_allocation field
        category_id_field: Name of the field containing category ID

    Returns:
        List of categories with validated/adjusted budget_allocation fields
    """
    if not total_budget or total_budget <= 0:
        logger.info("[BUDGET] No budget provided, skipping allocation validation")
        return categories

    if not categories:
        logger.info("[BUDGET] No categories provided")
        return categories

    logger.info(f"[BUDGET] Validating allocations for budget ₹{total_budget:,.0f}")

    # Collect current allocations
    allocations = []
    has_any_allocation = False

    for cat in categories:
        cat_id = getattr(cat, category_id_field, None) or cat.get(category_id_field)
        budget_alloc = getattr(cat, "budget_allocation", None)
        if budget_alloc is None and isinstance(cat, dict):
            budget_alloc = cat.get("budget_allocation")

        if budget_alloc and budget_alloc.get("max"):
            has_any_allocation = True
            allocations.append(
                {
                    "category": cat,
                    "cat_id": cat_id,
                    "current_max": float(budget_alloc.get("max", 0)),
                    "current_min": float(budget_alloc.get("min", 0)),
                }
            )
        else:
            allocations.append(
                {
                    "category": cat,
                    "cat_id": cat_id,
                    "current_max": None,
                    "current_min": None,
                }
            )

    # If no allocations provided by AI, generate defaults
    if not has_any_allocation:
        logger.info("[BUDGET] No AI allocations found, generating defaults")
        return _generate_default_allocations(total_budget, categories, category_id_field)

    # Calculate current sum of max values (only for categories with allocations)
    categories_with_alloc = [a for a in allocations if a["current_max"] is not None]
    current_sum = sum(a["current_max"] for a in categories_with_alloc)

    if current_sum == 0:
        logger.info("[BUDGET] Sum of allocations is 0, generating defaults")
        return _generate_default_allocations(total_budget, categories, category_id_field)

    # Calculate scaling factor to make sum = total_budget
    scale_factor = total_budget / current_sum
    logger.info(
        f"[BUDGET] Current sum: ₹{current_sum:,.0f}, " f"Target: ₹{total_budget:,.0f}, Scale factor: {scale_factor:.2f}"
    )

    # Apply scaling to all categories with allocations
    for alloc in allocations:
        cat = alloc["category"]
        if alloc["current_max"] is not None:
            new_max = alloc["current_max"] * scale_factor
            new_min = alloc["current_min"] * scale_factor if alloc["current_min"] else new_max * 0.5

            # Ensure min is reasonable (at least 500, at most 50% of max)
            new_min = max(500, min(new_min, new_max * 0.5))

            # Update the category's budget_allocation
            new_budget_alloc = {"min": round(new_min), "max": round(new_max)}

            if hasattr(cat, "budget_allocation"):
                cat.budget_allocation = new_budget_alloc
            elif isinstance(cat, dict):
                cat["budget_allocation"] = new_budget_alloc

            logger.info(f"[BUDGET] {alloc['cat_id']}: ₹{alloc['current_max']:,.0f} → ₹{new_max:,.0f}")

    # Verify the final sum
    final_sum = sum(
        (
            getattr(a["category"], "budget_allocation", {}).get("max", 0)
            if hasattr(a["category"], "budget_allocation")
            else a["category"].get("budget_allocation", {}).get("max", 0)
        )
        for a in allocations
        if a["current_max"] is not None
    )
    logger.info(f"[BUDGET] Final sum after scaling: ₹{final_sum:,.0f}")

    return categories


def _generate_default_allocations(
    total_budget: float,
    categories: List[Any],
    category_id_field: str = "category_id",
) -> List[Any]:
    """
    Generate default budget allocations for categories based on category type.

    The allocations are calculated to sum to exactly the total budget.

    Args:
        total_budget: The user's total budget
        categories: List of category objects
        category_id_field: Name of the field containing category ID

    Returns:
        Categories with generated budget_allocation fields
    """
    if not categories:
        return categories

    # Get percentages for each category
    category_percents = []
    for cat in categories:
        cat_id = getattr(cat, category_id_field, None) or cat.get(category_id_field)

        if cat_id in CATEGORY_ALLOCATIONS:
            percent = CATEGORY_ALLOCATIONS[cat_id]["percent"]
        else:
            # For unknown categories, use default
            percent = DEFAULT_CATEGORY_PERCENT
            logger.info(f"[BUDGET] Unknown category '{cat_id}', using default {percent*100}%")

        category_percents.append({"category": cat, "cat_id": cat_id, "percent": percent})

    # Normalize percentages so they sum to 1.0 (100%)
    total_percent = sum(cp["percent"] for cp in category_percents)
    if total_percent > 0:
        for cp in category_percents:
            cp["normalized_percent"] = cp["percent"] / total_percent
    else:
        # Equal distribution if no percentages
        equal_share = 1.0 / len(category_percents)
        for cp in category_percents:
            cp["normalized_percent"] = equal_share

    # Allocate budget based on normalized percentages
    for cp in category_percents:
        cat = cp["category"]
        max_budget = total_budget * cp["normalized_percent"]
        min_budget = max(500, max_budget * 0.5)  # Min is 50% of max, at least 500

        new_budget_alloc = {"min": round(min_budget), "max": round(max_budget)}

        if hasattr(cat, "budget_allocation"):
            cat.budget_allocation = new_budget_alloc
        elif isinstance(cat, dict):
            cat["budget_allocation"] = new_budget_alloc

        logger.info(
            f"[BUDGET] Generated default for {cp['cat_id']}: "
            f"₹{min_budget:,.0f} - ₹{max_budget:,.0f} ({cp['normalized_percent']*100:.1f}%)"
        )

    # Verify the sum
    final_sum = sum(
        (
            getattr(cp["category"], "budget_allocation", {}).get("max", 0)
            if hasattr(cp["category"], "budget_allocation")
            else cp["category"].get("budget_allocation", {}).get("max", 0)
        )
        for cp in category_percents
    )
    logger.info(f"[BUDGET] Generated allocations sum: ₹{final_sum:,.0f} (target: ₹{total_budget:,.0f})")

    return categories


def get_budget_summary(total_budget: float, categories: List[Any], category_id_field: str = "category_id") -> Dict[str, Any]:
    """
    Generate a human-readable budget summary for display to users.

    Args:
        total_budget: The user's total budget
        categories: List of category objects with budget allocations
        category_id_field: Name of the field containing category ID

    Returns:
        Dictionary with budget breakdown information
    """
    breakdown = []
    allocated_sum = 0

    for cat in categories:
        cat_id = getattr(cat, category_id_field, None) or cat.get(category_id_field)
        budget_alloc = getattr(cat, "budget_allocation", None)
        if budget_alloc is None and isinstance(cat, dict):
            budget_alloc = cat.get("budget_allocation")

        if budget_alloc:
            max_val = budget_alloc.get("max", 0)
            min_val = budget_alloc.get("min", 0)
            allocated_sum += max_val

            breakdown.append(
                {
                    "category": cat_id,
                    "display_name": (
                        getattr(cat, "display_name", None) or cat.get("display_name") or cat_id.replace("_", " ").title()
                    ),
                    "min": min_val,
                    "max": max_val,
                    "percent": (max_val / total_budget * 100) if total_budget > 0 else 0,
                }
            )

    return {
        "total_budget": total_budget,
        "allocated": allocated_sum,
        "remaining": total_budget - allocated_sum,
        "breakdown": breakdown,
    }
