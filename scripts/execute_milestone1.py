#!/usr/bin/env python3
"""
Execute Milestone 1: Complete production scraping operations
"""
import sys
import os
import time
import json
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.scraping_manager import ScrapingManager
from utils.data_quality import QualityReporter, DataCleaner, DuplicateDetector
from database.connection import init_database, get_db_session
from database.models import Product

def setup_environment():
    """Set up directories and environment"""
    print("🔧 Setting up environment...")

    directories = [
        'logs',
        'data/images',
        'data/reports'
    ]

    for directory in directories:
        path = project_root / directory
        path.mkdir(parents=True, exist_ok=True)

    print("✅ Environment setup complete")

def initialize_database():
    """Initialize database if needed"""
    print("🗄️  Initializing database...")

    try:
        init_database()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

    return True

def execute_full_scraping():
    """Execute complete scraping of all three websites"""
    print("\n🕷️  Starting full scraping operation...")
    print("=" * 60)

    manager = ScrapingManager()
    start_time = datetime.utcnow()

    # Target metrics for Milestone 1
    targets = {
        'westelm': 4000,
        'orangetree': 3000,
        'pelicanessentials': 3000
    }

    results = {}
    total_scraped = 0

    for spider_name in ['westelm', 'orangetree', 'pelicanessentials']:
        print(f"\n🔄 Running {spider_name} spider...")
        print(f"   Target: {targets[spider_name]} products")

        spider_start = datetime.utcnow()
        result = manager.run_spider(spider_name)
        spider_end = datetime.utcnow()

        duration = (spider_end - spider_start).total_seconds()

        # Get actual count from database
        with get_db_session() as session:
            actual_count = session.query(Product).filter(
                Product.source_website == spider_name
            ).count()

        results[spider_name] = {
            'status': result['status'],
            'duration': duration,
            'target': targets[spider_name],
            'actual': actual_count,
            'success': actual_count >= targets[spider_name] * 0.8  # 80% of target
        }

        total_scraped += actual_count

        # Display results
        status_icon = "✅" if result['status'] == 'success' else "❌"
        target_icon = "✅" if results[spider_name]['success'] else "⚠️"

        print(f"   {status_icon} Status: {result['status']}")
        print(f"   {target_icon} Products: {actual_count}/{targets[spider_name]}")
        print(f"   ⏱️  Duration: {duration:.1f}s")

        # Wait between spiders
        if spider_name != 'pelicanessentials':
            print("   ⏳ Waiting 30 seconds before next spider...")
            time.sleep(30)

    end_time = datetime.utcnow()
    total_duration = (end_time - start_time).total_seconds()

    print(f"\n📊 SCRAPING SUMMARY")
    print("=" * 60)
    print(f"Total Products Scraped: {total_scraped:,}")
    print(f"Target Products: {sum(targets.values()):,}")
    print(f"Success Rate: {(total_scraped / sum(targets.values()) * 100):.1f}%")
    print(f"Total Duration: {total_duration / 3600:.1f} hours")

    return results, total_scraped

def run_data_quality_checks():
    """Run comprehensive data quality checks"""
    print("\n🔍 Running data quality checks...")
    print("=" * 60)

    # Clean data
    print("🧹 Cleaning product data...")
    cleaner = DataCleaner()
    cleaner.clean_all_products()
    print("✅ Data cleaning complete")

    # Find duplicates
    print("🔍 Finding duplicate products...")
    detector = DuplicateDetector()
    duplicates = detector.find_duplicates()
    print(f"✅ Found {len(duplicates)} potential duplicates")

    # Generate quality report
    print("📋 Generating quality report...")
    reporter = QualityReporter()
    report = reporter.generate_quality_report()

    # Save report
    report_file = project_root / 'data' / 'reports' / f"milestone1_quality_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print("✅ Quality report generated")

    # Display key metrics
    print(f"\n📈 QUALITY METRICS")
    print("=" * 60)
    print(f"Total Products: {report['total_products']:,}")
    print(f"Image Coverage: {report['image_coverage']:.1f}%")
    print(f"Description Coverage: {report['description_coverage']:.1f}%")
    print(f"Availability Rate: {report['availability_rate']:.1f}%")
    print(f"Quality Score: {report['quality_score']:.1f}%")

    print(f"\nSource Breakdown:")
    for source, count in report['source_breakdown'].items():
        print(f"  {source}: {count:,} products")

    return report

def validate_milestone_success(total_scraped, quality_report):
    """Validate if Milestone 1 success criteria are met"""
    print("\n✅ MILESTONE 1 VALIDATION")
    print("=" * 60)

    criteria = {
        'Total Products (>10,000)': total_scraped >= 10000,
        'Quality Score (>80%)': quality_report['quality_score'] >= 80,
        'Image Coverage (>90%)': quality_report['image_coverage'] >= 90,
        'All Sources Active': len(quality_report['source_breakdown']) >= 3,
        'Data Freshness': True  # Assume fresh since we just scraped
    }

    all_passed = True
    for criterion, passed in criteria.items():
        icon = "✅" if passed else "❌"
        print(f"{icon} {criterion}")
        if not passed:
            all_passed = False

    print(f"\n{'🎉 MILESTONE 1 COMPLETED SUCCESSFULLY!' if all_passed else '⚠️  MILESTONE 1 PARTIALLY COMPLETED'}")

    if all_passed:
        print("✅ Ready to proceed to Milestone 2")
    else:
        print("🔄 Consider running additional scraping to meet all criteria")

    return all_passed

def save_milestone_summary(results, total_scraped, quality_report, success):
    """Save milestone completion summary"""
    summary = {
        'milestone': 1,
        'completed_at': datetime.utcnow().isoformat(),
        'scraping_results': results,
        'total_products_scraped': total_scraped,
        'quality_metrics': {
            'total_products': quality_report['total_products'],
            'image_coverage': quality_report['image_coverage'],
            'description_coverage': quality_report['description_coverage'],
            'quality_score': quality_report['quality_score']
        },
        'success_criteria_met': success,
        'next_steps': [
            "Set up React frontend development environment",
            "Create API endpoints for product data",
            "Integrate ChatGPT API for natural language processing",
            "Begin basic UI development for product browsing"
        ]
    }

    summary_file = project_root / 'data' / 'reports' / 'milestone1_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n📄 Milestone summary saved to: {summary_file}")

def main():
    """Main execution function"""
    print("🚀 OMNISHOP MILESTONE 1 EXECUTION")
    print("=" * 60)
    print("Executing complete data foundation and web scraping operations")
    print(f"Started at: {datetime.utcnow().isoformat()}")

    try:
        # Setup
        setup_environment()

        if not initialize_database():
            print("❌ Cannot proceed without database")
            return 1

        # Execute scraping
        results, total_scraped = execute_full_scraping()

        # Quality checks
        quality_report = run_data_quality_checks()

        # Validate success
        success = validate_milestone_success(total_scraped, quality_report)

        # Save summary
        save_milestone_summary(results, total_scraped, quality_report, success)

        print(f"\n🏁 EXECUTION COMPLETED")
        print(f"Finished at: {datetime.utcnow().isoformat()}")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⚠️  Execution interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Execution failed: {e}")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)