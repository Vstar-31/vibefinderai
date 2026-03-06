"""
spotify_routes.py
─────────────────
VibeFinderAI — Spotify OAuth 2.0 + Playlist Export + Track Search

ENDPOINTS
─────────
  GET  /api/spotify/authorize          → redirect URL for Spotify OAuth
  GET  /api/spotify/callback           → handles Spotify redirect, stores tokens
  GET  /api/spotify/status             → check if user has connected Spotify
  DELETE /api/spotify/disconnect       → revoke stored tokens
  POST /api/spotify/export-playlist    → create real Spotify playlist from result
  GET  /api/spotify/search             → search Spotify for a track (returns URI + preview)

SETUP
─────
Add to .env:
  SPOTIFY_CLIENT_ID=your_client_id
  SPOTIFY_CLIENT_SECRET=your_client_secret
  SPOTIFY_REDIRECT_URI=https://your-backend.onrender.com/api/spotify/callback

In Spotify Dashboard → App → Redirect URIs, add the SPOTIFY_REDIRECT_URI above.
"""

import os
import json
import base64
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import httpx
import jwt as _jwt

logger = logging.getLogger("VibeFinderEngine.Spotify")

router = APIRouter()

# ── injected by main.py ──────────────────────────────────────────────────────
_db = None
_SECRET_KEY = None
_ALGORITHM  = "HS256"

def set_db(instance, secret_key: str):
    global _db, _SECRET_KEY
    _db         = instance
    _SECRET_KEY = secret_key

# ── env vars ─────────────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI  = os.getenv(
    "SPOTIFY_REDIRECT_URI",
    "http://localhost:10000/api/spotify/callback"
)
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vibefinderai.netlify.app")

SPOTIFY_SCOPES = " ".join([
    "playlist-modify-public",
    "playlist-modify-private",
    "streaming",
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-read-email",
    "user-read-private",
])

# ── auth helper ───────────────────────────────────────────────────────────────
def _get_user_id(token: str) -> str:
    try:
        payload = _jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        return uid
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

async def _get_oauth2_scheme_optional(authorization: Optional[str] = None) -> Optional[str]:
    return authorization

# ── token refresh ─────────────────────────────────────────────────────────────
async def _refresh_spotify_token(identity) -> Optional[str]:
    """Refresh expired Spotify access token using stored refresh token."""
    if not identity.refreshToken:
        return None
    try:
        creds = base64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://accounts.spotify.com/api/token",
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": identity.refreshToken,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"[Spotify] Token refresh failed: {resp.text}")
                return None
            data = resp.json()
            new_token = data.get("access_token")
            # Update stored token
            await _db.oauthidentity.update(
                where={"id": identity.id},
                data={
                    "accessToken": new_token,
                    **({"refreshToken": data["refresh_token"]} if "refresh_token" in data else {}),
                }
            )
            return new_token
    except Exception as e:
        logger.error(f"[Spotify] Refresh error: {e}")
        return None


async def _get_valid_spotify_token(user_id: str) -> Optional[str]:
    """Get a valid Spotify access token for user, refreshing if needed."""
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "spotify"}
    )
    if not identity:
        return None
    # Try the stored token first — if it fails a Spotify call will 401
    # We proactively refresh if we know it's stale (Spotify tokens last 1hr)
    # Simple approach: always try, catch 401, refresh, retry
    return identity.accessToken


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/spotify/authorize")
async def spotify_authorize(token: str = Query(..., description="VibeFinder JWT")):
    """
    Returns a Spotify OAuth authorization URL.
    Frontend redirects user there; Spotify sends them back to /callback.
    """
    if not SPOTIFY_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Spotify not configured — add SPOTIFY_CLIENT_ID to env")

    # Encode VibeFinder token in state so we know who to store tokens for
    state = base64.urlsafe_b64encode(token.encode()).decode()

    params = {
        "response_type": "code",
        "client_id":     SPOTIFY_CLIENT_ID,
        "scope":         SPOTIFY_SCOPES,
        "redirect_uri":  SPOTIFY_REDIRECT_URI,
        "state":         state,
    }
    query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
    url = f"https://accounts.spotify.com/authorize?{query}"
    return {"url": url}


