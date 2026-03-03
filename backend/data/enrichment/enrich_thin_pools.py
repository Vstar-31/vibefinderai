"""
enrich_thin_pools.py
════════════════════
VibeFinderAI — Offline Thin Pool Cache Builder  (NEW — v1.0)

PURPOSE
-------
Pre-fetches and caches track pools for Language×Vibe combos that consistently
return fewer than 20 results from Last.fm (identified from the 10k QA batch run).

These pre-built pools are stored in ThinPoolCache (schema.prisma) and served
by semantic_search.get_thin_pool_supplement() in the hot query path — providing
a fast Stage 2 fallback before the generic dream-pop safety pool.

WHY THIS EXISTS
---------------
The 10k QA analysis revealed these combos have critically thin Last.fm pools:

  SIGNAL LOST (0 tracks):
    punjabi_soft × any language   — Last.fm has no "b praak" or "ap dhillon" tags
    haryanvi × any language       — "ragini" tag returns nothing

  THIN (<10 avg scored):
    bollywood_sad × Hindi         — pooled tags consistently return <15
    Japanese × ambient            — niche intersection, LFM doesn't tag this well
    Japanese × heartbreak         — same issue
    Arabic × any                  — Arabic tags on Last.fm are sparse
    Any × Direct                  — direct search fallback hits dead ends

STRATEGY
--------
For each thin combo, we use a ranked source strategy:
  1. ListenBrainz Radio (radio:similar-to:<mbid>) — rich, genre-aware
  2. TheAudioDB artist top tracks — reliable for known artists
  3. MusicBrainz search — broad but accurate
  4. Last.fm artist top tracks — as a last resort via direct artist names

All sources are tried in order and results are merged/deduplicated.
The final pool is stored in ThinPoolCache with a 7-day TTL.

APIS USED
---------
  ListenBrainz  — CC0 / open. Commercial use allowed per MetaBrainz.
                  Needs a free LB user token from listenbrainz.org/settings/
                  Set env: LISTENBRAINZ_TOKEN=your_token

  MusicBrainz   — CC0. Free. 1 req/s rate limit. No key needed.

  TheAudioDB    — Free test key "2". For production: $8/mo Patreon.
                  Set env: THEAUDIODB_KEY=2

  Last.fm       — Free, attribution required.
                  Set env: LASTFM_API_KEY=your_key

USAGE
-----
  # Run for all known thin combos (recommended: run weekly)
  python enrich_thin_pools.py

  # Run for a specific combo
  python enrich_thin_pools.py --language punjabi_soft --vibe Any

  # Dry run (prints what would be fetched, no DB writes)
  python enrich_thin_pools.py --dry-run

  # Check current cache health
  python enrich_thin_pools.py --health

SCHEDULING
----------
Add to cron (weekly refresh):
  0 3 * * 1 /path/to/venv/bin/python /path/to/enrich_thin_pools.py >> /var/log/vibefinder_thin.log 2>&1
"""

import asyncio
import argparse
import json
import logging
import os
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from dotenv import load_dotenv
from prisma import Prisma

load_dotenv()

# ─── CONFIG ──────────────────────────────────────────────────────────────────

LB_BASE      = "https://api.listenbrainz.org/1"
MB_BASE      = "https://musicbrainz.org/ws/2"
TADB_BASE    = "https://www.theaudiodb.com/api/v1/json"
LASTFM_BASE  = "http://ws.audioscrobbler.com/2.0"

LB_TOKEN     = os.getenv("LISTENBRAINZ_TOKEN", "")
TADB_KEY     = os.getenv("THEAUDIODB_KEY", "2")
LASTFM_KEY   = os.getenv("LASTFM_API_KEY", "")
MB_UA        = "VibeFinderAI/1.0 (vibefinder-thin-pools; contact@vibefinder.ai)"

CACHE_TTL_DAYS = 7
MIN_POOL_TARGET = 40  # aim for at least this many tracks per combo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("VibeFinderAI.ThinPools")


# ─── KNOWN THIN COMBOS ───────────────────────────────────────────────────────
# Identified from 10k QA batch. Format: (language, vibe, artist_seeds, lb_tags)
# artist_seeds: used for artist-based fetches (Last.fm/TADB)
# lb_tags: Last.fm tag names to try as supplement
# ─────────────────────────────────────────────────────────────────────────────

