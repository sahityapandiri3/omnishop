"""
Pydantic schemas for authentication
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_serializer


# Request schemas
class UserRegister(BaseModel):
    """Schema for user registration"""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    name: Optional[str] = Field(None, max_length=200)


class UserLogin(BaseModel):
    """Schema for user login"""

    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Schema for Google OAuth authentication"""

    token: str  # Google ID token from frontend


# Response schemas
class UserResponse(BaseModel):
    """Schema for user response"""

    id: str
    email: str
    name: Optional[str] = None
    profile_image_url: Optional[str] = None
    auth_provider: str
    is_active: bool
    role: str  # "user", "admin", or "super_admin"
    created_at: datetime

    @field_serializer("role")
    def serialize_role(self, role):
        """Convert UserRole enum to string value"""
        if hasattr(role, "value"):
            return role.value
        return role

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response"""

    access_token: str
    refresh_token: Optional[str] = None  # Optional for backwards compatibility
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""

    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Schema for refresh token response"""

    access_token: str
    token_type: str = "bearer"


class AuthStatusResponse(BaseModel):
    """Schema for checking auth status"""

    authenticated: bool
    user: Optional[UserResponse] = None
