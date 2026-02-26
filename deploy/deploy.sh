#!/bin/bash
# ===========================================================
# HEAT — Production Deployment Script
# Sets up TLS certificates and starts all services
# ===========================================================
set -euo pipefail

DOMAIN="${HEAT_DOMAIN:-heat.example.com}"
EMAIL="${HEAT_EMAIL:-admin@example.com}"

echo "=============================================="
echo "  HEAT Production Deployment"
echo "  Domain: $DOMAIN"
echo "  Email:  $EMAIL"
echo "=============================================="

# Step 1: Build images
echo "[1/4] Building Docker images..."
docker compose build

# Step 2: Start nginx with temporary self-signed cert for ACME
echo "[2/4] Starting services with temporary certificate..."

# Generate temporary self-signed cert if no real cert exists
if [ ! -f "./deploy/ssl/fullchain.pem" ]; then
    echo "  Generating temporary self-signed certificate..."
    mkdir -p "./deploy/ssl"
    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout "./deploy/ssl/privkey.pem" \
        -out "./deploy/ssl/fullchain.pem" \
        -subj "/CN=$DOMAIN" \
        -days 1
fi

# Start frontend + websocket (without certbot initially)
docker compose up -d frontend websocket

# Step 3: Obtain real Let's Encrypt certificate
echo "[3/4] Requesting Let's Encrypt certificate..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

# Step 4: Reload nginx with real certificate
echo "[4/4] Reloading nginx with production certificate..."
docker compose exec frontend nginx -s reload

# Start certbot renewal daemon
docker compose up -d certbot

echo ""
echo "=============================================="
echo "  HEAT is now running!"
echo "  Frontend: https://$DOMAIN"
echo "  WebSocket: wss://$DOMAIN/ws"
echo "=============================================="
echo ""
echo "Useful commands:"
echo "  docker compose logs -f           # View all logs"
echo "  docker compose logs websocket    # WebSocket logs"
echo "  docker compose restart frontend  # Reload nginx"
echo "  docker compose down              # Stop all services"
