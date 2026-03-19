#!/usr/bin/env python3
"""
test_batch_imports.py — Verify all imports in batch_tester_v10k_2.py are correct
"""
import sys
import os

print("=" * 80)
print("  IMPORT VERIFICATION FOR batch_tester_v10k_2.py")
print("=" * 80 + "\n")

# Test 1: Core module imports
print("[1] Testing core module imports...")
try:
    from core import vibe_engine
    print("  ✓ from core import vibe_engine")
except ImportError as e:
    print(f"  ✗ from core import vibe_engine: {e}")

try:
    from core.vibe_engine import LANGUAGE_TAG_MAP
    print("  ✓ from core.vibe_engine import LANGUAGE_TAG_MAP")
except ImportError as e:
    print(f"  ✗ from core.vibe_engine import LANGUAGE_TAG_MAP: {e}")

# Test 2: Main module imports
print("\n[2] Testing main module imports...")
required_functions = [
    'fetch_lastfm_tracks',
    'fetch_lastfm_artist_tracks',
    'fetch_lastfm_track_search',
    'filter_and_score_tracks',
]

required_classes = [
    'VibeRequest',
]

required_constants = [
    'COMMON_WORDS_BLACKLIST',
    'TRACK_BLOCKLIST',
]

for func in required_functions:
    try:
        exec(f"from main import {func}")
        print(f"  ✓ from main import {func}")
    except ImportError as e:
        print(f"  ✗ from main import {func}: {e}")

for cls in required_classes:
    try:
        exec(f"from main import {cls}")
        print(f"  ✓ from main import {cls}")
    except ImportError as e:
        print(f"  ✗ from main import {cls}: {e}")

for const in required_constants:
    try:
        exec(f"from main import {const}")
        print(f"  ✓ from main import {const}")
    except ImportError as e:
        print(f"  ✗ from main import {const}: {e}")

# Test 3: Other imports
print("\n[3] Testing other imports...")
try:
    from prisma import Prisma
    print("  ✓ from prisma import Prisma")
except ImportError as e:
    print(f"  ✗ from prisma import Prisma: {e}")

try:
    import aiohttp
    print("  ✓ import aiohttp")
except ImportError as e:
    print(f"  ⚠ import aiohttp: {e} (optional)")

try:
    import asyncio
    print("  ✓ import asyncio")
except ImportError as e:
    print(f"  ✗ import asyncio: {e}")

try:
    import logging
    print("  ✓ import logging")
except ImportError as e:
    print(f"  ✗ import logging: {e}")

print("\n[4] Testing environment variables...")
from dotenv import load_dotenv
load_dotenv()

env_vars = [
    'GEMINI_API_KEY',
    'LASTFM_API_KEY',
    'YOUTUBE_API_KEY',
    'METRICS_PASSPHRASE',
]

for var in env_vars:
    val = os.getenv(var)
    if val:
        print(f"  ✓ {var} is set")
    else:
        print(f"  ⚠ {var} is NOT set (optional)")

print("\n" + "=" * 80)
print("  IMPORT VERIFICATION COMPLETE")
print("=" * 80 + "\n")
