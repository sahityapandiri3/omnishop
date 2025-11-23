"""
Furniture Removal API routes for async image processing
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from services.furniture_removal_service import furniture_removal_service
from services.google_ai_service import google_ai_service

logger = logging.getLogger(__name__)
router = APIRouter()  # No prefix here - it's added in main.py


class FurnitureRemovalRequest(BaseModel):
    """Request model for furniture removal"""

    image: str  # base64 encoded image


class FurnitureRemovalResponse(BaseModel):
    """Response model for furniture removal job"""

    job_id: str
    status: str  # pending, processing, completed, failed


class FurnitureStatusResponse(BaseModel):
    """Response model for furniture removal status"""

    job_id: str
    status: str
    image: Optional[str] = None  # Only present when completed or failed


async def process_furniture_removal(job_id: str, image: str) -> None:
    """
    Background task for furniture removal processing
    Retries 3 times with exponential backoff
    """
    try:
        logger.info(f"Starting furniture removal processing for job {job_id}")
        furniture_removal_service.update_job(job_id, "processing")

        # Call Google AI service with retry logic (max 3 attempts)
        processed_image = await google_ai_service.remove_furniture(image, max_retries=3)

        if processed_image:
            # Success - cache and update job
            logger.info(f"Furniture removal completed successfully for job {job_id}")
            furniture_removal_service.update_job(job_id, "completed", processed_image)
            furniture_removal_service.cache_result(image, processed_image)
        else:
            # Failed after all retries
            logger.error(f"Furniture removal failed for job {job_id} after all retries")
            furniture_removal_service.update_job(job_id, "failed")

    except Exception as e:
        logger.error(f"Error in furniture removal background task for job {job_id}: {e}", exc_info=True)
        furniture_removal_service.update_job(job_id, "failed")


@router.post("/remove", response_model=FurnitureRemovalResponse)
async def start_furniture_removal(request: FurnitureRemovalRequest, background_tasks: BackgroundTasks):
    """
    Start async furniture removal job
    Returns job_id immediately for polling
    """
    try:
        logger.info("Received furniture removal request")

        # Create job (checks cache automatically)
        job_id = furniture_removal_service.create_job(request.image)

        # Check if we got a cache hit
        job = furniture_removal_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=500, detail="Failed to create job")

        if job.status == "completed":
            # Cache hit - return immediately
            logger.info(f"Cache hit for furniture removal job {job_id}")
            return FurnitureRemovalResponse(job_id=job_id, status="completed")

        # Start background processing
        background_tasks.add_task(process_furniture_removal, job_id, request.image)
        logger.info(f"Started background furniture removal processing for job {job_id}")

        return FurnitureRemovalResponse(job_id=job_id, status="pending")

    except Exception as e:
        logger.error(f"Error starting furniture removal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start furniture removal: {str(e)}")


@router.get("/status/{job_id}", response_model=FurnitureStatusResponse)
async def get_furniture_removal_status(job_id: str):
    """
    Check status of furniture removal job
    Returns processed image when completed, original image when failed
    """
    try:
        job = furniture_removal_service.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        response = FurnitureStatusResponse(job_id=job_id, status=job.status)

        if job.status == "completed" and job.processed_image:
            response.image = job.processed_image
        elif job.status == "failed":
            # Fallback to original image on failure
            response.image = job.original_image
            logger.info(f"Job {job_id} failed, returning original image")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking furniture removal status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")
