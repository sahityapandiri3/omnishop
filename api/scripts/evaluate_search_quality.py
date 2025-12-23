"""
Search quality evaluation script.

Evaluates semantic search quality using golden test cases
and computes standard IR metrics: Precision@K, Recall@K, MRR, NDCG.

Usage:
    python scripts/evaluate_search_quality.py [--threshold 0.7]
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.config import settings
from services.embedding_service import get_embedding_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =====================================================================
# GOLDEN TEST CASES
# =====================================================================

SEARCH_TEST_CASES = [
    {
        "query": "cozy living room sofa",
        "expected_styles": ["scandinavian", "boho", "modern"],
        "should_match_keywords": ["comfortable", "cozy", "plush", "soft"],
        "should_match_categories": ["sofas", "couches"],
    },
    {
        "query": "minimalist dining table",
        "expected_styles": ["minimalist", "japandi", "modern", "scandinavian"],
        "should_match_keywords": ["clean", "simple", "sleek", "modern"],
        "should_match_categories": ["dining tables", "tables"],
    },
    {
        "query": "indian brass decor",
        "expected_styles": ["indian_contemporary", "eclectic"],
        "should_match_keywords": ["brass", "traditional", "indian", "ethnic"],
        "should_match_categories": ["decor", "home decor"],
    },
    {
        "query": "navy blue velvet armchair",
        "expected_styles": ["modern_luxury", "contemporary", "modern"],
        "should_match_keywords": ["blue", "navy", "velvet", "armchair"],
        "should_match_categories": ["chairs", "armchairs", "seating"],
    },
    {
        "query": "rustic wooden coffee table",
        "expected_styles": ["boho", "eclectic", "industrial"],
        "should_match_keywords": ["wood", "wooden", "rustic", "natural"],
        "should_match_categories": ["coffee tables", "tables"],
    },
    {
        "query": "scandinavian light wood bookshelf",
        "expected_styles": ["scandinavian", "japandi", "minimalist"],
        "should_match_keywords": ["wood", "light", "scandinavian", "nordic"],
        "should_match_categories": ["shelves", "bookcases", "storage"],
    },
    {
        "query": "mid century modern floor lamp",
        "expected_styles": ["mid_century_modern", "modern", "contemporary"],
        "should_match_keywords": ["lamp", "floor lamp", "mid-century", "retro"],
        "should_match_categories": ["lamps", "lighting", "floor lamps"],
    },
    {
        "query": "bohemian woven rug",
        "expected_styles": ["boho", "eclectic"],
        "should_match_keywords": ["woven", "rug", "boho", "textured"],
        "should_match_categories": ["rugs", "carpets"],
    },
    {
        "query": "luxury velvet bed",
        "expected_styles": ["modern_luxury", "contemporary"],
        "should_match_keywords": ["velvet", "bed", "luxury", "upholstered"],
        "should_match_categories": ["beds", "bedroom"],
    },
    {
        "query": "industrial metal stool",
        "expected_styles": ["industrial", "modern"],
        "should_match_keywords": ["metal", "stool", "industrial", "iron"],
        "should_match_categories": ["stools", "seating", "bar stools"],
    },
]


# =====================================================================
# EVALUATION METRICS
# =====================================================================

def precision_at_k(relevant: Set[int], retrieved: List[int], k: int) -> float:
    """Calculate Precision@K - what fraction of top K results are relevant."""
    if k == 0:
        return 0.0
    top_k = set(retrieved[:k])
    relevant_in_top_k = len(relevant & top_k)
    return relevant_in_top_k / k


def recall_at_k(relevant: Set[int], retrieved: List[int], k: int) -> float:
    """Calculate Recall@K - what fraction of relevant items are in top K."""
    if len(relevant) == 0:
        return 0.0
    top_k = set(retrieved[:k])
    relevant_in_top_k = len(relevant & top_k)
    return relevant_in_top_k / len(relevant)


def mean_reciprocal_rank(relevant: Set[int], retrieved: List[int]) -> float:
    """Calculate MRR - reciprocal rank of first relevant result."""
    for i, item_id in enumerate(retrieved):
        if item_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(relevant: Set[int], retrieved: List[int], k: int) -> float:
    """
    Calculate NDCG@K - Normalized Discounted Cumulative Gain.
    Uses binary relevance (1 for relevant, 0 for not relevant).
    """
    import math

    if k == 0 or len(relevant) == 0:
        return 0.0

    # DCG
    dcg = 0.0
    for i, item_id in enumerate(retrieved[:k]):
        rel = 1.0 if item_id in relevant else 0.0
        dcg += rel / math.log2(i + 2)  # log2(i + 2) because i is 0-indexed

    # Ideal DCG (all relevant items at top)
    ideal_dcg = 0.0
    for i in range(min(len(relevant), k)):
        ideal_dcg += 1.0 / math.log2(i + 2)

    return dcg / ideal_dcg if ideal_dcg > 0 else 0.0


# =====================================================================
# SEARCH QUALITY EVALUATOR
# =====================================================================

class SearchQualityEvaluator:
    """Evaluates search quality using test cases."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)
        self.embedding_service = get_embedding_service()

    async def run_search(
        self,
        query: str,
        limit: int = 50
    ) -> List[Tuple[int, float, str, str]]:
        """
        Run semantic search and return results.

        Returns list of (product_id, similarity, name, primary_style).
        """
        session = self.Session()

        try:
            # Get query embedding
            query_embedding = await self.embedding_service.get_query_embedding(query)
            if not query_embedding:
                return []

            # Get products with embeddings
            result = session.execute(
                text("""
                    SELECT id, embedding, name, primary_style
                    FROM products
                    WHERE is_available = true
                    AND embedding IS NOT NULL
                    LIMIT 1000
                """)
            )
            rows = result.fetchall()

            # Calculate similarities
            results = []
            for product_id, embedding_json, name, style in rows:
                try:
                    product_embedding = json.loads(embedding_json)
                    similarity = self.embedding_service.compute_cosine_similarity(
                        query_embedding,
                        product_embedding
                    )
                    results.append((product_id, similarity, name, style))
                except Exception:
                    continue

            # Sort by similarity
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]

        finally:
            session.close()

    def find_relevant_products(
        self,
        test_case: Dict,
        limit: int = 100
    ) -> Set[int]:
        """Find products that are relevant to the test case."""
        session = self.Session()

        try:
            # Build query to find relevant products
            conditions = []

            # Match by style
            styles = test_case.get("expected_styles", [])
            if styles:
                style_list = ", ".join(f"'{s}'" for s in styles)
                conditions.append(f"primary_style IN ({style_list})")

            # Match by keywords in name/description
            keywords = test_case.get("should_match_keywords", [])
            for keyword in keywords[:3]:  # Limit to avoid overly complex query
                conditions.append(
                    f"(LOWER(name) LIKE '%{keyword.lower()}%' OR "
                    f"LOWER(description) LIKE '%{keyword.lower()}%')"
                )

            if not conditions:
                return set()

            # At least one condition should match
            where_clause = " OR ".join(conditions)
            query = f"""
                SELECT id FROM products
                WHERE is_available = true
                AND ({where_clause})
                LIMIT {limit}
            """

            result = session.execute(text(query))
            return {row[0] for row in result.fetchall()}

        finally:
            session.close()

    async def evaluate_single_query(
        self,
        test_case: Dict,
        k: int = 10
    ) -> Dict:
        """Evaluate a single test query."""
        query = test_case["query"]

        # Run search
        search_results = await self.run_search(query, limit=100)
        retrieved_ids = [r[0] for r in search_results]

        # Find relevant products
        relevant_ids = self.find_relevant_products(test_case)

        if not relevant_ids:
            logger.warning(f"No relevant products found for query: {query}")
            return {
                "query": query,
                "num_retrieved": len(retrieved_ids),
                "num_relevant": 0,
                "error": "No relevant products in database"
            }

        # Calculate metrics
        p_at_k = precision_at_k(relevant_ids, retrieved_ids, k)
        r_at_k = recall_at_k(relevant_ids, retrieved_ids, k)
        mrr = mean_reciprocal_rank(relevant_ids, retrieved_ids)
        ndcg = ndcg_at_k(relevant_ids, retrieved_ids, k)

        # Check style distribution in top results
        top_styles = [r[3] for r in search_results[:k] if r[3]]
        style_match_ratio = sum(1 for s in top_styles if s in test_case.get("expected_styles", [])) / len(top_styles) if top_styles else 0

        return {
            "query": query,
            "num_retrieved": len(retrieved_ids),
            "num_relevant": len(relevant_ids),
            "precision_at_k": round(p_at_k, 3),
            "recall_at_k": round(r_at_k, 3),
            "mrr": round(mrr, 3),
            "ndcg_at_k": round(ndcg, 3),
            "style_match_ratio": round(style_match_ratio, 3),
            "top_results": [
                {"id": r[0], "similarity": round(r[1], 3), "name": r[2][:50], "style": r[3]}
                for r in search_results[:5]
            ]
        }

    async def evaluate_all(self, k: int = 10) -> Dict:
        """Evaluate all test cases and compute aggregate metrics."""
        results = []
        metrics = {
            "precision_at_k": [],
            "recall_at_k": [],
            "mrr": [],
            "ndcg_at_k": [],
            "style_match_ratio": []
        }

        for test_case in SEARCH_TEST_CASES:
            result = await self.evaluate_single_query(test_case, k)
            results.append(result)

            if "error" not in result:
                for metric in metrics:
                    metrics[metric].append(result[metric])

        # Calculate averages
        avg_metrics = {
            metric: round(sum(values) / len(values), 3) if values else 0.0
            for metric, values in metrics.items()
        }

        return {
            "k": k,
            "num_queries": len(SEARCH_TEST_CASES),
            "average_metrics": avg_metrics,
            "per_query_results": results
        }


