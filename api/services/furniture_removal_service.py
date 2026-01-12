"""
Furniture Removal Service
Handles async job tracking for furniture removal from room images
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class FurnitureRemovalJob:
    """Job tracking for furniture removal"""

    job_id: str
    status: str  # pending, processing, completed, failed
    original_image: str
    processed_image: Optional[str] = None
    room_analysis: Optional[Dict] = None  # Room analysis JSON from analyze_room_image
    retries: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class FurnitureRemovalService:
    """Service for managing furniture removal jobs with caching"""

    def __init__(self):
        self.jobs: Dict[str, FurnitureRemovalJob] = {}
        self.cache: Dict[str, str] = {}  # image_hash -> processed_image
        self._cleanup_counter = 0  # Track job creations for opportunistic cleanup

    def create_job(self, image: str) -> str:
        """
        Create new job, check cache first
        Returns job_id
        """
        # Opportunistic cleanup every 10 job creations
        self._cleanup_counter += 1
        if self._cleanup_counter >= 10:
            self._cleanup_counter = 0
            self.cleanup_stale_jobs()

        image_hash = hashlib.md5(image.encode()).hexdigest()

        # Check cache first
        if image_hash in self.cache:
            # Return cached result immediately
            job_id = str(uuid.uuid4())
            self.jobs[job_id] = FurnitureRemovalJob(
                job_id=job_id,
                status="completed",
                original_image=image,
                processed_image=self.cache[image_hash],
                retries=0,
            )
            return job_id

        # Create new processing job
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = FurnitureRemovalJob(
            job_id=job_id,
            status="pending",
            original_image=image,
            processed_image=None,
            retries=0,
        )
        return job_id

    def get_job(self, job_id: str) -> Optional[FurnitureRemovalJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)

    def update_job(
        self, job_id: str, status: str, processed_image: Optional[str] = None, room_analysis: Optional[Dict] = None
    ) -> None:
        """Update job status and optionally processed image and room analysis"""
        if job_id in self.jobs:
            self.jobs[job_id].status = status
            if processed_image:
                self.jobs[job_id].processed_image = processed_image
            if room_analysis:
                self.jobs[job_id].room_analysis = room_analysis
            self.jobs[job_id].updated_at = datetime.utcnow()

    def increment_retries(self, job_id: str) -> None:
        """Increment retry count for a job"""
        if job_id in self.jobs:
            self.jobs[job_id].retries += 1
            self.jobs[job_id].updated_at = datetime.utcnow()

    def cache_result(self, image: str, processed_image: str) -> None:
        """Cache processed image for future requests"""
        image_hash = hashlib.md5(image.encode()).hexdigest()
        self.cache[image_hash] = processed_image

    def invalidate_cache(self, image: str) -> bool:
        """Remove a specific image from cache. Returns True if removed, False if not found."""
        image_hash = hashlib.md5(image.encode()).hexdigest()
        if image_hash in self.cache:
            del self.cache[image_hash]
            logger.info(f"Invalidated cache for image hash {image_hash}")
            return True
        return False

    def clear_all_cache(self) -> int:
        """Clear all cached results. Returns number of entries cleared."""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared all {count} cache entries")
        return count

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """
        Remove jobs older than max_age_hours
        Call this periodically to prevent memory leaks
        Returns number of jobs removed
        """
        cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        jobs_to_remove = [job_id for job_id, job in self.jobs.items() if job.updated_at.timestamp() < cutoff_time]
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old furniture removal jobs (>{max_age_hours}h)")
        return len(jobs_to_remove)

    def cleanup_stale_jobs(self) -> int:
        """
        More aggressive cleanup for production:
        - Completed/failed jobs older than 1 hour (frontend should have fetched them by now)
        - Pending/processing jobs older than 10 minutes (stuck jobs)
        - Any job older than 24 hours regardless of status
        Returns total number of jobs removed
        """
        now = datetime.utcnow().timestamp()
        completed_cutoff = now - (1 * 3600)  # 1 hour for completed/failed
        stuck_cutoff = now - (10 * 60)  # 10 minutes for pending/processing
        max_cutoff = now - (24 * 3600)  # 24 hours absolute max

        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            job_age = job.updated_at.timestamp()
            # Remove any job older than 24 hours
            if job_age < max_cutoff:
                jobs_to_remove.append(job_id)
            # Remove completed/failed jobs older than 1 hour
            elif job.status in ("completed", "failed") and job_age < completed_cutoff:
                jobs_to_remove.append(job_id)
            # Remove stuck pending/processing jobs older than 10 minutes
            elif job.status in ("pending", "processing") and job_age < stuck_cutoff:
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del self.jobs[job_id]

        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} stale furniture removal jobs")
        return len(jobs_to_remove)

    def get_job_stats(self) -> dict:
        """Get statistics about current jobs for monitoring"""
        stats = {"total": len(self.jobs), "pending": 0, "processing": 0, "completed": 0, "failed": 0}
        for job in self.jobs.values():
            if job.status in stats:
                stats[job.status] += 1
        stats["cache_size"] = len(self.cache)
        return stats


# Global instance
furniture_removal_service = FurnitureRemovalService()
