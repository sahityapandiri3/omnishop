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
    PaginatedProductsRequest,
    PaginatedProductsResponse,
    PaginationCursor,
    StartSessionRequest,
    StartSessionResponse,
)
from services.budget_allocator import validate_and_adjust_budget_allocations
from services.chatgpt_service import chatgpt_service
from services.conversation_context import conversation_context_manager
from services.embedding_service import get_embedding_service
from services.google_ai_service import VisualizationRequest, VisualizationResult, google_ai_service
from services.ml_recommendation_model import ml_recommendation_model
from services.nlp_processor import design_nlp_processor
from services.ranking_service import get_ranking_service
from services.recommendation_engine import RecommendationRequest, recommendation_engine
from sqlalchemy import and_, case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from database.models import Category, ChatLog, ChatMessage, ChatSession, Product, UserPreferences
from utils.chat_logger import chat_logger

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


async def load_user_preferences_from_db(user_id: str, session_id: str, db: AsyncSession) -> None:
    """Load user preferences from database and populate conversation context"""
    if not user_id:
        return

    try:
        # Query user preferences from DB
        query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await db.execute(query)
        db_prefs = result.scalar_one_or_none()

        if db_prefs:
            # Update conversation context with preferences from DB
            conversation_context_manager.update_omni_preferences(
                session_id,
                scope=db_prefs.scope,
                preference_mode=db_prefs.preference_mode,
                target_category=db_prefs.target_category,
                room_type=db_prefs.room_type,
                usage=db_prefs.usage if db_prefs.usage else None,
                overall_style=db_prefs.overall_style,
                budget_total=float(db_prefs.budget_total) if db_prefs.budget_total else None,
                room_analysis_suggestions=db_prefs.room_analysis_suggestions,
            )

            # Load category preferences
            if db_prefs.category_preferences:
                for category, pref_data in db_prefs.category_preferences.items():
                    conversation_context_manager.update_omni_category_preference(
                        session_id,
                        category=category,
                        colors=pref_data.get("colors"),
                        materials=pref_data.get("materials"),
                        textures=pref_data.get("textures"),
                        style_override=pref_data.get("style_override"),
                        budget_allocation=pref_data.get("budget_allocation"),
                        source=pref_data.get("source", "omni"),
                    )

            logger.info(f"Loaded preferences from DB for user {user_id}")

    except Exception as e:
        logger.warning(f"Error loading user preferences from DB: {e}")


