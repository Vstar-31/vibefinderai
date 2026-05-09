"""
isrc_mapper.py
──────────────
VibeFinderAI — Cross-Language ISRC Mapper & Metadata Enricher
Place in: backend/data/enrichment/isrc_mapper.py

PURPOSE
-------
Maps tracks across languages and regions by resolving their ISRC codes.

An ISRC (International Standard Recording Code) is the unique ID assigned
to a specific recording. The SAME song released in Hindi + Tamil + Telugu
will have DIFFERENT ISRCs per recording but share the same MusicBrainz
Work ID. This lets us:

  1. Find the "canonical" versions of a track across languages
  2. Enrich TrackFeatureCache with ISRC for Spotify/Apple deep-links
  3. Cluster regional variants (e.g. AR Rahman's same composition in
     Tamil, Hindi, Telugu) so the engine doesn't return duplicates

APIS USED
---------
  MusicBrainz  — Free CC0 data. No key needed. Strict 1 req/s limit.
                 https://musicbrainz.org/doc/MusicBrainz_API
  
  Open licensing: CC0 / CC BY-SA. Safe for all use including commercial.

USAGE
-----
  # Enrich a single track
  python isrc_mapper.py --title "Tum Hi Ho" --artist "Arijit Singh"

  # Batch enrich TrackFeatureCache rows missing ISRCs
  python isrc_mapper.py --batch --limit 500

  # Enrich a specific language pool
  python isrc_mapper.py --batch --language Hindi --limit 200

  # Find all regional variants of a track by Work ID
  python isrc_mapper.py --work-id "mbworkid-here"

ENV VARS
--------
  DATABASE_URL=postgresql://...   # Prisma connection (set in .env)
  MB_EMAIL=your@email.com         # Required in User-Agent per MB ToS
"""

import asyncio
import argparse
import json
import logging
import os
import re
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from prisma import Prisma

load_dotenv()

log = logging.getLogger("VibeFinderAI.ISRCMapper")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

MB_BASE       = "https://musicbrainz.org/ws/2"
MB_EMAIL      = os.getenv("MB_EMAIL", "your@email.com")
MB_USER_AGENT = f"VibeFinderAI/8.0 (https://github.com/yourusername/vibefinder; {MB_EMAIL})"

# MusicBrainz allows 1 req/s strictly. We add 0.15s buffer.
MB_RATE_DELAY = 1.15

# Languages that have high regional variant overlap (AR Rahman, film music, etc.)
REGIONAL_CLUSTER_LANGS = {
    "Tamil", "Telugu", "Malayalam", "Kannada", "Hindi", "Bengali", "Marathi"
}

# ─── RATE LIMITER ────────────────────────────────────────────────────────────

class StrictRateLimiter:
    def __init__(self, delay: float):
        self._delay     = delay
        self._last_call = 0.0
        self._lock      = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now     = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
            self._last_call = time.monotonic()

_mb_limiter = StrictRateLimiter(MB_RATE_DELAY)


# ─── MUSICBRAINZ HELPERS ─────────────────────────────────────────────────────

async def mb_search_recording(
    client: httpx.AsyncClient,
    title: str,
    artist: str,
) -> Optional[dict]:
    """
    Search MusicBrainz for a recording by title + artist.
    Returns the best match dict (score >= 85) or None.
    Includes: mbid, isrc list, work relations, release country.
    """
    await _mb_limiter.acquire()
    try:
        r = await client.get(
            f"{MB_BASE}/recording",
            params={
                "query":  f'recording:"{title}" AND artistname:"{artist}"',
                "limit":  5,
                "fmt":    "json",
                "inc":    "isrcs+artist-credits+releases+work-rels",
            },
            headers={"User-Agent": MB_USER_AGENT},
            timeout=12,
        )
        r.raise_for_status()
        recordings = r.json().get("recordings", [])

        for rec in recordings:
            score = int(rec.get("score", 0))
            if score >= 85:
                return rec

        return None

    except Exception as e:
        log.debug(f"[MB] recording search failed for '{title}' / '{artist}': {e}")
        return None


