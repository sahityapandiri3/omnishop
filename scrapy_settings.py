"""
Scrapy settings for Omnishop project
"""
from config.settings import settings

# Scrapy settings
BOT_NAME = 'omnishop'
SPIDER_MODULES = ['scrapers.spiders']
NEWSPIDER_MODULE = 'scrapers.spiders'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure delays
DOWNLOAD_DELAY = settings.scraping.download_delay
RANDOMIZE_DOWNLOAD_DELAY = settings.scraping.randomize_download_delay

# Concurrent requests
CONCURRENT_REQUESTS = settings.scraping.concurrent_requests
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# User agent
USER_AGENT = settings.scraping.user_agent_list

# AutoThrottle extension
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# Item processing pipelines (order matters!)
ITEM_PIPELINES = {
    'scrapers.pipelines.ValidationPipeline': 100,           # Validate required fields
    'scrapers.pipelines.DuplicatesPipeline': 200,           # Filter duplicates
    'scrapers.pipelines.CategoryPipeline': 250,             # Process categories
    'scrapers.pipelines.CustomImagesPipeline': 300,         # Download & process images
    'scrapers.pipelines.AttributeExtractionPipeline': 350,  # Extract product attributes with Gemini AI
    'scrapers.pipelines.DatabasePipeline': 400,             # Save to database
    'scrapers.pipelines.StatsPipeline': 500,                # Collect statistics
}

# Image settings
IMAGES_STORE = settings.images.store_path
IMAGES_URLS_FIELD = settings.images.urls_field
IMAGES_RESULT_FIELD = settings.images.result_field

# User agent rotation (disabled - package not installed)
# DOWNLOADER_MIDDLEWARES = {
#     'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
#     'scrapy_user_agents.middlewares.RandomUserAgentMiddleware': 400,
# }

# Request fingerprinting
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'

# Telnet console
TELNETCONSOLE_ENABLED = False

# Logging
LOG_LEVEL = settings.monitoring.log_level