@router.get("/api/spotify/callback")
async def spotify_callback(
    code:  str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
):
    """
    Spotify OAuth callback. Exchanges code for tokens, stores in OAuthIdentity.
    Redirects to frontend with ?spotify=connected or ?spotify=error.
    """
    if error:
        return RedirectResponse(f"{FRONTEND_URL}?spotify=error&reason={error}")

    if not code or not state:
        return RedirectResponse(f"{FRONTEND_URL}?spotify=error&reason=missing_params")

    # Decode VibeFinder user token from state
    try:
        vf_token = base64.urlsafe_b64decode(state.encode()).decode()
        user_id  = _get_user_id(vf_token)
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}?spotify=error&reason=bad_state")

    # Exchange code for Spotify tokens
    try:
        creds = base64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://accounts.spotify.com/api/token",
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type":   "authorization_code",
                    "code":         code,
                    "redirect_uri": SPOTIFY_REDIRECT_URI,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error(f"[Spotify] Token exchange failed: {resp.text}")
                return RedirectResponse(f"{FRONTEND_URL}?spotify=error&reason=token_exchange")

            tokens = resp.json()

            # Get Spotify user profile to get their Spotify user ID
            profile_resp = await client.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=10,
            )
            if profile_resp.status_code != 200:
                return RedirectResponse(f"{FRONTEND_URL}?spotify=error&reason=profile_fetch")

            profile = profile_resp.json()
            spotify_user_id = profile["id"]
            display_name    = profile.get("display_name", "")

    except Exception as e:
        logger.error(f"[Spotify] Callback error: {e}")
        return RedirectResponse(f"{FRONTEND_URL}?spotify=error&reason=server_error")

    # Upsert OAuthIdentity
    try:
        existing = await _db.oauthidentity.find_first(
            where={"userId": user_id, "providerName": "spotify"}
        )
        if existing:
            await _db.oauthidentity.update(
                where={"id": existing.id},
                data={
                    "accessToken":  tokens["access_token"],
                    "refreshToken": tokens.get("refresh_token", existing.refreshToken),
                    "providerId":   spotify_user_id,
                }
            )
        else:
            await _db.oauthidentity.create(data={
                "providerName": "spotify",
                "providerId":   spotify_user_id,
                "accessToken":  tokens["access_token"],
                "refreshToken": tokens.get("refresh_token"),
                "userId":       user_id,
            })
        logger.info(f"[Spotify] Connected for user {user_id} → Spotify {spotify_user_id} ({display_name})")
    except Exception as e:
        logger.error(f"[Spotify] DB upsert error: {e}")
        return RedirectResponse(f"{FRONTEND_URL}?spotify=error&reason=db_error")

    return RedirectResponse(f"{FRONTEND_URL}?spotify=connected&name={httpx.QueryParams({'n': display_name})['n']}")


@router.get("/api/spotify/status")
async def spotify_status(authorization: str = Query(...)):
    """Returns whether the current user has Spotify connected."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)

    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "spotify"}
    )
    if not identity:
        return {"connected": False}

    # Fetch display name from Spotify
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f"Bearer {identity.accessToken}"},
                timeout=8,
            )
            if resp.status_code == 401:
                new_token = await _refresh_spotify_token(identity)
                if new_token:
                    resp = await client.get(
                        "https://api.spotify.com/v1/me",
                        headers={"Authorization": f"Bearer {new_token}"},
                        timeout=8,
                    )
            if resp.status_code == 200:
                profile = resp.json()
                return {
                    "connected":    True,
                    "display_name": profile.get("display_name", ""),
                    "spotify_id":   profile.get("id", ""),
                    "image":        (profile.get("images") or [{}])[0].get("url"),
                }
    except Exception as e:
        logger.warning(f"[Spotify] Status check error: {e}")

    return {"connected": True, "display_name": "", "spotify_id": identity.providerId}


@router.delete("/api/spotify/disconnect")
async def spotify_disconnect(authorization: str = Query(...)):
    """Remove stored Spotify tokens."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)

    await _db.oauthidentity.delete_many(
        where={"userId": user_id, "providerName": "spotify"}
    )
    return {"disconnected": True}


class ExportPlaylistRequest(BaseModel):
    name:        str
    description: str = ""
    tracks:      list[dict]   # [{title, artist, spotify_uri, ...}]
    is_public:   bool = False


