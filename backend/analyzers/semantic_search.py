"""
semantic_search.py
──────────────────
VibeFinderAI — Semantic Fallback Engine + Audio Feature Scorer

WHAT'S NEW (v3)
---------------
  blend_audio_features() now accepts an optional feature_index parameter.
  When main.py passes TRACK_FEATURE_INDEX (loaded at startup), no DB call
  is made — O(1) lookup instead of a round-trip to trackfeaturecache.
  Falls back to DB query when feature_index is None (backwards compatible).

ORIGINAL PURPOSE (unchanged)
-----------------------------
When the NLP heuristic engine fires the fallback path (confidence < 0.25),
rank a candidate track pool by cosine similarity between the user's prompt
and pre-computed track embeddings from {title} + {artist} text.

Model: sentence-transformers/all-MiniLM-L6-v2 (80MB, CPU-friendly, no GPU)
NOT training — frozen inference only. Cold start ~2s, queries <50ms.

GRACEFUL DEGRADATION
--------------------
All functions return the input unchanged if the model or DB is unavailable.
"""

import json
import logging
import time
from typing import Optional

logger = logging.getLogger("VibeFinderEngine.Semantic")

# ── Model state ───────────────────────────────────────────────────────────────
_model = None
_model_load_error: Optional[str] = None
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _load_model():
    global _model, _model_load_error
    if _model is not None:
        return _model
    if _model_load_error is not None:
        return None
    try:
        logger.info(f"[Semantic] Loading model: {_MODEL_NAME} ...")
        t0 = time.time()
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info(f"[Semantic] Model loaded in {time.time()-t0:.2f}s — ready.")
        return _model
    except ImportError:
        _model_load_error = "sentence-transformers not installed. Run: pip install sentence-transformers"
        logger.warning(f"[Semantic] {_model_load_error}")
        return None
    except Exception as e:
        _model_load_error = str(e)
        logger.error(f"[Semantic] Model load failed: {e}")
        return None


def semantic_ready() -> bool:
    return _load_model() is not None


def build_track_text(track: dict) -> str:
    title  = track.get("title",  "").strip()
    artist = track.get("artist", "").strip()
    if not title and not artist:
        return ""
    if not artist:
        return title
    if not title:
        return f"music by {artist}"
    return f"{title} by {artist}"


def rank_tracks_by_prompt(
    prompt: str,
    tracks: list[dict],
    top_n: Optional[int] = None,
) -> list[dict]:
    """
    Rank a list of track dicts by semantic similarity to the user's prompt.
    Adds 'semantic_score' key (float 0–1) to each dict.
    Returns input unchanged on model failure.
    """
    if not tracks:
        return tracks

    model = _load_model()
    if model is None:
        logger.warning("[Semantic] Model unavailable — returning tracks unranked.")
        return tracks

    try:
        import numpy as np
        t0 = time.time()

        track_texts   = [build_track_text(t) for t in tracks]
        valid_indices = [i for i, text in enumerate(track_texts) if text.strip()]
        valid_texts   = [track_texts[i] for i in valid_indices]
        if not valid_texts:
            return tracks

        all_texts  = [prompt] + valid_texts
        embeddings = model.encode(all_texts, convert_to_numpy=True, show_progress_bar=False)

        prompt_emb  = embeddings[0]
        track_embs  = embeddings[1:]
        prompt_norm = prompt_emb / (np.linalg.norm(prompt_emb) + 1e-10)
        track_norms = track_embs / (np.linalg.norm(track_embs, axis=1, keepdims=True) + 1e-10)
        similarities = track_norms @ prompt_norm

        result    = [t.copy() for t in tracks]
        score_map = {track_idx: float(similarities[idx]) for idx, track_idx in enumerate(valid_indices)}
        for i, track in enumerate(result):
            track["semantic_score"] = score_map.get(i, 0.0)

        result.sort(key=lambda t: t.get("semantic_score", 0.0), reverse=True)

        logger.info(
            f"[Semantic] Ranked {len(valid_texts)} tracks in {(time.time()-t0)*1000:.1f}ms. "
            f"Top: '{result[0].get('title')} — {result[0].get('artist')}' "
            f"(score={result[0].get('semantic_score', 0):.3f})"
        )

        return result[:top_n] if top_n else result

    except Exception as e:
        logger.error(f"[Semantic] Ranking failed: {e}", exc_info=True)
        return tracks


