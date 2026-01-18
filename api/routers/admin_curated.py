"""
Admin API routes for managing curated looks
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.curated import (
    CuratedLookCreate,
    CuratedLookListResponse,
    CuratedLookProductSchema,
    CuratedLookProductUpdate,
    CuratedLookSchema,
    CuratedLookSummarySchema,
    CuratedLookUpdate,
)
from services.embedding_service import EmbeddingService
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.auth import require_admin
from core.database import get_db
from database.models import BudgetTier, Category, CuratedLook, CuratedLookProduct, Product, ProductAttribute, User

# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def calculate_budget_tier(total_price: float) -> str:
    """
    Calculate budget tier based on total price.

    Thresholds (in INR):
    - Pocket-friendly: < ₹2L (< 200,000)
    - Mid-tier: ₹2L – ₹8L (200,000 - 800,000)
    - Premium: ₹8L – ₹15L (800,000 - 1,500,000)
    - Luxury: ₹15L+ (>= 1,500,000)
    """
    if total_price < 200000:
        return "pocket_friendly"
    elif total_price < 800000:
        return "mid_tier"
    elif total_price < 1500000:
        return "premium"
    else:
        return "luxury"


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/curated", tags=["admin-curated"])


# Simple singular/plural normalization
def normalize_singular_plural(word: str) -> list:
    """
    Returns both singular and plural forms of a word.
    Handles common English patterns and hyphenated words.
    """
    word = word.lower().strip()
    forms = [word]

    # Common irregular plurals
    irregulars = {
        "furniture": "furniture",  # Uncountable
        "decor": "decor",
        "seating": "seating",
    }

    if word in irregulars:
        return [word]

    # Handle hyphenated words (e.g., "l-shaped" -> "l-shape", "l shaped", "l shape")
    if "-" in word:
        # Add space-separated version: "l-shaped" -> "l shaped"
        space_version = word.replace("-", " ")
        forms.append(space_version)

        # If ends in "-shaped", also add "-shape" version: "l-shaped" -> "l-shape", "l shape"
        if word.endswith("-shaped"):
            no_d_version = word[:-1]  # "l-shaped" -> "l-shape"
            forms.append(no_d_version)
            forms.append(no_d_version.replace("-", " "))  # "l-shape" -> "l shape"
        elif word.endswith("ed"):
            # Generic -ed handling for hyphenated words
            no_d_version = word[:-1]
            forms.append(no_d_version)
            forms.append(no_d_version.replace("-", " "))

    # If word ends in 's', try to get singular
    if word.endswith("ies"):
        # categories -> category
        forms.append(word[:-3] + "y")
    elif word.endswith("es"):
        # boxes -> box, dishes -> dish
        if word.endswith("sses") or word.endswith("shes") or word.endswith("ches") or word.endswith("xes"):
            forms.append(word[:-2])
        else:
            forms.append(word[:-1])  # tables -> table (via 'es' -> 'e')
            forms.append(word[:-2])  # boxes -> box
    elif word.endswith("s") and not word.endswith("ss"):
        # sculptures -> sculpture
        forms.append(word[:-1])

    # If word doesn't end in 's', try to get plural
    if not word.endswith("s"):
        if word.endswith("y") and len(word) > 2 and word[-2] not in "aeiou":
            # category -> categories
            forms.append(word[:-1] + "ies")
        elif word.endswith(("s", "sh", "ch", "x", "z")):
            # box -> boxes
            forms.append(word + "es")
        else:
            # sculpture -> sculptures
            forms.append(word + "s")

    return list(set(forms))  # Remove duplicates


# Exclusion dictionary - when searching for key, exclude products containing these terms
# This prevents "center table" search from returning "dining table" etc.
SEARCH_EXCLUSIONS = {
    "center table": ["dining", "console", "side table", "end table", "nightstand"],
    "centre table": ["dining", "console", "side table", "end table", "nightstand"],
    "coffee table": ["dining", "console", "side table", "end table", "nightstand"],
    "dining table": ["center", "centre", "coffee", "side table", "end table", "console"],
    "side table": ["dining", "center", "centre", "coffee"],
    "end table": ["dining", "center", "centre", "coffee"],
    "console table": ["dining", "center", "centre", "coffee", "side table"],
    "nightstand": ["dining", "center", "centre", "coffee", "console"],
    "bedside table": ["dining", "center", "centre", "coffee", "console"],
}

# Synonym dictionary for search terms - maps search term to list of synonyms
SEARCH_SYNONYMS = {
    "carpet": ["rug", "carpet", "runner", "mat", "floor covering"],
    "rug": ["rug", "carpet", "runner", "mat", "floor covering"],
    "sofa": ["sofa", "couch", "settee", "sectional"],
    "sofas": ["sofa", "couch", "settee", "sectional"],
    "couch": ["sofa", "couch", "settee", "sectional"],
    "couches": ["sofa", "couch", "settee", "sectional"],
    # L-shaped / corner / sectional sofa synonyms
    "l-shaped": ["l-shaped", "l-shape", "l shaped", "l shape", "corner", "sectional"],
    "l-shape": ["l-shaped", "l-shape", "l shaped", "l shape", "corner", "sectional"],
    "corner": ["corner", "l-shaped", "l-shape", "l shaped", "l shape", "sectional"],
    "sectional": ["sectional", "l-shaped", "l-shape", "l shaped", "l shape", "corner", "chaise"],
    "sectionals": ["sectional", "l-shaped", "l-shape", "l shaped", "l shape", "corner", "chaise"],
    "cupboard": ["cupboard", "cabinet", "wardrobe", "armoire"],
    "cabinet": ["cupboard", "cabinet", "wardrobe", "armoire"],
    "lamp": ["lamp", "floor lamp", "standing lamp", "table lamp"],
    "lamps": ["lamp", "floor lamp", "standing lamp", "table lamp"],
    "floor lamp": ["floor lamp", "standing lamp", "lamp"],
    "standing lamp": ["standing lamp", "floor lamp", "lamp"],
    "table lamp": ["table lamp", "desk lamp", "lamp"],
    "light": ["light", "lighting", "chandelier", "pendant light"],
    "lights": ["light", "lighting", "chandelier", "pendant light"],
    "chandelier": ["chandelier", "pendant light", "ceiling light"],
    "table": ["table", "desk"],
    # Center/Centre table synonyms (American vs British spelling)
    "center": ["center", "centre"],
    "centre": ["centre", "center"],
    "coffee": ["coffee", "center", "centre"],  # Coffee tables are similar to center tables
    "tables": ["table", "desk"],
    "desk": ["table", "desk"],
    "desks": ["table", "desk"],
    "chair": ["chair", "seat", "seating"],
    "chairs": ["chair", "seat", "seating"],
    "curtain": ["curtain", "drape", "drapes", "blind", "blinds"],
    "curtains": ["curtain", "drape", "drapes", "blind", "blinds"],
    "drape": ["curtain", "drape", "drapes"],
    "drapes": ["curtain", "drape", "drapes"],
    # Bedroom furniture - handle plurals
    "bed": ["bed", "bedframe", "bed frame"],
    "beds": ["bed", "bedframe", "bed frame"],
    "bedside table": ["bedside table", "nightstand", "night stand", "bedside"],
    "bedside tables": ["bedside table", "nightstand", "night stand", "bedside"],
    "nightstand": ["nightstand", "bedside table", "night stand", "bedside"],
    "nightstands": ["nightstand", "bedside table", "night stand", "bedside"],
    # Planters and pots
    "planter": ["planter", "pot", "plant pot", "flower pot"],
    "planters": ["planter", "pot", "plant pot", "flower pot"],
    "pot": ["pot", "planter", "plant pot", "flower pot"],
    "pots": ["pot", "planter", "plant pot", "flower pot"],
    # Wall art and paintings
    "painting": ["painting", "wall art", "artwork", "canvas art", "art print"],
    "paintings": ["painting", "wall art", "artwork", "canvas art", "art print"],
    "wall art": ["wall art", "painting", "artwork", "canvas art", "art print", "wall decor"],
    "wall decor": ["wall decor", "wall art", "painting", "artwork", "canvas art"],
    "artwork": ["artwork", "wall art", "painting", "canvas art", "art print"],
    "art": ["art", "wall art", "painting", "artwork", "art print"],
    # Storage furniture - drawers, dressers, chests
    "drawer": ["drawer", "drawers", "chest of drawers", "dresser", "chest"],
    "drawers": ["drawer", "drawers", "chest of drawers", "dresser", "chest"],
    "draws": ["drawer", "drawers", "chest of drawers", "dresser", "chest"],  # Common misspelling
    "chest of drawers": ["chest of drawers", "drawer", "drawers", "dresser", "chest"],
    "chest of draws": ["chest of drawers", "drawer", "drawers", "dresser", "chest"],  # Common misspelling
    "dresser": ["dresser", "drawer", "drawers", "chest of drawers", "chest"],
    "dressers": ["dresser", "drawer", "drawers", "chest of drawers", "chest"],
    "storage": ["storage", "cabinet", "cupboard", "drawer", "shelf", "shelves"],
    "storage unit": ["storage", "cabinet", "cupboard", "drawer", "shelf"],
    "storage units": ["storage", "cabinet", "cupboard", "drawer", "shelf"],
}


def expand_search_query(query: str) -> list:
    """Expand a search query to include synonyms and singular/plural forms.

    For single-word queries, returns flat list of synonyms.
    For multi-word queries, returns flat list but search logic handles AND between words.
    """
    query_lower = query.lower().strip()

    # Split query into words for multi-word searches
    words = query_lower.split()

    # For single-word queries, use original logic
    if len(words) == 1:
        # Check if query matches any synonym key directly
        for key, synonyms in SEARCH_SYNONYMS.items():
            if key == query_lower or query_lower == key:
                return synonyms

        # Try singular/plural forms
        word_forms = normalize_singular_plural(query_lower)
        for form in word_forms:
            for key, synonyms in SEARCH_SYNONYMS.items():
                if key == form or form == key:
                    return synonyms

        logger.info(f"No synonym match for '{query}', using singular/plural forms: {word_forms}")
        return word_forms

    # For multi-word queries, collect all terms and their synonyms
    all_terms = set()

    for word in words:
        # Check for direct synonym match
        matched = False
        for key, synonyms in SEARCH_SYNONYMS.items():
            if key == word or word == key:
                all_terms.update(synonyms)
                matched = True
                break

        # If no synonym match, add the word itself (and its singular/plural forms)
        if not matched:
            word_forms = normalize_singular_plural(word)
            all_terms.update(word_forms)

    result = list(all_terms)
    logger.info(f"Multi-word query '{query}' expanded to: {result}")
    return result


def expand_search_query_grouped(query: str) -> List[List[str]]:
    """Expand a search query and return GROUPED synonyms for AND logic.

    Returns list of lists: [[synonyms for word1], [synonyms for word2], ...]
    Search should match: (any of group1) AND (any of group2) AND ...

    Example: "L-shaped sofa" -> [["l-shaped", "l-shapeds"], ["sofa", "couch", "settee"]]
    """
    query_lower = query.lower().strip()
    words = query_lower.split()

    if len(words) == 1:
        # Single word - return as single group
        for key, synonyms in SEARCH_SYNONYMS.items():
            if key == query_lower or query_lower == key:
                return [synonyms]

        word_forms = normalize_singular_plural(query_lower)
        for form in word_forms:
            for key, synonyms in SEARCH_SYNONYMS.items():
                if key == form or form == key:
                    return [synonyms]

        return [word_forms]

    # Multi-word query - create groups for each word
    groups = []
    for word in words:
        matched = False
        for key, synonyms in SEARCH_SYNONYMS.items():
            if key == word or word == key:
                groups.append(list(synonyms))
                matched = True
                break

        if not matched:
            word_forms = normalize_singular_plural(word)
            groups.append(word_forms)

    logger.info(f"Multi-word query '{query}' grouped to: {groups}")
    return groups


def get_exclusion_terms(query: str) -> List[str]:
    """Get list of terms to exclude from search results based on query.

    Example: "center table" -> ["dining", "console", "side table", "end table", "nightstand"]
    """
    query_lower = query.lower().strip()

    # Check for exact match first
    if query_lower in SEARCH_EXCLUSIONS:
        return SEARCH_EXCLUSIONS[query_lower]

    # Check if query contains any exclusion key
    for key, exclusions in SEARCH_EXCLUSIONS.items():
        if key in query_lower:
            return exclusions

    return []


def should_exclude_product(product_name: str, exclusion_terms: List[str]) -> bool:
    """Check if a product should be excluded based on exclusion terms."""
    if not exclusion_terms:
        return False

    name_lower = product_name.lower()
    for term in exclusion_terms:
        if term.lower() in name_lower:
            return True
    return False


async def semantic_search_products(
    query_text: str,
    db: AsyncSession,
    source_websites: Optional[List[str]] = None,
    category_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 500,
) -> Dict[int, float]:
    """
    Perform semantic search using embeddings.

    Returns dict mapping product_id to similarity score (0.0 to 1.0).
    Only searches products that have embeddings.
    """
    embedding_service = get_embedding_service()

    # Get query embedding
    query_embedding = await embedding_service.get_query_embedding(query_text)
    if not query_embedding:
        logger.warning(f"[SEMANTIC SEARCH] Failed to generate embedding for: {query_text[:50]}...")
        return {}

    logger.info(f"[SEMANTIC SEARCH] Generated query embedding for: {query_text[:50]}...")

    # Build query for products with embeddings
    query = select(Product.id, Product.embedding).where(Product.is_available.is_(True)).where(Product.embedding.isnot(None))

    # Apply filters
    if source_websites:
        query = query.where(Product.source_website.in_(source_websites))

    if category_id:
        query = query.where(Product.category_id == category_id)

    if min_price is not None:
        query = query.where(Product.price >= min_price)

    if max_price is not None:
        query = query.where(Product.price <= max_price)

    # Execute query
    result = await db.execute(query)
    rows = result.fetchall()

    logger.info(f"[SEMANTIC SEARCH] Found {len(rows)} products with embeddings")

    if not rows:
        return {}

    # Calculate similarity scores
    similarity_scores: Dict[int, float] = {}

    for product_id, embedding_json in rows:
        try:
            product_embedding = json.loads(embedding_json)
            similarity = embedding_service.compute_cosine_similarity(query_embedding, product_embedding)
            similarity_scores[product_id] = similarity
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"[SEMANTIC SEARCH] Error processing product {product_id}: {e}")
            continue

    # Sort by similarity and take top N
    sorted_scores = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    result_dict = dict(sorted_scores)

    if result_dict:
        top_score = sorted_scores[0][1] if sorted_scores else 0
        logger.info(f"[SEMANTIC SEARCH] Top similarity score: {top_score:.3f}, returning {len(result_dict)} products")

    return result_dict


def get_primary_image_url(product: Product) -> Optional[str]:
    """Get the primary image URL for a product"""
    if not product.images:
        return None
    primary = next((img for img in product.images if img.is_primary), None)
    if primary:
        return primary.original_url
    return product.images[0].original_url if product.images else None


async def fetch_curated_look_with_products(look_id: int, db: AsyncSession) -> CuratedLookSchema:
    """Helper function to fetch a curated look with full details - can be called directly"""
    query = (
        select(CuratedLook)
        .where(CuratedLook.id == look_id)
        .options(selectinload(CuratedLook.products).selectinload(CuratedLookProduct.product).selectinload(Product.images))
    )
    result = await db.execute(query)
    look = result.scalar_one_or_none()

    if not look:
        raise HTTPException(status_code=404, detail="Curated look not found")

    # Build product list with details
    products = []
    for lp in sorted(look.products, key=lambda x: x.display_order or 0):
        product = lp.product
        if product:
            products.append(
                CuratedLookProductSchema(
                    id=product.id,
                    name=product.name,
                    price=product.price,
                    image_url=get_primary_image_url(product),
                    source_website=product.source_website,
                    source_url=product.source_url,
                    product_type=lp.product_type,
                    quantity=lp.quantity or 1,
                    description=product.description,
                )
            )

    return CuratedLookSchema(
        id=look.id,
        title=look.title,
        style_theme=look.style_theme,
        style_description=look.style_description,
        style_labels=look.style_labels or [],
        room_type=look.room_type,
        room_image=look.room_image,
        visualization_image=look.visualization_image,
        total_price=look.total_price or 0,
        budget_tier=look.budget_tier if look.budget_tier else None,
        is_published=look.is_published,
        display_order=look.display_order or 0,
        products=products,
        created_at=look.created_at,
        updated_at=look.updated_at,
    )


# NOTE: These routes MUST be defined BEFORE the /{look_id} route
# otherwise FastAPI will try to match "categories" or "search" as a look_id


@router.get("/categories")
async def get_product_categories(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get all product categories for filtering"""
    try:
        # Get categories that have products
        query = select(Category).order_by(Category.name)
        result = await db.execute(query)
        categories = result.scalars().all()

        return {"categories": [{"id": c.id, "name": c.name, "slug": c.slug} for c in categories]}

    except Exception as e:
        logger.error(f"Error fetching categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching categories")


