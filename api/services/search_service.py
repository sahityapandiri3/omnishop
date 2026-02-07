"""
Shared search service — unified search logic for products.

Extracts the best search patterns from admin_curated.py (synonym expansion,
word-boundary matching, AND-grouped logic, exclusion terms) and chat.py
(numpy-vectorized semantic search) into a single reusable module.

Used by: products.py (Design Studio), admin_curated.py (Curation), chat.py (Chat)
"""
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from services.embedding_service import EmbeddingService
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models import Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding service singleton (shared across all callers)
# ---------------------------------------------------------------------------
_embedding_service: Optional[EmbeddingService] = None


def _get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


# ---------------------------------------------------------------------------
# Singular / plural normalisation
# ---------------------------------------------------------------------------
def normalize_singular_plural(word: str) -> list:
    """
    Returns both singular and plural forms of a word.
    Handles common English patterns and hyphenated words.
    """
    word = word.lower().strip()
    forms = [word]

    irregulars = {
        "furniture": "furniture",
        "decor": "decor",
        "seating": "seating",
    }
    if word in irregulars:
        return [word]

    # Hyphenated words  e.g. "l-shaped" -> "l-shape", "l shaped", "l shape"
    if "-" in word:
        space_version = word.replace("-", " ")
        forms.append(space_version)

        if word.endswith("-shaped"):
            no_d_version = word[:-1]  # "l-shaped" -> "l-shape"
            forms.append(no_d_version)
            forms.append(no_d_version.replace("-", " "))
        elif word.endswith("ed"):
            no_d_version = word[:-1]
            forms.append(no_d_version)
            forms.append(no_d_version.replace("-", " "))

    # Singular from plural
    if word.endswith("ies"):
        forms.append(word[:-3] + "y")
    elif word.endswith("es"):
        if word.endswith("sses") or word.endswith("shes") or word.endswith("ches") or word.endswith("xes"):
            forms.append(word[:-2])
        else:
            forms.append(word[:-1])
            forms.append(word[:-2])
    elif word.endswith("s") and not word.endswith("ss"):
        forms.append(word[:-1])

    # Plural from singular
    if not word.endswith("s"):
        if word.endswith("y") and len(word) > 2 and word[-2] not in "aeiou":
            forms.append(word[:-1] + "ies")
        elif word.endswith(("s", "sh", "ch", "x", "z")):
            forms.append(word + "es")
        else:
            forms.append(word + "s")

    return list(set(forms))