THIN_COMBOS: list[dict] = [
    # ── punjabi_soft — 0% success rate in QA, ALL signal lost ────────────────
    {
        "language": "punjabi_soft", "vibe": "Any",
        "artist_seeds": [
            "B Praak", "AP Dhillon", "Satinder Sartaaj", "Prabh Gill",
            "Jassi Gill", "Ninja", "Mankirt Aulakh", "Jassie Gill",
            "Ammy Virk", "Sharry Mann",
        ],
        "lb_tags": ["punjabi sad", "punjabi ballad", "punjabi soft pop"],
        "description": "Thin: tag-based fetch returns 0 (artist names mistaken for tags)",
    },
    # ── haryanvi — avg 6 scored tracks ───────────────────────────────────────
    {
        "language": "haryanvi", "vibe": "Any",
        "artist_seeds": [
            "Sapna Choudhary", "Masoom Sharma", "Raju Punjabi", "Pardeep Boora",
            "Ajay Hooda", "Amit Dhull", "Vikram Pannu", "Renuka Panwar",
            "KD Desi Rock", "Sumit Goswami",
        ],
        "lb_tags": ["haryanvi", "haryanvi folk"],
        "description": "Thin: 'ragini' tag returns near-zero on Last.fm",
    },
    # ── bollywood_sad Hindi — avg 7 scored tracks ─────────────────────────────
    {
        "language": "bollywood_sad", "vibe": "Hindi",
        "artist_seeds": [
            "Arijit Singh", "Atif Aslam", "KK", "Mohit Chauhan",
            "Shreya Ghoshal", "Jubin Nautiyal", "Armaan Malik",
            "Rahat Fateh Ali Khan", "Udit Narayan",
        ],
        "lb_tags": ["bollywood sad", "filmi sad", "hindi sad songs"],
        "description": "Thin: filmi sad tag pools score poorly after diversity guard",
    },
    # ── Japanese×ambient ─────────────────────────────────────────────────────
    {
        "language": "Japanese", "vibe": "ambient",
        "artist_seeds": [
            "Hiroshi Yoshimura", "Haruomi Hosono", "Midori Takada",
            "Susumu Yokota", "Yas-Kaz", "Yasuaki Shimizu", "Colleen",
        ],
        "lb_tags": ["japanese ambient", "kankyo ongaku", "japanese new age"],
        "description": "Thin: niche intersection, Last.fm has sparse Japanese ambient tags",
    },
    # ── Japanese×heartbreak ──────────────────────────────────────────────────
    {
        "language": "Japanese", "vibe": "heartbreak",
        "artist_seeds": [
            "Hikaru Utada", "Aimyon", "Yonezu Kenshi", "MISIA",
            "Superfly", "Cocco", "Ringo Sheena",
        ],
        "lb_tags": ["j-pop ballad", "japanese sad", "jpop heartbreak"],
        "description": "Thin: Japanese×heartbreak intersection has limited Last.fm coverage",
    },
    # ── Arabic×any ───────────────────────────────────────────────────────────
    {
        "language": "Arabic", "vibe": "Any",
        "artist_seeds": [
            "Fairuz", "Umm Kulthum", "Abdel Halim Hafez", "Wael Kfoury",
            "Amr Diab", "Kadim Al Sahir", "Nancy Ajram", "Elissa",
            "Mohammed Abdo", "Majid Al Mohandis",
        ],
        "lb_tags": ["arabic pop", "arabic music", "arabic ballad", "arabic sad"],
        "description": "Thin: Arabic tags sparsely represented on Last.fm",
    },
    # ── Korean×Direct (fallback) ─────────────────────────────────────────────
    {
        "language": "Korean", "vibe": "Direct",
        "artist_seeds": [
            "IU", "BTS", "BLACKPINK", "Epik High", "Zion.T",
            "Dean", "Crush", "Heize", "Paul Kim", "Lim Young Woong",
        ],
        "lb_tags": ["k-pop", "korean indie", "k-rnb", "korean ballad"],
        "description": "Thin: Direct search for Korean prompts hits low-result zone",
    },
    # ── Bengali×any ──────────────────────────────────────────────────────────
    {
        "language": "Bengali", "vibe": "Any",
        "artist_seeds": [
            "Rabindranath Tagore", "Hemanta Mukherjee", "Manna Dey",
            "Lata Mangeshkar Bengali", "Kumar Sanu Bengali",
            "Arijit Singh Bengali", "Nachiketa Chakraborty",
        ],
        "lb_tags": ["bengali music", "rabindra sangeet", "bengali folk"],
        "description": "Thin: Bengali tags are very sparse on Last.fm",
    },
]


# ─── RATE LIMITER ────────────────────────────────────────────────────────────

