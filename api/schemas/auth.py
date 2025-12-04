"""
Pydantic schemas for authentication
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


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
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AuthStatusResponse(BaseModel):
    """Schema for checking auth status"""

    authenticated: bool
    user: Optional[UserResponse] = None
