"""
FastAPI main application for Omnishop
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import time
import sys
import os

# Add parent directory to path to import from scrapers
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from api.routers import products, categories, chat, visualization
    from api.core.config import settings
    # from api.core.database import database
    from api.core.logging import setup_logging

    # Setup logging
    setup_logging()
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback imports for basic functionality
    settings = None
    def setup_logging():
        logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Omnishop API...")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
        }
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
        "database": "ready"  # Database sessions managed per-request
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
            "visualization": "/api/visualization"
        }
    }


# Include routers
app.include_router(
    products.router,
    prefix="/api",
    tags=["products"]
)

app.include_router(
    categories.router,
    prefix="/api",
    tags=["categories"]
)

app.include_router(
    chat.router,
    prefix="/api/chat",
    tags=["chat"]
)

app.include_router(
    visualization.router,
    prefix="/api",
    tags=["visualization"]
)

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