class RateLimiter:
    def __init__(self, calls_per_second: float):
        self.min_interval = 1.0 / calls_per_second
        self._last_call   = 0.0
        self._lock        = asyncio.Lock()

    async def __aenter__(self):
        async with self._lock:
            elapsed = time.monotonic() - self._last_call
            wait    = self.min_interval - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()
        return self

    async def __aexit__(self, *_):
        pass


_mb_rl   = RateLimiter(0.9)   # MusicBrainz: 1 req/s
_lb_rl   = RateLimiter(2.0)   # ListenBrainz: generous
_lfm_rl  = RateLimiter(4.0)   # Last.fm: very generous
_tadb_rl = RateLimiter(1.8)   # TheAudioDB: 2 req/s


# ─── FETCHERS ────────────────────────────────────────────────────────────────

async def fetch_lastfm_artist_tracks(
    client: httpx.AsyncClient, artist: str, limit: int = 50
) -> list[dict]:
    """Fetch top tracks for an artist via Last.fm API."""
    if not LASTFM_KEY:
        log.warning("LASTFM_API_KEY not set — skipping Last.fm artist fetch")
        return []
    async with _lfm_rl:
        try:
            url = (
                f"{LASTFM_BASE}/?method=artist.gettoptracks"
                f"&artist={urllib.parse.quote(artist)}"
                f"&api_key={LASTFM_KEY}&format=json&limit={limit}"
            )
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            data  = r.json()
            tracks = data.get("toptracks", {}).get("track", [])
            result = [
                {"title": t.get("name"), "artist": t.get("artist", {}).get("name")}
                for t in tracks
                if t.get("name") and t.get("artist", {}).get("name")
            ]
            log.debug(f"Last.fm: {len(result)} tracks for artist '{artist}'")
            return result
        except Exception as e:
            log.warning(f"Last.fm artist fetch failed for '{artist}': {e}")
            return []


async def fetch_lastfm_tag_tracks(
    client: httpx.AsyncClient, tag: str, limit: int = 50
) -> list[dict]:
    """Fetch top tracks for a Last.fm tag."""
    if not LASTFM_KEY:
        return []
    async with _lfm_rl:
        try:
            url = (
                f"{LASTFM_BASE}/?method=tag.gettoptracks"
                f"&tag={urllib.parse.quote(tag)}"
                f"&api_key={LASTFM_KEY}&format=json&limit={limit}"
            )
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            data   = r.json()
            tracks = data.get("tracks", {}).get("track", [])
            result = [
                {"title": t.get("name"), "artist": t.get("artist", {}).get("name")}
                for t in tracks
                if t.get("name") and t.get("artist", {}).get("name")
            ]
            log.debug(f"Last.fm tag '{tag}': {len(result)} tracks")
            return result
        except Exception as e:
            log.warning(f"Last.fm tag fetch failed for '{tag}': {e}")
            return []


async def mb_lookup_artist_mbid(
    client: httpx.AsyncClient, artist_name: str
) -> Optional[str]:
    """Return the MusicBrainz artist MBID for a given name."""
    async with _mb_rl:
        try:
            url = (
                f"{MB_BASE}/artist/?query=artist:{urllib.parse.quote(artist_name)}"
                f"&fmt=json&limit=1"
            )
            r = await client.get(
                url, timeout=10,
                headers={"User-Agent": MB_UA, "Accept": "application/json"},
            )
            r.raise_for_status()
            data    = r.json()
            artists = data.get("artists", [])
            if artists:
                mbid = artists[0].get("id")
                log.debug(f"MB: MBID for '{artist_name}' = {mbid}")
                return mbid
        except Exception as e:
            log.warning(f"MB artist lookup failed for '{artist_name}': {e}")
    return None


async def lb_similar_recordings(
    client: httpx.AsyncClient, mbid: str, count: int = 30
) -> list[dict]:
    """
    Use ListenBrainz radio endpoint to get similar recordings for a seed MBID.
    Returns list of {title, artist, mbid} dicts.
    """
    if not LB_TOKEN:
        log.warning("LISTENBRAINZ_TOKEN not set — skipping LB radio fetch")
        return []
    async with _lb_rl:
        try:
            url = f"{LB_BASE}/explore/lb-radio?prompt=artist:{mbid}&mode=easy&count={count}"
            r = await client.get(
                url, timeout=15,
                headers={"Authorization": f"Token {LB_TOKEN}", "Accept": "application/json"},
            )
            if r.status_code == 404:
                log.debug(f"LB radio: no results for mbid={mbid}")
                return []
            r.raise_for_status()
            data = r.json()
            tracks = data.get("payload", {}).get("jspf", {}).get("track", [])
            result = []
            for t in tracks:
                title  = t.get("title") or t.get("track", {}).get("title", "")
                artist = t.get("creator") or t.get("track", {}).get("creator", "")
                if title and artist:
                    result.append({"title": title, "artist": artist})
            log.debug(f"LB radio: {len(result)} similar recordings for mbid={mbid}")
            return result
        except Exception as e:
            log.warning(f"LB radio failed for mbid={mbid}: {e}")
            return []


