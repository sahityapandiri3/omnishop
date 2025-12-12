"""
Chat API routes for interior design assistance
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from schemas.chat import (
    BudgetAllocation,
    CategoryRecommendation,
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatMessageSchema,
    ChatSessionSchema,
    ConversationState,
    DesignAnalysisSchema,
    MessageType,
    StartSessionRequest,
    StartSessionResponse,
)
from services.budget_allocator import validate_and_adjust_budget_allocations
from services.chatgpt_service import chatgpt_service
from services.conversation_context import conversation_context_manager
from services.google_ai_service import VisualizationRequest, VisualizationResult, google_ai_service
from services.ml_recommendation_model import ml_recommendation_model
from services.nlp_processor import design_nlp_processor
from services.recommendation_engine import RecommendationRequest, recommendation_engine
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from database.models import Category, ChatLog, ChatMessage, ChatSession, Product
from utils.chat_logger import chat_logger

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

        # Add persistent chat log entry to database
        chat_log_entry = ChatLog(
            session_id=session_id,
            user_id=session.user_id,
            server_type=chat_logger.server_type,
            user_message=request.message,
            assistant_response=conversational_response,
        )
        db.add(chat_log_entry)

        await db.commit()

        # Also log to chat.md file (for local development quick viewing)
        chat_logger.log_conversation(
            session_id=session_id,
            user_id=session.user_id,
            user_message=request.message,
            assistant_response=conversational_response,
        )

        # Initialize response fields
        recommended_products = []
        detected_furniture = None
        similar_furniture_items = None
        action_options = None
        requires_action_choice = False
        visualization_image = None

        # =================================================================
        # EARLY: Determine conversation state based on user message count
        # This controls whether we fetch products or continue gathering info
        # =================================================================
        message_count_query = select(func.count(ChatMessage.id)).where(
            ChatMessage.session_id == session_id, ChatMessage.type == MessageType.user
        )
        message_count_result = await db.execute(message_count_query)
        user_message_count = message_count_result.scalar() or 1

        # =================================================================
        # DIRECT SEARCH DETECTION: Check if user is making a direct product search
        # Example: "show me brown sofas" or "large rugs under 20000"
        # If detected, bypass guided flow and search immediately
        # =================================================================
        direct_search_result = _detect_direct_search_query(request.message)
        is_direct_search = direct_search_result["is_direct_search"]

        # =================================================================
        # DIRECT SEARCH FOLLOW-UP: Check if previous message was DIRECT_SEARCH_GATHERING
        # If user provided a follow-up (e.g., "abstract art" after "give me wall art"),
        # combine their response with the original category
        # =================================================================
        previous_direct_search_categories = None
        if not is_direct_search:
            # Check if previous assistant message was in DIRECT_SEARCH_GATHERING state
            # CRITICAL: Exclude the current request's assistant message (we just created it above)
            # Without this exclusion, we'd get the message we're currently creating, not the PREVIOUS one
            prev_msg_query = (
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == session_id,
                    ChatMessage.type == MessageType.assistant,
                    ChatMessage.id != assistant_message_id,  # Exclude current message
                )
                .order_by(ChatMessage.timestamp.desc())
                .limit(1)
            )
            prev_msg_result = await db.execute(prev_msg_query)
            prev_msg = prev_msg_result.scalar_one_or_none()

            logger.info(
                f"[DIRECT SEARCH FOLLOW-UP] Querying for previous message (excluding current {assistant_message_id[:8]}...)"
            )

            if prev_msg:
                logger.info(f"[DIRECT SEARCH FOLLOW-UP] Found previous message: {prev_msg.id[:8]}...")
            else:
                logger.info(f"[DIRECT SEARCH FOLLOW-UP] No previous assistant message found (this is the first message)")

            if prev_msg and prev_msg.analysis_data:
                try:
                    import json

                    prev_analysis = (
                        prev_msg.analysis_data
                        if isinstance(prev_msg.analysis_data, dict)
                        else json.loads(prev_msg.analysis_data)
                    )
                    prev_state = prev_analysis.get("conversation_state")
                    logger.info(f"[DIRECT SEARCH FOLLOW-UP] Previous message state: {prev_state}")

                    if prev_state == "DIRECT_SEARCH_GATHERING":
                        # DIRECT RETRIEVAL: Use ALL stored detected_categories (not just the first one)
                        # This allows multi-category searches like "show me sofas and coffee tables"
                        stored_categories = prev_analysis.get("detected_categories", [])
                        if stored_categories and len(stored_categories) > 0:
                            # Use ALL categories, not just the first one
                            previous_direct_search_categories = stored_categories
                            logger.info(
                                f"[DIRECT SEARCH FOLLOW-UP] Retrieved {len(stored_categories)} stored categories: {[c.get('display_name') for c in stored_categories]}"
                            )

                        if previous_direct_search_categories:
                            # User is providing follow-up info - treat current message as qualifiers
                            # Re-run detection but force it to be a direct search with ALL previous categories
                            is_direct_search = True
                            direct_search_result["is_direct_search"] = True
                            direct_search_result["detected_categories"] = previous_direct_search_categories
                            # Mark as having sufficient info since user provided follow-up
                            direct_search_result["has_sufficient_info"] = True
                            # Extract qualifiers from current message
                            # For follow-up messages, we need to extract colors even from short messages like "red"
                            # Use direct keyword matching instead of _detect_direct_search_query which requires 5+ char messages
                            message_lower = request.message.lower().strip()

                            # Direct color extraction for follow-up (no minimum length requirement)
                            extracted_colors = []
                            for color in COLOR_KEYWORDS:
                                if color in message_lower:
                                    extracted_colors.append(color)

                            # Direct material extraction for follow-up
                            extracted_materials = []
                            for material in MATERIAL_KEYWORDS:
                                if material in message_lower:
                                    extracted_materials.append(material)

                            # Direct style extraction for follow-up
                            extracted_styles = []
                            for style in STYLE_KEYWORDS_DIRECT:
                                if style in message_lower:
                                    extracted_styles.append(style)

                            # Direct size extraction for follow-up
                            extracted_sizes = []
                            for size in SIZE_KEYWORDS:
                                if size in message_lower:
                                    extracted_sizes.append(size)

                            # Budget extraction
                            import re

                            budget_match = re.search(
                                r"(?:under|below|max|budget|upto|up to|less than)\s*(?:rs\.?|₹|inr)?\s*(\d{1,3}(?:[,\s]?\d{3})*)",
                                message_lower,
                            )
                            extracted_budget = (
                                int(budget_match.group(1).replace(",", "").replace(" ", "")) if budget_match else None
                            )

                            direct_search_result["extracted_colors"] = extracted_colors
                            direct_search_result["extracted_materials"] = extracted_materials
                            direct_search_result["extracted_styles"] = extracted_styles
                            direct_search_result["extracted_sizes"] = extracted_sizes
                            direct_search_result["extracted_budget_max"] = extracted_budget

                            logger.info(
                                f"[DIRECT SEARCH FOLLOW-UP] Extracted from message: colors={extracted_colors}, styles={extracted_styles}"
                            )

                            # If no explicit style was detected, use the message as style hint
                            # BUT exclude color keywords - those should be handled as colors, not styles
                            if not direct_search_result["extracted_styles"]:
                                # Add the user's message as a style keyword (e.g., "abstract art" -> "abstract")
                                words = request.message.lower().split()
                                # Exclude stop words AND color keywords (colors should be filtered, not used as styles)
                                exclude_words = ["art", "the", "a", "an", "some", "please"] + [
                                    c.lower() for c in COLOR_KEYWORDS
                                ]
                                direct_search_result["extracted_styles"] = [w for w in words if w not in exclude_words]

                            logger.info(
                                f"[DIRECT SEARCH FOLLOW-UP] Converted to direct search with {len(previous_direct_search_categories)} categories={[c['category_id'] for c in previous_direct_search_categories]}, colors={direct_search_result['extracted_colors']}, styles={direct_search_result['extracted_styles']}"
                            )
                except Exception as e:
                    logger.error(f"[DIRECT SEARCH FOLLOW-UP] Error parsing previous message: {e}")

        # =================================================================
        # ACCUMULATED CONTEXT SEARCH: Use accumulated filters when user provides only qualifiers
        # Example: User says "green color" or "under ₹50000" without mentioning a category
        # If we have an accumulated category from conversation history, use it
        # =================================================================
        if not is_direct_search and session_id:
            # Check if user message contains qualifiers (colors, styles, prices) but no category
            message_lower = request.message.lower().strip()
            has_color_qualifier = any(color in message_lower for color in COLOR_KEYWORDS)
            has_style_qualifier = any(style in message_lower for style in STYLE_KEYWORDS_DIRECT)
            has_material_qualifier = any(material in message_lower for material in MATERIAL_KEYWORDS)

            # Extract price from message
            import re

            price_pattern = r"(?:under|below|less than|max|upto|up to|within|budget)\s*(?:₹|rs\.?|inr)?\s*([\d,\s]+)"
            price_match = re.search(price_pattern, message_lower)
            has_price_qualifier = price_match is not None

            has_any_qualifier = has_color_qualifier or has_style_qualifier or has_material_qualifier or has_price_qualifier
            has_no_category = len(direct_search_result.get("detected_categories", [])) == 0

            if has_any_qualifier and has_no_category:
                # Check accumulated filters for a category
                accumulated_filters = conversation_context_manager.get_accumulated_filters(session_id)
                accumulated_category = accumulated_filters.get("category")
                accumulated_product_types = accumulated_filters.get("product_types", [])

                if accumulated_category or accumulated_product_types:
                    # We have an accumulated category - convert to direct search
                    logger.info(
                        f"[ACCUMULATED CONTEXT] User provided qualifiers without category, using accumulated: {accumulated_category or accumulated_product_types}"
                    )

                    is_direct_search = True
                    direct_search_result["is_direct_search"] = True
                    direct_search_result["has_sufficient_info"] = True

                    # Build categories from accumulated context
                    if accumulated_product_types:
                        # Use product_types if available (more specific)
                        for ptype in accumulated_product_types:
                            direct_search_result["detected_categories"].append(
                                {
                                    "category_id": ptype,
                                    "display_name": ptype.replace("_", " ").title(),
                                    "matched_keyword": ptype,
                                }
                            )
                    elif accumulated_category:
                        # Fall back to generic category
                        direct_search_result["detected_categories"].append(
                            {
                                "category_id": accumulated_category,
                                "display_name": accumulated_category.replace("_", " ").title(),
                                "matched_keyword": accumulated_category,
                            }
                        )

                    # Extract qualifiers from current message
                    if has_color_qualifier:
                        direct_search_result["extracted_colors"] = [c for c in COLOR_KEYWORDS if c in message_lower]
                    if has_style_qualifier:
                        direct_search_result["extracted_styles"] = [s for s in STYLE_KEYWORDS_DIRECT if s in message_lower]
                    if has_material_qualifier:
                        direct_search_result["extracted_materials"] = [m for m in MATERIAL_KEYWORDS if m in message_lower]
                    if has_price_qualifier and price_match:
                        direct_search_result["extracted_budget_max"] = int(
                            price_match.group(1).replace(",", "").replace(" ", "")
                        )

                    logger.info(
                        f"[ACCUMULATED CONTEXT] Converted to direct search: categories={[c['category_id'] for c in direct_search_result['detected_categories']]}, "
                        f"colors={direct_search_result.get('extracted_colors', [])}, styles={direct_search_result.get('extracted_styles', [])}"
                    )

        # Determine early conversation state
        # States: GATHERING_USAGE (msg 1), GATHERING_STYLE (msg 2), GATHERING_BUDGET (msg 3), READY_TO_RECOMMEND (msg 4+)
        early_conversation_state = "INITIAL"
        if is_direct_search:
            # BYPASS: Direct search query detected - skip guided flow entirely
            early_conversation_state = "DIRECT_SEARCH"
            logger.info(f"[DIRECT SEARCH] Bypassing guided flow for direct search query: {request.message[:50]}...")
        elif user_message_count == 1:
            early_conversation_state = "GATHERING_USAGE"
        elif user_message_count == 2:
            early_conversation_state = "GATHERING_STYLE"
        elif user_message_count == 3:
            early_conversation_state = "GATHERING_BUDGET"
        else:
            early_conversation_state = "READY_TO_RECOMMEND"

        logger.info(f"[GUIDED FLOW EARLY] User message count: {user_message_count}, state: {early_conversation_state}")

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

            # Get product recommendations ONLY if in READY_TO_RECOMMEND state
            # This prevents showing products during the guided conversation gathering phase
            if early_conversation_state == "READY_TO_RECOMMEND":
                logger.info("[GUIDED FLOW] In READY_TO_RECOMMEND state - fetching products")
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
                    logger.warning(f"Analysis is None for session {session_id}, attempting keyword-based search")
                    # Even without AI analysis, try to extract keywords from user message
                    # This ensures "show me sofas" returns sofas, not random products
                    from schemas.chat import DesignAnalysisSchema

                    fallback_analysis = DesignAnalysisSchema(
                        design_analysis={},
                        product_matching_criteria={},
                        visualization_guidance={},
                        confidence_scores={},
                        recommendations={},
                    )

                    # Extract keywords from user message for targeted search
                    extracted_keywords = _extract_product_keywords(request.message)
                    if extracted_keywords:
                        logger.info(f"Extracted keywords from user message: {extracted_keywords}")
                        # Use keyword-based search instead of random products
                        recommended_products = await _get_product_recommendations(
                            fallback_analysis,
                            db,
                            user_message=request.message,
                            limit=50,
                            user_id=session.user_id,
                            session_id=session_id,
                            selected_stores=request.selected_stores,
                        )
                    else:
                        # No keywords found, fall back to random products
                        logger.warning("No keywords extracted, using basic random recommendations")
                        recommended_products = await _get_basic_product_recommendations(fallback_analysis, db, limit=50)
            else:
                logger.info(f"[GUIDED FLOW] In {early_conversation_state} state - skipping product fetch (gathering info)")

            # Enhance conversational response based on whether products were found
            # ONLY do this during READY_TO_RECOMMEND state - during gathering phases, let the follow-up questions handle the response
            if early_conversation_state == "READY_TO_RECOMMEND":
                if recommended_products and len(recommended_products) > 0:
                    # Products found - mention they're being shown
                    if (
                        " products" not in conversational_response.lower()
                        and " showing" not in conversational_response.lower()
                    ):
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
            else:
                logger.info(f"[GUIDED FLOW] Skipping product response enhancement during {early_conversation_state} state")

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
                        "sculpture",
                        "figurine",
                        "statue",
                        "art piece",
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

            # =================================================================
            # SPACE FITNESS VALIDATION - Check if product fits before visualizing
            # =================================================================
            try:
                logger.info(f"Validating space fitness for {product.name}")
                space_fitness = await google_ai_service.validate_space_fitness(
                    room_image=room_image,
                    product_name=product.name,
                    product_image=product_image_url,
                    product_description=product.description,
                )

                # If product doesn't fit and we have high confidence, return helpful message
                if not space_fitness.fits and space_fitness.confidence >= 0.7:
                    logger.info(f"Product '{product.name}' doesn't fit in the space: {space_fitness.reason}")

                    # Build a helpful response message
                    response_message = f"I've analyzed the space and unfortunately this product may not fit well in your room. {space_fitness.reason}"
                    if space_fitness.suggestion:
                        response_message += f"\n\n💡 Suggestion: {space_fitness.suggestion}"
                    response_message += (
                        "\n\nWould you like me to suggest some alternatives that might work better for your space?"
                    )

                    # Update the conversational response with the space fitness message
                    conversational_response = response_message

                    # Don't generate visualization - return early with the message
                    message_schema = ChatMessageSchema(
                        id=assistant_message_id,
                        type=MessageType.assistant,
                        content=conversational_response,
                        timestamp=assistant_message.timestamp,
                        session_id=session_id,
                        products=None,
                        image_url=None,  # No visualization since product doesn't fit
                    )

                    return ChatMessageResponse(
                        message=message_schema,
                        analysis=analysis,
                        recommended_products=None,
                        detected_furniture=detected_furniture,
                        similar_furniture_items=similar_furniture_items,
                        requires_action_choice=False,
                        action_options=None,
                        background_task_id=background_task_id,
                    )

                logger.info(f"Space fitness validation passed: {space_fitness.reason}")

            except Exception as fitness_error:
                # Log the error but continue with visualization (fail open)
                logger.warning(f"Space fitness validation failed, proceeding with visualization: {fitness_error}")

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
            # SKIP if: direct search (handled later) or in gathering state (no products during gathering)
            should_skip_default_products = is_direct_search or early_conversation_state in [
                "GATHERING_USAGE",
                "GATHERING_STYLE",
                "GATHERING_BUDGET",
            ]
            if analysis and not should_skip_default_products:
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

        # =================================================================
        # NEW: Extract guided conversation fields from analysis
        # =================================================================
        conversation_state = "INITIAL"
        selected_categories_response: Optional[List[CategoryRecommendation]] = None
        products_by_category: Optional[Dict[str, List[dict]]] = None
        follow_up_question: Optional[str] = None
        total_budget: Optional[int] = None

        if analysis:
            # Extract conversation state and related fields
            conversation_state = getattr(analysis, "conversation_state", None) or "INITIAL"
            follow_up_question = getattr(analysis, "follow_up_question", None)
            total_budget = getattr(analysis, "total_budget", None)
            raw_categories = getattr(analysis, "selected_categories", None)

            logger.info(
                f"[GUIDED FLOW] ChatGPT returned conversation_state={conversation_state}, has_categories={raw_categories is not None}"
            )

            # =================================================================
            # BACKEND STATE OVERRIDE: Force guided flow if ChatGPT fails
            # =================================================================
            # Count existing messages in this session (excluding the one we just added)
            message_count_query = select(func.count(ChatMessage.id)).where(
                ChatMessage.session_id == session_id, ChatMessage.type == MessageType.user
            )
            message_count_result = await db.execute(message_count_query)
            user_message_count = message_count_result.scalar() or 1  # Current message makes it at least 1

            logger.info(f"[GUIDED FLOW] Session has {user_message_count} user messages")

            # =================================================================
            # DIRECT SEARCH BYPASS: Skip guided flow for direct product searches
            # =================================================================
            if is_direct_search:
                has_sufficient_info = direct_search_result.get("has_sufficient_info", False)

                if has_sufficient_info:
                    # User provided enough info (category + qualifier) - search directly
                    conversation_state = "DIRECT_SEARCH"
                    follow_up_question = None
                    logger.info(f"[DIRECT SEARCH] Sufficient info - bypassing guided flow for direct search")

                    # Build categories from detected categories
                    raw_categories = []
                    for idx, cat_data in enumerate(direct_search_result["detected_categories"]):
                        budget_max = direct_search_result["extracted_budget_max"] or 999999
                        raw_categories.append(
                            {
                                "category_id": cat_data["category_id"],
                                "display_name": cat_data["display_name"],
                                "priority": idx + 1,
                                "budget_allocation": {"min": 0, "max": budget_max},
                            }
                        )

                    logger.info(f"[DIRECT SEARCH] Built {len(raw_categories)} categories from user query")
                else:
                    # User mentioned a category but no qualifiers - ask follow-up
                    conversation_state = "DIRECT_SEARCH_GATHERING"
                    follow_up_question = _build_direct_search_followup_question(direct_search_result["detected_categories"])
                    logger.info(f"[DIRECT SEARCH] Set conversation_state=DIRECT_SEARCH_GATHERING (insufficient info)")
                    logger.info(f"[DIRECT SEARCH] Follow-up question: {follow_up_question[:50]}...")

            # ALWAYS enforce guided flow based on message count for consistent friendly tone
            # Use our friendly fallback questions instead of AI-generated ones for better UX
            elif user_message_count == 1:
                conversation_state = "GATHERING_USAGE"
                # Always use our friendly question for consistent tone
                follow_up_question = "Love it! How do you usually use this space - relaxing, working, or entertaining?"
                logger.info(f"[GUIDED FLOW] Set to GATHERING_USAGE (message 1)")
            elif user_message_count == 2:
                conversation_state = "GATHERING_STYLE"
                follow_up_question = "Perfect! What vibe are you going for - modern and sleek, cozy and warm, or eclectic?"
                logger.info(f"[GUIDED FLOW] Set to GATHERING_STYLE (message 2)")
            elif user_message_count == 3:
                conversation_state = "GATHERING_BUDGET"
                follow_up_question = "Great choice! What's your budget for this transformation?"
                logger.info(f"[GUIDED FLOW] Set to GATHERING_BUDGET (message 3)")
            else:
                conversation_state = "READY_TO_RECOMMEND"
                follow_up_question = None
                logger.info(f"[GUIDED FLOW] Set to READY_TO_RECOMMEND (message {user_message_count})")

                # Generate default categories if ChatGPT didn't provide them
                if not raw_categories or len(raw_categories) == 0:
                    # Determine room type from conversation context (simplified)
                    room_context = request.message.lower()
                    if "living" in room_context or "sofa" in room_context:
                        raw_categories = [
                            {
                                "category_id": "sofas",
                                "display_name": "Sofas",
                                "priority": 1,
                                "budget_allocation": {"min": 20000, "max": 50000},
                            },
                            {
                                "category_id": "coffee_tables",
                                "display_name": "Coffee Tables",
                                "priority": 2,
                                "budget_allocation": {"min": 5000, "max": 15000},
                            },
                            {
                                "category_id": "side_tables",
                                "display_name": "Side Tables",
                                "priority": 3,
                                "budget_allocation": {"min": 3000, "max": 10000},
                            },
                            {
                                "category_id": "floor_lamps",
                                "display_name": "Floor Lamps",
                                "priority": 4,
                                "budget_allocation": {"min": 2000, "max": 8000},
                            },
                            {
                                "category_id": "rugs",
                                "display_name": "Rugs & Carpets",
                                "priority": 5,
                                "budget_allocation": {"min": 5000, "max": 20000},
                            },
                        ]
                    elif "bed" in room_context or "sleep" in room_context:
                        raw_categories = [
                            {
                                "category_id": "beds",
                                "display_name": "Beds",
                                "priority": 1,
                                "budget_allocation": {"min": 25000, "max": 60000},
                            },
                            {
                                "category_id": "nightstands",
                                "display_name": "Nightstands",
                                "priority": 2,
                                "budget_allocation": {"min": 5000, "max": 15000},
                            },
                            {
                                "category_id": "table_lamps",
                                "display_name": "Table Lamps",
                                "priority": 3,
                                "budget_allocation": {"min": 2000, "max": 8000},
                            },
                            {
                                "category_id": "wardrobes",
                                "display_name": "Wardrobes",
                                "priority": 4,
                                "budget_allocation": {"min": 20000, "max": 50000},
                            },
                        ]
                    elif "dining" in room_context or "eat" in room_context:
                        raw_categories = [
                            {
                                "category_id": "dining_tables",
                                "display_name": "Dining Tables",
                                "priority": 1,
                                "budget_allocation": {"min": 20000, "max": 50000},
                            },
                            {
                                "category_id": "dining_chairs",
                                "display_name": "Dining Chairs",
                                "priority": 2,
                                "budget_allocation": {"min": 10000, "max": 30000},
                            },
                            {
                                "category_id": "sideboards",
                                "display_name": "Sideboards",
                                "priority": 3,
                                "budget_allocation": {"min": 15000, "max": 40000},
                            },
                        ]
                    else:
                        # Default to living room categories
                        raw_categories = [
                            {
                                "category_id": "sofas",
                                "display_name": "Sofas",
                                "priority": 1,
                                "budget_allocation": {"min": 20000, "max": 50000},
                            },
                            {
                                "category_id": "coffee_tables",
                                "display_name": "Coffee Tables",
                                "priority": 2,
                                "budget_allocation": {"min": 5000, "max": 15000},
                            },
                            {
                                "category_id": "accent_chairs",
                                "display_name": "Accent Chairs",
                                "priority": 3,
                                "budget_allocation": {"min": 8000, "max": 25000},
                            },
                            {
                                "category_id": "floor_lamps",
                                "display_name": "Floor Lamps",
                                "priority": 4,
                                "budget_allocation": {"min": 2000, "max": 8000},
                            },
                            {
                                "category_id": "decor",
                                "display_name": "Decor",
                                "priority": 5,
                                "budget_allocation": {"min": 2000, "max": 10000},
                            },
                        ]
                    logger.info(f"[GUIDED FLOW] Generated {len(raw_categories)} default categories")

            # If we have selected categories, convert to CategoryRecommendation objects
            if raw_categories and isinstance(raw_categories, list) and len(raw_categories) > 0:
                try:
                    selected_categories_response = []
                    for idx, cat_data in enumerate(raw_categories):
                        if isinstance(cat_data, dict):
                            # Parse budget_allocation if present
                            budget_alloc = None
                            if "budget_allocation" in cat_data and cat_data["budget_allocation"]:
                                budget_data = cat_data["budget_allocation"]
                                budget_alloc = BudgetAllocation(
                                    min=budget_data.get("min", 0), max=budget_data.get("max", 999999)
                                )

                            cat_rec = CategoryRecommendation(
                                category_id=cat_data.get("category_id", f"category_{idx}"),
                                display_name=cat_data.get(
                                    "display_name", cat_data.get("category_id", "").replace("_", " ").title()
                                ),
                                budget_allocation=budget_alloc,
                                priority=cat_data.get("priority", idx + 1),
                            )
                            selected_categories_response.append(cat_rec)

                    logger.info(f"[GUIDED FLOW] Parsed {len(selected_categories_response)} categories")

                    # MANDATORY: Ensure generic categories (planters, wall_art, decor, rugs) are ALWAYS included
                    # BUT ONLY for READY_TO_RECOMMEND - NOT for DIRECT_SEARCH or GATHERING states
                    # Direct search should ONLY show what the user asked for (e.g., "sofas" -> only sofas)
                    # Gathering states should NOT show categories yet (we're still collecting preferences)
                    if conversation_state == "READY_TO_RECOMMEND":
                        existing_cat_ids = {cat.category_id for cat in selected_categories_response}
                        mandatory_generic = [
                            ("planters", "Planters", 100),
                            ("wall_art", "Wall Art", 101),
                            ("decor", "Decor", 102),
                            ("rugs", "Rugs", 103),
                        ]
                        for cat_id, display_name, priority in mandatory_generic:
                            if cat_id not in existing_cat_ids:
                                selected_categories_response.append(
                                    CategoryRecommendation(
                                        category_id=cat_id,
                                        display_name=display_name,
                                        budget_allocation=BudgetAllocation(min=500, max=15000),
                                        priority=priority,
                                    )
                                )
                                logger.info(f"[GUIDED FLOW] Added missing mandatory category: {cat_id}")
                    else:
                        logger.info(f"[DIRECT SEARCH] Skipping mandatory categories - showing only user-requested categories")

                    # =================================================================
                    # BUDGET VALIDATION: Ensure budget allocations sum to total budget
                    # Get budget from: AI analysis, direct search extraction, or accumulated filters
                    # =================================================================
                    user_total_budget = None
                    if total_budget:
                        user_total_budget = total_budget
                    elif direct_search_result.get("extracted_budget_max"):
                        user_total_budget = direct_search_result["extracted_budget_max"]
                    elif session_id:
                        # Try to get from accumulated filters
                        acc_filters = conversation_context_manager.get_accumulated_filters(session_id)
                        if acc_filters and acc_filters.get("price_max"):
                            user_total_budget = acc_filters["price_max"]

                    if user_total_budget and selected_categories_response:
                        logger.info(f"[BUDGET] Validating allocations for total budget ₹{user_total_budget:,}")
                        # Convert CategoryRecommendation objects to a format the validator can work with
                        selected_categories_response = validate_and_adjust_budget_allocations(
                            total_budget=float(user_total_budget),
                            categories=selected_categories_response,
                            category_id_field="category_id",
                        )

                    # If we're in READY_TO_RECOMMEND or DIRECT_SEARCH state, fetch products by category
                    if conversation_state in ["READY_TO_RECOMMEND", "DIRECT_SEARCH"] and selected_categories_response:
                        if conversation_state == "DIRECT_SEARCH":
                            logger.info("[DIRECT SEARCH] Fetching products for direct search query...")

                            # Build style attributes from user's direct input instead of ChatGPT analysis
                            style_attributes = {
                                "style_keywords": direct_search_result["extracted_styles"][:],  # Copy to avoid mutation
                                "colors": direct_search_result["extracted_colors"],
                                "materials": direct_search_result["extracted_materials"],
                            }
                            # Also add size keywords to style_keywords for matching
                            if direct_search_result["extracted_sizes"]:
                                style_attributes["style_keywords"].extend(direct_search_result["extracted_sizes"])

                            logger.info(f"[DIRECT SEARCH] Style attributes from user query: {style_attributes}")
                        else:
                            logger.info("[GUIDED FLOW] Fetching category-based recommendations...")

                            # Extract style attributes from ChatGPT analysis to pass to product search
                            # This enables style-aware product prioritization
                            style_attributes = _extract_style_attributes_from_analysis(analysis)
                            logger.info(f"[GUIDED FLOW] Extracted style attributes: {style_attributes}")

                        products_by_category = await _get_category_based_recommendations(
                            selected_categories_response,
                            db,
                            selected_stores=request.selected_stores,
                            limit_per_category=50,  # Increased from 20 to provide more variety
                            style_attributes=style_attributes,
                        )

                        # Update product counts in category recommendations
                        for cat in selected_categories_response:
                            if cat.category_id in products_by_category:
                                cat.product_count = len(products_by_category[cat.category_id])

                        logger.info(
                            f"[{'DIRECT SEARCH' if conversation_state == 'DIRECT_SEARCH' else 'GUIDED FLOW'}] Fetched products for {len(products_by_category)} categories"
                        )

                        # For direct search, override the conversational response with a friendly message
                        if conversation_state == "DIRECT_SEARCH" and products_by_category:
                            total_products = sum(len(prods) for prods in products_by_category.values())
                            conversational_response = _build_direct_search_response_message(
                                detected_categories=direct_search_result["detected_categories"],
                                colors=direct_search_result["extracted_colors"],
                                materials=direct_search_result["extracted_materials"],
                                styles=direct_search_result["extracted_styles"],
                                product_count=total_products,
                            )
                            logger.info(f"[DIRECT SEARCH] Response: {conversational_response[:80]}...")

                            # CRITICAL: Rebuild message_schema with the direct search response
                            # (the original was built with ChatGPT's response before we could override)
                            message_schema = ChatMessageSchema(
                                id=assistant_message_id,
                                type=MessageType.assistant,
                                content=conversational_response,
                                timestamp=assistant_message.timestamp,
                                session_id=session_id,
                                products=recommended_products,
                                image_url=visualization_image,
                            )

                except Exception as e:
                    logger.error(f"[GUIDED FLOW] Error parsing categories: {e}")
                    import traceback

                    traceback.print_exc()

        # =================================================================
        # CRITICAL FIX: During GATHERING states:
        # 1. Clear products - don't show any product recommendations
        # 2. Replace AI response with ONLY the follow-up question
        #    (ChatGPT often ignores the prompt and gives recommendations anyway)
        # 3. Clear follow_up_question so frontend doesn't append it again
        # =================================================================
        if conversation_state in ["GATHERING_USAGE", "GATHERING_STYLE", "GATHERING_BUDGET", "DIRECT_SEARCH_GATHERING"]:
            logger.info(f"[GUIDED FLOW] State is {conversation_state} - enforcing clean guided flow")
            recommended_products = None
            # CRITICAL: Also clear category-based products - no products during gathering!
            products_by_category = None
            selected_categories_response = None

            # CRITICAL: Replace the full AI response with JUST the follow-up question
            # This ensures NO design recommendations slip through during gathering
            if follow_up_question:
                conversational_response = follow_up_question
                # Clear follow_up_question so frontend doesn't append it again
                # (frontend appends follow_up_question to message.content)
                follow_up_question = None
                logger.info(f"[GUIDED FLOW] Replaced AI response with follow-up question only")

            # Rebuild message schema with clean response and no products
            message_schema = ChatMessageSchema(
                id=assistant_message_id,
                type=MessageType.assistant,
                content=conversational_response,
                timestamp=assistant_message.timestamp,
                session_id=session_id,
                products=None,  # Clear products during gathering
                image_url=visualization_image,
            )

        # =================================================================
        # CRITICAL: Update assistant_message.analysis_data with our overridden
        # conversation_state so that follow-up detection works correctly
        # The original analysis_data contains ChatGPT's state, but we override it
        # =================================================================
        if analysis:
            import json

            updated_analysis_data = analysis.dict() if hasattr(analysis, "dict") else dict(analysis)
            updated_analysis_data["conversation_state"] = conversation_state
            # Store the FULL detected_categories objects for follow-up detection
            # This allows us to directly retrieve the category without re-detecting from keywords
            logger.info(
                f"[ANALYSIS DATA] About to update - conversation_state={conversation_state}, has_detected_categories={bool(direct_search_result.get('detected_categories'))}"
            )
            if direct_search_result.get("detected_categories"):
                updated_analysis_data["detected_categories"] = direct_search_result["detected_categories"]
                updated_analysis_data["product_matching_criteria"] = {
                    "product_types": [
                        cat.get("category_id", cat.get("name", "")) for cat in direct_search_result["detected_categories"]
                    ],
                    "search_terms": [
                        cat.get("category_id", cat.get("name", "")) for cat in direct_search_result["detected_categories"]
                    ],
                    "colors": direct_search_result.get("extracted_colors", []),
                    "styles": direct_search_result.get("extracted_styles", []),
                }
                logger.info(f"[ANALYSIS DATA] Saved detected_categories: {updated_analysis_data['detected_categories']}")
            assistant_message.analysis_data = updated_analysis_data
            await db.commit()
            logger.info(
                f"[ANALYSIS DATA] Updated assistant_message.analysis_data with conversation_state={conversation_state}"
            )

        return ChatMessageResponse(
            message=message_schema,
            analysis=analysis,
            recommended_products=recommended_products,
            detected_furniture=detected_furniture,
            similar_furniture_items=similar_furniture_items,
            requires_action_choice=requires_action_choice,
            action_options=action_options,
            # NEW: Guided conversation fields
            conversation_state=conversation_state,
            selected_categories=selected_categories_response,
            products_by_category=products_by_category,
            follow_up_question=follow_up_question,
            total_budget=total_budget,
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

        # Handle force reset FIRST - this takes priority over incremental mode
        # force_reset means products were removed, so we must use the clean base image
        if force_reset:
            logger.info(f"Force reset requested - clearing visualization history for session {session_id}")
            context = conversation_context_manager.get_or_create_context(session_id)
            context.visualization_history = []
            context.visualization_redo_stack = []
            # CRITICAL: Do NOT use incremental mode when force_reset is True
            # We need to use the provided clean base image and visualize ALL products fresh
            is_incremental = False
            logger.info("Force reset: Disabled incremental mode to ensure clean visualization")

        # Check product count and enforce incremental visualization for larger sets
        # The Gemini API has input size limitations and fails with 500 errors when
        # processing 5+ products simultaneously. Use incremental mode as workaround.
        # IMPORTANT: Only force incremental if NOT doing a force_reset
        MAX_PRODUCTS_BATCH = 4
        forced_incremental = False
        if len(products) > MAX_PRODUCTS_BATCH and not is_incremental and not force_reset:
            logger.info(
                f"Product count ({len(products)}) exceeds batch limit ({MAX_PRODUCTS_BATCH}). Forcing incremental visualization."
            )
            is_incremental = True
            forced_incremental = True

        # Note: force_reset handling was moved above to take priority over incremental mode

        # Default: visualize all products provided
        new_products_to_visualize = products

        if is_incremental:
            # CRITICAL FIX: Use the base image sent by the frontend, NOT the backend's history.
            # The frontend manages its own undo/redo stack and sends the correct base image
            # (e.g., after undo, it sends the post-undo image, not the pre-undo one).
            # The backend's history might be out of sync with the frontend's local undo/redo state.
            #
            # The frontend also sends only NEW products (already filtered), so we treat all
            # products in the request as new_products_to_visualize.
            new_products_to_visualize = products  # Frontend already sends only new products

            logger.info(
                f"Incremental mode: Using frontend-provided base image. " f"Products to add: {len(new_products_to_visualize)}"
            )

            # If no products to visualize, return the provided base image
            if not new_products_to_visualize:
                logger.info("No products to visualize - returning provided base image")
                return {
                    "visualization": {
                        "rendered_image": base_image,
                        "processing_time": 0.0,
                        "quality_metrics": {
                            "overall_quality": 0.85,
                            "placement_accuracy": 0.90,
                            "lighting_realism": 0.85,
                            "confidence_score": 0.87,
                        },
                    },
                    "message": "All selected products are already visualized.",
                    "can_undo": conversation_context_manager.can_undo(session_id),
                    "can_redo": conversation_context_manager.can_redo(session_id),
                }

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
        # IMPORTANT: Skip clarification if custom_positions are provided (user explicitly positioned items)
        if matching_existing and not user_action and not custom_positions:
            product_type_display = list(selected_product_types)[0].replace("_", " ")
            count = len(matching_existing)
            plural = "s" if count > 1 else ""
            logger.info(f"Requesting clarification: found {count} matching {product_type_display}{plural} in room")

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
        elif matching_existing and custom_positions:
            # Skip clarification when custom positions are provided
            logger.info(
                f"Skipping clarification: custom_positions provided (user explicitly positioned {len(custom_positions)} items)"
            )

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

        # Handle incremental visualization (add ONLY NEW products to existing visualization)
        if is_incremental:
            logger.info(
                f"Incremental visualization: Adding {len(new_products_to_visualize)} NEW products (out of {len(products)} total)"
            )

            # Use BATCH add visualization for all new products in a SINGLE API call
            # This is much faster than calling generate_add_visualization one product at a time
            try:
                product_names = [p.get("full_name") or p.get("name") for p in new_products_to_visualize]
                logger.info(f"  Batch adding products: {', '.join(product_names)}")

                current_image = await google_ai_service.generate_add_multiple_visualization(
                    room_image=base_image,  # Start with previous visualization (already has old products)
                    products=new_products_to_visualize,
                )
            except ValueError as e:
                logger.error(f"Batch visualization error: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to add products to visualization. Please try again.",
                )

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
            # When force_reset is True, use exclusive_products mode to ONLY show specified products
            # and remove any existing furniture from the base image
            viz_request = VisualizationRequest(
                base_image=base_image,
                products_to_place=products,
                placement_positions=custom_positions if custom_positions else [],
                lighting_conditions=lighting_conditions,
                render_quality="high",
                style_consistency=True,
                user_style_description=user_style_description,
                exclusive_products=force_reset,  # When True, ONLY show specified products
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

        # CRITICAL FIX: For incremental visualizations, the frontend now manages undo/redo
        # locally and sends the complete product state. We trust the frontend's information
        # rather than trying to accumulate from backend history (which may be out of sync
        # after local undo/redo operations).
        #
        # The frontend sends:
        # - all_products: Complete list of ALL products currently in the scene (for history)
        # - products: The products to visualize in this request (may be subset for incremental)
        all_products_in_scene = request.get("all_products", products)  # Fallback to products if not provided
        delta_products = new_products_to_visualize if is_incremental else products

        if is_incremental:
            logger.info(
                f"Incremental mode: All products in scene: {len(all_products_in_scene)}, "
                f"Delta (new products to add): {len(delta_products)}"
            )
        else:
            logger.info(f"Standard mode: Visualizing {len(products)} products")

        # Use all_products_in_scene as the accumulated products (from frontend's source of truth)
        accumulated_products = all_products_in_scene

        visualization_data = {
            "rendered_image": viz_result.rendered_image,
            "products": accumulated_products,  # All products in scene (for frontend display)
            "delta_products": delta_products,  # Products added in THIS step (for accurate undo tracking)
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


def _extract_style_attributes_from_analysis(analysis: Any) -> Dict[str, List[str]]:
    """
    Extract style attributes from ChatGPT design analysis for product search.

    This extracts:
    - style_keywords: Primary and secondary style terms (e.g., "modern", "minimalist")
    - colors: User's color preferences from the room analysis
    - materials: User's material preferences (e.g., "wood", "leather")

    Args:
        analysis: DesignAnalysisSchema from ChatGPT

    Returns:
        Dict with 'style_keywords', 'colors', and 'materials' lists
    """
    style_keywords: List[str] = []
    colors: List[str] = []
    materials: List[str] = []

    if not analysis:
        return {"style_keywords": [], "colors": [], "materials": []}

    try:
        # Extract design_analysis dict
        design_analysis = None
        if hasattr(analysis, "design_analysis"):
            design_analysis = analysis.design_analysis
        elif isinstance(analysis, dict):
            design_analysis = analysis.get("design_analysis", {})

        if design_analysis and isinstance(design_analysis, dict):
            # Extract style preferences
            style_prefs = design_analysis.get("style_preferences", {})
            if isinstance(style_prefs, dict):
                primary_style = style_prefs.get("primary_style", "")
                if primary_style:
                    style_keywords.append(primary_style.lower())

                secondary_styles = style_prefs.get("secondary_styles", [])
                if isinstance(secondary_styles, list):
                    style_keywords.extend([s.lower() for s in secondary_styles if s])

                kw_list = style_prefs.get("style_keywords", [])
                if isinstance(kw_list, list):
                    style_keywords.extend([k.lower() for k in kw_list if k])

            # Extract color scheme preferences
            color_scheme = design_analysis.get("color_scheme", {})
            if isinstance(color_scheme, dict):
                preferred_colors = color_scheme.get("preferred_colors", [])
                if isinstance(preferred_colors, list):
                    colors.extend([c.lower() for c in preferred_colors if c])

                accent_colors = color_scheme.get("accent_colors", [])
                if isinstance(accent_colors, list):
                    colors.extend([c.lower() for c in accent_colors if c])

        # Extract product_matching_criteria for materials
        product_criteria = None
        if hasattr(analysis, "product_matching_criteria"):
            product_criteria = analysis.product_matching_criteria
        elif isinstance(analysis, dict):
            product_criteria = analysis.get("product_matching_criteria", {})

        if product_criteria and isinstance(product_criteria, dict):
            filtering = product_criteria.get("filtering_keywords", {})
            if isinstance(filtering, dict):
                material_prefs = filtering.get("material_preferences", [])
                if isinstance(material_prefs, list):
                    materials.extend([m.lower() for m in material_prefs if m])

        # Also check color_palette if present (hex codes won't help, but sometimes it has color names)
        color_palette = None
        if hasattr(analysis, "color_palette"):
            color_palette = analysis.color_palette
        elif isinstance(analysis, dict):
            color_palette = analysis.get("color_palette", [])

        # Note: color_palette often has hex codes, but sometimes color names slip through

        # Deduplicate while preserving order
        style_keywords = list(dict.fromkeys(style_keywords))
        colors = list(dict.fromkeys(colors))
        materials = list(dict.fromkeys(materials))

        logger.info(f"[STYLE EXTRACTION] Extracted - styles: {style_keywords}, colors: {colors}, materials: {materials}")

    except Exception as e:
        logger.warning(f"[STYLE EXTRACTION] Error extracting style attributes: {e}")

    return {
        "style_keywords": style_keywords,
        "colors": colors,
        "materials": materials,
    }


# =================================================================
# DIRECT SEARCH DETECTION
# =================================================================
# Keywords and patterns for detecting direct search queries
# that should bypass the guided conversation flow

# Color keywords to detect in user messages
COLOR_KEYWORDS = [
    "white",
    "black",
    "brown",
    "beige",
    "grey",
    "gray",
    "blue",
    "green",
    "red",
    "yellow",
    "orange",
    "pink",
    "purple",
    "cream",
    "ivory",
    "tan",
    "navy",
    "teal",
    "gold",
    "silver",
    "bronze",
    "copper",
    "walnut",
    "oak",
    "mahogany",
    "natural",
    "dark",
    "light",
    "neutral",
]

# Material keywords to detect in user messages
MATERIAL_KEYWORDS = [
    "wood",
    "wooden",
    "leather",
    "velvet",
    "fabric",
    "metal",
    "glass",
    "marble",
    "stone",
    "ceramic",
    "rattan",
    "wicker",
    "bamboo",
    "cotton",
    "linen",
    "silk",
    "wool",
    "jute",
    "cane",
    "plastic",
    "acrylic",
    "brass",
    "iron",
    "steel",
    "chrome",
    "upholstered",
    "teak",
    "sheesham",
]

# Size/quantity keywords
SIZE_KEYWORDS = [
    "large",
    "small",
    "big",
    "compact",
    "mini",
    "xl",
    "king",
    "queen",
    "single",
    "double",
    "twin",
    "3 seater",
    "three seater",
    "2 seater",
    "two seater",
    "4 seater",
    "four seater",
    "6 seater",
    "six seater",
]

# Style keywords to detect in user messages
STYLE_KEYWORDS_DIRECT = [
    "modern",
    "contemporary",
    "minimalist",
    "traditional",
    "classic",
    "rustic",
    "industrial",
    "scandinavian",
    "bohemian",
    "boho",
    "vintage",
    "retro",
    "mid-century",
    "luxurious",
    "luxury",
    "elegant",
    "simple",
    "ornate",
    "cozy",
    "warm",
    "sleek",
    "coastal",
    "farmhouse",
]


def _detect_direct_search_query(message: str) -> Dict[str, Any]:
    """
    Detect if a user message is a direct search query that should bypass
    the guided conversation flow.

    Examples of direct search queries:
    - "show me brown sofas"
    - "large rugs"
    - "modern coffee tables under 20000"
    - "leather armchairs"

    Returns:
        {
            "is_direct_search": bool,
            "detected_categories": [{"category_id": str, "display_name": str}, ...],
            "extracted_colors": ["brown", "beige", ...],
            "extracted_materials": ["leather", "wood", ...],
            "extracted_sizes": ["large", "3 seater", ...],
            "extracted_styles": ["modern", "minimalist", ...],
            "extracted_budget_max": int or None,
        }
    """
    message_lower = message.lower().strip()

    # Result structure
    result = {
        "is_direct_search": False,
        "detected_categories": [],
        "extracted_colors": [],
        "extracted_materials": [],
        "extracted_sizes": [],
        "extracted_styles": [],
        "extracted_budget_max": None,
    }

    # Skip very short messages or greetings
    greeting_patterns = ["hi", "hello", "hey", "help", "thank", "thanks", "okay", "ok", "yes", "no"]
    if len(message_lower) < 5 or message_lower in greeting_patterns:
        return result

    # Detect product categories
    # Using a local copy to avoid circular imports with CATEGORY_KEYWORDS defined later
    category_keywords_map = {
        "sofas": ["sofa", "couch", "sectional", "loveseat", "settee", "futon", "daybed"],
        "ottomans": ["ottoman", "pouf", "footstool"],
        "coffee_tables": ["coffee table", "center table", "cocktail table"],
        "side_tables": ["side table", "end table", "accent table", "occasional table"],
        "floor_lamps": ["floor lamp", "standing lamp", "arc lamp", "tripod lamp"],
        "table_lamps": ["table lamp", "desk lamp", "bedside lamp"],
        "ceiling_lights": [
            "ceiling light",
            "ceiling lights",
            "ceiling lamp",
            "ceiling lamps",
            "pendant light",
            "pendant lights",
            "pendant lamp",
            "pendant",
            "chandelier",
            "chandeliers",
            "hanging light",
            "hanging lamp",
            "overhead light",
        ],
        "wall_lights": ["wall light", "wall lights", "wall lamp", "wall lamps", "sconce", "wall sconce"],
        "accent_chairs": ["accent chair", "armchair", "club chair", "lounge chair", "wing chair", "chair"],
        "beds": ["bed", "bedframe", "headboard"],
        "nightstands": ["nightstand", "bedside table", "night table"],
        "dressers": ["dresser", "chest of drawers"],
        "wardrobes": ["wardrobe", "armoire", "closet"],
        "dining_tables": ["dining table", "dinner table", "kitchen table"],
        "dining_chairs": ["dining chair", "kitchen chair"],
        # Note: pendant_lamps removed - merged into ceiling_lights above
        "sideboards": ["sideboard", "buffet", "credenza", "console"],
        "desks": ["desk", "writing desk", "computer desk", "work table"],
        "office_chairs": ["office chair", "task chair", "ergonomic chair"],
        "study_tables": ["study table", "study desk", "student desk", "homework desk"],
        "study_chairs": ["study chair", "student chair", "homework chair"],
        "bookshelves": ["bookshelf", "bookcase", "shelving unit"],
        "storage_cabinets": ["storage cabinet", "cabinet", "cupboard"],
        "planters": ["planter", "plant pot", "flower pot", "plant stand"],
        "wall_art": ["wall art", "painting", "print", "poster", "canvas", "artwork", "frame"],
        "decor": ["decor", "sculpture", "figurine", "vase", "decorative", "ornament"],
        "rugs": ["rug", "carpet", "area rug", "dhurrie", "kilim", "floor rug"],
        "mats": ["mat", "floor mat", "door mat", "bath mat", "runner", "table runner"],
        "mirrors": ["mirror", "wall mirror", "floor mirror", "vanity mirror"],
        "cushions": ["cushion", "pillow", "throw pillow", "decorative pillow"],
        "throws": ["throw", "blanket", "throw blanket"],
    }

    # Check for category matches
    detected_cats = []
    for category_id, keywords in category_keywords_map.items():
        for keyword in keywords:
            if keyword in message_lower:
                display_name = category_id.replace("_", " ").title()
                detected_cats.append({"category_id": category_id, "display_name": display_name, "matched_keyword": keyword})
                break  # Only match once per category

    result["detected_categories"] = detected_cats

    # Collect matched keywords to avoid extracting them as qualifiers
    # e.g., "light" in "ceiling lights" should not be extracted as a color
    matched_category_keywords = set()
    for cat in detected_cats:
        keyword = cat.get("matched_keyword", "")
        if keyword:
            matched_category_keywords.update(keyword.split())

    # Extract colors (skip if part of detected category keyword)
    for color in COLOR_KEYWORDS:
        if color in message_lower:
            # Skip "light" if it's part of a lighting category keyword
            if color == "light" and "light" in matched_category_keywords:
                continue
            # Skip "dark" if it's part of a category keyword (e.g., future-proofing)
            if color in matched_category_keywords:
                continue
            result["extracted_colors"].append(color)

    # Extract materials
    for material in MATERIAL_KEYWORDS:
        if material in message_lower:
            result["extracted_materials"].append(material)

    # Extract sizes
    for size in SIZE_KEYWORDS:
        if size in message_lower:
            result["extracted_sizes"].append(size)

    # Extract styles
    for style in STYLE_KEYWORDS_DIRECT:
        if style in message_lower:
            result["extracted_styles"].append(style)

    # Extract budget (look for patterns like "under 20000", "below 50k", "budget 10000")
    import re

    budget_patterns = [
        r"under\s*(?:rs\.?|₹|inr)?\s*(\d+(?:,\d{3})*(?:k)?)",
        r"below\s*(?:rs\.?|₹|inr)?\s*(\d+(?:,\d{3})*(?:k)?)",
        r"budget\s*(?:of\s*)?(?:rs\.?|₹|inr)?\s*(\d+(?:,\d{3})*(?:k)?)",
        r"(?:rs\.?|₹|inr)\s*(\d+(?:,\d{3})*(?:k)?)\s*(?:max|maximum|or\s*less)",
        r"(\d+(?:,\d{3})*(?:k)?)\s*(?:rupees?|rs\.?|₹)\s*(?:max|maximum|or\s*less|budget)",
    ]

    for pattern in budget_patterns:
        match = re.search(pattern, message_lower)
        if match:
            budget_str = match.group(1).replace(",", "")
            # Handle 'k' suffix (e.g., "20k" = 20000)
            if budget_str.endswith("k"):
                result["extracted_budget_max"] = int(budget_str[:-1]) * 1000
            else:
                result["extracted_budget_max"] = int(budget_str)
            break

    # Determine if this is a direct search query
    # A message is considered a direct search if it contains at least one product category
    if len(detected_cats) > 0:
        result["is_direct_search"] = True

        # Check if we have SUFFICIENT info to search directly
        # We need: category + at least one qualifier (color, material, style, size, or budget)
        has_qualifiers = (
            len(result["extracted_colors"]) > 0
            or len(result["extracted_materials"]) > 0
            or len(result["extracted_styles"]) > 0
            or len(result["extracted_sizes"]) > 0
            or result["extracted_budget_max"] is not None
        )

        result["has_sufficient_info"] = has_qualifiers

        logger.info(
            f"[DIRECT SEARCH] Detected direct search: categories={[c['category_id'] for c in detected_cats]}, "
            f"colors={result['extracted_colors']}, materials={result['extracted_materials']}, "
            f"styles={result['extracted_styles']}, sizes={result['extracted_sizes']}, "
            f"budget_max={result['extracted_budget_max']}, has_sufficient_info={has_qualifiers}"
        )
    else:
        result["has_sufficient_info"] = False

    return result


def _build_direct_search_response_message(
    detected_categories: List[Dict], colors: List[str], materials: List[str], styles: List[str], product_count: int
) -> str:
    """
    Build a friendly response message for direct search results.
    """
    # Build a description of what was searched
    descriptors = []
    if colors:
        descriptors.append(colors[0])
    if materials:
        descriptors.append(materials[0])
    if styles:
        descriptors.append(styles[0])

    # Allow all categories (no limit) for multi-category searches
    category_names = [c["display_name"].lower() for c in detected_categories]

    # Build category string based on count
    if len(category_names) == 1:
        category_str = category_names[0]
    elif len(category_names) == 2:
        category_str = f"{category_names[0]} and {category_names[1]}"
    else:
        # For 3+ categories, use comma-separated list with "and" for last item
        category_str = ", ".join(category_names[:-1]) + f", and {category_names[-1]}"

    if descriptors:
        descriptor_str = " ".join(descriptors)
        if product_count > 0:
            return f"Here are my top {product_count} {descriptor_str} {category_str} picks for you! Take a look at the products panel to browse."
        else:
            return f"I couldn't find any {descriptor_str} {category_str} in our current inventory. Try adjusting your search or check back later!"
    else:
        if product_count > 0:
            return f"Found my top {product_count} {category_str} picks for you! Check out the products panel to explore your options."
        else:
            return f"I couldn't find any {category_str} matching your request. Try a different search or check back later!"


def _build_direct_search_followup_question(detected_categories: List[Dict]) -> str:
    """
    Build a follow-up question when user asks for categories without enough qualifiers.
    Handles both single and multiple categories with generic questions that apply to all.
    Example: User says "show me sofas and rugs" - we ask about style/color preferences for both.
    """
    category_names = [c["display_name"].lower() for c in detected_categories]

    # Build category string based on count
    if len(category_names) == 1:
        category_str = category_names[0]
    elif len(category_names) == 2:
        category_str = f"{category_names[0]} and {category_names[1]}"
    else:
        # For 3+ categories, use comma-separated list with "and" for last item
        category_str = ", ".join(category_names[:-1]) + f", and {category_names[-1]}"

    # Generic follow-up questions that work for any category combination
    questions = [
        f"Great choices! What style are you looking for - modern, traditional, minimalist, or something else?",
        f"I can help you find the perfect {category_str}! Any preference on colors or materials?",
        f"Looking for {category_str}! Do you have a specific style, color palette, or budget in mind?",
    ]

    # Pick based on first category character (deterministic but varied)
    idx = ord(category_names[0][0]) % len(questions)
    return questions[idx]


def _extract_furniture_type(product_name: str) -> str:
    """Extract furniture type from product name with specific table categorization"""
    name_lower = product_name.lower()

    # Check DECOR ITEMS FIRST (before table) to prevent "Table Top Figurine" being classified as table
    if "figurine" in name_lower or "figurines" in name_lower:
        return "figurine"
    elif "sculpture" in name_lower or "sculptures" in name_lower:
        return "sculpture"
    elif "statue" in name_lower or "statues" in name_lower:
        return "statue"
    elif "mirror" in name_lower:
        return "mirror"
    elif "planter" in name_lower or "pot" in name_lower or "vase" in name_lower:
        return "decor"
    # Check ottoman FIRST (before sofa) to handle "Sofa Ottoman" products correctly
    elif "ottoman" in name_lower:
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
        # Study furniture - maps to Study Tables and Study Chairs database categories
        ("study table", ["study table", "study tables", "desk", "writing desk"], {}),
        ("study tables", ["study table", "study tables", "desk", "writing desk"], {}),
        ("study chair", ["study chair", "study chairs", "office chair", "desk chair"], {}),
        ("study chairs", ["study chair", "study chairs", "office chair", "desk chair"], {}),
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

        # Get accumulated filters from conversation context (fallback mechanism)
        accumulated_filters = None
        if session_id:
            from services.conversation_context import conversation_context_manager

            accumulated_filters = conversation_context_manager.get_accumulated_filters(session_id)
            if accumulated_filters:
                logger.info(f"[CONTEXT] Loaded accumulated filters for session {session_id}: {accumulated_filters}")

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

        # CRITICAL FALLBACK: If no product keywords extracted from analysis, use keywords from user message
        # This ensures "show me sofas" returns sofas even when AI doesn't populate product_matching_criteria
        logger.info(
            f"[KEYWORD CHECK] Before fallback - user_preferences.product_keywords: {user_preferences.get('product_keywords', [])}, extracted: {product_keywords}"
        )
        if "product_keywords" not in user_preferences or not user_preferences["product_keywords"]:
            # Use the keywords extracted from user message at the start of this function
            if product_keywords:
                user_preferences["product_keywords"] = product_keywords
                logger.info(f"[KEYWORD FALLBACK] Applied extracted keywords: {product_keywords}")
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

        # ACCUMULATED CONTEXT FALLBACK: If still no product keywords, use accumulated filters from conversation context
        # This ensures context is carried forward even if AI doesn't properly populate product_matching_criteria
        if ("product_keywords" not in user_preferences or not user_preferences["product_keywords"]) and accumulated_filters:
            accumulated_product_types = accumulated_filters.get("product_types", [])
            accumulated_category = accumulated_filters.get("category")
            accumulated_search_terms = accumulated_filters.get("search_terms", [])

            # Build product keywords from accumulated context
            accumulated_keywords = []
            if accumulated_product_types:
                accumulated_keywords.extend(accumulated_product_types)
            if accumulated_category:
                accumulated_keywords.append(accumulated_category)
            if accumulated_search_terms:
                accumulated_keywords.extend(accumulated_search_terms)

            if accumulated_keywords:
                user_preferences["product_keywords"] = list(set(accumulated_keywords))
                logger.info(f"[CONTEXT FALLBACK] Applied accumulated filters as product keywords: {accumulated_keywords}")

        # Also merge accumulated style/color if not in AI response
        if accumulated_filters:
            if not style_preferences and accumulated_filters.get("style"):
                style_preferences.append(accumulated_filters["style"])
                logger.info(f"[CONTEXT FALLBACK] Applied accumulated style: {accumulated_filters['style']}")
            if not user_preferences.get("colors") and accumulated_filters.get("color"):
                user_preferences["colors"] = [accumulated_filters["color"]]
                logger.info(f"[CONTEXT FALLBACK] Applied accumulated color: {accumulated_filters['color']}")

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
                Product.is_available.is_(True),
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


# Category keyword mappings for product search
CATEGORY_KEYWORDS = {
    # Room-specific furniture
    "sofas": [
        "sofa",
        "couch",
        "sectional",
        "loveseat",
        "settee",
        "futon",
        "daybed",
        "3 seater",
        "three seater",
        "2 seater",
        "two seater",
    ],
    "ottomans": ["ottoman", "pouf", "footstool", "foot stool"],  # Separate category for ottomans
    "coffee_tables": ["coffee table", "center table", "cocktail table"],
    "side_tables": ["side table", "end table", "accent table", "occasional table", "lamp table"],
    "floor_lamps": ["floor lamp", "standing lamp", "arc lamp", "tripod lamp", "torchiere"],
    "table_lamps": ["table lamp", "desk lamp", "bedside lamp", "accent lamp"],
    "ceiling_lights": [
        "ceiling light",
        "ceiling lights",
        "ceiling lamp",
        "ceiling lamps",
        "pendant light",
        "pendant lights",
        "pendant lamp",
        "pendant",
        "chandelier",
        "chandeliers",
        "hanging light",
        "hanging lamp",
        "overhead light",
    ],
    "wall_lights": ["wall light", "wall lights", "wall lamp", "wall lamps", "sconce", "wall sconce"],
    "accent_chairs": ["accent chair", "armchair", "club chair", "lounge chair", "wing chair", "chair"],
    "beds": ["bed", "bedframe", "headboard", "king bed", "queen bed", "double bed"],
    "nightstands": ["nightstand", "bedside table", "night table"],
    "dressers": ["dresser", "chest of drawers", "bureau"],
    "wardrobes": ["wardrobe", "armoire", "closet"],
    "dining_tables": ["dining table", "dinner table", "kitchen table"],
    "dining_chairs": ["dining chair", "kitchen chair", "side chair"],
    # Note: pendant_lamps merged into ceiling_lights above
    "sideboards": ["sideboard", "buffet", "credenza", "console"],
    "desks": ["desk", "writing desk", "computer desk", "work table"],
    "office_chairs": ["office chair", "task chair", "ergonomic chair", "executive chair"],
    "study_tables": ["study table", "study desk", "student desk", "homework desk"],
    "study_chairs": ["study chair", "student chair", "homework chair"],
    "bookshelves": ["bookshelf", "bookcase", "shelving unit", "display shelf"],
    "storage_cabinets": ["storage cabinet", "cabinet", "cupboard", "hutch"],
    # Generic categories for ALL room types
    "planters": [
        "planter",
        "plant pot",
        "flower pot",
        "plant stand",
        "jardiniere",
        "indoor plant",
        "artificial plant",
        "faux plant",
    ],
    "wall_art": ["wall art", "painting", "print", "poster", "canvas", "artwork", "wall decor", "frame"],
    "decor": ["decor", "sculpture", "figurine", "vase", "decorative", "ornament", "statue", "object"],
    "rugs": ["rug", "carpet", "area rug", "dhurrie", "kilim", "floor rug"],
    "mats": [
        "mat",
        "floor mat",
        "door mat",
        "bath mat",
        "runner",
        "table runner",
        "runner cloth",
        "dining runner",
        "hallway runner",
    ],  # Mats and runners category
    "table_runners": [
        "table runner",
        "runner cloth",
        "dining runner",
    ],  # Separate category for table runners (kept for backwards compatibility)
    # Additional generic
    "mirrors": ["mirror", "wall mirror", "floor mirror", "vanity mirror"],
    "cushions": ["cushion", "pillow", "throw pillow", "decorative pillow"],
    "throws": ["throw", "blanket", "throw blanket"],
}

# Exclusion keywords - products containing these terms will be excluded from the category
CATEGORY_EXCLUSIONS = {
    "sofas": ["ottoman", "pouf", "footstool", "bench", "stool", "cover", "protector", "slipcover"],
    "planters": ["potpourri", "scented", "fragrance", "aroma", "diffuser", "candle", "incense"],
    "rugs": [
        "table runner",
        "runner cloth",
        "dining runner",
        "flower",
        "faux flower",
        "artificial flower",
        "stem",
        "bouquet",
        "potpourri",
        # Cushions and pillows should not appear in rug category
        "cushion",
        "cushion cover",
        "pillow",
        "pillow cover",
        "throw pillow",
    ],
    "decor": ["potpourri", "scented"],
}

# Priority keywords - products matching these terms will be sorted first
CATEGORY_PRIORITY_KEYWORDS = {
    "sofas": ["3 seater", "three seater", "l shape", "sectional", "corner"],  # Prioritize larger sofas
}


async def _get_category_based_recommendations(
    selected_categories: List[CategoryRecommendation],
    db: AsyncSession,
    selected_stores: Optional[List[str]] = None,
    limit_per_category: int = 50,
    style_attributes: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[dict]]:
    """
    Get product recommendations grouped by AI-selected categories.

    This function queries products for each category using keyword matching,
    applies optional budget and store filters, and returns products grouped by category.

    NEW: Also uses ChatGPT style attributes (colors, materials, style keywords) to
    prioritize products that match the user's design preferences.

    Args:
        selected_categories: List of CategoryRecommendation from ChatGPT analysis
        db: Database session
        selected_stores: Optional list of store names to filter by
        limit_per_category: Max products per category (default 50)
        style_attributes: Optional dict with style preferences from ChatGPT analysis
            - style_keywords: List of style terms (e.g., ["modern", "minimalist"])
            - colors: List of color preferences (e.g., ["beige", "gray", "neutral"])
            - materials: List of material preferences (e.g., ["wood", "leather", "velvet"])

    Returns:
        Dict mapping category_id to list of product dicts
    """
    import asyncio
    from typing import Dict

    from sqlalchemy import func, or_
    from sqlalchemy.orm import selectinload

    # Extract style attributes for product prioritization
    style_keywords = style_attributes.get("style_keywords", []) if style_attributes else []
    preferred_colors = style_attributes.get("colors", []) if style_attributes else []
    preferred_materials = style_attributes.get("materials", []) if style_attributes else []

    logger.info(f"[CATEGORY RECS] Getting recommendations for {len(selected_categories)} categories")
    logger.info(
        f"[CATEGORY RECS] Style attributes - keywords: {style_keywords}, colors: {preferred_colors}, materials: {preferred_materials}"
    )

    products_by_category: Dict[str, List[dict]] = {}

    async def fetch_category_products(category: CategoryRecommendation) -> Tuple[str, List[dict]]:
        """Fetch products for a single category"""
        try:
            category_id = category.category_id
            keywords = CATEGORY_KEYWORDS.get(category_id, [category_id.replace("_", " ")])
            exclusions = CATEGORY_EXCLUSIONS.get(category_id, [])
            priority_keywords = CATEGORY_PRIORITY_KEYWORDS.get(category_id, [])

            logger.info(f"[CATEGORY RECS] Fetching {category_id} with keywords: {keywords}, exclusions: {exclusions}")

            # Build keyword filter - match any keyword in product name OR category name
            keyword_conditions = []
            for keyword in keywords:
                # Match in product name
                keyword_conditions.append(Product.name.ilike(f"%{keyword}%"))
                # Also match in category name (to find products in "Study Tables" category)
                keyword_conditions.append(Category.name.ilike(f"%{keyword}%"))

            # Build exclusion filter - exclude products with these terms
            exclusion_conditions = []
            for exclusion in exclusions:
                exclusion_conditions.append(~Product.name.ilike(f"%{exclusion}%"))

            # Base query with eager loading (including attributes for style matching)
            # Join with Category to also filter by category name
            query = (
                select(Product)
                .join(Category, Product.category_id == Category.id, isouter=True)
                .options(selectinload(Product.images), selectinload(Product.attributes))
                .where(Product.is_available.is_(True), or_(*keyword_conditions) if keyword_conditions else True)
            )

            # Apply exclusion filters
            for excl_condition in exclusion_conditions:
                query = query.where(excl_condition)

            # Apply store filter if provided
            if selected_stores:
                query = query.where(Product.source_website.in_(selected_stores))

            # Apply budget filter if provided
            if category.budget_allocation:
                if category.budget_allocation.min > 0:
                    query = query.where(Product.price >= category.budget_allocation.min)
                if category.budget_allocation.max < 999999:
                    query = query.where(Product.price <= category.budget_allocation.max)

            # Don't limit in SQL - fetch ALL products in this category so we can score them all
            # This ensures we don't miss products with great style matches that happen to be pricier
            # The limit is applied AFTER scoring to get the best style-matched products
            result = await db.execute(query)
            products = result.scalars().all()

            logger.info(f"[CATEGORY RECS] {category_id}: Fetched {len(products)} candidate products for scoring")

            # =================================================================
            # STYLE MATCHING: Score products based on style attributes
            # Matches against: name, description, and ProductAttributes
            # =================================================================
            def calculate_style_score(product) -> float:
                """
                Calculate a style match score for a product (lower = better match).
                Checks name, description, and product attributes.
                """
                score = 100.0  # Base score (high = no match)

                # Build searchable text from product
                name_lower = (product.name or "").lower()
                desc_lower = (product.description or "").lower()

                # Extract attribute values for matching
                attr_style = ""
                attr_colors = ""
                attr_materials = ""
                attr_texture = ""

                if product.attributes:
                    for attr in product.attributes:
                        attr_name = (attr.attribute_name or "").lower()
                        attr_value = (attr.attribute_value or "").lower()

                        if attr_name == "style":
                            attr_style = attr_value
                        elif attr_name in ["color_primary", "color_secondary", "color"]:
                            attr_colors += f" {attr_value}"
                        elif attr_name in ["material_primary", "material_secondary", "material", "materials"]:
                            attr_materials += f" {attr_value}"
                        elif attr_name == "texture":
                            attr_texture = attr_value

                # Check category priority keywords first (highest priority)
                for idx, pk in enumerate(priority_keywords):
                    pk_lower = pk.lower()
                    if pk_lower in name_lower:
                        score = min(score, idx * 0.5)  # Very strong match
                        break

                # Check style keywords (e.g., "modern", "minimalist")
                for idx, sk in enumerate(style_keywords):
                    sk_lower = sk.lower()
                    # Check attribute style first (most accurate)
                    if sk_lower in attr_style:
                        score = min(score, 5 + idx * 0.5)
                    # Check name
                    elif sk_lower in name_lower:
                        score = min(score, 10 + idx * 0.5)
                    # Check description
                    elif sk_lower in desc_lower:
                        score = min(score, 15 + idx * 0.5)

                # Check color preferences
                for idx, color in enumerate(preferred_colors):
                    color_lower = color.lower()
                    # Check color attributes first (most accurate)
                    if color_lower in attr_colors:
                        score = min(score, 20 + idx * 0.5)
                    # Check name
                    elif color_lower in name_lower:
                        score = min(score, 25 + idx * 0.5)
                    # Check description
                    elif color_lower in desc_lower:
                        score = min(score, 30 + idx * 0.5)

                # Check material preferences
                for idx, material in enumerate(preferred_materials):
                    material_lower = material.lower()
                    # Check material attributes first (most accurate)
                    if material_lower in attr_materials or material_lower in attr_texture:
                        score = min(score, 35 + idx * 0.5)
                    # Check name
                    elif material_lower in name_lower:
                        score = min(score, 40 + idx * 0.5)
                    # Check description
                    elif material_lower in desc_lower:
                        score = min(score, 45 + idx * 0.5)

                return score

            # Score and sort products
            scored_products = []
            for product in products:
                style_score = calculate_style_score(product)
                scored_products.append((product, style_score))

            # Sort by style score (lower is better), then by price
            scored_products.sort(key=lambda x: (x[1], x[0].price or 0))

            # =================================================================
            # STRICT COLOR FILTER: If colors are specified, filter to only products
            # that actually contain the color in their name, description, or attributes
            # This ensures "red sofas" shows ONLY red sofas, not just red first
            # =================================================================
            if preferred_colors:

                def product_matches_color(product) -> bool:
                    """Check if product matches any of the preferred colors"""
                    name_lower = (product.name or "").lower()
                    desc_lower = (product.description or "").lower()

                    # Check product attributes for color
                    attr_colors = ""
                    if product.attributes:
                        for attr in product.attributes:
                            attr_name = (attr.attribute_name or "").lower()
                            if attr_name in ["color_primary", "color_secondary", "color", "color_accent"]:
                                attr_colors += f" {(attr.attribute_value or '').lower()}"

                    for color in preferred_colors:
                        color_lower = color.lower()
                        if color_lower in name_lower or color_lower in desc_lower or color_lower in attr_colors:
                            return True
                    return False

                color_matched = [(p, s) for p, s in scored_products if product_matches_color(p)]
                if color_matched:
                    logger.info(
                        f"[CATEGORY RECS] {category_id}: Strict color filter - {len(color_matched)} products match colors {preferred_colors}"
                    )
                    scored_products = color_matched
                else:
                    logger.info(
                        f"[CATEGORY RECS] {category_id}: No products match colors {preferred_colors}, showing all products"
                    )

            # Take only the limit we need
            top_products = scored_products[:limit_per_category]

            # Log style matching results
            if style_keywords or preferred_colors or preferred_materials:
                matched_count = sum(1 for _, score in top_products if score < 50)
                logger.info(
                    f"[CATEGORY RECS] {category_id}: {matched_count}/{len(top_products)} products matched style criteria"
                )

            # Convert to product dicts
            product_list = []
            for product, style_score in top_products:
                primary_image = None
                if product.images:
                    primary_image = next(
                        (img for img in product.images if img.is_primary), product.images[0] if product.images else None
                    )

                product_dict = {
                    "id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "currency": product.currency,
                    "brand": product.brand,
                    "source_website": product.source_website,
                    "source_url": product.source_url,
                    "is_on_sale": product.is_on_sale,
                    "style_score": style_score,  # Include score for debugging
                    "primary_image": {
                        "url": primary_image.original_url if primary_image else None,
                        "alt_text": primary_image.alt_text if primary_image else product.name,
                    }
                    if primary_image
                    else None,
                }
                product_list.append(product_dict)

            logger.info(f"[CATEGORY RECS] Found {len(product_list)} products for {category_id}")
            return category_id, product_list

        except Exception as e:
            logger.error(f"[CATEGORY RECS] Error fetching {category.category_id}: {e}")
            return category.category_id, []

    # Fetch all categories in parallel for better performance
    tasks = [fetch_category_products(cat) for cat in selected_categories]
    results = await asyncio.gather(*tasks)

    # Build result dict
    for category_id, products in results:
        products_by_category[category_id] = products

    # Log summary
    total_products = sum(len(prods) for prods in products_by_category.values())
    logger.info(f"[CATEGORY RECS] Total: {total_products} products across {len(products_by_category)} categories")

    return products_by_category


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
