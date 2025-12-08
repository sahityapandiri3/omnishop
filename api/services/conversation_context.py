"""
Conversation context management for maintaining chat session state and memory
"""
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Represents conversation context for a session"""

    session_id: str
    user_id: Optional[str]
    messages: List[Dict[str, Any]]
    user_preferences: Dict[str, Any]
    design_analysis_history: List[Dict[str, Any]]
    current_room_context: Optional[Dict[str, Any]]
    conversation_state: str  # "new", "active", "design_focused", "product_selection"
    last_updated: datetime
    total_interactions: int
    last_uploaded_image: Optional[str] = None  # Store last uploaded image for transformations
    pending_action_options: Optional[Dict[str, Any]] = None  # Store pending action options (A, B, C, etc.)
    visualization_history: List[Dict[str, Any]] = None  # Stack of visualization states for undo/redo
    visualization_redo_stack: List[Dict[str, Any]] = None  # Stack for redo operations
    # Accumulated search filters for conversational context understanding
    accumulated_filters: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {**asdict(self), "last_updated": self.last_updated.isoformat()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Create from dictionary"""
        data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        # Handle backward compatibility for new fields
        if "last_uploaded_image" not in data:
            data["last_uploaded_image"] = None
        if "pending_action_options" not in data:
            data["pending_action_options"] = None
        if "visualization_history" not in data:
            data["visualization_history"] = []
        if "visualization_redo_stack" not in data:
            data["visualization_redo_stack"] = []
        if "accumulated_filters" not in data:
            data["accumulated_filters"] = None
        return cls(**data)