async def save_user_preferences_to_db(user_id: str, session_id: str, db: AsyncSession) -> None:
    """Save user preferences from conversation context to database"""
    if not user_id:
        return

    try:
        # Get preferences from conversation context
        prefs = conversation_context_manager.get_omni_preferences(session_id)

        # Query existing preferences
        query = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await db.execute(query)
        db_prefs = result.scalar_one_or_none()

        # Prepare category preferences dict
        category_prefs_dict = {}
        for cat, pref in prefs.category_preferences.items():
            category_prefs_dict[cat] = {
                "colors": pref.colors,
                "materials": pref.materials,
                "textures": pref.textures,
                "style_override": pref.style_override,
                "budget_allocation": pref.budget_allocation,
                "source": pref.source,
            }

        if db_prefs:
            # Update existing preferences
            db_prefs.scope = prefs.scope
            db_prefs.preference_mode = prefs.preference_mode
            db_prefs.target_category = prefs.target_category
            db_prefs.room_type = prefs.room_type
            db_prefs.usage = prefs.usage
            db_prefs.overall_style = prefs.overall_style
            db_prefs.budget_total = prefs.budget_total
            db_prefs.room_analysis_suggestions = (
                prefs.room_analysis_suggestions.to_dict() if prefs.room_analysis_suggestions else None
            )
            db_prefs.category_preferences = category_prefs_dict
            db_prefs.preferences_confirmed = prefs.preferences_confirmed
        else:
            # Create new preferences
            db_prefs = UserPreferences(
                user_id=user_id,
                scope=prefs.scope,
                preference_mode=prefs.preference_mode,
                target_category=prefs.target_category,
                room_type=prefs.room_type,
                usage=prefs.usage,
                overall_style=prefs.overall_style,
                budget_total=prefs.budget_total,
                room_analysis_suggestions=prefs.room_analysis_suggestions.to_dict()
                if prefs.room_analysis_suggestions
                else None,
                category_preferences=category_prefs_dict,
                preferences_confirmed=prefs.preferences_confirmed,
            )
            db.add(db_prefs)

        await db.commit()
        logger.info(f"Saved preferences to DB for user {user_id}")

    except Exception as e:
        logger.warning(f"Error saving user preferences to DB: {e}")


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

        # Load user preferences from DB if authenticated
        if request.user_id:
            await load_user_preferences_from_db(request.user_id, session_id, db)

        # Check if returning user with preferences
        is_returning = conversation_context_manager.is_returning_user(session_id)
        prefs = conversation_context_manager.get_omni_preferences(session_id)

        # Customize welcome message based on returning user status
        if is_returning and prefs.overall_style and prefs.budget_total:
            # Returning user with known preferences
            welcome_message = f"Welcome back! Last time we were working on your {prefs.overall_style} style space with a ₹{prefs.budget_total:,.0f} budget. Ready to continue, or would you like to start fresh?"
        elif is_returning and prefs.room_type:
            # Returning user with partial preferences
            welcome_message = f"Welcome back! I remember you were working on your {prefs.room_type}. Ready to continue?"
        else:
            # New user - Omni greeting
            welcome_message = "Hi! I'm Omni, your AI interior stylist. I'd love to help you transform your space. Upload a photo of your room, or tell me what you're looking for!"

        return StartSessionResponse(
            session_id=session_id,
            message=welcome_message,
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

        # Load user preferences from DB if not in memory (handles server restarts)
        # This ensures context is preserved even if in-memory cache was cleared
        if session.user_id and not conversation_context_manager.is_returning_user(session_id):
            await load_user_preferences_from_db(session.user_id, session_id, db)
            logger.info(f"[Context Reload] Loaded preferences from DB for session {session_id}")

        # Store image in conversation context if provided
        if request.image:
            conversation_context_manager.store_image(session_id, request.image)

        # Process onboarding preferences if provided
        if request.onboarding_preferences:
            prefs = request.onboarding_preferences
            logger.info(f"[Onboarding] Processing preferences for session {session_id}: {prefs}")

            # Store preferences in conversation context
            omni_prefs = conversation_context_manager.get_omni_preferences(session_id)

            # Set room type
            if prefs.roomType:
                omni_prefs.room_type = prefs.roomType

            # Set style preferences
            if prefs.primaryStyle:
                # Set BOTH overall_style (for essentials check) AND styles array (for search)
                overall_style = prefs.primaryStyle
                if prefs.secondaryStyle:
                    overall_style = f"{prefs.primaryStyle} with {prefs.secondaryStyle} touches"
                omni_prefs.overall_style = overall_style
                # Also set styles array for search filtering
                styles = [prefs.primaryStyle]
                if prefs.secondaryStyle:
                    styles.append(prefs.secondaryStyle)
                omni_prefs.styles = styles

            # Set budget - MUST set budget_total (for essentials check) AND budget (for filters)
            if prefs.budget and not prefs.budgetFlexible:
                omni_prefs.budget_total = prefs.budget  # Used by essentials check
                omni_prefs.budget = prefs.budget  # Used by search filters
            elif prefs.budgetFlexible:
                omni_prefs.budget = None  # Flexible = no budget filter for search
                # CRITICAL: Set budget_total to a marker value so essentials check passes
                # "Flexible" means user HAS given budget info (they said "no limit")
                # This is different from "no budget info provided" (None)
                omni_prefs.budget_total = -1  # Special marker: flexible/no limit

            # Store room image from onboarding if provided
            if prefs.roomImage:
                conversation_context_manager.store_image(session_id, prefs.roomImage)

            # Auto-set scope to "full_room" when user provided a room type in onboarding
            # User selecting "bedroom" or "living_room" implies they want to furnish the entire room
            # This prevents the AI from asking an unnecessary follow-up question
            if prefs.roomType:
                omni_prefs.scope = "full_room"
                logger.info(f"[Onboarding] Auto-set scope to 'full_room' based on room type: {prefs.roomType}")

            conversation_context_manager.store_omni_preferences(session_id, omni_prefs)
            logger.info(
                f"[Onboarding] Stored preferences: room={omni_prefs.room_type}, overall_style={omni_prefs.overall_style}, budget_total={omni_prefs.budget_total}, scope={omni_prefs.scope}"
            )

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

        # DISABLED: Pre-extract scope from user message
        # Per user requirement: The AI stylist MUST ask about scope (entire room vs specific category)
        # even when style and budget are provided from onboarding. Let GPT ask the question.
        # The scope should only be set when the user explicitly answers the scope question.
        message_lower = request.message.lower()
        current_prefs = conversation_context_manager.get_omni_preferences(session_id)

        # NOTE: Scope pre-extraction is DISABLED - AI must ask the user about scope
        # Per user requirement: The stylist must ask "entire room or specific category?"
        # The scope should only be set when the user explicitly answers the scope question.

        # Pre-extract room type from user message (this is still useful)
        if not current_prefs.room_type:
            room_type_keywords = {
                "living room": ["living room", "living space", "living area", "lounge"],
                "bedroom": ["bedroom", "master bedroom", "guest bedroom", "sleep room"],
                "dining room": ["dining room", "dining area", "dining space"],
                "office": ["office", "study", "home office", "workspace", "work space"],
                "kitchen": ["kitchen", "cooking area"],
                "bathroom": ["bathroom", "washroom", "restroom"],
                "balcony": ["balcony", "patio", "terrace", "outdoor"],
            }
            for room_type, keywords in room_type_keywords.items():
                if any(kw in message_lower for kw in keywords):
                    conversation_context_manager.update_omni_preferences(session_id, room_type=room_type)
                    logger.info(f"[Session {session_id}] Pre-extracted room_type: {room_type} from user message")
                    break

        conversational_response, analysis = await chatgpt_service.analyze_user_input(
            user_message=request.message,
            session_id=session_id,
            image_data=active_image or request.image,  # Use active image, fallback to request
        )

        # =================================================================
        # GPT INTENT DETECTION: Use GPT as single source of truth for intent
        # GPT returns: is_direct_search, detected_category, preference_mode, etc.
        # =================================================================
        gpt_is_direct_search = False
        gpt_detected_category = None
        gpt_preference_mode = None
        gpt_category_attributes = {}
        gpt_attributes_complete = False

        if analysis:
            # Extract intent detection fields from GPT response
            gpt_is_direct_search = getattr(analysis, "is_direct_search", False)
            gpt_detected_category = getattr(analysis, "detected_category", None)
            gpt_preference_mode = getattr(analysis, "preference_mode", None)
            gpt_category_attributes = getattr(analysis, "category_attributes", {}) or {}
            gpt_attributes_complete = getattr(analysis, "attributes_complete", False)

            # Update omni preferences with GPT's intent detection
            if gpt_is_direct_search or gpt_detected_category or gpt_preference_mode:
                conversation_context_manager.update_omni_preferences(
                    session_id,
                    is_direct_search=gpt_is_direct_search,
                    detected_category=gpt_detected_category,
                    preference_mode=gpt_preference_mode,
                    category_attributes=gpt_category_attributes if gpt_category_attributes else None,
                    attributes_complete=gpt_attributes_complete,
                )
                logger.info(
                    f"[GPT INTENT] Updated intent: is_direct_search={gpt_is_direct_search}, "
                    f"detected_category={gpt_detected_category}, preference_mode={gpt_preference_mode}, "
                    f"attributes_complete={gpt_attributes_complete}"
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
        # DIRECT SEARCH DETECTION: GPT is primary source, keyword detection is fallback
        # GPT returns is_direct_search, detected_category in analysis
        # Fallback to _detect_direct_search_query only if GPT doesn't set it
        # =================================================================

        # First, check if GPT detected a direct search
        is_direct_search = gpt_is_direct_search

        # Initialize direct_search_result with GPT's values or defaults
        direct_search_result = {
            "is_direct_search": gpt_is_direct_search,
            "detected_categories": [],
            "has_sufficient_info": gpt_attributes_complete,
            "extracted_colors": [],
            "extracted_styles": [],
            "extracted_materials": [],
            "extracted_sizes": [],
            "extracted_budget_max": None,
        }

        # If GPT detected a category, use it AND treat as direct search
        # GPT detecting a category means user is searching for something specific
        if gpt_detected_category:
            # Import simple categories check
            from config.category_attributes import is_simple_category, normalize_category_name

            normalized_cat = normalize_category_name(gpt_detected_category)
            is_simple = is_simple_category(normalized_cat)

            # IMPORTANT: GPT detecting a category implies direct search intent
            # Even if GPT returned is_direct_search=false, the user IS searching for a specific category
            is_direct_search = True
            direct_search_result["is_direct_search"] = True

            direct_search_result["detected_categories"] = [
                {
                    "category_id": normalized_cat,
                    "display_name": normalized_cat.replace("_", " ").title(),
                    "is_simple": is_simple,
                }
            ]

            # For simple categories, mark as having sufficient info (show immediately)
            if is_simple:
                direct_search_result["has_sufficient_info"] = True
                logger.info(f"[GPT INTENT] Simple category detected: {normalized_cat} - showing products immediately")

            logger.info(
                f"[GPT INTENT] GPT detected category: {normalized_cat}, is_simple={is_simple}, forcing is_direct_search=True"
            )

        # Fallback: If GPT didn't detect direct search, use keyword detection
        if not is_direct_search and not gpt_detected_category:
            keyword_search_result = _detect_direct_search_query(request.message)
            if keyword_search_result["is_direct_search"]:
                is_direct_search = True
                direct_search_result = keyword_search_result
                logger.info(
                    f"[FALLBACK] Keyword detection found direct search: {keyword_search_result.get('detected_categories', [])}"
                )
        elif is_direct_search:
            # GPT detected direct search - supplement with keyword extraction for colors/styles
            keyword_search_result = _detect_direct_search_query(request.message)
            # Merge extracted attributes from keyword detection
            direct_search_result["extracted_colors"] = keyword_search_result.get("extracted_colors", [])
            direct_search_result["extracted_styles"] = keyword_search_result.get("extracted_styles", [])
            direct_search_result["extracted_materials"] = keyword_search_result.get("extracted_materials", [])
            direct_search_result["extracted_sizes"] = keyword_search_result.get("extracted_sizes", [])
            direct_search_result["extracted_budget_max"] = keyword_search_result.get("extracted_budget_max")

            # CRITICAL: If keyword detection found qualifiers (color, style, material, etc.),
            # update has_sufficient_info so we show products instead of asking follow-up questions
            if keyword_search_result.get("has_sufficient_info"):
                direct_search_result["has_sufficient_info"] = True
                logger.info(f"[DIRECT SEARCH] Keyword detection found qualifiers - marking has_sufficient_info=True")

            # =================================================================
            # PERSIST EXTRACTED ATTRIBUTES: Store sizes/types in category_attributes
            # so they survive across messages (e.g., "sectional sofas" + "no preference")
            # =================================================================
            if direct_search_result.get("extracted_sizes"):
                # Map size keywords to proper attribute names
                size_attrs = {}
                for size in direct_search_result["extracted_sizes"]:
                    size_lower = size.lower()
                    # Sofa types: sectional, L-shaped
                    if size_lower in ["sectional", "l shaped", "l-shaped", "modular"]:
                        size_attrs["seating_type"] = size_lower.replace("-", " ")
                    # Seating capacity: 2 seater, 3 seater, etc.
                    elif "seater" in size_lower or size_lower in ["single", "double"]:
                        size_attrs["seating_capacity"] = size_lower
                    # Bed sizes: king, queen, single, double
                    elif size_lower in ["king", "queen", "twin", "single", "double"]:
                        size_attrs["size"] = size_lower
                    # General sizes: large, small, compact
                    elif size_lower in ["large", "small", "big", "compact", "mini", "xl"]:
                        size_attrs["size"] = size_lower

                if size_attrs:
                    conversation_context_manager.update_omni_preferences(
                        session_id,
                        category_attributes=size_attrs,
                    )
                    logger.info(f"[DIRECT SEARCH] Persisted size attributes: {size_attrs}")

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

                        # Check if user wants "all types" of a generic category (e.g., "any kind" of lighting)
                        message_lower_followup = request.message.lower().strip()
                        all_types_keywords = [
                            "any kind",
                            "all types",
                            "all of them",
                            "show me all",
                            "all",
                            "any",
                            "everything",
                            "all kinds",
                        ]
                        user_wants_all_types = any(kw in message_lower_followup for kw in all_types_keywords)

                        # Check if we have a generic category that should be expanded
                        if previous_direct_search_categories and user_wants_all_types:
                            expanded_categories = []
                            for cat in previous_direct_search_categories:
                                if cat.get("is_generic") and cat.get("subcategories"):
                                    # Expand generic category to all subcategories
                                    subcategories = cat.get("subcategories", [])
                                    for sub_id in subcategories:
                                        expanded_categories.append(
                                            {
                                                "category_id": sub_id,
                                                "display_name": sub_id.replace("_", " ").title(),
                                            }
                                        )
                                    logger.info(
                                        f"[GENERIC CATEGORY] Expanded '{cat['category_id']}' to {len(subcategories)} subcategories: {subcategories}"
                                    )
                                else:
                                    expanded_categories.append(cat)

                            if expanded_categories:
                                previous_direct_search_categories = expanded_categories
                                logger.info(
                                    f"[GENERIC CATEGORY] Final categories after expansion: {[c['category_id'] for c in expanded_categories]}"
                                )

                        if previous_direct_search_categories:
                            # User is providing follow-up info - treat current message as qualifiers
                            # Re-run detection but force it to be a direct search with ALL previous categories
                            is_direct_search = True
                            direct_search_result["is_direct_search"] = True
                            direct_search_result["detected_categories"] = previous_direct_search_categories
                            # IMPORTANT: Clear is_simple flag from inherited categories
                            # When we're in DIRECT_SEARCH_GATHERING follow-up, we've already decided to gather info
                            # so we shouldn't let is_simple bypass the gathering process
                            for cat in direct_search_result["detected_categories"]:
                                cat["is_simple"] = False
                            # DON'T mark as sufficient yet - we'll determine this after extracting qualifiers
                            # We need BOTH style AND budget before showing products
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

                            # CRITICAL: Determine if we have SUFFICIENT info to show products
                            # For direct search gathering, we want BOTH style AND budget before showing products
                            # Check what we have accumulated from Omni preferences + current message
                            omni_prefs_check = conversation_context_manager.get_omni_preferences(session_id)
                            has_style = bool(
                                direct_search_result.get("extracted_styles")
                                or direct_search_result.get("extracted_colors")
                                or omni_prefs_check.overall_style
                            )
                            has_budget = bool(extracted_budget or omni_prefs_check.budget_total)

                            # Check if user is declining to provide more info
                            decline_keywords = [
                                "any",
                                "no preference",
                                "don't care",
                                "doesn't matter",
                                "you choose",
                                "surprise me",
                                "whatever",
                            ]
                            user_declines = any(kw in message_lower for kw in decline_keywords)

                            if has_style and has_budget:
                                direct_search_result["has_sufficient_info"] = True
                                logger.info(
                                    f"[DIRECT SEARCH FOLLOW-UP] Has style AND budget - sufficient info, will show products"
                                )
                            elif user_declines:
                                direct_search_result["has_sufficient_info"] = True
                                logger.info(
                                    f"[DIRECT SEARCH FOLLOW-UP] User declined preferences - sufficient info, will show products"
                                )
                            else:
                                direct_search_result["has_sufficient_info"] = False
                                missing = []
                                if not has_style:
                                    missing.append("style")
                                if not has_budget:
                                    missing.append("budget")
                                logger.info(f"[DIRECT SEARCH FOLLOW-UP] Still missing: {missing} - will continue gathering")

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
                        price_str = price_match.group(1).replace(",", "").replace(" ", "")
                        if price_str:  # Only convert if not empty
                            direct_search_result["extracted_budget_max"] = int(price_str)

                    logger.info(
                        f"[ACCUMULATED CONTEXT] Converted to direct search: categories={[c['category_id'] for c in direct_search_result['detected_categories']]}, "
                        f"colors={direct_search_result.get('extracted_colors', [])}, styles={direct_search_result.get('extracted_styles', [])}"
                    )

        # Determine early conversation state
        # Priority: GPT's conversation_state > direct search detection > message count based
        early_conversation_state = "INITIAL"

        # First priority: Use GPT's conversation_state if it returned one
        gpt_conversation_state = None
        if analysis:
            gpt_conversation_state = getattr(analysis, "conversation_state", None)

        # PRIORITY: Check for direct search FIRST, before accepting GPT's conversation state
        # This ensures "suggest lounge chairs" triggers product display even if GPT returns "INITIAL"
        if is_direct_search:
            # Check if we have sufficient info or it's a simple category
            has_sufficient = direct_search_result.get("has_sufficient_info", False)
            detected_cats = direct_search_result.get("detected_categories", [])
            is_simple = any(cat.get("is_simple", False) for cat in detected_cats) if detected_cats else False

            if has_sufficient or is_simple:
                early_conversation_state = "READY_TO_RECOMMEND"
                logger.info(f"[DIRECT SEARCH] Simple category or has sufficient info - setting READY_TO_RECOMMEND")
            else:
                early_conversation_state = "DIRECT_SEARCH_GATHERING"
                logger.info(f"[DIRECT SEARCH] Complex category - need to gather preferences")
        elif gpt_conversation_state and gpt_conversation_state in [
            "READY_TO_RECOMMEND",
            "BROWSING",
            "DIRECT_SEARCH",  # Map to READY_TO_RECOMMEND below
            "DIRECT_SEARCH_GATHERING",
        ]:
            # GPT explicitly returned a product-showing state - use it
            # Map DIRECT_SEARCH to READY_TO_RECOMMEND for consistency
            if gpt_conversation_state == "DIRECT_SEARCH":
                early_conversation_state = "READY_TO_RECOMMEND"
            else:
                early_conversation_state = gpt_conversation_state
            logger.info(
                f"[GPT STATE] Using conversation_state: {early_conversation_state} (GPT returned: {gpt_conversation_state})"
            )
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

            # Get product recommendations if in READY_TO_RECOMMEND state
            # This prevents showing products during the guided conversation gathering phase
            if early_conversation_state in ["READY_TO_RECOMMEND", "BROWSING"]:
                logger.info("[GUIDED FLOW] In READY_TO_RECOMMEND state - fetching products")
                if analysis:
                    recommended_products = await _get_product_recommendations(
                        analysis,
                        db,
                        user_message=request.message,
                        limit=100,
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
                            limit=100,
                            user_id=session.user_id,
                            session_id=session_id,
                            selected_stores=request.selected_stores,
                        )
                    else:
                        # No keywords found, fall back to random products
                        logger.warning("No keywords extracted, using basic random recommendations")
                        recommended_products = await _get_basic_product_recommendations(fallback_analysis, db, limit=100)
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

            # Get product from DB with images AND attributes (for color extraction)
            product_query = (
                select(Product)
                .options(selectinload(Product.images), selectinload(Product.attributes))
                .where(Product.id == int(request.selected_product_id))
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

            # Extract color from product attributes for visualization accuracy
            product_color = None
            if product.attributes:
                for attr in product.attributes:
                    if attr.attribute_name.lower() == "color":
                        product_color = attr.attribute_value
                        break
            logger.info(f"Product color for visualization: {product_color}")

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
            # Build product name with color for better visualization accuracy
            product_name_with_color = product.name
            if product_color:
                product_name_with_color = f"{product_color} {product.name}"
                logger.info(f"Using color-enhanced product name: {product_name_with_color}")

            try:
                if request.user_action == "add":
                    logger.info(f"Generating ADD visualization for {product_name_with_color}")
                    visualization_image = await google_ai_service.generate_add_visualization(
                        room_image=room_image,
                        product_name=product_name_with_color,
                        product_image=product_image_url,
                        product_color=product_color,
                    )
                elif request.user_action == "replace":
                    logger.info(f"Generating REPLACE visualization for {product_name_with_color} (replacing {furniture_type})")
                    visualization_image = await google_ai_service.generate_replace_visualization(
                        room_image=room_image,
                        product_name=product_name_with_color,
                        furniture_type=furniture_type,
                        product_image=product_image_url,
                        product_color=product_color,
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
                    limit=100,
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
            # OMNI SMART FLOW: Check if Omni already has essentials
            # Essentials = style + budget + scope (all three required before showing products)
            # =================================================================
            omni_prefs = conversation_context_manager.get_omni_preferences(session_id)
            omni_has_essentials = bool(omni_prefs.overall_style and omni_prefs.budget_total and omni_prefs.scope)
            gpt_ready_to_recommend = analysis.conversation_state == "READY_TO_RECOMMEND" if analysis else False
            logger.info(
                f"[OMNI ESSENTIALS] style='{omni_prefs.overall_style}', budget='{omni_prefs.budget_total}', scope='{omni_prefs.scope}' -> has_essentials={omni_has_essentials}"
            )

            # =================================================================
            # DIRECT SEARCH BYPASS: Skip guided flow for direct product searches
            # =================================================================
            if is_direct_search:
                has_sufficient_info = direct_search_result.get("has_sufficient_info", False)
                is_generic_category = direct_search_result.get("is_generic_category", False)

                # For direct search, we only need style OR budget from context (not all three essentials)
                # The scope is implicit in the specific category request itself
                omni_has_context = bool(omni_prefs.overall_style or omni_prefs.budget_total)

                # GENERIC CATEGORY CHECK: If user asks for generic category like "lighting",
                # ALWAYS ask for subcategory preference, even if they have style/budget
                # This ensures we ask "floor lamps, table lamps, or ceiling lights?" first
                if is_generic_category:
                    has_sufficient_info = False
                    logger.info(
                        f"[GENERIC CATEGORY] Detected generic category - will ask for subcategory preference before showing products"
                    )
                # OMNI CONTEXT: If Omni already has style OR budget, treat direct search as having sufficient info
                # This allows "show me wall art" to work when user already provided style/budget earlier
                # Direct searches don't need scope - the specific category IS the scope
                elif not has_sufficient_info and omni_has_context:
                    has_sufficient_info = True
                    logger.info(
                        f"[DIRECT SEARCH] Omni has context (style='{omni_prefs.overall_style}', budget='{omni_prefs.budget_total}') - treating as sufficient info"
                    )

                if has_sufficient_info:
                    # User provided enough info (category + qualifier) - ready to show products
                    conversation_state = "READY_TO_RECOMMEND"
                    follow_up_question = None
                    logger.info(f"[DIRECT SEARCH] Sufficient info - setting READY_TO_RECOMMEND")

                    # Build categories from detected categories
                    raw_categories = []
                    for idx, cat_data in enumerate(direct_search_result["detected_categories"]):
                        # Use Omni's budget if available, otherwise use extracted budget from message
                        budget_max = direct_search_result["extracted_budget_max"]
                        if not budget_max and omni_has_essentials and omni_prefs.budget_total:
                            budget_max = int(omni_prefs.budget_total)
                        budget_max = budget_max or 999999
                        raw_categories.append(
                            {
                                "category_id": cat_data["category_id"],
                                "display_name": cat_data["display_name"],
                                "priority": idx + 1,
                                "budget_allocation": {"min": 0, "max": budget_max},
                            }
                        )

                    logger.info(
                        f"[DIRECT SEARCH] Built {len(raw_categories)} categories from user query (budget_max: ₹{budget_max:,})"
                    )
                else:
                    # User mentioned a category but no qualifiers - ask follow-up
                    conversation_state = "DIRECT_SEARCH_GATHERING"

                    # IMPORTANT: Still populate raw_categories so frontend knows the target category
                    # This allows the category to be displayed even while gathering preferences
                    raw_categories = []
                    for idx, cat_data in enumerate(direct_search_result["detected_categories"]):
                        # Use default budget until user provides one
                        raw_categories.append(
                            {
                                "category_id": cat_data["category_id"],
                                "display_name": cat_data["display_name"],
                                "priority": idx + 1,
                                "budget_allocation": {"min": 0, "max": 999999},  # No budget filter yet
                            }
                        )
                    logger.info(f"[DIRECT SEARCH GATHERING] Built {len(raw_categories)} categories for gathering state")

                    # Check if this is a generic category (like "lighting" → needs "what kind?" question)
                    if direct_search_result.get("is_generic_category"):
                        generic_info = direct_search_result.get("generic_category_info", {})
                        follow_up_question = generic_info.get(
                            "follow_up_question",
                            _build_direct_search_followup_question(direct_search_result["detected_categories"]),
                        )
                        logger.info(f"[GENERIC CATEGORY] Asking: {follow_up_question[:50]}...")
                    else:
                        follow_up_question = _build_direct_search_followup_question(
                            direct_search_result["detected_categories"]
                        )

                    logger.info(f"[DIRECT SEARCH] Set conversation_state=DIRECT_SEARCH_GATHERING (insufficient info)")
                    logger.info(f"[DIRECT SEARCH] Follow-up question: {follow_up_question[:50]}...")

            # If Omni has style + budget, go directly to READY_TO_RECOMMEND (skip gathering questions)
            # This allows users who provide all info upfront to get recommendations immediately
            elif omni_has_essentials:
                conversation_state = "READY_TO_RECOMMEND"
                follow_up_question = None
                logger.info(
                    f"[OMNI SMART FLOW] Style '{omni_prefs.overall_style}' + budget '₹{omni_prefs.budget_total:,.0f}' known - skipping gathering, going to READY_TO_RECOMMEND"
                )
            # =================================================================
            # STRUCTURED FIELD CHECK: If GPT detected a category, consider showing products
            # Skip gathering if user already provided style OR budget (context is sufficient)
            # =================================================================
            gpt_has_category = bool(gpt_detected_category) or bool(analysis and getattr(analysis, "detected_category", None))
            gpt_signals_products = (
                gpt_has_category or gpt_is_direct_search or (analysis and getattr(analysis, "is_direct_search", False))
            )
            # Check if we have enough context to skip gathering
            # Require BOTH style AND budget before skipping gathering
            omni_has_context = bool(omni_prefs.overall_style and omni_prefs.budget_total)

            # =================================================================
            # USER DECLINES PREFERENCES: Detect when user says they have no style/budget
            # Patterns: "no style", "no budget", "any style", "don't have", "you choose", "surprise me"
            # When detected, skip gathering and show products without filters
            # =================================================================
            message_lower = request.message.lower()
            user_declines_preferences = any(
                phrase in message_lower
                for phrase in [
                    "no style",
                    "no budget",
                    "any style",
                    "any budget",
                    "don't have",
                    "dont have",
                    "no preference",
                    "no preferences",
                    "you choose",
                    "you decide",
                    "surprise me",
                    "anything",
                    "whatever you",
                    "up to you",
                    "your choice",
                    "omni choose",
                    "no particular",
                    "not particular",
                    "open to",
                    "flexible",
                    # User asking for suggestions = delegating choice to Omni
                    "suggest option",
                    "suggest some",
                    "show me option",
                    "show me some",
                    "just show",
                    "recommend some",
                    "recommend option",
                    "go ahead",
                    "yes please",
                    "yes, please",
                    "sure",
                    "sounds good",
                    "let's go",
                    "lets go",
                ]
            )

            if user_declines_preferences:
                logger.info(
                    f"[USER DECLINES] User declined to provide preferences: '{request.message[:50]}' - setting omni_decides mode"
                )
                # Set preference_mode to "omni_decides" so Omni picks based on room analysis
                # NOTE: DO NOT set scope here - let the AI ask "entire room or specific category?"
                conversation_context_manager.update_omni_preferences(session_id, preference_mode="omni_decides")
                # IMPORTANT: Set to GATHERING_SCOPE so AI asks about scope before showing products
                # User requirement: AI must ask "Would you like me to help with the entire room or something specific?"
                conversation_state = "GATHERING_SCOPE"
                # Let GPT generate the scope question - don't override it
                logger.info(f"[USER DECLINES] Set state to GATHERING_SCOPE - AI will ask about scope")

            # =================================================================
            # SCOPE DETECTION: Detect when user specifies scope (entire room vs specific)
            # This persists the scope so the system knows what user wants
            # =================================================================
            user_wants_full_room = any(
                phrase in message_lower
                for phrase in [
                    "entire room",
                    "full room",
                    "whole room",
                    "the room",
                    "style the room",
                    "style my room",
                    "design my room",
                    "designing my room",
                    "everything",
                    "all of it",
                    "the whole",
                    "complete room",
                    "entire space",
                    "full space",
                    "whole space",
                    # Phrases that imply full room styling
                    "help me find furniture",
                    "find furniture",
                    "help me style",
                    "help me design",
                    "need furniture",
                    "looking for furniture",
                    "want furniture",
                    "show me furniture",
                    "furniture for my",
                    "furnish my",
                    "furnishing my",
                ]
            )

            if user_wants_full_room and not omni_prefs.scope:
                logger.info(f"[SCOPE DETECTION] User wants full room: '{request.message[:50]}' - setting scope=full_room")
                conversation_context_manager.update_omni_preferences(session_id, scope="full_room")
                omni_prefs.scope = "full_room"  # Update local reference
                # Recalculate essentials with new scope
                omni_has_essentials = bool(omni_prefs.overall_style and omni_prefs.budget_total and omni_prefs.scope)

            # Only respect gathering states if we DON'T have style/budget context
            # If user already told us their style/budget, show products instead of asking more questions
            gpt_wants_to_gather = conversation_state in [
                "GATHERING_USAGE",
                "GATHERING_STYLE",
                "GATHERING_BUDGET",
                "GATHERING_SCOPE",
                "GATHERING_PREFERENCE_MODE",
                "GATHERING_ATTRIBUTES",
                "DIRECT_SEARCH_GATHERING",
            ]
            should_skip_gathering = omni_has_context and gpt_has_category

            if (
                gpt_signals_products
                and (not gpt_wants_to_gather or should_skip_gathering)
                and conversation_state not in ["READY_TO_RECOMMEND", "BROWSING"]
            ):
                # Only go to READY_TO_RECOMMEND if we have ALL essentials including scope
                if omni_prefs.scope:
                    logger.info(
                        f"[STRUCTURED CHECK] GPT detected category='{gpt_detected_category}', has_context={omni_has_context}, has_scope='{omni_prefs.scope}' - forcing READY_TO_RECOMMEND"
                    )
                    conversation_state = "READY_TO_RECOMMEND"
                    follow_up_question = None
                else:
                    # Missing scope - don't auto-set, let it fall through to GATHERING_SCOPE
                    logger.info(
                        f"[STRUCTURED CHECK] GPT detected category but scope is missing - NOT forcing READY_TO_RECOMMEND, will ask for scope"
                    )

            # =================================================================
            # GPT READY_TO_RECOMMEND TRUST: Only trust GPT if ALL essentials are set
            # GPT often returns READY_TO_RECOMMEND too early - we must verify
            # that style, budget, AND scope are known before showing products
            # =================================================================
            elif gpt_ready_to_recommend:
                # Check if we have ALL essentials (style AND budget AND scope)
                has_style = bool(omni_prefs.overall_style)
                has_budget = bool(omni_prefs.budget_total)
                has_scope = bool(omni_prefs.scope)
                user_declined = omni_prefs.preference_mode == "omni_decides"

                # IMPORTANT: Scope is ALWAYS required, even when user declined preferences
                # User requirement: AI must ask "entire room or specific category?" before showing products
                if has_scope and ((has_style and has_budget) or user_declined):
                    # We have scope AND (all essentials OR user declined for style/budget) - trust GPT
                    conversation_state = "READY_TO_RECOMMEND"
                    follow_up_question = None
                    logger.info(
                        f"[GPT TRUST] Trusting GPT's READY_TO_RECOMMEND (style='{omni_prefs.overall_style}', budget='{omni_prefs.budget_total}', scope='{omni_prefs.scope}', declined={user_declined})"
                    )
                else:
                    # GPT says ready but we don't have ALL essentials - DON'T trust, fall through to gathering
                    logger.info(
                        f"[GPT OVERRIDE] GPT returned READY_TO_RECOMMEND but missing essentials (style={has_style}, budget={has_budget}, scope={has_scope}) - falling through to gathering flow"
                    )
                    # Don't set conversation_state here - let it fall through to message-count logic below
            # =================================================================
            # OMNI NATURAL FLOW: Let GPT's warm responses come through
            # We track state for internal logic, but DON'T override GPT's follow_up_question
            # GPT's Omni persona generates context-aware, friendly questions naturally
            # IMPORTANT: Skip this if we already have a direct search state set above!
            # =================================================================
            elif conversation_state == "DIRECT_SEARCH_GATHERING":
                # Direct search gathering state was already set - preserve it, don't override with message-count logic
                logger.info(
                    f"[DIRECT SEARCH PRESERVED] Keeping conversation_state=DIRECT_SEARCH_GATHERING (not overriding with message-count logic)"
                )
            elif conversation_state == "READY_TO_RECOMMEND":
                # State was already set to READY_TO_RECOMMEND (e.g., user declined preferences) - preserve it
                logger.info(
                    f"[READY_TO_RECOMMEND PRESERVED] Keeping conversation_state=READY_TO_RECOMMEND (not overriding with message-count logic)"
                )
            # =================================================================
            # CRITICAL FIX: Check for onboarding preferences BEFORE message-count logic
            # If user provided style+budget in onboarding but NOT scope, ask for scope
            # regardless of message count. This prevents re-asking style/budget.
            # =================================================================
            elif omni_prefs.overall_style and omni_prefs.budget_total and not omni_prefs.scope:
                # User completed onboarding with style+budget, but scope is unknown
                # Force GATHERING_SCOPE to ask "entire room or specific item?"
                conversation_state = "GATHERING_SCOPE"
                logger.info(
                    f"[ONBOARDING SCOPE] Style='{omni_prefs.overall_style}', Budget='{omni_prefs.budget_total}' from onboarding, but scope is UNKNOWN - forcing GATHERING_SCOPE"
                )
            elif user_message_count == 1:
                conversation_state = "GATHERING_USAGE"
                # DON'T override follow_up_question - let GPT's Omni response come through
                logger.info(
                    f"[OMNI FLOW] State: GATHERING_USAGE (message 1), GPT follow_up: {follow_up_question[:50] if follow_up_question else 'None'}..."
                )
            elif user_message_count == 2:
                conversation_state = "GATHERING_STYLE"
                logger.info(
                    f"[OMNI FLOW] State: GATHERING_STYLE (message 2), GPT follow_up: {follow_up_question[:50] if follow_up_question else 'None'}..."
                )
            elif user_message_count == 3:
                conversation_state = "GATHERING_BUDGET"
                logger.info(
                    f"[OMNI FLOW] State: GATHERING_BUDGET (message 3), GPT follow_up: {follow_up_question[:50] if follow_up_question else 'None'}..."
                )
            else:
                # Message 4+: Check if we have all essentials (style, budget, scope) before recommending
                # If scope is missing, stay in GATHERING_SCOPE state
                if omni_prefs.scope:
                    conversation_state = "READY_TO_RECOMMEND"
                    # Only clear follow_up when we're ready to show products
                    follow_up_question = None
                    logger.info(
                        f"[OMNI FLOW] State: READY_TO_RECOMMEND (message {user_message_count}, scope='{omni_prefs.scope}')"
                    )
                else:
                    conversation_state = "GATHERING_SCOPE"
                    logger.info(
                        f"[OMNI FLOW] State: GATHERING_SCOPE (message {user_message_count}, scope is missing - waiting for user to specify)"
                    )

            # =================================================================
            # CATEGORY GENERATION: Generate defaults for READY_TO_RECOMMEND
            # This runs for BOTH Omni smart flow and message-count-based flow
            # Priority: 1) Accumulated product_types from conversation, 2) Default room categories
            # =================================================================
            if conversation_state == "READY_TO_RECOMMEND" and (not raw_categories or len(raw_categories) == 0):
                # First check if we have accumulated product_types from earlier in conversation
                acc_filters = conversation_context_manager.get_accumulated_filters(session_id)
                accumulated_product_types = acc_filters.get("product_types", []) if acc_filters else []

                if accumulated_product_types:
                    # Use accumulated product types to generate specific categories
                    logger.info(f"[CATEGORY GEN] Using accumulated product_types: {accumulated_product_types}")
                    raw_categories = []

                    # Map product types to category IDs
                    product_type_to_category = {
                        "sofa": "sofas",
                        "sofas": "sofas",
                        "l-shaped sofa": "sofas",
                        "sectional": "sofas",
                        "chair": "accent_chairs",
                        "chairs": "accent_chairs",
                        "lounge chair": "accent_chairs",
                        "accent chair": "accent_chairs",
                        "armchair": "accent_chairs",
                        "table": "coffee_tables",
                        "coffee table": "coffee_tables",
                        "side table": "side_tables",
                        "dining table": "dining_tables",
                        "console table": "console_tables",
                        "bed": "beds",
                        "beds": "beds",
                        "lamp": "floor_lamps",
                        "floor lamp": "floor_lamps",
                        "table lamp": "table_lamps",
                        "rug": "rugs",
                        "rugs": "rugs",
                        "carpet": "rugs",
                        "decor": "decor_objects",
                        "vase": "decor_objects",
                        "planter": "planters",
                        "wall art": "wall_art",
                        "painting": "wall_art",
                        "artwork": "wall_art",
                        "mirror": "mirrors",
                        "mirrors": "mirrors",
                        "curtain": "curtains",
                        "curtains": "curtains",
                        "drapes": "curtains",
                        "bookshelf": "bookcases",
                        "shelf": "bookcases",
                        "storage": "bookcases",
                    }

                    seen_categories = set()
                    for idx, ptype in enumerate(accumulated_product_types):
                        ptype_lower = ptype.lower()
                        # Try exact match first, then partial match
                        cat_id = product_type_to_category.get(ptype_lower)
                        if not cat_id:
                            # Try partial matching
                            for key, value in product_type_to_category.items():
                                if key in ptype_lower or ptype_lower in key:
                                    cat_id = value
                                    break

                        if cat_id and cat_id not in seen_categories:
                            seen_categories.add(cat_id)
                            raw_categories.append(
                                {
                                    "category_id": cat_id,
                                    "display_name": ptype.title(),  # Use original name for display
                                    "priority": idx + 1,
                                    "budget_allocation": None,  # No budget filter
                                }
                            )

                    if raw_categories:
                        logger.info(
                            f"[CATEGORY GEN] Generated {len(raw_categories)} categories from accumulated product_types"
                        )

                # Fall back to room-based defaults if no accumulated product types
                if not raw_categories:
                    # Determine room type from: 1) current message, 2) stored Omni preferences, 3) conversation history
                    room_context = request.message.lower()

                    # If current message doesn't contain room info, check stored preferences
                    if not any(
                        kw in room_context for kw in ["living", "bed", "sleep", "dining", "eat", "office", "study", "sofa"]
                    ):
                        # Use stored room type from conversation context
                        if omni_prefs.room_type:
                            room_context = omni_prefs.room_type.lower()
                            logger.info(f"[CATEGORY GEN] Using stored room_type from Omni preferences: {room_context}")
                        else:
                            # Default to living room if no room type is available
                            room_context = "living room"
                            logger.info(f"[CATEGORY GEN] No room type found, defaulting to: {room_context}")

                    # Only generate room-based defaults if we didn't get categories from accumulated product_types
                    if raw_categories:
                        pass  # Already have categories from accumulated product types
                    elif "living" in room_context or "sofa" in room_context:
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
                                "category_id": "table_lamps",
                                "display_name": "Table Lamps",
                                "priority": 5,
                                "budget_allocation": {"min": 2000, "max": 8000},
                            },
                            {
                                "category_id": "ceiling_lights",
                                "display_name": "Ceiling & Pendant Lights",
                                "priority": 6,
                                "budget_allocation": {"min": 3000, "max": 15000},
                            },
                            {
                                "category_id": "rugs",
                                "display_name": "Rugs & Carpets",
                                "priority": 7,
                                "budget_allocation": {"min": 5000, "max": 20000},
                            },
                            {
                                "category_id": "planters",
                                "display_name": "Planters",
                                "priority": 8,
                                "budget_allocation": {"min": 1000, "max": 5000},
                            },
                            {
                                "category_id": "wall_art",
                                "display_name": "Wall Art",
                                "priority": 9,
                                "budget_allocation": {"min": 2000, "max": 7000},
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
                            "category_id": "floor_lamps",
                            "display_name": "Floor Lamps",
                            "priority": 4,
                            "budget_allocation": {"min": 2000, "max": 8000},
                        },
                        {
                            "category_id": "ceiling_lights",
                            "display_name": "Ceiling Lights",
                            "priority": 5,
                            "budget_allocation": {"min": 3000, "max": 12000},
                        },
                        {
                            "category_id": "wall_lights",
                            "display_name": "Wall Lights",
                            "priority": 6,
                            "budget_allocation": {"min": 2000, "max": 8000},
                        },
                        {
                            "category_id": "wardrobes",
                            "display_name": "Wardrobes",
                            "priority": 7,
                            "budget_allocation": {"min": 20000, "max": 50000},
                        },
                        {
                            "category_id": "rugs",
                            "display_name": "Rugs & Carpets",
                            "priority": 8,
                            "budget_allocation": {"min": 5000, "max": 20000},
                        },
                        {
                            "category_id": "wall_art",
                            "display_name": "Wall Art",
                            "priority": 9,
                            "budget_allocation": {"min": 2000, "max": 7000},
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
                        {
                            "category_id": "ceiling_lights",
                            "display_name": "Ceiling & Pendant Lights",
                            "priority": 4,
                            "budget_allocation": {"min": 5000, "max": 15000},
                        },
                        {
                            "category_id": "floor_lamps",
                            "display_name": "Floor Lamps",
                            "priority": 5,
                            "budget_allocation": {"min": 2000, "max": 8000},
                        },
                        {
                            "category_id": "wall_lights",
                            "display_name": "Wall Lights",
                            "priority": 6,
                            "budget_allocation": {"min": 2000, "max": 8000},
                        },
                        {
                            "category_id": "rugs",
                            "display_name": "Rugs & Carpets",
                            "priority": 7,
                            "budget_allocation": {"min": 5000, "max": 15000},
                        },
                        {
                            "category_id": "wall_art",
                            "display_name": "Wall Art",
                            "priority": 8,
                            "budget_allocation": {"min": 2000, "max": 7000},
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
                            "category_id": "table_lamps",
                            "display_name": "Table Lamps",
                            "priority": 5,
                            "budget_allocation": {"min": 2000, "max": 8000},
                        },
                        {
                            "category_id": "ceiling_lights",
                            "display_name": "Ceiling & Pendant Lights",
                            "priority": 6,
                            "budget_allocation": {"min": 3000, "max": 15000},
                        },
                        {
                            "category_id": "rugs",
                            "display_name": "Rugs & Carpets",
                            "priority": 7,
                            "budget_allocation": {"min": 5000, "max": 20000},
                        },
                        {
                            "category_id": "planters",
                            "display_name": "Planters",
                            "priority": 8,
                            "budget_allocation": {"min": 1000, "max": 5000},
                        },
                        {
                            "category_id": "wall_art",
                            "display_name": "Wall Art",
                            "priority": 9,
                            "budget_allocation": {"min": 2000, "max": 7000},
                        },
                    ]
                logger.info(f"[CATEGORY GEN] Generated {len(raw_categories)} default categories for room type")

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

                    # MANDATORY: Ensure generic categories (planters, wall_art, rugs) are ALWAYS included
                    # BUT ONLY for READY_TO_RECOMMEND with FULL ROOM styling
                    # NOT for: direct searches, BROWSING, or when user requests specific categories
                    #
                    # DETECT SPECIFIC CATEGORY REQUEST:
                    # If GPT returned only 1-2 categories, user is asking for something specific
                    # e.g., "show me decor items" → only show decor, don't add sofas, tables, etc.
                    is_specific_category_request = len(selected_categories_response) <= 2

                    # Also detect from message if user is asking for specific items
                    message_lower = request.message.lower()
                    specific_category_phrases = [
                        "show me decor",
                        "show me rugs",
                        "show me lamps",
                        "show me planters",
                        "decor items",
                        "decor for",
                        "just decor",
                        "only decor",
                        "show me sofas",
                        "show me tables",
                        "show me chairs",
                        "just show",
                        "only show",
                        "looking for decor",
                        "need decor",
                    ]
                    user_asking_specific = any(phrase in message_lower for phrase in specific_category_phrases)

                    if (
                        conversation_state == "READY_TO_RECOMMEND"
                        and not is_specific_category_request
                        and not user_asking_specific
                    ):
                        existing_cat_ids = {cat.category_id for cat in selected_categories_response}
                        mandatory_generic = [
                            ("planters", "Planters", 100),
                            ("wall_art", "Wall Art", 101),
                            ("rugs", "Rugs", 102),
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
                        logger.info(
                            f"[SPECIFIC REQUEST] Skipping mandatory categories - user requested specific category (is_specific={is_specific_category_request}, user_asking={user_asking_specific})"
                        )

                    # =================================================================
                    # BUDGET VALIDATION: Ensure budget allocations sum to total budget
                    # Get budget from: AI analysis, direct search extraction, accumulated filters, or onboarding
                    # =================================================================
                    user_total_budget = None
                    if total_budget:
                        user_total_budget = total_budget
                    elif direct_search_result.get("extracted_budget_max"):
                        user_total_budget = direct_search_result["extracted_budget_max"]
                    elif omni_prefs.budget_total:
                        # Use budget from onboarding preferences
                        user_total_budget = omni_prefs.budget_total
                        logger.info(f"[BUDGET] Using onboarding budget: ₹{user_total_budget:,}")
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

                    # =================================================================
                    # NO BUDGET? REMOVE BUDGET FILTER
                    # If user hasn't specified any budget, clear budget_allocation from
                    # all categories to show products across all price ranges
                    # =================================================================
                    if not user_total_budget and not omni_prefs.budget_total:
                        logger.info("[NO BUDGET] User hasn't specified budget - removing budget filters from all categories")
                        for cat in selected_categories_response:
                            cat.budget_allocation = None

                    # If we're in READY_TO_RECOMMEND or BROWSING state, fetch products by category
                    # BROWSING: User is filtering to specific category mid-conversation (e.g., "show me decor items")
                    if conversation_state in ["READY_TO_RECOMMEND", "BROWSING"] and selected_categories_response:
                        # Extract size keywords for category-specific filtering
                        size_keywords_for_search = []

                        if is_direct_search:
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
                                # IMPORTANT: Pass size keywords separately for category-first filtering
                                size_keywords_for_search = direct_search_result["extracted_sizes"]

                            logger.info(f"[DIRECT SEARCH] Style attributes from user query: {style_attributes}")
                            logger.info(f"[DIRECT SEARCH] Size keywords for category filtering: {size_keywords_for_search}")
                        else:
                            logger.info("[GUIDED FLOW] Fetching category-based recommendations...")

                            # Extract style attributes from ChatGPT analysis to pass to product search
                            # This enables style-aware product prioritization
                            style_attributes = _extract_style_attributes_from_analysis(analysis)
                            logger.info(f"[GUIDED FLOW] Extracted style attributes: {style_attributes}")

                        # =================================================================
                        # MERGE PERSISTED STYLES: Add user's style preferences from context
                        # Style should persist across category changes (modern sofas → modern floor lamps)
                        # Sources: onboarding styles array AND overall_style from conversation
                        # =================================================================
                        existing_keywords = [s.lower() for s in style_attributes.get("style_keywords", [])]

                        # First, add overall_style from conversation context (highest priority)
                        if omni_prefs.overall_style:
                            style_value = omni_prefs.overall_style.lower()
                            # Handle compound styles like "modern with industrial touches"
                            for word in style_value.replace(" with ", " ").replace(" touches", "").split():
                                if word not in existing_keywords and len(word) > 2:
                                    style_attributes.setdefault("style_keywords", []).insert(0, word)
                                    existing_keywords.append(word)
                            logger.info(
                                f"[PERSISTED STYLE] Added overall_style '{omni_prefs.overall_style}' to style_keywords"
                            )

                        # Then add onboarding styles array if available
                        if hasattr(omni_prefs, "styles") and omni_prefs.styles:
                            for style in omni_prefs.styles:
                                if style and style.lower() not in existing_keywords:
                                    style_attributes.setdefault("style_keywords", []).insert(0, style.lower())
                                    existing_keywords.append(style.lower())
                            logger.info(
                                f"[ONBOARDING STYLES] Merged onboarding styles {omni_prefs.styles} into style_attributes"
                            )

                        if style_attributes.get("style_keywords"):
                            logger.info(f"[STYLE PERSISTENCE] Final style_keywords: {style_attributes['style_keywords']}")

                        # =================================================================
                        # RETRIEVE PERSISTED ATTRIBUTES: Get size/type from category_attributes
                        # This ensures "sectional" persists from "find me sectional sofas"
                        # even after user says "no preference"
                        # =================================================================
                        if not size_keywords_for_search and omni_prefs.category_attributes:
                            # Convert persisted attributes back to size keywords
                            cat_attrs = omni_prefs.category_attributes
                            for attr_name, attr_value in cat_attrs.items():
                                if attr_name in ["seating_type", "seating_capacity", "size"] and attr_value:
                                    size_keywords_for_search.append(str(attr_value))
                            if size_keywords_for_search:
                                logger.info(
                                    f"[PERSISTED ATTRS] Retrieved size keywords from category_attributes: {size_keywords_for_search}"
                                )

                        # =================================================================
                        # AUTO-CHOOSE STYLE: If user hasn't specified style, use room analysis
                        # If room image was analyzed, use detected_style as the style preference
                        # =================================================================
                        if not omni_prefs.overall_style and omni_prefs.room_analysis_suggestions:
                            detected_style = omni_prefs.room_analysis_suggestions.detected_style
                            if detected_style:
                                logger.info(
                                    f"[AUTO-STYLE] User didn't specify style - using room analysis detected style: '{detected_style}'"
                                )
                                # Set the detected style as the user's style preference
                                conversation_context_manager.update_omni_preferences(session_id, overall_style=detected_style)
                                omni_prefs.overall_style = detected_style  # Update local reference too
                                # Add to style keywords for product matching
                                if detected_style.lower() not in [
                                    s.lower() for s in style_attributes.get("style_keywords", [])
                                ]:
                                    style_attributes["style_keywords"].insert(0, detected_style.lower())
                                logger.info(f"[AUTO-STYLE] Updated style_attributes: {style_attributes}")

                        products_by_category = await _get_category_based_recommendations(
                            selected_categories_response,
                            db,
                            selected_stores=request.selected_stores,
                            limit_per_category=0,  # 0 = no limit, return ALL scored products
                            style_attributes=style_attributes,
                            size_keywords=size_keywords_for_search,
                            semantic_query=request.message,  # Enable semantic search for hybrid scoring
                            user_total_budget=user_total_budget,  # User's total budget for scoring
                        )

                        # Update product counts in category recommendations
                        for cat in selected_categories_response:
                            if cat.category_id in products_by_category:
                                cat.product_count = len(products_by_category[cat.category_id])

                        state_label = (
                            "DIRECT SEARCH"
                            if is_direct_search
                            else ("BROWSING" if conversation_state == "BROWSING" else "GUIDED FLOW")
                        )
                        logger.info(f"[{state_label}] Fetched products for {len(products_by_category)} categories")

                        # =================================================================
                        # RESPONSE ENHANCEMENT: Add "here are recommended products" when products shown
                        # This ensures users know products are available in the panel
                        # =================================================================
                        if not is_direct_search and products_by_category:
                            total_products = sum(len(prods) for prods in products_by_category.values())
                            if total_products > 0:
                                # Check if GPT's response already mentions products
                                response_lower = (conversational_response or "").lower()
                                already_mentions_products = any(
                                    phrase in response_lower
                                    for phrase in ["products", "recommendations", "options", "items", "check out", "panel"]
                                )

                                if not already_mentions_products:
                                    # Append product notification to GPT's response
                                    conversational_response = (
                                        f"{conversational_response} "
                                        f"I've found {total_products} products matching your preferences - check them out in the Products panel!"
                                    )
                                    logger.info(f"[RESPONSE ENHANCED] Added product notification ({total_products} products)")

                                    # Rebuild message_schema with updated response
                                    message_schema = ChatMessageSchema(
                                        id=assistant_message_id,
                                        type=MessageType.assistant,
                                        content=conversational_response,
                                        timestamp=assistant_message.timestamp,
                                        session_id=session_id,
                                        products=recommended_products,
                                        image_url=visualization_image,
                                    )

                        # For direct search, use GPT's warm response if available
                        # Only fall back to generic template if GPT didn't provide a good response
                        if is_direct_search and products_by_category:
                            total_products = sum(len(prods) for prods in products_by_category.values())

                            # Check if GPT provided a meaningful response (not generic fallback)
                            gpt_response_is_good = (
                                conversational_response
                                and len(conversational_response) > 30
                                and "I've analyzed your request" not in conversational_response
                            )

                            if gpt_response_is_good:
                                # Use GPT's warm response - it already mentions style/budget
                                logger.info(f"[DIRECT SEARCH] Using GPT's warm response: {conversational_response[:80]}...")
                            else:
                                # Fall back to template only if GPT failed
                                conversational_response = _build_direct_search_response_message(
                                    detected_categories=direct_search_result["detected_categories"],
                                    colors=direct_search_result["extracted_colors"],
                                    materials=direct_search_result["extracted_materials"],
                                    styles=direct_search_result["extracted_styles"],
                                    product_count=total_products,
                                )
                                logger.info(f"[DIRECT SEARCH] Using template response: {conversational_response[:80]}...")

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
        # OMNI DYNAMIC FLOW: Check if style, budget, AND scope are already known
        # If Omni has all three, let the AI response through (don't force gathering questions)
        # Also skip gathering if user declined preferences (omni_decides mode)
        # =================================================================
        omni_prefs = conversation_context_manager.get_omni_preferences(session_id)
        user_declined_prefs = omni_prefs.preference_mode == "omni_decides"
        omni_has_essentials = (
            bool(omni_prefs.overall_style and omni_prefs.budget_total and omni_prefs.scope) or user_declined_prefs
        )

        if omni_has_essentials:
            if user_declined_prefs:
                logger.info("[OMNI FLOW] User declined preferences (omni_decides mode) - skipping gathering, showing products")
            else:
                logger.info(
                    f"[OMNI FLOW] Style '{omni_prefs.overall_style}', budget '{omni_prefs.budget_total}', scope '{omni_prefs.scope}' known - letting Omni response through"
                )

            # =================================================================
            # FALLBACK: If Omni has essentials but products weren't fetched (e.g., analysis=None),
            # generate categories and fetch products now. This ensures products are shown
            # even when GPT response parsing fails.
            # =================================================================
            if not products_by_category and not selected_categories_response:
                logger.info(
                    "[OMNI FALLBACK] Omni has essentials but no products - generating categories and fetching products"
                )

                # Generate default categories based on room type
                room_context = omni_prefs.room_type.lower() if omni_prefs.room_type else "living room"
                logger.info(f"[OMNI FALLBACK] Using room context: {room_context}")

                # Generate room-based categories
                if "living" in room_context or "sofa" in room_context:
                    fallback_categories = [
                        {"category_id": "sofas", "display_name": "Sofas", "priority": 1},
                        {"category_id": "coffee_tables", "display_name": "Coffee Tables", "priority": 2},
                        {"category_id": "side_tables", "display_name": "Side Tables", "priority": 3},
                        {"category_id": "floor_lamps", "display_name": "Floor Lamps", "priority": 4},
                        {"category_id": "rugs", "display_name": "Rugs", "priority": 5},
                        {"category_id": "wall_art", "display_name": "Wall Art", "priority": 6},
                        {"category_id": "planters", "display_name": "Planters", "priority": 7},
                    ]
                elif "bed" in room_context or "sleep" in room_context:
                    fallback_categories = [
                        {"category_id": "beds", "display_name": "Beds", "priority": 1},
                        {"category_id": "nightstands", "display_name": "Nightstands", "priority": 2},
                        {"category_id": "table_lamps", "display_name": "Table Lamps", "priority": 3},
                        {"category_id": "rugs", "display_name": "Rugs", "priority": 4},
                        {"category_id": "wall_art", "display_name": "Wall Art", "priority": 5},
                    ]
                elif "dining" in room_context:
                    fallback_categories = [
                        {"category_id": "dining_tables", "display_name": "Dining Tables", "priority": 1},
                        {"category_id": "dining_chairs", "display_name": "Dining Chairs", "priority": 2},
                        {"category_id": "ceiling_lights", "display_name": "Ceiling Lights", "priority": 3},
                        {"category_id": "rugs", "display_name": "Rugs", "priority": 4},
                    ]
                else:
                    # Default to living room categories
                    fallback_categories = [
                        {"category_id": "sofas", "display_name": "Sofas", "priority": 1},
                        {"category_id": "coffee_tables", "display_name": "Coffee Tables", "priority": 2},
                        {"category_id": "floor_lamps", "display_name": "Floor Lamps", "priority": 3},
                        {"category_id": "rugs", "display_name": "Rugs", "priority": 4},
                        {"category_id": "wall_art", "display_name": "Wall Art", "priority": 5},
                    ]

                # Convert to CategoryRecommendation objects
                selected_categories_response = []
                for cat_data in fallback_categories:
                    selected_categories_response.append(
                        CategoryRecommendation(
                            category_id=cat_data["category_id"],
                            display_name=cat_data["display_name"],
                            budget_allocation=None,  # Will be set by budget validator below
                            priority=cat_data["priority"],
                        )
                    )

                # Apply budget validation if user has a budget
                if omni_prefs.budget_total and selected_categories_response:
                    logger.info(f"[OMNI FALLBACK] Applying budget validation for ₹{omni_prefs.budget_total:,}")
                    selected_categories_response = validate_and_adjust_budget_allocations(
                        total_budget=float(omni_prefs.budget_total),
                        categories=selected_categories_response,
                        category_id_field="category_id",
                    )

                # Fetch products for these categories
                style_attributes = {
                    "style_keywords": [omni_prefs.overall_style.lower()] if omni_prefs.overall_style else [],
                    "colors": [],
                    "materials": [],
                }

                products_by_category = await _get_category_based_recommendations(
                    selected_categories_response,
                    db,
                    selected_stores=request.selected_stores,
                    limit_per_category=0,  # 0 = no limit, return ALL scored products
                    style_attributes=style_attributes,
                    size_keywords=[],
                    semantic_query=request.message,  # Enable semantic search for hybrid scoring
                    user_total_budget=float(omni_prefs.budget_total) if omni_prefs.budget_total else None,
                )

                # Update product counts
                for cat in selected_categories_response:
                    if cat.category_id in products_by_category:
                        cat.product_count = len(products_by_category[cat.category_id])

                # Set conversation state to READY_TO_RECOMMEND
                conversation_state = "READY_TO_RECOMMEND"

                # Count total products
                total_fallback_products = sum(len(p) for p in products_by_category.values())

                logger.info(
                    f"[OMNI FALLBACK] Generated {len(selected_categories_response)} categories with {total_fallback_products} total products"
                )

                # =================================================================
                # RESPONSE ENHANCEMENT: Add "here are recommended products" for fallback flow
                # =================================================================
                if total_fallback_products > 0:
                    response_lower = (conversational_response or "").lower()
                    already_mentions_products = any(
                        phrase in response_lower
                        for phrase in ["products", "recommendations", "options", "items", "check out", "panel"]
                    )

                    if not already_mentions_products:
                        conversational_response = (
                            f"{conversational_response} "
                            f"I've found {total_fallback_products} products matching your preferences - check them out in the Products panel!"
                        )
                        logger.info(
                            f"[OMNI FALLBACK RESPONSE] Added product notification ({total_fallback_products} products)"
                        )

                        # Rebuild message_schema with updated response
                        message_schema = ChatMessageSchema(
                            id=assistant_message_id,
                            type=MessageType.assistant,
                            content=conversational_response,
                            timestamp=assistant_message.timestamp,
                            session_id=session_id,
                            products=recommended_products,
                            image_url=visualization_image,
                        )

            # Omni has the essentials, don't force gathering flow
            # Let GPT's dynamic response through unchanged
        elif conversation_state in [
            "GATHERING_USAGE",
            "GATHERING_STYLE",
            "GATHERING_BUDGET",
            "GATHERING_SCOPE",
            "DIRECT_SEARCH_GATHERING",
        ]:
            # Omni doesn't have essentials yet - enforce clean gathering flow
            logger.info(f"[OMNI FLOW] State is {conversation_state} - gathering, clearing products")
            recommended_products = None
            # CRITICAL: Clear products during gathering - but for DIRECT_SEARCH_GATHERING, keep categories!
            # DIRECT_SEARCH_GATHERING means user asked for a specific category, we just need more details
            # Keeping categories lets the frontend know what category the user is interested in
            products_by_category = None
            if conversation_state != "DIRECT_SEARCH_GATHERING":
                selected_categories_response = None
            else:
                logger.info(
                    f"[DIRECT SEARCH GATHERING] Keeping selected_categories ({len(selected_categories_response) if selected_categories_response else 0} categories)"
                )

            # =================================================================
            # SCOPE QUESTION INJECTION: If in GATHERING_SCOPE but no proper scope question,
            # inject one that acknowledges their style/budget preferences
            # =================================================================
            if conversation_state == "GATHERING_SCOPE" and omni_prefs.overall_style and omni_prefs.budget_total:
                # Build a personalized scope question referencing their known preferences
                style_text = omni_prefs.overall_style
                budget_text = (
                    f"₹{omni_prefs.budget_total:,}"
                    if isinstance(omni_prefs.budget_total, (int, float))
                    else f"₹{omni_prefs.budget_total}"
                )
                scope_question = f"With your {style_text} style and {budget_text} budget, would you like me to help style the entire room, or are you looking for something specific like a sofa or coffee table?"

                # Check if GPT already asked a scope-like question
                gpt_response_lower = (conversational_response or "").lower()
                is_asking_scope = any(
                    phrase in gpt_response_lower
                    for phrase in [
                        "entire room",
                        "whole room",
                        "full room",
                        "specific",
                        "something specific",
                        "particular piece",
                        "specific item",
                    ]
                )

                if not is_asking_scope:
                    # GPT didn't ask scope - inject our scope question
                    conversational_response = scope_question
                    follow_up_question = scope_question
                    logger.info(f"[SCOPE INJECTION] GPT didn't ask scope, injecting: {scope_question}")
                else:
                    logger.info(f"[SCOPE CHECK] GPT already asking about scope: {gpt_response_lower[:80]}...")

            # CRITICAL FIX: For DIRECT_SEARCH_GATHERING, ALWAYS use the follow-up question
            # This ensures consistency: if we're clearing products, we ask for preferences
            # Without this, GPT might say "here are products" but no products are shown
            if follow_up_question:
                # Use the follow-up question as the main response for all gathering states
                conversational_response = follow_up_question
                is_generic = direct_search_result.get("is_generic_category", False)
                if is_generic:
                    logger.info(f"[GENERIC CATEGORY] Using subcategory question: {follow_up_question[:80]}...")
                else:
                    logger.info(f"[DIRECT SEARCH GATHERING] Using follow-up question: {follow_up_question[:80]}...")
                follow_up_question = None  # Clear so frontend doesn't duplicate
            else:
                # Fallback to GPT's response if no follow-up question was generated
                logger.info(
                    f"[OMNI FLOW] No follow-up question, using GPT response: {conversational_response[:80] if conversational_response else 'None'}..."
                )

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

        # Save Omni preferences to database for persistence across sessions
        if session.user_id:
            await save_user_preferences_to_db(session.user_id, session_id, db)

        # =================================================================
        # GENERIC CATEGORY OVERRIDE: If user asked for a generic category like
        # "lighting", override the response to ask for subcategory preference
        # This happens REGARDLESS of omni_has_essentials - we always want to
        # ask "What kind of lighting?" before showing products
        # =================================================================
        if direct_search_result.get("is_generic_category", False):
            generic_info = direct_search_result.get("generic_category_info", {})
            subcategory_question = generic_info.get("follow_up_question", "")
            if subcategory_question:
                logger.info(f"[GENERIC CATEGORY OVERRIDE] Replacing response with subcategory question")
                # Update the message content to ask for subcategory
                message_schema = ChatMessageSchema(
                    id=message_schema.id,
                    type=message_schema.type,
                    content=subcategory_question,
                    timestamp=message_schema.timestamp,
                    session_id=message_schema.session_id,
                    products=None,  # No products until subcategory is chosen
                    image_url=message_schema.image_url,
                )
                # Clear products - don't show until subcategory is chosen
                products_by_category = None
                selected_categories_response = None

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
                        limit=100,
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

        # Perspective transformation: Convert side-angle photos to front view
        # Only applies to fresh visualizations (force_reset or first time)
        normalize_perspective = request.get("normalize_perspective", True)
        if normalize_perspective and (force_reset or not is_incremental):
            try:
                # Quick room analysis to detect viewing angle
                logger.info("Analyzing room image for perspective transformation...")
                room_analysis = await google_ai_service.analyze_room_image(base_image)

                # Check if viewing angle needs transformation
                camera_view = getattr(room_analysis, "camera_view_analysis", {}) or {}
                viewing_angle = camera_view.get("viewing_angle", "straight_on")

                if viewing_angle and viewing_angle != "straight_on":
                    logger.info(f"Detected {viewing_angle} camera angle - transforming to front view")
                    transformed_image = await google_ai_service.transform_perspective_to_front(base_image, viewing_angle)
                    if transformed_image and transformed_image != base_image:
                        base_image = transformed_image
                        logger.info("Successfully transformed perspective to front view")
                    else:
                        logger.info("Perspective transformation returned original image")
                else:
                    logger.info("Room already has straight-on perspective, no transformation needed")
            except Exception as e:
                logger.warning(f"Perspective transformation failed, using original image: {e}")
                # Continue with original image if transformation fails

        # Check product count and enforce incremental visualization for larger sets
        # The Gemini API has input size limitations and fails with 500 errors when
        # processing 5+ products simultaneously. Use incremental mode as workaround.
        MAX_PRODUCTS_BATCH = 4
        forced_incremental = False

        # Check expanded product count (after quantity expansion) for batch limit
        # We need to check this BEFORE deciding on incremental mode
        expanded_count_estimate = sum(p.get("quantity", 1) for p in products)

        if expanded_count_estimate > MAX_PRODUCTS_BATCH and not is_incremental:
            if force_reset:
                # For force_reset with many products, we need a special approach:
                # Start fresh with first batch, then incrementally add the rest
                logger.info(
                    f"Force reset with {expanded_count_estimate} expanded products exceeds batch limit ({MAX_PRODUCTS_BATCH}). "
                    f"Will process first {MAX_PRODUCTS_BATCH} products initially, then add rest incrementally."
                )
                forced_incremental = True
                # Keep force_reset True for first batch to use clean base image
            else:
                logger.info(
                    f"Product count ({expanded_count_estimate} expanded) exceeds batch limit ({MAX_PRODUCTS_BATCH}). Forcing incremental visualization."
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

        # DISABLED: Same-category clarification prompt
        # Users can now add multiple products of the same category without being asked
        # The system defaults to "add" behavior - keeping existing furniture and adding new ones
        if matching_existing and not user_action and not custom_positions:
            product_type_display = list(selected_product_types)[0].replace("_", " ")
            count = len(matching_existing)
            plural = "s" if count > 1 else ""
            logger.info(
                f"Found {count} matching {product_type_display}{plural} in room - defaulting to ADD (no clarification)"
            )
            # Default to add behavior - set user_action so the visualization instruction is generated
            user_action = "add"
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

                    # Preserve instance labels from frontend (e.g., "Prakrit Cushion Cover #2")
                    # Only overwrite if frontend didn't send an instance-labeled name
                    frontend_name = product.get("name", "")
                    frontend_full_name = product.get("full_name", "")
                    if "#" in frontend_name and db_product.name in frontend_name:
                        # Frontend sent an instance-labeled name like "Product Name #2" - preserve it
                        logger.info(f"Preserving instance-labeled name: {frontend_name}")
                        # Also ensure full_name is set if not already
                        if not frontend_full_name:
                            product["full_name"] = frontend_name
                    else:
                        # Use database name
                        product["name"] = db_product.name
                        product["full_name"] = db_product.name

                    product["source"] = db_product.source_website

                    # Add image URLs - include ALL images for better visualization accuracy
                    if db_product.images:
                        primary_image = next((img for img in db_product.images if img.is_primary), db_product.images[0])
                        if primary_image:
                            product["image_url"] = primary_image.original_url
                        # Add all image URLs for multi-reference visualization
                        product["image_urls"] = [img.original_url for img in db_product.images if img.original_url]

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

        # Expand products based on quantity for multiple placements
        # If a product has quantity > 1, create multiple entries for the AI to place
        def expand_products_by_quantity(product_list):
            """Expand products list based on quantity field. If qty=3, create 3 entries."""
            expanded = []
            for product in product_list:
                qty = product.get("quantity", 1)
                if qty <= 1:
                    expanded.append(product)
                else:
                    # Create multiple entries with numbered names for distinct placement
                    for i in range(qty):
                        expanded_product = product.copy()
                        if qty > 1:
                            # Add instance number to help AI place them distinctly
                            original_name = product.get("full_name") or product.get("name", "item")
                            expanded_product["name"] = f"{original_name} #{i+1}"
                            expanded_product["full_name"] = f"{original_name} #{i+1}"
                            expanded_product["instance_number"] = i + 1
                            expanded_product["total_instances"] = qty
                        expanded.append(expanded_product)
            return expanded

        # Log quantity information for debugging
        total_items = 0
        for p in products:
            qty = p.get("quantity", 1)
            total_items += qty
            logger.info(f"[Quantity Debug] Product: {p.get('name')}, quantity: {qty}")

        if total_items != len(products):
            logger.info(f"Products contain quantities totaling {total_items} items (from {len(products)} product entries)")

        # Expand products based on quantity for full visualization (non-incremental path)
        expanded_products = expand_products_by_quantity(products)
        logger.info(f"Expanded {len(products)} products to {len(expanded_products)} items for visualization")

        # Handle incremental visualization (add ONLY NEW products to existing visualization)
        if is_incremental:
            logger.info(
                f"Incremental visualization: Adding {len(new_products_to_visualize)} product entries (out of {len(products)} total)"
            )

            # Use BATCH add visualization for all new products in a SINGLE API call
            # Products now include quantity field - the AI service handles rendering multiple copies
            try:
                products_for_viz = new_products_to_visualize
                product_details = [f"{p.get('name')} (qty={p.get('quantity', 1)})" for p in products_for_viz]
                logger.info(f"  Batch adding products: {', '.join(product_details)}")

                current_image = await google_ai_service.generate_add_multiple_visualization(
                    room_image=base_image,  # Start with previous visualization (already has old products)
                    products=products_for_viz,  # Use expanded products for quantity support
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
            # BUT if we have too many products and forced_incremental is True, process in batches
            if forced_incremental and force_reset and len(expanded_products) > MAX_PRODUCTS_BATCH:
                logger.info(f"Processing {len(expanded_products)} products in batches due to API limits")

                # Phase 1: Visualize first batch on clean base image
                first_batch = expanded_products[:MAX_PRODUCTS_BATCH]
                logger.info(f"Phase 1: Visualizing first {len(first_batch)} products on clean base")

                viz_request = VisualizationRequest(
                    base_image=base_image,
                    products_to_place=first_batch,
                    placement_positions=[],
                    lighting_conditions=lighting_conditions,
                    render_quality="high",
                    style_consistency=True,
                    user_style_description=user_style_description,
                    exclusive_products=True,
                )
                viz_result = await google_ai_service.generate_room_visualization(viz_request)
                current_image = viz_result.rendered_image

                # Phase 2+: Incrementally add remaining products in batches
                remaining_products = expanded_products[MAX_PRODUCTS_BATCH:]
                batch_num = 2
                while remaining_products:
                    batch = remaining_products[:MAX_PRODUCTS_BATCH]
                    remaining_products = remaining_products[MAX_PRODUCTS_BATCH:]
                    logger.info(f"Phase {batch_num}: Adding {len(batch)} more products incrementally")

                    current_image = await google_ai_service.generate_add_multiple_visualization(
                        room_image=current_image,
                        products=batch,
                    )
                    batch_num += 1

                # Final result
                viz_result = VisualizationResult(
                    rendered_image=current_image,
                    processing_time=0.0,
                    quality_score=0.85,
                    placement_accuracy=0.90,
                    lighting_realism=0.85,
                    confidence_score=0.87,
                )
            else:
                # Normal single-batch visualization
                # Create visualization request
                # When force_reset is True, use exclusive_products mode to ONLY show specified products
                # and remove any existing furniture from the base image
                viz_request = VisualizationRequest(
                    base_image=base_image,
                    products_to_place=expanded_products,  # Use expanded products for quantity support
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


@router.post("/sessions/{session_id}/visualize/angle")
async def generate_angle_view(session_id: str, request: dict, db: AsyncSession = Depends(get_db)):
    """
    Generate a visualization from a specific viewing angle (on-demand).

    Request body:
    - visualization_image: Base64 encoded front-view visualization
    - target_angle: "left", "right", or "back"
    - products_description: Optional description of products in the room
    """
    try:
        # Verify session exists
        session_query = select(ChatSession).where(ChatSession.id == session_id)
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Extract request data
        visualization_image = request.get("visualization_image")
        target_angle = request.get("target_angle")
        products_description = request.get("products_description")

        if not visualization_image:
            raise HTTPException(status_code=400, detail="Visualization image is required")

        if target_angle not in ["left", "right", "back"]:
            raise HTTPException(status_code=400, detail="Invalid target angle. Must be 'left', 'right', or 'back'")

        logger.info(f"Generating {target_angle} view for session {session_id}")

        # Generate alternate view using Google AI service
        result_image = await google_ai_service.generate_alternate_view(
            visualization_image=visualization_image, target_angle=target_angle, products_description=products_description
        )

        return {"angle": target_angle, "image": result_image, "message": f"Successfully generated {target_angle} view"}

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Error generating angle view: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating angle view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating {target_angle} view: {str(e)}")


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
    # Seater variations - include both with and without hyphen
    "single seater",
    "single-seater",
    "1 seater",
    "one seater",
    "2 seater",
    "two seater",
    "two-seater",
    "3 seater",
    "three seater",
    "three-seater",
    "4 seater",
    "four seater",
    "four-seater",
    "5 seater",
    "five seater",
    "6 seater",
    "six seater",
    "l shaped",
    "l-shaped",
    "sectional",
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
        # Specific lighting categories (checked BEFORE generic "lighting")
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
        "wall_art": ["wall art", "painting", "print", "poster", "canvas", "artwork"],
        "wallpapers": ["wallpaper", "wallpapers", "wall paper", "wall covering", "wall coverings"],
        "photo_frames": ["photo frame", "picture frame", "frame"],
        "rugs": ["rug", "carpet", "area rug", "dhurrie", "kilim", "floor rug"],
        "mats": ["mat", "floor mat", "door mat", "bath mat", "runner", "table runner"],
        "mirrors": ["mirror", "wall mirror", "floor mirror", "vanity mirror"],
        "cushion_covers": ["cushion cover", "cushion covers", "pillow cover", "pillow covers"],
        "cushions": ["cushion", "pillow", "throw pillow", "decorative pillow"],
        "throws": ["throw", "blanket", "throw blanket"],
        "benches": ["bench", "benches", "entryway bench", "storage bench", "bedroom bench"],
        # Decor categories - specific types first, then generic
        "sculptures": ["sculpture", "sculptures", "statue", "statues", "statuette"],
        "figurines": ["figurine", "figurines", "figure", "decorative figure"],
        "vases": ["vase", "vases", "flower vase", "decorative vase"],
        "ornaments": ["ornament", "ornaments", "decorative ornament"],
        "artefacts": ["artefact", "artefacts", "artifact", "artifacts"],
        "decorative_bowls": ["decorative bowl", "decorative bowls", "accent bowl"],
        "decorative_boxes": ["decorative box", "decorative boxes", "trinket box"],
        "candle_holders": ["candle holder", "candle holders", "candleholder", "candlestick"],
        "clocks": ["clock", "clocks", "wall clock", "table clock", "mantel clock"],
        # Generic decor - only for broad "decor" searches
        "decor_accents": [
            "decor",
            "decor item",
            "decor items",
            "decoration",
            "decorations",
            "decorative",
            "accent piece",
            "accent pieces",
            "home decor",
        ],
    }

    # Generic categories that expand to multiple subcategories
    # When detected, Omni asks "what kind?" - if user says "any kind", expand all subcategories
    generic_category_map = {
        "lighting": {
            "keywords": ["lights", "lighting", "lamps", "light fixtures"],
            "subcategories": ["floor_lamps", "table_lamps", "ceiling_lights", "wall_lights"],
            "follow_up_question": "What kind of lighting are you looking for? Floor lamps, table lamps, ceiling/pendant lights, or wall lights? Or I can show you all types!",
            "display_name": "Lighting",
        },
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

    # Check for generic categories (e.g., "lighting" which expands to floor_lamps, table_lamps, etc.)
    # Only trigger if NO specific subcategory was already detected
    detected_cat_ids = {cat["category_id"] for cat in detected_cats}
    for generic_id, generic_info in generic_category_map.items():
        # Check if any generic keyword matches
        for keyword in generic_info["keywords"]:
            if keyword in message_lower:
                # Check if any specific subcategory was already detected
                subcategory_detected = any(sub in detected_cat_ids for sub in generic_info["subcategories"])
                if not subcategory_detected:
                    # Mark as generic category - needs follow-up question
                    result["is_generic_category"] = True
                    result["generic_category_id"] = generic_id
                    result["generic_category_info"] = generic_info
                    # Add the generic category to detected_cats so it's treated as a direct search
                    detected_cats.append(
                        {
                            "category_id": generic_id,
                            "display_name": generic_info["display_name"],
                            "matched_keyword": keyword,
                            "is_generic": True,
                            "subcategories": generic_info["subcategories"],
                        }
                    )
                    logger.info(f"[GENERIC CATEGORY] Detected generic '{generic_id}' - will ask for subcategory preference")
                break
        if result.get("is_generic_category"):
            break

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
            if budget_str:  # Only convert if not empty
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
        # EXCEPTION: Simple categories don't need qualifiers - show immediately!
        has_qualifiers = (
            len(result["extracted_colors"]) > 0
            or len(result["extracted_materials"]) > 0
            or len(result["extracted_styles"]) > 0
            or len(result["extracted_sizes"]) > 0
            or result["extracted_budget_max"] is not None
        )

        # Import simple category check
        from config.category_attributes import is_simple_category

        # Check if ANY detected category is a simple category (wall_art, planters, etc.)
        # Simple categories should show products immediately without qualifiers
        is_any_simple = any(is_simple_category(cat["category_id"]) for cat in detected_cats)

        # Mark simple categories as having sufficient info (no follow-up needed)
        result["has_sufficient_info"] = has_qualifiers or is_any_simple

        # Also mark each category with is_simple flag
        for cat in detected_cats:
            cat["is_simple"] = is_simple_category(cat["category_id"])

        logger.info(
            f"[DIRECT SEARCH] Detected direct search: categories={[c['category_id'] for c in detected_cats]}, "
            f"colors={result['extracted_colors']}, materials={result['extracted_materials']}, "
            f"styles={result['extracted_styles']}, sizes={result['extracted_sizes']}, "
            f"budget_max={result['extracted_budget_max']}, is_any_simple={is_any_simple}, "
            f"has_sufficient_info={result['has_sufficient_info']}"
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
    # Generic "lighting" category - searches all lighting types
    "lighting": [
        "light",
        "lights",
        "lighting",
        "lamp",
        "lamps",
        "floor lamp",
        "table lamp",
        "desk lamp",
        "pendant",
        "chandelier",
        "sconce",
        "light fixture",
    ],
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
    "wall_art": ["wall art", "painting", "print", "poster", "canvas", "artwork", "wall decor"],
    "wallpapers": ["wallpaper", "wallpapers", "wall paper", "wall covering", "wall coverings"],
    "photo_frames": ["photo frame", "picture frame", "photo frames", "picture frames"],
    # Specific decor subcategories (more specific matches)
    "sculptures": ["sculpture", "sculptures", "statue", "statues", "statuette"],
    "figurines": ["figurine", "figurines", "figure", "decorative figure"],
    "vases": ["vase", "vases", "flower vase", "decorative vase"],
    "ornaments": ["ornament", "ornaments", "decorative ornament"],
    "artefacts": ["artefact", "artefacts", "artifact", "artifacts"],
    "decorative_bowls": ["decorative bowl", "decorative bowls", "accent bowl"],
    "decorative_boxes": ["decorative box", "decorative boxes", "trinket box"],
    "candle_holders": ["candle holder", "candle holders", "candleholder", "candlestick"],
    "clocks": ["clock", "clocks", "wall clock", "table clock", "mantel clock"],
    # Generic decor - for broad searches
    "decor_accents": [
        "decor",
        "decor item",
        "decor items",
        "decoration",
        "decorations",
        "decorative",
        "accent piece",
        "home decor",
    ],
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
    "cushion_covers": ["cushion cover", "cushion covers", "pillow cover", "pillow covers"],
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

# Special category handling - for categories where we need to search in a parent category
# but filter by product name. Use this when products are miscategorized.
# NOTE: Prefer fixing the data (moving products to correct category) over using this workaround.
CATEGORY_SPECIAL_HANDLING = {
    # cushion_covers no longer needs special handling - data was fixed (402 products moved to Cushion Cover category)
}

# Priority keywords - products matching these terms will be sorted first
CATEGORY_PRIORITY_KEYWORDS = {
    "sofas": ["3 seater", "three seater", "l shape", "sectional", "corner"],  # Prioritize larger sofas
}


async def _semantic_search(
    query_text: str,
    db: AsyncSession,
    category_ids: Optional[List[int]] = None,
    store_filter: Optional[List[str]] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    limit: int = 100,
) -> Dict[int, float]:
    """
    Perform vector similarity search for semantic matching.

    This function generates an embedding for the query text and searches
    products using cosine similarity with their stored embeddings.

    Args:
        query_text: Search query (e.g., "cozy minimalist sofa")
        db: Database session
        category_ids: Optional list of category IDs to filter by
        store_filter: Optional list of store names to filter by
        price_min: Optional minimum price
        price_max: Optional maximum price
        limit: Maximum products to return

    Returns:
        Dict mapping product_id to similarity score (0.0 to 1.0)
    """
    import json

    embedding_service = get_embedding_service()

    # Get query embedding
    query_embedding = await embedding_service.get_query_embedding(query_text)
    if not query_embedding:
        logger.warning(f"[SEMANTIC SEARCH] Failed to generate embedding for: {query_text[:50]}...")
        return {}

    logger.info(f"[SEMANTIC SEARCH] Generated query embedding for: {query_text[:50]}...")

    # Build base query for products with embeddings
    query = select(Product.id, Product.embedding).where(Product.is_available.is_(True)).where(Product.embedding.isnot(None))

    # Apply filters
    if category_ids:
        query = query.where(Product.category_id.in_(category_ids))

    if store_filter:
        query = query.where(Product.source_website.in_(store_filter))

    if price_min is not None:
        query = query.where(Product.price >= price_min)

    if price_max is not None:
        query = query.where(Product.price <= price_max)

    # Execute query
    result = await db.execute(query)
    rows = result.fetchall()

    logger.info(f"[SEMANTIC SEARCH] Found {len(rows)} products with embeddings")

    # Calculate similarity scores
    similarity_scores: Dict[int, float] = {}

    for product_id, embedding_json in rows:
        try:
            # Parse stored embedding
            product_embedding = json.loads(embedding_json)

            # Compute cosine similarity
            similarity = embedding_service.compute_cosine_similarity(query_embedding, product_embedding)

            similarity_scores[product_id] = similarity

        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"[SEMANTIC SEARCH] Error processing product {product_id}: {e}")
            continue

    # Sort by similarity and take top N
    sorted_scores = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    result_dict = dict(sorted_scores)

    if result_dict:
        top_score = sorted_scores[0][1] if sorted_scores else 0
        logger.info(f"[SEMANTIC SEARCH] Top similarity score: {top_score:.3f}, " f"returning {len(result_dict)} products")

    return result_dict


async def _get_category_based_recommendations(
    selected_categories: List[CategoryRecommendation],
    db: AsyncSession,
    selected_stores: Optional[List[str]] = None,
    limit_per_category: int = 0,
    style_attributes: Optional[Dict[str, Any]] = None,
    size_keywords: Optional[List[str]] = None,
    semantic_query: Optional[str] = None,
    user_total_budget: Optional[float] = None,
) -> Dict[str, List[dict]]:
    """
    Get product recommendations grouped by AI-selected categories.

    This function queries products for each category using keyword matching,
    applies optional budget and store filters, and returns products grouped by category.

    Uses HYBRID scoring combining:
    - Keyword matching (exact/partial)
    - Style/color/material attribute matching
    - Semantic similarity (vector embeddings) when semantic_query is provided

    Args:
        selected_categories: List of CategoryRecommendation from ChatGPT analysis
        db: Database session
        selected_stores: Optional list of store names to filter by
        limit_per_category: Max products per category (0 = no limit, return ALL scored products)
        style_attributes: Optional dict with style preferences from ChatGPT analysis
            - style_keywords: List of style terms (e.g., ["modern", "minimalist"])
            - colors: List of color preferences (e.g., ["beige", "gray", "neutral"])
            - materials: List of material preferences (e.g., ["wood", "leather", "velvet"])
        size_keywords: Optional list of size/type keywords (e.g., ["3 seater", "sectional"])
        semantic_query: Optional search query for semantic similarity matching

    Returns:
        Dict mapping category_id to list of product dicts (sorted by score descending)
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
    logger.info(f"[CATEGORY RECS] Size keywords: {size_keywords}")

    # Get semantic similarity scores if query provided
    semantic_scores: Dict[int, float] = {}
    if semantic_query:
        logger.info(f"[CATEGORY RECS] Running semantic search for: {semantic_query[:50]}...")
        semantic_scores = await _semantic_search(
            query_text=semantic_query, db=db, store_filter=selected_stores, limit=500  # Get top 500 for each category's pool
        )
        logger.info(f"[CATEGORY RECS] Got {len(semantic_scores)} semantic scores")

    # Normalize size keywords for flexible matching
    # Map various formats to a standard form for database search
    size_keyword_normalizations = {
        "single-seater": "single seater",
        "single": "single seater",
        "one seater": "single seater",
        "1 seater": "single seater",
        "two-seater": "two seater",
        "2 seater": "two seater",
        "three-seater": "three seater",
        "3 seater": "three seater",
        "four-seater": "four seater",
        "4 seater": "four seater",
        "five-seater": "five seater",
        "5 seater": "five seater",
        "six-seater": "six seater",
        "6 seater": "six seater",
        "l-shaped": "l shaped",
        "sectional": "sectional",
    }

    normalized_sizes = []
    if size_keywords:
        for size in size_keywords:
            size_lower = size.lower()
            if size_lower in size_keyword_normalizations:
                normalized_sizes.append(size_keyword_normalizations[size_lower])
            else:
                normalized_sizes.append(size_lower)

    logger.info(f"[CATEGORY RECS] Normalized sizes: {normalized_sizes}")

    products_by_category: Dict[str, List[dict]] = {}

    async def fetch_category_products(category: CategoryRecommendation) -> Tuple[str, List[dict]]:
        """Fetch products for a single category"""
        try:
            category_id = category.category_id
            keywords = CATEGORY_KEYWORDS.get(category_id, [category_id.replace("_", " ")])
            exclusions = CATEGORY_EXCLUSIONS.get(category_id, [])
            priority_keywords = CATEGORY_PRIORITY_KEYWORDS.get(category_id, [])
            special_handling = CATEGORY_SPECIAL_HANDLING.get(category_id)

            logger.info(f"[CATEGORY RECS] Fetching {category_id} with keywords: {keywords}, exclusions: {exclusions}")

            # =====================================================================
            # SPECIAL HANDLING: For categories that need parent category + product name filter
            # e.g., cushion_covers searches in "Cushion" category but filters to "cover" in name
            # =====================================================================
            if special_handling:
                parent_keywords = special_handling.get("parent_category_keywords", [])
                name_filters = special_handling.get("product_name_filters", [])

                # Find parent category
                parent_conditions = [Category.name.ilike(f"%{kw}%") for kw in parent_keywords]
                parent_query = select(Category.id, Category.name).where(or_(*parent_conditions))
                parent_result = await db.execute(parent_query)
                parent_matches = [(row[0], row[1]) for row in parent_result.fetchall()]
                parent_category_ids = [row[0] for row in parent_matches]

                logger.info(f"[SPECIAL HANDLING] {category_id}: Found parent categories: {[row[1] for row in parent_matches]}")

                if parent_category_ids and name_filters:
                    # Build query with parent category + product name filter
                    name_conditions = [Product.name.ilike(f"%{nf}%") for nf in name_filters]
                    query = (
                        select(Product)
                        .join(Category, Product.category_id == Category.id, isouter=True)
                        .options(selectinload(Product.images), selectinload(Product.attributes))
                        .where(
                            Product.is_available.is_(True),
                            Product.category_id.in_(parent_category_ids),
                            or_(*name_conditions),
                        )
                    )

                    # Apply store filter if provided
                    if selected_stores:
                        query = query.where(Product.source_website.in_(selected_stores))

                    # NOTE: Budget is NOT filtered here at SQL level
                    # Instead, budget is used as a scoring factor in RankingService
                    # Products over budget get lower scores but are still shown

                    # Execute query - no limit, get ALL products for scoring
                    result = await db.execute(query)
                    products = result.scalars().all()

                    logger.info(
                        f"[SPECIAL HANDLING] {category_id}: Found {len(products)} products with name filters {name_filters}"
                    )

                    # Convert to dict format
                    product_list = [
                        {
                            "id": p.id,
                            "name": p.name,
                            "price": float(p.price) if p.price else 0,
                            "currency": p.currency or "INR",
                            "brand": p.brand,
                            "source_website": p.source_website,
                            "source_url": p.source_url,
                            "is_on_sale": p.is_on_sale or False,
                            "style_score": 100.0,
                            "description": p.description,
                            "primary_image": (
                                {"url": p.images[0].original_url, "alt_text": p.images[0].alt_text} if p.images else None
                            ),
                        }
                        for p in products
                    ]

                    return category_id, product_list

            # =====================================================================
            # CATEGORY-FIRST FILTERING with SIZE-SPECIFIC PRIORITIZATION
            # First find matching database categories, prioritizing size-specific
            # categories when size keywords are present (e.g., "Single Seater Sofa"
            # when user searches for "single-seater sofas")
            # =====================================================================

            matching_category_ids = []

            # Step 1A: If size keywords are present, first try to find specific category matches
            # E.g., "single seater" + "sofa" -> find "Single Seater Sofa" category
            if normalized_sizes:
                specific_category_conditions = []
                for size in normalized_sizes:
                    for keyword in keywords:
                        # Look for categories containing both size AND category keyword
                        specific_category_conditions.append(
                            Category.name.ilike(f"%{size}%") & Category.name.ilike(f"%{keyword}%")
                        )

                if specific_category_conditions:
                    specific_query = select(Category.id, Category.name).where(or_(*specific_category_conditions))
                    specific_result = await db.execute(specific_query)
                    specific_matches = [(row[0], row[1]) for row in specific_result.fetchall()]

                    if specific_matches:
                        matching_category_ids = [row[0] for row in specific_matches]
                        matched_names = [row[1] for row in specific_matches]
                        logger.info(
                            f"[CATEGORY RECS] Found {len(matching_category_ids)} SIZE-SPECIFIC categories: {matched_names}"
                        )

            # Step 1B: If no specific matches found, fall back to general category matching
            if not matching_category_ids:
                category_conditions = []
                for keyword in keywords:
                    category_conditions.append(Category.name.ilike(f"%{keyword}%"))

                # Query for matching category IDs
                category_query = select(Category.id, Category.name).where(
                    or_(*category_conditions) if category_conditions else True
                )
                category_result = await db.execute(category_query)
                general_matches = [(row[0], row[1]) for row in category_result.fetchall()]
                matching_category_ids = [row[0] for row in general_matches]
                matched_names = [row[1] for row in general_matches]
                logger.info(f"[CATEGORY RECS] Found {len(matching_category_ids)} GENERAL categories: {matched_names}")

            logger.info(f"[CATEGORY RECS] Final matching category IDs for {category_id}: {matching_category_ids}")

            # Step 2: Build product query with category-first filtering
            if matching_category_ids:
                # Primary filter: products in matching categories
                query = (
                    select(Product)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .options(selectinload(Product.images), selectinload(Product.attributes))
                    .where(Product.is_available.is_(True), Product.category_id.in_(matching_category_ids))
                )
                logger.info(f"[CATEGORY RECS] Using category-first filtering with {len(matching_category_ids)} category IDs")
            else:
                # Fallback: no matching categories found, use keyword matching on product name
                # This ensures we still return results even if category names don't match
                keyword_conditions = []
                for keyword in keywords:
                    keyword_conditions.append(Product.name.ilike(f"%{keyword}%"))

                query = (
                    select(Product)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .options(selectinload(Product.images), selectinload(Product.attributes))
                    .where(Product.is_available.is_(True), or_(*keyword_conditions) if keyword_conditions else True)
                )
                logger.info(f"[CATEGORY RECS] Fallback to keyword matching (no matching categories found)")

            # Build exclusion filter - exclude products with these terms
            exclusion_conditions = []
            for exclusion in exclusions:
                exclusion_conditions.append(~Product.name.ilike(f"%{exclusion}%"))

            # Apply exclusion filters
            for excl_condition in exclusion_conditions:
                query = query.where(excl_condition)

            # Apply store filter if provided
            if selected_stores:
                query = query.where(Product.source_website.in_(selected_stores))

            # NOTE: Budget is NOT filtered here at SQL level
            # Instead, budget is used as a scoring factor in RankingService
            # Products over budget get lower scores but are still shown
            # This ensures ALL products are displayed, ranked by relevance

            # Fetch ALL products in this category for scoring
            result = await db.execute(query)
            products = result.scalars().all()

            logger.info(f"[CATEGORY RECS] {category_id}: Fetched {len(products)} candidate products for scoring")

            # =================================================================
            # RANKING: Use deterministic weighted scoring via RankingService
            # Formula: 0.45*vector + 0.15*attribute + 0.15*style + 0.10*material_color + 0.10*budget + 0.05*text_intent
            # Higher score = better match (inverse of old scoring)
            # Budget scoring: within budget=1.0, 20% over=0.7, 50% over=0.4, >50% over=0.2
            # =================================================================
            ranking_service = get_ranking_service()

            # Get query embedding for text intent scoring
            query_embedding = None
            if semantic_query:
                embedding_service = get_embedding_service()
                query_embedding = await embedding_service.get_query_embedding(semantic_query)

            # Extract user preferences for ranking
            # Use first style keyword as primary style, second as secondary
            user_primary_style = style_keywords[0] if style_keywords else None
            user_secondary_style = style_keywords[1] if len(style_keywords) > 1 else None
            user_type = normalized_sizes[0] if normalized_sizes else None
            user_color = preferred_colors[0] if preferred_colors else None

            # Get category ID for attribute matching
            user_category_id = matching_category_ids[0] if matching_category_ids else None

            # Use user's total budget for scoring (not category allocation)
            # Any product under the user's total budget scores 1.0
            if user_total_budget:
                logger.info(f"[RANKING] {category_id}: Using user's total budget ₹{user_total_budget:,.0f} for scoring")

            # Rank products using the new weighted scoring system
            ranked_products = ranking_service.rank_products(
                products=products,
                vector_scores=semantic_scores,
                query_embedding=query_embedding,
                user_category=user_category_id,
                user_type=user_type,
                user_capacity=None,  # Could be extracted from query if needed
                user_primary_style=user_primary_style,
                user_secondary_style=user_secondary_style,
                user_materials=preferred_materials if preferred_materials else None,
                user_color=user_color,
                user_budget_max=user_total_budget,  # Use user's total budget, not category allocation
            )

            # Log top ranked products for debugging
            if ranked_products:
                logger.info(
                    f"[RANKING] {category_id}: Top 3 products - "
                    + ", ".join([f"{rp.product.id}:{rp.final_score:.3f}" for rp in ranked_products[:3]])
                )
                # Log breakdown for top product
                if ranked_products[0].breakdown:
                    logger.info(f"[RANKING] Top product breakdown: {ranked_products[0].breakdown}")

            # Convert to scored_products format for compatibility with downstream code
            # Note: Higher score is now better (inverted from old system)
            scored_products = [(rp.product, rp.final_score, rp.breakdown) for rp in ranked_products]

            # Log style matching results
            if user_primary_style or preferred_colors or preferred_materials:
                high_score_count = sum(1 for _, score, _ in scored_products if score > 0.5)
                logger.info(f"[RANKING] {category_id}: {high_score_count}/{len(scored_products)} products scored > 0.5")

            # Take only the limit we need (0 = no limit, return all scored products)
            if limit_per_category > 0:
                top_products = scored_products[:limit_per_category]
            else:
                top_products = scored_products  # Return all products, sorted by score

            # Convert to product dicts with explainable ranking breakdown
            product_list = []
            for product, final_score, breakdown in top_products:
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
                    "ranking_score": final_score,  # New deterministic score (higher = better)
                    "ranking_breakdown": breakdown,  # Explainable score components
                    "description": product.description,  # Include for AI visualization context
                    "primary_image": {
                        "url": primary_image.original_url if primary_image else None,
                        "alt_text": primary_image.alt_text if primary_image else product.name,
                    }
                    if primary_image
                    else None,
                    # Include attributes for visualization (especially dimensions: width, height, depth)
                    "attributes": [
                        {"attribute_name": attr.attribute_name, "attribute_value": attr.attribute_value}
                        for attr in product.attributes
                    ]
                    if product.attributes
                    else [],
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


# ============================================================================
# Paginated Products Endpoint for Infinite Scroll
# ============================================================================


def _build_style_score_expression(
    style_keywords: List[str],
    preferred_colors: List[str],
    preferred_materials: List[str],
    size_keywords: List[str],
):
    """
    Build a SQL CASE expression that approximates style scoring.
    This allows efficient database-side sorting and cursor-based pagination.

    Score ranges (lower = better match):
    - Size/type match in name: -20 to -10
    - Style keyword match: 5 to 15
    - Color match: 20 to 30
    - Material match: 35 to 45
    - No match: 100

    Returns: SQLAlchemy column expression for computed score
    """
    score_cases = []

    # Size/type keywords get the best scores (most important for relevance)
    for idx, size in enumerate(size_keywords[:5]):  # Limit to first 5
        size_lower = size.lower()
        score_cases.append((Product.name.ilike(f"%{size_lower}%"), literal(-20.0 + idx * 2)))

    # Style keyword matches
    for idx, style in enumerate(style_keywords[:5]):
        style_lower = style.lower()
        score_cases.append((Product.name.ilike(f"%{style_lower}%"), literal(5.0 + idx * 2)))
        score_cases.append((Product.description.ilike(f"%{style_lower}%"), literal(10.0 + idx * 2)))

    # Color matches
    for idx, color in enumerate(preferred_colors[:5]):
        color_lower = color.lower()
        score_cases.append((Product.name.ilike(f"%{color_lower}%"), literal(20.0 + idx * 2)))
        score_cases.append((Product.description.ilike(f"%{color_lower}%"), literal(25.0 + idx * 2)))

    # Material matches
    for idx, material in enumerate(preferred_materials[:5]):
        material_lower = material.lower()
        score_cases.append((Product.name.ilike(f"%{material_lower}%"), literal(35.0 + idx * 2)))
        score_cases.append((Product.description.ilike(f"%{material_lower}%"), literal(40.0 + idx * 2)))

    # Return CASE expression with default score of 100 for non-matching products
    if score_cases:
        return case(*score_cases, else_=literal(100.0))
    else:
        return literal(100.0)


@router.post("/sessions/{session_id}/products/paginated", response_model=PaginatedProductsResponse)
async def get_paginated_products(
    session_id: str,
    request: PaginatedProductsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated products for a category with consistent style-based ordering.
    Uses cursor pagination for efficiency and consistency.

    This endpoint is used for infinite scroll - after the initial product load,
    subsequent pages are fetched using this endpoint with the cursor from the previous response.
    """
    try:
        logger.info(f"[PAGINATED] Fetching page for category '{request.category_id}', page_size={request.page_size}")

        # Extract style attributes for scoring
        style_attrs = request.style_attributes or {}
        style_keywords = style_attrs.get("style_keywords", [])
        preferred_colors = style_attrs.get("colors", [])
        preferred_materials = style_attrs.get("materials", [])
        size_keywords = style_attrs.get("size_keywords", [])

        # Build the style score expression for SQL-level scoring
        score_expr = _build_style_score_expression(
            style_keywords=style_keywords,
            preferred_colors=preferred_colors,
            preferred_materials=preferred_materials,
            size_keywords=size_keywords,
        )

        # Map category_id to database category keywords
        # This matches the logic in _get_category_based_recommendations
        category_keywords = _get_category_keywords(request.category_id)

        # Build base query with filters
        query = (
            select(Product, score_expr.label("computed_score"))
            .options(selectinload(Product.images), selectinload(Product.attributes))
            .where(Product.is_available.is_(True))
        )

        # Apply category filter using keywords
        if category_keywords:
            category_conditions = []
            for keyword in category_keywords:
                category_conditions.append(Product.name.ilike(f"%{keyword}%"))
            query = query.where(or_(*category_conditions))

        # Apply budget filters
        if request.budget_min is not None:
            query = query.where(Product.price >= request.budget_min)
        if request.budget_max is not None:
            query = query.where(Product.price <= request.budget_max)

        # Apply store filter
        if request.selected_stores:
            query = query.where(Product.source_website.in_(request.selected_stores))

        # Apply cursor for pagination (fetch items AFTER the cursor position)
        if request.cursor:
            # Cursor-based pagination: get items where (score > cursor_score) OR (score == cursor_score AND id > cursor_id)
            query = query.where(
                or_(
                    score_expr > request.cursor.style_score,
                    and_(
                        score_expr == request.cursor.style_score,
                        Product.id > request.cursor.product_id,
                    ),
                )
            )

        # Order by score (ascending = best first), then by id for deterministic ordering
        query = query.order_by(score_expr.asc(), Product.id.asc())

        # Fetch one extra to check if there are more pages
        query = query.limit(request.page_size + 1)

        # Execute query
        result = await db.execute(query)
        rows = result.all()

        # Check if there are more results
        has_more = len(rows) > request.page_size
        products_rows = rows[: request.page_size]

        # Build next cursor from the last item
        next_cursor = None
        if has_more and products_rows:
            last_row = products_rows[-1]
            next_cursor = PaginationCursor(
                style_score=float(last_row.computed_score),
                product_id=last_row.Product.id,
            )

        # Convert to product dicts (same format as _get_category_based_recommendations)
        products = []
        for row in products_rows:
            product = row.Product
            computed_score = row.computed_score

            primary_image = None
            if product.images:
                primary_image = next(
                    (img for img in product.images if img.is_primary),
                    product.images[0] if product.images else None,
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
                "style_score": float(computed_score),
                "description": product.description,
                "primary_image": {
                    "url": primary_image.original_url if primary_image else None,
                    "alt_text": primary_image.alt_text if primary_image else product.name,
                }
                if primary_image
                else None,
                "attributes": [
                    {"attribute_name": attr.attribute_name, "attribute_value": attr.attribute_value}
                    for attr in product.attributes
                ]
                if product.attributes
                else [],
            }
            products.append(product_dict)

        # Get estimated total count (cached count query for performance)
        total_estimated = await _get_category_product_count(request.category_id, category_keywords, db)

        logger.info(
            f"[PAGINATED] Returning {len(products)} products for '{request.category_id}', has_more={has_more}, total_estimated={total_estimated}"
        )

        return PaginatedProductsResponse(
            products=products,
            next_cursor=next_cursor,
            has_more=has_more,
            total_estimated=total_estimated,
        )

    except Exception as e:
        import traceback

        logger.error(f"Error fetching paginated products: {e}\n{traceback.format_exc()}")
        error_type = type(e).__name__
        raise HTTPException(status_code=500, detail=f"{error_type}: {str(e)}")


def _get_category_keywords(category_id: str) -> List[str]:
    """
    Map category_id to search keywords for product matching.
    This is a simplified version of the category mapping used in _get_category_based_recommendations.
    """
    # Common category keyword mappings
    category_keyword_map = {
        "sofas": ["sofa", "couch", "sectional", "loveseat", "settee"],
        "chairs": ["chair", "armchair", "accent chair", "lounge chair"],
        "coffee_tables": ["coffee table", "center table"],
        "side_tables": ["side table", "end table", "accent table"],
        "dining_tables": ["dining table"],
        "dining_chairs": ["dining chair"],
        "beds": ["bed", "bedframe"],
        "wardrobes": ["wardrobe", "closet", "armoire"],
        "dressers": ["dresser", "chest of drawers"],
        "nightstands": ["nightstand", "bedside table"],
        "desks": ["desk", "writing desk", "computer desk"],
        "office_chairs": ["office chair", "desk chair", "ergonomic chair"],
        "bookcases": ["bookcase", "bookshelf", "shelving"],
        "tv_stands": ["tv stand", "tv unit", "media console", "entertainment center"],
        "rugs": ["rug", "carpet", "area rug"],
        "curtains": ["curtain", "drape", "window treatment"],
        "lighting": ["lamp", "light", "chandelier", "pendant", "sconce"],
        "mirrors": ["mirror", "wall mirror"],
        "artwork": ["art", "painting", "print", "poster", "wall art"],
        "wallpapers": ["wallpaper", "wallpapers", "wall paper", "wall covering"],
        "planters": ["planter", "pot", "vase"],
        "decor_accents": ["decor", "accent", "decorative", "ornament"],
        "cushions": ["cushion", "pillow", "throw pillow"],
        "throws": ["throw", "blanket"],
        "storage": ["storage", "basket", "bin", "organizer"],
    }

    # Return keywords for the category, or use the category_id itself as a keyword
    return category_keyword_map.get(category_id, [category_id.replace("_", " ")])


async def _get_category_product_count(category_id: str, category_keywords: List[str], db: AsyncSession) -> int:
    """
    Get estimated product count for a category.
    Uses a simple count query with category keyword matching.
    """
    try:
        count_query = select(func.count(Product.id)).where(Product.is_available.is_(True))

        if category_keywords:
            category_conditions = []
            for keyword in category_keywords:
                category_conditions.append(Product.name.ilike(f"%{keyword}%"))
            count_query = count_query.where(or_(*category_conditions))

        result = await db.execute(count_query)
        count = result.scalar() or 0
        return count

    except Exception as e:
        logger.warning(f"Error getting category count for {category_id}: {e}")
        return 0
