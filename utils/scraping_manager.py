"""
Scraping management utilities and scheduling
"""
import subprocess
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json

from database.connection import get_db_session
from database.models import ScrapingLog, ScrapingStatus
from config.settings import settings

logger = logging.getLogger(__name__)


class ScrapingManager:
    """Manage scraping operations and scheduling"""

    def __init__(self):
        self.spiders = ['pelicanessentials', 'sageliving', 'objectry']
        self.project_root = Path(__file__).parent.parent

    def run_spider(self, spider_name: str, **kwargs) -> Dict:
        """Run a single spider and return results"""
        if spider_name not in self.spiders:
            raise ValueError(f"Unknown spider: {spider_name}. Available: {', '.join(self.spiders)}")

        logger.info(f"Starting spider: {spider_name}")
        start_time = datetime.utcnow()

        # Create log entry and get its ID
        log_id = self._create_log_entry(spider_name, start_time)

        try:
            # Build scrapy command
            cmd = [
                'python3', '-m', 'scrapy', 'crawl', spider_name,
                '-s', f'IMAGES_STORE={settings.images.store_path}',
                '-s', f'DOWNLOAD_DELAY={settings.scraping.download_delay}',
            ]

            # Add custom settings from kwargs
            for key, value in kwargs.items():
                cmd.extend(['-s', f'{key}={value}'])

            # Run spider
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            # Update log entry
            self._update_log_entry(
                log_id,
                end_time=end_time,
                duration=int(duration),
                status=ScrapingStatus.SUCCESS if result.returncode == 0 else ScrapingStatus.FAILED,
                stdout=result.stdout,
                stderr=result.stderr
            )

            return {
                'spider': spider_name,
                'status': 'success' if result.returncode == 0 else 'failed',
                'duration': duration,
                'log_id': log_id,
                'stdout': result.stdout,
                'stderr': result.stderr
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Spider {spider_name} timed out")
            self._update_log_entry(
                log_id,
                end_time=datetime.utcnow(),
                status=ScrapingStatus.FAILED,
                error_messages=['Spider timed out after 1 hour']
            )
            return {
                'spider': spider_name,
                'status': 'timeout',
                'log_id': log_id,
                'error': 'Spider timed out'
            }

        except Exception as e:
            logger.error(f"Error running spider {spider_name}: {e}")
            self._update_log_entry(
                log_id,
                end_time=datetime.utcnow(),
                status=ScrapingStatus.FAILED,
                error_messages=[str(e)]
            )
            return {
                'spider': spider_name,
                'status': 'error',
                'log_id': log_id,
                'error': str(e)
            }

    def run_all_spiders(self, **kwargs) -> Dict:
        """Run all spiders sequentially"""
        logger.info("Starting batch scraping of all spiders")
        start_time = datetime.utcnow()
        results = {}

        for spider_name in self.spiders:
            try:
                result = self.run_spider(spider_name, **kwargs)
                results[spider_name] = result

                # Wait between spiders to be respectful
                if spider_name != self.spiders[-1]:  # Don't wait after last spider
                    time.sleep(10)

            except Exception as e:
                logger.error(f"Failed to run spider {spider_name}: {e}")
                results[spider_name] = {
                    'status': 'error',
                    'error': str(e)
                }

        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds()

        # Generate summary
        successful = sum(1 for r in results.values() if r.get('status') == 'success')
        failed = len(results) - successful

        summary = {
            'batch_start': start_time.isoformat(),
            'batch_end': end_time.isoformat(),
            'total_duration': total_duration,
            'spiders_run': len(results),
            'successful': successful,
            'failed': failed,
            'results': results
        }

        logger.info(f"Batch scraping completed. {successful}/{len(results)} spiders successful")
        return summary

    def get_scraping_status(self) -> Dict:
        """Get current scraping status and recent history"""
        with get_db_session() as session:
            # Get recent logs (last 24 hours)
            recent_logs = session.query(ScrapingLog).filter(
                ScrapingLog.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).order_by(ScrapingLog.created_at.desc()).limit(50).all()

            # Get latest log for each spider
            latest_logs = {}
            for spider in self.spiders:
                latest = session.query(ScrapingLog).filter(
                    ScrapingLog.spider_name == spider
                ).order_by(ScrapingLog.created_at.desc()).first()
                if latest:
                    latest_logs[spider] = {
                        'last_run': latest.created_at.isoformat(),
                        'status': latest.status.value,
                        'products_saved': latest.products_saved,
                        'duration': latest.duration_seconds
                    }

            # Calculate success rates
            success_rates = {}
            for spider in self.spiders:
                logs = session.query(ScrapingLog).filter(
                    ScrapingLog.spider_name == spider,
                    ScrapingLog.created_at >= datetime.utcnow() - timedelta(days=7)
                ).all()

                if logs:
                    successful = sum(1 for log in logs if log.status == ScrapingStatus.SUCCESS)
                    success_rates[spider] = successful / len(logs) * 100
                else:
                    success_rates[spider] = 0

            return {
                'current_time': datetime.utcnow().isoformat(),
                'recent_runs': len(recent_logs),
                'latest_runs': latest_logs,
                'success_rates_7d': success_rates,
                'total_products': self._get_total_products_by_source()
            }

    def _create_log_entry(self, spider_name: str, start_time: datetime) -> int:
        """Create initial log entry for scraping run and return its ID"""
        website_mapping = {
            'westelm': 'westelm.com',
            'orangetree': 'orangetree.com',
            'pelicanessentials': 'pelicanessentials.com',
            'sageliving': 'sageliving.in',
            'objectry': 'objectry.com'
        }

        with get_db_session() as session:
            log_entry = ScrapingLog(
                website=website_mapping.get(spider_name, spider_name),
                spider_name=spider_name,
                started_at=start_time,
                status=ScrapingStatus.IN_PROGRESS
            )
            session.add(log_entry)
            session.commit()
            session.refresh(log_entry)
            log_id = log_entry.id
            return log_id

    def _update_log_entry(
        self,
        log_id: int,
        end_time: datetime = None,
        duration: int = None,
        status: ScrapingStatus = None,
        stdout: str = None,
        stderr: str = None,
        error_messages: List[str] = None
    ):
        """Update log entry with results"""
        with get_db_session() as session:
            # Fetch the log entry by ID
            log = session.query(ScrapingLog).filter(ScrapingLog.id == log_id).first()
            if not log:
                return

            if end_time:
                log.finished_at = end_time
            if duration:
                log.duration_seconds = duration
            if status:
                log.status = status

            # Parse scrapy output for statistics
            if stdout:
                stats = self._parse_scrapy_output(stdout)
                log.products_found = stats.get('items_scraped', 0)
                log.products_processed = stats.get('items_scraped', 0)
                log.products_saved = stats.get('items_scraped', 0)
                log.pages_scraped = stats.get('pages_scraped', 0)
                log.requests_made = stats.get('requests_made', 0)

            if stderr or error_messages:
                errors = []
                if stderr:
                    errors.append(stderr)
                if error_messages:
                    errors.extend(error_messages)
                log.error_messages = errors
                log.errors_count = len(errors)

            session.commit()

    def _parse_scrapy_output(self, output: str) -> Dict:
        """Parse scrapy output for statistics"""
        stats = {}

        # Extract common scrapy statistics
        patterns = {
            'items_scraped': r"'item_scraped_count': (\d+)",
            'pages_scraped': r"'response_received_count': (\d+)",
            'requests_made': r"'downloader/request_count': (\d+)",
            'bytes_downloaded': r"'downloader/response_bytes': (\d+)"
        }

        for key, pattern in patterns.items():
            import re
            match = re.search(pattern, output)
            if match:
                stats[key] = int(match.group(1))

        return stats

    def _get_total_products_by_source(self) -> Dict:
        """Get total products count by source website"""
        from database.models import Product

        with get_db_session() as session:
            totals = {}
            for spider in self.spiders:
                count = session.query(Product).filter(
                    Product.source_website == spider
                ).count()
                totals[spider] = count

            return totals

    def schedule_daily_scraping(self):
        """Set up daily scraping schedule (for production use with cron)"""
        # This would typically be used with a cron job or task scheduler
        # For now, it returns the cron command that should be set up

        script_path = self.project_root / "scripts" / "run_daily_scraping.py"
        cron_command = f"0 2 * * * cd {self.project_root} && python {script_path}"

        return {
            'cron_command': cron_command,
            'description': 'Run daily scraping at 2 AM',
            'script_path': str(script_path)
        }

    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old scraping logs"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        with get_db_session() as session:
            deleted_count = session.query(ScrapingLog).filter(
                ScrapingLog.created_at < cutoff_date
            ).delete()

            session.commit()
            logger.info(f"Cleaned up {deleted_count} old scraping logs")

            return deleted_count