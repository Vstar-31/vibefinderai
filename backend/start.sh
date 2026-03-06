#!/bin/bash
set -e

echo "=== VibeFinderAI Backend Startup ==="

# ── Prisma: only re-generate if schema changed or binaries missing ─────────
# On Render, the Prisma binary is cached at a stable path after first install.
# Re-running 'prisma generate' every boot wastes ~60s. We skip it if:
#   1. The Prisma binary already exists in the cache
#   2. The schema hasn't changed since last generate (checked via hash)

PRISMA_CACHE_DIR="${HOME}/.cache/prisma-python/binaries"
SCHEMA_HASH_FILE=".prisma_schema_hash"
CURRENT_HASH=$(md5sum schema.prisma 2>/dev/null | cut -d' ' -f1 || echo "none")
CACHED_HASH=$(cat "$SCHEMA_HASH_FILE" 2>/dev/null || echo "")
PRISMA_BINARY_EXISTS=$(find "$PRISMA_CACHE_DIR" -name "query-engine*" 2>/dev/null | head -1)

if [ -n "$PRISMA_BINARY_EXISTS" ] && [ "$CURRENT_HASH" = "$CACHED_HASH" ]; then
    echo "[Prisma] Binary cached and schema unchanged — skipping generate (saves ~60s)"
else
    echo "[Prisma] Installing CLI and generating client..."
    pip install prisma --quiet --no-deps 2>/dev/null || pip install prisma --quiet
    prisma generate
    echo "$CURRENT_HASH" > "$SCHEMA_HASH_FILE"
    echo "[Prisma] Generate complete."
fi

# ── NOTE: sentence-transformers / torch intentionally NOT loaded ───────────
# These packages exceed Render free tier RAM (512 MB).
# The semantic fallback in semantic_search.py degrades gracefully when the
# model is absent — all NLP heuristic + audio feature scoring still works.

echo "Starting uvicorn server..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT:-10000}" \
    --workers 1 \
    --loop uvloop \
    --http httptools \
    --log-level warning \
    --no-access-log
