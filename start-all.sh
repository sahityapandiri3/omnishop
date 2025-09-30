#!/bin/bash

echo "🚀 Starting Omnishop Full Stack Application..."

# Function to handle cleanup on script exit
cleanup() {
    echo "🛑 Stopping all services..."
    jobs -p | xargs -r kill
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Make scripts executable
chmod +x start-frontend.sh
chmod +x start-backend.sh

# Start backend in background
echo "🔧 Starting backend server..."
./start-backend.sh &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend in background
echo "🎨 Starting frontend application..."
./start-frontend.sh &
FRONTEND_PID=$!

echo ""
echo "✅ Omnishop is starting up!"
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for processes to finish
wait