# ---------------------------------------------------------------------------
# Exclusion terms  (prevents "center table" from returning "dining table")
# ---------------------------------------------------------------------------
SEARCH_EXCLUSIONS: Dict[str, List[str]] = {
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


# ---------------------------------------------------------------------------
# Synonym dictionary  (merged from admin_curated.py + chat.py)
# ---------------------------------------------------------------------------
SEARCH_SYNONYMS: Dict[str, List[str]] = {
    # Rugs & carpets (merged chat.py dhurrie/kilim synonyms)
    "carpet": ["rug", "carpet", "runner", "mat", "floor covering", "dhurrie", "kilim"],
    "rug": ["rug", "carpet", "runner", "mat", "floor covering", "dhurrie", "kilim"],
    # Sofas
    "sofa": ["sofa", "couch", "settee", "sectional"],
    "sofas": ["sofa", "couch", "settee", "sectional"],
    "couch": ["sofa", "couch", "settee", "sectional"],
    "couches": ["sofa", "couch", "settee", "sectional"],
    # L-shaped / corner / sectional
    "l-shaped": ["l-shaped", "l-shape", "l shaped", "l shape", "corner", "sectional"],
    "l-shape": ["l-shaped", "l-shape", "l shaped", "l shape", "corner", "sectional"],
    "corner": ["corner", "l-shaped", "l-shape", "l shaped", "l shape", "sectional"],
    "sectional": ["sectional", "l-shaped", "l-shape", "l shaped", "l shape", "corner", "chaise"],
    "sectionals": ["sectional", "l-shaped", "l-shape", "l shaped", "l shape", "corner", "chaise"],
    # Cupboard / cabinet
    "cupboard": ["cupboard", "cabinet", "wardrobe", "armoire"],
    "cabinet": ["cupboard", "cabinet", "wardrobe", "armoire"],
    # Lamps & lights
    "lamp": ["lamp", "floor lamp", "standing lamp", "table lamp"],
    "lamps": ["lamp", "floor lamp", "standing lamp", "table lamp"],
    "floor lamp": ["floor lamp", "standing lamp", "lamp"],
    "standing lamp": ["standing lamp", "floor lamp", "lamp"],
    "table lamp": ["table lamp", "desk lamp", "lamp"],
    "light": ["light", "lighting", "chandelier", "pendant light"],
    "lights": ["light", "lighting", "chandelier", "pendant light"],
    "chandelier": ["chandelier", "pendant light", "ceiling light"],
    # Tables
    "table": ["table", "desk"],
    "center": ["center", "centre"],
    "centre": ["centre", "center"],
    "coffee": ["coffee", "center", "centre"],
    "tables": ["table", "desk"],
    "desk": ["table", "desk"],
    "desks": ["table", "desk"],
    # Seater size synonyms (number vs word forms)
    "single": ["single", "1", "one"],
    "one": ["single", "1", "one"],
    "1": ["single", "1", "one"],
    "double": ["double", "2", "two"],
    "two": ["two", "2", "double"],
    "2": ["two", "2", "double"],
    "triple": ["triple", "3", "three"],
    "three": ["three", "3", "triple"],
    "3": ["three", "3", "triple"],
    "four": ["four", "4"],
    "4": ["four", "4"],
    "five": ["five", "5"],
    "5": ["five", "5"],
    "six": ["six", "6"],
    "6": ["six", "6"],
    "seven": ["seven", "7"],
    "7": ["seven", "7"],
    "eight": ["eight", "8"],
    "8": ["eight", "8"],
    "nine": ["nine", "9"],
    "9": ["nine", "9"],
    "ten": ["ten", "10"],
    "10": ["ten", "10"],
    "seater": ["seater", "seat"],
    "seaters": ["seater", "seat"],
    # Chairs
    "chair": ["chair", "seat", "seating"],
    "chairs": ["chair", "seat", "seating"],
    # Curtains & drapes
    "curtain": ["curtain", "drape", "drapes", "blind", "blinds"],
    "curtains": ["curtain", "drape", "drapes", "blind", "blinds"],
    "drape": ["curtain", "drape", "drapes"],
    "drapes": ["curtain", "drape", "drapes"],
    # Beds
    "bed": ["bed", "bedframe", "bed frame"],
    "beds": ["bed", "bedframe", "bed frame"],
    "bedside table": ["bedside table", "nightstand", "night stand", "bedside"],
    "bedside tables": ["bedside table", "nightstand", "night stand", "bedside"],
    "nightstand": ["nightstand", "bedside table", "night stand", "bedside"],
    "nightstands": ["nightstand", "bedside table", "night stand", "bedside"],
    # Planters
    "planter": ["planter", "pot", "plant pot", "flower pot"],
    "planters": ["planter", "pot", "plant pot", "flower pot"],
    "pot": ["pot", "planter", "plant pot", "flower pot"],
    "pots": ["pot", "planter", "plant pot", "flower pot"],
    # Wall art & paintings
    "painting": ["painting", "wall art", "artwork", "canvas art", "art print"],
    "paintings": ["painting", "wall art", "artwork", "canvas art", "art print"],
    "wall art": ["wall art", "painting", "artwork", "canvas art", "art print", "wall decor"],
    "wall decor": ["wall decor", "wall art", "painting", "artwork", "canvas art"],
    "artwork": ["artwork", "wall art", "painting", "canvas art", "art print"],
    "art": ["art", "wall art", "painting", "artwork", "art print"],
    # Storage
    "drawer": ["drawer", "drawers", "chest of drawers", "dresser", "chest"],
    "drawers": ["drawer", "drawers", "chest of drawers", "dresser", "chest"],
    "draws": ["drawer", "drawers", "chest of drawers", "dresser", "chest"],
    "chest of drawers": ["chest of drawers", "drawer", "drawers", "dresser", "chest"],
    "chest of draws": ["chest of drawers", "drawer", "drawers", "dresser", "chest"],
    "dresser": ["dresser", "drawer", "drawers", "chest of drawers", "chest"],
    "dressers": ["dresser", "drawer", "drawers", "chest of drawers", "chest"],
    "storage": ["storage", "cabinet", "cupboard", "drawer", "shelf", "shelves"],
    "storage unit": ["storage", "cabinet", "cupboard", "drawer", "shelf"],
    "storage units": ["storage", "cabinet", "cupboard", "drawer", "shelf"],
    # Wallpaper (from chat.py)
    "wallpaper": ["wallpaper", "wall paper", "wall covering", "wallpapers"],
    "wallpapers": ["wallpaper", "wall paper", "wall covering", "wallpapers"],
}


# ---------------------------------------------------------------------------
# Query expansion helpers
# ---------------------------------------------------------------------------
def expand_search_query_grouped(query: str) -> List[List[str]]:
    """Expand a search query and return GROUPED synonyms for AND logic.

    Returns list of lists: [[synonyms for word1], [synonyms for word2], ...]
    Search should match: (any of group1) AND (any of group2) AND ...

    Example: "L-shaped sofa" -> [["l-shaped", "l-shape", ...], ["sofa", "couch", ...]]
    """
    query_lower = query.lower().strip()
    words = query_lower.split()

    if len(words) == 1:
        for key, synonyms in SEARCH_SYNONYMS.items():
            if key == query_lower:
                return [synonyms]

        word_forms = normalize_singular_plural(query_lower)
        for form in word_forms:
            for key, synonyms in SEARCH_SYNONYMS.items():
                if key == form:
                    return [synonyms]

        return [word_forms]

    # Multi-word: create one group per word
    groups = []
    for word in words:
        matched = False
        for key, synonyms in SEARCH_SYNONYMS.items():
            if key == word:
                groups.append(list(synonyms))
                matched = True
                break

        if not matched:
            word_forms = normalize_singular_plural(word)
            groups.append(word_forms)

    logger.info(f"Multi-word query '{query}' grouped to: {groups}")
    return groups


def get_exclusion_terms(query: str) -> List[str]:
    """Get terms to exclude from results based on query.

    Example: "center table" -> ["dining", "console", "side table", ...]
    """
    query_lower = query.lower().strip()

    if query_lower in SEARCH_EXCLUSIONS:
        return SEARCH_EXCLUSIONS[query_lower]

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


# ---------------------------------------------------------------------------
# Keyword condition builder  (replaces the broken ILIKE/OR logic in products.py)
# ---------------------------------------------------------------------------

# Words that are too generic for description matching (too many false positives)
BROAD_TERMS = {"decor", "art", "furniture", "home", "living", "style", "design"}


def build_keyword_conditions(query: str) -> Tuple[Any, List[List[str]]]:
    """Build SQLAlchemy WHERE conditions for a keyword search.

    Uses:
    - expand_search_query_grouped() for synonym expansion
    - PostgreSQL regex \\y (word boundary) for precise matching on product name
    - AND logic between word groups, OR within each group
    - Falls back to brand/description match for the full original phrase

    Returns:
        (where_clause, search_groups)  — ready to pass to query.where()
    """
    search_groups = expand_search_query_grouped(query)

    # AND conditions: product name must match >= 1 term from EACH group
    and_conditions = []
    for group in search_groups:
        group_conditions = []
        for term in group:
            escaped_term = re.escape(term)
            group_conditions.append(Product.name.op("~*")(rf"\y{escaped_term}\y"))
        if group_conditions:
            and_conditions.append(or_(*group_conditions))

    # Also match original query in brand and (non-broad) description
    escaped_query = re.escape(query)
    query_lower = query.lower().strip()

    original_query_conditions = [
        Product.brand.op("~*")(rf"\y{escaped_query}\y"),
    ]
    if query_lower not in BROAD_TERMS:
        original_query_conditions.append(Product.description.op("~*")(rf"\y{escaped_query}\y"))

    if and_conditions:
        grouped_condition = and_(*and_conditions)
        all_conditions = [grouped_condition] + original_query_conditions
        where_clause = or_(*all_conditions)
    else:
        where_clause = or_(*original_query_conditions)

    return where_clause, search_groups


# ---------------------------------------------------------------------------
# Semantic search  (numpy-vectorized, extracted from chat.py)
# ---------------------------------------------------------------------------
async def semantic_search_products(
    query_text: str,
    db: AsyncSession,
    category_ids: Optional[List[int]] = None,
    source_websites: Optional[List[str]] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 500,
) -> Dict[int, float]:
    """Perform vector similarity search using numpy-vectorized cosine similarity.

    ~100x faster than the Python-loop implementation it replaces.

    Returns dict mapping product_id -> similarity score (0.0-1.0).
    """
    start_time = time.time()
    embedding_service = _get_embedding_service()

    query_embedding = await embedding_service.get_query_embedding(query_text)
    if not query_embedding:
        logger.warning(f"[SEMANTIC SEARCH] Failed to generate embedding for: {query_text[:50]}...")
        return {}

    embed_time = time.time() - start_time
    logger.info(f"[SEMANTIC SEARCH] Generated query embedding in {embed_time:.2f}s for: {query_text[:50]}...")

    # Build base query
    query = select(Product.id, Product.embedding).where(Product.is_available.is_(True)).where(Product.embedding.isnot(None))

    if category_ids:
        query = query.where(Product.category_id.in_(category_ids))
    if source_websites:
        query = query.where(Product.source_website.in_(source_websites))
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)

    db_start = time.time()
    result = await db.execute(query)
    rows = result.fetchall()
    db_time = time.time() - db_start

    logger.info(f"[SEMANTIC SEARCH] Fetched {len(rows)} products with embeddings in {db_time:.2f}s")

    if not rows:
        return {}

    # Vectorised cosine similarity via numpy
    calc_start = time.time()

    query_vec = np.array(query_embedding, dtype=np.float32)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        logger.warning("[SEMANTIC SEARCH] Query embedding has zero norm")
        return {}
    query_vec_normalized = query_vec / query_norm

    product_ids = []
    valid_embeddings = []
    for product_id, embedding_json in rows:
        try:
            product_embedding = json.loads(embedding_json)
            product_ids.append(product_id)
            valid_embeddings.append(product_embedding)
        except (json.JSONDecodeError, Exception):
            continue

    if not valid_embeddings:
        return {}

    embeddings_matrix = np.array(valid_embeddings, dtype=np.float32)
    norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings_normalized = embeddings_matrix / norms

    similarities = np.dot(embeddings_normalized, query_vec_normalized)

    calc_time = time.time() - calc_start

    top_indices = np.argsort(similarities)[::-1][:limit]
    result_dict = {product_ids[i]: float(similarities[i]) for i in top_indices}

    total_time = time.time() - start_time
    if result_dict:
        top_score = similarities[top_indices[0]] if len(top_indices) > 0 else 0
        logger.info(
            f"[SEMANTIC SEARCH] Top score: {top_score:.3f}, returning {len(result_dict)} products "
            f"(embed={embed_time:.2f}s, db={db_time:.2f}s, calc={calc_time:.2f}s, total={total_time:.2f}s)"
        )

    return result_dict
