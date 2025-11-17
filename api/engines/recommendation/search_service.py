"""
Search Service for Product Discovery

Handles product search, keyword extraction, and categorization.
"""
import logging
import re
from typing import List, Dict, Set
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from database.models import Product

logger = logging.getLogger(__name__)


class SearchService:
    """Service for product search and discovery"""

    def __init__(self):
        self.product_categories = self._define_product_categories()
        logger.info("SearchService initialized")

    def _define_product_categories(self) -> Dict[str, List[str]]:
        """Define product categories for keyword classification"""
        return {
            'ceiling_lighting': ['ceiling lamp', 'ceiling light', 'chandelier', 'pendant', 'overhead light', 'pendant light'],
            'portable_lighting': ['table lamp', 'desk lamp', 'floor lamp'],
            'wall_lighting': ['wall lamp', 'sconce', 'wall light'],
            'seating_furniture': ['sofa', 'couch', 'sectional', 'loveseat', 'chair', 'armchair', 'recliner', 'bench', 'stool', 'ottoman'],
            'center_tables': ['coffee table', 'center table', 'centre table'],
            'side_tables': ['side table', 'end table', 'nightstand', 'bedside table'],
            'dining_tables': ['dining table'],
            'other_tables': ['console table', 'desk', 'table'],
            'storage_furniture': ['dresser', 'chest', 'cabinet', 'bookshelf', 'shelving', 'shelf', 'wardrobe'],
            'bedroom_furniture': ['bed', 'mattress', 'headboard'],
            'decor': ['mirror', 'rug', 'carpet', 'mat'],
            'general_lighting': ['lamp', 'lighting'],
        }

    def categorize_keywords(self, keywords: List[str]) -> Dict[str, List[str]]:
        """
        Categorize keywords into product categories to enable strict filtering

        Args:
            keywords: List of search keywords

        Returns:
            Dictionary mapping category names to keywords in that category
        """
        # Create reverse mapping from keyword to category
        keyword_to_category = {}
        for category, terms in self.product_categories.items():
            for term in terms:
                keyword_to_category[term.lower()] = category

        # Group keywords by category
        categorized = defaultdict(list)
        for keyword in keywords:
            category = keyword_to_category.get(keyword.lower())
            if category:
                categorized[category].append(keyword)
            else:
                # Unknown keyword - put in its own category
                categorized['other'].append(keyword)

        logger.info(f"Categorized keywords: {dict(categorized)}")
        return dict(categorized)

    async def search_products(
        self,
        keywords: List[str],
        db: AsyncSession,
        budget_range: tuple = None,
        exclude_products: List[str] = None,
        limit: int = 1000
    ) -> List[Product]:
        """
        Search for products using keywords with category-aware filtering

        Args:
            keywords: Search keywords
            db: Database session
            budget_range: Optional (min, max) price range
            exclude_products: Optional list of product IDs to exclude
            limit: Maximum number of results

        Returns:
            List of matching products
        """
        query = select(Product).where(Product.is_available == True)

        # Apply keyword filtering with category awareness
        if keywords:
            logger.info(f"Searching products with keywords: {keywords}")

            # Categorize keywords
            categorized_keywords = self.categorize_keywords(keywords)

            # Build category-aware query conditions
            category_conditions = []
            for category, kw_list in categorized_keywords.items():
                keyword_conditions = []
                for keyword in kw_list:
                    # Use PostgreSQL regex with word boundaries
                    escaped_keyword = re.escape(keyword)
                    keyword_conditions.append(Product.name.op('~*')(rf'\y{escaped_keyword}\y'))
                    keyword_conditions.append(Product.description.op('~*')(rf'\y{escaped_keyword}\y'))

                if keyword_conditions:
                    category_conditions.append(or_(*keyword_conditions))

            # Combine category conditions
            if category_conditions:
                if len(category_conditions) == 1:
                    query = query.where(category_conditions[0])
                else:
                    query = query.where(or_(*category_conditions))

            logger.info(f"Applied category-aware filtering for {len(category_conditions)} categories")

        # Apply budget filter
        if budget_range:
            min_price, max_price = budget_range
            query = query.where(Product.price >= min_price, Product.price <= max_price)

        # Exclude specific products
        if exclude_products:
            query = query.where(~Product.id.in_(exclude_products))

        # Eagerly load images
        query = query.options(selectinload(Product.images))

        # Apply limit
        query = query.limit(limit)

        result = await db.execute(query)
        products = result.scalars().all()

        logger.info(f"Found {len(products)} products matching search criteria")
        return products

    def extract_search_keywords(self, query: str) -> List[str]:
        """
        Extract search keywords from natural language query

        Args:
            query: Natural language search query

        Returns:
            List of extracted keywords
        """
        # Lowercase the query
        query = query.lower()

        # Remove common words (simple stopword removal)
        stopwords = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'for', 'in', 'on', 'at', 'to', 'with'}
        words = [w for w in query.split() if w not in stopwords]

        # Check for multi-word category matches
        keywords = []
        for category, terms in self.product_categories.items():
            for term in terms:
                if term in query:
                    keywords.append(term)

        # Add individual words not already captured
        for word in words:
            if word not in keywords and len(word) > 2:
                keywords.append(word)

        return keywords
