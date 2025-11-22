"""
FastAPI main application for Omnishop
"""
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

# Add api directory to path for imports (works both locally and on Railway)
api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

# Add parent directory to path to import from scrapers
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Store import error for debugging
import_error_message = None
import_error_traceback = None

try:
    from core.config import settings

    # from core.database import database
    from core.logging import setup_logging
    from routers import categories, chat, furniture, products, stores, visualization

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("✅ All routers imported successfully")
except ImportError as e:
    # Log the full error and traceback
    import traceback

    import_error_message = str(e)
    import_error_traceback = traceback.format_exc()

    print(f"❌ IMPORT ERROR: {e}")
    print(f"Full traceback:\n{import_error_traceback}")
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import routers: {e}")
    logger.error(f"Traceback: {import_error_traceback}")

    # Create minimal fallback settings for basic functionality
    class FallbackSettings:
        environment = "production"
        cors_origins = ["*"]
        debug = False

    settings = FallbackSettings()

    def setup_logging():
        logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Omnishop API...")

    # Check critical environment variables
    logger.info("=" * 60)
    logger.info("ENVIRONMENT VARIABLES CHECK")
    logger.info("=" * 60)

    openai_key = os.getenv("OPENAI_API_KEY", "")
    google_key = os.getenv("GOOGLE_AI_API_KEY", "")
    db_url = os.getenv("DATABASE_URL", "")

    if openai_key:
        key_preview = f"{openai_key[:7]}...{openai_key[-4:]}" if len(openai_key) > 11 else "***"
        logger.info(f"✅ OPENAI_API_KEY is set: {key_preview}")
    else:
        logger.error("❌ OPENAI_API_KEY is NOT set - Chat will not work!")

    if google_key:
        key_preview = f"{google_key[:7]}...{google_key[-4:]}" if len(google_key) > 11 else "***"
        logger.info(f"✅ GOOGLE_AI_API_KEY is set: {key_preview}")
    else:
        logger.error("❌ GOOGLE_AI_API_KEY is NOT set - Image analysis will not work!")

    if db_url:
        # Sanitize database URL
        import re

        sanitized = re.sub(r":\/\/[^:]*:[^@]*@", "://***:***@", db_url)
        logger.info(f"✅ DATABASE_URL is set: {sanitized}")
    else:
        logger.error("❌ DATABASE_URL is NOT set!")

    logger.info("=" * 60)

    # Database connection is managed by SQLAlchemy async session
    # No explicit connect/disconnect needed
    logger.info("Application started")

    yield

    # Shutdown
    logger.info("Shutting down Omnishop API...")
    logger.info("Application stopped")


# Create FastAPI application
app = FastAPI(
    title="Omnishop API",
    description="AI Interior Design Platform API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)

# Add middleware
# Note: Wildcard patterns in allow_origins don't work, so we use allow_origin_regex
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://omnishop-three.vercel.app",  # Production frontend
    ],
    allow_origin_regex=r"https://omnishop-.*\.vercel\.app",  # All Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests for monitoring and debugging"""
    start_time = time.time()

    # Get client IP
    client_ip = request.headers.get("x-forwarded-for", request.client.host)

    response = await call_next(request)

    process_time = time.time() - start_time

    logger.info(
        "Request completed",
        extra={
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "process_time": f"{process_time:.3f}s",
            "client_ip": client_ip,
        },
    )

    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)

    return response


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "database": "ready",  # Database sessions managed per-request
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Omnishop API",
        "version": "1.0.0",
        "description": "AI Interior Design Platform API",
        "docs": "/docs" if settings.environment == "development" else None,
        "endpoints": {
            "products": "/api/products",
            "categories": "/api/categories",
            "chat": "/api/chat",
            "visualization": "/api/visualization",
        },
    }


# Debug endpoint to check import status
@app.get("/debug")
async def debug_info():
    """Debug endpoint to check router import status and configuration"""
    import sys

    return {
        "environment": getattr(settings, "environment", "unknown"),
        "routers_imported": {
            "products": "products" in dir(),
            "categories": "categories" in dir(),
            "chat": "chat" in dir(),
            "visualization": "visualization" in dir(),
        },
        "settings_type": str(type(settings)),
        "python_version": sys.version,
        "registered_routes": [route.path for route in app.routes],
        "import_error": import_error_message,
        "import_traceback": import_error_traceback,
        "cors_configured": {
            "allow_origins": getattr(settings, "cors_origins", None),
            "note": "Using allow_origin_regex for Vercel preview deployments",
        },
    }


# OpenAI API test endpoint
@app.get("/debug/openai")
async def test_openai():
    """Test OpenAI API connection"""
    import openai

    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        return {"status": "error", "message": "OPENAI_API_KEY not set"}

    try:
        client = openai.AsyncOpenAI(api_key=api_key, timeout=10.0)
        response = await client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "Say 'API test successful'"}], max_tokens=10
        )

        return {
            "status": "success",
            "message": "OpenAI API is working",
            "response": response.choices[0].message.content,
            "model": response.model,
        }
    except Exception as e:
        return {"status": "error", "message": f"OpenAI API test failed: {str(e)}", "error_type": type(e).__name__}


# Include routers
if "products" in dir():
    app.include_router(products.router, prefix="/api", tags=["products"])

if "categories" in dir():
    app.include_router(categories.router, prefix="/api", tags=["categories"])

if "chat" in dir():
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

if "visualization" in dir():
    app.include_router(visualization.router, prefix="/api", tags=["visualization"])

if "stores" in dir():
    app.include_router(stores.router, tags=["stores"])

if "furniture" in dir():
    app.include_router(furniture.router, tags=["furniture"])

# Additional routers can be added here as needed

# Mount static files for serving images
if os.path.exists("../data/images"):
    app.mount("/static/images", StaticFiles(directory="../data/images"), name="images")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_config=None,  # Use our custom logging
        access_log=False,  # We handle this in middleware
    )
