"""
Configuration settings for Omnishop scraping system
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    url: str = Field(default="postgresql://omnishop_user:omnishop_secure_2024@localhost:5432/omnishop")
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    name: str = Field(default="omnishop")
    user: str = Field(default="omnishop_user")
    password: str = Field(default="omnishop_secure_2024")

    class Config:
        env_prefix = "DATABASE_"


class RedisSettings(BaseSettings):
    """Redis configuration"""
    url: str = Field(default="redis://localhost:6379/0")
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)

    class Config:
        env_prefix = "REDIS_"


class ScrapingSettings(BaseSettings):
    """Scraping configuration"""
    delay: float = Field(default=1.0)
    concurrent_requests: int = Field(default=16)
    download_delay: float = Field(default=1.0)
    randomize_download_delay: float = Field(default=0.5)
    user_agent_list: str = Field(default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    class Config:
        env_prefix = "SCRAPING_"


class ImageSettings(BaseSettings):
    """Image processing configuration"""
    store_path: str = Field(default="data/images")
    urls_field: str = Field(default="image_urls")
    result_field: str = Field(default="images")
    thumbnail_size: tuple = Field(default=(150, 150))
    medium_size: tuple = Field(default=(400, 400))
    large_size: tuple = Field(default=(800, 800))

    class Config:
        env_prefix = "IMAGES_"


class AWSSettings(BaseSettings):
    """AWS configuration"""
    access_key_id: Optional[str] = Field(default=None)
    secret_access_key: Optional[str] = Field(default=None)
    storage_bucket_name: Optional[str] = Field(default=None)
    region: str = Field(default="us-east-1")

    class Config:
        env_prefix = "AWS_"


class MonitoringSettings(BaseSettings):
    """Monitoring configuration"""
    sentry_dsn: Optional[str] = Field(default=None)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    class Config:
        env_prefix = "MONITORING_"


class APISettings(BaseSettings):
    """API configuration"""
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=True)

    class Config:
        env_prefix = "API_"


class Settings(BaseSettings):
    """Main settings class"""
    environment: str = Field(default="development")

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    scraping: ScrapingSettings = Field(default_factory=ScrapingSettings)
    images: ImageSettings = Field(default_factory=ImageSettings)
    aws: AWSSettings = Field(default_factory=AWSSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    api: APISettings = Field(default_factory=APISettings)

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields from .env


# Global settings instance
settings = Settings()


# Scrapy settings
SCRAPY_SETTINGS = {
    'BOT_NAME': 'omnishop',
    'SPIDER_MODULES': ['scrapers.spiders'],
    'NEWSPIDER_MODULE': 'scrapers.spiders',

    # Obey robots.txt rules
    'ROBOTSTXT_OBEY': True,

    # Configure delays
    'DOWNLOAD_DELAY': settings.scraping.download_delay,
    'RANDOMIZE_DOWNLOAD_DELAY': settings.scraping.randomize_download_delay,

    # Concurrent requests
    'CONCURRENT_REQUESTS': settings.scraping.concurrent_requests,
    'CONCURRENT_REQUESTS_PER_DOMAIN': 8,

    # User agent
    'USER_AGENT': settings.scraping.user_agent_list,

    # AutoThrottle extension
    'AUTOTHROTTLE_ENABLED': True,
    'AUTOTHROTTLE_START_DELAY': 1,
    'AUTOTHROTTLE_MAX_DELAY': 60,
    'AUTOTHROTTLE_TARGET_CONCURRENCY': 2.0,
    'AUTOTHROTTLE_DEBUG': False,

    # Image pipeline
    'ITEM_PIPELINES': {
        'scrapers.pipelines.ImagesPipeline': 300,
        'scrapers.pipelines.DatabasePipeline': 400,
    },

    # Image settings
    'IMAGES_STORE': settings.images.store_path,
    'IMAGES_URLS_FIELD': settings.images.urls_field,
    'IMAGES_RESULT_FIELD': settings.images.result_field,

    # User agent rotation
    'DOWNLOADER_MIDDLEWARES': {
        'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        'scrapy_user_agents.middlewares.RandomUserAgentMiddleware': 400,
    },

    # Request fingerprinting
    'REQUEST_FINGERPRINTER_IMPLEMENTATION': '2.7',

    # Telnet console
    'TELNETCONSOLE_ENABLED': False,

    # Logging
    'LOG_LEVEL': settings.monitoring.log_level,
}