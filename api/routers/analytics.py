"""
Analytics API routes for event tracking and admin dashboard queries.

Two sections:
1. Event tracking (public, optional auth) — POST /analytics/track and /analytics/track/batch
2. Admin queries (admin-only) — GET /analytics/admin/*
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from schemas.analytics import (
    ActiveUser,
    ActiveUsersResponse,
    DropoffFunnel,
    DropoffResponse,
    DropoffStep,
    EventsPerDay,
    FeaturesResponse,
    FeatureUsage,
    FunnelResponse,
    FunnelStep,
    OverviewResponse,
    PageMetric,
    PagesResponse,
    SearchEvent,
    SearchEventsResponse,
    TrackBatchRequest,
    TrackEventRequest,
    TrackEventResponse,
    VisualizationEvent,
    VisualizationEventsResponse,
)
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_optional_user, require_admin
from core.database import get_db
from database.models import AnalyticsEvent, ApiUsage, CuratedLook, HomeStylingView, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


# =====================================================================
# EVENT TRACKING ENDPOINTS (public, optional auth)
# =====================================================================


@router.post("/track", response_model=TrackEventResponse)
async def track_event(
    request: TrackEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Track a single analytics event.
    Auto-fills user_id from JWT if the user is authenticated.
    """
    try:
        # Convert timezone-aware datetime to naive UTC if needed
        timestamp = request.timestamp
        if timestamp and timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)
        event = AnalyticsEvent(
            event_type=request.event_type,
            step_name=request.step_name,
            event_data=request.event_data or {},
            page_url=request.page_url,
            user_id=current_user.id if current_user else None,
            created_at=timestamp or datetime.utcnow(),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        logger.info(f"Tracked event: {request.event_type}")
        return TrackEventResponse(success=True, event_id=event.id)
    except Exception as e:
        logger.error(f"Failed to track event: {e}", exc_info=True)
        await db.rollback()
        return TrackEventResponse(success=False)


@router.post("/track/batch", response_model=TrackEventResponse)
async def track_batch(
    request: TrackBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Track a batch of analytics events in a single request.
    Reduces network overhead when the frontend flushes its event queue.
    """
    try:
        user_id = current_user.id if current_user else None
        logger.info(f"Tracking batch of {len(request.events)} events, user_id={user_id}")
        events = []
        for evt in request.events:
            # Convert timezone-aware datetime to naive UTC if needed
            timestamp = evt.timestamp
            if timestamp and timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)
            events.append(
                AnalyticsEvent(
                    event_type=evt.event_type,
                    step_name=evt.step_name,
                    event_data=evt.event_data or {},
                    page_url=evt.page_url,
                    user_id=user_id,
                    created_at=timestamp or datetime.utcnow(),
                )
            )
        db.add_all(events)
        await db.commit()
        logger.info(f"Successfully tracked {len(events)} events")
        return TrackEventResponse(success=True, events_tracked=len(events))
    except Exception as e:
        logger.error(f"Failed to track batch: {e}", exc_info=True)
        await db.rollback()
        return TrackEventResponse(success=False, events_tracked=0)


# =====================================================================
# ADMIN QUERY ENDPOINTS (admin-only)
# =====================================================================


@router.get("/admin/overview", response_model=OverviewResponse)
async def admin_overview(
    days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Overview summary cards: total users, active users, new signups, total events,
    plus events-per-day chart data for the given period.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Total users (all time)
    total_users_q = await db.execute(select(func.count(User.id)))
    total_users = total_users_q.scalar() or 0

    # Active users (users with at least one event in the period)
    active_users_q = await db.execute(
        select(func.count(distinct(AnalyticsEvent.user_id))).where(
            AnalyticsEvent.created_at >= cutoff,
            AnalyticsEvent.user_id.isnot(None),
        )
    )
    active_users = active_users_q.scalar() or 0

    # New signups in period
    new_signups_q = await db.execute(select(func.count(User.id)).where(User.created_at >= cutoff))
    new_signups = new_signups_q.scalar() or 0

    # Total events in period
    total_events_q = await db.execute(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.created_at >= cutoff))
    total_events = total_events_q.scalar() or 0

    # Events per day
    events_per_day_q = await db.execute(
        select(
            func.date(AnalyticsEvent.created_at).label("day"),
            func.count(AnalyticsEvent.id).label("count"),
        )
        .where(AnalyticsEvent.created_at >= cutoff)
        .group_by(func.date(AnalyticsEvent.created_at))
        .order_by(func.date(AnalyticsEvent.created_at))
    )
    events_per_day = [EventsPerDay(date=str(row.day), count=row.count) for row in events_per_day_q.fetchall()]

    return OverviewResponse(
        total_users=total_users,
        active_users=active_users,
        new_signups=new_signups,
        total_events=total_events,
        events_per_day=events_per_day,
    )


@router.get("/admin/funnel", response_model=FunnelResponse)
async def admin_funnel(
    days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    User lifecycle funnel: Signup → First Page View → Feature Used → Visualization Created.
    Shows how many unique users reached each step in the given period.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Step 1: Signed up (users created in period)
    signup_q = await db.execute(select(func.count(User.id)).where(User.created_at >= cutoff))
    signup_count = signup_q.scalar() or 0

    # Step 2: Had at least one page view
    pageview_q = await db.execute(
        select(func.count(distinct(AnalyticsEvent.user_id))).where(
            AnalyticsEvent.created_at >= cutoff,
            AnalyticsEvent.user_id.isnot(None),
            AnalyticsEvent.event_type == "page.view",
        )
    )
    pageview_count = pageview_q.scalar() or 0

    # Step 3: Used a feature (any event that's not page.view or page.exit)
    feature_q = await db.execute(
        select(func.count(distinct(AnalyticsEvent.user_id))).where(
            AnalyticsEvent.created_at >= cutoff,
            AnalyticsEvent.user_id.isnot(None),
            AnalyticsEvent.event_type.notin_(["page.view", "page.exit"]),
        )
    )
    feature_count = feature_q.scalar() or 0

    # Step 4: Created a visualization
    viz_q = await db.execute(
        select(func.count(distinct(AnalyticsEvent.user_id))).where(
            AnalyticsEvent.created_at >= cutoff,
            AnalyticsEvent.user_id.isnot(None),
            AnalyticsEvent.event_type.in_(["homestyling.generate_complete", "design.visualize_complete"]),
        )
    )
    viz_count = viz_q.scalar() or 0

    base = signup_count if signup_count > 0 else 1

    steps = [
        FunnelStep(step="Signup", count=signup_count, percentage=100.0),
        FunnelStep(
            step="First Page View",
            count=pageview_count,
            percentage=round(pageview_count / base * 100, 1),
        ),
        FunnelStep(
            step="Feature Used",
            count=feature_count,
            percentage=round(feature_count / base * 100, 1),
        ),
        FunnelStep(
            step="Visualization Created",
            count=viz_count,
            percentage=round(viz_count / base * 100, 1),
        ),
    ]

    return FunnelResponse(steps=steps)


@router.get("/admin/pages", response_model=PagesResponse)
async def admin_pages(
    days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Page-level metrics: path, total views, unique users.
    Only includes page.view events.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Extract path from event_data JSON or fall back to page_url
    q = await db.execute(
        select(
            func.coalesce(
                AnalyticsEvent.page_url,
                AnalyticsEvent.event_data["path"].as_string(),
            ).label("path"),
            func.count(AnalyticsEvent.id).label("views"),
            func.count(distinct(AnalyticsEvent.user_id)).label("unique_users"),
        )
        .where(
            AnalyticsEvent.created_at >= cutoff,
            AnalyticsEvent.event_type == "page.view",
        )
        .group_by("path")
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(50)
    )
    pages = [PageMetric(path=row.path or "unknown", views=row.views, unique_users=row.unique_users) for row in q.fetchall()]

    return PagesResponse(pages=pages)


@router.get("/admin/features", response_model=FeaturesResponse)
async def admin_features(
    days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Feature usage grouped by event category prefix (design, chat, homestyling, product, curated, auth, nav).
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Extract the category prefix (everything before the first dot)
    # We use a CASE expression to map event_type prefixes to feature names
    categories = ["design", "chat", "homestyling", "product", "curated", "auth", "nav"]

    features = []
    for cat in categories:
        q = await db.execute(
            select(
                func.count(AnalyticsEvent.id).label("event_count"),
                func.count(distinct(AnalyticsEvent.user_id)).label("unique_users"),
            ).where(
                AnalyticsEvent.created_at >= cutoff,
                AnalyticsEvent.event_type.like(f"{cat}.%"),
            )
        )
        row = q.fetchone()
        if row and row.event_count > 0:
            features.append(
                FeatureUsage(
                    feature=cat,
                    event_count=row.event_count,
                    unique_users=row.unique_users,
                )
            )

    # Sort by event_count descending
    features.sort(key=lambda f: f.event_count, reverse=True)

    return FeaturesResponse(features=features)


@router.get("/admin/dropoff", response_model=DropoffResponse)
async def admin_dropoff(
    days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Drop-off analysis for Homestyling and Design funnels.
    Shows step-by-step unique user counts and retention percentages.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    async def get_step_count(event_type: str) -> int:
        q = await db.execute(
            select(func.count(distinct(AnalyticsEvent.user_id))).where(
                AnalyticsEvent.created_at >= cutoff,
                AnalyticsEvent.user_id.isnot(None),
                AnalyticsEvent.event_type == event_type,
            )
        )
        return q.scalar() or 0

    # Homestyling funnel
    hs_steps = [
        ("Preferences", "homestyling.preferences_complete"),
        ("Upload", "homestyling.upload_complete"),
        ("Tier Selected", "homestyling.tier_selected"),
        ("Generate", "homestyling.generate_complete"),
        ("View Results", "homestyling.view_result"),
    ]

    hs_counts = []
    for label, event_type in hs_steps:
        count = await get_step_count(event_type)
        hs_counts.append((label, count))

    hs_dropoff = []
    for i, (label, count) in enumerate(hs_counts):
        prev_count = hs_counts[i - 1][1] if i > 0 else count
        retained = round(count / prev_count * 100, 1) if prev_count > 0 else 0.0
        if i == 0:
            retained = 100.0
        hs_dropoff.append(DropoffStep(step=label, count=count, retained_pct=retained))

    # Design funnel
    ds_steps = [
        ("Project Create", "design.project_create"),
        ("Image Upload", "design.image_upload"),
        ("Product Add", "design.product_add"),
        ("Visualize", "design.visualize_start"),
        ("Save", "design.save"),
    ]

    ds_counts = []
    for label, event_type in ds_steps:
        count = await get_step_count(event_type)
        ds_counts.append((label, count))

    ds_dropoff = []
    for i, (label, count) in enumerate(ds_counts):
        prev_count = ds_counts[i - 1][1] if i > 0 else count
        retained = round(count / prev_count * 100, 1) if prev_count > 0 else 0.0
        if i == 0:
            retained = 100.0
        ds_dropoff.append(DropoffStep(step=label, count=count, retained_pct=retained))

    return DropoffResponse(
        funnels=[
            DropoffFunnel(name="Homestyling", steps=hs_dropoff),
            DropoffFunnel(name="Design Studio", steps=ds_dropoff),
        ]
    )


@router.get("/admin/users", response_model=ActiveUsersResponse)
async def admin_users(
    days: int = Query(default=7, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Get list of active users for filtering.
    Returns users who have events in the given period, sorted by event count.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Get users with events in the period
    q = await db.execute(
        select(
            AnalyticsEvent.user_id,
            func.count(AnalyticsEvent.id).label("event_count"),
        )
        .where(
            AnalyticsEvent.created_at >= cutoff,
            AnalyticsEvent.user_id.isnot(None),
        )
        .group_by(AnalyticsEvent.user_id)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(100)
    )
    user_events = q.fetchall()

    # Get user details
    user_ids = [row.user_id for row in user_events]
    if not user_ids:
        return ActiveUsersResponse(users=[])

    users_q = await db.execute(select(User.id, User.email, User.name).where(User.id.in_(user_ids)))
    users_map = {row.id: (row.email, row.name) for row in users_q.fetchall()}

    users = []
    for row in user_events:
        if row.user_id in users_map:
            email, name = users_map[row.user_id]
            users.append(
                ActiveUser(
                    user_id=row.user_id,
                    email=email,
                    name=name,
                    event_count=row.event_count,
                )
            )

    return ActiveUsersResponse(users=users)


@router.get("/admin/searches", response_model=SearchEventsResponse)
async def admin_searches(
    days: int = Query(default=7, ge=1, le=365),
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Get detailed search and filter events.
    Shows search queries, result counts, and filters applied.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Build query
        conditions = [
            AnalyticsEvent.created_at >= cutoff,
            AnalyticsEvent.event_type.in_(["product.search", "product.filter"]),
        ]
        if user_id:
            conditions.append(AnalyticsEvent.user_id == user_id)

        q = await db.execute(select(AnalyticsEvent).where(*conditions).order_by(AnalyticsEvent.created_at.desc()).limit(limit))
        events = q.scalars().all()

        # Get user emails for display
        user_ids = list(set(e.user_id for e in events if e.user_id))
        users_map = {}
        if user_ids:
            users_q = await db.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
            users_map = {row.id: row.email for row in users_q.fetchall()}

        # Count total
        count_q = await db.execute(select(func.count(AnalyticsEvent.id)).where(*conditions))
        total = count_q.scalar() or 0

        search_events = []
        for e in events:
            try:
                event_data = e.event_data or {}
                # Get filters_applied, or use specific fields from event_data (not the whole dict)
                filters = event_data.get("filters_applied")
                if not filters:
                    # Extract relevant filter fields only (avoid non-serializable types)
                    filters = {
                        k: v
                        for k, v in event_data.items()
                        if k in ["categories", "brands", "price_min", "price_max", "sort_by", "filters"] and v is not None
                    }
                search_events.append(
                    SearchEvent(
                        id=e.id,
                        user_id=str(e.user_id) if e.user_id else None,
                        user_email=users_map.get(e.user_id) if e.user_id else None,
                        query=event_data.get("query"),
                        results_count=event_data.get("results_count"),
                        filters_applied=filters if filters else None,
                        page_url=e.page_url,
                        created_at=e.created_at,
                    )
                )
            except Exception as evt_error:
                logger.error(f"Error processing search event {e.id}: {evt_error}")
                continue

        return SearchEventsResponse(events=search_events, total=total)
    except Exception as e:
        logger.error(f"Error in admin_searches endpoint: {e}", exc_info=True)
        # Return empty response with error logged, rather than crashing
        return SearchEventsResponse(events=[], total=0)


@router.get("/admin/visualizations", response_model=VisualizationEventsResponse)
async def admin_visualizations(
    days: int = Query(default=7, ge=1, le=365),
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Get detailed visualization events.
    Shows completed visualizations with products, method, tokens, and timing.
    Note: Start events are excluded - only complete events are returned.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Build query - only complete events (not start events)
    # Include both design studio and homestyling visualization events
    conditions = [
        AnalyticsEvent.created_at >= cutoff,
        AnalyticsEvent.event_type.in_(
            [
                "design.visualize_complete",
                "design.wall_color_change",
                "design.wall_texture_change",
                "design.floor_tile_change",
                "homestyling.generate_complete",  # Free/tier visualizations
            ]
        ),
    ]
    if user_id:
        conditions.append(AnalyticsEvent.user_id == user_id)

    q = await db.execute(select(AnalyticsEvent).where(*conditions).order_by(AnalyticsEvent.created_at.desc()).limit(limit))
    events = q.scalars().all()

    # Get user emails for display
    user_ids = list(set(e.user_id for e in events if e.user_id))
    users_map = {}
    if user_ids:
        users_q = await db.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
        users_map = {row.id: row.email for row in users_q.fetchall()}

    # Count total
    count_q = await db.execute(select(func.count(AnalyticsEvent.id)).where(*conditions))
    total = count_q.scalar() or 0

    # Get token usage from api_usage table for visualization operations
    # Match by: 1) user_id + minute, 2) session_id, 3) timestamp-only (fallback)
    # Note: Many api_usage records have user_id=None (esp. homestyling), so we use multiple strategies
    token_usage_map = {}  # (user_id, minute) -> {input, output, operation}
    session_usage_map = {}  # session_id -> {input, output, operation} for session-based matching
    timestamp_only_map = {}  # minute -> {input, output, operation} for timestamp-only fallback
    if events:
        # Query api_usage for visualization-related operations in the time range
        usage_q = await db.execute(
            select(
                ApiUsage.user_id,
                ApiUsage.session_id,
                ApiUsage.timestamp,
                ApiUsage.operation,
                ApiUsage.prompt_tokens,
                ApiUsage.completion_tokens,
            )
            .where(
                ApiUsage.timestamp >= cutoff,
                ApiUsage.operation.in_(
                    [
                        # Actual operation names from api_usage table
                        "generate_add_multiple_visualization",
                        "generate_add_visualization",
                        "generate_replace_visualization",
                        "generate_full_visualization",
                        "visualize_curated_look",
                        "detect_objects",
                        "change_wall_color",
                        "change_wall_texture",
                        "change_floor_tile",
                        "apply_room_surfaces",
                        "remove_furniture",
                        # Legacy names for backward compatibility
                        "visualize",
                        "add_visualization",
                        "remove_visualization",
                        "add_remove_visualization",
                        "apply_surfaces",
                    ]
                ),
            )
            .order_by(ApiUsage.timestamp.desc())
        )
        usage_records = usage_q.fetchall()

        # Group usage by multiple keys for flexible matching
        for usage in usage_records:
            minute = usage.timestamp.replace(second=0, microsecond=0)

            # Index by session_id if available (for homestyling which passes session_id)
            if usage.session_id:
                if usage.session_id not in session_usage_map:
                    session_usage_map[usage.session_id] = {"input": 0, "output": 0, "operation": None}
                session_usage_map[usage.session_id]["input"] += usage.prompt_tokens or 0
                session_usage_map[usage.session_id]["output"] += usage.completion_tokens or 0
                if session_usage_map[usage.session_id]["operation"] is None:
                    session_usage_map[usage.session_id]["operation"] = usage.operation

            if usage.user_id:
                # Create a key based on user_id and timestamp rounded to minute
                minute_key = (usage.user_id, minute)
                if minute_key not in token_usage_map:
                    token_usage_map[minute_key] = {"input": 0, "output": 0, "operation": None}
                token_usage_map[minute_key]["input"] += usage.prompt_tokens or 0
                token_usage_map[minute_key]["output"] += usage.completion_tokens or 0
                if token_usage_map[minute_key]["operation"] is None:
                    token_usage_map[minute_key]["operation"] = usage.operation
            else:
                # For records with user_id=None, index by timestamp only
                if minute not in timestamp_only_map:
                    timestamp_only_map[minute] = {"input": 0, "output": 0, "operation": None}
                timestamp_only_map[minute]["input"] += usage.prompt_tokens or 0
                timestamp_only_map[minute]["output"] += usage.completion_tokens or 0
                if timestamp_only_map[minute]["operation"] is None:
                    timestamp_only_map[minute]["operation"] = usage.operation

    # For homestyling events, fetch curated look names from the session's views
    homestyling_session_ids = [
        e.event_data.get("session_id")
        for e in events
        if e.event_type == "homestyling.generate_complete" and e.event_data and e.event_data.get("session_id")
    ]
    curated_looks_map = {}  # session_id -> list of {name, id}
    if homestyling_session_ids:
        # Query HomeStylingView joined with CuratedLook to get look names
        looks_q = await db.execute(
            select(
                HomeStylingView.session_id,
                HomeStylingView.view_number,
                CuratedLook.id,
                CuratedLook.title,
            )
            .join(CuratedLook, HomeStylingView.curated_look_id == CuratedLook.id)
            .where(HomeStylingView.session_id.in_(homestyling_session_ids))
            .order_by(HomeStylingView.session_id, HomeStylingView.view_number)
        )
        for row in looks_q.fetchall():
            if row.session_id not in curated_looks_map:
                curated_looks_map[row.session_id] = []
            curated_looks_map[row.session_id].append(
                {
                    "id": str(row.id),
                    "name": row.title or f"Look #{row.view_number}",
                }
            )

    viz_events = []
    # IST offset (5 hours 30 minutes) - api_usage may be in local IST while analytics is in UTC
    ist_offset = timedelta(hours=5, minutes=30)

    for e in events:
        event_data = e.event_data or {}

        # Look up token usage for this event
        # Strategy: 1) session_id match, 2) user_id + minute, 3) timestamp-only fallback
        # Note: Analytics events are in UTC, api_usage may be in local IST
        input_tokens = None
        output_tokens = None
        api_operation = None

        # Try session_id match first (best for homestyling events)
        event_session_id = event_data.get("session_id")
        if event_session_id and event_session_id in session_usage_map:
            input_tokens = session_usage_map[event_session_id]["input"]
            output_tokens = session_usage_map[event_session_id]["output"]
            api_operation = session_usage_map[event_session_id].get("operation")

        # Try user_id + minute match (with IST offset fallback)
        if input_tokens is None and e.created_at:
            minute_utc = e.created_at.replace(second=0, microsecond=0)
            minute_ist = (e.created_at + ist_offset).replace(second=0, microsecond=0)

            if e.user_id:
                for minute in [minute_utc, minute_ist]:
                    minute_key = (e.user_id, minute)
                    if minute_key in token_usage_map:
                        input_tokens = token_usage_map[minute_key]["input"]
                        output_tokens = token_usage_map[minute_key]["output"]
                        api_operation = token_usage_map[minute_key].get("operation")
                        break

            # Fall back to timestamp-only match (for api_usage records with user_id=None)
            if input_tokens is None:
                for minute in [minute_utc, minute_ist]:
                    if minute in timestamp_only_map:
                        input_tokens = timestamp_only_map[minute]["input"]
                        output_tokens = timestamp_only_map[minute]["output"]
                        api_operation = timestamp_only_map[minute].get("operation")
                        break

        # Get method from event_data, or use api_operation as fallback
        method = event_data.get("method")
        if not method or method == "visualize":
            # Use api_operation as more specific method name
            method = api_operation or method

        # For homestyling events, get curated look names instead of products
        products = event_data.get("products")
        event_session_id = event_data.get("session_id")
        if e.event_type == "homestyling.generate_complete" and event_session_id:
            products = curated_looks_map.get(event_session_id, [])

        viz_events.append(
            VisualizationEvent(
                id=e.id,
                event_type=e.event_type,
                user_id=e.user_id,
                user_email=users_map.get(e.user_id) if e.user_id else None,
                project_id=event_data.get("project_id"),
                session_id=event_session_id,  # Homestyling
                product_count=event_data.get("product_count"),
                views_count=event_data.get("views_count"),  # Homestyling (1, 3, or 6)
                products=products,
                wall_color=event_data.get("wall_color"),
                wall_texture=event_data.get("wall_texture"),
                floor_tile=event_data.get("floor_tile"),
                method=method,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=event_data.get("duration_ms"),
                success=event_data.get("success"),
                page_url=e.page_url,
                created_at=e.created_at,
            )
        )

    return VisualizationEventsResponse(events=viz_events, total=total)
