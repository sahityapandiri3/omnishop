"""
Furniture Removal Service
Handles async job tracking for furniture removal from room images
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class FurnitureRemovalJob:
    """Job tracking for furniture removal"""

    job_id: str
    status: str  # pending, processing, completed, failed
    original_image: str
    processed_image: Optional[str] = None
    retries: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class FurnitureRemovalService:
    """Service for managing furniture removal jobs with caching"""

    def __init__(self):
        self.jobs: Dict[str, FurnitureRemovalJob] = {}
        self.cache: Dict[str, str] = {}  # image_hash -> processed_image

    def create_job(self, image: str) -> str:
        """
        Create new job, check cache first
        Returns job_id
        """
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

    def update_job(self, job_id: str, status: str, processed_image: Optional[str] = None) -> None:
        """Update job status and optionally processed image"""
        if job_id in self.jobs:
            self.jobs[job_id].status = status
            if processed_image:
                self.jobs[job_id].processed_image = processed_image
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

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> None:
        """
        Remove jobs older than max_age_hours
        Call this periodically to prevent memory leaks
        """
        cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        jobs_to_remove = [job_id for job_id, job in self.jobs.items() if job.updated_at.timestamp() < cutoff_time]
        for job_id in jobs_to_remove:
            del self.jobs[job_id]


# Global instance
furniture_removal_service = FurnitureRemovalService()
