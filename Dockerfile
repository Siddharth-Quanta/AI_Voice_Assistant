# KOTS Voice Assistant - Cloud Run Optimized Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy cloud requirements first for better caching
COPY requirements-cloud.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run the application with longer timeout for startup
CMD exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --timeout-keep-alive 300