class ConversationContextManager:
    """Manages conversation context across sessions"""

    def __init__(self, max_context_length: int = 20, context_ttl_hours: int = 24):
        self.max_context_length = max_context_length
        self.context_ttl = timedelta(hours=context_ttl_hours)
        self.contexts: Dict[str, ConversationContext] = {}
        self.user_preferences_cache: Dict[str, Dict[str, Any]] = {}

        logger.info(f"Conversation context manager initialized - Max length: {max_context_length}, TTL: {context_ttl_hours}h")

    def get_or_create_context(self, session_id: str, user_id: Optional[str] = None) -> ConversationContext:
        """Get existing context or create new one"""
        if session_id in self.contexts:
            context = self.contexts[session_id]

            # Check if context has expired
            if datetime.now() - context.last_updated > self.context_ttl:
                logger.info(f"Context expired for session {session_id}, creating new one")
                del self.contexts[session_id]
            else:
                return context

        # Create new context
        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            messages=[],
            user_preferences=self._get_user_preferences(user_id) if user_id else {},
            design_analysis_history=[],
            current_room_context=None,
            conversation_state="new",
            last_updated=datetime.now(),
            total_interactions=0,
            last_uploaded_image=None,
            visualization_history=[],
            visualization_redo_stack=[],
            accumulated_filters=self._get_default_accumulated_filters(),
        )

        self.contexts[session_id] = context
        logger.info(f"Created new conversation context for session {session_id}")
        return context

    def add_message(
        self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationContext:
        """Add message to conversation context"""
        context = self.get_or_create_context(session_id)

        message = {"role": role, "content": content, "timestamp": datetime.now().isoformat(), "metadata": metadata or {}}

        context.messages.append(message)
        context.total_interactions += 1
        context.last_updated = datetime.now()

        # Trim context if too long
        if len(context.messages) > self.max_context_length:
            # Keep system messages and recent messages
            system_messages = [msg for msg in context.messages if msg["role"] == "system"]
            recent_messages = context.messages[-(self.max_context_length - len(system_messages)) :]
            context.messages = system_messages + recent_messages

        # Update conversation state based on content
        context.conversation_state = self._determine_conversation_state(context)

        return context

    def add_design_analysis(self, session_id: str, analysis: Dict[str, Any]) -> ConversationContext:
        """Add design analysis to context history"""
        context = self.get_or_create_context(session_id)

        analysis_entry = {
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "analysis_id": self._generate_analysis_id(analysis),
        }

        context.design_analysis_history.append(analysis_entry)
        context.last_updated = datetime.now()

        # Extract and update user preferences from analysis
        self._extract_preferences_from_analysis(context, analysis)

        # Update room context if spatial analysis is present
        if "space_analysis" in analysis.get("design_analysis", {}):
            context.current_room_context = analysis["design_analysis"]["space_analysis"]

        return context

    def update_room_context(self, session_id: str, room_data: Dict[str, Any]) -> ConversationContext:
        """Update current room context"""
        context = self.get_or_create_context(session_id)
        context.current_room_context = room_data
        context.last_updated = datetime.now()
        return context

    def store_image(self, session_id: str, image_data: str) -> ConversationContext:
        """Store image data in conversation context"""
        context = self.get_or_create_context(session_id)
        context.last_uploaded_image = image_data
        context.last_updated = datetime.now()
        logger.info(f"Stored image for session {session_id}")
        return context

    def get_last_image(self, session_id: str) -> Optional[str]:
        """Get last uploaded image from conversation context"""
        context = self.get_or_create_context(session_id)
        return context.last_uploaded_image

    def store_pending_action_options(
        self,
        session_id: str,
        action_options: Dict[str, Any],
        detected_furniture: list,
        selected_product_id: str,
        room_image: str,
    ) -> ConversationContext:
        """Store pending action options with associated data for letter choice detection"""
        context = self.get_or_create_context(session_id)
        context.pending_action_options = {
            "action_options": action_options,
            "detected_furniture": detected_furniture,
            "selected_product_id": selected_product_id,
            "room_image": room_image,
            "timestamp": datetime.now().isoformat(),
        }
        context.last_updated = datetime.now()
        logger.info(f"Stored pending action options for session {session_id}")
        return context

    def get_pending_action_options(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get pending action options if available"""
        context = self.get_or_create_context(session_id)
        return context.pending_action_options

    def clear_pending_action_options(self, session_id: str) -> ConversationContext:
        """Clear pending action options after they've been used"""
        context = self.get_or_create_context(session_id)
        context.pending_action_options = None
        context.last_updated = datetime.now()
        logger.info(f"Cleared pending action options for session {session_id}")
        return context

    def push_visualization_state(self, session_id: str, visualization_data: Dict[str, Any]) -> ConversationContext:
        """Push visualization state to history for undo/redo support"""
        context = self.get_or_create_context(session_id)

        # Initialize if None
        if context.visualization_history is None:
            context.visualization_history = []
        if context.visualization_redo_stack is None:
            context.visualization_redo_stack = []

        # Add timestamp to visualization data
        vis_state = {**visualization_data, "timestamp": datetime.now().isoformat()}

        # Push to history stack
        context.visualization_history.append(vis_state)

        # Clear redo stack when new visualization is added
        context.visualization_redo_stack = []

        # Limit history size to prevent memory issues (keep last 20 states)
        if len(context.visualization_history) > 20:
            context.visualization_history = context.visualization_history[-20:]

        context.last_updated = datetime.now()
        logger.info(
            f"Pushed visualization state to history for session {session_id}. History size: {len(context.visualization_history)}"
        )
        return context

    def undo_visualization(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Undo last visualization and return previous state"""
        context = self.get_or_create_context(session_id)

        # Initialize if None
        if context.visualization_history is None:
            context.visualization_history = []
        if context.visualization_redo_stack is None:
            context.visualization_redo_stack = []

        # If no history at all, cannot undo
        if len(context.visualization_history) == 0:
            logger.info(f"Cannot undo: no visualization history for session {session_id}")
            return None

        # If only 1 visualization exists, undo should return the original uploaded image
        if len(context.visualization_history) == 1:
            # Pop current state and move to redo stack
            current_state = context.visualization_history.pop()
            context.visualization_redo_stack.append(current_state)

            # Return original uploaded image as the previous state
            context.last_updated = datetime.now()
            logger.info(
                f"Undo to original image for session {session_id}. History: {len(context.visualization_history)}, Redo: {len(context.visualization_redo_stack)}"
            )

            return {
                "image": context.last_uploaded_image,
                "timestamp": datetime.now().isoformat(),
                "is_original": True,
            }

        # If 2+ visualizations, pop current and return previous
        # Pop current state and move to redo stack
        current_state = context.visualization_history.pop()
        context.visualization_redo_stack.append(current_state)

        # Get previous state (now at top of history)
        previous_state = context.visualization_history[-1]

        context.last_updated = datetime.now()
        logger.info(
            f"Undo visualization for session {session_id}. History: {len(context.visualization_history)}, Redo: {len(context.visualization_redo_stack)}"
        )

        return previous_state

    def redo_visualization(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Redo visualization and return next state"""
        context = self.get_or_create_context(session_id)

        # Initialize if None
        if context.visualization_history is None:
            context.visualization_history = []
        if context.visualization_redo_stack is None:
            context.visualization_redo_stack = []

        # Need at least 1 item in redo stack
        if len(context.visualization_redo_stack) == 0:
            logger.info(f"Cannot redo: empty redo stack for session {session_id}")
            return None

        # Pop from redo stack and push back to history
        next_state = context.visualization_redo_stack.pop()
        context.visualization_history.append(next_state)

        context.last_updated = datetime.now()
        logger.info(
            f"Redo visualization for session {session_id}. History: {len(context.visualization_history)}, Redo: {len(context.visualization_redo_stack)}"
        )

        return next_state

    def can_undo(self, session_id: str) -> bool:
        """Check if undo is available"""
        context = self.get_or_create_context(session_id)
        if context.visualization_history is None:
            return False
        # Can undo if there is at least 1 visualization (allows undoing back to original uploaded room)
        return len(context.visualization_history) >= 1

    def can_redo(self, session_id: str) -> bool:
        """Check if redo is available"""
        context = self.get_or_create_context(session_id)
        if context.visualization_redo_stack is None:
            return False
        return len(context.visualization_redo_stack) > 0

    def get_context_for_ai(self, session_id: str, include_system_prompt: bool = True) -> List[Dict[str, Any]]:
        """Get formatted context for AI model"""
        context = self.get_or_create_context(session_id)

        ai_context = []

        if include_system_prompt:
            # Add enhanced system prompt with context
            system_prompt = self._build_enhanced_system_prompt(context)
            ai_context.append({"role": "system", "content": system_prompt})

        # Add recent messages (excluding system messages to avoid duplication)
        recent_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in context.messages[-10:]  # Last 10 messages
            if msg["role"] != "system"
        ]

        ai_context.extend(recent_messages)
        return ai_context

    def get_user_preferences_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summarized user preferences"""
        context = self.get_or_create_context(session_id)
        return {
            "style_preferences": context.user_preferences.get("styles", []),
            "color_preferences": context.user_preferences.get("colors", []),
            "material_preferences": context.user_preferences.get("materials", []),
            "budget_range": context.user_preferences.get("budget_range", "unknown"),
            "room_types": context.user_preferences.get("room_types", []),
            "confidence_score": context.user_preferences.get("confidence_score", 0.0),
            "last_updated": context.user_preferences.get("last_updated", ""),
        }

    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Get conversation summary and insights"""
        context = self.get_or_create_context(session_id)

        return {
            "session_id": session_id,
            "conversation_state": context.conversation_state,
            "total_interactions": context.total_interactions,
            "message_count": len(context.messages),
            "analysis_count": len(context.design_analysis_history),
            "has_room_context": context.current_room_context is not None,
            "user_preferences": self.get_user_preferences_summary(session_id),
            "last_updated": context.last_updated.isoformat(),
            "session_duration": (datetime.now() - context.last_updated).total_seconds(),
        }

    def clear_context(self, session_id: str) -> bool:
        """Clear conversation context for session"""
        if session_id in self.contexts:
            del self.contexts[session_id]
            logger.info(f"Cleared context for session {session_id}")
            return True
        return False

    def cleanup_expired_contexts(self) -> int:
        """Remove expired contexts"""
        expired_sessions = []
        now = datetime.now()

        for session_id, context in self.contexts.items():
            if now - context.last_updated > self.context_ttl:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self.contexts[session_id]

        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired contexts")

        return len(expired_sessions)

    # ==================== Accumulated Filters Management ====================

    def _get_default_accumulated_filters(self) -> Dict[str, Any]:
        """Get default accumulated filters structure"""
        return {
            "category": None,  # Last searched category (e.g., "sofas", "tables")
            "furniture_type": None,  # Specific furniture type
            "product_types": [],  # Product types list
            "price_min": None,  # Price range minimum
            "price_max": None,  # Price range maximum
            "style": None,  # Style preference (modern, traditional)
            "color": None,  # Color preference
            "material": None,  # Material preference
            "room_type": None,  # Living room, bedroom, etc.
            "search_terms": [],  # Search terms from user queries
        }

    def update_accumulated_filters(
        self, session_id: str, new_filters: Dict[str, Any], category_changed: bool = False
    ) -> ConversationContext:
        """
        Update accumulated filters for a session.

        If category_changed is True, clears all other filters (auto-clear on category change behavior).
        Otherwise, merges new filters with existing ones (new values override old).

        Args:
            session_id: Session ID
            new_filters: New filter values to merge/set
            category_changed: If True, clear other filters when category changes

        Returns:
            Updated ConversationContext
        """
        context = self.get_or_create_context(session_id)

        # Initialize filters if None
        if context.accumulated_filters is None:
            context.accumulated_filters = self._get_default_accumulated_filters()

        # If category changed, clear all filters and start fresh with new category
        if category_changed:
            old_category = context.accumulated_filters.get("category")
            new_category = new_filters.get("category") or new_filters.get("furniture_type")

            if new_category and new_category != old_category:
                logger.info(f"Category changed from '{old_category}' to '{new_category}' - clearing other filters")
                context.accumulated_filters = self._get_default_accumulated_filters()

        # Merge new filters with existing (new values override old, but None/empty don't clear)
        for key, value in new_filters.items():
            if value is not None and value != "" and value != []:
                context.accumulated_filters[key] = value

        context.last_updated = datetime.now()
        logger.info(f"Updated accumulated filters for session {session_id}: {context.accumulated_filters}")
        return context

    def clear_accumulated_filters(self, session_id: str) -> ConversationContext:
        """Clear all accumulated filters for a session (e.g., on 'start fresh')"""
        context = self.get_or_create_context(session_id)
        context.accumulated_filters = self._get_default_accumulated_filters()
        context.last_updated = datetime.now()
        logger.info(f"Cleared accumulated filters for session {session_id}")
        return context

    def get_accumulated_filters(self, session_id: str) -> Dict[str, Any]:
        """Get accumulated filters for a session"""
        context = self.get_or_create_context(session_id)
        if context.accumulated_filters is None:
            context.accumulated_filters = self._get_default_accumulated_filters()
        return context.accumulated_filters

    def get_search_context_summary(self, session_id: str) -> str:
        """
        Generate a human-readable summary of current search context for AI.
        This helps the AI understand what filters are currently active.

        Returns:
            String summary of active filters, or empty string if no filters active
        """
        filters = self.get_accumulated_filters(session_id)

        # Build list of active filters
        active_parts = []

        if filters.get("category"):
            active_parts.append(f"Category: {filters['category']}")
        if filters.get("furniture_type"):
            active_parts.append(f"Furniture type: {filters['furniture_type']}")
        if filters.get("product_types"):
            active_parts.append(f"Product types: {', '.join(filters['product_types'])}")
        if filters.get("price_min") is not None or filters.get("price_max") is not None:
            price_min = filters.get("price_min", 0)
            price_max = filters.get("price_max", "unlimited")
            active_parts.append(f"Price range: ₹{price_min} - ₹{price_max}")
        if filters.get("style"):
            active_parts.append(f"Style: {filters['style']}")
        if filters.get("color"):
            active_parts.append(f"Color: {filters['color']}")
        if filters.get("material"):
            active_parts.append(f"Material: {filters['material']}")
        if filters.get("room_type"):
            active_parts.append(f"Room: {filters['room_type']}")

        if not active_parts:
            return ""

        summary = "CURRENT SEARCH CONTEXT (from previous messages):\n"
        summary += "- " + "\n- ".join(active_parts)
        summary += "\n\nApply these filters to follow-up queries unless user explicitly changes them."
        summary += "\nIf user asks for a DIFFERENT category/furniture type, CLEAR all other filters and start fresh."

        return summary

    def has_active_filters(self, session_id: str) -> bool:
        """Check if session has any active accumulated filters"""
        filters = self.get_accumulated_filters(session_id)
        return any(value is not None and value != "" and value != [] for key, value in filters.items())

    def export_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export context for persistence"""
        if session_id in self.contexts:
            return self.contexts[session_id].to_dict()
        return None

    def import_context(self, context_data: Dict[str, Any]) -> bool:
        """Import context from persistence"""
        try:
            context = ConversationContext.from_dict(context_data)
            self.contexts[context.session_id] = context
            logger.info(f"Imported context for session {context.session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to import context: {e}")
            return False

    def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get cached user preferences"""
        return self.user_preferences_cache.get(user_id, {})

    def _determine_conversation_state(self, context: ConversationContext) -> str:
        """Determine conversation state based on recent messages"""
        if not context.messages:
            return "new"

        recent_content = " ".join([msg["content"].lower() for msg in context.messages[-3:] if msg["role"] == "user"])

        # Simple keyword-based state detection
        if any(word in recent_content for word in ["room", "space", "visualize", "place", "layout"]):
            return "design_focused"
        elif any(word in recent_content for word in ["product", "furniture", "buy", "purchase", "recommend"]):
            return "product_selection"
        elif len(context.messages) > 2:
            return "active"
        else:
            return "new"

    def _extract_preferences_from_analysis(self, context: ConversationContext, analysis: Dict[str, Any]):
        """Extract user preferences from design analysis"""
        try:
            design_analysis = analysis.get("design_analysis", {})

            # Skip if design_analysis is not a dictionary
            if not isinstance(design_analysis, dict):
                logger.debug(f"design_analysis is not a dict, skipping preference extraction (type: {type(design_analysis)})")
                return

            # Extract style preferences
            style_prefs = design_analysis.get("style_preferences", {})
            if style_prefs and isinstance(style_prefs, dict):
                # Convert to set even if it's already stored as a list
                existing_styles = context.user_preferences.get("styles", [])
                styles = set(existing_styles) if isinstance(existing_styles, list) else existing_styles
                if not isinstance(styles, set):
                    styles = set()
                styles.add(style_prefs.get("primary_style", ""))
                styles.update(style_prefs.get("secondary_styles", []))
                context.user_preferences["styles"] = list(styles)

            # Extract color preferences
            color_scheme = design_analysis.get("color_scheme", {})
            if color_scheme and isinstance(color_scheme, dict):
                # Convert to set even if it's already stored as a list
                existing_colors = context.user_preferences.get("colors", [])
                colors = set(existing_colors) if isinstance(existing_colors, list) else existing_colors
                if not isinstance(colors, set):
                    colors = set()
                colors.update(color_scheme.get("preferred_colors", []))
                colors.update(color_scheme.get("accent_colors", []))
                context.user_preferences["colors"] = list(colors)

            # Extract budget indicators
            budget = design_analysis.get("budget_indicators", {})
            if budget and isinstance(budget, dict):
                context.user_preferences["budget_range"] = budget.get("price_range", "unknown")

            # Update confidence and timestamp
            confidence_scores = analysis.get("confidence_scores", {})
            if isinstance(confidence_scores, dict):
                context.user_preferences["confidence_score"] = confidence_scores.get("overall_analysis", 0)
            else:
                context.user_preferences["confidence_score"] = 0
            context.user_preferences["last_updated"] = datetime.now().isoformat()

        except Exception as e:
            logger.warning(f"Error extracting preferences from analysis: {e}")

    def _build_enhanced_system_prompt(self, context: ConversationContext) -> str:
        """Build enhanced system prompt with context"""
        base_prompt = """You are an expert interior designer and product analyst with deep knowledge of furniture, decor, color theory, spatial design, and current design trends. You MUST respond in valid JSON format with structured design analysis."""

        # Add user preferences context
        if context.user_preferences:
            prefs_summary = self.get_user_preferences_summary(context.session_id)
            # Filter out None values from preference lists before joining
            style_prefs = [s for s in prefs_summary["style_preferences"] if s is not None]
            if style_prefs:
                base_prompt += f"\n\nUser's preferred styles: {', '.join(style_prefs)}"
            color_prefs = [c for c in prefs_summary["color_preferences"] if c is not None]
            if color_prefs:
                base_prompt += f"\nUser's color preferences: {', '.join(color_prefs)}"
            if prefs_summary["budget_range"] != "unknown":
                base_prompt += f"\nUser's budget range: {prefs_summary['budget_range']}"

        # Add conversation state context
        base_prompt += f"\n\nConversation state: {context.conversation_state}"
        base_prompt += f"\nTotal interactions: {context.total_interactions}"

        # Add room context if available
        if context.current_room_context:
            room_type = context.current_room_context.get("room_type", "unknown")
            base_prompt += f"\nCurrent room context: {room_type}"

        base_prompt += "\n\nProvide helpful, personalized interior design advice based on this context. Always return your response as a JSON object with design analysis and a user-friendly message."

        return base_prompt

    def _generate_analysis_id(self, analysis: Dict[str, Any]) -> str:
        """Generate unique ID for analysis"""
        analysis_str = json.dumps(analysis, sort_keys=True, default=str)
        return hashlib.md5(analysis_str.encode()).hexdigest()[:12]


# Global context manager instance
conversation_context_manager = ConversationContextManager()