async def tadb_artist_top_tracks(
    client: httpx.AsyncClient, artist_name: str, limit: int = 10
) -> list[dict]:
    """Fetch top tracks for an artist via TheAudioDB."""
    async with _tadb_rl:
        try:
            url = f"{TADB_BASE}/{TADB_KEY}/track-top10.php?s={urllib.parse.quote(artist_name)}"
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            data   = r.json()
            tracks = data.get("track") or []
            result = [
                {"title": t.get("strTrack"), "artist": t.get("strArtist")}
                for t in tracks
                if t.get("strTrack") and t.get("strArtist")
            ]
            log.debug(f"TADB: {len(result)} top tracks for '{artist_name}'")
            return result[:limit]
        except Exception as e:
            log.warning(f"TADB top tracks failed for '{artist_name}': {e}")
            return []


# ─── POOL BUILDER ─────────────────────────────────────────────────────────────

def _dedupe(tracks: list[dict]) -> list[dict]:
    """Remove duplicates by title+artist key, preserving order."""
    seen   = set()
    result = []
    for t in tracks:
        title  = (t.get("title") or "").strip().lower()
        artist = (t.get("artist") or "").strip().lower()
        if not title or not artist:
            continue
        key = f"{title}|{artist}"
        if key not in seen:
            seen.add(key)
            result.append({"title": t["title"], "artist": t["artist"]})
    return result


async def build_pool_for_combo(
    client: httpx.AsyncClient, combo: dict, dry_run: bool = False
) -> list[dict]:
    """
    Build a rich track pool for a single Language×Vibe thin combo using
    all available sources in priority order.
    """
    lang     = combo["language"]
    vibe     = combo["vibe"]
    artists  = combo.get("artist_seeds", [])
    tags     = combo.get("lb_tags", [])
    pool     = []

    log.info(f"Building pool for: {lang}×{vibe} (target={MIN_POOL_TARGET})")

    # ── Stage 1: Last.fm tag-based fetch ─────────────────────────────────────
    tag_tasks = [fetch_lastfm_tag_tracks(client, tag, limit=50) for tag in tags]
    tag_results = await asyncio.gather(*tag_tasks, return_exceptions=True)
    for r in tag_results:
        if isinstance(r, list):
            pool.extend(r)
    log.info(f"  After LFM tags: {len(_dedupe(pool))} tracks")

    # ── Stage 2: Last.fm artist top-tracks ───────────────────────────────────
    if len(_dedupe(pool)) < MIN_POOL_TARGET:
        artist_tasks = [
            fetch_lastfm_artist_tracks(client, artist, limit=30)
            for artist in artists
        ]
        artist_results = await asyncio.gather(*artist_tasks, return_exceptions=True)
        for r in artist_results:
            if isinstance(r, list):
                pool.extend(r)
        log.info(f"  After LFM artists: {len(_dedupe(pool))} tracks")

    # ── Stage 3: TheAudioDB top-10 per artist ────────────────────────────────
    if len(_dedupe(pool)) < MIN_POOL_TARGET:
        tadb_tasks = [tadb_artist_top_tracks(client, a) for a in artists[:5]]
        tadb_results = await asyncio.gather(*tadb_tasks, return_exceptions=True)
        for r in tadb_results:
            if isinstance(r, list):
                pool.extend(r)
        log.info(f"  After TADB: {len(_dedupe(pool))} tracks")

    # ── Stage 4: ListenBrainz Radio (artist MBID → similar recordings) ────────
    if len(_dedupe(pool)) < MIN_POOL_TARGET and LB_TOKEN:
        for artist in artists[:3]:  # only seed from top 3 artists to avoid rate spam
            mbid = await mb_lookup_artist_mbid(client, artist)
            if mbid:
                lb_tracks = await lb_similar_recordings(client, mbid, count=25)
                pool.extend(lb_tracks)
                if len(_dedupe(pool)) >= MIN_POOL_TARGET:
                    break
        log.info(f"  After LB radio: {len(_dedupe(pool))} tracks")

    final_pool = _dedupe(pool)
    log.info(f"Final pool for {lang}×{vibe}: {len(final_pool)} unique tracks")

    if len(final_pool) < 5:
        log.warning(f"  ⚠ Pool critically thin ({len(final_pool)} tracks). May need more artist seeds.")

    return final_pool


