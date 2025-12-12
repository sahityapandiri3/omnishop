"""
Authentication service for user management, JWT tokens, and OAuth
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import bcrypt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from database.models import User

logger = logging.getLogger(__name__)

# Whitelist of allowed email addresses (set to None to allow all)
ALLOWED_EMAILS: Optional[List[str]] = None  # Disabled for customer testing


def check_email_allowed(email: str) -> bool:
    """Check if email is in the whitelist. Returns True if whitelist is disabled or email is allowed."""
    if ALLOWED_EMAILS is None:
        return True
    return email.lower() in [e.lower() for e in ALLOWED_EMAILS]


class AuthService:
    """Service for authentication operations"""

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt

    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            return None

    async def verify_google_token(self, token: str) -> Optional[dict]:
        """Verify a Google OAuth token and return user info"""
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), settings.google_client_id)

            # Token is valid, extract user info
            return {
                "google_id": idinfo["sub"],
                "email": idinfo["email"],
                "name": idinfo.get("name", ""),
                "profile_image_url": idinfo.get("picture", ""),
                "email_verified": idinfo.get("email_verified", False),
            }
        except Exception as e:
            logger.error(f"Google token verification failed: {e}")
            return None

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_google_id(self, db: AsyncSession, google_id: str) -> Optional[User]:
        """Get a user by Google ID"""
        result = await db.execute(select(User).where(User.google_id == google_id))
        return result.scalar_one_or_none()

    async def create_user(
        self,
        db: AsyncSession,
        email: str,
        password: Optional[str] = None,
        name: Optional[str] = None,
        auth_provider: str = "email",
        google_id: Optional[str] = None,
        profile_image_url: Optional[str] = None,
    ) -> User:
        """Create a new user"""
        hashed_password = self.hash_password(password) if password else None

        user = User(
            email=email,
            hashed_password=hashed_password,
            name=name,
            auth_provider=auth_provider,
            google_id=google_id,
            profile_image_url=profile_image_url,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Created new user: {email} (provider: {auth_provider})")
        return user

    async def authenticate_user(self, db: AsyncSession, email: str, password: str) -> Optional[User]:
        """Authenticate a user with email and password"""
        user = await self.get_user_by_email(db, email)
        if not user:
            return None
        if not user.hashed_password:
            # User registered with OAuth, can't use password login
            return None
        if not self.verify_password(password, user.hashed_password):
            return None

        # Update last_login timestamp
        user.last_login = datetime.utcnow()
        await db.commit()
        await db.refresh(user)

        return user

    async def authenticate_google_user(self, db: AsyncSession, google_token: str) -> Optional[tuple[User, bool]]:
        """
        Authenticate or create a user via Google OAuth.
        Returns (user, is_new_user) tuple or None if failed.
        Returns "blocked" string if email is not whitelisted.
        """
        # Verify the Google token
        google_info = await self.verify_google_token(google_token)
        if not google_info:
            return None

        # Check whitelist
        if not check_email_allowed(google_info["email"]):
            logger.warning(f"Google auth blocked for non-whitelisted email: {google_info['email']}")
            return "blocked"  # type: ignore

        # Check if user exists by Google ID
        user = await self.get_user_by_google_id(db, google_info["google_id"])
        if user:
            # Update last_login timestamp
            user.last_login = datetime.utcnow()
            await db.commit()
            await db.refresh(user)
            return (user, False)

        # Check if user exists by email (may have registered with email/password)
        user = await self.get_user_by_email(db, google_info["email"])
        if user:
            # Link Google account to existing user
            user.google_id = google_info["google_id"]
            user.auth_provider = "google"
            user.last_login = datetime.utcnow()
            if not user.profile_image_url:
                user.profile_image_url = google_info["profile_image_url"]
            if not user.name:
                user.name = google_info["name"]
            await db.commit()
            await db.refresh(user)
            return (user, False)

        # Create new user (last_login set to now for first login)
        user = await self.create_user(
            db=db,
            email=google_info["email"],
            name=google_info["name"],
            auth_provider="google",
            google_id=google_info["google_id"],
            profile_image_url=google_info["profile_image_url"],
        )
        # Set last_login for new user
        user.last_login = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
        return (user, True)


# Global service instance
auth_service = AuthService()
