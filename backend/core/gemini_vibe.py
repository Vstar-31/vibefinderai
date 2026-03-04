"""
gemini_vibe.py
──────────────
VibeFinderAI — Gemini Flash AI Enhancement Layer
Place in: backend/core/gemini_vibe.py

PURPOSE
-------
The rule-based vibe_engine is fast and deterministic but struggles with:
  - Novel slang / non-English phrases not yet in the SYNONYM table
  - Mixed-language prompts ("give me something like Arijit but darker")
  - Nuanced emotional descriptions ("watching my city drown in amber light")
  - Artist/cultural references outside the entity scanner's DB

Gemini 1.5 Flash handles all of these. We call it ONLY when:
  1. Heuristic confidence < CONFIDENCE_THRESHOLD (default 0.40), OR
  2. The prompt appears non-English and no language was explicitly selected, OR
  3. Request has use_gemini=True (future Pro Mode feature)

FREE TIER SAFETY
----------------
Gemini 1.5 Flash free tier: 15 RPM, 1 million tokens/day, 1500 req/day.
We enforce a rolling 60s window capped at 13 RPM to stay safely under.
On 429 / quota exceeded we log a warning and fall back to heuristic result.
Never blocks the user — always returns something.

INTEGRATION IN main.py
-----------------------
  from core.gemini_vibe import gemini_enhancer

  # After heuristic analysis:
  vibe_data = vibe_engine.analyze_vibe_algorithm(...)
  if gemini_enhancer.should_enhance(vibe_data, request.text):
      vibe_data = await gemini_enhancer.enhance(request.text, request.language, vibe_data)

ENV VARS
--------
  GEMINI_API_KEY=your_key_here   # Get free key at aistudio.google.com
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("VibeFinderEngine.Gemini")

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.0-flash-lite"
GEMINI_URL     = (
    f"https://generativelanguage.googleapis.com/v1/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# Only fire Gemini if heuristic confidence is below this threshold
CONFIDENCE_THRESHOLD = 0.40

# Rolling rate limiter: max 13 calls per 60s (free tier = 15 RPM)
_MAX_CALLS_PER_WINDOW = 27  # flash-lite free tier = 30 RPM
_WINDOW_SECONDS       = 60.0

# All valid vibe names the engine recognises (keep in sync with VIBE_MAP)
VALID_VIBES = {
    "heartbreak", "romantic", "happy", "party", "hype", "calm", "chill",
    "focus", "euphoric", "soulful", "retro", "dreamy", "cinematic", "dark",
    "intense", "rock", "indie_folk", "ambient", "desi", "punjabi",
    "punjabi_soft", "haryanvi", "hyperpop", "industrial", "tropical", "country",
}

VALID_LANGUAGES = {
    "English", "Hindi", "Punjabi", "Tamil", "Telugu", "Kannada", "Malayalam",
    "Bengali", "Urdu", "Korean", "Japanese", "Spanish", "Portuguese", "French",
    "Arabic", "Afrobeats", "Any",
}

# ─── SYSTEM PROMPT ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are VibeFinderAI's music intelligence engine.
Your task: analyse a free-text user prompt and return a structured JSON describing the musical vibe.

VALID_VIBES: heartbreak, romantic, happy, party, hype, calm, chill, focus, euphoric, soulful,
retro, dreamy, cinematic, dark, intense, rock, indie_folk, ambient, desi, punjabi, punjabi_soft,
haryanvi, hyperpop, industrial, tropical, country

VALID_LANGUAGES: English, Hindi, Punjabi, Tamil, Telugu, Kannada, Malayalam, Bengali, Urdu,
Korean, Japanese, Spanish, Portuguese, French, Arabic, Afrobeats, Any

RULES:
1. dominant_vibe MUST be one of VALID_VIBES.
2. secondary_vibe MUST be one of VALID_VIBES or null.
3. confidence: float 0.0–1.0. Be honest — if the prompt is vague, 0.45 is fine.
4. detected_language: one of VALID_LANGUAGES. Use "Any" if clearly multilingual or ambiguous.
5. matched_keywords: 2–5 short phrases extracted directly from the prompt that drove your classification.
6. bpm_hint: integer 0–100 representing perceived energy/tempo (0=very slow, 50=neutral, 100=very fast).
7. reasoning: one sentence explaining your classification (for logs, not shown to user).

Return ONLY valid JSON. No preamble, no markdown fences, no extra text.

Example output:
{
  "dominant_vibe": "heartbreak",
  "secondary_vibe": "dreamy",
  "confidence": 0.82,
  "detected_language": "English",
  "matched_keywords": ["late night", "crying", "rain", "empty house"],
  "bpm_hint": 28,
  "reasoning": "Strong emotional imagery of loss and isolation maps to heartbreak with dreamy undertones."
}"""

# ─── ROLLING RATE LIMITER ────────────────────────────────────────────────────

