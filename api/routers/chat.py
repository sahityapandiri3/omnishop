"""
Chat API routes for interior design assistance
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Tuple
import logging
import uuid
from datetime import datetime

from api.core.database import get_db
from api.schemas.chat import (
    ChatMessageRequest, ChatMessageResponse, ChatMessageSchema,
    StartSessionRequest, StartSessionResponse, ChatHistoryResponse,
    ChatSessionSchema, MessageType, DesignAnalysisSchema
)
from api.services.chatgpt_service import chatgpt_service
from api.services.recommendation_engine import recommendation_engine, RecommendationRequest
from api.services.ml_recommendation_model import ml_recommendation_model
from api.services.google_ai_service import google_ai_service, VisualizationRequest
from api.services.conversation_context import conversation_context_manager
from api.services.nlp_processor import design_nlp_processor
from database.models import ChatSession, ChatMessage, Product

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/sessions", response_model=StartSessionResponse)
async def start_chat_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Start a new chat session"""
    try:
        # Create new session
        session_id = str(uuid.uuid4())
        session = ChatSession(
            id=session_id,
            user_id=request.user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(session)
        await db.commit()

        return StartSessionResponse(
            session_id=session_id,
            message="Hello! I'm your AI interior design assistant. How can I help you transform your space today?"
        )

    except Exception as e:
        import traceback
        logger.error(f"Error starting chat session: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: str,
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a message and get AI response"""
    try:
        # Verify session exists
        session_query = select(ChatSession).where(ChatSession.id == session_id)
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Store image in conversation context if provided
        if request.image:
            conversation_context_manager.store_image(session_id, request.image)

        # Save user message
        user_message_id = str(uuid.uuid4())
        user_message = ChatMessage(
            id=user_message_id,
            session_id=session_id,
            type=MessageType.user,
            content=request.message,
            timestamp=datetime.utcnow(),
            image_url=request.image if request.image else None
        )

        db.add(user_message)

        # Get AI response
        conversational_response, analysis = await chatgpt_service.analyze_user_input(
            user_message=request.message,
            session_id=session_id,
            image_data=request.image
        )

        # Save assistant message
        assistant_message_id = str(uuid.uuid4())
        assistant_message = ChatMessage(
            id=assistant_message_id,
            session_id=session_id,
            type=MessageType.assistant,
            content=conversational_response,
            timestamp=datetime.utcnow(),
            analysis_data=analysis.dict() if analysis else None
        )

        db.add(assistant_message)

        # Update session
        session.updated_at = datetime.utcnow()
        session.message_count += 2

        await db.commit()

        # Get product recommendations if analysis is available
        recommended_products = []
        if analysis:
            recommended_products = await _get_product_recommendations(
                analysis, db, limit=10, user_id=session.user_id, session_id=session_id
            )

        # Smart 3-mode visualization detection
        visualization_image = None

        # Get conversation messages from database for context (MOVED BEFORE USE)
        messages_query = select(ChatMessage).where(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.timestamp)
        messages_result = await db.execute(messages_query)
        messages = list(messages_result.scalars().all())

        # Use NLP to detect user intent
        intent_result = await design_nlp_processor.classify_intent(request.message)

        # Helper function to find last generated visualization in conversation
        def find_last_generated_visualization():
            """Find the most recent AI-generated visualization image"""
            # Get messages from database in reverse order
            for msg in reversed(messages):
                # Check if message has an image URL that's a data URI (AI-generated)
                if msg.image_url and msg.image_url.startswith('data:image'):
                    return msg.image_url
            return None

        # MODE 3: Iterative Improvement - User modifying existing generated image
        if intent_result.primary_intent == "image_modification":
            last_viz = find_last_generated_visualization()
            if last_viz:
                logger.info(f"Detected image modification intent: {request.message[:50]}...")
                try:
                    # Extract lighting conditions from analysis if available
                    lighting_conditions = "mixed"
                    if analysis and hasattr(analysis, 'design_analysis') and analysis.design_analysis:
                        space_analysis = analysis.design_analysis.get('space_analysis', {})
                        if isinstance(space_analysis, dict):
                            lighting_conditions = space_analysis.get('lighting_conditions', 'mixed')

                    # Generate iterative visualization
                    viz_result = await google_ai_service.generate_iterative_visualization(
                        base_image=last_viz,
                        modification_request=request.message,
                        lighting_conditions=lighting_conditions,
                        render_quality="high"
                    )

                    visualization_image = viz_result.rendered_image
                    logger.info("Successfully generated iterative visualization")
                except Exception as viz_error:
                    logger.error(f"Failed to generate iterative visualization: {viz_error}")
            else:
                logger.info("Image modification intent detected but no previous visualization found")

        # MODE 2: Full Transformation - User uploaded image + wants transformation
        elif request.image and request.message:
            # Visualization keywords that indicate user wants image transformation
            visualization_keywords = [
                'visualize', 'transform', 'make this', 'redesign',
                'modernize', 'see how', 'would look', 'convert', 'turn into'
            ]

            message_lower = request.message.lower()
            has_visualization_intent = (
                intent_result.primary_intent == "visualization" or
                any(keyword in message_lower for keyword in visualization_keywords)
            )

            # If visualization intent detected with image, generate visualization
            if has_visualization_intent:
                logger.info(f"Detected full transformation intent: {request.message[:50]}...")
                try:
                    # Extract lighting conditions from analysis if available
                    lighting_conditions = "mixed"
                    if analysis and hasattr(analysis, 'design_analysis') and analysis.design_analysis:
                        space_analysis = analysis.design_analysis.get('space_analysis', {})
                        if isinstance(space_analysis, dict):
                            lighting_conditions = space_analysis.get('lighting_conditions', 'mixed')

                    # Generate text-based visualization
                    viz_result = await google_ai_service.generate_text_based_visualization(
                        base_image=request.image,
                        user_request=request.message,
                        lighting_conditions=lighting_conditions,
                        render_quality="high"
                    )

                    visualization_image = viz_result.rendered_image
                    logger.info("Successfully generated text-based visualization")
                except Exception as viz_error:
                    logger.error(f"Failed to generate text-based visualization: {viz_error}")

        # MODE 1: Product Recommendations - Default behavior when no visualization needed
        # This happens automatically below when recommended_products are fetched

        # Create response message schema
        message_schema = ChatMessageSchema(
            id=assistant_message_id,
            type=MessageType.assistant,
            content=conversational_response,
            timestamp=assistant_message.timestamp,
            session_id=session_id,
            products=recommended_products,
            image_url=visualization_image  # Include visualization if generated
        )

        return ChatMessageResponse(
            message=message_schema,
            analysis=analysis,
            recommended_products=recommended_products
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Error processing message: {e}\n{error_traceback}")
        # Include detailed error information for debugging
        error_type = type(e).__name__
        error_detail = f"{error_type}: {str(e)}"
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get chat history for a session"""
    try:
        # Get session
        session_query = select(ChatSession).where(ChatSession.id == session_id)
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Get messages
        messages_query = select(ChatMessage).where(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.timestamp)

        messages_result = await db.execute(messages_query)
        messages = messages_result.scalars().all()

        # Convert to schemas
        message_schemas = []
        for message in messages:
            products = []
            if message.analysis_data and message.type == MessageType.assistant:
                # Get product recommendations from analysis
                try:
                    analysis = DesignAnalysisSchema(**message.analysis_data)
                    products = await _get_product_recommendations(analysis, db)
                except Exception as e:
                    logger.warning(f"Error loading analysis data for message {message.id}: {e}")

            message_schema = ChatMessageSchema(
                id=message.id,
                type=message.type,
                content=message.content,
                timestamp=message.timestamp,
                session_id=message.session_id,
                products=products,
                image_url=message.image_url
            )
            message_schemas.append(message_schema)

        session_schema = ChatSessionSchema(
            id=session.id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=session.message_count,
            user_id=session.user_id
        )

        return ChatHistoryResponse(
            session=session_schema,
            messages=message_schemas
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error fetching chat history: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/sessions/{session_id}/visualize")
async def visualize_room(
    session_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """Generate room visualization with selected products using Google AI Studio"""
    try:
        # Verify session exists
        session_query = select(ChatSession).where(ChatSession.id == session_id)
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Extract request data
        base_image = request.get('image')
        products = request.get('products', [])
        analysis = request.get('analysis')

        if not base_image:
            raise HTTPException(status_code=400, detail="Image is required")

        if not products:
            raise HTTPException(status_code=400, detail="At least one product must be selected")

        # Get full product details with images from database
        product_ids = [p.get('id') for p in products if p.get('id')]
        if product_ids:
            from sqlalchemy.orm import selectinload
            query = select(Product).options(selectinload(Product.images)).where(Product.id.in_(product_ids))
            result = await db.execute(query)
            db_products = result.scalars().all()

            # Enrich products with image URLs
            for product in products:
                db_product = next((p for p in db_products if p.id == product.get('id')), None)
                if db_product and db_product.images:
                    primary_image = next((img for img in db_product.images if img.is_primary), db_product.images[0])
                    if primary_image:
                        product['image_url'] = primary_image.original_url
                        product['full_name'] = db_product.name

        # Get user's style description from analysis
        user_style_description = ""
        lighting_conditions = "mixed"

        if analysis:
            design_analysis = analysis.get('design_analysis', {})
            if design_analysis:
                # Style preferences
                style_prefs = design_analysis.get('style_preferences', {})
                if isinstance(style_prefs, dict):
                    primary_style = style_prefs.get('primary_style', '')
                    style_keywords = style_prefs.get('style_keywords', [])
                    if primary_style:
                        user_style_description += f"{primary_style} style. "
                    if style_keywords:
                        user_style_description += f"Style keywords: {', '.join(style_keywords)}. "

                # Space analysis
                space_analysis = design_analysis.get('space_analysis', {})
                if isinstance(space_analysis, dict):
                    lighting_conditions = space_analysis.get('lighting_conditions', 'mixed')

        # Create visualization request
        viz_request = VisualizationRequest(
            base_image=base_image,
            products_to_place=products,
            placement_positions=[],
            lighting_conditions=lighting_conditions,
            render_quality="high",
            style_consistency=True,
            user_style_description=user_style_description
        )

        # Generate visualization using Google AI Studio
        viz_result = await google_ai_service.generate_room_visualization(viz_request)

        # Note: Due to AI model limitations, the visualization shows a design concept
        # The room structure may vary from the original as generative models create new images
        # rather than editing existing ones. For pixel-perfect preservation, an inpainting model
        # would be required. See VISUALIZATION_ANALYSIS.md for technical details.

        return {
            "rendered_image": viz_result.rendered_image,
            "message": "Visualization generated successfully. Note: This shows a design concept with your selected products.",
            "technical_note": "Generative AI models create new images rather than edit existing ones. Some variation in room structure is expected."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating visualization: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating visualization: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a chat session and all its messages"""
    try:
        # Verify session exists
        session_query = select(ChatSession).where(ChatSession.id == session_id)
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Delete messages first (due to foreign key constraints)
        messages_query = select(ChatMessage).where(ChatMessage.session_id == session_id)
        messages_result = await db.execute(messages_query)
        messages = messages_result.scalars().all()

        for message in messages:
            await db.delete(message)

        # Delete session
        await db.delete(session)
        await db.commit()

        # Clear conversation context from ChatGPT service
        chatgpt_service.clear_conversation_context(session_id)

        return {"message": "Chat session deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error deleting chat session: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


async def _get_product_recommendations(
    analysis: DesignAnalysisSchema,
    db: AsyncSession,
    limit: int = 10,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> List[dict]:
    """Get advanced product recommendations based on design analysis"""
    try:
        # Extract preferences from analysis
        user_preferences = {}
        style_preferences = []
        functional_requirements = []
        budget_range = None
        room_context = None

        # Extract design analysis data
        if hasattr(analysis, 'design_analysis') and analysis.design_analysis:
            design_analysis = analysis.design_analysis
            if isinstance(design_analysis, dict):
                # Style preferences
                style_prefs = design_analysis.get('style_preferences', {})
                if isinstance(style_prefs, dict):
                    primary_style = style_prefs.get('primary_style', '')
                    secondary_styles = style_prefs.get('secondary_styles', [])
                    if primary_style:
                        style_preferences.append(primary_style)
                    style_preferences.extend(secondary_styles)

                # Color preferences
                color_scheme = design_analysis.get('color_scheme', {})
                if isinstance(color_scheme, dict):
                    user_preferences['colors'] = (
                        color_scheme.get('preferred_colors', []) +
                        color_scheme.get('accent_colors', [])
                    )

                # Functional requirements
                func_reqs = design_analysis.get('functional_requirements', {})
                if isinstance(func_reqs, dict):
                    functional_requirements = func_reqs.get('primary_functions', [])

                # Budget indicators
                budget_indicators = design_analysis.get('budget_indicators', {})
                if isinstance(budget_indicators, dict):
                    price_range = budget_indicators.get('price_range', 'mid-range')
                    budget_range = _map_budget_range(price_range)

                # Room context
                space_analysis = design_analysis.get('space_analysis', {})
                if isinstance(space_analysis, dict):
                    room_context = {
                        'room_type': space_analysis.get('room_type', 'living_room'),
                        'dimensions': space_analysis.get('dimensions', ''),
                        'layout_type': space_analysis.get('layout_type', 'open')
                    }

        # Extract material preferences from product matching criteria
        if hasattr(analysis, 'product_matching_criteria') and analysis.product_matching_criteria:
            criteria = analysis.product_matching_criteria
            if isinstance(criteria, dict):
                filtering = criteria.get('filtering_keywords', {})
                if isinstance(filtering, dict):
                    user_preferences['materials'] = filtering.get('material_preferences', [])

        # Create recommendation request
        recommendation_request = RecommendationRequest(
            user_preferences=user_preferences,
            room_context=room_context,
            budget_range=budget_range,
            style_preferences=style_preferences,
            functional_requirements=functional_requirements,
            max_recommendations=limit
        )

        # Get advanced recommendations
        recommendation_response = await recommendation_engine.get_recommendations(
            recommendation_request, db, user_id
        )

        # Convert recommendations to product data
        product_recommendations = []
        if recommendation_response.recommendations:
            # Get product details for recommended products (eagerly load images)
            from sqlalchemy.orm import selectinload

            recommended_ids = [rec.product_id for rec in recommendation_response.recommendations]
            query = select(Product).options(selectinload(Product.images)).where(Product.id.in_(recommended_ids))
            result = await db.execute(query)
            products_dict = {product.id: product for product in result.scalars().all()}

            for rec in recommendation_response.recommendations:
                product = products_dict.get(rec.product_id)
                if product:
                    primary_image = None
                    if product.images:
                        primary_image = next((img for img in product.images if img.is_primary), product.images[0])

                    product_dict = {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "currency": product.currency,
                        "brand": product.brand,
                        "source_website": product.source_website,
                        "source_url": product.source_url,
                        "is_on_sale": product.is_on_sale,
                        "primary_image": {
                            "url": primary_image.original_url if primary_image else None,
                            "alt_text": primary_image.alt_text if primary_image else product.name
                        } if primary_image else None,
                        # Add recommendation metadata
                        "recommendation_data": {
                            "confidence_score": rec.confidence_score,
                            "reasoning": rec.reasoning,
                            "style_match": rec.style_match_score,
                            "functional_match": rec.functional_match_score,
                            "price_score": rec.price_score,
                            "overall_score": rec.overall_score
                        }
                    }
                    product_recommendations.append(product_dict)

        # If advanced recommendations failed or returned few results, fall back to basic search
        if len(product_recommendations) < limit // 2:
            logger.info("Using fallback recommendation method")
            fallback_recommendations = await _get_basic_product_recommendations(
                analysis, db, limit - len(product_recommendations)
            )
            product_recommendations.extend(fallback_recommendations)

        return product_recommendations[:limit]

    except Exception as e:
        logger.error(f"Error getting advanced product recommendations: {e}")
        # Fallback to basic recommendations
        return await _get_basic_product_recommendations(analysis, db, limit)


def _map_budget_range(price_range: str) -> Tuple[float, float]:
    """Map budget indicators to price ranges"""
    budget_map = {
        'budget': (0, 500),
        'mid-range': (500, 2000),
        'premium': (2000, 5000),
        'luxury': (5000, 50000)
    }
    return budget_map.get(price_range, (0, 10000))


async def _get_basic_product_recommendations(
    analysis: DesignAnalysisSchema,
    db: AsyncSession,
    limit: int = 10
) -> List[dict]:
    """Basic product recommendations as fallback"""
    try:
        # Simple keyword-based search (eagerly load images)
        from sqlalchemy.orm import selectinload

        query = select(Product).options(selectinload(Product.images)).where(Product.is_available == True).limit(limit)
        result = await db.execute(query)
        products = result.scalars().all()

        product_recommendations = []
        for product in products:
            primary_image = None
            if product.images:
                primary_image = next((img for img in product.images if img.is_primary), product.images[0])

            product_dict = {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "currency": product.currency,
                "brand": product.brand,
                "source_website": product.source_website,
                "source_url": product.source_url,
                "is_on_sale": product.is_on_sale,
                "primary_image": {
                    "url": primary_image.original_url if primary_image else None,
                    "alt_text": primary_image.alt_text if primary_image else product.name
                } if primary_image else None,
                "recommendation_data": {
                    "confidence_score": 0.5,
                    "reasoning": ["Basic search result"],
                    "style_match": 0.5,
                    "functional_match": 0.5,
                    "price_score": 0.5,
                    "overall_score": 0.5
                }
            }
            product_recommendations.append(product_dict)

        return product_recommendations

    except Exception as e:
        logger.error(f"Error in basic product recommendations: {e}")
        return []


@router.get("/sessions/{session_id}/context")
async def get_conversation_context(session_id: str):
    """Get conversation context for a session"""
    try:
        context = chatgpt_service.get_conversation_context(session_id)
        return {
            "session_id": session_id,
            "context": context,
            "context_length": len(context)
        }
    except Exception as e:
        import traceback
        logger.error(f"Error getting conversation context: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.delete("/sessions/{session_id}/context")
async def clear_conversation_context(session_id: str):
    """Clear conversation context for a session"""
    try:
        chatgpt_service.clear_conversation_context(session_id)
        return {"message": f"Conversation context cleared for session {session_id}"}
    except Exception as e:
        import traceback
        logger.error(f"Error clearing conversation context: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.get("/health")
async def chat_health_check():
    """Perform health check on chat service"""
    try:
        health_status = await chatgpt_service.health_check()
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/usage-stats")
async def get_usage_statistics():
    """Get ChatGPT API usage statistics"""
    try:
        stats = chatgpt_service.get_usage_stats()
        return stats
    except Exception as e:
        import traceback
        logger.error(f"Error getting usage stats: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/usage-stats/reset")
async def reset_usage_statistics():
    """Reset ChatGPT API usage statistics"""
    try:
        chatgpt_service.reset_usage_stats()
        return {"message": "Usage statistics reset successfully"}
    except Exception as e:
        import traceback
        logger.error(f"Error resetting usage stats: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/sessions/{session_id}/analyze-preference")
async def analyze_user_preference(
    session_id: str,
    request: dict,  # Contains preference_text
    db: AsyncSession = Depends(get_db)
):
    """Analyze user preference text for design insights"""
    try:
        preference_text = request.get("preference_text", "")
        if not preference_text:
            raise HTTPException(status_code=400, detail="preference_text is required")

        # Use ChatGPT to analyze preferences
        conversational_response, analysis = await chatgpt_service.analyze_user_input(
            user_message=f"Analyze these design preferences: {preference_text}",
            session_id=session_id
        )

        return {
            "analysis": analysis,
            "insights": conversational_response,
            "session_id": session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error analyzing user preference: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/sessions/{session_id}/generate-style-guide")
async def generate_style_guide(
    session_id: str,
    request: dict,  # Contains room_type, style_preferences, etc.
    db: AsyncSession = Depends(get_db)
):
    """Generate a comprehensive style guide based on conversation history"""
    try:
        # Get conversation context
        context = chatgpt_service.get_conversation_context(session_id)

        if not context:
            raise HTTPException(status_code=400, detail="No conversation context found")

        # Create style guide request
        style_guide_prompt = f"""
        Based on our conversation, create a comprehensive interior design style guide.

        Request details: {request}

        Generate a detailed style guide that includes:
        1. Overall design theme and aesthetic
        2. Color palette recommendations
        3. Material and texture suggestions
        4. Furniture style guidelines
        5. Lighting recommendations
        6. Accessory and decor suggestions
        7. Room layout principles
        """

        conversational_response, analysis = await chatgpt_service.analyze_user_input(
            user_message=style_guide_prompt,
            session_id=session_id
        )

        return {
            "style_guide": conversational_response,
            "analysis": analysis,
            "session_id": session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error generating style guide: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")