"""
Filtering Service for Product Filtering

Handles advanced product filtering by various criteria.
"""
import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from database.models import Product
from .schemas import FilterCriteria

logger = logging.getLogger(__name__)


class FilteringService:
    """Service for filtering products by various criteria"""

    def __init__(self):
        self.room_category_map = self._build_room_category_map()
        logger.info("FilteringService initialized")

    def _build_room_category_map(self) -> Dict[str, List[str]]:
        """Map room types to relevant product categories"""
        return {
            "living_room": ["sofas", "chairs", "coffee_tables", "entertainment_centers", "rugs", "lighting"],
            "bedroom": ["beds", "dressers", "nightstands", "mirrors", "lighting", "rugs"],
            "dining_room": ["dining_tables", "dining_chairs", "sideboards", "lighting"],
            "kitchen": ["bar_stools", "kitchen_islands", "storage", "lighting"],
            "office": ["desks", "office_chairs", "bookcases", "storage", "lighting"],
            "bathroom": ["vanities", "mirrors", "storage", "lighting"]
        }

    async def filter_products(
        self,
        products: List[Product],
        criteria: FilterCriteria,
        db: AsyncSession
    ) -> List[Product]:
        """
        Filter products based on multiple criteria

        Args:
            products: List of products to filter
            criteria: Filtering criteria
            db: Database session

        Returns:
            Filtered list of products
        """
        filtered = products

        # Price range filter
        if criteria.price_min is not None or criteria.price_max is not None:
            min_price = criteria.price_min or 0
            max_price = criteria.price_max or float('inf')
            filtered = [p for p in filtered if min_price <= p.price <= max_price]

        # Website filter
        if criteria.website:
            filtered = [p for p in filtered if criteria.website.lower() in (p.source_website or '').lower()]

        # Brand filter
        if criteria.brand:
            filtered = [p for p in filtered if criteria.brand.lower() in (p.brand or '').lower()]

        # In stock filter
        if criteria.in_stock is not None:
            filtered = [p for p in filtered if p.is_available == criteria.in_stock]

        # On sale filter
        if criteria.on_sale is not None:
            filtered = [p for p in filtered if (p.sale_price is not None) == criteria.on_sale]

        # Style filter
        if criteria.style:
            style_keywords = [s.lower() for s in criteria.style]
            filtered = [
                p for p in filtered
                if any(style in (p.name + ' ' + (p.description or '')).lower() for style in style_keywords)
            ]

        # Material filter
        if criteria.material:
            material_keywords = [m.lower() for m in criteria.material]
            filtered = [
                p for p in filtered
                if any(material in (p.name + ' ' + (p.description or '')).lower() for material in material_keywords)
            ]

        # Color filter
        if criteria.color:
            color_keywords = [c.lower() for c in criteria.color]
            filtered = [
                p for p in filtered
                if any(color in (p.name + ' ' + (p.description or '')).lower() for color in color_keywords)
            ]

        logger.info(f"Filtered from {len(products)} to {len(filtered)} products")
        return filtered

    def get_room_categories(self, room_type: str) -> List[str]:
        """
        Get relevant product categories for a room type

        Args:
            room_type: Type of room (e.g., 'living_room', 'bedroom')

        Returns:
            List of relevant category names
        """
        return self.room_category_map.get(room_type, [])

    def filter_by_room_context(self, products: List[Product], room_context: Dict[str, Any]) -> List[Product]:
        """
        Filter products based on room context

        Args:
            products: List of products
            room_context: Context about the room (type, style, etc.)

        Returns:
            Filtered products suitable for the room
        """
        room_type = room_context.get('room_type')
        if not room_type:
            return products

        # Get relevant categories for this room
        relevant_categories = self.get_room_categories(room_type)

        # For now, we can't filter by category ID without proper category mapping
        # This would require database queries to resolve category names to IDs
        # So we'll return all products for now

        logger.info(f"Room context filtering for {room_type} with {len(relevant_categories)} relevant categories")
        return products