@router.get("/search/products")
async def search_products_for_look(
    query: Optional[str] = Query(None, min_length=1),
    category_id: Optional[int] = Query(None),
    source_website: Optional[str] = Query(None, description="Comma-separated list of stores to filter by"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    colors: Optional[str] = Query(None, description="Comma-separated list of colors"),
    styles: Optional[str] = Query(None, description="Comma-separated list of primary_style values"),
    materials: Optional[str] = Query(None, description="Comma-separated list of materials"),
    use_semantic: bool = Query(True, description="Use semantic search (embeddings) when available"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(50, ge=1, le=200, description="Number of products per page"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Search for products to add to a curated look. Uses semantic search + keyword fallback with pagination."""
    try:
        semantic_product_ids: Dict[int, float] = {}
        search_groups = []

        # Parse comma-separated stores into a list
        source_websites: Optional[List[str]] = None
        if source_website:
            source_websites = [s.strip() for s in source_website.split(",") if s.strip()]
            if not source_websites:
                source_websites = None

        # Step 1: Try semantic search first (for products with embeddings)
        # Get all semantic matches (we'll paginate the combined results later)
        if query and use_semantic:
            try:
                semantic_product_ids = await semantic_search_products(
                    query_text=query,
                    db=db,
                    source_websites=source_websites,
                    category_id=category_id,
                    min_price=min_price,
                    max_price=max_price,
                    limit=10000,  # Get all semantic matches, pagination happens later
                )
                logger.info(f"[SEARCH] Semantic search returned {len(semantic_product_ids)} products")
            except Exception as e:
                logger.warning(f"[SEARCH] Semantic search failed, falling back to keyword: {e}")
                semantic_product_ids = {}

        # Step 2: Build keyword search query (for products without embeddings or as fallback)
        search_query = select(Product).options(selectinload(Product.images)).where(Product.is_available.is_(True))

        logger.info(f"[SEARCH DEBUG] query='{query}', source_websites={source_websites}, page={page}")

        # Apply text search if query provided (with synonym expansion for name only)
        if query:
            # Use grouped expansion for AND logic between word groups
            search_groups = expand_search_query_grouped(query)
            logger.info(f"Search query '{query}' expanded to groups: {search_groups}")

            # Build AND conditions: product must match at least one term from EACH group
            # Example: "L-shaped sofa" -> must match (l-shaped OR l-shapeds) AND (sofa OR couch OR settee)
            and_conditions = []
            for group in search_groups:
                group_conditions = []
                for term in group:
                    escaped_term = re.escape(term)
                    # Use PostgreSQL regex with word boundaries (\y) for accurate matching
                    group_conditions.append(Product.name.op("~*")(rf"\y{escaped_term}\y"))
                if group_conditions:
                    # OR within each group
                    and_conditions.append(or_(*group_conditions))

            # Broad terms that should NOT match in description (too many false positives)
            BROAD_TERMS = {"decor", "art", "furniture", "home", "living", "style", "design"}

            # Also match original query in brand and description with word boundaries
            escaped_query = re.escape(query)
            query_lower = query.lower().strip()

            original_query_conditions = [
                Product.brand.op("~*")(rf"\y{escaped_query}\y"),
            ]

            # Only match description for specific (non-broad) terms
            if query_lower not in BROAD_TERMS:
                original_query_conditions.append(Product.description.op("~*")(rf"\y{escaped_query}\y"))

            # Final condition: (all AND conditions from groups) OR (original query in brand/description)
            if and_conditions:
                # AND between all groups
                grouped_condition = and_(*and_conditions)
                # OR with brand/description match for full phrase
                all_conditions = [grouped_condition] + original_query_conditions
                search_query = search_query.where(or_(*all_conditions))

        # Filter by category if specified
        if category_id:
            search_query = search_query.where(Product.category_id == category_id)

        # Filter by store(s) if specified
        if source_websites:
            search_query = search_query.where(Product.source_website.in_(source_websites))

        # Filter by price range
        if min_price is not None:
            search_query = search_query.where(Product.price >= min_price)
        if max_price is not None:
            search_query = search_query.where(Product.price <= max_price)

        # Filter by colors (search in name, description, color field)
        if colors:
            color_list = [c.strip().lower() for c in colors.split(",")]
            color_conditions = []
            for color in color_list:
                color_conditions.append(or_(Product.name.ilike(f"%{color}%"), Product.description.ilike(f"%{color}%")))
            if color_conditions:
                search_query = search_query.where(or_(*color_conditions))

        # Filter by styles (uses Product.primary_style field)
        if styles:
            style_list = [s.strip().lower() for s in styles.split(",") if s.strip()]
            if style_list:
                # OR logic: match any of the selected styles
                search_query = search_query.where(func.lower(Product.primary_style).in_(style_list))

        # Filter by materials (uses ProductAttribute with material/material_primary)
        if materials:
            material_list = [m.strip().lower() for m in materials.split(",") if m.strip()]
            if material_list:
                # Subquery to find products with matching materials in ProductAttribute
                material_subquery = (
                    select(ProductAttribute.product_id)
                    .where(ProductAttribute.attribute_name.in_(["material", "material_primary"]))
                    .where(func.lower(ProductAttribute.attribute_value).in_(material_list))
                )
                search_query = search_query.where(Product.id.in_(material_subquery))

        # Order by: match priority (name > brand > description), then price
        # This ensures "paintings" shows actual paintings first, not rugs that mention paintings
        if query:
            escaped_query = re.escape(query)
            # Build name match condition for ALL expanded search terms (flatten the groups)
            all_search_terms = [term for group in search_groups for term in group]
            name_match_conditions = [Product.name.op("~*")(rf"\y{re.escape(term)}\y") for term in all_search_terms]
            # Case expression to prioritize matches by field:
            # - Priority 0: Name matches ANY synonym (most relevant - actual paintings/wall art)
            # - Priority 1: Brand matches
            # - Priority 2: Description matches (least relevant - rugs mentioning paintings)
            match_priority = case(
                (or_(*name_match_conditions), 0),  # Name matches any synonym - highest priority
                (Product.brand.op("~*")(rf"\y{escaped_query}\y"), 1),  # Brand match - medium priority
                else_=2,  # Description only match - lowest priority
            )
            search_query = search_query.order_by(match_priority, Product.price.desc().nullslast())
        else:
            search_query = search_query.order_by(Product.price.desc().nullslast())

        # Get all keyword matches (no limit - we paginate combined results)
        search_query = search_query.limit(10000)

        result = await db.execute(search_query)
        keyword_products = result.scalars().unique().all()

        # STEP 3: Merge semantic and keyword results into ordered list of product IDs
        # Priority: semantic matches first (sorted by similarity), then keyword-only matches
        ordered_product_ids: List[int] = []
        semantic_scores: Dict[int, float] = {}
        seen_product_ids = set()

        # Get exclusion terms for the query (e.g., "center table" excludes "dining")
        exclusion_terms = get_exclusion_terms(query) if query else []
        if exclusion_terms:
            logger.info(f"[SEARCH] Exclusion terms for '{query}': {exclusion_terms}")

        # Helper: Check if product name matches ALL search groups (for primary match)
        def name_matches_all_groups(product_name: str, groups: List[List[str]]) -> bool:
            """Check if product name contains at least one term from EACH group."""
            if not groups:
                return True
            name_lower = product_name.lower()
            # Normalize: "L - Shaped" -> "l-shaped"
            name_normalized = re.sub(r"\s*-\s*", "-", name_lower)
            name_spaced = re.sub(r"-", " ", name_lower)  # Also try with spaces

            for group in groups:
                group_matched = False
                for term in group:
                    term_normalized = re.sub(r"\s*-\s*", "-", term.lower())
                    # Check various forms
                    if term_normalized in name_normalized or term_normalized in name_spaced:
                        group_matched = True
                        break
                    # Also check with spaces
                    term_spaced = re.sub(r"-", " ", term.lower())
                    if term_spaced in name_lower or term_spaced in name_spaced:
                        group_matched = True
                        break
                if not group_matched:
                    return False
            return True

        if semantic_product_ids:
            # First, include products from semantic search that ALSO match keyword search
            # This prevents "carpet" search from returning cushions/curtains just because they're semantically similar
            semantic_threshold = 0.3
            semantic_sorted = sorted(semantic_product_ids.items(), key=lambda x: x[1], reverse=True)

            # Get the set of keyword-matching product IDs and names
            keyword_product_ids = {p.id for p in keyword_products}
            keyword_product_names = {p.id: p.name for p in keyword_products}

            # If we have exclusion terms, we need to fetch names for semantic-only products
            semantic_only_names = {}
            if exclusion_terms:
                semantic_only_ids = [pid for pid, _ in semantic_sorted if pid not in keyword_product_ids]
                if semantic_only_ids:
                    names_query = select(Product.id, Product.name).where(Product.id.in_(semantic_only_ids))
                    names_result = await db.execute(names_query)
                    semantic_only_names = {row[0]: row[1] for row in names_result.fetchall()}

            excluded_count = 0
            for product_id, similarity in semantic_sorted:
                if similarity >= semantic_threshold:
                    # Only include semantic results that also match keyword search
                    # OR have very high similarity (>= 0.5) for genuine semantic matches
                    if product_id in keyword_product_ids or similarity >= 0.5:
                        # Check exclusion terms
                        product_name = keyword_product_names.get(product_id) or semantic_only_names.get(product_id, "")
                        if exclusion_terms and should_exclude_product(product_name, exclusion_terms):
                            excluded_count += 1
                            continue

                        ordered_product_ids.append(product_id)
                        semantic_scores[product_id] = similarity
                        seen_product_ids.add(product_id)

            logger.info(
                f"[SEARCH] Added {len(seen_product_ids)} semantic results (threshold={semantic_threshold}, keyword-filtered, {excluded_count} excluded)"
            )

        # Add keyword-only results (products without embeddings or below semantic threshold)
        excluded_keyword_count = 0
        for p in keyword_products:
            if p.id not in seen_product_ids:
                # Check exclusion terms
                if exclusion_terms and should_exclude_product(p.name, exclusion_terms):
                    excluded_keyword_count += 1
                    continue
                ordered_product_ids.append(p.id)
                seen_product_ids.add(p.id)

        if excluded_keyword_count > 0:
            logger.info(f"[SEARCH] Excluded {excluded_keyword_count} keyword results due to exclusion terms")

        total_results = len(ordered_product_ids)

        # Calculate total_primary and total_related by fetching ALL product names
        # This is needed for accurate counts across pagination
        total_primary = 0
        total_related = 0
        if ordered_product_ids and search_groups:
            # Fetch just names for all products (efficient - no images/full data)
            names_query = select(Product.id, Product.name).where(Product.id.in_(ordered_product_ids))
            names_result = await db.execute(names_query)
            all_products_names = {row[0]: row[1] for row in names_result.fetchall()}

            for product_id in ordered_product_ids:
                name = all_products_names.get(product_id, "")
                if name_matches_all_groups(name, search_groups):
                    total_primary += 1
                else:
                    total_related += 1

            logger.info(f"[SEARCH] Total counts: {total_primary} primary, {total_related} related (out of {total_results})")
        else:
            # No search query - all are primary matches
            total_primary = total_results
            total_related = 0

        # STEP 4: Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_product_ids = ordered_product_ids[start_idx:end_idx]
        has_more = end_idx < total_results

        # STEP 5: Fetch product details for this page
        if page_product_ids:
            products_query = select(Product).options(selectinload(Product.images)).where(Product.id.in_(page_product_ids))
            products_result = await db.execute(products_query)
            products_map = {p.id: p for p in products_result.scalars().unique().all()}

            # Build response in the correct order
            final_products = []
            for product_id in page_product_ids:
                if product_id in products_map:
                    p = products_map[product_id]
                    similarity = semantic_scores.get(product_id, 0)

                    # Primary match = product name contains ALL search terms (using synonym groups)
                    # This is more accurate than similarity threshold for specific queries like "L-shaped sofa"
                    is_primary = name_matches_all_groups(p.name, search_groups) if search_groups else True

                    product_data = {
                        "id": p.id,
                        "name": p.name,
                        "price": p.price,
                        "image_url": get_primary_image_url(p),
                        "source_website": p.source_website,
                        "source_url": p.source_url,
                        "brand": p.brand,
                        "category_id": p.category_id,
                        "description": p.description,
                        "is_primary_match": is_primary,
                        "similarity_score": round(similarity, 3) if similarity > 0 else None,
                    }
                    final_products.append(product_data)
        else:
            final_products = []

        # Count primary matches in this page
        page_primary_count = sum(1 for p in final_products if p.get("is_primary_match"))
        logger.info(
            f"[SEARCH] Page {page}: {len(final_products)} products, {page_primary_count} primary (name matches all search terms)"
        )

        return {
            "products": final_products,
            "total": total_results,
            "total_primary": total_primary,
            "total_related": total_related,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        }

    except Exception as e:
        logger.error(f"Error searching products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching products")


@router.get("/", response_model=CuratedLookListResponse)
async def list_curated_looks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    room_type: Optional[str] = Query(None),
    is_published: Optional[bool] = Query(None),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all curated looks with pagination (admin view)"""
    try:
        # Build base query
        query = select(CuratedLook).options(selectinload(CuratedLook.products))

        # Apply filters
        if room_type:
            query = query.where(CuratedLook.room_type == room_type)
        if is_published is not None:
            query = query.where(CuratedLook.is_published == is_published)

        # Order by: published first, then display_order, then created_at
        query = query.order_by(
            CuratedLook.is_published.desc(),  # Published first
            CuratedLook.display_order.asc(),
            CuratedLook.created_at.desc()
        )

        # Get total count
        count_query = select(func.count()).select_from(CuratedLook)
        if room_type:
            count_query = count_query.where(CuratedLook.room_type == room_type)
        if is_published is not None:
            count_query = count_query.where(CuratedLook.is_published == is_published)

        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)

        # Execute query
        result = await db.execute(query)
        looks = result.scalars().unique().all()

        # Calculate pagination
        pages = (total + size - 1) // size if total else 0
        has_next = page < pages
        has_prev = page > 1

        # Convert to summary schemas
        look_summaries = [
            CuratedLookSummarySchema(
                id=look.id,
                title=look.title,
                style_theme=look.style_theme,
                style_description=look.style_description,
                style_labels=look.style_labels or [],
                room_type=look.room_type,
                visualization_image=look.visualization_image,
                total_price=look.total_price or 0,
                budget_tier=look.budget_tier if look.budget_tier else None,
                is_published=look.is_published,
                display_order=look.display_order or 0,
                product_count=len(look.products) if look.products else 0,
                created_at=look.created_at,
            )
            for look in looks
        ]

        return CuratedLookListResponse(
            items=look_summaries, total=total, page=page, size=size, pages=pages, has_next=has_next, has_prev=has_prev
        )

    except Exception as e:
        logger.error(f"Error listing curated looks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching curated looks")


@router.get("/{look_id}", response_model=CuratedLookSchema)
async def get_curated_look(
    look_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get a single curated look with full details"""
    try:
        return await fetch_curated_look_with_products(look_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching curated look")


@router.post("/", response_model=CuratedLookSchema)
async def create_curated_look(
    look_data: CuratedLookCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new curated look"""
    # Log request details
    viz_size = len(look_data.visualization_image) if look_data.visualization_image else 0
    room_size = len(look_data.room_image) if look_data.room_image else 0
    logger.info(
        f"[Create Curated Look] Received: title='{look_data.title}', viz_size={viz_size/1024:.1f}KB, room_size={room_size/1024:.1f}KB, products={len(look_data.product_ids)}"
    )

    try:
        # Create the look (budget_tier will be auto-calculated after products are added)
        look = CuratedLook(
            title=look_data.title,
            style_theme=look_data.style_theme,
            style_description=look_data.style_description,
            style_labels=look_data.style_labels or [],
            room_type=look_data.room_type.value,
            room_image=look_data.room_image,
            visualization_image=look_data.visualization_image,
            is_published=look_data.is_published,
            display_order=look_data.display_order,
            total_price=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(look)
        await db.flush()  # Get the ID

        # Add products if provided
        total_price = 0
        product_types = look_data.product_types or []
        product_quantities = look_data.product_quantities or []

        for i, product_id in enumerate(look_data.product_ids):
            # Verify product exists and get price
            product_query = select(Product).where(Product.id == product_id)
            product_result = await db.execute(product_query)
            product = product_result.scalar_one_or_none()

            if product:
                product_type = product_types[i] if i < len(product_types) else None
                quantity = product_quantities[i] if i < len(product_quantities) else 1
                look_product = CuratedLookProduct(
                    curated_look_id=look.id,
                    product_id=product_id,
                    product_type=product_type,
                    quantity=quantity,
                    display_order=i,
                    created_at=datetime.utcnow(),
                )
                db.add(look_product)
                if product.price:
                    total_price += product.price * quantity

        # Update total price and auto-calculate budget tier
        look.total_price = total_price
        look.budget_tier = calculate_budget_tier(total_price)
        await db.commit()
        await db.refresh(look)

        # Return the created look with full details
        # Note: Pre-computation happens after /visualize endpoint, not here
        return await fetch_curated_look_with_products(look.id, db)

    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating curated look: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating curated look: {str(e)}")


@router.put("/{look_id}", response_model=CuratedLookSchema)
async def update_curated_look(
    look_id: int,
    look_data: CuratedLookUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a curated look's details and optionally its products"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        # Update metadata fields if provided (budget_tier is auto-calculated, not manual)
        if look_data.title is not None:
            look.title = look_data.title
        if look_data.style_theme is not None:
            look.style_theme = look_data.style_theme
        if look_data.style_description is not None:
            look.style_description = look_data.style_description
        if look_data.style_labels is not None:
            look.style_labels = look_data.style_labels
        if look_data.room_type is not None:
            look.room_type = look_data.room_type.value
        if look_data.room_image is not None:
            look.room_image = look_data.room_image
        if look_data.visualization_image is not None:
            look.visualization_image = look_data.visualization_image
        if look_data.is_published is not None:
            look.is_published = look_data.is_published
        if look_data.display_order is not None:
            look.display_order = look_data.display_order

        # Update products if provided
        if look_data.product_ids is not None:
            logger.info(f"Updating products for look {look_id}: {len(look_data.product_ids)} products")

            # Delete existing products
            await db.execute(delete(CuratedLookProduct).where(CuratedLookProduct.curated_look_id == look_id))

            # Add new products with quantities
            total_price = 0
            product_types = look_data.product_types or []
            product_quantities = look_data.product_quantities or []

            for i, product_id in enumerate(look_data.product_ids):
                # Verify product exists and get price
                product_query = select(Product).where(Product.id == product_id)
                product_result = await db.execute(product_query)
                product = product_result.scalar_one_or_none()

                if product:
                    product_type = product_types[i] if i < len(product_types) else None
                    quantity = product_quantities[i] if i < len(product_quantities) else 1

                    logger.info(f"  Product {product_id}: type={product_type}, quantity={quantity}")

                    look_product = CuratedLookProduct(
                        curated_look_id=look_id,
                        product_id=product_id,
                        product_type=product_type,
                        quantity=quantity,
                        display_order=i,
                        created_at=datetime.utcnow(),
                    )
                    db.add(look_product)
                    if product.price:
                        total_price += product.price * quantity

            # Update total price and auto-calculate budget tier
            look.total_price = total_price
            look.budget_tier = calculate_budget_tier(total_price)

        look.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(look)

        # Note: Pre-computation happens after /visualize endpoint, not here
        return await fetch_curated_look_with_products(look_id, db)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating curated look")


@router.put("/{look_id}/products", response_model=CuratedLookSchema)
async def update_curated_look_products(
    look_id: int,
    product_data: CuratedLookProductUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update the products in a curated look"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        # Delete existing products
        await db.execute(delete(CuratedLookProduct).where(CuratedLookProduct.curated_look_id == look_id))

        # Add new products
        total_price = 0
        product_types = product_data.product_types or []

        for i, product_id in enumerate(product_data.product_ids):
            # Verify product exists and get price
            product_query = select(Product).where(Product.id == product_id)
            product_result = await db.execute(product_query)
            product = product_result.scalar_one_or_none()

            if product:
                product_type = product_types[i] if i < len(product_types) else None
                look_product = CuratedLookProduct(
                    curated_look_id=look_id,
                    product_id=product_id,
                    product_type=product_type,
                    display_order=i,
                    created_at=datetime.utcnow(),
                )
                db.add(look_product)
                if product.price:
                    total_price += product.price

        # Update total price and auto-calculate budget tier
        look.total_price = total_price
        look.budget_tier = calculate_budget_tier(total_price)
        look.updated_at = datetime.utcnow()
        await db.commit()

        return await fetch_curated_look_with_products(look_id, db)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating products for look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating curated look products")


@router.delete("/{look_id}")
async def delete_curated_look(
    look_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a curated look"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        # Delete associated products first (cascade should handle this, but being explicit)
        await db.execute(delete(CuratedLookProduct).where(CuratedLookProduct.curated_look_id == look_id))

        # Delete the look
        await db.delete(look)
        await db.commit()

        return {"message": "Curated look deleted successfully", "id": look_id}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error deleting curated look")


@router.post("/{look_id}/publish")
async def publish_curated_look(
    look_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Publish a curated look (make it visible to users)"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        look.is_published = True
        look.updated_at = datetime.utcnow()
        await db.commit()

        return {"message": "Curated look published", "id": look_id}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error publishing curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error publishing curated look")


@router.post("/{look_id}/unpublish")
async def unpublish_curated_look(
    look_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Unpublish a curated look (hide from users)"""
    try:
        query = select(CuratedLook).where(CuratedLook.id == look_id)
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        look.is_published = False
        look.updated_at = datetime.utcnow()
        await db.commit()

        return {"message": "Curated look unpublished", "id": look_id}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error unpublishing curated look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error unpublishing curated look")


@router.post("/{look_id}/precompute-masks")
async def precompute_masks_for_curated_look(
    look_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger mask precomputation for a curated look.
    This pre-computes SAM segmentation masks for instant "Edit Position" functionality.
    """
    from services.mask_precomputation_service import mask_precomputation_service

    try:
        # Get the curated look with products
        query = (
            select(CuratedLook)
            .options(selectinload(CuratedLook.products).selectinload(CuratedLookProduct.product))
            .where(CuratedLook.id == look_id)
        )
        result = await db.execute(query)
        look = result.scalar_one_or_none()

        if not look:
            raise HTTPException(status_code=404, detail="Curated look not found")

        if not look.visualization_image:
            raise HTTPException(status_code=400, detail="Curated look has no visualization image")

        # Build products list
        products = []
        for clp in look.products:
            if clp.product:
                products.append({"id": clp.product.id, "name": clp.product.name})

        logger.info(f"[PrecomputeMasks] Starting precomputation for look {look_id} with {len(products)} products")

        # Delete any existing masks for this look (force refresh)
        await mask_precomputation_service.invalidate_curated_look_masks(db, look_id)

        # Trigger precomputation
        job_id = await mask_precomputation_service.trigger_precomputation_for_curated_look(
            db, look_id, look.visualization_image, products
        )

        if not job_id:
            raise HTTPException(status_code=500, detail="Failed to create precomputation job")

        # Process synchronously (blocking) so we can return results
        await mask_precomputation_service.process_precomputation(db, job_id, look.visualization_image, products)

        # Get results
        from database.models import PrecomputedMask

        result = await db.execute(select(PrecomputedMask).where(PrecomputedMask.id == job_id))
        mask_record = result.scalar_one_or_none()

        if mask_record:
            layer_count = len(mask_record.layers_data) if mask_record.layers_data else 0
            return {
                "message": "Precomputation completed",
                "look_id": look_id,
                "job_id": job_id,
                "status": mask_record.status.value,
                "layer_count": layer_count,
                "processing_time": mask_record.processing_time,
            }

        return {"message": "Precomputation triggered", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error precomputing masks for look {look_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error precomputing masks: {str(e)}")