class _RollingRateLimiter:
    """Thread-safe rolling window rate limiter for Gemini free tier."""

    def __init__(self, max_calls: int, window_sec: float):
        self._max   = max_calls
        self._win   = window_sec
        self._times: list[float] = []
        self._lock  = asyncio.Lock()

    async def acquire(self) -> bool:
        """Returns True if a call slot is available, False if rate limit hit."""
        async with self._lock:
            now = time.monotonic()
            # Purge calls older than the window
            self._times = [t for t in self._times if now - t < self._win]
            if len(self._times) >= self._max:
                return False
            self._times.append(now)
            return True

    def remaining(self) -> int:
        now = time.monotonic()
        active = [t for t in self._times if now - t < self._win]
        return max(0, self._max - len(active))


_rate_limiter = _RollingRateLimiter(_MAX_CALLS_PER_WINDOW, _WINDOW_SECONDS)

# ─── MAIN ENHANCER CLASS ─────────────────────────────────────────────────────

class GeminiVibeAnalyzer:
    """
    Wraps Gemini Flash to enhance low-confidence vibe analysis.
    Drop-in: never raises, always returns a valid vibe_data dict.
    """

    def should_enhance(self, heuristic_result: dict, prompt: str) -> bool:
        """
        Returns True if Gemini enhancement is worth attempting.
        Criteria:
          - API key is configured
          - Heuristic confidence is below threshold
          - Rate limit not exhausted
        """
        if not GEMINI_API_KEY:
            return False
        if heuristic_result.get("confidence", 1.0) >= CONFIDENCE_THRESHOLD:
            return False
        if _rate_limiter.remaining() == 0:
            logger.warning("[Gemini] Rate limit window full — skipping enhancement.")
            return False
        return True

    async def enhance(
        self,
        prompt: str,
        language: Optional[str],
        heuristic_result: dict,
    ) -> dict:
        """
        Calls Gemini Flash and merges the result with the heuristic baseline.
        If anything fails, returns the original heuristic_result unchanged.

        Merge strategy:
          - If Gemini confidence > heuristic confidence: use Gemini's vibe/secondary/keywords/bpm
          - Always preserve heuristic detected_artist and detected_song (entity scanner is more reliable)
          - bpm_hint from Gemini adjusts bpm_range string if confidence >= 0.6
        """
        acquired = await _rate_limiter.acquire()
        if not acquired:
            logger.warning("[Gemini] Rate slot denied at call time — falling back.")
            return heuristic_result

        user_message = f'Prompt: "{prompt}"\nUser-selected language: {language or "Any"}'

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": _SYSTEM_PROMPT},
                        {"text": user_message},
                    ],
                }
            ],
            "generationConfig": {
                "temperature":     0.2,   # Low temp for deterministic classification
                "maxOutputTokens": 300,
                "topP":            0.8,
            },
        }

        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    GEMINI_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp:

                    if resp.status == 429:
                        logger.warning("[Gemini] 429 quota exceeded — falling back to heuristic.")
                        return heuristic_result

                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning(f"[Gemini] HTTP {resp.status}: {body[:200]}")
                        return heuristic_result

                    raw = await resp.json()

        except asyncio.TimeoutError:
            logger.warning("[Gemini] Request timed out (>8s) — falling back.")
            return heuristic_result
        except Exception as e:
            logger.warning(f"[Gemini] Network error: {e} — falling back.")
            return heuristic_result

        # ── Parse Gemini response ──────────────────────────────────────────
        try:
            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            # Strip any accidental markdown fences
            text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
            parsed: dict = json.loads(text)
        except (KeyError, json.JSONDecodeError, IndexError) as e:
            logger.warning(f"[Gemini] Parse failed: {e} — falling back.")
            return heuristic_result

        # ── Validate fields ──────────────────────────────────────────────
        g_vibe  = parsed.get("dominant_vibe", "")
        g_sec   = parsed.get("secondary_vibe")
        g_conf  = float(parsed.get("confidence", 0.0))
        g_lang  = parsed.get("detected_language", "Any")
        g_kws   = parsed.get("matched_keywords", [])
        g_bpm   = int(parsed.get("bpm_hint", 50))
        g_reason = parsed.get("reasoning", "")

        if g_vibe not in VALID_VIBES:
            logger.warning(f"[Gemini] Invalid dominant_vibe '{g_vibe}' — falling back.")
            return heuristic_result

        if g_sec and g_sec not in VALID_VIBES:
            g_sec = None

        h_conf = float(heuristic_result.get("confidence", 0.0))

        logger.info(
            f"[Gemini] dominant={g_vibe} ({g_conf:.2f}) | "
            f"secondary={g_sec} | lang={g_lang} | "
            f"heuristic_conf={h_conf:.2f} | reason={g_reason}"
        )

        # ── Merge: Gemini wins if it's more confident ──────────────────────
        if g_conf > h_conf:
            result = dict(heuristic_result)  # shallow copy
            result["dominant_vibe"]     = g_vibe
            result["confidence"]        = g_conf
            result["secondary_vibe"]    = g_sec or heuristic_result.get("secondary_vibe")
            result["matched_keywords"]  = g_kws or heuristic_result.get("matched_keywords", [])
            result["_gemini_enhanced"]  = True
            result["_gemini_reason"]    = g_reason

            # Update language detection only if user didn't explicitly pick one
            if (not language or language == "Any") and g_lang in VALID_LANGUAGES:
                result["_gemini_detected_language"] = g_lang

            # Map bpm_hint → bpm_range string if Gemini is confident
            if g_conf >= 0.6:
                if g_bpm <= 20:
                    result["bpm_range"] = "40–70 BPM"
                elif g_bpm <= 40:
                    result["bpm_range"] = "70–95 BPM"
                elif g_bpm <= 60:
                    result["bpm_range"] = "90–120 BPM"
                elif g_bpm <= 80:
                    result["bpm_range"] = "115–145 BPM"
                else:
                    result["bpm_range"] = "140–180 BPM"

            logger.info(f"[Gemini] Enhancement ACCEPTED — replacing heuristic result.")
            return result

        else:
            # Gemini was less confident — still harvest keywords if they add new ones
            existing_kws = set(heuristic_result.get("matched_keywords", []))
            new_kws = [k for k in g_kws if k.lower() not in existing_kws]
            if new_kws:
                result = dict(heuristic_result)
                result["matched_keywords"] = list(existing_kws) + new_kws[:2]
                logger.info(f"[Gemini] Lower confidence but merged {len(new_kws)} new keywords.")
                return result

            logger.info(f"[Gemini] Enhancement SKIPPED — heuristic confidence already higher.")
            return heuristic_result

    async def detect_language(self, prompt: str) -> Optional[str]:
        """
        Lightweight language detection call. Used when language='Any' and the
        prompt looks non-English (high ratio of non-ASCII characters).
        Returns a VALID_LANGUAGE string or None on failure.
        """
        if not GEMINI_API_KEY:
            return None

        non_ascii = sum(1 for c in prompt if ord(c) > 127)
        if non_ascii / max(len(prompt), 1) < 0.15:
            return None  # Looks English enough — skip API call

        acquired = await _rate_limiter.acquire()
        if not acquired:
            return None

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": (
                    f"What music language/region does this prompt most likely belong to?\n"
                    f"Prompt: \"{prompt}\"\n"
                    f"Answer with exactly one word from this list: "
                    f"{', '.join(VALID_LANGUAGES)}. No other text."
                )}],
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 10},
        }

        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(GEMINI_URL, json=payload,
                                        headers={"Content-Type": "application/json"}) as resp:
                    if resp.status != 200:
                        return None
                    raw = await resp.json()
                    lang = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return lang if lang in VALID_LANGUAGES else None
        except Exception:
            return None


