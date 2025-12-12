"""
Chat logging utility for logging all conversations to chat.md
Logs user inputs and AI responses with user ID, session ID, and server type
"""
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import settings


class ChatLogger:
    """Logger for chat conversations to chat.md file"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Determine log file path - in project root
        self.log_file = Path(__file__).parent.parent.parent / "chat.md"

        # Determine server type from environment
        env = settings.environment.lower()
        if env in ["production", "prod"]:
            self.server_type = "prod"
        else:
            self.server_type = "local"

        # Create file with header if it doesn't exist
        if not self.log_file.exists():
            self._create_log_file()

        self._initialized = True

    def _create_log_file(self):
        """Create the chat.md file with a header"""
        header = """# Chat Conversation Log

This file logs all chat conversations across all users and sessions.

---

"""
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(header)

    def log_conversation(
        self,
        session_id: str,
        user_id: Optional[str],
        user_message: str,
        assistant_response: str,
    ):
        """
        Log a conversation exchange to chat.md

        Args:
            session_id: The chat session ID
            user_id: The user's ID (or None for anonymous)
            user_message: The user's input message
            assistant_response: The AI assistant's response
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        user_display = user_id if user_id else "anonymous"

        # Format the log entry
        log_entry = f"""
## [{timestamp}] | Server: {self.server_type} | Session: {session_id[:8]}... | User: {user_display}

**User:** {user_message}

**Assistant:** {assistant_response}

---
"""

        # Thread-safe write to file
        with self._lock:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception as e:
                # Don't crash the app if logging fails
                print(f"[ChatLogger] Failed to log conversation: {e}")

    def log_user_message(
        self,
        session_id: str,
        user_id: Optional[str],
        message: str,
    ):
        """Log just the user message (for async scenarios)"""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        user_display = user_id if user_id else "anonymous"

        log_entry = f"""
## [{timestamp}] | Server: {self.server_type} | Session: {session_id[:8]}... | User: {user_display}

**User:** {message}
"""

        with self._lock:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception as e:
                print(f"[ChatLogger] Failed to log user message: {e}")

    def log_assistant_response(
        self,
        session_id: str,
        response: str,
    ):
        """Log just the assistant response (for async scenarios)"""
        log_entry = f"""
**Assistant:** {response}

---
"""

        with self._lock:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception as e:
                print(f"[ChatLogger] Failed to log assistant response: {e}")


# Global singleton instance
chat_logger = ChatLogger()
