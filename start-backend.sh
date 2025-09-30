#!/bin/bash

echo "🚀 Starting Omnishop Backend..."

# Check if we're in the right directory
if [ ! -d "api" ]; then
    echo "❌ Error: api directory not found. Please run this script from the root of the omnishop project."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found. Creating one from .env.example"
    cp .env.example .env
    echo "✏️  Please edit .env file with your actual configuration values before running the backend."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
    echo "📦 Installing Python dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "🐍 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if requirements.txt exists and install dependencies
if [ -f "requirements.txt" ]; then
    echo "📦 Installing/updating Python dependencies..."
    pip install -r requirements.txt
else
    echo "⚠️  Warning: requirements.txt not found. Installing core dependencies..."
    pip install fastapi uvicorn sqlalchemy asyncpg openai python-dotenv pydantic pillow structlog databases
fi

# Start the FastAPI server
echo "🌐 Starting FastAPI server on http://localhost:8000"
echo "📚 API documentation available at http://localhost:8000/docs"

cd api
# Try the full version first, fallback to simple version
if python -c "import main" 2>/dev/null; then
    echo "🚀 Starting full API with database support..."
    python main.py
else
    echo "🚧 Starting simple API (database not configured)..."
    python simple_main.py
fi