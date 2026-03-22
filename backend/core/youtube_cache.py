"""
youtube_cache.py
────────────────
VibeFinderAI — Persistent YouTube search cache backed by ThinPoolCache table.

Replaces the in-memory _YT_SEARCH_CACHE dict in services_routes.py, which
was reset on every Render deploy. This module stores video_id lookups in the
existing ThinPoolCache table (using a "yt:" prefix on the cacheKey) so the
7-day TTL survives cold starts.

Usage in services_routes.py:
    from core.youtube_cache import yt_cache_get, yt_cache_set, yt_cache_stats

    # Replace _yt_cache_get / _yt_cache_set calls with these.
    # _db must be set before use (called from set_db()).
"""

import json
import logging
import time as _time
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("VibeFinderEngine.YouTubeCache")

_db = None
_YT_CACHE_TTL_DAYS = 7

# In-process L1 cache — avoids a DB hit for the same track within one request
# burst. Capped at 5000 entries with simple LRU-ish eviction (discard oldest).
_L1: dict[str, tuple[str, float]] = {}  # key → (video_id, expires_unix)
_L1_MAX = 5000
_L1_TTL = _YT_CACHE_TTL_DAYS * 24 * 3600


def init(db) -> None:
    """Call once from services_routes.set_db()."""
    global _db
    _db = db


def _cache_key(title: str, artist: str) -> str:
    return "yt:" + f"{title.strip().lower()}|{artist.strip().lower()}".replace(" ", "_")


# ── L1 helpers ────────────────────────────────────────────────────────────────

def _l1_get(key: str) -> Optional[str]:
    entry = _L1.get(key)
    if not entry:
        return None
    video_id, expires = entry
    if _time.time() > expires:
        del _L1[key]
        return None
    return video_id


def _l1_set(key: str, video_id: str) -> None:
    if len(_L1) >= _L1_MAX:
        # Evict oldest 10%
        cutoff = _time.time()
        expired = [k for k, (_, exp) in _L1.items() if exp < cutoff]
        for k in expired[:max(1, _L1_MAX // 10)]:
            _L1.pop(k, None)
        # If nothing expired, evict first N items
        if len(_L1) >= _L1_MAX:
            for k in list(_L1.keys())[:_L1_MAX // 10]:
                del _L1[k]
    _L1[key] = (video_id, _time.time() + _L1_TTL)


# ── Public API ────────────────────────────────────────────────────────────────

async def yt_cache_get(title: str, artist: str) -> Optional[str]:
    """
    Returns cached video_id or None.
    Checks L1 (in-process) first, then ThinPoolCache (DB).
    """
    key = _cache_key(title, artist)

    # L1 hit
    hit = _l1_get(key)
    if hit:
        return hit

    # DB hit
    if _db is None:
        return None
    try:
        row = await _db.thinpoolcache.find_unique(where={"cacheKey": key})
        if not row:
            return None
        now = datetime.now(timezone.utc)
        expires = row.expiresAt
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now > expires:
            return None
        # tracksJson stores {"video_id": "..."} for YouTube entries
        data = json.loads(row.tracksJson)
        video_id = data.get("video_id")
        if video_id:
            _l1_set(key, video_id)
        return video_id
    except Exception as e:
        logger.debug(f"[YTCache] DB get failed for '{title}': {e}")
        return None


async def yt_cache_set(title: str, artist: str, video_id: str) -> None:
    """
    Store video_id in both L1 and ThinPoolCache DB.
    Uses upsert so re-runs are safe.
    """
    key = _cache_key(title, artist)
    _l1_set(key, video_id)

    if _db is None:
        return
    try:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=_YT_CACHE_TTL_DAYS)
        payload = json.dumps({"video_id": video_id})
        await _db.thinpoolcache.upsert(
            where={"cacheKey": key},
            data={
                "create": {
                    "cacheKey":   key,
                    "tracksJson": payload,
                    "trackCount": 1,
                    "source":     "youtube_search",
                    "fetchedAt":  now,
                    "expiresAt":  expires_at,
                },
                "update": {
                    "tracksJson": payload,
                    "fetchedAt":  now,
                    "expiresAt":  expires_at,
                },
            },
        )
    except Exception as e:
        logger.debug(f"[YTCache] DB set failed for '{title}': {e}")


async def yt_cache_stats() -> dict:
    """Returns cache stats for the /api/services/youtube/cache-stats endpoint."""
    now_ts = _time.time()
    l1_valid = sum(1 for _, exp in _L1.values() if exp > now_ts)

    db_count = 0
    if _db is not None:
        try:
            db_count = await _db.thinpoolcache.count(
                where={"cacheKey": {"startswith": "yt:"}}
            )
        except Exception:
            pass

    return {
        "l1_entries": len(_L1),
        "l1_valid_entries": l1_valid,
        "db_entries": db_count,
        "ttl_days": _YT_CACHE_TTL_DAYS,
        "quota_saved_est": (l1_valid + db_count) * 100,
    }