def blend_semantic_scores(
    tracks: list[dict],
    semantic_weight: float = 0.35,
    heuristic_key: str = "score",
) -> list[dict]:
    """
    Blend semantic_score with the heuristic 'score' from filter_and_score_tracks().
    final = (1 - w) * heuristic_norm + w * semantic_score
    """
    if not tracks:
        return tracks

    has_semantic = any("semantic_score" in t for t in tracks)
    if not has_semantic:
        return tracks

    h_scores = [t.get(heuristic_key, 0.0) for t in tracks]
    h_max = max(h_scores) if h_scores else 1.0
    h_min = min(h_scores) if h_scores else 0.0
    h_range = (h_max - h_min) or 1.0

    result = []
    for t in tracks:
        t = t.copy()
        h_norm = (t.get(heuristic_key, 0.0) - h_min) / h_range
        s_norm = t.get("semantic_score", 0.5)
        t["blended_score"] = (1.0 - semantic_weight) * h_norm + semantic_weight * s_norm
        result.append(t)

    result.sort(key=lambda t: t.get("blended_score", 0.0), reverse=True)
    return result


# ─── AUDIO FEATURE BLENDING ───────────────────────────────────────────────────

_VIBE_FEATURE_AFFINITY: dict[str, list[tuple[str, str, float]]] = {
    "hype":        [("energy", "high", 0.9), ("danceability", "high", 0.6), ("tempo", "high", 0.7)],
    "party":       [("danceability", "high", 0.9), ("energy", "high", 0.7), ("valence", "high", 0.5)],
    "chill":       [("energy", "low", 0.8), ("tempo", "low", 0.6), ("acousticness", "high", 0.4)],
    "calm":        [("energy", "low", 0.9), ("instrumentalness", "high", 0.5), ("tempo", "low", 0.7)],
    "ambient":     [("instrumentalness", "high", 0.9), ("energy", "low", 0.8), ("acousticness", "high", 0.5)],
    "focus":       [("instrumentalness", "high", 0.8), ("speechiness", "low", 0.7), ("energy", "low", 0.5)],
    "heartbreak":  [("valence", "low", 0.9), ("energy", "low", 0.5), ("acousticness", "high", 0.4)],
    "happy":       [("valence", "high", 0.9), ("energy", "high", 0.6), ("danceability", "high", 0.5)],
    "euphoric":    [("valence", "high", 0.8), ("energy", "high", 0.8), ("danceability", "high", 0.6)],
    "dark":        [("valence", "low", 0.8), ("instrumentalness", "high", 0.5), ("energy", "high", 0.4)],
    "intense":     [("energy", "high", 0.9), ("loudness", "high", 0.6), ("danceability", "low", 0.3)],
    "dreamy":      [("instrumentalness", "high", 0.6), ("energy", "low", 0.7), ("acousticness", "high", 0.5)],
    "cinematic":   [("instrumentalness", "high", 0.8), ("energy", "high", 0.5), ("valence", "low", 0.3)],
    "romantic":    [("valence", "high", 0.6), ("acousticness", "high", 0.5), ("energy", "low", 0.5)],
    "retro":       [("acousticness", "high", 0.5), ("danceability", "high", 0.5), ("energy", "high", 0.4)],
    "soulful":     [("acousticness", "high", 0.6), ("valence", "high", 0.5), ("speechiness", "low", 0.4)],
    "indie_folk":  [("acousticness", "high", 0.9), ("instrumentalness", "high", 0.4), ("energy", "low", 0.5)],
    "industrial":  [("energy", "high", 0.9), ("valence", "low", 0.7), ("loudness", "high", 0.6)],
    "hyperpop":    [("energy", "high", 0.8), ("danceability", "high", 0.7), ("tempo", "high", 0.6)],
    "tropical":    [("valence", "high", 0.7), ("danceability", "high", 0.8), ("energy", "high", 0.5)],
    "country":     [("acousticness", "high", 0.8), ("valence", "high", 0.5), ("instrumentalness", "low", 0.4)],
}

