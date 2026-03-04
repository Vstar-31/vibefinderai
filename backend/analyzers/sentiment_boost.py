"""
sentiment_boost.py
──────────────────
VibeFinderAI — TextBlob Sentiment Analysis Layer
Place in: backend/core/sentiment_boost.py

PURPOSE
-------
Augments the rule-based vibe engine with TextBlob sentiment scoring.
TextBlob gives us two free dimensions:
  • polarity    (-1.0 negative → +1.0 positive)
  • subjectivity (0.0 objective → 1.0 subjective/emotional)

We use these to:
  1. Boost vibes that match the emotional tone of the prompt
  2. Catch ambiguous prompts where keyword matching scored low
  3. Disambiguate ties between vibes with similar keyword scores

INTEGRATION
-----------
In main.py, after analyze_vibe_algorithm() and Gemini enhancement:

  from core.sentiment_boost import apply_sentiment_boost
  vibe_data = apply_sentiment_boost(request.text, vibe_data)

No API key, no rate limit, pure offline NLP.

REQUIREMENTS
------------
  pip install textblob
  python -m textblob.download_corpora  (one-time, or set TEXTBLOB_NO_CORPORA=1)
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("VibeFinderEngine.Sentiment")

# ── GRACEFUL IMPORT ───────────────────────────────────────────────────────────
try:
    from textblob import TextBlob
    _TEXTBLOB_AVAILABLE = True
except ImportError:
    _TEXTBLOB_AVAILABLE = False
    logger.warning("[Sentiment] textblob not installed — sentiment boost disabled. Run: pip install textblob")

# ── SENTIMENT → VIBE BOOST MAP ───────────────────────────────────────────────
# Maps (polarity_bucket, subjectivity_bucket) → {vibe: boost_weight}
# polarity:    "positive" | "neutral" | "negative"
# subjectivity: "high" | "low"

_BOOST_MAP: dict[tuple[str, str], dict[str, float]] = {
    # Happy, uplifting, joyful prompt
    ("positive", "high"):   {"happy": 0.35, "euphoric": 0.25, "romantic": 0.15, "soulful": 0.10},
    # Factual / informational positive (e.g. "good workout music")
    ("positive", "low"):    {"happy": 0.20, "hype": 0.20, "focus": 0.15, "party": 0.10},
    # Flat, neutral, descriptive (e.g. "late night coding")
    ("neutral",  "low"):    {"focus": 0.25, "chill": 0.20, "ambient": 0.15, "calm": 0.10},
    # Emotional but not clearly positive/negative (e.g. "feels like drifting")
    ("neutral",  "high"):   {"dreamy": 0.30, "chill": 0.20, "cinematic": 0.15, "heartbreak": 0.10},
    # Emotional negative — loss, pain, longing
    ("negative", "high"):   {"heartbreak": 0.40, "dark": 0.20, "dreamy": 0.15, "soulful": 0.10},
    # Factual/objective negative (e.g. "angry gym session")
    ("negative", "low"):    {"intense": 0.30, "hype": 0.20, "dark": 0.15, "rock": 0.10},
}

# Minimum polarity distance from 0 to call it positive/negative (vs neutral)
_POLARITY_THRESHOLD = 0.08
# Subjectivity threshold to call it "high"
_SUBJECTIVITY_THRESHOLD = 0.45

# Max boost we'll add to any single vibe score
# Kept conservative — sentiment guides, doesn't override keyword matches
_MAX_BOOST = 0.40

# Only apply boost when heuristic confidence is below this
# High-confidence matches don't need sentiment help
_CONFIDENCE_GATE = 0.65

# ── SPECIAL STUDY / FOCUS INTENT DETECTOR ────────────────────────────────────
# TextBlob can't read intent, so we handle study/focus/work explicitly here
_STUDY_PATTERNS = re.compile(
    r"\b(study|studying|revision|revising|homework|concentrate|concentrating|"
    r"focus|focusing|work session|deep work|coding session|late night work|"
    r"reading music|background music|white noise|productive|productivity|"
    r"exam|assignment|dissertation|thesis|essay writing)\b",
    re.IGNORECASE
)

_ENERGY_INTENSIFIERS = re.compile(
    r"\b(really|super|very|extremely|so|absolutely|fucking|damn|totally|"
    r"completely|utterly|deeply|intensely|overwhelmingly)\b",
    re.IGNORECASE
)


def _get_buckets(polarity: float, subjectivity: float) -> tuple[str, str]:
    """Convert raw TextBlob scores into categorical buckets."""
    if polarity > _POLARITY_THRESHOLD:
        pol = "positive"
    elif polarity < -_POLARITY_THRESHOLD:
        pol = "negative"
    else:
        pol = "neutral"

    subj = "high" if subjectivity >= _SUBJECTIVITY_THRESHOLD else "low"
    return pol, subj


def _scale_boost(boost_val: float, confidence: float, intensifier_present: bool) -> float:
    """
    Scale the boost:
      - Lower existing confidence → stronger boost (we trust sentiment more)
      - Intensifier words (really, super, etc.) → 1.3× boost
      - Cap at _MAX_BOOST
    """
    # Confidence scaling: 0.0 conf → full boost, 0.65 conf → 0 boost
    conf_scale = max(0.0, 1.0 - (confidence / _CONFIDENCE_GATE))
    scaled = boost_val * conf_scale
    if intensifier_present:
        scaled *= 1.3
    return min(scaled, _MAX_BOOST)


def apply_sentiment_boost(text: str, vibe_data: dict) -> dict:
    """
    Main entry point. Takes raw prompt text and vibe_data dict from
    analyze_vibe_algorithm(), returns an updated vibe_data dict.

    Safe to call even if textblob isn't installed — returns vibe_data unchanged.
    """
    if not _TEXTBLOB_AVAILABLE or not text:
        return vibe_data

    confidence = vibe_data.get("confidence", 0.0)

    # Skip if already high-confidence — don't mess with good results
    if confidence >= _CONFIDENCE_GATE:
        return vibe_data

    try:
        blob = TextBlob(text)
        polarity    = blob.sentiment.polarity      # -1.0 to +1.0
        subjectivity = blob.sentiment.subjectivity # 0.0 to 1.0

        pol_bucket, subj_bucket = _get_buckets(polarity, subjectivity)
        boost_map = _BOOST_MAP.get((pol_bucket, subj_bucket), {})

        has_intensifier = bool(_ENERGY_INTENSIFIERS.search(text))
        has_study_intent = bool(_STUDY_PATTERNS.search(text))

        logger.info(
            f"[Sentiment] polarity={polarity:.2f} subjectivity={subjectivity:.2f} "
            f"→ ({pol_bucket},{subj_bucket}) | study={has_study_intent}"
        )

        # Build adjusted scores dict (copy so we don't mutate original)
        scores = dict(vibe_data.get("_raw_scores", {}))

        # Apply sentiment boosts
        for vibe, raw_boost in boost_map.items():
            boost = _scale_boost(raw_boost, confidence, has_intensifier)
            if boost > 0.01:
                scores[vibe] = scores.get(vibe, 0.0) + boost
                logger.debug(f"[Sentiment] +{boost:.3f} → {vibe}")

        # Study intent override: strongly boost focus, suppress party/hype
        if has_study_intent:
            study_boost = _scale_boost(0.50, confidence, False)
            scores["focus"] = scores.get("focus", 0.0) + study_boost
            scores["chill"] = scores.get("chill", 0.0) + study_boost * 0.5
            # Suppress party/hype when studying
            scores["party"] = scores.get("party", 0.0) * 0.3
            scores["hype"]  = scores.get("hype",  0.0) * 0.3
            logger.info(f"[Sentiment] Study intent detected — boosting focus +{study_boost:.2f}")

        if not scores:
            return vibe_data

        # Re-derive dominant + secondary from boosted scores
        sorted_vibes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        new_dominant  = sorted_vibes[0][0]
        new_secondary = sorted_vibes[1][0] if len(sorted_vibes) > 1 else None
        new_top_score = sorted_vibes[0][1]

        # Normalise to a confidence-like value (cap at 0.97)
        new_confidence = min(new_top_score / (new_top_score + 0.5), 0.97)

        # Only update if sentiment actually changed the dominant vibe or improved confidence
        changed = (new_dominant != vibe_data.get("dominant_vibe"))
        improved = (new_confidence > confidence + 0.05)

        if changed or improved:
            updated = dict(vibe_data)
            updated["dominant_vibe"]   = new_dominant
            updated["secondary_vibe"]  = new_secondary
            updated["confidence"]      = new_confidence
            updated["_sentiment_boost"] = {
                "polarity":     round(polarity, 3),
                "subjectivity": round(subjectivity, 3),
                "bucket":       f"{pol_bucket}_{subj_bucket}",
                "study_intent": has_study_intent,
                "changed_vibe": changed,
            }
            logger.info(
                f"[Sentiment] {'Changed' if changed else 'Improved'}: "
                f"{vibe_data.get('dominant_vibe')} → {new_dominant} "
                f"(conf {confidence:.2f} → {new_confidence:.2f})"
            )
            return updated

        return vibe_data

    except Exception as e:
        logger.warning(f"[Sentiment] Error (non-fatal): {e}")
        return vibe_data
