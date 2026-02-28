"""
enrich_tracks.py
────────────────
VibeFinderAI — Offline Track Feature Cache Builder

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
from typing import Optional

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
RB_RATE_LIMIT     = 0.6   # conservative — adjust based on actual tier
AB_RATE_LIMIT     = 1.1   # AcousticBrainz: 10 req / 10s
MB_RATE_LIMIT     = 1.1   # MusicBrainz: 1 req/s

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("VibeFinderAI.EnrichTracks")


# ─── RECCOBEATS ──────────────────────────────────────────────────────────────

async def rb_get_features(
    client: httpx.AsyncClient,
    spotify_id: str
) -> Optional[dict]:
    """
    Fetch audio features from ReccoBeats for a Spotify track ID.
    Returns normalised feature dict or None.

    ReccoBeats mirrors Spotify's audio features endpoint structure,
    making it a near drop-in replacement.
    """
    try:
        headers = {}
        if RECCOBEATS_KEY:
            headers["Authorization"] = f"Bearer {RECCOBEATS_KEY}"

        # ReccoBeats track features endpoint
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

    AcousticBrainz stores two 'levels' of analysis:
      - low-level: BPM, loudness, spectral features
      - high-level: mood probabilities (happy, sad, aggressive etc.)
    We fetch high-level (more useful for vibe routing).

    Note: AcousticBrainz is FROZEN — no data for tracks added after ~2022.
    For recent tracks, fall back to ReccoBeats or estimated values.
    """
    try:
        r = await client.get(
            f"{ACOUSTICBRAINZ_BASE}/{mbid}/high-level",
            headers={"User-Agent": MB_USER_AGENT},
            timeout=10,
        )
        if r.status_code == 404:
            return None  # Track not in AB — normal for post-2022 tracks
        r.raise_for_status()
        data = r.json()

        hl = data.get("highlevel", {})

        def mood_prob(key: str) -> Optional[float]:
            """Extract probability for the 'true' class from an AB classifier."""
            block = hl.get(key, {})
            all_vals = block.get("all", {})
            # AB uses class names like "happy", "not_happy" — get positive class
            for k, v in all_vals.items():
                if "not_" not in k and "_not" not in k:
                    return _safe_float(v)
            return None

        # Also try to get BPM from low-level if we need to supplement ReccoBeats
        bpm = None
        try:
            r2 = await client.get(
                f"{ACOUSTICBRAINZ_BASE}/{mbid}/low-level",
                headers={"User-Agent": MB_USER_AGENT},
                timeout=10,
            )
            if r2.status_code == 200:
                ll = r2.json()
                bpm = _safe_float(
                    ll.get("rhythm", {}).get("bpm")
                )
        except Exception:
            pass

        return {
            "tempo":          bpm,
            "moodHappy":      mood_prob("mood_happy"),
            "moodSad":        mood_prob("mood_sad"),
            "moodRelaxed":    mood_prob("mood_relaxed"),
            "moodAggressive": mood_prob("mood_aggressive"),
            "moodParty":      mood_prob("mood_party"),
            "moodAcoustic":   mood_prob("mood_acoustic"),
            "moodElectronic": mood_prob("mood_electronic"),
            "featureSource":  "acousticbrainz",
        }
    except Exception as e:
        log.debug(f"[AB] mood features failed for mbid {mbid}: {e}")
        return None


async def mb_recording_to_mbid(
    client: httpx.AsyncClient,
    title: str,
    artist: str
) -> Optional[str]:
    """
    Look up a MusicBrainz Recording ID (MBID) by title + artist.
    Used to bridge Spotify tracks → AcousticBrainz when no MBID is stored.
    """
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
            return recordings[0]["id"]
        return None
    except Exception as e:
        log.debug(f"[MB] recording lookup failed for '{title}' by '{artist}': {e}")
        return None


# ─── CACHE WRITER ────────────────────────────────────────────────────────────

async def cache_track_features(
    db: Prisma,
    spotify_id: Optional[str],
    mbid: Optional[str],
    title: str,
    artist: str,
    features: dict,
) -> None:
    """Upsert a track's features into TrackFeatureCache."""
    if not spotify_id and not mbid:
        return

    data = {
        "title":  title,
        "artist": artist,
        **{k: v for k, v in features.items() if v is not None},
    }

    try:
        if spotify_id:
            await db.trackfeaturecache.upsert(
                where={"spotifyId": spotify_id},
                data={
                    "create": {"spotifyId": spotify_id, "mbid": mbid, **data},
                    "update": data,
                },
            )
        elif mbid:
            await db.trackfeaturecache.upsert(
                where={"mbid": mbid},
                data={
                    "create": {"mbid": mbid, **data},
                    "update": data,
                },
            )
    except Exception as e:
        log.error(f"Cache write failed for '{title}' by '{artist}': {e}")


# ─── ENRICHMENT SOURCES ──────────────────────────────────────────────────────