async def mb_get_recording_isrcs(
    client: httpx.AsyncClient,
    mbid: str,
) -> list[str]:
    """
    Fetch ISRC codes for a known MusicBrainz recording ID.
    Returns a list of ISRC strings (may be empty if MB has no data).
    """
    await _mb_limiter.acquire()
    try:
        r = await client.get(
            f"{MB_BASE}/recording/{mbid}",
            params={"fmt": "json", "inc": "isrcs"},
            headers={"User-Agent": MB_USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("isrcs", [])
    except Exception as e:
        log.debug(f"[MB] ISRC fetch failed for mbid {mbid}: {e}")
        return []


async def mb_get_work_variants(
    client: httpx.AsyncClient,
    work_mbid: str,
) -> list[dict]:
    """
    Given a MusicBrainz Work ID, fetch ALL recordings linked to that work.
    This resolves regional variants: the same song in Tamil, Telugu, Hindi, etc.
    Returns list of {mbid, title, artist, language, isrcs, release_country}.
    """
    await _mb_limiter.acquire()
    try:
        r = await client.get(
            f"{MB_BASE}/work/{work_mbid}",
            params={"fmt": "json", "inc": "recording-rels+artist-rels"},
            headers={"User-Agent": MB_USER_AGENT},
            timeout=12,
        )
        r.raise_for_status()
        data  = r.json()
        rels  = data.get("relations", [])

        variants = []
        for rel in rels:
            if rel.get("type") != "performance":
                continue
            rec = rel.get("recording", {})
            if not rec:
                continue

            artist_credit = rec.get("artist-credit", [{}])
            artist_name   = artist_credit[0].get("artist", {}).get("name", "") if artist_credit else ""

            variants.append({
                "mbid":            rec.get("id"),
                "title":           rec.get("title", ""),
                "artist":          artist_name,
                "language":        data.get("language"),
                "isrcs":           rec.get("isrcs", []),
                "release_country": None,  # populated by caller if needed
            })

        return variants

    except Exception as e:
        log.debug(f"[MB] work variants failed for {work_mbid}: {e}")
        return []


async def extract_work_mbid(recording: dict) -> Optional[str]:
    """Extract the Work MBID from a recording's relations list."""
    for rel in recording.get("relations", []):
        if rel.get("type") == "performance" and "work" in rel:
            return rel["work"].get("id")
    return None


# ─── DB HELPERS ──────────────────────────────────────────────────────────────

async def upsert_isrc(
    db: Prisma,
    title: str,
    artist: str,
    isrc: str,
    mbid: Optional[str] = None,
    work_mbid: Optional[str] = None,
    language: Optional[str] = None,
) -> bool:
    """
    Write ISRC + MBID data back to TrackFeatureCache.
    Uses upsert to avoid duplicates. Returns True on success.
    """
    payload = {
        "title": title,
        "artist": artist,
        "isrc": isrc,
        "mbid": mbid,
        "workMbid": work_mbid,
        "language": language,
    }

    try:
        # First preference: exact ISRC match.
        existing = await db.trackfeaturecache.find_first(where={"isrc": isrc})
        if not existing and mbid:
            # Second preference: MBID match.
            existing = await db.trackfeaturecache.find_first(where={"mbid": mbid})
        if not existing:
            # Final fallback: title+artist row.
            existing = await db.trackfeaturecache.find_first(where={"title": title, "artist": artist})

        if existing:
            await db.trackfeaturecache.update(
                where={"id": existing.id},
                data={k: v for k, v in payload.items() if v is not None},
            )
        else:
            await db.trackfeaturecache.create(
                data={k: v for k, v in payload.items() if v is not None},
            )
        return True
    except Exception as e:
        log.warning(f"[DB] upsert_isrc failed for '{title}': {e}")
        return False


# ─── CROSS-LANGUAGE CLUSTER BUILDER ──────────────────────────────────────────

async def build_regional_clusters(
    db: Prisma,
    language: Optional[str] = None,
    limit: int = 500,
) -> dict[str, list[dict]]:
    """
    For each track in TrackFeatureCache with a workMbid, groups all regional
    variants together. Returns a dict keyed by work_mbid → list of variant dicts.

    This powers the engine's ability to avoid returning the same composition
    twice (e.g. both the Tamil and Hindi version of an AR Rahman score).
    """
    where: dict = {}
    if language:
        where["language"] = language

    try:
        rows = await db.trackfeaturecache.find_many(
            where={**where, "workMbid": {"not": None}},
            take=limit,
        )
    except Exception as e:
        log.error(f"[Cluster] DB fetch failed: {e}")
        return {}

    clusters: dict[str, list[dict]] = {}
    for row in rows:
        key = row.workMbid
        clusters.setdefault(key, []).append({
            "title":    row.title,
            "artist":   row.artist,
            "isrc":     row.isrc,
            "language": row.language,
            "mbid":     row.mbid,
        })

    log.info(f"[Cluster] Built {len(clusters)} work clusters from {len(rows)} cached tracks.")
    return clusters


# ─── SINGLE TRACK ENRICHMENT ─────────────────────────────────────────────────

async def enrich_single_track(
    client: httpx.AsyncClient,
    db: Prisma,
    title: str,
    artist: str,
    language: Optional[str] = None,
    fetch_variants: bool = True,
) -> dict:
    """
    Full enrichment pipeline for one track:
      1. Search MB for recording → get mbid + existing ISRCs
      2. If no ISRCs in search result, fetch separately
      3. Extract Work MBID from recording relations
      4. Optionally fetch all regional work variants
      5. Upsert results to DB

    Returns a dict with all enriched data.
    """
    log.info(f"[Enrich] Processing: '{title}' by '{artist}'")

    recording = await mb_search_recording(client, title, artist)
    if not recording:
        log.warning(f"[Enrich] No MB match for '{title}' / '{artist}'")
        return {"title": title, "artist": artist, "isrcs": [], "variants": []}

    mbid      = recording.get("id")
    isrcs     = recording.get("isrcs", [])
    work_mbid = await extract_work_mbid(recording)

    # Fetch ISRCs separately if not in search result
    if not isrcs and mbid:
        isrcs = await mb_get_recording_isrcs(client, mbid)

    log.info(f"[Enrich] mbid={mbid} | isrcs={isrcs} | work={work_mbid}")

    # Upsert primary track
    for isrc in isrcs:
        await upsert_isrc(db, title, artist, isrc, mbid, work_mbid, language)

    # Fetch regional variants if this is a regional language track
    variants = []
    if fetch_variants and work_mbid and language in REGIONAL_CLUSTER_LANGS:
        variants = await mb_get_work_variants(client, work_mbid)
        log.info(f"[Enrich] Found {len(variants)} regional variants via Work {work_mbid}")

        # Upsert each variant
        for v in variants:
            for v_isrc in v.get("isrcs", []):
                await upsert_isrc(
                    db, v["title"], v["artist"], v_isrc,
                    v.get("mbid"), work_mbid, v.get("language")
                )

    return {
        "title":     title,
        "artist":    artist,
        "mbid":      mbid,
        "isrcs":     isrcs,
        "work_mbid": work_mbid,
        "variants":  variants,
    }


# ─── BATCH ENRICHMENT ────────────────────────────────────────────────────────

async def batch_enrich(
    language: Optional[str] = None,
    limit: int = 500,
    skip_existing: bool = True,
) -> None:
    """
    Batch enrichment: pulls tracks from TrackFeatureCache that are missing
    ISRC data, then enriches them via MusicBrainz.

    Progress is saved after each track — safe to interrupt and resume.
    """
    db = Prisma()
    await db.connect()
    log.info(f"[Batch] Starting ISRC enrichment. language={language}, limit={limit}")

    try:
        where: dict = {}
        if skip_existing:
            where["OR"] = [{"isrc": None}, {"isrc": ""}]  # only enrich rows missing ISRC
        if language:
            where["language"] = language

        rows = await db.trackfeaturecache.find_many(
            where=where,
            take=limit,
            order={"id": "asc"},
        )

        log.info(f"[Batch] {len(rows)} tracks to enrich.")

        enriched  = 0
        failed    = 0
        no_match  = 0

        async with httpx.AsyncClient() as client:
            for i, row in enumerate(rows, 1):
                try:
                    result = await enrich_single_track(
                        client, db,
                        title=row.title,
                        artist=row.artist,
                        language=row.language or language,
                        fetch_variants=(row.language in REGIONAL_CLUSTER_LANGS
                                        if row.language else False),
                    )
                    if result["isrcs"]:
                        enriched += 1
                        log.info(
                            f"[{i}/{len(rows)}] ✓ {row.title} | "
                            f"isrcs={result['isrcs']} | variants={len(result['variants'])}"
                        )
                    else:
                        no_match += 1
                        log.debug(f"[{i}/{len(rows)}] ○ No MB match: {row.title}")

                except Exception as e:
                    failed += 1
                    log.error(f"[{i}/{len(rows)}] ✗ Error on '{row.title}': {e}")

        log.info(
            f"\n[Batch] Complete! "
            f"Enriched={enriched} | NoMatch={no_match} | Failed={failed} | "
            f"Total={len(rows)}"
        )

    finally:
        await db.disconnect()


# ─── FASTAPI UTILITY (inline use in main.py) ─────────────────────────────────

async def get_isrc_for_track(
    title: str,
    artist: str,
    db: Prisma,
) -> Optional[str]:
    """
    Hot-path ISRC lookup: checks DB cache first, hits MB only on miss.
    Returns first ISRC found or None. Used to enrich track cards in real-time.

    NOTE: This is deliberately a single-track lookup. Do NOT call this in a
    loop for every track in a playlist — use batch_enrich for that.
    """
    # 1. Check cache
    try:
        cached = await db.trackfeaturecache.find_first(
            where={"title": title, "artist": artist, "isrc": {"not": None}}
        )
        if cached and cached.isrc:
            return cached.isrc
    except Exception:
        pass

    # 2. MB lookup (respects rate limiter)
    async with httpx.AsyncClient() as client:
        rec = await mb_search_recording(client, title, artist)
        if not rec:
            return None

        isrcs = rec.get("isrcs", [])
        if not isrcs:
            mbid  = rec.get("id")
            if mbid:
                isrcs = await mb_get_recording_isrcs(client, mbid)

        if isrcs:
            # Cache the result for future calls
            await upsert_isrc(db, title, artist, isrcs[0], rec.get("id"))
            return isrcs[0]

    return None


# ─── CLI ENTRYPOINT ──────────────────────────────────────────────────────────

async def _cli_main():
    parser = argparse.ArgumentParser(description="VibeFinderAI ISRC Mapper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--batch",     action="store_true",      help="Batch enrich TrackFeatureCache")
    group.add_argument("--title",     type=str,                  help="Single track title")
    group.add_argument("--work-id",  type=str, default=None,    help="Find variants for a Work MBID")
    parser.add_argument("--artist",   type=str, default="",      help="Artist name (with --title)")
    parser.add_argument("--language", type=str, default=None,    help="Filter by language")
    parser.add_argument("--limit",    type=int, default=500,     help="Max tracks to process")
    args = parser.parse_args()

    if args.batch:
        await batch_enrich(language=args.language, limit=args.limit)

    elif args.title:
        if not args.artist:
            parser.error("--artist is required when using --title")
        db = Prisma()
        await db.connect()
        async with httpx.AsyncClient() as client:
            result = await enrich_single_track(
                client, db,
                title=args.title,
                artist=args.artist,
                language=args.language,
                fetch_variants=True,
            )
        await db.disconnect()
        print(json.dumps(result, indent=2))

    elif args.work_id:
        async with httpx.AsyncClient() as client:
            variants = await mb_get_work_variants(client, args.work_id)
        print(json.dumps(variants, indent=2))


if __name__ == "__main__":
    asyncio.run(_cli_main())
