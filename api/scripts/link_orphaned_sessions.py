#!/usr/bin/env python3
"""
One-time migration script to link orphaned HomeStylingSession records to users.

Sessions created before the fix weren't properly linked to users. This script:
1. Finds sessions with clean_room_image but no user_id
2. Looks up the user from ApiUsage or AnalyticsEvent records
3. Updates the session with the found user_id

Run with: python -m scripts.link_orphaned_sessions
"""

import asyncio
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from database.models import HomeStylingSession, ApiUsage, AnalyticsEvent, User

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


async def find_user_for_session(db: AsyncSession, session_id: str) -> str | None:
    """
    Try to find the user who owns a session by looking at:
    1. ApiUsage records with the same session_id
    2. AnalyticsEvent records with session_id in event_data
    """
    # Strategy 1: Check ApiUsage table
    api_usage_query = (
        select(ApiUsage.user_id)
        .where(ApiUsage.session_id == session_id)
        .where(ApiUsage.user_id.isnot(None))
        .limit(1)
    )
    result = await db.execute(api_usage_query)
    user_id = result.scalar_one_or_none()
    if user_id:
        return user_id

    # Strategy 2: Check AnalyticsEvent table for homestyling events with this session_id
    # Events like homestyling.generate_complete have session_id in event_data
    analytics_query = (
        select(AnalyticsEvent.user_id)
        .where(AnalyticsEvent.user_id.isnot(None))
        .where(AnalyticsEvent.event_type.like("homestyling.%"))
        .where(AnalyticsEvent.event_data["session_id"].as_string() == session_id)
        .limit(1)
    )
    result = await db.execute(analytics_query)
    user_id = result.scalar_one_or_none()
    if user_id:
        return user_id

    return None


async def link_orphaned_sessions(dry_run: bool = True):
    """
    Find and link orphaned sessions to their users.

    Args:
        dry_run: If True, only report what would be done without making changes
    """
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable not set")
        return

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Find orphaned sessions (have clean_room_image but no user_id, and not copied)
        orphan_query = (
            select(HomeStylingSession)
            .where(HomeStylingSession.clean_room_image.isnot(None))
            .where(HomeStylingSession.user_id.is_(None))
            .where(HomeStylingSession.source_session_id.is_(None))  # Not a copy
            .order_by(HomeStylingSession.created_at.desc())
        )
        result = await db.execute(orphan_query)
        orphaned_sessions = result.scalars().all()

        logger.info(f"Found {len(orphaned_sessions)} orphaned sessions with images")

        linked_count = 0
        not_found_count = 0

        for session in orphaned_sessions:
            user_id = await find_user_for_session(db, session.id)

            if user_id:
                # Verify user exists
                user_check = await db.execute(select(User.email).where(User.id == user_id))
                user_email = user_check.scalar_one_or_none()

                if user_email:
                    logger.info(
                        f"{'[DRY RUN] Would link' if dry_run else 'Linking'} session {session.id} "
                        f"(created {session.created_at}) to user {user_email}"
                    )
                    if not dry_run:
                        session.user_id = user_id
                    linked_count += 1
                else:
                    logger.warning(f"User {user_id} not found for session {session.id}")
                    not_found_count += 1
            else:
                logger.debug(f"Could not find user for session {session.id}")
                not_found_count += 1

        if not dry_run:
            await db.commit()
            logger.info(f"Committed {linked_count} session updates")

        logger.info(f"\nSummary:")
        logger.info(f"  Total orphaned sessions: {len(orphaned_sessions)}")
        logger.info(f"  Sessions linked to users: {linked_count}")
        logger.info(f"  Sessions without identifiable user: {not_found_count}")

        if dry_run:
            logger.info("\nThis was a DRY RUN. Run with --apply to make changes.")

    await engine.dispose()


async def show_stats():
    """Show statistics about session ownership."""
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable not set")
        return

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Count sessions with clean images
        total_query = select(func.count(HomeStylingSession.id)).where(
            HomeStylingSession.clean_room_image.isnot(None)
        )
        total = (await db.execute(total_query)).scalar() or 0

        # Count sessions with user_id
        with_user_query = select(func.count(HomeStylingSession.id)).where(
            HomeStylingSession.clean_room_image.isnot(None),
            HomeStylingSession.user_id.isnot(None),
        )
        with_user = (await db.execute(with_user_query)).scalar() or 0

        # Count orphaned (no user_id, not a copy)
        orphaned_query = select(func.count(HomeStylingSession.id)).where(
            HomeStylingSession.clean_room_image.isnot(None),
            HomeStylingSession.user_id.is_(None),
            HomeStylingSession.source_session_id.is_(None),
        )
        orphaned = (await db.execute(orphaned_query)).scalar() or 0

        # Count copies
        copies_query = select(func.count(HomeStylingSession.id)).where(
            HomeStylingSession.clean_room_image.isnot(None),
            HomeStylingSession.source_session_id.isnot(None),
        )
        copies = (await db.execute(copies_query)).scalar() or 0

        # Sessions per user
        per_user_query = (
            select(User.email, func.count(HomeStylingSession.id).label("count"))
            .join(HomeStylingSession, HomeStylingSession.user_id == User.id)
            .where(HomeStylingSession.clean_room_image.isnot(None))
            .where(HomeStylingSession.source_session_id.is_(None))
            .group_by(User.email)
            .order_by(func.count(HomeStylingSession.id).desc())
            .limit(10)
        )
        per_user = (await db.execute(per_user_query)).fetchall()

        logger.info("\n=== Session Statistics ===")
        logger.info(f"Total sessions with images: {total}")
        logger.info(f"  - Linked to users: {with_user}")
        logger.info(f"  - Orphaned (no user): {orphaned}")
        logger.info(f"  - Copies from other sessions: {copies}")

        if per_user:
            logger.info("\nTop users by original uploads:")
            for email, count in per_user:
                logger.info(f"  {email}: {count} rooms")

    await engine.dispose()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Link orphaned homestyling sessions to users")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry run)")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    args = parser.parse_args()

    if args.stats:
        asyncio.run(show_stats())
    else:
        asyncio.run(link_orphaned_sessions(dry_run=not args.apply))


if __name__ == "__main__":
    main()
