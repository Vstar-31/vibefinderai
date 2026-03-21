"""
itunes_enrichment.py
────────────────────
VibeFinderAI Phase 9 — Bulk iTunes Metadata Enrichment
Place in: backend/scripts/itunes_enrichment.py

PURPOSE
-------
84.7% of returned tracks have no preview URL or cover art.
This script hits the iTunes Search API (free, no auth) for the
top N most-served tracks and populates TrackFeatureCache with:
  - preview_url    → 30s MP3 preview
  - artwork_url    → 100×100 cover art (scaled to 600×600)
  - duration_ms    → track duration
  - primary_genre  → iTunes genre name (cross-check for filtering)
  - apple_id       → iTunes track ID (for future Apple Music deep links)

USAGE
-----
  # Enrich top 5000 most-served tracks:
  python scripts/itunes_enrichment.py --limit 5000

  # Enrich specific tracks from a file (one "title|artist" per line):
  python scripts/itunes_enrichment.py --from-file tracks.txt

  # Dry run — see what would be fetched without writing to DB:
  python scripts/itunes_enrichment.py --limit 100 --dry-run

  # Resume from where you left off (skips already-enriched tracks):
  python scripts/itunes_enrichment.py --limit 5000 --skip-existing

RATE LIMITING
-------------
iTunes Search API: no auth, no documented rate limit, but be polite.
We use 3 concurrent workers + 0.1s delay between batches.
At this rate: ~5000 tracks enriched in ~5 minutes.

ENV VARS
--------
  DATABASE_URL   → set in .env (loaded automatically)
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import aiohttp
from dotenv import load_dotenv

# ── Path setup ───────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

load_dotenv(dotenv_path=_BACKEND_DIR / ".env", override=False)
load_dotenv(override=False)

from prisma import Prisma  # noqa: E402

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("iTunes.Enrichment")

# ── Constants ─────────────────────────────────────────────────────────────────
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
CONCURRENT_WORKERS = 3
BATCH_PAUSE_SECONDS = 0.1
REQUEST_TIMEOUT_SECONDS = 8

# ── iTunes API helpers ───────────────────────────────────────────────────────

def _build_itunes_url(title: str, artist: str) -> str:
    term = f"{title} {artist}"
    return f"{ITUNES_SEARCH_URL}?term={quote(term)}&entity=song&limit=3&media=music"


def _best_match(results: list[dict], title: str, artist: str) -> dict | None:
    """Pick the best matching iTunes result from up to 3 candidates."""
    title_lower = title.lower().strip()
    artist_lower = artist.lower().strip()

    for r in results:
        r_title = (r.get("trackName") or "").lower().strip()
        r_artist = (r.get("artistName") or "").lower().strip()
        # Exact match on both — best case
        if title_lower == r_title and artist_lower in r_artist:
            return r
    for r in results:
        r_title = (r.get("trackName") or "").lower().strip()
        r_artist = (r.get("artistName") or "").lower().strip()
        # Title match + artist starts with
        if title_lower in r_title and artist_lower[:6] in r_artist:
            return r
    # Fallback: return first result if title words mostly match
    if results:
        r = results[0]
        r_title = (r.get("trackName") or "").lower()
        title_words = [w for w in title_lower.split() if len(w) > 2]
        matches = sum(1 for w in title_words if w in r_title)
        if matches / max(len(title_words), 1) >= 0.6:
            return r
    return None


async def _fetch_itunes(
    session: aiohttp.ClientSession,
    title: str,
    artist: str,
) -> dict | None:
    """Fetch iTunes metadata for one track. Returns dict or None."""
    url = _build_itunes_url(title, artist)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
            results = data.get("results", [])
            if not results:
                return None
            match = _best_match(results, title, artist)
            if not match:
                return None

            artwork = match.get("artworkUrl100", "")
            # Upgrade artwork to 600×600
            if artwork:
                artwork = re.sub(r"100x100bb", "600x600bb", artwork)

            return {
                "preview_url":   match.get("previewUrl"),
                "artwork_url":   artwork or None,
                "duration_ms":   match.get("trackTimeMillis"),
                "primary_genre": match.get("primaryGenreName"),
                "apple_id":      str(match.get("trackId", "")) or None,
                "itunes_track":  match.get("trackName"),
                "itunes_artist": match.get("artistName"),
            }
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        logger.debug(f"iTunes fetch error for '{title}': {e}")
        return None


# ── DB helpers ───────────────────────────────────────────────────────────────

async def _get_top_tracks(db: Prisma, limit: int) -> list[tuple[str, str]]:
    """
    Get the most-served tracks from VibeRequest.returnedTracks JSON column.
    Returns list of (title, artist) tuples ordered by frequency.
    """
    logger.info(f"Scanning VibeRequest history for top {limit} tracks...")
    rows = await db.viberequest.find_many(
        take=5000,  # scan last 5000 requests
        order={"createdAt": "desc"},
    )

    track_counts: dict[tuple, int] = {}
    for row in rows:
        try:
            if not row.returnedTracks:
                continue
            tracks = json.loads(row.returnedTracks or "[]")
            for t in tracks:
                title = (t.get("title") or "").strip()
                artist = (t.get("artist") or "").strip()
                if title and artist:
                    key = (title.lower(), artist.lower())
                    track_counts[key] = track_counts.get(key, 0) + 1
        except Exception:
            continue

    sorted_tracks = sorted(track_counts.items(), key=lambda x: -x[1])
    top = [(t[0][0].title(), t[0][1].title()) for t in sorted_tracks[:limit]]
    logger.info(f"Found {len(top)} unique tracks to enrich")
    return top


async def _get_existing_enriched(db: Prisma) -> set[str]:
    """Get set of 'title|artist' keys already in TrackFeatureCache."""
    try:
        rows = await db.trackfeaturecache.find_many()
        return {
            f"{(r.trackTitle or '').lower()}|{(r.trackArtist or '').lower()}"
            for r in rows
            if getattr(r, "previewUrl", None)
        }
    except Exception as e:
        logger.warning(f"Could not fetch existing enriched tracks: {e}")
        return set()


async def _upsert_track_cache(
    db: Prisma,
    title: str,
    artist: str,
    data: dict,
) -> bool:
    """Upsert enriched data into TrackFeatureCache."""
    try:
        existing = await db.trackfeaturecache.find_first(
            where={"trackTitle": title, "trackArtist": artist}
        )
        update_data = {}
        if data.get("preview_url"):
            update_data["previewUrl"] = data["preview_url"]
        if data.get("artwork_url"):
            update_data["artworkUrl"] = data["artwork_url"]
        if data.get("duration_ms"):
            update_data["durationMs"] = int(data["duration_ms"])
        if data.get("apple_id"):
            update_data["appleId"] = data["apple_id"]

        if not update_data:
            return False  # Nothing useful from iTunes

        if existing:
            await db.trackfeaturecache.update(
                where={"id": existing.id},
                data=update_data,
            )
        else:
            await db.trackfeaturecache.create(data={
                "trackTitle":  title,
                "trackArtist": artist,
                **update_data,
            })
        return True
    except Exception as e:
        logger.debug(f"DB upsert failed for '{title}': {e}")
        return False


# ── Worker ───────────────────────────────────────────────────────────────────

async def _worker(
    worker_id: int,
    queue: asyncio.Queue,
    db: Prisma,
    session: aiohttp.ClientSession,
    counters: dict,
    dry_run: bool,
):
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break

        title, artist = item
        result = await _fetch_itunes(session, title, artist)

        if result:
            has_preview = bool(result.get("preview_url"))
            has_art = bool(result.get("artwork_url"))

            if not dry_run:
                saved = await _upsert_track_cache(db, title, artist, result)
                if saved:
                    counters["enriched"] += 1
                    if has_preview:
                        counters["with_preview"] += 1
                    if has_art:
                        counters["with_art"] += 1
            else:
                counters["enriched"] += 1
                if has_preview:
                    counters["with_preview"] += 1
                logger.info(f"[DRY RUN] '{title}' — preview={has_preview} art={has_art}")
        else:
            counters["not_found"] += 1

        counters["processed"] += 1
        if counters["processed"] % 100 == 0:
            pct = counters["processed"] / counters["total"] * 100
            logger.info(
                f"Progress: {counters['processed']}/{counters['total']} ({pct:.0f}%) | "
                f"enriched={counters['enriched']} previews={counters['with_preview']} "
                f"not_found={counters['not_found']}"
            )

        queue.task_done()
        await asyncio.sleep(BATCH_PAUSE_SECONDS / CONCURRENT_WORKERS)


# ── Main ─────────────────────────────────────────────────────────────────────

async def run_enrichment(
    limit: int = 5000,
    from_file: str | None = None,
    skip_existing: bool = True,
    dry_run: bool = False,
):
    db = Prisma()
    await db.connect()
    logger.info(f"DB connected. Mode: {'DRY RUN' if dry_run else 'LIVE'}")

    # Get tracks to enrich
    if from_file:
        logger.info(f"Loading tracks from {from_file}...")
        tracks = []
        with open(from_file) as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) >= 2:
                    tracks.append((parts[0].strip(), parts[1].strip()))
    else:
        tracks = await _get_top_tracks(db, limit)

    # Filter already-enriched
    if skip_existing:
        existing = await _get_existing_enriched(db)
        before = len(tracks)
        tracks = [
            (t, a) for t, a in tracks
            if f"{t.lower()}|{a.lower()}" not in existing
        ]
        logger.info(f"Skipped {before - len(tracks)} already-enriched tracks. "
                    f"{len(tracks)} remaining.")

    if not tracks:
        logger.info("Nothing to enrich. All tracks already have metadata.")
        await db.disconnect()
        return

    counters = {
        "total": len(tracks),
        "processed": 0,
        "enriched": 0,
        "with_preview": 0,
        "with_art": 0,
        "not_found": 0,
    }

    queue: asyncio.Queue = asyncio.Queue()
    for t in tracks:
        await queue.put(t)
    for _ in range(CONCURRENT_WORKERS):
        await queue.put(None)  # Sentinel per worker

    start = time.monotonic()

    connector = aiohttp.TCPConnector(limit=CONCURRENT_WORKERS + 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        workers = [
            asyncio.create_task(
                _worker(i, queue, db, session, counters, dry_run)
            )
            for i in range(CONCURRENT_WORKERS)
        ]
        await queue.join()
        for w in workers:
            w.cancel()

    elapsed = time.monotonic() - start
    await db.disconnect()

    logger.info("=" * 60)
    logger.info(f"DONE in {elapsed:.1f}s")
    logger.info(f"  Processed:    {counters['processed']}")
    logger.info(f"  Enriched:     {counters['enriched']}")
    logger.info(f"  With preview: {counters['with_preview']}")
    logger.info(f"  With art:     {counters['with_art']}")
    logger.info(f"  Not found:    {counters['not_found']}")
    if not dry_run:
        logger.info(f"TrackFeatureCache now has previews for "
                    f"{counters['with_preview']} additional tracks.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="iTunes bulk enrichment for VibeFinderAI")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Max tracks to enrich (default: 5000)")
    parser.add_argument("--from-file", type=str, default=None,
                        help="File with 'title|artist' per line instead of DB scan")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip tracks already in TrackFeatureCache (default: on)")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Fetch from iTunes but don't write to DB")
    args = parser.parse_args()

    asyncio.run(run_enrichment(
        limit=args.limit,
        from_file=args.from_file,
        skip_existing=args.skip_existing,
        dry_run=args.dry_run,
    ))
