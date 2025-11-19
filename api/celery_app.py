"""
Celery application configuration for background tasks
"""
from celery import Celery
from core.config import settings

# Create Celery application
celery_app = Celery(
    "omnishop",
    broker=f"redis://localhost:6379/0",  # Redis as message broker
    backend=f"redis://localhost:6379/1",  # Redis as result backend
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max
    result_expires=3600,  # Results expire after 1 hour
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks from api.tasks module
celery_app.autodiscover_tasks([".tasks"])

if __name__ == "__main__":
    celery_app.start()
