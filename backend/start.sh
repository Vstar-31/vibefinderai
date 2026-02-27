#!/bin/bash
set -e

echo "Fetching Prisma binaries..."
prisma py fetch

echo "Waiting for binaries to be ready..."
sleep 10

echo "Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
