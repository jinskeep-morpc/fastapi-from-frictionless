#!/bin/bash
set -e

SCHEMA_DIR="${SCHEMA_FOLDER:-/schemas}"

echo "Generating FastAPI application from schemas in ${SCHEMA_DIR}..."
mkdir -p /app/api
fastapifromfrictionless generate "${SCHEMA_DIR}" --output /app/api
touch /app/api/__init__.py

echo "Starting API server on port 8000..."
cd /app
exec uvicorn api.app:app --host 0.0.0.0 --port 8000
