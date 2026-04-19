FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by MNE
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch FIRST (much smaller — fits Render's 512MB free tier)
# Default 'torch' includes GPU/CUDA which is ~2GB and OOMs on free tier
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy and install remaining requirements (torch already installed above, skip it)
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