_AB_MOOD_TO_VIBE: dict[str, list[str]] = {
    "moodHappy":      ["happy", "euphoric", "party", "tropical"],
    "moodSad":        ["heartbreak", "dark", "dreamy"],
    "moodRelaxed":    ["chill", "calm", "ambient", "focus"],
    "moodAggressive": ["intense", "hype", "industrial", "dark"],
    "moodParty":      ["party", "hype", "euphoric"],
    "moodAcoustic":   ["indie_folk", "country", "calm", "romantic"],
    "moodElectronic": ["hyperpop", "industrial", "retro", "ambient"],
}


def score_track_with_features(
    track: dict,
    cached_features: Optional[dict],
    dominant_vibe: str,
    bpm_knob: int = 50,
) -> float:
    """
    Compute an audio-feature-based relevance score for a track.
    Returns a float [0.0, 1.0] — higher is better match for the vibe.
    """
    if not cached_features:
        return 0.5

    score_components = []
    weights_total = 0.0

    vibe_affinities = _VIBE_FEATURE_AFFINITY.get(dominant_vibe, [])

    for feature_key, direction, weight in vibe_affinities:
        raw_val = cached_features.get(feature_key)
        if raw_val is None:
            continue

        if feature_key == "tempo":
            val = max(0.0, min(1.0, (raw_val - 40) / 160))
        elif feature_key == "loudness":
            val = max(0.0, min(1.0, (raw_val + 60) / 60))
        else:
            val = max(0.0, min(1.0, float(raw_val)))

        component_score = val if direction == "high" else (1.0 - val)
        score_components.append(component_score * weight)
        weights_total += weight

    # BPM knob alignment
    if cached_features.get("tempo") is not None:
        target_bpm = 60 + (bpm_knob / 100) * 115
        actual_bpm = cached_features["tempo"]
        bpm_diff   = abs(actual_bpm - target_bpm)
        bpm_score  = max(0.0, 1.0 - (bpm_diff / 40))
        score_components.append(bpm_score * 1.2)
        weights_total += 1.2

    # AcousticBrainz mood alignment
    for mood_key, vibe_list in _AB_MOOD_TO_VIBE.items():
        if dominant_vibe in vibe_list:
            mood_val = cached_features.get(mood_key)
            if mood_val is not None:
                score_components.append(float(mood_val) * 0.6)
                weights_total += 0.6

    # Junk track filter
    speechiness = cached_features.get("speechiness")
    if speechiness is not None and speechiness > 0.65:
        return 0.0

    if not score_components or weights_total == 0:
        return 0.5

    return sum(score_components) / weights_total


