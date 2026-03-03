"""
enrich_tracks.py
────────────────
VibeFinderAI — Offline Track Feature Cache Builder (CRAZY FAST EDITION 🚀)

PURPOSE
-------
Populates TrackFeatureCache with:
  - Audio features from ReccoBeats (tempo/BPM, energy, valence, danceability,
    acousticness, instrumentalness, loudness, speechiness)
  - Mood probability scores from AcousticBrainz (happy, sad, relaxed,
    aggressive, party, acoustic, electronic)

This is an OFFLINE job — it must NOT run in the hot path of a user query.
Run it once to seed the cache, then weekly as a cron job for new tracks.

WHY TWO SOURCES
---------------
ReccoBeats has current tracks but is rate-limited.
AcousticBrainz has deep coverage of pre-2022 tracks with richer mood scores,
but is a frozen dataset (no new data added since 2022). They complement each
other perfectly — try ReccoBeats first, fall back to AcousticBrainz for older
tracks via MBID.

APIs USED
---------
  ReccoBeats    — Free tier. No official published commercial ToS at time of
                  writing. Check https://reccobeats.com before monetising.
                  Set env: RECCOBEATS_KEY=your_key (if they require one)

  AcousticBrainz — Frozen CC0 dataset. Free, no key needed. Safe for all use.
                  Rate limit: 10 requests per 10 seconds.

USAGE
-----
  # Seed from ArtistDirectory top songs (quickest way to pre-warm cache)
  python enrich_tracks.py --source artist_songs

  # Feed it a file of Spotify IDs (one per line)
  python enrich_tracks.py --source spotify_ids --file my_ids.txt

  # Enrich tracks already in the Track table (saved playlists)
  python enrich_tracks.py --source playlist_tracks

  # Single track by Spotify ID
  python enrich_tracks.py --spotify-id 3n3Ppam7vgaVa1iaRUIOKE
"""

import asyncio
import argparse
import json
import logging
import os
import re
import time
from typing import Optional, Dict, Any

import httpx
from dotenv import load_dotenv
from prisma import Prisma

load_dotenv()

# ─── CONFIG ──────────────────────────────────────────────────────────────────

RECCOBEATS_BASE   = "https://api.reccobeats.com/v1"
ACOUSTICBRAINZ_BASE = "https://acousticbrainz.org"
MB_BASE           = "https://musicbrainz.org/ws/2"
MB_USER_AGENT     = "VibeFinderAI/8.0 (https://github.com/yourusername/vibefinder; your@email.com)"

RECCOBEATS_KEY    = os.getenv("RECCOBEATS_KEY", "")

# Turbo limits. Override in .env if you need to go faster/slower
RB_RATE_LIMIT     = float(os.getenv("RB_RATE_LIMIT", "0.1"))   # 10 req/s
AB_RATE_LIMIT     = float(os.getenv("AB_RATE_LIMIT", "0.3"))   # ~3.3 req/s
MB_RATE_LIMIT     = float(os.getenv("MB_RATE_LIMIT", "1.0"))   # 1 req/s (Strict - MetaBrainz will ban you if lower)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("VibeFinderAI.EnrichTracks")

# Silence httpx so it doesn't spam our console
logging.getLogger("httpx").setLevel(logging.WARNING)

# ─── RATE LIMITERS ───────────────────────────────────────────────────────────

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

RB_LIMITER = RateLimiter(RB_RATE_LIMIT)
AB_LIMITER = RateLimiter(AB_RATE_LIMIT)
MB_LIMITER = RateLimiter(MB_RATE_LIMIT)

# ─── IN-MEMORY CACHE ─────────────────────────────────────────────────────────

# Prevents 100 concurrent workers from hitting MusicBrainz for the exact same track simultaneously
MBID_MEMORY_CACHE: Dict[str, Any] = {}

