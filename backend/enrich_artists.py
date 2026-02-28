"""
enrich_artists.py
─────────────────
VibeFinderAI — Offline Artist Enrichment Script

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
  python enrich_artists.py                  # enrich all artists
  python enrich_artists.py --limit 50       # enrich first 50 (test run)
  python enrich_artists.py --artist "Adele" # enrich single artist
  python enrich_artists.py --phase mb       # MusicBrainz only
  python enrich_artists.py --phase lb       # ListenBrainz only
  python enrich_artists.py --phase tadb     # TheAudioDB only

TIMING
------
  ~1100 artists × 3 APIs × rate limiting ≈ 60-90 minutes total.
  Run overnight or in a tmux session.
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

MB_RATE_LIMIT  = 1.1   # seconds between MB requests (1/s limit, slight buffer)
LB_RATE_LIMIT  = 0.5   # ListenBrainz is more generous
TADB_RATE_LIMIT = 0.55 # 2/s limit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("VibeFinderAI.Enrich")


# ─── MUSICBRAINZ ─────────────────────────────────────────────────────────────

async def mb_search_artist(client: httpx.AsyncClient, name: str) -> Optional[dict]:
    """
    Search MusicBrainz for an artist by name.
    Returns the best match dict (with 'id' = MBID) or None.
    Only trusts results with score >= 90.
    """
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
        # Find best match with high confidence
        for a in artists:
            if a.get("score", 0) >= 90:
                return a
        return None
    except Exception as e:
        log.warning(f"[MB] search failed for '{name}': {e}")
        return None


async def mb_get_artist_tags(client: httpx.AsyncClient, mbid: str) -> list[str]:
    """
    Fetch community tags for an artist by MBID.
    Returns list of tag strings sorted by vote count.
    """
    try:
        r = await client.get(
            f"{MB_BASE}/artist/{mbid}",
            params={"inc": "tags+genres", "fmt": "json"},
            headers={"User-Agent": MB_USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        # Merge tags and genres, sort by count
        raw_tags = data.get("tags", []) + data.get("genres", [])
        sorted_tags = sorted(raw_tags, key=lambda t: t.get("count", 0), reverse=True)
        return [t["name"] for t in sorted_tags[:20]]  # top 20 tags
    except Exception as e:
        log.warning(f"[MB] tags failed for mbid {mbid}: {e}")
        return []


# ─── LISTENBRAINZ ────────────────────────────────────────────────────────────

async def lb_get_similar_artists(
    client: httpx.AsyncClient,
    mbid: str,
    limit: int = 8
) -> list[dict]:
    """
    Fetch similar artists via ListenBrainz radio endpoint.
    Returns list of {name, mbid, similarity} dicts.
    Requires a valid LB user token.

    Endpoint: GET /1/lb-radio/artist/{mbid}/similar
    This is collaborative filtering on real listening data — much better
    than editorial similarity for niche/regional artists.
    """
    if not LB_TOKEN:
        log.warning("[LB] No LISTENBRAINZ_TOKEN set — skipping similar artists")
        return []
    try:
        r = await client.get(
            f"{LB_BASE}/lb-radio/artist/{mbid}/similar",
            params={"count": limit},
            headers={"Authorization": f"Token {LB_TOKEN}"},
            timeout=15,
        )
        if r.status_code == 404:
            return []  # artist not in LB — not an error
        r.raise_for_status()
        data = r.json()

        results = []
        for artist_mbid, tracks in data.items():
            if not tracks:
                continue
            # LB radio returns {mbid: [{recording_mbid, artist_name, ...}]}
            artist_name = tracks[0].get("artist_name", "") if tracks else ""
            similarity = tracks[0].get("similarity", 0.0) if tracks else 0.0
            results.append({
                "mbid": artist_mbid,
                "name": artist_name,
                "similarity": round(similarity, 3),
            })

        # Sort by similarity descending
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
    """
    Search TheAudioDB for an artist by name.
    Returns first result dict or None.
    Free key "2" limited to 1 search result per query.
    """
    try:
        r = await client.get(
            f"{TADB_BASE}/{TADB_KEY}/search.php",
            params={"s": name},
            timeout=10,
        )
        r.raise_for_status()
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
    """
    Fetch top 10 tracks for an artist from TheAudioDB.
    Uses artist name (free tier endpoint).
    Returns list of {title, tadbTrackId, duration}.
    """
    try:
        # Prefer ID lookup if we have it, else name search
        if tadb_id:
            url = f"{TADB_BASE}/{TADB_KEY}/track-top10.php"
            params = {"m": tadb_id}
        else:
            url = f"{TADB_BASE}/{TADB_KEY}/track-top10.php"
            params = {"s": artist_name}

        r = await client.get(url, params=params, timeout=10)
        r.raise_for_status()
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
) -> None:
    """
    Enrich a single ArtistDirectory entry with data from MB, LB, TADB.
    Skips phases that are already populated (idempotent).
    """
    name = artist.name
    update_data = {}

    # ── Phase 1: MusicBrainz ─────────────────────────────────────────────────
    if "mb" in phases:
        current_mbid = artist.mbid
        if not current_mbid:
            log.info(f"[MB] Searching: {name}")
            mb_artist = await mb_search_artist(client, name)
            await asyncio.sleep(MB_RATE_LIMIT)

            if mb_artist:
                current_mbid = mb_artist["id"]
                update_data["mbid"] = current_mbid
                log.info(f"  ✅ MBID: {current_mbid}")
            else:
                log.info(f"  ⚠️  No confident MB match for '{name}'")

        # Fetch tags if we now have a MBID and don't have tags yet
        if current_mbid and not artist.mbTags:
            tags = await mb_get_artist_tags(client, current_mbid)
            await asyncio.sleep(MB_RATE_LIMIT)
            if tags:
                update_data["mbTags"] = ",".join(tags)
                log.info(f"  🏷️  MB tags: {', '.join(tags[:5])}...")

    # ── Phase 2: ListenBrainz ─────────────────────────────────────────────────
    if "lb" in phases and LB_TOKEN:
        mbid_for_lb = update_data.get("mbid") or artist.mbid
        if mbid_for_lb and not artist.lbSimilarArtists:
            log.info(f"[LB] Similar artists for: {name}")
            similar = await lb_get_similar_artists(client, mbid_for_lb)
            await asyncio.sleep(LB_RATE_LIMIT)
            if similar:
                update_data["lbSimilarArtists"] = json.dumps(similar)
                names = [s["name"] for s in similar[:3]]
                log.info(f"  🎵 Similar: {', '.join(names)}...")

    # ── Phase 3: TheAudioDB ───────────────────────────────────────────────────
    if "tadb" in phases:
        if not artist.tadbId:
            log.info(f"[TADB] Searching: {name}")
            tadb_artist = await tadb_search_artist(client, name)
            await asyncio.sleep(TADB_RATE_LIMIT)

            if tadb_artist:
                tadb_id = int(tadb_artist.get("idArtist", 0)) or None
                if tadb_id:
                    update_data["tadbId"]    = tadb_id
                    update_data["tadbMood"]  = tadb_artist.get("strMood") or None
                    update_data["tadbStyle"] = tadb_artist.get("strStyle") or None
                    log.info(f"  ✅ TADB ID: {tadb_id}, Mood: {tadb_artist.get('strMood')}")

                    # Top 10 tracks
                    top10 = await tadb_get_top_tracks(client, name, tadb_id)
                    await asyncio.sleep(TADB_RATE_LIMIT)
                    if top10:
                        update_data["tadbTop10"] = json.dumps(top10)
                        log.info(f"  🎵 Top tracks: {', '.join(t['title'] for t in top10[:3])}...")

    # ── Persist ───────────────────────────────────────────────────────────────
    if update_data:
        try:
            await db.artistdirectory.update(
                where={"name": name},
                data=update_data,
            )
        except Exception as e:
            log.error(f"DB update failed for '{name}': {e}")
    else:
        log.debug(f"[skip] '{name}' — all phases already populated or no data found")


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
        if args.artist:
            artists = await db.artistdirectory.find_many(where={"name": args.artist})
        elif args.limit:
            artists = await db.artistdirectory.find_many(take=args.limit)
        else:
            artists = await db.artistdirectory.find_many()

        log.info(f"Processing {len(artists)} artists...")
        t_start = time.time()

        async with httpx.AsyncClient() as client:
            for i, artist in enumerate(artists, 1):
                log.info(f"[{i}/{len(artists)}] {artist.name}")
                await enrich_artist(db, client, artist, phases)

                # Progress checkpoint every 50 artists
                if i % 50 == 0:
                    elapsed = time.time() - t_start
                    remaining = (len(artists) - i) * (elapsed / i)
                    log.info(
                        f"  📊 Progress: {i}/{len(artists)} "
                        f"({elapsed/60:.1f}m elapsed, "
                        f"~{remaining/60:.1f}m remaining)"
                    )

        total = time.time() - t_start
        log.info(f"\n✅ Enrichment complete — {len(artists)} artists in {total/60:.1f} minutes")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
