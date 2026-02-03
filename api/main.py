"""
FastAPI main application for Omnishop
"""
import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Load environment variables from .env file FIRST (before any other imports)
from dotenv import load_dotenv

# Find and load .env file from api directory
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"✅ Loaded .env file from: {env_path}")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

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
    from routers import (
        admin_curated,
        admin_migrations,
        auth,
        categories,
        chat,
        curated,
        furniture,
        homestyling,
        permissions,
        products,
        projects,
        stores,
        visualization,
        wall_colors,
        wall_textures,
    )
    from routers.curated import warm_curated_looks_cache
    from services.furniture_removal_service import furniture_removal_service

    from core.config import settings
    from core.database import AsyncSessionLocal

    # from core.database import database
    from core.logging import setup_logging

    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("✅ All routers imported successfully")

    # Flag to track if furniture cleanup service was imported
    furniture_cleanup_available = True
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
    furniture_cleanup_available = False
    warm_curated_looks_cache = None
    AsyncSessionLocal = None

    def setup_logging():
        logging.basicConfig(level=logging.INFO)


# Background task for periodic furniture job cleanup
async def periodic_furniture_cleanup():
    """Background task that cleans up stale furniture removal jobs every 30 minutes"""
    while True:
        await asyncio.sleep(30 * 60)  # Wait 30 minutes between cleanups
        try:
            if furniture_cleanup_available:
                removed = furniture_removal_service.cleanup_stale_jobs()
                stats = furniture_removal_service.get_job_stats()
                logger.info(f"Periodic furniture cleanup: removed {removed} jobs, {stats['total']} remaining")
        except Exception as e:
            logger.error(f"Error in periodic furniture cleanup: {e}")


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

    # Ensure budget_tier column exists (fix for production)
    if AsyncSessionLocal:
        try:
            from sqlalchemy import text

            async with AsyncSessionLocal() as session:
                # Check if column exists
                result = await session.execute(
                    text(
                        """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'curated_looks' AND column_name = 'budget_tier'
                """
                    )
                )
                column_exists = result.fetchone() is not None

                if not column_exists:
                    logger.info("🔧 Adding missing budget_tier column to curated_looks...")
                    # Create enum type if not exists
                    await session.execute(
                        text(
                            """
                        DO $$ BEGIN
                            CREATE TYPE budgettier AS ENUM ('pocket_friendly', 'mid_tier', 'premium', 'luxury');
                        EXCEPTION
                            WHEN duplicate_object THEN null;
                        END $$;
                    """
                        )
                    )
                    # Add column
                    await session.execute(
                        text(
                            """
                        ALTER TABLE curated_looks ADD COLUMN IF NOT EXISTS budget_tier VARCHAR(50)
                    """
                        )
                    )
                    await session.commit()
                    logger.info("✅ Added budget_tier column to curated_looks")
                else:
                    logger.info("✅ budget_tier column already exists")
        except Exception as e:
            logger.error(f"❌ Failed to check/add budget_tier column: {e}")

    # Start background cleanup task for furniture removal jobs
    cleanup_task = None
    if furniture_cleanup_available:
        cleanup_task = asyncio.create_task(periodic_furniture_cleanup())
        logger.info("✅ Started periodic furniture job cleanup task (every 30 min)")

    # Warm up curated looks cache for faster first request
    if warm_curated_looks_cache and AsyncSessionLocal:
        try:
            await warm_curated_looks_cache(AsyncSessionLocal)
        except Exception as e:
            logger.error(f"Failed to warm curated looks cache: {e}")

    # Database connection is managed by SQLAlchemy async session
    # No explicit connect/disconnect needed
    logger.info("Application started")

    yield

    # Shutdown
    logger.info("Shutting down Omnishop API...")

    # Cancel the background cleanup task
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Furniture cleanup task cancelled")

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
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://omnishop-three.vercel.app",  # Old production frontend (keep during transition)
        "https://omni-shop.in",  # Custom domain frontend
        "https://www.omni-shop.in",  # Custom domain frontend with www
    ],
    allow_origin_regex=r"https://omnishop-.*\.vercel\.app",  # All Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request logging middleware with correlation IDs
try:
    from middleware.logging_middleware import RequestLoggingMiddleware

    app.add_middleware(RequestLoggingMiddleware)
    logger.info("✅ Request logging middleware enabled with correlation IDs")
except ImportError as e:
    logger.warning(f"Could not import RequestLoggingMiddleware: {e}")

    # Fallback to basic logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Fallback: Log all requests for monitoring and debugging"""
        start_time = time.time()
        client_ip = request.headers.get("x-forwarded-for", request.client.host)
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"Request: {request.method} {request.url.path} -> {response.status_code} ({process_time:.3f}s)",
            extra={"method": request.method, "status_code": response.status_code, "client_ip": client_ip},
        )
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
    app.include_router(furniture.router, prefix="/api/furniture", tags=["furniture"])

if "curated" in dir():
    app.include_router(curated.router, prefix="/api", tags=["curated"])

if "admin_curated" in dir():
    app.include_router(admin_curated.router, prefix="/api", tags=["admin-curated"])

if "auth" in dir():
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

if "projects" in dir():
    app.include_router(projects.router, prefix="/api/projects", tags=["projects"])

if "admin_migrations" in dir():
    app.include_router(admin_migrations.router, prefix="/api", tags=["admin"])

if "permissions" in dir():
    app.include_router(permissions.router, prefix="/api", tags=["permissions"])

if "homestyling" in dir():
    app.include_router(homestyling.router, prefix="/api", tags=["homestyling"])

if "wall_colors" in dir():
    app.include_router(wall_colors.router, prefix="/api", tags=["wall-colors"])

if "wall_textures" in dir():
    app.include_router(wall_textures.router, prefix="/api", tags=["wall-textures"])

# Additional routers can be added here as needed

# Mount static files for serving images
if os.path.exists("../data/images"):
    app.mount("/static/images", StaticFiles(directory="../data/images"), name="images")

# Mount static files for style thumbnails (used by onboarding wizard)
styles_dir = os.path.join(os.path.dirname(__file__), "static/styles")
if os.path.exists(styles_dir):
    app.mount("/api/styles", StaticFiles(directory=styles_dir), name="styles")

# Mount static files for room type thumbnails (used by onboarding wizard)
rooms_dir = os.path.join(os.path.dirname(__file__), "static/rooms")
if os.path.exists(rooms_dir):
    app.mount("/api/rooms", StaticFiles(directory=rooms_dir), name="rooms")

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
