"""
Chat API routes for interior design assistance
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
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

        # Initialize response fields
        recommended_products = []
        detected_furniture = None
        similar_furniture_items = None
        action_options = None
        requires_action_choice = False
        visualization_image = None

        # =================================================================
        # STEP 1: Initial Request (image + message, no product selected)
        # =================================================================
        if request.image and request.message and not request.selected_product_id and not request.user_action:
            logger.info("STEP 1: Initial request - detecting furniture and getting product recommendations")

            # Detect furniture in the uploaded image
            try:
                detected_furniture = await google_ai_service.detect_furniture_in_image(request.image)
                logger.info(f"Detected {len(detected_furniture) if detected_furniture else 0} furniture items")
            except Exception as e:
                logger.error(f"Error detecting furniture: {e}")
                detected_furniture = []

            # Get product recommendations
            if analysis:
                recommended_products = await _get_product_recommendations(
                    analysis, db, user_message=request.message, limit=30,
                    user_id=session.user_id, session_id=session_id
                )
            else:
                logger.warning(f"Analysis is None for session {session_id}, using fallback recommendations")
                from api.schemas.chat import DesignAnalysisSchema
                fallback_analysis = DesignAnalysisSchema(
                    design_analysis={},
                    product_matching_criteria={},
                    visualization_guidance={},
                    confidence_scores={},
                    recommendations={}
                )
                recommended_products = await _get_basic_product_recommendations(
                    fallback_analysis, db, limit=30
                )

        # =================================================================
        # STEP 2: Visualize Request (product selected, no action yet)
        # =================================================================
        elif request.selected_product_id and not request.user_action:
            logger.info("STEP 2: Visualize request - checking if furniture exists for ADD/REPLACE options")

            # Get product from DB
            product_query = select(Product).where(Product.id == int(request.selected_product_id))
            result = await db.execute(product_query)
            product = result.scalar_one_or_none()

            if not product:
                raise HTTPException(status_code=404, detail="Product not found")

            # Determine furniture type from product name
            furniture_type = _extract_furniture_type(product.name)
            logger.info(f"Extracted furniture type: {furniture_type} from product: {product.name}")

            # Get stored room image from conversation context
            stored_image = conversation_context_manager.get_last_image(session_id)

            if stored_image:
                # Check if similar furniture exists in the image
                try:
                    exists, matching_items = await google_ai_service.check_furniture_exists(
                        stored_image, furniture_type
                    )

                    similar_furniture_items = matching_items if exists else []

                    if exists and matching_items:
                        # Furniture exists - user can ADD or REPLACE
                        action_options = ["add", "replace"]
                        requires_action_choice = True
                        logger.info(f"Found {len(matching_items)} matching {furniture_type} items - user can ADD or REPLACE")
                    else:
                        # No matching furniture - user can only ADD
                        action_options = ["add"]
                        requires_action_choice = False
                        logger.info(f"No matching {furniture_type} found - user can only ADD")
                except Exception as e:
                    logger.error(f"Error checking furniture existence: {e}")
                    # Default to ADD only on error
                    similar_furniture_items = []
                    action_options = ["add"]
                    requires_action_choice = False
            else:
                logger.warning("No stored image found in conversation context")
                # Default to ADD only if no image
                similar_furniture_items = []
                action_options = ["add"]
                requires_action_choice = False

        # =================================================================
        # STEP 3: Action Execution (product selected + action specified)
        # =================================================================
        elif request.selected_product_id and request.user_action:
            logger.info(f"STEP 3: Executing {request.user_action} action for product {request.selected_product_id}")

            # Get product from DB with images
            product_query = select(Product).options(selectinload(Product.images)).where(
                Product.id == int(request.selected_product_id)
            )
            result = await db.execute(product_query)
            product = result.scalar_one_or_none()

            if not product:
                raise HTTPException(status_code=404, detail="Product not found")

            # Get product image URL
            product_image_url = None
            if product.images:
                primary_img = next((img for img in product.images if img.is_primary), product.images[0])
                product_image_url = primary_img.original_url if primary_img else None

            # Get stored room image from conversation context
            room_image = conversation_context_manager.get_last_image(session_id)
            if not room_image:
                raise HTTPException(status_code=400, detail="No room image found in conversation. Please upload an image first.")

            # Extract furniture type
            furniture_type = _extract_furniture_type(product.name)

            # Generate visualization based on action
            try:
                if request.user_action == "add":
                    logger.info(f"Generating ADD visualization for {product.name}")
                    visualization_image = await google_ai_service.generate_add_visualization(
                        room_image=room_image,
                        product_name=product.name,
                        product_image=product_image_url
                    )
                elif request.user_action == "replace":
                    logger.info(f"Generating REPLACE visualization for {product.name} (replacing {furniture_type})")
                    visualization_image = await google_ai_service.generate_replace_visualization(
                        room_image=room_image,
                        product_name=product.name,
                        furniture_type=furniture_type,
                        product_image=product_image_url
                    )
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid action: {request.user_action}. Must be 'add' or 'replace'")

                logger.info("Visualization generated successfully")
            except Exception as viz_error:
                logger.error(f"Error generating visualization: {viz_error}")
                raise HTTPException(status_code=500, detail=f"Failed to generate visualization: {str(viz_error)}")

        # =================================================================
        # Default: No special workflow triggered
        # =================================================================
        else:
            # Get product recommendations for default responses
            if analysis:
                recommended_products = await _get_product_recommendations(
                    analysis, db, user_message=request.message, limit=30,
                    user_id=session.user_id, session_id=session_id
                )

        # Create response message schema
        message_schema = ChatMessageSchema(
            id=assistant_message_id,
            type=MessageType.assistant,
            content=conversational_response,
            timestamp=assistant_message.timestamp,
            session_id=session_id,
            products=recommended_products,
            image_url=visualization_image
        )

        return ChatMessageResponse(
            message=message_schema,
            analysis=analysis,
            recommended_products=recommended_products,
            detected_furniture=detected_furniture,
            similar_furniture_items=similar_furniture_items,
            requires_action_choice=requires_action_choice,
            action_options=action_options
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
        user_action = request.get('action')  # "replace_one", "replace_all", "add", or None

        if not base_image:
            raise HTTPException(status_code=400, detail="Image is required")

        if not products:
            raise HTTPException(status_code=400, detail="At least one product must be selected")

        # Detect existing furniture in the room if not yet done
        existing_furniture = request.get('existing_furniture')
        if not existing_furniture:
            logger.info("Detecting existing furniture in room image...")
            objects = await google_ai_service.detect_objects_in_room(base_image)
            existing_furniture = objects

        # Check if selected product matches existing furniture category
        selected_product_types = set()
        for product in products:
            product_name = product.get('name', '').lower()
            # Extract furniture type - order matters!
            if 'sofa' in product_name or 'couch' in product_name:
                selected_product_types.add('sofa')
            elif 'table' in product_name:
                # Distinguish between center tables and side tables
                if 'coffee' in product_name or 'center' in product_name or 'centre' in product_name:
                    selected_product_types.add('center_table')
                elif 'side' in product_name or 'end' in product_name or 'nightstand' in product_name or 'bedside' in product_name:
                    selected_product_types.add('side_table')
                elif 'dining' in product_name:
                    selected_product_types.add('dining_table')
                elif 'console' in product_name:
                    selected_product_types.add('console_table')
                else:
                    selected_product_types.add('table')
            elif 'chair' in product_name or 'armchair' in product_name:
                selected_product_types.add('chair')
            elif 'lamp' in product_name:
                selected_product_types.add('lamp')
            # Add more categories as needed

        # Find matching existing furniture - STRICT MATCHING for tables
        matching_existing = []
        for obj in existing_furniture:
            obj_type = obj.get('object_type', '').lower()

            # Strict table matching - center tables don't match side tables
            for ptype in selected_product_types:
                matched = False

                if ptype == 'center_table':
                    # Center table only matches center_table, coffee_table
                    if obj_type in ['center_table', 'coffee_table', 'centre_table']:
                        matched = True
                elif ptype == 'side_table':
                    # Side table only matches side_table, end_table, nightstand
                    if obj_type in ['side_table', 'end_table', 'nightstand', 'bedside_table']:
                        matched = True
                elif ptype == 'dining_table':
                    # Dining table only matches dining_table
                    if obj_type == 'dining_table':
                        matched = True
                elif ptype == 'console_table':
                    # Console table only matches console_table
                    if obj_type == 'console_table':
                        matched = True
                else:
                    # For non-table furniture, use existing matching logic
                    if obj_type == ptype or ptype in obj_type:
                        matched = True

                if matched:
                    matching_existing.append(obj)
                    break

        # If we found matching furniture and user hasn't specified action yet, ask for clarification
        if matching_existing and not user_action:
            product_type_display = list(selected_product_types)[0].replace('_', ' ')
            count = len(matching_existing)
            plural = 's' if count > 1 else ''

            clarification_message = f"I see there {'are' if count > 1 else 'is'} {count} {product_type_display}{plural} in your room. Would you like me to:\n\n"

            if count == 1:
                clarification_message += f"a) Replace the existing {product_type_display} with the selected {product_type_display}\n"
                clarification_message += f"b) Add the selected {product_type_display} to the room (keep existing {product_type_display})\n"
            else:
                clarification_message += f"a) Replace one of the existing {product_type_display}{plural} with the selected {product_type_display}\n"
                clarification_message += f"b) Replace all {count} {product_type_display}{plural} with the selected {product_type_display}\n"
                clarification_message += f"c) Add the selected {product_type_display} to the room (keep all existing {product_type_display}{plural})\n"

            clarification_message += "\nPlease respond with your choice (a, b, or c)."

            return {
                "needs_clarification": True,
                "message": clarification_message,
                "existing_furniture": existing_furniture,
                "matching_count": count,
                "product_type": product_type_display
            }

        # If user provided action, prepare visualization instruction
        visualization_instruction = ""
        if user_action:
            product_type_display = list(selected_product_types)[0].replace('_', ' ') if selected_product_types else "furniture"

            if user_action == "replace_one":
                visualization_instruction = f"Replace ONE of the existing {product_type_display}s with the selected product. Keep all other furniture unchanged."
            elif user_action == "replace_all":
                visualization_instruction = f"Replace ALL existing {product_type_display}s with the selected product. Remove all {product_type_display}s currently in the room and place only the new one."
            elif user_action == "add":
                visualization_instruction = f"Add the selected {product_type_display} to the room. Keep all existing {product_type_display}s in their current positions."
            else:
                visualization_instruction = "Place the selected product naturally in the room."
        else:
            # No matching furniture found, proceed normally
            visualization_instruction = "Place the selected product naturally in an appropriate location in the room."

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
        user_style_description = visualization_instruction  # Use the clarification-based instruction
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
                        user_style_description += f" {primary_style} style. "
                    if style_keywords:
                        user_style_description += f"Style keywords: {', '.join(style_keywords)}. "

                # Space analysis
                space_analysis = design_analysis.get('space_analysis', {})
                if isinstance(space_analysis, dict):
                    lighting_conditions = space_analysis.get('lighting_conditions', 'mixed')

        logger.info(f"Generating visualization with instruction: {user_style_description}")

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

        # Push visualization to history for undo/redo support
        # First, push the ORIGINAL state if history is empty (first visualization)
        context = conversation_context_manager.get_or_create_context(session_id)
        if context.visualization_history is None or len(context.visualization_history) == 0:
            original_state = {
                "rendered_image": base_image,
                "products": [],
                "user_action": None,
                "existing_furniture": existing_furniture
            }
            conversation_context_manager.push_visualization_state(session_id, original_state)

        # Then push the NEW visualization state
        visualization_data = {
            "rendered_image": viz_result.rendered_image,
            "products": products,
            "user_action": user_action,
            "existing_furniture": existing_furniture
        }
        conversation_context_manager.push_visualization_state(session_id, visualization_data)

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


@router.post("/sessions/{session_id}/visualization/undo")
async def undo_visualization(session_id: str):
    """Undo last visualization and return previous state"""
    try:
        # Get previous visualization state from context manager
        previous_state = conversation_context_manager.undo_visualization(session_id)

        if previous_state is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot undo: No previous visualization available"
            )

        logger.info(f"Undid visualization for session {session_id}")

        return {
            "visualization": previous_state,
            "message": "Successfully undid last visualization",
            "can_undo": conversation_context_manager.can_undo(session_id),
            "can_redo": conversation_context_manager.can_redo(session_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error undoing visualization: {e}")
        raise HTTPException(status_code=500, detail=f"Error undoing visualization: {str(e)}")


@router.post("/sessions/{session_id}/visualization/redo")
async def redo_visualization(session_id: str):
    """Redo visualization and return next state"""
    try:
        # Get next visualization state from context manager
        next_state = conversation_context_manager.redo_visualization(session_id)

        if next_state is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot redo: No next visualization available"
            )

        logger.info(f"Redid visualization for session {session_id}")

        return {
            "visualization": next_state,
            "message": "Successfully redid visualization",
            "can_undo": conversation_context_manager.can_undo(session_id),
            "can_redo": conversation_context_manager.can_redo(session_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redoing visualization: {e}")
        raise HTTPException(status_code=500, detail=f"Error redoing visualization: {str(e)}")


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


def _extract_furniture_type(product_name: str) -> str:
    """Extract furniture type from product name with specific table categorization"""
    name_lower = product_name.lower()

    if 'sofa' in name_lower or 'couch' in name_lower or 'sectional' in name_lower:
        return 'sofa'
    elif 'chair' in name_lower or 'armchair' in name_lower:
        return 'chair'
    elif 'table' in name_lower:
        # Prioritize specific table types - order matters!
        if 'coffee' in name_lower or 'center' in name_lower or 'centre' in name_lower:
            return 'center table'  # For placement in front of sofa
        elif 'side' in name_lower or 'end' in name_lower or 'nightstand' in name_lower or 'bedside' in name_lower:
            return 'side table'  # For placement beside furniture
        elif 'dining' in name_lower:
            return 'dining table'
        elif 'console' in name_lower:
            return 'console table'
        return 'table'  # Generic fallback
    elif 'bed' in name_lower:
        return 'bed'
    elif 'lamp' in name_lower:
        return 'lamp'
    elif 'desk' in name_lower:
        return 'desk'
    elif 'cabinet' in name_lower or 'dresser' in name_lower:
        return 'cabinet'
    elif 'shelf' in name_lower or 'bookcase' in name_lower:
        return 'shelf'
    else:
        # Default: extract first word
        return name_lower.split()[0] if name_lower.split() else 'furniture'


def _extract_product_keywords(user_message: str) -> List[str]:
    """Extract product type keywords from user message with category awareness"""

    # Product keywords with synonyms and related terms - ORDER MATTERS (longer phrases first)
    # Format: (search_term, [keywords_to_return])
    product_patterns = [
        # Lighting - ceiling/overhead
        ('ceiling lamp', ['ceiling lamp', 'ceiling light', 'pendant', 'chandelier']),
        ('ceiling light', ['ceiling lamp', 'ceiling light', 'pendant', 'chandelier']),
        ('pendant light', ['pendant', 'ceiling lamp', 'ceiling light', 'chandelier']),
        ('pendant lamp', ['pendant', 'ceiling lamp', 'ceiling light', 'chandelier']),
        ('chandelier', ['chandelier', 'ceiling lamp', 'ceiling light', 'pendant']),
        ('overhead light', ['ceiling lamp', 'ceiling light', 'pendant', 'chandelier']),

        # Lighting - table/desk
        ('table lamp', ['table lamp', 'desk lamp']),
        ('desk lamp', ['desk lamp', 'table lamp']),

        # Lighting - floor
        ('floor lamp', ['floor lamp']),

        # Lighting - wall
        ('wall lamp', ['wall lamp', 'sconce', 'wall light']),
        ('sconce', ['sconce', 'wall lamp', 'wall light']),

        # Multi-word furniture - tables
        ('center table', ['coffee table', 'center table']),
        ('centre table', ['coffee table', 'center table']),
        ('coffee table', ['coffee table', 'center table']),
        ('dining table', ['dining table']),
        ('side table', ['side table', 'end table', 'nightstand']),
        ('end table', ['end table', 'side table']),
        ('nightstand', ['nightstand', 'side table', 'bedside table']),
        ('console table', ['console table', 'entry table']),

        # Multi-word furniture - chairs
        ('accent chair', ['accent chair', 'armchair']),
        ('dining chair', ['dining chair']),
        ('office chair', ['office chair', 'desk chair']),
        ('lounge chair', ['lounge chair', 'armchair']),

        # Multi-word furniture - sofas
        ('sectional sofa', ['sectional', 'sectional sofa']),
        ('leather sofa', ['sofa', 'couch']),

        # Single word furniture - only after checking multi-word
        ('sofa', ['sofa', 'couch', 'sectional']),
        ('couch', ['couch', 'sofa', 'sectional']),
        ('sectional', ['sectional', 'sofa', 'couch']),
        ('loveseat', ['loveseat', 'sofa']),
        ('chair', ['chair']),
        ('armchair', ['armchair', 'accent chair']),
        ('recliner', ['recliner']),
        ('table', ['table']),
        ('bed', ['bed']),
        ('mattress', ['mattress', 'bed']),
        ('headboard', ['headboard']),
        ('desk', ['desk']),
        ('workstation', ['desk', 'workstation']),
        ('dresser', ['dresser', 'chest']),
        ('chest', ['chest', 'dresser']),
        ('cabinet', ['cabinet']),
        ('bookshelf', ['bookshelf', 'shelving']),
        ('shelving', ['shelving', 'bookshelf', 'shelf']),
        ('shelf', ['shelf', 'shelving', 'bookshelf']),

        # Lighting - generic (only after specific types checked)
        ('lamp', ['lamp']),
        ('lighting', ['lighting']),

        # Other
        ('rug', ['rug', 'carpet']),
        ('carpet', ['carpet', 'rug']),
        ('mirror', ['mirror']),
        ('ottoman', ['ottoman']),
        ('bench', ['bench']),
        ('stool', ['stool']),
    ]

    message_lower = user_message.lower()
    found_keywords = []
    matched_phrases = set()  # Track which phrases we've already matched

    # Check patterns in order (longer phrases first due to order above)
    for search_term, keywords in product_patterns:
        if search_term in message_lower:
            # Check if this phrase overlaps with an already matched phrase
            # This prevents "lamp" from matching after "ceiling lamp" already matched
            overlaps = False
            for matched in matched_phrases:
                if search_term in matched or matched in search_term:
                    # If the new match is longer, replace the old match
                    if len(search_term) > len(matched):
                        overlaps = False
                        matched_phrases.discard(matched)
                        # Remove keywords from the old match
                        # (we'll add the new ones below)
                        break
                    else:
                        overlaps = True
                        break

            if not overlaps:
                matched_phrases.add(search_term)
                for keyword in keywords:
                    if keyword not in found_keywords:
                        found_keywords.append(keyword)

    logger.info(f"Extracted keywords from '{user_message}': {found_keywords}")
    return found_keywords


async def _get_product_recommendations(
    analysis: DesignAnalysisSchema,
    db: AsyncSession,
    user_message: str = "",
    limit: int = 30,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> List[dict]:
    """Get advanced product recommendations based on design analysis"""
    try:
        # Extract product keywords from user message
        product_keywords = _extract_product_keywords(user_message)

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

                # Budget indicators - ONLY set if explicitly provided
                budget_indicators = design_analysis.get('budget_indicators', {})
                if isinstance(budget_indicators, dict):
                    price_range = budget_indicators.get('price_range')
                    if price_range:  # Only map if actually specified
                        budget_range = _map_budget_range(price_range)
                        logger.info(f"Budget range from analysis: {price_range} -> ₹{budget_range[0]}-₹{budget_range[1]}")

                # Room context
                space_analysis = design_analysis.get('space_analysis', {})
                if isinstance(space_analysis, dict):
                    room_context = {
                        'room_type': space_analysis.get('room_type', 'living_room'),
                        'dimensions': space_analysis.get('dimensions', ''),
                        'layout_type': space_analysis.get('layout_type', 'open')
                    }

        # Extract material and product type preferences from product matching criteria
        if hasattr(analysis, 'product_matching_criteria') and analysis.product_matching_criteria:
            criteria = analysis.product_matching_criteria
            if isinstance(criteria, dict):
                filtering = criteria.get('filtering_keywords', {})
                if isinstance(filtering, dict):
                    user_preferences['materials'] = filtering.get('material_preferences', [])

                # PRIMARY: Extract product type keywords (e.g., "table", "sofa", "chair") - TOP PRIORITY
                product_types = criteria.get('product_types', [])
                if product_types:
                    user_preferences['product_keywords'] = product_types
                    logger.info(f"Extracted product_types from analysis: {product_types}")

                # SECONDARY: Also check for category names
                categories = criteria.get('categories', [])
                if categories:
                    if 'product_keywords' in user_preferences:
                        user_preferences['product_keywords'].extend(categories)
                    else:
                        user_preferences['product_keywords'] = categories
                    logger.info(f"Extracted categories from analysis: {categories}")

                # TERTIARY: Check for search terms
                search_terms = criteria.get('search_terms', [])
                if search_terms:
                    # Add search terms to product keywords as well for maximum matching
                    if 'product_keywords' in user_preferences:
                        user_preferences['product_keywords'].extend(search_terms)
                    else:
                        user_preferences['product_keywords'] = search_terms

                    # Also add to description keywords
                    if 'description_keywords' not in user_preferences:
                        user_preferences['description_keywords'] = []
                    user_preferences['description_keywords'].extend(search_terms)
                    logger.info(f"Extracted search_terms from analysis: {search_terms}")

        # FALLBACK: If no product keywords extracted from analysis, try to extract from original message
        if 'product_keywords' not in user_preferences or not user_preferences['product_keywords']:
            # Extract furniture keywords from the conversation context if available
            import re
            furniture_pattern = r'\b(sofa|table|chair|bed|desk|cabinet|shelf|dresser|nightstand|ottoman|bench|couch|sectional|sideboard|console|bookcase|armchair|stool|vanity|wardrobe|chest|mirror|lamp|chandelier)\b'

            # Get last user message from session_id context
            if session_id:
                context = chatgpt_service.get_conversation_context(session_id)
                if context:
                    last_message = context[-1] if context else ""
                    if isinstance(last_message, dict):
                        last_message = last_message.get('content', '')

                    matches = re.findall(furniture_pattern, last_message.lower())
                    if matches:
                        user_preferences['product_keywords'] = list(set(matches))
                        logger.info(f"Extracted product keywords from message: {matches}")

        # Create recommendation request
        recommendation_request = RecommendationRequest(
            user_preferences=user_preferences,
            room_context=room_context,
            budget_range=budget_range,
            style_preferences=style_preferences,
            functional_requirements=functional_requirements,
            product_keywords=product_keywords,
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

        # IMPORTANT: Only use fallback if NO specific product keywords were requested
        # If user asked for "vases" but we have no vases, show empty list instead of random products
        has_specific_keywords = 'product_keywords' in user_preferences and user_preferences['product_keywords']

        if len(product_recommendations) < limit // 2 and not has_specific_keywords:
            logger.info("Using fallback recommendation method (no specific keywords)")
            fallback_recommendations = await _get_basic_product_recommendations(
                analysis, db, limit - len(product_recommendations)
            )
            product_recommendations.extend(fallback_recommendations)
        elif len(product_recommendations) == 0 and has_specific_keywords:
            logger.info(f"No products found matching keywords: {user_preferences['product_keywords']}")
            # Return empty list - frontend should display "No products found"

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
    limit: int = 30
) -> List[dict]:
    """Basic product recommendations as fallback"""
    try:
        # Simple keyword-based search (eagerly load images)
        from sqlalchemy.orm import selectinload
        from sqlalchemy import func

        # Use random ordering and exclude small accessories for variety
        query = (
            select(Product)
            .options(selectinload(Product.images))
            .where(
                Product.is_available == True,
                ~Product.name.ilike('%pillow%'),
                ~Product.name.ilike('%cushion%'),
                ~Product.name.ilike('%throw%')
            )
            .order_by(func.random())
            .limit(limit * 2)  # Get more candidates for variety
        )
        result = await db.execute(query)
        products = list(result.scalars().all())[:limit]  # Take first 'limit' results

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