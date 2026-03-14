"""
apple_routes.py
───────────────
VibeFinderAI — Apple Music MusicKit JS Integration

HOW IT WORKS
────────────
Unlike Spotify's server-side OAuth, MusicKit JS runs entirely in the browser:

  1. Frontend fetches a developer token from GET /api/apple/developer-token
  2. MusicKit JS (loaded from Apple's CDN) is configured with that token
  3. User clicks "Connect Apple Music" → music.authorize() opens Apple's popup
  4. User approves → MusicKit JS receives the Music User Token (stays in browser)
  5. All Apple Music API calls (search, create playlist, add tracks) are made
     client-side by MusicKit JS using both the dev token and user token.
     No user data touches our backend.

ENDPOINT
────────
  GET /api/apple/developer-token   → returns {token: "...jwt..."}

SETUP — add to Render env vars
──────────────────────────────
  APPLE_TEAM_ID      — 10-char alphanumeric, found top-right in developer.apple.com/account
  APPLE_KEY_ID       — 10-char key ID from Certificates > Keys in developer portal
  APPLE_PRIVATE_KEY  — full contents of the .p8 file (including -----BEGIN/END----- lines)
                       Use "\\n" for line breaks in the Render env var field, OR
                       paste the raw multiline value using Render's multiline env var support.

HOW TO GET THESE
────────────────
  1. developer.apple.com → Certificates, Identifiers & Profiles
  2. Identifiers → + → App IDs → App → Continue
     → Enable "MusicKit" in App Services → Register
  3. Keys → + → name it "VibeFinderAI MusicKit" → check "Media Services (MusicKit)"
     → Configure → select your identifier → Save → Download .p8 (ONE TIME ONLY)
  4. Your Key ID is shown on the key detail page (10 chars)
  5. Your Team ID is shown top-right on developer.apple.com/account

TOKEN LIFETIME
──────────────
  Apple developer tokens expire after max 6 months (15,778,800 seconds).
  This module caches the token and auto-regenerates when it expires.
  No restarts needed.
"""

import os
import time
import logging
import textwrap
from typing import Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("VibeFinderEngine.Apple")

router = APIRouter()

# ── env vars ─────────────────────────────────────────────────────────────────
APPLE_TEAM_ID    = os.getenv("APPLE_TEAM_ID", "")
APPLE_KEY_ID     = os.getenv("APPLE_KEY_ID", "")
APPLE_PRIVATE_KEY = os.getenv("APPLE_PRIVATE_KEY", "")  # full .p8 contents

# Token lifetime: 6 months minus 1 day (safe margin before Apple rejects it)
_TOKEN_LIFETIME_SECS = 15_778_800 - 86_400  # ~179 days

# In-memory cache: regenerate token before it expires
_cached_token: Optional[str] = None
_token_generated_at: float  = 0.0


def _normalize_private_key(raw: str) -> str:
    """
    Render env vars can't contain literal newlines easily.
    Accept both:
      - raw multiline (already correct)
      - \\n escaped (common when pasting into single-line env var fields)
    Also handles missing BEGIN/END headers for safety.
    """
    key = raw.strip().replace("\\n", "\n")

    # If it's a bare base64 blob without PEM headers, wrap it
    if "-----" not in key:
        key = (
            "-----BEGIN PRIVATE KEY-----\n"
            + "\n".join(textwrap.wrap(key, 64))
            + "\n-----END PRIVATE KEY-----"
        )
    return key


def _generate_developer_token() -> str:
    """
    Generate a MusicKit JWT developer token signed with ES256.
    Apple's format:
      Header: { "alg": "ES256", "kid": KEY_ID }
      Payload: { "iss": TEAM_ID, "iat": now, "exp": now + lifetime }
    """
    try:
        import jwt as _jwt
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="PyJWT not installed — run: pip install PyJWT cryptography"
        )

    if not APPLE_TEAM_ID or not APPLE_KEY_ID or not APPLE_PRIVATE_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Apple Music not configured. Add APPLE_TEAM_ID, APPLE_KEY_ID, "
                "and APPLE_PRIVATE_KEY to your Render environment variables."
            )
        )

    now = int(time.time())
    private_key = _normalize_private_key(APPLE_PRIVATE_KEY)

    token = _jwt.encode(
        payload={
            "iss": APPLE_TEAM_ID,
            "iat": now,
            "exp": now + _TOKEN_LIFETIME_SECS,
        },
        key=private_key,
        algorithm="ES256",
        headers={
            "alg": "ES256",
            "kid": APPLE_KEY_ID,
        },
    )

    logger.info(
        f"[Apple] Developer token generated "
        f"(team={APPLE_TEAM_ID}, key={APPLE_KEY_ID}, "
        f"expires_in={_TOKEN_LIFETIME_SECS // 86400}d)"
    )
    return token


def _get_or_refresh_token() -> str:
    """Return cached token, regenerating if expired or missing."""
    global _cached_token, _token_generated_at

    now = time.time()
    age = now - _token_generated_at
    # Regenerate if never generated or within 1 day of expiry
    if _cached_token is None or age >= (_TOKEN_LIFETIME_SECS - 86_400):
        _cached_token = _generate_developer_token()
        _token_generated_at = now

    return _cached_token


# ═══════════════════════════════════════════════════════════════════
# ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/apple/developer-token")
async def get_apple_developer_token():
    """
    Returns the MusicKit JS developer token.
    Called by the frontend on page load to configure MusicKit JS.
    No auth required — the token is public (it only identifies the app,
    not any user). User tokens are obtained client-side via music.authorize().
    """
    token = _get_or_refresh_token()
    return {"token": token}
