# Multi-stage production Dockerfile for VIDYA-X AI
FROM python:3.12-slim AS base

# System dependencies: FFmpeg for audio/video extraction, build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./backend/requirements.txt

# Copy source code
COPY backend ./backend
COPY frontend ./frontend
COPY scripts ./scripts

# Create persistent storage directories
RUN mkdir -p /app/backend/uploads /app/backend/visual_assets /app/backend/extracted

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/vidya_x

# Create unprivileged application user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check using the new /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
