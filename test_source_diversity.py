#!/usr/bin/env python3
"""Test source diversity in product recommendations - LOCAL DATABASE"""
import sys
sys.path.insert(0, 'api')

import asyncio
from sqlalchemy import select, text
from core.database import get_db_session
from database.models import Product
from services.recommendation_engine import recommendation_engine, RecommendationRequest

async def test_diversity():
    """Test that source diversity is working"""
    async with get_db_session() as db:
        # Get sofa products
        print("🔍 Testing source diversity for sofa search...\n")

        request = RecommendationRequest(
            product_keywords=['sofa', 'couch', 'sectional', 'loveseat'],
            max_recommendations=30
        )

        # Get recommendations
        response = await recommendation_engine.get_recommendations(request, db)

        print(f"✅ Found {len(response.recommendations)} recommendations")
        print(f"📊 Total candidates found: {response.total_found}\n")

        # Group by source
        sources = {}
        for i, rec in enumerate(response.recommendations[:30]):
            source = rec.source_website or 'unknown'
            if source not in sources:
                sources[source] = []
            sources[source].append((i+1, rec.product_name, rec.overall_score))

        # Show source distribution
        print("="*80)
        print("SOURCE DISTRIBUTION IN TOP 30 RESULTS:")
        print("="*80)
        for source, products in sorted(sources.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\n{source}: {len(products)} products")
            for rank, name, score in products[:5]:  # Show first 5 from each source
                print(f"  #{rank:2d} | {name[:50]:50s} | Score: {score:.3f}")
            if len(products) > 5:
                print(f"  ... and {len(products)-5} more")

        print("\n" + "="*80)
        print("SUMMARY:")
        print("="*80)
        for source, products in sorted(sources.items()):
            percentage = (len(products) / 30) * 100
            print(f"{source:25s}: {len(products):2d} products ({percentage:5.1f}%)")

        # Check if diversity is working
        unique_sources = len(sources)
        print(f"\n{'✅ SUCCESS' if unique_sources > 1 else '❌ ISSUE'}: {unique_sources} unique sources in top 30 results")

        if unique_sources == 1:
            print("⚠️  Only one source is showing - diversity NOT working!")
        else:
            print("🎉 Multiple sources present - diversity IS working!")

if __name__ == "__main__":
    asyncio.run(test_diversity())
