#!/bin/bash
set -e

echo "=== VibeFinderAI Backend Startup ==="
echo "Python version:"
python --version

echo -e "\nSetting up Prisma binaries..."
export PRISMA_CLI_BINARY_TARGETS=debian-openssl-3.0
prisma py fetch
touch /tmp/prisma-ready

echo "Waiting for binaries to initialize..."
sleep 15

if [ ! -f /tmp/prisma-ready ]; then
    echo "ERROR: Prisma binaries failed to initialize"
    exit 1
fi

echo -e "\nStarting uvicorn server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
