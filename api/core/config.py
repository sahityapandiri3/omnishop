"""
Configuration settings for the FastAPI application
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""

    # Application
    app_name: str = "Omnishop API"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/omnishop"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 4000
    openai_temperature: float = 0.7

    # Google AI Studio
    google_ai_api_key: str = ""
    google_ai_model: str = "gemini-2.5-pro"
    google_ai_max_tokens: int = 2048
    google_ai_temperature: float = 0.3

    # Replicate (for SDXL Inpainting)
    replicate_api_key: str = ""
    replicate_model_sdxl_inpaint: str = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"
    replicate_model_interior_design: str = "adirik/interior-design:76604baddc85b1b4616e1c6475eca080da339c8875bd4996705440484a6879c2"
    replicate_model_ip_adapter_sdxl: str = "ostris/ip-adapter-sdxl:7d00780da0e4fc2a8d8a89c3c4b89d5f99ebb04be6bd3e9c8c6b8e31b8c5e5b2"

    # File upload
    upload_path: str = "../data/uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_image_types: List[str] = ["image/jpeg", "image/png", "image/webp"]

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # Caching
    cache_ttl: int = 300  # 5 minutes

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields from .env


# Global settings instance
settings = Settings()