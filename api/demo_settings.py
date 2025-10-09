"""
Demo settings configuration for Omnishop Milestone 3 localhost demo
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class DemoSettings(BaseSettings):
    """Demo settings for localhost development"""

    # Environment
    environment: str = Field(default="demo")
    debug: bool = Field(default=True)

    # API Configuration
    api_v1_str: str = Field(default="/api/v1")
    secret_key: str = Field(default="demo-secret-key-for-localhost")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)

    # OpenAI Configuration
    openai_api_key: str = Field(default="demo_key_for_localhost")
    openai_model: str = Field(default="gpt-4-vision-preview")
    openai_max_tokens: int = Field(default=4000)
    openai_temperature: float = Field(default=0.7)

    # Google AI Studio Configuration
    google_ai_api_key: str = Field(default="demo_key_for_localhost")
    google_ai_model: str = Field(default="gemini-1.5-pro")
    google_ai_max_tokens: int = Field(default=2048)
    google_ai_temperature: float = Field(default=0.3)

    # Database Configuration (not used in demo)
    database_url: str = Field(default="postgresql://demo:demo@localhost:5432/demo")
    database_pool_size: int = Field(default=20)
    database_max_overflow: int = Field(default=30)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console")

    # CORS
    cors_origins: List[str] = Field(default=["http://localhost:3000", "http://127.0.0.1:3000", "*"])

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from .env


# Demo settings instance
demo_settings = DemoSettings()