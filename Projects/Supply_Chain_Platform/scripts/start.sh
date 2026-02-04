#!/bin/bash
# Startup script for Railway deployment
# Runs migrations then starts the FastAPI app

set -e

echo "=== Une Femme Supply Chain Platform ==="
echo "Starting deployment..."

# Run database migrations
echo "Running database migrations..."
python -m alembic upgrade head

echo "Migrations complete!"

# Start the FastAPI application
echo "Starting FastAPI server..."
exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
