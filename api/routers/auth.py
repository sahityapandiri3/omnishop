"""
Authentication API routes
"""
import enum
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from schemas.auth import (
    AuthStatusResponse,
    GoogleAuthRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from services.auth_service import auth_service
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, get_optional_user
from core.database import get_db
from database.models import SystemSettings, User

logger = logging.getLogger(__name__)
router = APIRouter()

# Admin secret for protected endpoints
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "omnishop-admin-2024")


async def check_email_allowed(email: str, db: AsyncSession) -> bool:
    """
    Check if email is allowed based on whitelist settings in the database.
    Returns True if whitelist is disabled or email is in the whitelist.
    """
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == "whitelist"))
    setting = result.scalar_one_or_none()

    if not setting:
        return True

    value = setting.value or {}
    if not value.get("enabled", False):
        return True

    allowed_emails = value.get("emails", [])
    return email.lower() in [e.lower() for e in allowed_emails]


@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user with email and password.
    Returns access token on success.
    """
    # Check whitelist
    if not await check_email_allowed(user_data.email, db):
        logger.warning(f"Registration blocked for non-whitelisted email: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently restricted. Please contact the administrator.",
        )

    # Check if email already exists
    existing_user = await auth_service.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = await auth_service.create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        name=user_data.name,
        auth_provider="email",
    )

    # Generate tokens
    access_token = auth_service.create_access_token(data={"sub": user.id})
    refresh_token = auth_service.create_refresh_token(data={"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.
    Returns access token on success.
    """
    # Check whitelist
    if not await check_email_allowed(credentials.email, db):
        logger.warning(f"Login blocked for non-whitelisted email: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access is currently restricted. Please contact the administrator.",
        )

    user = await auth_service.authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Generate tokens
    access_token = auth_service.create_access_token(data={"sub": user.id})
    refresh_token = auth_service.create_refresh_token(data={"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    request: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with Google OAuth.
    Creates a new user if one doesn't exist.
    Returns access token on success.
    """
    result = await auth_service.authenticate_google_user(db, request.token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    # Check if email was blocked by whitelist
    if result == "blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access is currently restricted. Please contact the administrator.",
        )

    user, is_new = result

    # Generate tokens
    access_token = auth_service.create_access_token(data={"sub": user.id})
    refresh_token = auth_service.create_refresh_token(data={"sub": user.id})

    logger.info(f"Google auth successful for {user.email} (new_user={is_new})")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get the current authenticated user's information.
    """
    return UserResponse.model_validate(current_user)


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    current_user: User = Depends(get_optional_user),
):
    """
    Check authentication status.
    Returns authenticated=true with user info if logged in,
    or authenticated=false if not.
    """
    if current_user:
        return AuthStatusResponse(
            authenticated=True,
            user=UserResponse.model_validate(current_user),
        )
    return AuthStatusResponse(authenticated=False)


@router.post("/logout")
async def logout():
    """
    Logout the current user.
    Note: Since we use JWT tokens, actual logout is handled client-side
    by removing the token. This endpoint is provided for API completeness.
    """
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh the access token using a valid refresh token.
    Returns a new access token on success.
    """
    # Verify the refresh token
    user_id = auth_service.verify_refresh_token(request.refresh_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Verify user still exists and is active
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    # Generate new access token
    access_token = auth_service.create_access_token(data={"sub": user.id})

    logger.info(f"Token refreshed for user {user.email}")

    return RefreshTokenResponse(access_token=access_token)


# ============================================================================
# Subscription Endpoints
# ============================================================================


class UpgradeRequest(BaseModel):
    """Request to upgrade subscription tier"""

    tier: str = "basic"  # Default to basic tier


class UpgradeResponse(BaseModel):
    """Response for subscription upgrade"""

    success: bool
    subscription_tier: str
    message: str


@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade_subscription(
    request: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upgrade user's subscription tier.

    Supports the new 5-tier pricing system:
    - free: 1 curated look with sample room
    - basic: 3 curated looks (₹399)
    - basic_plus: 6 curated looks (₹699)
    - advanced: Full Omni Studio access (₹11,999/mo)
    - curator: Full access + publish to gallery (₹14,999/mo)

    IMPORTANT: Advanced and Curator are monthly subscriptions that persist.
    Users with these tiers can still use lower tiers for homestyling sessions,
    but their account badge always shows Advanced/Curator until subscription expires.

    TODO: Integrate with Razorpay/Stripe for actual payment processing.
    """
    try:
        # Validate tier - supports both old and new tier names
        valid_tiers = ["free", "basic", "basic_plus", "advanced", "curator", "upgraded", "build_your_own"]
        if request.tier not in valid_tiers:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid tier. Must be one of: {valid_tiers}")

        # Monthly subscription tiers that should never be downgraded automatically
        monthly_tiers = ["advanced", "curator", "upgraded"]
        lower_tiers = ["free", "basic", "basic_plus"]

        current_tier = current_user.subscription_tier
        if isinstance(current_tier, enum.Enum):
            current_tier = current_tier.value

        # Protect Advanced/Curator users from accidental downgrades
        # They keep their badge even when selecting lower tiers for homestyling sessions
        if current_tier in monthly_tiers and request.tier in lower_tiers:
            logger.info(
                f"User {current_user.email} selected {request.tier} for session but keeping {current_tier} subscription"
            )
            # Return success but keep the original tier
            return UpgradeResponse(
                success=True,
                subscription_tier=current_tier,
                message=f"Session tier set to {request.tier}, but your {current_tier} subscription is preserved"
            )

        # Update user's subscription tier (for actual upgrades or non-monthly users)
        current_user.subscription_tier = request.tier
        await db.commit()
        await db.refresh(current_user)

        logger.info(f"User {current_user.email} upgraded to {request.tier}")

        return UpgradeResponse(
            success=True, subscription_tier=request.tier, message=f"Successfully upgraded to {request.tier}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upgrading subscription for user {current_user.email}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upgrade subscription")


# ============================================================================
# Admin Endpoints (Protected by ADMIN_SECRET)
# ============================================================================


class UserActivity(BaseModel):
    """User activity response model"""

    id: str
    email: Optional[str]
    name: Optional[str]
    auth_provider: Optional[str]
    created_at: Optional[datetime]
    last_login: Optional[datetime]


class UserActivityResponse(BaseModel):
    """Response for user activity endpoint"""

    total_users: int
    users: List[UserActivity]
    query_days: int


def verify_admin_secret(x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    """Verify the admin secret header"""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin secret")
    return True


@router.get("/admin/users/count")
async def get_user_count(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_secret),
):
    """Get total user count in database."""
    from sqlalchemy import func

    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar()
    return {"total_users": count}


@router.get("/admin/users/recent", response_model=UserActivityResponse)
async def get_recent_users(
    days: int = Query(default=3, ge=1, le=30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_secret),
):
    """
    Get users who logged in or registered in the last N days.

    Requires X-Admin-Secret header for authentication.

    Example:
        curl -H "X-Admin-Secret: your-secret" "https://app.omni-shop.in/api/auth/admin/users/recent?days=3"
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = (
            select(User)
            .where(or_(User.last_login >= cutoff_date, User.created_at >= cutoff_date))
            .order_by(User.last_login.desc().nullslast(), User.created_at.desc())
        )

        result = await db.execute(query)
        users = result.scalars().all()

        user_activities = [
            UserActivity(
                id=str(user.id),
                email=user.email,
                name=user.name,
                auth_provider=user.auth_provider,
                created_at=user.created_at,
                last_login=user.last_login,
            )
            for user in users
        ]

        logger.info(f"Admin query: Found {len(user_activities)} users active in last {days} days")

        return UserActivityResponse(total_users=len(user_activities), users=user_activities, query_days=days)

    except Exception as e:
        logger.error(f"Error fetching recent users: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching user data: {str(e)}")