async def memoized_mbid_and_isrc_lookup(
    client: httpx.AsyncClient, title: str, artist: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Smart cache: Returns (mbid, isrc) tuple or hitches a ride on already-running API request.
    """
    if not title or not artist:
        return (None, None)
        
    key = f"{title.lower().strip()}|{artist.lower().strip()}"
    
    if key in MBID_MEMORY_CACHE:
        val = MBID_MEMORY_CACHE[key]
        if isinstance(val, asyncio.Task):
            # Another worker is already fetching this! Wait for their answer.
            return await val
        return val

    # Create a task and store it so other workers can await it instead of spamming the API
    task = asyncio.create_task(mb_recording_to_mbid_and_isrc(client, title, artist))
    MBID_MEMORY_CACHE[key] = task
    
    result = await task
    MBID_MEMORY_CACHE[key] = result  # Replace task with actual tuple result
    return result


async def memoized_mbid_lookup(client: httpx.AsyncClient, title: str, artist: str) -> Optional[str]:
    """
    Legacy wrapper: Smart cache returning just MBID.
    Use memoized_mbid_and_isrc_lookup for ISRC as well.
    """
    mbid, _ = await memoized_mbid_and_isrc_lookup(client, title, artist)
    return mbid


# ─── RECCOBEATS ──────────────────────────────────────────────────────────────

async def rb_get_features(
    client: httpx.AsyncClient,
    spotify_id: str
) -> Optional[dict]:
    """
    Fetch audio features from ReccoBeats for a Spotify track ID.
    Returns normalised feature dict or None.
    """
    await RB_LIMITER.acquire()
    try:
        headers = {}
        if RECCOBEATS_KEY:
            headers["Authorization"] = f"Bearer {RECCOBEATS_KEY}"

        r = await client.get(
            f"{RECCOBEATS_BASE}/track/{spotify_id}/audio-features",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()

        return {
            "tempo":            _safe_float(data.get("tempo")),
            "energy":           _safe_float(data.get("energy")),
            "valence":          _safe_float(data.get("valence")),
            "danceability":     _safe_float(data.get("danceability")),
            "acousticness":     _safe_float(data.get("acousticness")),
            "instrumentalness": _safe_float(data.get("instrumentalness")),
            "loudness":         _safe_float(data.get("loudness")),
            "speechiness":      _safe_float(data.get("speechiness")),
            "featureSource":    "reccobeats",
        }
    except Exception as e:
        log.debug(f"[RB] features failed for {spotify_id}: {e}")
        return None


# ─── ACOUSTICBRAINZ ──────────────────────────────────────────────────────────

async def ab_get_mood_features(
    client: httpx.AsyncClient,
    mbid: str
) -> Optional[dict]:
    """
    Fetch mood + audio features from AcousticBrainz for a MusicBrainz Recording ID.
    Returns normalised feature dict or None.
    """
    try:
        await AB_LIMITER.acquire()
        r = await client.get(
            f"{ACOUSTICBRAINZ_BASE}/{mbid}/high-level",
            headers={"User-Agent": MB_USER_AGENT},
            timeout=10,
        )
        if r.status_code == 404:
            return None  
        r.raise_for_status()
        data = r.json()

        hl = data.get("highlevel", {})

        def class_prob(category: str, target_class: str) -> Optional[float]:
            """Extract probability for a specific class from an AB classifier."""
            try:
                val = hl.get(category, {}).get("all", {}).get(target_class)
                return _safe_float(val)
            except Exception:
                return None

        # 1. Extract explicit moods
        mood_happy      = class_prob("mood_happy", "happy")
        mood_sad        = class_prob("mood_sad", "sad")
        mood_relaxed    = class_prob("mood_relaxed", "relaxed")
        mood_aggressive = class_prob("mood_aggressive", "aggressive")
        mood_party      = class_prob("mood_party", "party")
        mood_acoustic   = class_prob("mood_acoustic", "acoustic")
        mood_electronic = class_prob("mood_electronic", "electronic")

        # 2. PROXY MAPPING: Fill in Spotify-equivalent features using AB's models!
        danceability     = class_prob("danceability", "danceable")
        instrumentalness = class_prob("voice_instrumental", "instrumental")
        
        # Acousticness is literally just mood_acoustic
        acousticness = mood_acoustic
        
        # Valence is musical positiveness, so mood_happy is a near-perfect proxy
        valence = mood_happy
        
        # Energy proxy: If it's NOT relaxed, it's energetic.
        # 1.0 - relaxed is a highly reliable proxy for energy in AcousticBrainz
        energy = None
        if mood_relaxed is not None:
            energy = round(1.0 - mood_relaxed, 4)

        bpm = None
        try:
            await AB_LIMITER.acquire()
            r2 = await client.get(
                f"{ACOUSTICBRAINZ_BASE}/{mbid}/low-level",
                headers={"User-Agent": MB_USER_AGENT},
                timeout=10,
            )
            if r2.status_code == 200:
                ll = r2.json()
                bpm = _safe_float(ll.get("rhythm", {}).get("bpm"))
        except Exception:
            pass

        return {
            "tempo":            bpm,
            "energy":           energy,            # 🔥 Mapped!
            "valence":          valence,           # 🔥 Mapped!
            "danceability":     danceability,      # 🔥 Mapped!
            "acousticness":     acousticness,      # 🔥 Mapped!
            "instrumentalness": instrumentalness,  # 🔥 Mapped!
            # We omit loudness/speechiness as AB doesn't map these easily without deep spectral parsing.
            "moodHappy":        mood_happy,
            "moodSad":          mood_sad,
            "moodRelaxed":      mood_relaxed,
            "moodAggressive":   mood_aggressive,
            "moodParty":        mood_party,
            "moodAcoustic":     mood_acoustic,
            "moodElectronic":   mood_electronic,
            "featureSource":    "acousticbrainz",
        }
    except Exception as e:
        log.debug(f"[AB] mood features failed for mbid {mbid}: {e}")
        return None


async def mb_recording_to_mbid_and_isrc(
    client: httpx.AsyncClient,
    title: str,
    artist: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Look up a MusicBrainz Recording and extract MBID + ISRC code.
    Returns (mbid, isrc) tuple. Either can be None if not found.
    """
    await MB_LIMITER.acquire()
    try:
        query = f'recording:"{title}" AND artist:"{artist}"'
        r = await client.get(
            f"{MB_BASE}/recording",
            params={"query": query, "limit": 1, "fmt": "json"},
            headers={"User-Agent": MB_USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        recordings = r.json().get("recordings", [])
        if recordings and recordings[0].get("score", 0) >= 85:
            mbid = recordings[0].get("id")
            # ISRC codes are in isrc-list array, take the first one
            isrc = None
            isrc_list = recordings[0].get("isrc-list", [])
            if isrc_list:
                isrc = isrc_list[0]
            return (mbid, isrc)
        return (None, None)
    except Exception as e:
        log.debug(f"[MB] recording lookup failed for '{title}' by '{artist}': {e}")
        return (None, None)


async def mb_recording_to_mbid(
    client: httpx.AsyncClient,
    title: str,
    artist: str
) -> Optional[str]:
    """
    Legacy wrapper: Look up a MusicBrainz Recording ID (MBID) by title + artist.
    Use mb_recording_to_mbid_and_isrc for ISRC as well.
    """
    mbid, _ = await mb_recording_to_mbid_and_isrc(client, title, artist)
    return mbid


# ─── CACHE WRITER ────────────────────────────────────────────────────────────

async def cache_track_features(
    db: Prisma,
    spotify_id: Optional[str],
    mbid: Optional[str],
    isrc: Optional[str],
    title: str,
    artist: str,
    features: dict,
) -> None:
    """Upsert a track's features into TrackFeatureCache with ISRC support."""
    if not spotify_id and not mbid:
        return

    data = {
        "title":  title,
        "artist": artist,
        **{k: v for k, v in features.items() if v is not None},
    }
    if isrc:
        data["isrc"] = isrc

    try:
        if spotify_id:
            await db.trackfeaturecache.upsert(
                where={"spotifyId": spotify_id},
                data={
                    "create": {"spotifyId": spotify_id, "mbid": mbid, "isrc": isrc, **data},
                    "update": data,
                },
            )
        elif mbid:
            await db.trackfeaturecache.upsert(
                where={"mbid": mbid},
                data={
                    "create": {"mbid": mbid, "isrc": isrc, **data},
                    "update": data,
                },
            )
    except Exception as e:
        log.error(f"Cache write failed for '{title}' by '{artist}': {e}")


# ─── ENRICHMENT SOURCES (CONCURRENT EDITION) ─────────────────────────────────

async def enrich_from_artist_songs(db: Prisma, client: httpx.AsyncClient) -> None:
    """
    Enrich tracks extracted from ArtistDirectory.songs fields AND the tadbTop10 data.
    """
    artists = await db.artistdirectory.find_many()
    
    log.info(f"Loaded {len(artists)} artists. Fetching existing cache keys...")
    existing_records = await db.trackfeaturecache.find_many()
    existing_set = {f"{r.title.lower()}|{r.artist.lower()}" for r in existing_records if r.title and r.artist}
    log.info(f"Loaded {len(existing_set)} existing tracks from DB cache.")

    tasks = []
    for artist in artists:
        songs = []
        
        # 1. Grab hardcoded songs if they exist
        if artist.songs:
            songs.extend([s.strip() for s in artist.songs.split(",") if s.strip()])
            
        # 2. Grab the Top 10 tracks scraped by TheAudioDB (this is where the real volume is!)
        if hasattr(artist, 'tadbTop10') and artist.tadbTop10 and artist.tadbTop10 not in ("[]", '[{"status": "empty"}]'):
            try:
                top_tracks = json.loads(artist.tadbTop10)
                for t in top_tracks:
                    if isinstance(t, dict) and t.get("title"):
                        songs.append(t["title"].strip())
            except Exception as e:
                log.debug(f"Failed to parse tadbTop10 for {artist.name}: {e}")

        # Deduplicate tracks so we don't process the same one twice for an artist
        unique_songs = list(set(songs))
        
        for song in unique_songs:
            if not song: 
                continue
            if f"{song.lower()}|{artist.name.lower()}" not in existing_set:
                tasks.append((song, artist.name))

    total_songs = len(tasks)
    if total_songs == 0:
        log.info("All artist songs are already cached! We're good bro. 🚀")
        return

    log.info(f"Processing {total_songs} uncached songs concurrently (SUPER FAST)...")

    sem = asyncio.Semaphore(100) # 🔥 Cranked up to 100
    completed = 0
    total_cached = 0
    t_start = time.time()

    async def process_song(song_title, artist_name):
        nonlocal completed, total_cached
        async with sem:
            try:
                mbid, isrc = await memoized_mbid_and_isrc_lookup(client, song_title, artist_name)
                features = {}
                
                if mbid:
                    ab_features = await ab_get_mood_features(client, mbid)
                    if ab_features:
                        features.update({k: v for k, v in ab_features.items() if v is not None})

                if features:
                    await cache_track_features(
                        db, spotify_id=None, mbid=mbid, isrc=isrc,
                        title=song_title, artist=artist_name,
                        features=features,
                    )
                    total_cached += 1
            except Exception as e:
                log.error(f"Failed processing '{song_title}' by '{artist_name}': {e}")
            finally:
                completed += 1
                if completed % 50 == 0:
                    elapsed = time.time() - t_start
                    remaining = (total_songs - completed) * (elapsed / completed)
                    log.info(
                        f"  📊 Progress: {completed}/{total_songs} "
                        f"({elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m left)"
                    )

    # Fire off concurrently in chunks so we don't overwhelm the loop
    chunk_size = 5000
    for i in range(0, len(tasks), chunk_size):
        chunk = tasks[i:i+chunk_size]
        await asyncio.gather(*[process_song(t, a) for t, a in chunk])

    log.info(f"✅ Cached features for {total_cached} new tracks from artist songs")


async def enrich_from_spotify_ids(
    db: Prisma,
    client: httpx.AsyncClient,
    id_file: str,
) -> None:
    """
    Enrich a list of Spotify IDs from a file.
    """
    with open(id_file) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    log.info(f"Loaded {len(lines)} IDs. Fetching existing cache keys...")
    existing_records = await db.trackfeaturecache.find_many(where={"spotifyId": {"not": None}})
    existing_set = {r.spotifyId for r in existing_records if r.spotifyId}

    tasks = []
    for line in lines:
        parts = [p.strip() for p in line.split(",", 2)]
        if parts[0] not in existing_set:
            tasks.append(parts)

    total_tasks = len(tasks)
    if total_tasks == 0:
        log.info("All Spotify IDs are already cached! 🚀")
        return

    log.info(f"Processing {total_tasks} uncached Spotify IDs concurrently (SUPER FAST)...")

    sem = asyncio.Semaphore(100) # 🔥 Cranked up to 100
    completed = 0
    t_start = time.time()

    async def process_line(parts):
        nonlocal completed
        async with sem:
            try:
                spotify_id = parts[0]
                title  = parts[1] if len(parts) > 1 else ""
                artist = parts[2] if len(parts) > 2 else ""

                features = {}

                # 🔥 Blast both APIs concurrently
                rb_task = asyncio.create_task(rb_get_features(client, spotify_id))
                mb_task = None
                if title and artist:
                    mb_task = asyncio.create_task(memoized_mbid_and_isrc_lookup(client, title, artist))

                # Wait for RB to finish
                rb = await rb_task
                if rb:
                    features.update({k: v for k, v in rb.items() if v is not None})

                # Wait for MB to finish (if we ran it)
                mbid = None
                isrc = None
                if mb_task:
                    mbid, isrc = await mb_task
                    if mbid:
                        ab = await ab_get_mood_features(client, mbid)
                        if ab:
                            for k, v in ab.items():
                                if v is not None and k not in features:
                                    features[k] = v

                if features:
                    await cache_track_features(
                        db, spotify_id=spotify_id, mbid=mbid, isrc=isrc,
                        title=title, artist=artist, features=features,
                    )
            except Exception as e:
                log.error(f"Failed processing Spotify ID '{parts[0]}': {e}")
            finally:
                completed += 1
                if completed % 50 == 0:
                    elapsed = time.time() - t_start
                    remaining = (total_tasks - completed) * (elapsed / completed)
                    log.info(f"  📊 Progress: {completed}/{total_tasks} ({elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m left)")

    chunk_size = 5000
    for i in range(0, len(tasks), chunk_size):
        chunk = tasks[i:i+chunk_size]
        await asyncio.gather(*[process_line(p) for p in chunk])
        
    log.info("✅ Finished processing Spotify IDs.")


async def enrich_from_playlist_tracks(db: Prisma, client: httpx.AsyncClient) -> None:
    """
    Enrich all tracks saved in the Track table (user playlists).
    """
    log.info("Fetching existing cache keys...")
    existing_records = await db.trackfeaturecache.find_many(where={"spotifyId": {"not": None}})
    existing_set = {r.spotifyId for r in existing_records if r.spotifyId}

    tracks = await db.track.find_many(where={"spotifyId": {"not": None}})
    uncached_tracks = [t for t in tracks if t.spotifyId not in existing_set]
    total_tracks = len(uncached_tracks)
    
    if total_tracks == 0:
        log.info("All playlist tracks are already cached! 🚀")
        return

    log.info(f"Processing {total_tracks} uncached playlist tracks concurrently (SUPER FAST)...")

    sem = asyncio.Semaphore(100) # 🔥 Cranked up to 100
    completed = 0
    t_start = time.time()

    async def process_track(track):
        nonlocal completed
        async with sem:
            try:
                features = {}
                
                # 🔥 Blast ReccoBeats and MusicBrainz at the exact same time
                rb_task = asyncio.create_task(rb_get_features(client, track.spotifyId))
                
                mbid = track.mbid
                isrc = track.isrc if hasattr(track, 'isrc') else None
                mb_task = None
                if not mbid:
                    mb_task = asyncio.create_task(memoized_mbid_and_isrc_lookup(client, track.title, track.artist))
                
                # Await ReccoBeats
                rb = await rb_task
                if rb:
                    features.update({k: v for k, v in rb.items() if v is not None})
                
                # Await MusicBrainz if we needed it
                if mb_task:
                    mbid, isrc = await mb_task
                
                if mbid:
                    ab = await ab_get_mood_features(client, mbid)
                    if ab:
                        for k, v in ab.items():
                            if v is not None and k not in features:
                                features[k] = v
                                
                if features:
                    await cache_track_features(
                        db, spotify_id=track.spotifyId, mbid=mbid, isrc=isrc,
                        title=track.title, artist=track.artist, features=features,
                    )
            except Exception as e:
                log.error(f"Failed processing track '{track.title}': {e}")
            finally:
                completed += 1
                if completed % 50 == 0:
                    elapsed = time.time() - t_start
                    remaining = (total_tracks - completed) * (elapsed / completed)
                    log.info(f"  📊 Progress: {completed}/{total_tracks} ({elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m left)")

    chunk_size = 5000
    for i in range(0, len(uncached_tracks), chunk_size):
        chunk = uncached_tracks[i:i+chunk_size]
        await asyncio.gather(*[process_track(t) for t in chunk])
        
    log.info("✅ Finished processing playlist tracks.")


# ─── UTILITY ─────────────────────────────────────────────────────────────────

def _safe_float(val) -> Optional[float]:
    """Safely convert to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ─── MAIN ────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Build TrackFeatureCache from ReccoBeats + AcousticBrainz")
    parser.add_argument(
        "--source",
        choices=["artist_songs", "spotify_ids", "playlist_tracks"],
        default="artist_songs",
        help="Where to get tracks from (default: artist_songs)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to file of Spotify IDs (required for --source spotify_ids)",
    )
    parser.add_argument(
        "--spotify-id",
        type=str,
        default=None,
        help="Enrich a single Spotify ID directly",
    )
    args = parser.parse_args()

    db = Prisma()
    await db.connect()

    try:
        # 🔥 Pumped up connection limits so we don't hit max sockets
        limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
        async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
            if args.spotify_id:
                log.info(f"Single track enrichment: {args.spotify_id}")
                features = {}
                rb = await rb_get_features(client, args.spotify_id)
                if rb:
                    features.update(rb)
                    log.info(f"ReccoBeats: {features}")
                else:
                    log.info("ReccoBeats: no result")

            elif args.source == "artist_songs":
                await enrich_from_artist_songs(db, client)

            elif args.source == "spotify_ids":
                if not args.file:
                    parser.error("--file required for --source spotify_ids")
                await enrich_from_spotify_ids(db, client, args.file)

            elif args.source == "playlist_tracks":
                await enrich_from_playlist_tracks(db, client)

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())