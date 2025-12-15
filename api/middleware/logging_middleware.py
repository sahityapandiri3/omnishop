"""
Request logging middleware with correlation IDs for request tracing.
"""
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to store request ID across async calls
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
session_id_var: ContextVar[str] = ContextVar("session_id", default="")

logger = logging.getLogger(__name__)


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_var.get()


def get_session_id() -> str:
    """Get the current session ID from context."""
    return session_id_var.get()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Assigns a unique request ID to each request
    2. Logs request start/end with timing
    3. Captures session_id from URL for chat endpoints
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]  # Short ID for readability
        request_id_var.set(request_id)

        # Extract session_id from path if it's a chat endpoint
        session_id = ""
        path = request.url.path
        if "/chat/sessions/" in path:
            parts = path.split("/chat/sessions/")
            if len(parts) > 1:
                session_id = parts[1].split("/")[0]
                session_id_var.set(session_id)

        # Log request start
        start_time = time.time()
        logger.info(
            f"[{request_id}] → {request.method} {path}",
            extra={
                "request_id": request_id,
                "session_id": session_id,
                "method": request.method,
                "path": path,
                "query": str(request.query_params),
                "event": "request_start",
            },
        )

        # Process request
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Log request completion
            log_level = logging.INFO if response.status_code < 400 else logging.WARNING
            logger.log(
                log_level,
                f"[{request_id}] ← {response.status_code} ({duration_ms:.0f}ms)",
                extra={
                    "request_id": request_id,
                    "session_id": session_id,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "event": "request_end",
                },
            )

            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[{request_id}] ✗ Error: {str(e)[:100]} ({duration_ms:.0f}ms)",
                extra={
                    "request_id": request_id,
                    "session_id": session_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                    "event": "request_error",
                },
                exc_info=True,
            )
            raise


class ContextualLogger:
    """
    A logger wrapper that automatically includes request_id and session_id.
    Use this in your services for consistent logging.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _format_msg(self, msg: str) -> str:
        request_id = get_request_id()
        session_id = get_session_id()
        prefix = ""
        if request_id:
            prefix = f"[{request_id}]"
        if session_id:
            prefix += f"[sess:{session_id[:8]}]"
        return f"{prefix} {msg}" if prefix else msg

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(self._format_msg(msg), *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(self._format_msg(msg), *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(self._format_msg(msg), *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(self._format_msg(msg), *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        self.logger.exception(self._format_msg(msg), *args, **kwargs)


def get_logger(name: str) -> ContextualLogger:
    """Get a contextual logger that includes request/session IDs."""
    return ContextualLogger(name)
