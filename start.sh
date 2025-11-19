#!/bin/bash
set -e  # Exit on error

echo "=== Railway Startup Script ==="
echo "Current directory: $(pwd)"
echo "Listing root directory:"
ls -la

echo ""
echo "Checking for alembic.ini:"
if [ -f "alembic.ini" ]; then
    echo "✓ alembic.ini found in $(pwd)"
    echo "Running database migrations..."
    python -m alembic upgrade head
else
    echo "✗ alembic.ini NOT found in $(pwd)"
    echo "Contents of current directory:"
    ls -la
    echo ""
    echo "Skipping migrations - continuing with server startup..."
fi

echo ""
echo "Starting FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port $PORT