@router.post("/api/spotify/export-playlist")
async def export_to_spotify(body: ExportPlaylistRequest, authorization: str = Query(...)):
    """
    Create a real Spotify playlist and add tracks to it.
    Tracks with spotify:track:ID uris are added directly.
    Tracks with spotify:search: uris are resolved via Spotify search first.
    """
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)

    sp_token = await _get_valid_spotify_token(user_id)
    if not sp_token:
        raise HTTPException(status_code=403, detail="Spotify not connected")

    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "spotify"}
    )
    spotify_user_id = identity.providerId

    async def _spotify_request(method, url, **kwargs):
        """Make Spotify API request, auto-refreshing token on 401."""
        nonlocal sp_token
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {sp_token}"
        async with httpx.AsyncClient() as client:
            resp = await getattr(client, method)(url, headers=headers, timeout=15, **kwargs)
            if resp.status_code == 401:
                sp_token = await _refresh_spotify_token(identity)
                if not sp_token:
                    raise HTTPException(status_code=401, detail="Spotify token expired")
                headers["Authorization"] = f"Bearer {sp_token}"
                resp = await getattr(client, method)(url, headers=headers, timeout=15, **kwargs)
            return resp

    try:
        # 1. Create playlist
        create_resp = await _spotify_request(
            "post",
            f"https://api.spotify.com/v1/users/{spotify_user_id}/playlists",
            json={
                "name":        body.name[:100],
                "description": body.description[:300] or f"Created by VibeFinderAI",
                "public":      body.is_public,
            }
        )
        if create_resp.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Spotify playlist create failed: {create_resp.text}")

        playlist_id  = create_resp.json()["id"]
        playlist_url = create_resp.json()["external_urls"]["spotify"]

        # 2. Resolve track URIs — search for any that are spotify:search: style
        track_uris = []
        search_tasks = []

        for t in body.tracks:
            uri = t.get("spotify_uri", "")
            if uri.startswith("spotify:track:"):
                track_uris.append(uri)
            else:
                # Need to search
                search_tasks.append((len(track_uris), t))
                track_uris.append(None)  # placeholder

        # Resolve search tasks
        for idx, t in search_tasks:
            try:
                q = f"{t.get('title','')} {t.get('artist','')}".strip()
                search_resp = await _spotify_request(
                    "get",
                    "https://api.spotify.com/v1/search",
                    params={"q": q, "type": "track", "limit": 1}
                )
                if search_resp.status_code == 200:
                    items = search_resp.json().get("tracks", {}).get("items", [])
                    if items:
                        track_uris[idx] = items[0]["uri"]
            except Exception as e:
                logger.warning(f"[Spotify] Search failed for {t}: {e}")

        # Filter out unresolved
        resolved = [u for u in track_uris if u]

        # 3. Add tracks in batches of 100 (Spotify limit)
        for i in range(0, len(resolved), 100):
            batch = resolved[i:i+100]
            add_resp = await _spotify_request(
                "post",
                f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
                json={"uris": batch}
            )
            if add_resp.status_code not in (200, 201):
                logger.warning(f"[Spotify] Add tracks batch failed: {add_resp.text}")

        logger.info(f"[Spotify] Exported playlist '{body.name}' ({len(resolved)} tracks) for user {user_id}")
        return {
            "playlist_id":  playlist_id,
            "playlist_url": playlist_url,
            "tracks_added": len(resolved),
            "tracks_total": len(body.tracks),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Spotify] Export error: {e}")
        raise HTTPException(status_code=500, detail="Playlist export failed")


@router.get("/api/spotify/search")
async def spotify_search(
    q:             str = Query(...),
    authorization: str = Query(...),
):
    """Search Spotify for a track. Returns URI, preview_url, and album art."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)

    sp_token = await _get_valid_spotify_token(user_id)
    if not sp_token:
        raise HTTPException(status_code=403, detail="Spotify not connected")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {sp_token}"},
                params={"q": q, "type": "track", "limit": 1},
                timeout=8,
            )
            if resp.status_code == 200:
                items = resp.json().get("tracks", {}).get("items", [])
                if items:
                    t = items[0]
                    return {
                        "found":        True,
                        "spotify_uri":  t["uri"],
                        "preview_url":  t.get("preview_url"),
                        "cover_art":    (t.get("album", {}).get("images") or [{}])[0].get("url"),
                        "duration_ms":  t.get("duration_ms"),
                        "popularity":   t.get("popularity"),
                    }
        return {"found": False}
    except Exception as e:
        logger.error(f"[Spotify] Search error: {e}")
        return {"found": False}
