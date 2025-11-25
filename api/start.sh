#!/bin/bash

# Error handling: log errors but try to continue
set -o pipefail

# Color codes for better visibility
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Timestamp function
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

log_info() {
    echo -e "${BLUE}[$(timestamp)] INFO:${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(timestamp)] SUCCESS:${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(timestamp)] WARNING:${NC} $1"
}

log_error() {
    echo -e "${RED}[$(timestamp)] ERROR:${NC} $1"
}

# Error trap
trap 'log_error "Script failed at line $LINENO"' ERR

log_info "=== Railway Startup Script Starting ==="
log_info "Current directory: $(pwd)"
log_info "Current user: $(whoami)"

# Show Python version
log_info "Python version: $(python --version 2>&1)"

# Check environment variables
log_info "=== Environment Variables Check ==="
if [ -z "$PORT" ]; then
    log_warning "PORT is not set, using default: 8000"
    export PORT=8000
else
    log_success "PORT is set to: $PORT"
fi

if [ -z "$DATABASE_URL" ]; then
    log_error "DATABASE_URL is not set!"
    log_warning "Migrations will likely fail"
else
    # Sanitize and show DATABASE_URL (hide password)
    SANITIZED_URL=$(echo "$DATABASE_URL" | sed 's/:\/\/[^:]*:[^@]*@/:\/\/***:***@/')
    log_success "DATABASE_URL is set: $SANITIZED_URL"
fi

# Check OpenAI API Key
if [ -z "$OPENAI_API_KEY" ]; then
    log_error "OPENAI_API_KEY is not set!"
    log_error "Chat functionality will not work without this key"
else
    # Show first/last few characters only
    KEY_PREVIEW="${OPENAI_API_KEY:0:7}...${OPENAI_API_KEY: -4}"
    log_success "OPENAI_API_KEY is set: $KEY_PREVIEW"
fi

# Check Google AI API Key
if [ -z "$GOOGLE_AI_API_KEY" ]; then
    log_error "GOOGLE_AI_API_KEY is not set!"
    log_error "Image analysis functionality will not work without this key"
else
    # Show first/last few characters only
    KEY_PREVIEW="${GOOGLE_AI_API_KEY:0:7}...${GOOGLE_AI_API_KEY: -4}"
    log_success "GOOGLE_AI_API_KEY is set: $KEY_PREVIEW"
fi

# Validate PORT is a number
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    log_error "PORT must be a number, got: $PORT"
    log_warning "Setting PORT to 8000"
    export PORT=8000
fi

# Show directory contents
log_info "=== Directory Contents ==="
ls -la

# Check for required files
log_info "=== Checking for required files ==="
if [ -f "main.py" ]; then
    log_success "main.py found"
else
    log_error "main.py NOT found in $(pwd)"
    log_error "Available Python files:"
    ls -la *.py 2>/dev/null || log_error "No Python files found"
fi

if [ -f "alembic.ini" ]; then
    log_success "alembic.ini found"
else
    log_warning "alembic.ini NOT found in $(pwd)"
fi

if [ -d "alembic" ]; then
    log_success "alembic directory found"
else
    log_warning "alembic directory NOT found"
fi

# Run database migrations
log_info "=== Database Migration Phase ==="
if [ -f "alembic.ini" ]; then
    log_info "Running database migrations..."
    if python -m alembic upgrade head; then
        log_success "Database migrations completed successfully"
    else
        log_error "Database migrations failed!"
        log_warning "Continuing with server startup anyway..."
    fi
else
    log_warning "Skipping migrations - alembic.ini not found"
fi

# Start FastAPI server
log_info "=== Starting FastAPI Server ==="
log_info "Server configuration:"
log_info "  - Host: 0.0.0.0"
log_info "  - Port: $PORT"
log_info "  - Application: main:app"

# Check if main.py exists before starting
if [ ! -f "main.py" ]; then
    log_error "Cannot start server: main.py not found!"
    log_error "Working directory: $(pwd)"
    log_error "Please check your deployment configuration"
    exit 1
fi

log_info "Executing: uvicorn main:app --host 0.0.0.0 --port $PORT"
log_success "Starting uvicorn..."

# Start uvicorn in background temporarily to warm cache
uvicorn main:app --host 0.0.0.0 --port $PORT &
UVICORN_PID=$!

# Wait for server to be ready
log_info "Waiting for server to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
        log_success "Server is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        log_warning "Server health check timed out after 30 seconds"
        log_warning "Skipping cache warming"
        break
    fi
    sleep 1
done

# Warm the cache
log_info "=== Cache Warming Phase ==="
if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
    log_info "Warming stores cache..."
    if python scripts/warm_cache.py --url http://localhost:$PORT; then
        log_success "Cache warmed successfully"
    else
        log_warning "Cache warming failed, but continuing..."
    fi
else
    log_warning "Server not responding, skipping cache warming"
fi

# Bring uvicorn to foreground
log_success "Cache warming complete, server running in foreground"
wait $UVICORN_PID
