#!/bin/bash
set -e

echo "=== VibeFinderAI Backend Startup ==="

# Fetch the binaries explicitly
prisma py fetch

# Generate the client
prisma generate

echo "Starting uvicorn server..."
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
