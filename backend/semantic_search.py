"""
semantic_search.py
──────────────────
VibeFinderAI — Semantic Fallback Engine
Powered by sentence-transformers/all-MiniLM-L6-v2 (80MB, CPU-friendly)

PURPOSE
-------
When the NLP heuristic engine fires the fallback path (confidence < 0.25
and no entity lock), Last.fm's keyword search often returns junk — podcasts,
news clips, YouTube videos. This module provides an alternative: we embed
the user's raw prompt and rank a candidate track pool by cosine similarity
against pre-computed track embeddings built from {title} + {artist} text.

This is NOT training. We're using a frozen, pre-trained model as a
similarity function. No GPU, no fine-tuning. Just smart retrieval.

ARCHITECTURE
------------
  1. On first import, the model loads into memory (~80MB RAM, ~2s cold start).
     Subsequent calls are fast (<50ms per batch of 200 tracks).

  2. rank_tracks_by_prompt(prompt, tracks) — main entry point.
     Takes the raw user prompt and a list of track dicts (each with
     'title' and 'artist' keys). Returns the same list sorted by
     semantic relevance score, highest first.

  3. build_track_text(track) — converts a track dict into a short
     natural-language string for embedding. We deliberately keep it
     minimal so the model focuses on the music identity, not metadata.

  4. Scores are stored on each track dict under the key 'semantic_score'
     so the main scoring engine can blend them with the existing
     popularity and vibe-match scores.

GRACEFUL DEGRADATION
--------------------
If the model fails to load (bad install, OOM, etc.), ALL functions
return the input list unchanged and log a warning. The rest of the
engine continues normally — semantic search is additive, never blocking.

USAGE
-----
  from semantic_search import rank_tracks_by_prompt, semantic_ready

  if semantic_ready():
      tracks = rank_tracks_by_prompt(prompt, raw_pool)
  else:
      tracks = raw_pool   # fall back silently
"""

import logging
import time
from typing import Optional

logger = logging.getLogger("VibeFinderEngine.Semantic")

# ── Model state ───────────────────────────────────────────────────────────────
# Loaded lazily on first call so the API server starts instantly even if the
# model weights haven't been downloaded yet.
_model = None
_model_load_error: Optional[str] = None
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _load_model():
    """Load the sentence transformer model. Called once, cached in _model."""
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
        elapsed = time.time() - t0
        logger.info(f"[Semantic] Model loaded in {elapsed:.2f}s — ready.")
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
    """
    Returns True if the model is loaded and available.
    Triggers a load attempt on first call.
    """
    return _load_model() is not None


def build_track_text(track: dict) -> str:
    """
    Convert a track dict into a short natural-language string for embedding.

    We phrase it as a human would describe the track so the embedding space
    aligns with how users describe vibes. e.g.:
        "Motion Sickness by Phoebe Bridgers"

    We intentionally omit genres and tags here — those are handled by the
    heuristic engine. This module purely captures title/artist identity.
    """
    title = track.get("title", "").strip()
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

    Parameters
    ----------
    prompt : str
        The raw user vibe description, e.g. "deliriously tired but can't stop smiling"
    tracks : list[dict]
        Each dict must have at least 'title' and 'artist' keys.
        Additional keys are preserved untouched.
    top_n : int | None
        If provided, return only the top N results. Defaults to returning all.

    Returns
    -------
    list[dict]
        Same dicts, sorted by descending 'semantic_score' (float 0–1).
        On model failure, returns the input list unchanged (no semantic_score key).

    Notes
    -----
    - Embeddings are computed in a single batch call for efficiency.
    - Cosine similarity is used (standard for sentence-transformers).
    - The function is synchronous — call it from a thread executor in
      async contexts if latency matters (typically < 100ms for 200 tracks).
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

        # Build text representations
        track_texts = [build_track_text(t) for t in tracks]

        # Filter out empty strings (can't embed nothing)
        valid_indices = [i for i, text in enumerate(track_texts) if text.strip()]
        valid_texts = [track_texts[i] for i in valid_indices]

        if not valid_texts:
            return tracks

        # Batch encode: prompt + all track texts in one call
        all_texts = [prompt] + valid_texts
        embeddings = model.encode(all_texts, convert_to_numpy=True, show_progress_bar=False)

        prompt_embedding = embeddings[0]
        track_embeddings = embeddings[1:]

        # Cosine similarity — normalize then dot product
        prompt_norm = prompt_embedding / (np.linalg.norm(prompt_embedding) + 1e-10)
        track_norms = track_embeddings / (np.linalg.norm(track_embeddings, axis=1, keepdims=True) + 1e-10)
        similarities = track_norms @ prompt_norm  # shape: (N,)

        # Assign scores back to track dicts
        result = [t.copy() for t in tracks]  # don't mutate originals
        score_map = {}
        for idx, track_idx in enumerate(valid_indices):
            score_map[track_idx] = float(similarities[idx])

        for i, track in enumerate(result):
            track["semantic_score"] = score_map.get(i, 0.0)

        # Sort descending by semantic score
        result.sort(key=lambda t: t.get("semantic_score", 0.0), reverse=True)

        elapsed = time.time() - t0
        logger.info(
            f"[Semantic] Ranked {len(valid_texts)} tracks in {elapsed*1000:.1f}ms. "
            f"Top match: '{result[0].get('title')} - {result[0].get('artist')}' "
            f"(score={result[0].get('semantic_score', 0):.3f})"
        )

        if top_n is not None:
            result = result[:top_n]

        return result

    except Exception as e:
        logger.error(f"[Semantic] Ranking failed: {e}", exc_info=True)
        return tracks  # graceful degradation


def blend_semantic_scores(
    tracks: list[dict],
    semantic_weight: float = 0.35,
    heuristic_key: str = "score",
) -> list[dict]:
    """
    Blend the semantic_score with the existing heuristic score from the
    main scoring engine. Call this AFTER filter_and_score_tracks() has
    already set 'score' on each track.

    The blend is a weighted average. semantic_weight=0.35 means:
        final_score = 0.65 * heuristic_score + 0.35 * semantic_score

    Both scores are normalized to [0, 1] before blending.
    Tracks without a semantic_score (model unavailable) pass through unchanged.

    Parameters
    ----------
    tracks : list[dict]
        Track dicts with 'score' (heuristic) and optionally 'semantic_score'.
    semantic_weight : float
        How much weight to give the semantic score. 0.0 = pure heuristic,
        1.0 = pure semantic. Defaults to 0.35 — meaningful but not dominant.
    heuristic_key : str
        Key name for the heuristic score. Defaults to 'score'.
    """
    if not tracks:
        return tracks

    has_semantic = any("semantic_score" in t for t in tracks)
    if not has_semantic:
        return tracks

    # Normalize heuristic scores to [0, 1]
    heuristic_scores = [t.get(heuristic_key, 0.0) for t in tracks]
    h_max = max(heuristic_scores) if heuristic_scores else 1.0
    h_min = min(heuristic_scores) if heuristic_scores else 0.0
    h_range = h_max - h_min if h_max != h_min else 1.0

    result = []
    for t in tracks:
        t = t.copy()
        h_raw = t.get(heuristic_key, 0.0)
        h_norm = (h_raw - h_min) / h_range  # normalized 0–1
        s_norm = t.get("semantic_score", 0.5)  # already 0–1 from cosine sim

        blended = (1.0 - semantic_weight) * h_norm + semantic_weight * s_norm
        t["blended_score"] = blended
        result.append(t)

    result.sort(key=lambda t: t.get("blended_score", 0.0), reverse=True)
    return result
