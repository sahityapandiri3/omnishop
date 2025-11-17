"""
Background tasks for ChatGPT analysis
"""
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from celery_app import celery_app
from services.chatgpt_service import chatgpt_service
import json

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='api.tasks.analyze_user_input_async')
def analyze_user_input_async(
    self,
    user_message: str,
    session_id: Optional[str] = None,
    image_data: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Background task to analyze user input with ChatGPT

    Args:
        user_message: The user's message
        session_id: Session ID for conversation context
        image_data: Base64 encoded image data
        user_id: User ID for preference tracking

    Returns:
        Dict containing conversational_response and analysis data
    """
    try:
        logger.info(f"Background task {self.request.id} started for session {session_id}")

        # Update task state to STARTED
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Analyzing your request with AI...'}
        )

        # Run the async function in a new event loop
        # (Celery workers run in sync context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            conversational_response, analysis = loop.run_until_complete(
                chatgpt_service.analyze_user_input(
                    user_message=user_message,
                    session_id=session_id,
                    image_data=image_data,
                    user_id=user_id
                )
            )
        finally:
            loop.close()

        # Prepare result
        result = {
            'status': 'success',
            'conversational_response': conversational_response,
            'analysis': analysis.dict() if analysis else None,
            'session_id': session_id
        }

        logger.info(f"Background task {self.request.id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"Background task {self.request.id} failed: {e}", exc_info=True)

        # Return error result
        return {
            'status': 'error',
            'error': str(e),
            'conversational_response': "I encountered an error while analyzing your request. Please try again.",
            'analysis': None,
            'session_id': session_id
        }
