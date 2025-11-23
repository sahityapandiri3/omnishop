"""
Chat API routes for interior design assistance
"""
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from core.database import get_db
from database.models import ChatMessage, ChatSession, Product
from fastapi import APIRouter, Depends, HTTPException
from schemas.chat import (
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatMessageSchema,
    ChatSessionSchema,
    DesignAnalysisSchema,
    MessageType,
    StartSessionRequest,
    StartSessionResponse,
)
from services.chatgpt_service import chatgpt_service
from services.conversation_context import conversation_context_manager
from services.google_ai_service import VisualizationRequest, VisualizationResult, google_ai_service
from services.ml_recommendation_model import ml_recommendation_model
from services.nlp_processor import design_nlp_processor
from services.recommendation_engine import RecommendationRequest, recommendation_engine
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/sessions", response_model=StartSessionResponse)
async def start_chat_session(request: StartSessionRequest, db: AsyncSession = Depends(get_db)):
    """Start a new chat session"""
    try:
        # Create new session
        session_id = str(uuid.uuid4())
        session = ChatSession(
            id=session_id, user_id=request.user_id, created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )

        db.add(session)
        await db.commit()

        return StartSessionResponse(
            session_id=session_id,
            message="Hello! I'm your AI interior design assistant. How can I help you transform your space today?",
        )

    except Exception as e:
        import traceback

        logger.error(f"Error starting chat session: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(session_id: str, request: ChatMessageRequest, db: AsyncSession = Depends(get_db)):
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
            image_url=request.image if request.image else None,
        )

        db.add(user_message)

        # Get AI response
        # Use active image (latest visualization OR original upload) for analysis
        active_image = conversation_context_manager.get_last_image(session_id) if session_id else None
        conversational_response, analysis = await chatgpt_service.analyze_user_input(
            user_message=request.message,
            session_id=session_id,
            image_data=active_image or request.image,  # Use active image, fallback to request
        )

        # Check if a timeout occurred (low confidence scores indicate fallback response)
        is_timeout = False
        background_task_id = None
        if analysis and analysis.confidence_scores:
            # Fallback responses have very low confidence scores (30-50)
            overall_confidence = analysis.confidence_scores.get("overall_analysis", 100)
            if overall_confidence < 60:
                is_timeout = True
                logger.info(
                    f"Timeout detected (confidence: {overall_confidence}%) - background task disabled (Redis not available)"
                )

                # TODO: Re-enable background tasks once Redis is added to Railway
                # Start background task for real AI analysis
                # from tasks.chatgpt_tasks import analyze_user_input_async
                # task = analyze_user_input_async.delay(
                #     user_message=request.message,
                #     session_id=session_id,
                #     image_data=active_image or request.image,
                #     user_id=session.user_id
                # )
                # background_task_id = task.id
                # logger.info(f"Started background task {background_task_id}")

                # Update conversational response to mention background processing
                # conversational_response = "I'm analyzing your request in detail. I'll show you some product recommendations now, and I'll refine them once the analysis is complete. You can refresh in a moment to see updated recommendations!"

        # Save assistant message
        assistant_message_id = str(uuid.uuid4())
        assistant_message = ChatMessage(
            id=assistant_message_id,
            session_id=session_id,
            type=MessageType.assistant,
            content=conversational_response,
            timestamp=datetime.utcnow(),
            analysis_data=analysis.dict() if analysis else None,
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
                    analysis,
                    db,
                    user_message=request.message,
                    limit=50,
                    user_id=session.user_id,
                    session_id=session_id,
                    selected_stores=request.selected_stores,
                )
            else:
                logger.warning(f"Analysis is None for session {session_id}, using fallback recommendations")
                from schemas.chat import DesignAnalysisSchema

                fallback_analysis = DesignAnalysisSchema(
                    design_analysis={},
                    product_matching_criteria={},
                    visualization_guidance={},
                    confidence_scores={},
                    recommendations={},
                )
                recommended_products = await _get_basic_product_recommendations(fallback_analysis, db, limit=50)

            # Enhance conversational response based on whether products were found
            if recommended_products and len(recommended_products) > 0:
                # Products found - mention they're being shown
                if " products" not in conversational_response.lower() and " showing" not in conversational_response.lower():
                    conversational_response += f" I've found {len(recommended_products)} product{'s' if len(recommended_products) > 1 else ''} that match your request - check them out in the Products panel!"
            else:
                # No products found - update response to mention this
                # Extract what they were searching for from the message
                search_terms = []
                materials_mentioned = []

                # Check if specific materials or product types were mentioned
                import re

                message_lower = request.message.lower()

                # Extract materials (wicker, leather, etc.)
                material_patterns = ["wicker", "leather", "velvet", "wood", "metal", "glass", "rattan", "bamboo"]
                for mat in material_patterns:
                    if mat in message_lower:
                        materials_mentioned.append(mat)

                # Build a more specific message
                if materials_mentioned:
                    material_str = " and ".join(materials_mentioned)
                    conversational_response = f"Unfortunately, I couldn't find any {material_str} products matching your request in our current inventory. However, you might want to try searching for similar items without the material specification, or check back later as we regularly add new products!"
                else:
                    conversational_response = f"Unfortunately, I couldn't find any products that exactly match your request in our current inventory. You might want to try a broader search or check back later as we regularly add new products!"

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
                    exists, matching_items = await google_ai_service.check_furniture_exists(stored_image, furniture_type)

                    similar_furniture_items = matching_items if exists else []

                    # Define furniture types that are additive-only (no replace)
                    additive_only_types = [
                        "chair",
                        "armchair",
                        "accent chair",
                        "side chair",
                        "sofa chair",
                        "dining chair",
                        "recliner",
                        "bench",
                        "stool",
                        "ottoman",
                        "lamp",
                        "table lamp",
                        "desk lamp",
                        "floor lamp",
                        "wall lamp",
                        "ceiling lamp",
                        "pendant",
                        "chandelier",
                        "sconce",
                        "lighting",
                        "bookshelf",
                        "shelving",
                        "shelf",
                        "dresser",
                        "cabinet",
                        "wardrobe",
                        "chest",
                        "storage",
                        "mirror",
                        "rug",
                        "carpet",
                        "wall rug",
                        "floor rug",
                        "tapestry",
                        "decor",
                    ]

                    # Check if this furniture type is additive-only
                    is_additive_only = any(additive_type in furniture_type.lower() for additive_type in additive_only_types)

                    if exists and matching_items and not is_additive_only:
                        # Furniture exists AND it's replaceable (like sofas) - user can ADD or REPLACE
                        action_options = ["add", "replace"]
                        requires_action_choice = True
                        logger.info(f"Found {len(matching_items)} matching {furniture_type} items - user can ADD or REPLACE")
                    else:
                        # No matching furniture OR it's additive-only (chairs, etc.) - user can only ADD
                        action_options = ["add"]
                        if is_additive_only:
                            logger.info(f"{furniture_type} is additive-only - user can only ADD (no replace option)")
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
            product_query = (
                select(Product).options(selectinload(Product.images)).where(Product.id == int(request.selected_product_id))
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
                raise HTTPException(
                    status_code=400, detail="No room image found in conversation. Please upload an image first."
                )

            # Extract furniture type
            furniture_type = _extract_furniture_type(product.name)

            # Generate visualization based on action
            try:
                if request.user_action == "add":
                    logger.info(f"Generating ADD visualization for {product.name}")
                    visualization_image = await google_ai_service.generate_add_visualization(
                        room_image=room_image, product_name=product.name, product_image=product_image_url
                    )
                elif request.user_action == "replace":
                    logger.info(f"Generating REPLACE visualization for {product.name} (replacing {furniture_type})")
                    visualization_image = await google_ai_service.generate_replace_visualization(
                        room_image=room_image,
                        product_name=product.name,
                        furniture_type=furniture_type,
                        product_image=product_image_url,
                    )
                else:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid action: {request.user_action}. Must be 'add' or 'replace'"
                    )

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
                    analysis,
                    db,
                    user_message=request.message,
                    limit=50,
                    user_id=session.user_id,
                    session_id=session_id,
                    selected_stores=request.selected_stores,
                )

        # Create response message schema
        message_schema = ChatMessageSchema(
            id=assistant_message_id,
            type=MessageType.assistant,
            content=conversational_response,
            timestamp=assistant_message.timestamp,
            session_id=session_id,
            products=recommended_products,
            image_url=visualization_image,
        )

        return ChatMessageResponse(
            message=message_schema,
            analysis=analysis,
            recommended_products=recommended_products,
            detected_furniture=detected_furniture,
            similar_furniture_items=similar_furniture_items,
            requires_action_choice=requires_action_choice,
            action_options=action_options,
            background_task_id=background_task_id,
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


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    Check the status of a background AI analysis task

    Returns:
        - status: PENDING, PROCESSING, SUCCESS, or FAILURE
        - result: The analysis result when complete
        - meta: Progress information
    """
    try:
        from celery.result import AsyncResult
        from celery_app import celery_app

        task_result = AsyncResult(task_id, app=celery_app)

        response = {"task_id": task_id, "status": task_result.state, "ready": task_result.ready()}

        if task_result.state == "PENDING":
            response["message"] = "Task is waiting to be processed..."
        elif task_result.state == "PROCESSING":
            response["message"] = "Analyzing your request with AI..."
            response["meta"] = task_result.info
        elif task_result.state == "SUCCESS":
            result = task_result.result
            response["message"] = "Analysis complete!"
            response["result"] = result

            # If successful, we can now get better product recommendations
            if result.get("status") == "success" and result.get("analysis"):
                try:
                    from schemas.chat import DesignAnalysisSchema

                    analysis = DesignAnalysisSchema(**result["analysis"])

                    # Get improved product recommendations
                    recommended_products = await _get_product_recommendations(
                        analysis,
                        db,
                        user_message=result.get("user_message", ""),
                        limit=50,
                        selected_stores=None,  # No store filtering in this context
                    )
                    response["result"]["recommended_products"] = recommended_products
                except Exception as e:
                    logger.error(f"Error getting improved recommendations: {e}")

        elif task_result.state == "FAILURE":
            response["message"] = "Analysis failed"
            response["error"] = str(task_result.info)
        else:
            response["message"] = f"Task state: {task_result.state}"

        return response

    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        messages_query = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp)

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
                    products = await _get_product_recommendations(analysis, db, selected_stores=None)
                except Exception as e:
                    logger.warning(f"Error loading analysis data for message {message.id}: {e}")

            message_schema = ChatMessageSchema(
                id=message.id,
                type=message.type,
                content=message.content,
                timestamp=message.timestamp,
                session_id=message.session_id,
                products=products,
                image_url=message.image_url,
            )
            message_schemas.append(message_schema)

        session_schema = ChatSessionSchema(
            id=session.id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=session.message_count,
            user_id=session.user_id,
        )

        return ChatHistoryResponse(session=session_schema, messages=message_schemas)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Error fetching chat history: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/sessions/{session_id}/visualize")
async def visualize_room(session_id: str, request: dict, db: AsyncSession = Depends(get_db)):
    """Generate room visualization with selected products using Google AI Studio"""
    try:
        # Verify session exists
        session_query = select(ChatSession).where(ChatSession.id == session_id)
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Extract request data
        base_image = request.get("image")
        products = request.get("products", [])
        analysis = request.get("analysis")
        user_action = request.get("action")  # "replace_one", "replace_all", "add", or None
        is_incremental = request.get("is_incremental", False)  # Smart re-visualization flag
        force_reset = request.get("force_reset", False)  # Force fresh visualization
        custom_positions = request.get("custom_positions", [])  # Optional furniture positions for edit mode

        if not base_image:
            raise HTTPException(status_code=400, detail="Image is required")

        if not products:
            raise HTTPException(status_code=400, detail="At least one product must be selected")

        # Check product count and enforce incremental visualization for larger sets
        # The Gemini API has input size limitations and fails with 500 errors when
        # processing 5+ products simultaneously. Use incremental mode as workaround.
        MAX_PRODUCTS_BATCH = 4
        forced_incremental = False
        if len(products) > MAX_PRODUCTS_BATCH and not is_incremental:
            logger.info(
                f"Product count ({len(products)}) exceeds batch limit ({MAX_PRODUCTS_BATCH}). Forcing incremental visualization."
            )
            is_incremental = True
            forced_incremental = True

        # Handle force reset - clear visualization history and start fresh
        if force_reset:
            logger.info(f"Force reset requested - clearing visualization history for session {session_id}")
            context = conversation_context_manager.get_or_create_context(session_id)
            context.visualization_history = []
            context.visualization_redo_stack = []

        # CRITICAL FIX: For incremental visualization, use the last visualization as base image
        # This ensures that when adding product 4 after products 1, 2, 3, we add to the
        # existing visualization (with all 3 products) rather than starting from the original empty room
        if is_incremental:
            context = conversation_context_manager.get_or_create_context(session_id)
            if context.visualization_history:
                # Use the most recent visualization as the base
                last_visualization = context.visualization_history[-1]
                base_image = last_visualization.get("rendered_image")
                logger.info(f"Incremental mode: Using last visualization from history as base image (history length: {len(context.visualization_history)})")
            else:
                logger.info(f"Incremental mode: No history available, using provided base image")

        # Store original image if this is a new upload
        # This is critical for undo functionality - allows undo to return to base image
        user_uploaded_new_image = request.get("user_uploaded_new_image", False)
        if user_uploaded_new_image or force_reset:
            logger.info(f"Storing original room image for session {session_id} (new upload or reset)")
            conversation_context_manager.store_image(session_id, base_image)

        # Detect existing furniture in the room if not yet done
        existing_furniture = request.get("existing_furniture")
        if not existing_furniture:
            logger.info("Detecting existing furniture in room image...")
            objects = await google_ai_service.detect_objects_in_room(base_image)
            existing_furniture = objects

        # Check if selected product matches existing furniture category
        selected_product_types = set()
        for product in products:
            product_name = product.get("name", "").lower()
            # Extract furniture type - order matters!
            if "sofa" in product_name or "couch" in product_name:
                selected_product_types.add("sofa")
            elif "table" in product_name:
                # Distinguish between center tables and side tables
                if "coffee" in product_name or "center" in product_name or "centre" in product_name:
                    selected_product_types.add("center_table")
                elif (
                    "side" in product_name
                    or "end" in product_name
                    or "nightstand" in product_name
                    or "bedside" in product_name
                ):
                    selected_product_types.add("side_table")
                elif "dining" in product_name:
                    selected_product_types.add("dining_table")
                elif "console" in product_name:
                    selected_product_types.add("console_table")
                else:
                    selected_product_types.add("table")
            elif "chair" in product_name or "armchair" in product_name:
                selected_product_types.add("chair")
            elif "lamp" in product_name:
                selected_product_types.add("lamp")
            # Add more categories as needed

        # Find matching existing furniture - STRICT MATCHING for tables
        matching_existing = []
        for obj in existing_furniture:
            obj_type = obj.get("object_type", "").lower()

            # Strict table matching - center tables don't match side tables
            for ptype in selected_product_types:
                matched = False

                if ptype == "center_table":
                    # Center table only matches center_table, coffee_table
                    if obj_type in ["center_table", "coffee_table", "centre_table"]:
                        matched = True
                elif ptype == "side_table":
                    # Side table only matches side_table, end_table, nightstand
                    if obj_type in ["side_table", "end_table", "nightstand", "bedside_table"]:
                        matched = True
                elif ptype == "dining_table":
                    # Dining table only matches dining_table
                    if obj_type == "dining_table":
                        matched = True
                elif ptype == "console_table":
                    # Console table only matches console_table
                    if obj_type == "console_table":
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
            product_type_display = list(selected_product_types)[0].replace("_", " ")
            count = len(matching_existing)
            plural = "s" if count > 1 else ""

            clarification_message = f"I see there {'are' if count > 1 else 'is'} {count} {product_type_display}{plural} in your room. Would you like me to:\n\n"

            if count == 1:
                clarification_message += (
                    f"a) Replace the existing {product_type_display} with the selected {product_type_display}\n"
                )
                clarification_message += (
                    f"b) Add the selected {product_type_display} to the room (keep existing {product_type_display})\n"
                )
            else:
                clarification_message += (
                    f"a) Replace one of the existing {product_type_display}{plural} with the selected {product_type_display}\n"
                )
                clarification_message += (
                    f"b) Replace all {count} {product_type_display}{plural} with the selected {product_type_display}\n"
                )
                clarification_message += f"c) Add the selected {product_type_display} to the room (keep all existing {product_type_display}{plural})\n"

            clarification_message += "\nPlease respond with your choice (a, b, or c)."

            return {
                "needs_clarification": True,
                "message": clarification_message,
                "existing_furniture": existing_furniture,
                "matching_count": count,
                "product_type": product_type_display,
            }

        # If user provided action, prepare visualization instruction
        visualization_instruction = ""
        if user_action:
            product_type_display = list(selected_product_types)[0].replace("_", " ") if selected_product_types else "furniture"

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
        # ISSUE #3 FIX: Cast product IDs to integers for database query (PostgreSQL requires type matching)
        product_ids = [int(p.get("id")) for p in products if p.get("id")]
        if product_ids:
            from sqlalchemy.orm import selectinload

            query = select(Product).options(selectinload(Product.images)).where(Product.id.in_(product_ids))
            result = await db.execute(query)
            db_products = result.scalars().all()

            # Enrich products with full details for proper undo/redo support
            for product in products:
                db_product = next((p for p in db_products if p.id == product.get("id")), None)
                if db_product:
                    # Add price and other essential fields
                    product["price"] = float(db_product.price) if db_product.price else 0.0
                    product["name"] = db_product.name
                    product["full_name"] = db_product.name
                    product["source"] = db_product.source_website

                    # Add image URLs
                    if db_product.images:
                        primary_image = next((img for img in db_product.images if img.is_primary), db_product.images[0])
                        if primary_image:
                            product["image_url"] = primary_image.original_url

                    # Add productType for frontend replacement logic
                    # Extract from product name if not already present
                    if "productType" not in product or not product["productType"]:
                        product_name_lower = db_product.name.lower()
                        # Order matters - check specific types first
                        if "sofa" in product_name_lower or "couch" in product_name_lower or "sectional" in product_name_lower:
                            product["productType"] = "sofa"
                        elif (
                            "coffee table" in product_name_lower
                            or "center table" in product_name_lower
                            or "centre table" in product_name_lower
                        ):
                            product["productType"] = "coffee_table"
                        elif (
                            "side table" in product_name_lower
                            or "end table" in product_name_lower
                            or "nightstand" in product_name_lower
                        ):
                            product["productType"] = "side_table"
                        elif "dining table" in product_name_lower:
                            product["productType"] = "dining_table"
                        elif "console table" in product_name_lower:
                            product["productType"] = "console_table"
                        elif "accent chair" in product_name_lower or "armchair" in product_name_lower:
                            product["productType"] = "accent_chair"
                        elif "dining chair" in product_name_lower:
                            product["productType"] = "dining_chair"
                        elif "office chair" in product_name_lower:
                            product["productType"] = "office_chair"
                        elif "table lamp" in product_name_lower or "desk lamp" in product_name_lower:
                            product["productType"] = "table_lamp"
                        elif "floor lamp" in product_name_lower:
                            product["productType"] = "floor_lamp"
                        elif (
                            "ceiling lamp" in product_name_lower
                            or "pendant" in product_name_lower
                            or "chandelier" in product_name_lower
                        ):
                            product["productType"] = "ceiling_lamp"
                        elif "table" in product_name_lower:
                            product["productType"] = "table"
                        elif "chair" in product_name_lower:
                            product["productType"] = "chair"
                        elif "lamp" in product_name_lower:
                            product["productType"] = "lamp"
                        elif "bed" in product_name_lower:
                            product["productType"] = "bed"
                        elif "dresser" in product_name_lower:
                            product["productType"] = "dresser"
                        elif "mirror" in product_name_lower:
                            product["productType"] = "mirror"
                        elif "rug" in product_name_lower or "carpet" in product_name_lower:
                            if (
                                "wall" in product_name_lower
                                or "hanging" in product_name_lower
                                or "tapestry" in product_name_lower
                            ):
                                product["productType"] = "wall_rug"
                            else:
                                product["productType"] = "floor_rug"
                        elif "ottoman" in product_name_lower:
                            product["productType"] = "ottoman"
                        elif "bench" in product_name_lower:
                            product["productType"] = "bench"
                        else:
                            product["productType"] = "other"

        # Get user's style description from analysis
        user_style_description = visualization_instruction  # Use the clarification-based instruction
        lighting_conditions = "mixed"

        if analysis:
            design_analysis = analysis.get("design_analysis", {})
            if design_analysis:
                # Style preferences
                style_prefs = design_analysis.get("style_preferences", {})
                if isinstance(style_prefs, dict):
                    primary_style = style_prefs.get("primary_style", "")
                    style_keywords = style_prefs.get("style_keywords", [])
                    if primary_style:
                        user_style_description += f" {primary_style} style. "
                    if style_keywords:
                        user_style_description += f"Style keywords: {', '.join(style_keywords)}. "

                # Space analysis
                space_analysis = design_analysis.get("space_analysis", {})
                if isinstance(space_analysis, dict):
                    lighting_conditions = space_analysis.get("lighting_conditions", "mixed")

            # Add professional layout guidance from AI designer (new field)
            layout_guidance = analysis.get("layout_guidance")
            if layout_guidance:
                user_style_description += f"\n\nLayout Guidance: {layout_guidance}"
                logger.info(f"Using professional layout guidance: {layout_guidance[:100]}...")

        logger.info(f"Generating visualization with instruction: {user_style_description}")

        # Handle incremental visualization (add new products to existing visualization)
        if is_incremental:
            logger.info(f"Incremental visualization: Adding {len(products)} new products to existing visualization")

            # Use sequential add visualization for each product
            current_image = base_image  # Start with previous visualization

            for product in products:
                product_name = product.get("full_name") or product.get("name")
                product_image_url = product.get("image_url")

                logger.info(f"  Adding product: {product_name}")

                # Call add visualization for this product
                add_result = await google_ai_service.generate_add_visualization(
                    room_image=current_image, product_name=product_name, product_image=product_image_url
                )

                # Use the result as base for next product
                # add_result is already a base64 string, not an object
                if add_result:
                    current_image = add_result
                else:
                    logger.warning(f"Failed to add product {product_name}, skipping")

            # Final result
            viz_result = VisualizationResult(
                rendered_image=current_image,
                processing_time=0.0,  # Not tracked for incremental adds
                quality_score=0.85,
                placement_accuracy=0.90,
                lighting_realism=0.85,
                confidence_score=0.87,
            )
        else:
            # Standard visualization (all products at once)
            # Create visualization request
            viz_request = VisualizationRequest(
                base_image=base_image,
                products_to_place=products,
                placement_positions=custom_positions if custom_positions else [],
                lighting_conditions=lighting_conditions,
                render_quality="high",
                style_consistency=True,
                user_style_description=user_style_description,
            )

            # Log if using custom positions
            if custom_positions:
                logger.info(f"Using {len(custom_positions)} custom furniture positions from edit mode")

            # Generate visualization using Google AI Studio
            viz_result = await google_ai_service.generate_room_visualization(viz_request)

        # Note: Due to AI model limitations, the visualization shows a design concept
        # The room structure may vary from the original as generative models create new images
        # rather than editing existing ones. For pixel-perfect preservation, an inpainting model
        # would be required. See VISUALIZATION_ANALYSIS.md for technical details.

        # Push visualization to history for undo/redo support
        # Note: We only store states with furniture, not the empty original room
        # This allows undo to work through furniture additions without going back to empty
        visualization_data = {
            "rendered_image": viz_result.rendered_image,
            "products": products,
            "user_action": user_action,
            "existing_furniture": existing_furniture,
        }
        conversation_context_manager.push_visualization_state(session_id, visualization_data)

        # Verify that we have a valid visualization result
        # Check for None, empty string, or very short base64 strings (likely malformed)
        if (
            not viz_result
            or not viz_result.rendered_image
            or len(viz_result.rendered_image.strip()) < 100  # Valid base64 images are much longer
            or viz_result.rendered_image == base_image  # AI returned unchanged image (failure)
        ):
            logger.error(
                f"Visualization failed: rendered_image is empty, malformed, or unchanged "
                f"(length: {len(viz_result.rendered_image) if viz_result and viz_result.rendered_image else 0})"
            )
            raise HTTPException(
                status_code=500,
                detail="Visualization generation failed. The AI service did not return a valid image. Please try again or try with fewer products.",
            )

        # Prepare response message based on visualization mode
        if forced_incremental:
            message = f"Visualization generated successfully with {len(products)} products. Products were added sequentially for optimal results."
        else:
            message = "Visualization generated successfully. Note: This shows a design concept with your selected products."

        return {
            "visualization": {
                "rendered_image": viz_result.rendered_image,
                "processing_time": viz_result.processing_time if hasattr(viz_result, "processing_time") else 0.0,
                "quality_metrics": {
                    "overall_quality": viz_result.quality_score if hasattr(viz_result, "quality_score") else 0.85,
                    "placement_accuracy": viz_result.placement_accuracy if hasattr(viz_result, "placement_accuracy") else 0.90,
                    "lighting_realism": viz_result.lighting_realism if hasattr(viz_result, "lighting_realism") else 0.85,
                    "confidence_score": viz_result.confidence_score if hasattr(viz_result, "confidence_score") else 0.87,
                },
            },
            "message": message,
            "technical_note": "Generative AI models create new images rather than edit existing ones. Some variation in room structure is expected.",
            "can_undo": conversation_context_manager.can_undo(session_id),
            "can_redo": conversation_context_manager.can_redo(session_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating visualization: {e}", exc_info=True)
        # Provide user-friendly error message
        error_msg = str(e)
        if "500" in error_msg and "INTERNAL" in error_msg:
            detail = "The visualization service is temporarily unavailable. This may be due to processing too many products at once. Please try with fewer products or try again later."
        elif "timeout" in error_msg.lower():
            detail = "Visualization request timed out. Please try again with fewer products."
        else:
            detail = f"Error generating visualization: {error_msg}"
        raise HTTPException(status_code=500, detail=detail)


@router.post("/sessions/{session_id}/visualization/undo")
async def undo_visualization(session_id: str):
    """Undo last visualization and return previous state"""
    try:
        # Get previous visualization state from context manager
        previous_state = conversation_context_manager.undo_visualization(session_id)

        if previous_state is None:
            raise HTTPException(status_code=400, detail="Cannot undo: No previous visualization available")

        logger.info(f"Undid visualization for session {session_id}")

        # Add products_in_scene field for frontend compatibility
        # Frontend expects 'products_in_scene', backend stores 'products'
        visualization_response = {**previous_state, "products_in_scene": previous_state.get("products", [])}

        return {
            "visualization": visualization_response,
            "message": "Successfully undid last visualization",
            "can_undo": conversation_context_manager.can_undo(session_id),
            "can_redo": conversation_context_manager.can_redo(session_id),
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
            raise HTTPException(status_code=400, detail="Cannot redo: No next visualization available")

        logger.info(f"Redid visualization for session {session_id}")

        # Add products_in_scene field for frontend compatibility
        # Frontend expects 'products_in_scene', backend stores 'products'
        visualization_response = {**next_state, "products_in_scene": next_state.get("products", [])}

        return {
            "visualization": visualization_response,
            "message": "Successfully redid visualization",
            "can_undo": conversation_context_manager.can_undo(session_id),
            "can_redo": conversation_context_manager.can_redo(session_id),
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

    # Check ottoman FIRST (before sofa) to handle "Sofa Ottoman" products correctly
    if "ottoman" in name_lower:
        return "ottoman"
    elif "sofa" in name_lower or "couch" in name_lower or "sectional" in name_lower:
        return "sofa"
    elif "chair" in name_lower or "armchair" in name_lower:
        return "chair"
    elif "table" in name_lower:
        # Prioritize specific table types - order matters!
        if "coffee" in name_lower or "center" in name_lower or "centre" in name_lower:
            return "center table"  # For placement in front of sofa
        elif "side" in name_lower or "end" in name_lower or "nightstand" in name_lower or "bedside" in name_lower:
            return "side table"  # For placement beside furniture
        elif "dining" in name_lower:
            return "dining table"
        elif "console" in name_lower:
            return "console table"
        return "table"  # Generic fallback
    elif "rug" in name_lower or "carpet" in name_lower:
        # Distinguish between wall rugs and floor rugs
        if "wall" in name_lower or "hanging" in name_lower or "tapestry" in name_lower:
            return "wall rug"  # For wall mounting
        else:
            return "floor rug"  # For floor placement
    elif "bed" in name_lower:
        return "bed"
    elif "lamp" in name_lower:
        return "lamp"
    elif "desk" in name_lower:
        return "desk"
    elif "cabinet" in name_lower or "dresser" in name_lower:
        return "cabinet"
    elif "shelf" in name_lower or "bookcase" in name_lower:
        return "shelf"
    else:
        # Default: extract first word
        return name_lower.split()[0] if name_lower.split() else "furniture"


def _extract_product_keywords(user_message: str, style_context: Optional[str] = None) -> List[str]:
    """
    Extract product type keywords from user message with category awareness and style-based synonyms

    Args:
        user_message: User's search query
        style_context: Optional design style (e.g., 'modern', 'traditional', 'rustic')

    Returns:
        List of keywords including base term and style-appropriate synonyms
    """

    # BASE SYNONYM PATTERNS - Universal across all styles
    # Product keywords with synonyms and related terms - ORDER MATTERS (longer phrases first)
    # Format: (search_term, [base_keywords], {style: [additional_keywords]})
    product_patterns = [
        # Lighting - ceiling/overhead (check both singular and plural)
        ("ceiling lights", ["ceiling lamp", "ceiling light", "pendant", "chandelier"], {}),
        ("ceiling lamps", ["ceiling lamp", "ceiling light", "pendant", "chandelier"], {}),
        ("ceiling lamp", ["ceiling lamp", "ceiling light", "pendant", "chandelier"], {}),
        ("ceiling light", ["ceiling lamp", "ceiling light", "pendant", "chandelier"], {}),
        ("pendant lights", ["pendant", "ceiling lamp", "ceiling light", "chandelier"], {}),
        ("pendant lamps", ["pendant", "ceiling lamp", "ceiling light", "chandelier"], {}),
        ("pendant light", ["pendant", "ceiling lamp", "ceiling light", "chandelier"], {}),
        ("pendant lamp", ["pendant", "ceiling lamp", "ceiling light", "chandelier"], {}),
        ("chandeliers", ["chandelier", "ceiling lamp", "ceiling light", "pendant"], {}),
        ("chandelier", ["chandelier", "ceiling lamp", "ceiling light", "pendant"], {}),
        ("overhead lights", ["ceiling lamp", "ceiling light", "pendant", "chandelier"], {}),
        ("overhead light", ["ceiling lamp", "ceiling light", "pendant", "chandelier"], {}),
        # Lighting - table/desk (check both singular and plural)
        ("table lamps", ["table lamp", "desk lamp", "reading lamp"], {}),
        ("table lamp", ["table lamp", "desk lamp", "reading lamp"], {}),
        ("desk lamps", ["desk lamp", "table lamp", "task lamp"], {}),
        ("desk lamp", ["desk lamp", "table lamp", "task lamp"], {}),
        # Lighting - floor (check both singular and plural)
        ("floor lamps", ["floor lamp", "standing lamp", "torchiere"], {}),
        ("floor lamp", ["floor lamp", "standing lamp", "torchiere"], {}),
        # Lighting - wall (check both singular and plural)
        ("wall lamps", ["wall lamp", "sconce", "wall light", "wall fixture"], {}),
        ("wall lamp", ["wall lamp", "sconce", "wall light", "wall fixture"], {}),
        ("sconces", ["sconce", "wall lamp", "wall light"], {}),
        ("sconce", ["sconce", "wall lamp", "wall light"], {}),
        # Multi-word furniture - tables
        ("center table", ["coffee table", "center table", "centre table", "cocktail table"], {}),
        ("centre table", ["coffee table", "center table", "centre table", "cocktail table"], {}),
        ("coffee table", ["coffee table", "center table", "centre table", "cocktail table"], {}),
        ("cocktail table", ["cocktail table", "coffee table", "center table"], {}),
        ("dining table", ["dining table", "dinner table", "kitchen table"], {}),
        ("side table", ["side table", "end table", "nightstand", "bedside table", "night table"], {}),
        ("end table", ["end table", "side table", "accent table"], {}),
        ("nightstand", ["nightstand", "side table", "bedside table", "night table", "bedside cabinet"], {}),
        ("bedside table", ["bedside table", "nightstand", "night table", "side table"], {}),
        ("console table", ["console table", "entry table", "sofa table", "hall table"], {}),
        # Multi-word furniture - chairs
        ("accent chair", ["accent chair", "armchair", "side chair", "occasional chair"], {}),
        ("dining chair", ["dining chair", "kitchen chair", "side chair"], {}),
        ("office chair", ["office chair", "desk chair", "task chair", "computer chair"], {}),
        ("lounge chair", ["lounge chair", "armchair", "reading chair", "club chair"], {}),
        # Multi-word furniture - sofas (WITH STYLE VARIANTS)
        ("sectional sofa", ["sectional", "sectional sofa"], {}),
        ("leather sofa", ["sofa", "couch", "leather sofa"], {}),
        # Single word furniture - SOFAS WITH STYLE-AWARE SYNONYMS
        (
            "sofa",
            ["sofa", "couch", "sectional", "loveseat"],
            {
                "traditional": ["settee", "davenport", "chesterfield", "divan"],
                "modern": ["sectional", "modular sofa"],
                "french": ["chaise", "settee", "canapé"],
                "victorian": ["settee", "davenport", "chesterfield"],
                "british": ["settee", "chesterfield"],
            },
        ),
        ("couch", ["couch", "sofa", "sectional"], {}),
        ("sectional", ["sectional", "sofa", "couch", "modular sofa"], {}),
        ("loveseat", ["loveseat", "sofa", "two-seater"], {}),
        # Chairs with style variants
        ("chair", ["chair", "seat"], {}),
        (
            "armchair",
            ["armchair", "accent chair", "club chair"],
            {"traditional": ["wingback", "bergère"], "modern": ["accent chair", "lounge chair"]},
        ),
        ("recliner", ["recliner", "reclining chair", "lounger"], {}),
        # Tables with regional variants
        ("table", ["table"], {}),
        # Bedroom furniture with style variants
        (
            "bed",
            ["bed", "bedframe", "bed frame"],
            {"traditional": ["four-poster", "sleigh bed", "canopy bed"], "modern": ["platform bed", "low profile bed"]},
        ),
        ("mattress", ["mattress", "bed mattress"], {}),
        ("headboard", ["headboard", "bed head"], {}),
        # Workspace furniture
        (
            "desk",
            ["desk", "writing desk", "work table"],
            {"traditional": ["secretary desk", "writing bureau"], "modern": ["computer desk", "standing desk"]},
        ),
        ("workstation", ["desk", "workstation", "work desk"], {}),
        # Storage furniture with comprehensive synonyms
        (
            "dresser",
            ["dresser", "chest of drawers", "bureau", "chest"],
            {"traditional": ["bureau", "highboy", "lowboy"], "french": ["commode", "armoire"]},
        ),
        ("chest", ["chest", "chest of drawers", "dresser", "trunk"], {}),
        ("cabinet", ["cabinet", "cupboard", "storage cabinet"], {}),
        ("bookshelf", ["bookshelf", "shelving", "bookcase", "shelf unit"], {}),
        ("shelving", ["shelving", "bookshelf", "shelf", "shelving unit"], {}),
        ("shelf", ["shelf", "shelving", "bookshelf", "wall shelf"], {}),
        ("wardrobe", ["wardrobe", "closet", "armoire", "clothes closet"], {}),
        # Lighting - generic (only after specific types checked)
        ("lamps", ["lamp", "light", "lighting"], {}),
        ("lamp", ["lamp", "light"], {}),
        ("lighting", ["lighting", "lamp", "light", "fixture"], {}),
        # Textiles and soft furnishings
        ("wall rug", ["wall rug", "wall hanging", "tapestry", "wall tapestry", "hanging rug"], {}),
        ("tapestry", ["tapestry", "wall hanging", "wall rug", "wall tapestry"], {}),
        ("floor rug", ["rug", "carpet", "area rug", "floor rug", "floor covering"], {}),
        ("rug", ["rug", "carpet", "area rug", "floor covering"], {}),
        ("carpet", ["carpet", "rug", "floor covering"], {}),
        # Decor and accessories
        ("mirror", ["mirror", "looking glass", "wall mirror"], {}),
        ("planter", ["planter", "pot", "plant pot", "flower pot"], {}),
        ("planters", ["planter", "pot", "plant pot", "flower pot"], {}),
        ("plants", ["planter", "pot", "plant pot", "flower pot"], {}),  # "plants" maps to planters
        ("plant", ["planter", "pot", "plant pot", "flower pot"], {}),  # "plant" maps to planters
        ("vase", ["vase", "flower vase"], {}),
        ("bench", ["bench", "seat", "seating bench"], {}),
        ("stool", ["stool", "bar stool"], {}),
        # Ottoman - separate category (NOT a sofa, used as footrest/extra seating)
        ("ottoman", ["ottoman", "footstool", "pouf", "hassock"], {}),
    ]

    message_lower = user_message.lower()
    found_keywords = []
    matched_phrases = set()  # Track which phrases we've already matched

    # Normalize style context for matching
    style_lower = style_context.lower() if style_context else None

    # Check patterns in order (longer phrases first due to order above)
    for pattern in product_patterns:
        # Unpack pattern - now includes style variants
        if len(pattern) == 3:
            search_term, base_keywords, style_variants = pattern
        else:
            search_term, base_keywords = pattern
            style_variants = {}

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

                # Add base keywords
                for keyword in base_keywords:
                    if keyword not in found_keywords:
                        found_keywords.append(keyword)

                # Add style-specific synonyms if style context matches
                if style_lower and style_variants:
                    # Check for exact style match
                    if style_lower in style_variants:
                        for keyword in style_variants[style_lower]:
                            if keyword not in found_keywords:
                                found_keywords.append(keyword)
                                logger.info(f"Added style-aware synonym '{keyword}' for {style_lower} style")
                    # Check for style keywords within the style context
                    else:
                        for style_key, style_keywords in style_variants.items():
                            if style_key in style_lower:
                                for keyword in style_keywords:
                                    if keyword not in found_keywords:
                                        found_keywords.append(keyword)
                                        logger.info(f"Added style-aware synonym '{keyword}' for {style_key} style")

    if style_context:
        logger.info(f"Extracted keywords from '{user_message}' with style '{style_context}': {found_keywords}")
    else:
        logger.info(f"Extracted keywords from '{user_message}': {found_keywords}")

    return found_keywords


def _extract_color_modifiers(user_message: str) -> List[str]:
    """
    Extract color modifiers from user message for attribute filtering

    Args:
        user_message: User's search query

    Returns:
        List of color names found in the message
    """
    # Color patterns (longer phrases first)
    color_patterns = [
        "off-white",
        "multi-color",
        "multicolor",  # Multi-word colors first
        "beige",
        "cream",
        "ivory",
        "white",
        "black",
        "gray",
        "grey",
        "brown",
        "tan",
        "taupe",
        "khaki",
        "navy",
        "blue",
        "red",
        "green",
        "yellow",
        "orange",
        "purple",
        "pink",
        "burgundy",
        "maroon",
        "olive",
        "charcoal",
        "slate",
        "espresso",
        "chocolate",
        "caramel",
        "sand",
        "natural",
        "neutral",
        "gold",
        "silver",
    ]

    message_lower = user_message.lower()
    found_colors = []

    # Check for each color pattern
    for color in color_patterns:
        if color in message_lower:
            # Avoid duplicates and overlapping colors
            is_subset = False
            for existing in found_colors:
                if color in existing or existing in color:
                    # Keep the longer, more specific term
                    if len(color) > len(existing):
                        found_colors.remove(existing)
                        found_colors.append(color)
                    is_subset = True
                    break

            if not is_subset:
                found_colors.append(color)

    return found_colors


def _extract_material_modifiers(user_message: str) -> List[str]:
    """
    Extract material modifiers from user message for attribute filtering

    Args:
        user_message: User's search query

    Returns:
        List of material names found in the message
    """
    # Common furniture materials (longer phrases first)
    material_patterns = [
        # Fabrics and upholstery
        "faux leather",
        "genuine leather",
        "synthetic fabric",  # Multi-word first
        "velvet",
        "leather",
        "suede",
        "linen",
        "cotton",
        "silk",
        "wool",
        "microfiber",
        "chenille",
        "canvas",
        "denim",
        "upholstered",
        "fabric",
        # Woven materials
        "wicker",
        "rattan",
        "cane",
        "seagrass",
        "jute",
        "bamboo",
        "rush",
        # Woods (specific types)
        "mango wood",
        "reclaimed wood",
        "solid wood",
        "engineered wood",  # Multi-word first
        "teak",
        "oak",
        "walnut",
        "maple",
        "cherry",
        "mahogany",
        "pine",
        "birch",
        "ash",
        "cedar",
        "rosewood",
        "acacia",
        "wood",
        "wooden",
        "timber",
        # Metals
        "stainless steel",
        "wrought iron",  # Multi-word first
        "steel",
        "iron",
        "brass",
        "bronze",
        "copper",
        "aluminum",
        "chrome",
        "metal",
        "metallic",
        # Glass and stone
        "tempered glass",  # Multi-word first
        "glass",
        "marble",
        "granite",
        "stone",
        "concrete",
        "ceramic",
        "porcelain",
        "terracotta",
        # Synthetics and composites
        "particle board",  # Multi-word first
        "plastic",
        "acrylic",
        "resin",
        "fiberglass",
        "composite",
        "plywood",
        "mdf",
        # Natural fibers
        "rope",
        "twine",
        "hemp",
    ]

    message_lower = user_message.lower()
    found_materials = []

    # Check for each material pattern (longer phrases first)
    for material in material_patterns:
        if material in message_lower:
            # Avoid duplicates and overlapping materials
            # e.g., if "faux leather" is found, don't also add "leather"
            is_subset = False
            for existing in found_materials:
                if material in existing or existing in material:
                    # Keep the longer, more specific term
                    if len(material) > len(existing):
                        found_materials.remove(existing)
                        found_materials.append(material)
                    is_subset = True
                    break

            if not is_subset:
                found_materials.append(material)

    if found_materials:
        logger.info(f"Extracted materials from '{user_message}': {found_materials}")

    return found_materials


async def _get_product_recommendations(
    analysis: DesignAnalysisSchema,
    db: AsyncSession,
    user_message: str = "",
    limit: int = 30,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    selected_stores: Optional[List[str]] = None,
) -> List[dict]:
    """Get advanced product recommendations based on design analysis"""
    logger.info(
        f"[RECOMMENDATION ENTRY] _get_product_recommendations called with user_message='{user_message}', limit={limit}"
    )
    try:
        # Extract preferences from analysis first to get style context
        user_preferences = {}
        style_preferences = []
        functional_requirements = []
        budget_range = None
        room_context = None
        primary_style = None  # For context-aware keyword extraction

        # Extract design analysis data
        if hasattr(analysis, "design_analysis") and analysis.design_analysis:
            design_analysis = analysis.design_analysis
            if isinstance(design_analysis, dict):
                # Style preferences - extract primary style for context-aware synonyms
                style_prefs = design_analysis.get("style_preferences", {})
                if isinstance(style_prefs, dict):
                    primary_style = style_prefs.get("primary_style", "")  # Save for keyword extraction
                    secondary_styles = style_prefs.get("secondary_styles", [])
                    if primary_style:
                        style_preferences.append(primary_style)
                    style_preferences.extend(secondary_styles)

                # Color preferences
                color_scheme = design_analysis.get("color_scheme", {})
                if isinstance(color_scheme, dict):
                    user_preferences["colors"] = color_scheme.get("preferred_colors", []) + color_scheme.get(
                        "accent_colors", []
                    )

                # Functional requirements
                func_reqs = design_analysis.get("functional_requirements", {})
                if isinstance(func_reqs, dict):
                    functional_requirements = func_reqs.get("primary_functions", [])

                # Budget indicators - ONLY set if explicitly provided
                budget_indicators = design_analysis.get("budget_indicators", {})
                if isinstance(budget_indicators, dict):
                    price_range = budget_indicators.get("price_range")
                    if price_range:  # Only map if actually specified
                        budget_range = _map_budget_range(price_range)
                        logger.info(f"Budget range from analysis: {price_range} -> ₹{budget_range[0]}-₹{budget_range[1]}")

                # Room context
                space_analysis = design_analysis.get("space_analysis", {})
                if isinstance(space_analysis, dict):
                    room_context = {
                        "room_type": space_analysis.get("room_type", "living_room"),
                        "dimensions": space_analysis.get("dimensions", ""),
                        "layout_type": space_analysis.get("layout_type", "open"),
                    }

        # NOW extract product keywords WITH style context for intelligent synonym expansion
        logger.info(
            f"[EXTRACT DEBUG] About to call _extract_product_keywords with message: '{user_message}', style: '{primary_style}'"
        )
        product_keywords = _extract_product_keywords(user_message, style_context=primary_style)
        logger.info(f"[EXTRACT DEBUG] _extract_product_keywords returned: {product_keywords}")

        # Extract color modifiers directly from user message (e.g., "beige", "gray", "blue")
        user_colors_from_message = _extract_color_modifiers(user_message)
        logger.info(f"COLOR EXTRACTION: From message '{user_message}' extracted colors: {user_colors_from_message}")

        # Extract material modifiers directly from user message (e.g., "wicker", "leather", "velvet")
        user_materials_from_message = _extract_material_modifiers(user_message)
        logger.info(f"MATERIAL EXTRACTION: From message '{user_message}' extracted materials: {user_materials_from_message}")

        # Extract material and product type preferences from product matching criteria
        if hasattr(analysis, "product_matching_criteria") and analysis.product_matching_criteria:
            criteria = analysis.product_matching_criteria
            if isinstance(criteria, dict):
                filtering = criteria.get("filtering_keywords", {})
                if isinstance(filtering, dict):
                    user_preferences["materials"] = filtering.get("material_preferences", [])

                # PRIMARY: Extract product type keywords (e.g., "table", "sofa", "chair") - TOP PRIORITY
                product_types = criteria.get("product_types", [])
                if product_types:
                    user_preferences["product_keywords"] = product_types
                    logger.info(f"Extracted product_types from analysis: {product_types}")

                # SECONDARY: Also check for category names
                categories = criteria.get("categories", [])
                if categories:
                    if "product_keywords" in user_preferences:
                        user_preferences["product_keywords"].extend(categories)
                    else:
                        user_preferences["product_keywords"] = categories
                    logger.info(f"Extracted categories from analysis: {categories}")

                # TERTIARY: Check for search terms
                search_terms = criteria.get("search_terms", [])
                if search_terms:
                    # Add search terms to product keywords as well for maximum matching
                    if "product_keywords" in user_preferences:
                        user_preferences["product_keywords"].extend(search_terms)
                    else:
                        user_preferences["product_keywords"] = search_terms

                    # Also add to description keywords
                    if "description_keywords" not in user_preferences:
                        user_preferences["description_keywords"] = []
                    user_preferences["description_keywords"].extend(search_terms)
                    logger.info(f"Extracted search_terms from analysis: {search_terms}")

        # FALLBACK: If no product keywords extracted from analysis, try to extract from original message
        if "product_keywords" not in user_preferences or not user_preferences["product_keywords"]:
            # FIRST: Try using the result from _extract_product_keywords if available
            if product_keywords:
                user_preferences["product_keywords"] = product_keywords
                logger.info(f"Using extracted product keywords: {product_keywords}")
            else:
                # Extract furniture keywords from the conversation context if available
                import re

                furniture_pattern = r"\b(sofa|table|chair|bed|desk|cabinet|shelf|dresser|nightstand|ottoman|bench|couch|sectional|sideboard|console|bookcase|armchair|stool|vanity|wardrobe|chest|mirror|lamp|chandelier|planter|vase|pot)\b"

                # Get last user message from session_id context
                if session_id:
                    context = chatgpt_service.get_conversation_context(session_id)
                    if context:
                        last_message = context[-1] if context else ""
                        if isinstance(last_message, dict):
                            last_message = last_message.get("content", "")

                        matches = re.findall(furniture_pattern, last_message.lower())
                        if matches:
                            user_preferences["product_keywords"] = list(set(matches))
                            logger.info(f"Extracted product keywords from message: {matches}")

        # NEW: Extract professional designer fields from analysis
        color_palette = None
        styling_tips = None
        ai_product_types = None  # NEW: AI stylist validated product types

        if hasattr(analysis, "color_palette") and analysis.color_palette:
            color_palette = analysis.color_palette
            logger.info(f"Using AI designer color palette: {color_palette}")

        if hasattr(analysis, "styling_tips") and analysis.styling_tips:
            styling_tips = analysis.styling_tips
            logger.info(f"Using AI designer styling tips: {styling_tips}")

        # NEW: Extract AI-validated product types for hard filtering
        ai_textures = None
        ai_patterns = None
        if hasattr(analysis, "product_matching_criteria") and analysis.product_matching_criteria:
            criteria = analysis.product_matching_criteria
            if isinstance(criteria, dict):
                product_types = criteria.get("product_types", [])
                if product_types:
                    ai_product_types = product_types
                    logger.info(f"Using AI stylist product types for filtering: {ai_product_types}")

                # Extract textures and patterns from filtering keywords
                filtering = criteria.get("filtering_keywords", {})
                if isinstance(filtering, dict):
                    ai_textures = filtering.get("texture_preferences", [])
                    ai_patterns = filtering.get("pattern_preferences", [])
                    if ai_textures:
                        logger.info(f"Extracted AI texture preferences: {ai_textures}")
                    if ai_patterns:
                        logger.info(f"Extracted AI pattern preferences: {ai_patterns}")

        # Merge materials from user message with materials from AI analysis
        final_materials = list(user_materials_from_message)  # Start with materials from message
        if "materials" in user_preferences and user_preferences["materials"]:
            # Add materials from AI analysis that aren't already included
            for material in user_preferences["materials"]:
                if material.lower() not in [m.lower() for m in final_materials]:
                    final_materials.append(material)

        # NEW: Add textures if provided by AI
        final_textures = []
        if ai_textures:
            final_textures = list(ai_textures)

        # NEW: Add patterns if provided by AI
        final_patterns = []
        if ai_patterns:
            final_patterns = list(ai_patterns)

        # NEW: Merge colors from AI analysis with user message colors
        final_colors = list(user_colors_from_message)  # Start with user message colors
        # Add colors from AI design analysis
        if "colors" in user_preferences and user_preferences["colors"]:
            for color in user_preferences["colors"]:
                if color.lower() not in [c.lower() for c in final_colors]:
                    final_colors.append(color)
        # Add colors from AI color_palette
        if color_palette:
            for color in color_palette:
                # Convert hex to color name or use directly
                if isinstance(color, str) and color not in final_colors:
                    final_colors.append(color)

        # NEW: Combine AI-recommended styles with extracted styles
        final_styles = list(style_preferences) if style_preferences else []
        logger.info(f"Using AI style preferences: {final_styles}")

        # Enable strict attribute matching if user specified specific materials OR colors
        strict_match = bool(user_materials_from_message) or bool(user_colors_from_message)

        # Log all final filtering criteria
        if final_materials:
            logger.info(f"Final materials for filtering: {final_materials} (strict_match={strict_match})")
        if final_colors:
            logger.info(f"Final colors for filtering: {final_colors} (strict_match={strict_match})")
        if final_textures:
            logger.info(f"Final textures for filtering: {final_textures}")
        if final_patterns:
            logger.info(f"Final patterns for filtering: {final_patterns}")

        # DEBUG: Log what keywords are being used
        logger.info(f"[PLANTER DEBUG] product_keywords variable: {product_keywords}")
        logger.info(f"[PLANTER DEBUG] user_preferences['product_keywords']: {user_preferences.get('product_keywords', [])}")
        logger.info(f"[RECOMMENDATION DEBUG] About to create RecommendationRequest with product_keywords={product_keywords}")

        # Create recommendation request
        # IMPORTANT: Use keywords from user_preferences, not the local product_keywords variable
        # because the fallback logic stores the final keywords in user_preferences['product_keywords']
        final_product_keywords = user_preferences.get("product_keywords", product_keywords) or []

        recommendation_request = RecommendationRequest(
            user_preferences=user_preferences,
            room_context=room_context,
            budget_range=budget_range,
            style_preferences=final_styles,  # Use AI-combined styles
            functional_requirements=functional_requirements,
            product_keywords=final_product_keywords,
            max_recommendations=limit,
            # NEW: Professional AI designer fields
            color_palette=color_palette,
            styling_tips=styling_tips,
            ai_product_types=ai_product_types,  # NEW: AI stylist validated product types for hard filtering
            # NEW: Attribute filtering from AI stylist
            user_colors=final_colors if final_colors else None,
            user_materials=final_materials if final_materials else None,
            user_textures=final_textures if final_textures else None,  # NEW: AI texture preferences
            # Store filtering
            selected_stores=selected_stores,
            user_patterns=final_patterns if final_patterns else None,  # NEW: AI pattern preferences
            user_styles=final_styles if final_styles else None,  # NEW: AI style preferences
            strict_attribute_match=strict_match,
        )

        logger.info(
            f"[RECOMMENDATION DEBUG] RecommendationRequest created with product_keywords={recommendation_request.product_keywords}"
        )
        logger.info(f"[RECOMMENDATION DEBUG] final_product_keywords={final_product_keywords}")

        # Get advanced recommendations
        recommendation_response = await recommendation_engine.get_recommendations(recommendation_request, db, user_id)

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
                            "alt_text": primary_image.alt_text if primary_image else product.name,
                        }
                        if primary_image
                        else None,
                        # Add recommendation metadata
                        "recommendation_data": {
                            "confidence_score": rec.confidence_score,
                            "reasoning": rec.reasoning,
                            "style_match": rec.style_match_score,
                            "functional_match": rec.functional_match_score,
                            "price_score": rec.price_score,
                            "overall_score": rec.overall_score,
                        },
                    }
                    product_recommendations.append(product_dict)

        # IMPORTANT: Only use fallback if NO specific product keywords were requested
        # If user asked for "vases" but we have no vases, show empty list instead of random products
        has_specific_keywords = "product_keywords" in user_preferences and user_preferences["product_keywords"]
        has_specific_materials = final_materials and bool(user_materials_from_message)

        if len(product_recommendations) < limit // 2 and not has_specific_keywords and not has_specific_materials:
            logger.info("Using fallback recommendation method (no specific keywords or materials)")
            fallback_recommendations = await _get_basic_product_recommendations(
                analysis, db, limit - len(product_recommendations)
            )
            product_recommendations.extend(fallback_recommendations)
        elif len(product_recommendations) == 0:
            # Log specific reason for zero results
            if has_specific_materials and has_specific_keywords:
                logger.warning(f"No products found matching keywords {product_keywords} " f"with materials {final_materials}")
            elif has_specific_materials:
                logger.warning(f"No products found with materials: {final_materials}")
            elif has_specific_keywords:
                logger.warning(f"No products found matching keywords: {product_keywords}")
            # Return empty list - frontend should display "No products found"

        return product_recommendations[:limit]

    except Exception as e:
        logger.error(f"Error getting advanced product recommendations: {e}")
        # Fallback to basic recommendations
        return await _get_basic_product_recommendations(analysis, db, limit)


def _map_budget_range(price_range: str) -> Tuple[float, float]:
    """Map budget indicators to price ranges (in INR for furniture)"""
    budget_map = {
        "budget": (0, 15000),  # Budget furniture: up to ₹15K
        "mid-range": (10000, 50000),  # Mid-range furniture: ₹10K-50K
        "premium": (40000, 150000),  # Premium furniture: ₹40K-150K
        "luxury": (100000, 1000000),  # Luxury furniture: ₹100K+
    }
    return budget_map.get(price_range, (0, 200000))  # Default: no upper limit for most searches


async def _get_basic_product_recommendations(analysis: DesignAnalysisSchema, db: AsyncSession, limit: int = 30) -> List[dict]:
    """Basic product recommendations as fallback"""
    try:
        # Simple keyword-based search (eagerly load images)
        from sqlalchemy import func
        from sqlalchemy.orm import selectinload

        # Use random ordering and exclude small accessories for variety
        query = (
            select(Product)
            .options(selectinload(Product.images))
            .where(
                Product.is_available == True,
                ~Product.name.ilike("%pillow%"),
                ~Product.name.ilike("%cushion%"),
                ~Product.name.ilike("%throw%"),
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
                    "alt_text": primary_image.alt_text if primary_image else product.name,
                }
                if primary_image
                else None,
                "recommendation_data": {
                    "confidence_score": 0.5,
                    "reasoning": ["Basic search result"],
                    "style_match": 0.5,
                    "functional_match": 0.5,
                    "price_score": 0.5,
                    "overall_score": 0.5,
                },
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
        return {"session_id": session_id, "context": context, "context_length": len(context)}
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
        return {"status": "unhealthy", "error": str(e)}


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
    session_id: str, request: dict, db: AsyncSession = Depends(get_db)  # Contains preference_text
):
    """Analyze user preference text for design insights"""
    try:
        preference_text = request.get("preference_text", "")
        if not preference_text:
            raise HTTPException(status_code=400, detail="preference_text is required")

        # Use ChatGPT to analyze preferences
        conversational_response, analysis = await chatgpt_service.analyze_user_input(
            user_message=f"Analyze these design preferences: {preference_text}", session_id=session_id
        )

        return {"analysis": analysis, "insights": conversational_response, "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Error analyzing user preference: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/sessions/{session_id}/generate-style-guide")
async def generate_style_guide(
    session_id: str, request: dict, db: AsyncSession = Depends(get_db)  # Contains room_type, style_preferences, etc.
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
            user_message=style_guide_prompt, session_id=session_id
        )

        return {"style_guide": conversational_response, "analysis": analysis, "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Error generating style guide: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


@router.post("/sessions/{session_id}/remove-furniture")
async def remove_furniture_from_visualization(session_id: str, request: dict, db: AsyncSession = Depends(get_db)):
    """
    Remove furniture from a visualization image for edit mode.
    Synchronous endpoint that directly calls Google AI service.

    Request body should contain:
    - image: base64 encoded image
    """
    try:
        logger.info(f"Removing furniture for edit mode, session: {session_id}")

        # Extract image from request
        image = request.get("image")
        if not image:
            raise HTTPException(status_code=400, detail="No image provided")

        # Call Google AI service to remove furniture (with retries)
        clean_image = await google_ai_service.remove_furniture(image, max_retries=3)

        if not clean_image:
            raise HTTPException(status_code=500, detail="Failed to remove furniture after retries")

        logger.info(f"Successfully removed furniture for session {session_id}")
        return {"clean_image": clean_image, "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Error removing furniture: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")