# ─── DB WRITE ─────────────────────────────────────────────────────────────────

async def write_to_cache(
    db: Prisma, language: str, vibe: str,
    tracks: list[dict], source: str = "mixed",
    ttl_days: int = CACHE_TTL_DAYS,
) -> None:
    """Upsert a ThinPoolCache row for the given language×vibe combo."""
    cache_key  = f"{language}|{vibe}"
    now        = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=ttl_days)

    try:
        await db.thinpoolcache.upsert(
            where={"cacheKey": cache_key},
            data={
                "create": {
                    "cacheKey":   cache_key,
                    "tracksJson": json.dumps(tracks),
                    "trackCount": len(tracks),
                    "source":     source,
                    "fetchedAt":  now,
                    "expiresAt":  expires_at,
                },
                "update": {
                    "tracksJson": json.dumps(tracks),
                    "trackCount": len(tracks),
                    "source":     source,
                    "fetchedAt":  now,
                    "expiresAt":  expires_at,
                },
            },
        )
        log.info(f"✓ Cached {len(tracks)} tracks for '{cache_key}' (expires {expires_at.date()})")
    except Exception as e:
        log.error(f"DB write failed for '{cache_key}': {e}")


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────

async def run_health_check(db: Prisma) -> None:
    """Print current ThinPoolCache status."""
    rows = await db.thinpoolcache.find_many(order={"fetchedAt": "desc"})
    now  = datetime.now(timezone.utc)

    print(f"\n{'═'*60}")
    print(f"  ThinPoolCache Health Report  ({len(rows)} entries)")
    print(f"{'═'*60}")
    if not rows:
        print("  No entries found. Run without --health to populate.")
    for row in rows:
        expires = row.expiresAt
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        status = "✓ FRESH" if now < expires else "✗ EXPIRED"
        days_left = (expires - now).days
        print(
            f"  {status:12} | {row.cacheKey:30} | "
            f"{row.trackCount:3} tracks | {days_left:+3}d"
        )
    print(f"{'═'*60}\n")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="VibeFinderAI — Thin Pool Cache Builder")
    parser.add_argument("--language", type=str, help="Specific language key to process")
    parser.add_argument("--vibe",     type=str, help="Specific vibe to process")
    parser.add_argument("--dry-run",  action="store_true", help="Fetch but don't write to DB")
    parser.add_argument("--health",   action="store_true", help="Print cache health and exit")
    args = parser.parse_args()

    db = Prisma()
    await db.connect()
    log.info("DB connected.")

    try:
        if args.health:
            await run_health_check(db)
            return

        # Filter to specific combo if requested
        combos = THIN_COMBOS
        if args.language or args.vibe:
            combos = [
                c for c in THIN_COMBOS
                if (not args.language or c["language"].lower() == args.language.lower())
                and (not args.vibe or c["vibe"].lower() == args.vibe.lower())
            ]
            if not combos:
                log.error(f"No matching combo for language={args.language} vibe={args.vibe}")
                return

        total_start = time.monotonic()

        async with httpx.AsyncClient() as client:
            for combo in combos:
                start = time.monotonic()
                lang  = combo["language"]
                vibe  = combo["vibe"]
                desc  = combo.get("description", "")
                log.info(f"\n── Processing: {lang}×{vibe}")
                if desc:
                    log.info(f"   Reason: {desc}")

                tracks = await build_pool_for_combo(client, combo, dry_run=args.dry_run)

                if args.dry_run:
                    log.info(f"[DRY RUN] Would cache {len(tracks)} tracks for '{lang}|{vibe}'")
                    for t in tracks[:5]:
                        log.info(f"   Sample: {t['title']} — {t['artist']}")
                else:
                    await write_to_cache(db, lang, vibe, tracks, source="mixed")

                elapsed = time.monotonic() - start
                log.info(f"   Done in {elapsed:.1f}s")

        total = time.monotonic() - total_start
        log.info(f"\n✓ All combos processed in {total:.1f}s")

        if not args.dry_run:
            await run_health_check(db)

    finally:
        await db.disconnect()
        log.info("DB disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
