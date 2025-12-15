"""
Authentication API routes
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from schemas.auth import AuthStatusResponse, GoogleAuthRequest, TokenResponse, UserLogin, UserRegister, UserResponse
from services.auth_service import auth_service
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, get_optional_user
from core.database import get_db
from database.models import User

logger = logging.getLogger(__name__)
router = APIRouter()

# Whitelist of allowed email addresses (set to None to allow all)
ALLOWED_EMAILS = [
    "sahityapandiri3@gmail.com",
]


def check_email_allowed(email: str) -> bool:
    """Check if email is in the whitelist. Returns True if whitelist is disabled or email is allowed."""
    if ALLOWED_EMAILS is None:
        return True
    return email.lower() in [e.lower() for e in ALLOWED_EMAILS]


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
    if not check_email_allowed(user_data.email):
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

    # Generate token
    access_token = auth_service.create_access_token(data={"sub": user.id})

    return TokenResponse(
        access_token=access_token,
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
    if not check_email_allowed(credentials.email):
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

    # Generate token
    access_token = auth_service.create_access_token(data={"sub": user.id})

    return TokenResponse(
        access_token=access_token,
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

    # Generate token
    access_token = auth_service.create_access_token(data={"sub": user.id})

    logger.info(f"Google auth successful for {user.email} (new_user={is_new})")

    return TokenResponse(
        access_token=access_token,
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