# ─── SINGLETON ───────────────────────────────────────────────────────────────
# Import this in main.py: from core.gemini_vibe import gemini_enhancer
gemini_enhancer = GeminiVibeAnalyzer()


# ─── INTEGRATION SNIPPET FOR main.py ─────────────────────────────────────────
"""
Add these lines to main.py AFTER the existing NLP analysis in analyze_vibe():

  # --- PASTE THIS BLOCK (after existing vibe_engine call, before entity scan) ---
  from core.gemini_vibe import gemini_enhancer

  vibe_data = vibe_engine.analyze_vibe_algorithm(
      text=request.text,
      artist_focus=request.artist_focus,
      genre_focus=50,
      bpm_focus=request.bpm_focus
  )

  # 1b. Gemini enhancement for low-confidence / ambiguous prompts (free tier)
  if gemini_enhancer.should_enhance(vibe_data, request.text):
      logger.info(f"[Gemini] Confidence {vibe_data.get('confidence'):.2f} < threshold — calling Gemini Flash...")
      vibe_data = await gemini_enhancer.enhance(request.text, request.language, vibe_data)
      if vibe_data.get('_gemini_enhanced'):
          logger.info(f"[Gemini] Enhanced: {vibe_data['dominant_vibe']} ({vibe_data['confidence']:.2f})")

  # Language auto-detect for non-English prompts
  if (not request.language or request.language == 'Any') and not vibe_data.get('_gemini_detected_language'):
      detected_lang = await gemini_enhancer.detect_language(request.text)
      if detected_lang:
          request = request.model_copy(update={'language': detected_lang})
          logger.info(f"[Gemini] Auto-detected language: {detected_lang}")
  elif vibe_data.get('_gemini_detected_language') and (not request.language or request.language == 'Any'):
      request = request.model_copy(update={'language': vibe_data['_gemini_detected_language']})
  # --- END PASTE ---
"""
