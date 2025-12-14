FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    wget \
    git \
    postgresql-client \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p logs data/images data/reports

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port for potential API
EXPOSE 8000

# Start the API server
# Railway root is /api, so files (main.py, alembic.ini, start.sh) are in /app
# start.sh handles: migrations, uvicorn startup, and cache warming
CMD ["bash", "start.sh"]
