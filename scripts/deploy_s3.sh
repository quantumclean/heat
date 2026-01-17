#!/bin/bash
# HEAT - Deploy to AWS S3
# Syncs the build folder to S3 static website hosting

set -e

# --- CONFIGURATION ---
# Change this to your bucket name
BUCKET_NAME="your-heat-map-bucket"
REGION="us-east-1"

echo "========================================"
echo "HEAT S3 Deployment"
echo "========================================"
echo

cd "$(dirname "$0")/.."

echo "Deploying to S3 bucket: $BUCKET_NAME"
echo

# Sync build folder to S3
aws s3 sync build/ s3://$BUCKET_NAME/ \
    --delete \
    --cache-control "max-age=3600" \
    --exclude ".DS_Store" \
    --exclude "*.map"

echo
echo "========================================"
echo "Deployment complete!"
echo
echo "Your site is available at:"
echo "http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"
echo "========================================"
