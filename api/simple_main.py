"""
Simple FastAPI application for Omnishop API - Basic version without database
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Omnishop API",
    description="AI-powered interior design visualization and product recommendation API",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Omnishop API",
        "version": "1.0.0",
        "description": "AI-powered interior design visualization and product recommendation API",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/api/products")
async def get_products():
    """Mock products endpoint"""
    return {
        "items": [
            {
                "id": 1,
                "name": "Modern Sofa",
                "price": 899.99,
                "currency": "USD",
                "brand": "West Elm",
                "source_website": "westelm.com",
                "is_available": True,
                "is_on_sale": False
            },
            {
                "id": 2,
                "name": "Coffee Table",
                "price": 299.99,
                "currency": "USD",
                "brand": "Orange Tree",
                "source_website": "orangetree.com",
                "is_available": True,
                "is_on_sale": True
            }
        ],
        "total": 2,
        "page": 1,
        "size": 20,
        "pages": 1,
        "has_next": False,
        "has_prev": False
    }

@app.get("/api/categories")
async def get_categories():
    """Mock categories endpoint"""
    return [
        {"id": 1, "name": "Furniture", "slug": "furniture", "product_count": 150},
        {"id": 2, "name": "Lighting", "slug": "lighting", "product_count": 75},
        {"id": 3, "name": "Decor", "slug": "decor", "product_count": 200}
    ]

@app.post("/api/chat/sessions")
async def start_chat_session():
    """Mock chat session endpoint"""
    return {
        "session_id": "mock-session-123",
        "message": "Hello! I'm your AI interior design assistant. How can I help you transform your space today?"
    }

@app.post("/api/chat/sessions/{session_id}/messages")
async def send_chat_message(session_id: str):
    """Mock chat message endpoint"""
    return {
        "message": {
            "id": "mock-message-456",
            "type": "assistant",
            "content": "I'd be happy to help you design your space! Could you tell me more about the room you're working with and your style preferences?",
            "timestamp": "2024-01-01T00:00:00Z",
            "session_id": session_id
        },
        "analysis": None,
        "recommended_products": []
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "simple_main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )