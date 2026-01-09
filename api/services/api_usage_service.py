"""
API Usage Tracking Service

Tracks token usage and costs for all AI API calls (Gemini, OpenAI, etc.)
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ApiUsage

logger = logging.getLogger(__name__)

# Cost per 1M tokens (approximate, as of Jan 2025)
COST_PER_MILLION_TOKENS = {
    "gemini": {
        "gemini-2.0-flash-exp": {"input": 0.075, "output": 0.30},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-pro-vision": {"input": 0.25, "output": 0.50},
    },
    "openai": {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    },
}


def calculate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated cost for API call."""
    provider_costs = COST_PER_MILLION_TOKENS.get(provider, {})
    model_costs = provider_costs.get(model, {"input": 0.10, "output": 0.30})  # Default fallback

    input_cost = (prompt_tokens / 1_000_000) * model_costs["input"]
    output_cost = (completion_tokens / 1_000_000) * model_costs["output"]

    return round(input_cost + output_cost, 6)


async def log_api_usage(
    db: AsyncSession,
    provider: str,
    model: str,
    operation: str,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ApiUsage:
    """
    Log an API usage record to the database.

    Args:
        db: Database session
        provider: API provider (gemini, openai, etc.)
        model: Model name (gemini-2.0-flash-exp, gpt-4, etc.)
        operation: Operation type (visualize, analyze_room, chat, etc.)
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        total_tokens: Total tokens (if not provided, calculated from prompt + completion)
        user_id: Optional user ID
        session_id: Optional session ID
        metadata: Optional additional metadata

    Returns:
        Created ApiUsage record
    """
    # Calculate total tokens if not provided
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    # Calculate estimated cost
    estimated_cost = None
    if prompt_tokens is not None and completion_tokens is not None:
        estimated_cost = calculate_cost(provider, model, prompt_tokens, completion_tokens)

    usage = ApiUsage(
        timestamp=datetime.utcnow(),
        user_id=user_id,
        session_id=session_id,
        provider=provider,
        model=model,
        operation=operation,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        request_metadata=metadata,
    )

    db.add(usage)
    await db.commit()

    logger.info(
        f"[API Usage] {provider}/{model} - {operation}: " f"tokens={total_tokens}, cost=${estimated_cost:.4f}"
        if estimated_cost
        else f"tokens={total_tokens}"
    )

    return usage


def log_gemini_usage(response, operation: str, model: str = None):
    """
    Simple helper to log Gemini API usage directly to database.
    Can be called from anywhere - creates its own database connection.

    Args:
        response: Gemini API response object
        operation: Operation name (e.g., "identify_object", "inpaint")
        model: Model name override (if not in response)
    """
    try:
        from core.database import get_sync_db_session

        # Extract token counts from response
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None

        if hasattr(response, "usage_metadata"):
            metadata = response.usage_metadata
            prompt_tokens = getattr(metadata, "prompt_token_count", None)
            completion_tokens = getattr(metadata, "candidates_token_count", None)
            total_tokens = getattr(metadata, "total_token_count", None)

        model_name = model or getattr(response, "model", "unknown")

        with get_sync_db_session() as db:
            usage = ApiUsage(
                timestamp=datetime.utcnow(),
                provider="gemini",
                model=model_name,
                operation=operation,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            db.add(usage)

        logger.info(f"[API Usage] gemini/{model_name} - {operation}: tokens={total_tokens}")
    except Exception as e:
        # Don't fail the main request if logging fails
        logger.warning(f"Failed to log API usage: {e}")


def log_api_usage_sync(
    db_session,
    provider: str,
    model: str,
    operation: str,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ApiUsage:
    """
    Synchronous version of log_api_usage for non-async contexts.
    """
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    estimated_cost = None
    if prompt_tokens is not None and completion_tokens is not None:
        estimated_cost = calculate_cost(provider, model, prompt_tokens, completion_tokens)

    usage = ApiUsage(
        timestamp=datetime.utcnow(),
        user_id=user_id,
        session_id=session_id,
        provider=provider,
        model=model,
        operation=operation,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        request_metadata=metadata,
    )

    db_session.add(usage)
    db_session.commit()

    logger.info(
        f"[API Usage] {provider}/{model} - {operation}: " f"tokens={total_tokens}, cost=${estimated_cost:.4f}"
        if estimated_cost
        else f"tokens={total_tokens}"
    )

    return usage


async def get_usage_summary(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    provider: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get usage summary statistics.

    Args:
        db: Database session
        start_date: Start of date range (default: today)
        end_date: End of date range (default: now)
        provider: Filter by provider
        user_id: Filter by user

    Returns:
        Dictionary with usage statistics
    """
    if start_date is None:
        start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if end_date is None:
        end_date = datetime.utcnow()

    # Build query
    query = select(
        func.count(ApiUsage.id).label("total_calls"),
        func.sum(ApiUsage.prompt_tokens).label("total_prompt_tokens"),
        func.sum(ApiUsage.completion_tokens).label("total_completion_tokens"),
        func.sum(ApiUsage.total_tokens).label("total_tokens"),
        func.sum(ApiUsage.estimated_cost).label("total_cost"),
    ).where(
        ApiUsage.timestamp >= start_date,
        ApiUsage.timestamp <= end_date,
    )

    if provider:
        query = query.where(ApiUsage.provider == provider)
    if user_id:
        query = query.where(ApiUsage.user_id == user_id)

    result = await db.execute(query)
    row = result.fetchone()

    # Get breakdown by operation
    operation_query = (
        select(
            ApiUsage.operation,
            func.count(ApiUsage.id).label("calls"),
            func.sum(ApiUsage.total_tokens).label("tokens"),
            func.sum(ApiUsage.estimated_cost).label("cost"),
        )
        .where(
            ApiUsage.timestamp >= start_date,
            ApiUsage.timestamp <= end_date,
        )
        .group_by(ApiUsage.operation)
    )

    if provider:
        operation_query = operation_query.where(ApiUsage.provider == provider)
    if user_id:
        operation_query = operation_query.where(ApiUsage.user_id == user_id)

    operation_result = await db.execute(operation_query)
    operations = [
        {
            "operation": r.operation,
            "calls": r.calls,
            "tokens": r.tokens or 0,
            "cost": round(r.cost or 0, 4),
        }
        for r in operation_result.fetchall()
    ]

    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "summary": {
            "total_calls": row.total_calls or 0,
            "total_prompt_tokens": row.total_prompt_tokens or 0,
            "total_completion_tokens": row.total_completion_tokens or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost_usd": round(row.total_cost or 0, 4),
        },
        "by_operation": operations,
    }


async def get_usage_by_day(
    db: AsyncSession,
    days: int = 7,
    provider: Optional[str] = None,
) -> list:
    """Get daily usage for the last N days."""
    start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

    query = (
        select(
            func.date(ApiUsage.timestamp).label("date"),
            func.count(ApiUsage.id).label("calls"),
            func.sum(ApiUsage.total_tokens).label("tokens"),
            func.sum(ApiUsage.estimated_cost).label("cost"),
        )
        .where(
            ApiUsage.timestamp >= start_date,
        )
        .group_by(func.date(ApiUsage.timestamp))
        .order_by(func.date(ApiUsage.timestamp))
    )

    if provider:
        query = query.where(ApiUsage.provider == provider)

    result = await db.execute(query)

    return [
        {
            "date": str(r.date),
            "calls": r.calls,
            "tokens": r.tokens or 0,
            "cost": round(r.cost or 0, 4),
        }
        for r in result.fetchall()
    ]
