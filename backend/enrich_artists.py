"""
enrich_artists.py
─────────────────
VibeFinderAI — Offline Artist Enrichment Script (CONCURRENT EDITION 🚀)

PURPOSE
-------
One-time (then weekly cron) script that populates the new fields on
ArtistDirectory: mbid, mbTags, lbSimilarArtists, tadbId, tadbMood,
tadbStyle, tadbTop10.

Run AFTER seed_artists.py. Safe to re-run — all operations are upserts.

APIS USED
---------
  MusicBrainz  — CC0 core data. Free non-commercial. 1 req/s rate limit.
                 ⚠️  Contact MetaBrainz for commercial plan when monetising.
                 No API key needed. User-Agent header required.

  ListenBrainz — CC0 / open. Commercial use allowed (MetaBrainz tiers).
                 Needs a free LB user token from listenbrainz.org/settings/.
                 Set env: LISTENBRAINZ_TOKEN=your_token_here

  TheAudioDB   — Free test key "2", 2 req/s.
                 ⚠️  For production: upgrade to $8/mo Patreon key.
                 Set env: THEAUDIODB_KEY=2  (or your paid key)

USAGE
-----
  python enrich_artists.py                  # enrich all missing artists (resume mode)
  python enrich_artists.py --limit 50       # enrich first 50 (test run)
  python enrich_artists.py --artist "Adele" # enrich single artist
  python enrich_artists.py --phase mb       # MusicBrainz only
  python enrich_artists.py --phase lb       # ListenBrainz only
  python enrich_artists.py --phase tadb     # TheAudioDB only

TIMING
------
  Uses async workers + strict global rate limiters to safely maximize throughput.
  Theoretical max: ~3600 artists/hour (bottlenecked purely by MB's 1 req/s).
"""

import asyncio
import argparse
import json
import logging
import os
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from prisma import Prisma

load_dotenv()

# ─── CONFIG ──────────────────────────────────────────────────────────────────

MB_BASE        = "https://musicbrainz.org/ws/2"
LB_BASE        = "https://api.listenbrainz.org/1"
TADB_BASE      = "https://www.theaudiodb.com/api/v1/json"

# MusicBrainz requires a descriptive User-Agent or you get blocked
MB_USER_AGENT  = "VibeFinderAI/8.0 (https://github.com/yourusername/vibefinder; your@email.com)"

LB_TOKEN       = os.getenv("LISTENBRAINZ_TOKEN", "")
TADB_KEY       = os.getenv("THEAUDIODB_KEY", "2")  # "2" = free test key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("VibeFinderAI.Enrich")
logging.getLogger("httpx").setLevel(logging.WARNING)


# ─── GLOBAL RATE LIMITERS ────────────────────────────────────────────────────

class RateLimiter:
    """Guarantees strictly enforced delays between API calls across all concurrent workers."""
    def __init__(self, rate: float):
        self.rate = rate
        self.last_check = 0.0
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_check
            if elapsed < self.rate:
                await asyncio.sleep(self.rate - elapsed)
                self.last_check = time.monotonic()
            else:
                self.last_check = now

# Strict limits mapped to API docs
MB_LIMITER   = RateLimiter(1.1)   # 1 req/s + 0.1s safety buffer
LB_LIMITER   = RateLimiter(0.5)   # 2 req/s
TADB_LIMITER = RateLimiter(0.55)  # ~2 req/s


# ─── MUSICBRAINZ ─────────────────────────────────────────────────────────────

