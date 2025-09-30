#!/usr/bin/env python3
"""
Main script to run scraping operations
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.scraping_manager import ScrapingManager
from utils.data_quality import QualityReporter, DataCleaner, DuplicateDetector
from database.connection import init_database
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.monitoring.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scraping.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def setup_directories():
    """Create necessary directories"""
    directories = [
        'logs',
        'data/images',
        'data/reports'
    ]

    for directory in directories:
        path = project_root / directory
        path.mkdir(parents=True, exist_ok=True)


def run_single_spider(spider_name: str, **kwargs):
    """Run a single spider"""
    manager = ScrapingManager()
    result = manager.run_spider(spider_name, **kwargs)

    print(f"Spider {spider_name} completed:")
    print(f"Status: {result['status']}")
    print(f"Duration: {result.get('duration', 0):.2f} seconds")

    if result['status'] != 'success':
        print(f"Error: {result.get('error', 'Unknown error')}")
        if result.get('stderr'):
            print(f"Stderr: {result['stderr']}")

    return result


def run_all_spiders(**kwargs):
    """Run all spiders"""
    manager = ScrapingManager()
    results = manager.run_all_spiders(**kwargs)

    print("Batch scraping completed:")
    print(f"Total duration: {results['total_duration']:.2f} seconds")
    print(f"Successful: {results['successful']}/{results['spiders_run']}")

    for spider, result in results['results'].items():
        status_icon = "✓" if result.get('status') == 'success' else "✗"
        print(f"  {status_icon} {spider}: {result.get('status', 'unknown')}")

    return results


def generate_quality_report():
    """Generate and display data quality report"""
    reporter = QualityReporter()
    report = reporter.generate_quality_report()

    print("\n=== DATA QUALITY REPORT ===")
    print(f"Total products: {report['total_products']}")
    print(f"Image coverage: {report['image_coverage']:.1f}%")
    print(f"Description coverage: {report['description_coverage']:.1f}%")
    print(f"Availability rate: {report['availability_rate']:.1f}%")
    print(f"Quality score: {report['quality_score']:.1f}%")

    print("\nSource breakdown:")
    for source, count in report['source_breakdown'].items():
        print(f"  {source}: {count} products")

    print("\nTop categories:")
    sorted_categories = sorted(
        report['category_breakdown'].items(),
        key=lambda x: x[1],
        reverse=True
    )
    for category, count in sorted_categories[:10]:
        print(f"  {category}: {count} products")

    if report['price_statistics']:
        stats = report['price_statistics']
        print(f"\nPrice statistics:")
        print(f"  Range: ${stats['min']:.2f} - ${stats['max']:.2f}")
        print(f"  Average: ${stats['average']:.2f}")
        print(f"  Products with prices: {stats['count']}")

    # Save report to file
    import json
    report_file = project_root / 'data' / 'reports' / f"quality_report_{report['generated_at'][:10]}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to: {report_file}")
    return report


def clean_data():
    """Clean and normalize product data"""
    print("Cleaning product data...")
    cleaner = DataCleaner()
    cleaner.clean_all_products()
    print("Data cleaning completed.")


def find_duplicates():
    """Find and report duplicate products"""
    print("Searching for duplicate products...")
    detector = DuplicateDetector()
    duplicates = detector.find_duplicates()

    if duplicates:
        print(f"Found {len(duplicates)} potential duplicates:")
        for dup in duplicates[:10]:  # Show first 10
            print(f"  Products {dup['product1_id']} & {dup['product2_id']}: "
                  f"{dup['similarity']:.2f} similarity ({dup['reason']})")

        if len(duplicates) > 10:
            print(f"  ... and {len(duplicates) - 10} more")
    else:
        print("No duplicates found.")

    return duplicates


def get_status():
    """Display current scraping status"""
    manager = ScrapingManager()
    status = manager.get_scraping_status()

    print("\n=== SCRAPING STATUS ===")
    print(f"Current time: {status['current_time']}")
    print(f"Recent runs (24h): {status['recent_runs']}")

    print("\nLatest runs:")
    for spider, data in status['latest_runs'].items():
        print(f"  {spider}:")
        print(f"    Last run: {data['last_run']}")
        print(f"    Status: {data['status']}")
        print(f"    Products: {data['products_saved']}")
        print(f"    Duration: {data['duration']}s")

    print("\nSuccess rates (7 days):")
    for spider, rate in status['success_rates_7d'].items():
        print(f"  {spider}: {rate:.1f}%")

    print("\nTotal products by source:")
    for source, count in status['total_products'].items():
        print(f"  {source}: {count} products")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Omnishop Scraping Manager')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Spider commands
    spider_parser = subparsers.add_parser('spider', help='Run individual spider')
    spider_parser.add_argument('spider_name', choices=['westelm', 'orangetree', 'pelicanessentials'])
    spider_parser.add_argument('--delay', type=float, help='Download delay in seconds')

    # Batch command
    batch_parser = subparsers.add_parser('batch', help='Run all spiders')
    batch_parser.add_argument('--delay', type=float, help='Download delay in seconds')

    # Status command
    subparsers.add_parser('status', help='Show scraping status')

    # Quality commands
    subparsers.add_parser('report', help='Generate quality report')
    subparsers.add_parser('clean', help='Clean data')
    subparsers.add_parser('duplicates', help='Find duplicates')

    # Database command
    subparsers.add_parser('init-db', help='Initialize database')

    args = parser.parse_args()

    # Set up directories
    setup_directories()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == 'spider':
            kwargs = {}
            if args.delay:
                kwargs['DOWNLOAD_DELAY'] = args.delay
            run_single_spider(args.spider_name, **kwargs)

        elif args.command == 'batch':
            kwargs = {}
            if args.delay:
                kwargs['DOWNLOAD_DELAY'] = args.delay
            run_all_spiders(**kwargs)

        elif args.command == 'status':
            get_status()

        elif args.command == 'report':
            generate_quality_report()

        elif args.command == 'clean':
            clean_data()

        elif args.command == 'duplicates':
            find_duplicates()

        elif args.command == 'init-db':
            print("Initializing database...")
            init_database()
            print("Database initialized successfully.")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()