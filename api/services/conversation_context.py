"""
Conversation context management for maintaining chat session state and memory
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import pickle
import hashlib

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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            **asdict(self),
            "last_updated": self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Create from dictionary"""
        data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        # Handle backward compatibility for new fields
        if "last_uploaded_image" not in data:
            data["last_uploaded_image"] = None
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
            last_uploaded_image=None
        )

        self.contexts[session_id] = context
        logger.info(f"Created new conversation context for session {session_id}")
        return context

    def add_message(self, session_id: str, role: str, content: str,
                   metadata: Optional[Dict[str, Any]] = None) -> ConversationContext:
        """Add message to conversation context"""
        context = self.get_or_create_context(session_id)

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        context.messages.append(message)
        context.total_interactions += 1
        context.last_updated = datetime.now()

        # Trim context if too long
        if len(context.messages) > self.max_context_length:
            # Keep system messages and recent messages
            system_messages = [msg for msg in context.messages if msg["role"] == "system"]
            recent_messages = context.messages[-(self.max_context_length - len(system_messages)):]
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
            "analysis_id": self._generate_analysis_id(analysis)
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
            "last_updated": context.user_preferences.get("last_updated", "")
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
            "session_duration": (datetime.now() - context.last_updated).total_seconds()
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

        recent_content = " ".join([
            msg["content"].lower()
            for msg in context.messages[-3:]
            if msg["role"] == "user"
        ])

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

            # Extract style preferences
            style_prefs = design_analysis.get("style_preferences", {})
            if style_prefs:
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
            if color_scheme:
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
            if budget:
                context.user_preferences["budget_range"] = budget.get("price_range", "unknown")

            # Update confidence and timestamp
            context.user_preferences["confidence_score"] = analysis.get("confidence_scores", {}).get("overall_analysis", 0)
            context.user_preferences["last_updated"] = datetime.now().isoformat()

        except Exception as e:
            logger.warning(f"Error extracting preferences from analysis: {e}")

    def _build_enhanced_system_prompt(self, context: ConversationContext) -> str:
        """Build enhanced system prompt with context"""
        base_prompt = """You are an expert interior designer and product analyst with deep knowledge of furniture, decor, color theory, spatial design, and current design trends. You MUST respond in valid JSON format with structured design analysis."""

        # Add user preferences context
        if context.user_preferences:
            prefs_summary = self.get_user_preferences_summary(context.session_id)
            if prefs_summary["style_preferences"]:
                base_prompt += f"\n\nUser's preferred styles: {', '.join(prefs_summary['style_preferences'])}"
            if prefs_summary["color_preferences"]:
                base_prompt += f"\nUser's color preferences: {', '.join(prefs_summary['color_preferences'])}"
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