async def blend_audio_features(
    tracks: list[dict],
    dominant_vibe: str,
    bpm_knob: int,
    db,
    audio_weight: float = 0.4,
    heuristic_key: str = "score",
    feature_index: Optional[dict] = None,
) -> list[dict]:
    """
    Async: blend real audio features into heuristic track scores.

    Parameters
    ----------
    tracks : list[dict]
        Must have 'score' key (heuristic).
    dominant_vibe : str
        e.g. "heartbreak", "hype"
    bpm_knob : int
        0–100 user knob value.
    db : Prisma
        Connected Prisma client — only queried when feature_index is None.
    audio_weight : float
        Weight for audio feature score vs heuristic score.
    heuristic_key : str
        Key on each track dict for the heuristic score.
    feature_index : dict | None
        Pass TRACK_FEATURE_INDEX from main.py for a zero-DB-call fast path.
        Keys: "title_lower|artist_lower" → feature dict.
        When None, falls back to DB lookup via Spotify IDs (original behaviour).
    """
    if not tracks:
        return tracks

    # ── Resolve feature map ───────────────────────────────────────────────────
    if feature_index is not None:
        # Fast path: in-process index, no DB call
        cache_map: dict[str, dict] = {}
        for t in tracks:
            key = f"{(t.get('title') or '').strip().lower()}|{(t.get('artist') or '').strip().lower()}"
            feat = feature_index.get(key)
            if feat:
                cache_map[key] = feat
        cache_hits = len(cache_map)
        logger.info(f"[AudioFeatures] Index hits: {cache_hits}/{len(tracks)} (no DB call)")
    else:
        # Fallback: original DB lookup via Spotify IDs
        spotify_ids = [t.get("spotify_id") or t.get("spotifyId") for t in tracks]
        spotify_ids = [sid for sid in spotify_ids if sid]

        if not spotify_ids:
            logger.debug("[AudioFeatures] No Spotify IDs — skipping feature blend")
            return tracks

        try:
            cached_rows = await db.trackfeaturecache.find_many(
                where={"spotifyId": {"in": spotify_ids}}
            )
            cache_map = {row.spotifyId: row.__dict__ for row in cached_rows}
            cache_hits = len(cache_map)
            logger.info(f"[AudioFeatures] DB cache hits: {cache_hits}/{len(spotify_ids)}")
        except Exception as e:
            logger.warning(f"[AudioFeatures] DB lookup failed: {e}")
            return tracks

    if not cache_map:
        return tracks

    # ── Score and blend ───────────────────────────────────────────────────────
    h_scores = [t.get(heuristic_key, 0.0) for t in tracks]
    h_max    = max(h_scores) if h_scores else 1.0
    h_min    = min(h_scores) if h_scores else 0.0
    h_range  = (h_max - h_min) or 1.0

    result = []
    for t in tracks:
        t = t.copy()

        if feature_index is not None:
            key = f"{(t.get('title') or '').strip().lower()}|{(t.get('artist') or '').strip().lower()}"
            cached = cache_map.get(key)
        else:
            sid    = t.get("spotify_id") or t.get("spotifyId")
            cached = cache_map.get(sid) if sid else None

        h_norm  = (t.get(heuristic_key, 0.0) - h_min) / h_range
        a_score = score_track_with_features(t, cached, dominant_vibe, bpm_knob)

        if a_score == 0.0 and cached is not None:
            continue  # hard-exclude junk tracks

        blended = (1.0 - audio_weight) * h_norm + audio_weight * a_score
        t["audio_score"]   = round(a_score, 3)
        t["blended_score"] = blended
        result.append(t)

    result.sort(key=lambda t: t.get("blended_score", 0.0), reverse=True)
    if result:
        logger.info(
            f"[AudioFeatures] Blended {len(result)} tracks. "
            f"Top: '{result[0].get('title')}' (blended={result[0].get('blended_score', 0):.3f})"
        )
    else:
        logger.info("[AudioFeatures] Empty result after blending")
    return result


# ─── THIN POOL CACHE ──────────────────────────────────────────────────────────

async def get_thin_pool_supplement(
    language: Optional[str],
    dominant_vibe: str,
    db,
    max_tracks: int = 40,
) -> list[dict]:
    """
    Fetch pre-cached tracks from ThinPoolCache for Language×Vibe combos
    that historically return few results from Last.fm.
    """
    language = language or "Any"

    _FALLBACK_ROUTING: dict[str, str] = {
        "chill_mainstream": "chill",
        "niche_ambient_slow": "ambient",
    }
    mapped_vibe = _FALLBACK_ROUTING.get(dominant_vibe, dominant_vibe)
    if mapped_vibe != dominant_vibe:
        logger.info(f"[ThinPool] Restrictive vibe '{dominant_vibe}' → routed to broader pool '{mapped_vibe}'")

    cache_key = f"{language}|{mapped_vibe}"

    try:
        from datetime import datetime, timezone
        row = await db.thinpoolcache.find_unique(where={"cacheKey": cache_key})

        if not row:
            logger.debug(f"[ThinPool] No cache for '{cache_key}'")
            return []

        now     = datetime.now(timezone.utc)
        expires = row.expiresAt
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if now > expires:
            logger.info(f"[ThinPool] Cache expired for '{cache_key}' — returning empty")
            return []

        tracks = json.loads(row.tracksJson)
        logger.info(
            f"[ThinPool] Returning {len(tracks)} cached tracks for '{cache_key}' "
            f"(source: {row.source})"
        )
        return tracks[:max_tracks]

    except Exception as e:
        logger.warning(f"[ThinPool] Cache lookup failed for '{cache_key}': {e}")
        return []


async def refresh_thin_pool_cache(
    language: str,
    dominant_vibe: str,
    tracks: list[dict],
    source: str,
    db,
    ttl_days: int = 7,
) -> None:
    """Write or update a ThinPoolCache entry."""
    from datetime import datetime, timezone, timedelta

    cache_key  = f"{language}|{dominant_vibe}"
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
        logger.info(f"[ThinPool] Cached {len(tracks)} tracks for '{cache_key}' (ttl={ttl_days}d)")
    except Exception as e:
        logger.error(f"[ThinPool] Cache write failed for '{cache_key}': {e}")
