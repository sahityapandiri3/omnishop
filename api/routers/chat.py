"""
Chat API routes for interior design assistance
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
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
from database.models import ChatSession, ChatMessage, Product

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


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
        logger.error(f"Error starting chat session: {e}")
        raise HTTPException(status_code=500, detail="Error starting chat session")


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
            recommended_products = await _get_product_recommendations(analysis, db)

        # Create response message schema
        message_schema = ChatMessageSchema(
            id=assistant_message_id,
            type=MessageType.assistant,
            content=conversational_response,
            timestamp=assistant_message.timestamp,
            session_id=session_id,
            products=recommended_products
        )

        return ChatMessageResponse(
            message=message_schema,
            analysis=analysis,
            recommended_products=recommended_products
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail="Error processing message")


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
        logger.error(f"Error fetching chat history: {e}")
        raise HTTPException(status_code=500, detail="Error fetching chat history")


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
        logger.error(f"Error deleting chat session: {e}")
        raise HTTPException(status_code=500, detail="Error deleting chat session")


async def _get_product_recommendations(
    analysis: DesignAnalysisSchema,
    db: AsyncSession,
    limit: int = 10
) -> List[dict]:
    """Get product recommendations based on design analysis"""
    try:
        # Extract search criteria from analysis
        style_keywords = []
        color_preferences = []
        material_preferences = []

        # Get style keywords from design_analysis
        if hasattr(analysis, 'design_analysis') and analysis.design_analysis:
            design_analysis = analysis.design_analysis
            if isinstance(design_analysis, dict):
                style_prefs = design_analysis.get('style_preferences', {})
                if isinstance(style_prefs, dict):
                    style_keywords.extend(style_prefs.get('style_keywords', []))
                    style_keywords.append(style_prefs.get('primary_style', ''))

                # Get color preferences
                color_scheme = design_analysis.get('color_scheme', {})
                if isinstance(color_scheme, dict):
                    color_preferences.extend(color_scheme.get('preferred_colors', []))
                    color_preferences.extend(color_scheme.get('accent_colors', []))

        # Get material preferences
        if hasattr(analysis, 'product_matching_criteria') and analysis.product_matching_criteria:
            criteria = analysis.product_matching_criteria
            if isinstance(criteria, dict):
                filtering = criteria.get('filtering_keywords', {})
                if isinstance(filtering, dict):
                    material_preferences.extend(filtering.get('material_preferences', []))

        # Build search query
        search_terms = []
        search_terms.extend([kw for kw in style_keywords if kw])
        search_terms.extend([color for color in color_preferences if color])
        search_terms.extend([mat for mat in material_preferences if mat])

        # Query products
        query = select(Product).where(Product.is_available == True)

        # Apply search filters if we have terms
        if search_terms:
            search_conditions = []
            for term in search_terms[:5]:  # Limit to top 5 terms to avoid too complex query
                search_conditions.append(Product.name.ilike(f"%{term}%"))
                search_conditions.append(Product.description.ilike(f"%{term}%"))

            if search_conditions:
                from sqlalchemy import or_
                query = query.where(or_(*search_conditions))

        query = query.limit(limit)

        result = await db.execute(query)
        products = result.scalars().all()

        # Convert to dict format
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
                } if primary_image else None
            }
            product_recommendations.append(product_dict)

        return product_recommendations

    except Exception as e:
        logger.error(f"Error getting product recommendations: {e}")
        return []