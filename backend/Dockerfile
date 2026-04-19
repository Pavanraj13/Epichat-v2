FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed by MNE
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend
COPY . .

# Create necessary directories
RUN mkdir -p data/uploads data/db

# Expose the port Render / Railway uses
EXPOSE 8000

# Start the FastAPI server
# Note: Render injects $PORT automatically
CMD ["sh", "-c", "cd app && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