async def mb_search_artist(client: httpx.AsyncClient, name: str) -> Optional[dict]:
    await MB_LIMITER.acquire()
    try:
        r = await client.get(
            f"{MB_BASE}/artist",
            params={"query": f'artist:"{name}"', "limit": 3, "fmt": "json"},
            headers={"User-Agent": MB_USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        artists = r.json().get("artists", [])
        if not artists:
            return None
        for a in artists:
            if a.get("score", 0) >= 90:
                return a
        return None
    except Exception as e:
        log.warning(f"[MB] search failed for '{name}': {e}")
        return None

async def mb_get_artist_tags(client: httpx.AsyncClient, mbid: str) -> list[str]:
    await MB_LIMITER.acquire()
    try:
        r = await client.get(
            f"{MB_BASE}/artist/{mbid}",
            params={"inc": "tags+genres", "fmt": "json"},
            headers={"User-Agent": MB_USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        raw_tags = data.get("tags", []) + data.get("genres", [])
        sorted_tags = sorted(raw_tags, key=lambda t: t.get("count", 0), reverse=True)
        return [t["name"] for t in sorted_tags[:20]]
    except Exception as e:
        log.warning(f"[MB] tags failed for mbid {mbid}: {e}")
        return []


# ─── LISTENBRAINZ ────────────────────────────────────────────────────────────

async def lb_get_similar_artists(
    client: httpx.AsyncClient,
    mbid: str,
    limit: int = 8
) -> list[dict]:
    if not LB_TOKEN:
        return []
    
    await LB_LIMITER.acquire()
    try:
        r = await client.get(
            f"{LB_BASE}/lb-radio/artist/{mbid}/similar/",
            params={"count": limit},
            headers={"Authorization": f"Token {LB_TOKEN}"},
            timeout=15,
            follow_redirects=True
        )
        if r.status_code == 404:
            return []  
        r.raise_for_status()
        data = r.json()

        found_similars = []
        def _find(node):
            if isinstance(node, list):
                for item in node:
                    if isinstance(item, dict) and "artist_name" in item and "similarity" in item:
                        found_similars.append({
                            "mbid": item.get("artist_mbid") or item.get("mbid", ""),
                            "name": item.get("artist_name", ""),
                            "similarity": round(float(item.get("similarity", 0.0)), 3)
                        })
                    else:
                        _find(item)
            elif isinstance(node, dict):
                for k, v in node.items():
                    if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) and "artist_name" in v[0]:
                        found_similars.append({
                            "mbid": k,
                            "name": v[0].get("artist_name", ""),
                            "similarity": round(float(v[0].get("similarity", 0.0)), 3)
                        })
                    else:
                        _find(v)

        _find(data)

        unique_sims = {}
        for s in found_similars:
            if s["mbid"] not in unique_sims and s["name"]:
                unique_sims[s["mbid"]] = s

        results = list(unique_sims.values())
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
        
    except Exception as e:
        log.warning(f"[LB] similar artists failed for mbid {mbid}: {e}")
        return []


# ─── THEAUDIODB ──────────────────────────────────────────────────────────────

async def tadb_search_artist(
    client: httpx.AsyncClient,
    name: str
) -> Optional[dict]:
    await TADB_LIMITER.acquire()
    try:
        r = await client.get(
            f"{TADB_BASE}/{TADB_KEY}/search.php",
            params={"s": name},
            timeout=10,
        )
        r.raise_for_status()
        
        if not r.text.strip():
            return None
            
        artists = r.json().get("artists") or []
        return artists[0] if artists else None
    except Exception as e:
        log.warning(f"[TADB] search failed for '{name}': {e}")
        return None

async def tadb_get_top_tracks(
    client: httpx.AsyncClient,
    artist_name: str,
    tadb_id: Optional[int] = None
) -> list[dict]:
    await TADB_LIMITER.acquire()
    try:
        url = f"{TADB_BASE}/{TADB_KEY}/track-top10.php"
        params = {"s": artist_name}

        r = await client.get(url, params=params, timeout=10)
        r.raise_for_status()
        
        if not r.text.strip():
            return []
            
        tracks = r.json().get("track") or []
        return [
            {
                "title": t.get("strTrack", ""),
                "tadbTrackId": t.get("idTrack"),
                "duration": t.get("intDuration"),
                "album": t.get("strAlbum", ""),
            }
            for t in tracks[:10]
            if t.get("strTrack")
        ]
    except Exception as e:
        log.warning(f"[TADB] top tracks failed for '{artist_name}': {e}")
        return []


# ─── MAIN ENRICHMENT LOOP ────────────────────────────────────────────────────

async def enrich_artist(
    db: Prisma,
    client: httpx.AsyncClient,
    artist: object,
    phases: set[str],
    idx: int,
    total: int
) -> None:
    name = artist.name
    update_data = {}
    
    # ADDED: Perfect counter injected directly into the worker!
    log.info(f"[{idx}/{total}] ⚡ Enriching: {name}")

    # ── Phase 1: MusicBrainz ─────────────────────────────────────────────────
    if "mb" in phases:
        current_mbid = artist.mbid
        
        if not current_mbid:
            mb_artist = await mb_search_artist(client, name)
            if mb_artist:
                current_mbid = mb_artist["id"]
                update_data["mbid"] = current_mbid
                
        if current_mbid and artist.mbTags is None:
            tags = await mb_get_artist_tags(client, current_mbid)
            update_data["mbTags"] = ",".join(tags) if tags else ""
        elif not current_mbid and artist.mbTags is None:
            update_data["mbTags"] = ""

    # ── Phase 2: ListenBrainz ─────────────────────────────────────────────────
    if "lb" in phases and LB_TOKEN:
        mbid_for_lb = update_data.get("mbid") or artist.mbid
        
        if mbid_for_lb and (artist.lbSimilarArtists is None or "empty" in artist.lbSimilarArtists):
            similar = await lb_get_similar_artists(client, mbid_for_lb)
            update_data["lbSimilarArtists"] = json.dumps(similar) if similar else '[{"status": "empty"}]'
        elif not mbid_for_lb and artist.lbSimilarArtists is None:
            update_data["lbSimilarArtists"] = '[{"status": "empty"}]'

    # ── Phase 3: TheAudioDB ───────────────────────────────────────────────────
    if "tadb" in phases:
        current_tadb_id = artist.tadbId
        
        if not current_tadb_id:
            tadb_artist = await tadb_search_artist(client, name)
            if tadb_artist:
                current_tadb_id = int(tadb_artist.get("idArtist", 0)) or None
                if current_tadb_id:
                    update_data["tadbId"]    = current_tadb_id
                    update_data["tadbMood"]  = tadb_artist.get("strMood") or ""
                    update_data["tadbStyle"] = tadb_artist.get("strStyle") or ""

        if current_tadb_id and artist.tadbTop10 in (None, "[]"):
            top10 = await tadb_get_top_tracks(client, name, current_tadb_id)
            if top10:
                update_data["tadbTop10"] = json.dumps(top10)
            else:
                update_data["tadbTop10"] = '[{"status": "empty"}]'
                
        elif not current_tadb_id and artist.tadbTop10 in (None, "[]"):
            update_data["tadbTop10"] = '[{"status": "empty"}]'

    # ── Persist ───────────────────────────────────────────────────────────────
    if update_data:
        try:
            await db.artistdirectory.update(
                where={"name": name},
                data=update_data,
            )
            log.info(f"  ✅ Saved data for: {name}")
        except Exception as e:
            log.error(f"  ❌ DB update failed for '{name}': {e}")
    else:
        pass


async def main():
    parser = argparse.ArgumentParser(description="Enrich ArtistDirectory with MB/LB/TADB data")
    parser.add_argument("--limit",  type=int, default=None, help="Max artists to process")
    parser.add_argument("--artist", type=str, default=None, help="Enrich single artist by name")
    parser.add_argument("--phase",  type=str, default="mb,lb,tadb",
                        help="Comma-sep phases to run: mb,lb,tadb (default: all)")
    args = parser.parse_args()

    phases = set(p.strip() for p in args.phase.split(","))
    log.info(f"Enrichment phases: {phases}")

    if not LB_TOKEN and "lb" in phases:
        log.warning(
            "⚠️  LISTENBRAINZ_TOKEN not set — LB phase will be skipped.\n"
            "   Get your token at: https://listenbrainz.org/settings/"
        )

    db = Prisma()
    await db.connect()

    try:
        # Targeting empty or corrupted rows 
        target_query = {
            "OR": [
                {"tadbTop10": None},
                {"tadbTop10": "[]"}
            ]
        }
        
        if args.artist:
            artists = await db.artistdirectory.find_many(where={"name": args.artist})
        elif args.limit:
            artists = await db.artistdirectory.find_many(take=args.limit, where=target_query)
        else:
            artists = await db.artistdirectory.find_many(where=target_query)

        total_artists = len(artists)
        log.info(f"Processing {total_artists} missing/broken artists concurrently...")
        if total_artists == 0:
            log.info("All artists perfectly enriched! Nothing to do.")
            return
            
        t_start = time.time()
        
        # ── CONCURRENCY SETUP ──
        # 15 concurrent workers. This limits database connections but
        # maximizes the 1-second gaps required by MusicBrainz.
        sem = asyncio.Semaphore(15)
        completed = 0

        async def process_artist(artist, client, idx, total):
            async with sem:
                await enrich_artist(db, client, artist, phases, idx, total)

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Launch all workers, passing in their exact queue number (idx)
            tasks = [
                asyncio.create_task(process_artist(a, client, i, total_artists)) 
                for i, a in enumerate(artists, 1)
            ]

            # Track progress as they finish asynchronously
            for future in asyncio.as_completed(tasks):
                await future
                completed += 1

                if completed % 50 == 0:
                    elapsed = time.time() - t_start
                    remaining = (total_artists - completed) * (elapsed / completed)
                    log.info(
                        f"  📊 Global Progress: {completed}/{total_artists} "
                        f"({elapsed/60:.1f}m elapsed, "
                        f"~{remaining/60:.1f}m remaining)"
                    )

        total_time = time.time() - t_start
        log.info(f"\n✅ Enrichment complete — {total_artists} artists in {total_time/60:.1f} minutes")

    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())