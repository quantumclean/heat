#!/bin/bash
# HEAT - Run Data Processing Pipeline
# Processes raw CSVs through ingestion, clustering, buffering, and export

set -e

echo "========================================"
echo "HEAT Data Processing Pipeline"
echo "========================================"
echo

cd "$(dirname "$0")/.."

echo "[1/4] Running ingestion..."
python processing/ingest.py

echo
echo "[2/4] Running clustering..."
python processing/cluster.py

echo
echo "[3/4] Applying safety buffer..."
python processing/buffer.py

echo
echo "[4/4] Exporting static files..."
python processing/export_static.py

echo
echo "========================================"
echo "Pipeline complete!"
echo "Static files ready in: build/data/"
echo "========================================"