async def enrich_from_artist_songs(db: Prisma, client: httpx.AsyncClient) -> None:
    """
    Enrich tracks extracted from ArtistDirectory.songs fields.
    The songs field stores comma-sep track names — we search MB for MBIDs
    then try ReccoBeats + AcousticBrainz.
    This is the quickest way to pre-warm the cache with ~10k known tracks.
    """
    artists = await db.artistdirectory.find_many()
    log.info(f"Processing songs from {len(artists)} artists...")

    total_tracks = 0
    for i, artist in enumerate(artists, 1):
        if not artist.songs:
            continue

        songs = [s.strip() for s in artist.songs.split(",") if s.strip()]
        log.info(f"[{i}/{len(artists)}] {artist.name} — {len(songs)} songs")

        for song_title in songs:
            # Try ReccoBeats first (needs Spotify ID — skip if not resolvable)
            # For now, do MB lookup to get MBID for AcousticBrainz
            mbid = await mb_recording_to_mbid(client, song_title, artist.name)
            await asyncio.sleep(MB_RATE_LIMIT)

            features = {}

            if mbid:
                ab_features = await ab_get_mood_features(client, mbid)
                await asyncio.sleep(AB_RATE_LIMIT)
                if ab_features:
                    features.update({k: v for k, v in ab_features.items() if v is not None})

            if features:
                await cache_track_features(
                    db, spotify_id=None, mbid=mbid,
                    title=song_title, artist=artist.name,
                    features=features,
                )
                total_tracks += 1

    log.info(f"✅ Cached features for {total_tracks} tracks from artist songs")


async def enrich_from_spotify_ids(
    db: Prisma,
    client: httpx.AsyncClient,
    id_file: str,
) -> None:
    """
    Enrich a list of Spotify IDs from a file (one per line).
    Format: spotify_id[,title,artist]  (title+artist optional for AB lookup)
    """
    with open(id_file) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    log.info(f"Processing {len(lines)} Spotify IDs from {id_file}")

    for i, line in enumerate(lines, 1):
        parts = [p.strip() for p in line.split(",", 2)]
        spotify_id = parts[0]
        title  = parts[1] if len(parts) > 1 else ""
        artist = parts[2] if len(parts) > 2 else ""

        log.info(f"[{i}/{len(lines)}] {spotify_id}")

        # Check if already cached
        existing = await db.trackfeaturecache.find_unique(
            where={"spotifyId": spotify_id}
        )
        if existing and existing.energy is not None:
            log.debug(f"  Already cached — skipping")
            continue

        features = {}

        # Try ReccoBeats
        rb = await rb_get_features(client, spotify_id)
        await asyncio.sleep(RB_RATE_LIMIT)
        if rb:
            features.update({k: v for k, v in rb.items() if v is not None})
            log.info(f"  ✅ RB: tempo={rb.get('tempo')}, energy={rb.get('energy'):.2f}")

        # If we have title+artist, try AcousticBrainz for mood scores
        if title and artist:
            mbid = await mb_recording_to_mbid(client, title, artist)
            await asyncio.sleep(MB_RATE_LIMIT)

            if mbid:
                ab = await ab_get_mood_features(client, mbid)
                await asyncio.sleep(AB_RATE_LIMIT)
                if ab:
                    # Merge — prefer ReccoBeats for audio features, AB for mood
                    for k, v in ab.items():
                        if v is not None and k not in features:
                            features[k] = v
                    log.info(f"  ✅ AB: happy={ab.get('moodHappy')}, sad={ab.get('moodSad')}")

        if features:
            await cache_track_features(
                db, spotify_id=spotify_id, mbid=None,
                title=title, artist=artist, features=features,
            )


async def enrich_from_playlist_tracks(db: Prisma, client: httpx.AsyncClient) -> None:
    """
    Enrich all tracks saved in the Track table (user playlists).
    These already have spotifyId when available.
    """
    tracks = await db.track.find_many(where={"spotifyId": {"not": None}})
    log.info(f"Processing {len(tracks)} playlist tracks with Spotify IDs")

    for i, track in enumerate(tracks, 1):
        if not track.spotifyId:
            continue

        existing = await db.trackfeaturecache.find_unique(
            where={"spotifyId": track.spotifyId}
        )
        if existing:
            continue

        log.info(f"[{i}/{len(tracks)}] {track.title} — {track.artist}")

        features = {}

        rb = await rb_get_features(client, track.spotifyId)
        await asyncio.sleep(RB_RATE_LIMIT)
        if rb:
            features.update({k: v for k, v in rb.items() if v is not None})

        # Use stored MBID if present
        mbid = track.mbid
        if not mbid:
            mbid = await mb_recording_to_mbid(client, track.title, track.artist)
            await asyncio.sleep(MB_RATE_LIMIT)

        if mbid:
            ab = await ab_get_mood_features(client, mbid)
            await asyncio.sleep(AB_RATE_LIMIT)
            if ab:
                for k, v in ab.items():
                    if v is not None and k not in features:
                        features[k] = v

        if features:
            await cache_track_features(
                db, spotify_id=track.spotifyId, mbid=mbid,
                title=track.title, artist=track.artist, features=features,
            )


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
        async with httpx.AsyncClient() as client:
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
