# ===========================================================
# HEAT — Multi-stage Docker build
# Stage 1: Python backend (WebSocket server + pipeline)
# Stage 2: Nginx static frontend + TLS reverse proxy
# ===========================================================

# ---- Stage 1: Python backend ----
FROM python:3.11-slim AS backend

LABEL maintainer="HEAT Project" \
      description="HEAT WebSocket server and processing pipeline"

WORKDIR /app

# Install system deps for numpy/scipy/hdbscan
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir websockets

# Copy processing code
COPY processing/ /app/processing/
COPY run_pipeline.py /app/
COPY scheduler.py /app/

# Copy data directories
COPY data/ /app/data/
COPY build/data/ /app/build/data/

# Create log/output directories
RUN mkdir -p /app/data/logs /app/data/processed /app/build/data /app/build/exports

# Non-root user for security
RUN groupadd -r heat && useradd -r -g heat -d /app heat && \
    chown -R heat:heat /app
USER heat

# WebSocket port
EXPOSE 8765

# Health check — verify WebSocket is accepting connections
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import asyncio, websockets; asyncio.run(websockets.connect('ws://localhost:8765').__aenter__())" || exit 1

CMD ["python", "-m", "processing.websocket_server"]


# ---- Stage 2: Nginx frontend with TLS ----
FROM nginx:1.25-alpine AS frontend

LABEL maintainer="HEAT Project" \
      description="HEAT static frontend with TLS termination"

# Copy static site
COPY build/ /usr/share/nginx/html/

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY deploy/nginx.conf /etc/nginx/conf.d/heat.conf

# Create directory for TLS certificates
RUN mkdir -p /etc/nginx/ssl

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
