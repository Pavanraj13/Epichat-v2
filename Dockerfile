FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by MNE
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements first (better Docker layer caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code AND the root scripts/ folder (needed by analysis.py)
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Create necessary runtime directories
RUN mkdir -p backend/data/uploads backend/data/db

# Expose port
EXPOSE 8000

# Run FastAPI from backend/app directory
CMD ["sh", "-c", "cd /app/backend/app && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
