"""
Furniture Removal API routes for async image processing
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from services.furniture_removal_service import furniture_removal_service
from services.google_ai_service import generate_workflow_id, google_ai_service

logger = logging.getLogger(__name__)
router = APIRouter()  # No prefix here - it's added in main.py


class FurnitureRemovalRequest(BaseModel):
    """Request model for furniture removal"""

    image: str  # base64 encoded image
    user_id: Optional[str] = None  # User ID for tracking
    session_id: Optional[str] = None  # Session ID for tracking


class FurnitureRemovalResponse(BaseModel):
    """Response model for furniture removal job"""

    job_id: str
    status: str  # pending, processing, completed, failed


class FurnitureStatusResponse(BaseModel):
    """Response model for furniture removal status"""

    job_id: str
    status: str
    image: Optional[str] = None  # Only present when completed or failed
    room_analysis: Optional[dict] = None  # Room analysis JSON (style, type, dimensions, etc.)


async def process_furniture_removal(
    job_id: str, image: str, workflow_id: str = None, user_id: str = None, session_id: str = None
) -> None:
    """
    Background task for furniture removal and perspective transformation.

    The remove_furniture function performs 2 Gemini calls:
    1. analyze_room_image (JSON) - detect viewing angle + room style/type/dimensions
    2. remove_furniture (IMAGE) - removes furniture + transforms to front view + straightens lines

    Args:
        job_id: Job identifier for tracking
        image: Base64 encoded image
        workflow_id: Workflow ID for tracking all API calls from this user action
        user_id: User ID for tracking
        session_id: Session ID for tracking
    """
    try:
        logger.info(f"Starting furniture removal for job {job_id}, workflow {workflow_id}")
        furniture_removal_service.update_job(job_id, "processing")

        # Remove furniture - returns dict with 'image' and 'room_analysis'
        result = await google_ai_service.remove_furniture(
            image, max_retries=5, workflow_id=workflow_id, user_id=user_id, session_id=session_id
        )

        if result and result.get("image"):
            # Success - cache and update job with both image and room_analysis
            processed_image = result["image"]
            room_analysis = result.get("room_analysis")
            logger.info(
                f"Image processing completed successfully for job {job_id}, style={room_analysis.get('style_assessment') if room_analysis else 'unknown'}"
            )
            furniture_removal_service.update_job(job_id, "completed", processed_image, room_analysis)
            furniture_removal_service.cache_result(image, processed_image)
        else:
            # Failed after all retries
            logger.error(f"Furniture removal failed for job {job_id} after all retries")
            furniture_removal_service.update_job(job_id, "failed")

    except Exception as e:
        logger.error(f"Error in image processing background task for job {job_id}: {e}", exc_info=True)
        furniture_removal_service.update_job(job_id, "failed")


@router.post("/remove", response_model=FurnitureRemovalResponse)
async def start_furniture_removal(request: FurnitureRemovalRequest, background_tasks: BackgroundTasks):
    """
    Start async furniture removal job
    Returns job_id immediately for polling
    """
    try:
        # Generate workflow_id to track all API calls from this user action
        workflow_id = generate_workflow_id()
        logger.info(f"Received furniture removal request, workflow_id={workflow_id}")

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

        # Start background processing with workflow_id
        background_tasks.add_task(
            process_furniture_removal, job_id, request.image, workflow_id, request.user_id, request.session_id
        )
        logger.info(f"Started background furniture removal processing for job {job_id}, workflow {workflow_id}")

        return FurnitureRemovalResponse(job_id=job_id, status="pending")

    except Exception as e:
        logger.error(f"Error starting furniture removal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start furniture removal: {str(e)}")


@router.get("/status/{job_id}", response_model=FurnitureStatusResponse)
async def get_furniture_removal_status(job_id: str):
    """
    Check status of furniture removal job
    Returns processed image and room_analysis when completed, original image when failed
    """
    try:
        job = furniture_removal_service.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        response = FurnitureStatusResponse(job_id=job_id, status=job.status)

        if job.status == "completed" and job.processed_image:
            response.image = job.processed_image
            response.room_analysis = job.room_analysis  # Include room analysis (style, type, dimensions, etc.)
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


@router.post("/clear-cache")
async def clear_furniture_removal_cache():
    """
    Clear all cached furniture removal results.
    Use this when cached results are stale or incorrect.
    """
    try:
        count = furniture_removal_service.clear_all_cache()
        stats = furniture_removal_service.get_job_stats()
        return {"message": f"Cleared {count} cached results", "current_stats": stats}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