# =====================================================================
# MAIN
# =====================================================================

async def main():
    """Run search quality evaluation."""
    parser = argparse.ArgumentParser(
        description="Evaluate semantic search quality"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Minimum acceptable average NDCG (default: 0.7)"
    )
    parser.add_argument(
        "--k",
        type=int,
        default=10,
        help="Number of results to evaluate (default: 10)"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL (default: from settings)"
    )

    args = parser.parse_args()

    database_url = args.database_url or settings.database_url
    if not database_url:
        logger.error("No database URL configured")
        sys.exit(1)

    evaluator = SearchQualityEvaluator(database_url)

    print("=" * 60)
    print("SEARCH QUALITY EVALUATION")
    print("=" * 60)

    results = await evaluator.evaluate_all(k=args.k)

    print(f"\nEvaluated {results['num_queries']} queries at K={results['k']}")
    print("\nAVERAGE METRICS:")
    for metric, value in results['average_metrics'].items():
        print(f"  {metric}: {value}")

    print("\nPER-QUERY RESULTS:")
    for r in results['per_query_results']:
        print(f"\n  Query: \"{r['query']}\"")
        if "error" in r:
            print(f"    Error: {r['error']}")
        else:
            print(f"    Precision@K: {r['precision_at_k']}, Recall@K: {r['recall_at_k']}, MRR: {r['mrr']}, NDCG: {r['ndcg_at_k']}")
            print(f"    Style Match Ratio: {r['style_match_ratio']}")
            print(f"    Top 3 results:")
            for tr in r['top_results'][:3]:
                print(f"      - {tr['name']} (similarity: {tr['similarity']}, style: {tr['style']})")

    # Check threshold
    avg_ndcg = results['average_metrics']['ndcg_at_k']
    print(f"\n{'=' * 60}")
    if avg_ndcg >= args.threshold:
        print(f"PASS: Average NDCG ({avg_ndcg}) >= threshold ({args.threshold})")
        sys.exit(0)
    else:
        print(f"FAIL: Average NDCG ({avg_ndcg}) < threshold ({args.threshold})")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
