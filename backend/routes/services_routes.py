"""
services_routes.py
──────────────────
VibeFinderAI — Multi-Service Music Integration

SERVICES
────────
  Last.fm     — Love tracks, scrobble listens. Free, no caps.
  Deezer      — Add to library, create playlists. Free OAuth, no user caps.
  SoundCloud  — Like tracks, create playlists. Free OAuth.
                NOTE: SoundCloud closed new app registrations in 2021.
                Only works if you have an existing SC developer app.
  YouTube     — Create playlists, add videos. Free (10k quota/day).

ENDPOINTS
─────────
  GET  /api/services/status                        → all connected services for user
  GET  /api/services/{service}/authorize           → OAuth URL
  GET  /api/services/{service}/callback            → OAuth callback handler
  DELETE /api/services/{service}/disconnect        → remove stored tokens

  POST /api/services/lastfm/love                   → love a track
  POST /api/services/lastfm/scrobble               → scrobble a track

  POST /api/services/deezer/love                   → add track to Deezer favorites
  POST /api/services/deezer/playlist               → create Deezer playlist + add tracks

  POST /api/services/soundcloud/like               → like a track
  POST /api/services/soundcloud/playlist           → create SoundCloud playlist

  GET  /api/services/youtube/search                → search YouTube (no user auth needed)
  POST /api/services/youtube/playlist              → create YouTube playlist + add videos

ENV VARS NEEDED (add to Render)
────────────────────────────────
  # Last.fm
  LASTFM_API_KEY          — from last.fm/api/account
  LASTFM_SHARED_SECRET    — from last.fm/api/account

  # Deezer
  DEEZER_APP_ID           — from developers.deezer.com
  DEEZER_APP_SECRET       — from developers.deezer.com

  # SoundCloud (only if you have an existing SC developer app)
  SOUNDCLOUD_CLIENT_ID    — from soundcloud.com/you/apps
  SOUNDCLOUD_CLIENT_SECRET

  # YouTube / Google
  YOUTUBE_API_KEY         — from console.cloud.google.com (for search, no auth needed)
  GOOGLE_CLIENT_ID        — for playlist creation (OAuth)
  GOOGLE_CLIENT_SECRET    — for playlist creation (OAuth)

  # Shared
  FRONTEND_URL            — already set (e.g. https://vibefinderai.netlify.app)
  BACKEND_URL             — e.g. https://vibefinderai.onrender.com
"""

import os
import hashlib
import json
import time
import base64
import logging
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
import jwt as _jwt
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

logger = logging.getLogger("VibeFinderEngine.Services")
router = APIRouter()

# ── injected by main.py ──────────────────────────────────────────────────────
_db         = None
_SECRET_KEY = None
_ALGORITHM  = "HS256"

def set_db(instance, secret_key: str):
    global _db, _SECRET_KEY
    _db         = instance
    _SECRET_KEY = secret_key

# ── env vars ─────────────────────────────────────────────────────────────────
FRONTEND_URL  = os.getenv("FRONTEND_URL", "https://vibefinderai.netlify.app")
BACKEND_URL   = os.getenv("BACKEND_URL",  "https://vibefinderai.onrender.com")

LASTFM_API_KEY       = os.getenv("LASTFM_API_KEY", "")
LASTFM_SHARED_SECRET = os.getenv("LASTFM_SHARED_SECRET", "")

DEEZER_APP_ID     = os.getenv("DEEZER_APP_ID", "")
DEEZER_APP_SECRET = os.getenv("DEEZER_APP_SECRET", "")

SOUNDCLOUD_CLIENT_ID     = os.getenv("SOUNDCLOUD_CLIENT_ID", "")
SOUNDCLOUD_CLIENT_SECRET = os.getenv("SOUNDCLOUD_CLIENT_SECRET", "")

YOUTUBE_API_KEY      = os.getenv("YOUTUBE_API_KEY", "")
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

SUPPORTED_SERVICES = ["lastfm", "deezer", "soundcloud", "youtube"]

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

def _callback_url(service: str) -> str:
    return f"{BACKEND_URL}/api/services/{service}/callback"

# ── Last.fm signature ────────────────────────────────────────────────────────
def _lastfm_sign(params: dict) -> str:
    """Create MD5 signature for Last.fm API calls."""
    sig_str = "".join(f"{k}{v}" for k, v in sorted(params.items()) if k != "format")
    sig_str += LASTFM_SHARED_SECRET
    return hashlib.md5(sig_str.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════
# STATUS — all services at once
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/services/status")
async def services_status(authorization: str = Query(...)):
    """Returns which services the user has connected."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)

    identities = await _db.oauthidentity.find_many(
        where={"userId": user_id, "providerName": {"in": SUPPORTED_SERVICES}}
    )
    connected = {row.providerName: {"connected": True, "provider_id": row.providerId}
                 for row in identities}
    return {
        svc: connected.get(svc, {"connected": False})
        for svc in SUPPORTED_SERVICES
    }


# ═══════════════════════════════════════════════════════════════════
# AUTHORIZE — per service
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/services/{service}/authorize")
async def service_authorize(service: str, token: str = Query(...)):
    if service not in SUPPORTED_SERVICES:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")

    # Encode VibeFinder token in state
    state = base64.urlsafe_b64encode(token.encode()).decode()
    cb    = _callback_url(service)

    if service == "lastfm":
        if not LASTFM_API_KEY:
            raise HTTPException(status_code=503, detail="Last.fm not configured")
        url = f"https://www.last.fm/api/auth/?api_key={LASTFM_API_KEY}&cb={quote(cb + '?state=' + state, safe='')}"
        return {"url": url}

    if service == "deezer":
        if not DEEZER_APP_ID:
            raise HTTPException(status_code=503, detail="Deezer not configured")
        perms = "basic_access,email,offline_access,manage_library,manage_playlist,listening_history"
        params = {"app_id": DEEZER_APP_ID, "redirect_uri": cb, "perms": perms, "state": state}
        return {"url": "https://connect.deezer.com/oauth/auth.php?" + urlencode(params)}

    if service == "soundcloud":
        if not SOUNDCLOUD_CLIENT_ID:
            raise HTTPException(status_code=503, detail="SoundCloud not configured")
        params = {
            "client_id":     SOUNDCLOUD_CLIENT_ID,
            "redirect_uri":  cb,
            "response_type": "code",
            "scope":         "non-expiring",
            "state":         state,
        }
        return {"url": "https://soundcloud.com/connect?" + urlencode(params)}

    if service == "youtube":
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=503, detail="YouTube/Google not configured")
        params = {
            "client_id":     GOOGLE_CLIENT_ID,
            "redirect_uri":  cb,
            "response_type": "code",
            "scope":         "https://www.googleapis.com/auth/youtube",
            "access_type":   "offline",
            "prompt":        "consent",
            "state":         state,
        }
        return {"url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


# ═══════════════════════════════════════════════════════════════════
# CALLBACK — per service
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/services/{service}/callback")
async def service_callback(
    service: str,
    code:    str = Query(None),
    token:   str = Query(None),  # Last.fm sends 'token' not 'code'
    state:   str = Query(None),
    error:   str = Query(None),
):
    if service not in SUPPORTED_SERVICES:
        return RedirectResponse(f"{FRONTEND_URL}?service_error={service}&reason=unknown_service")

    if error:
        return RedirectResponse(f"{FRONTEND_URL}?service_error={service}&reason={error}")

    # Decode VibeFinder user from state
    try:
        vf_token = base64.urlsafe_b64decode(state.encode()).decode()
        user_id  = _get_user_id(vf_token)
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}?service_error={service}&reason=bad_state")

    provider_id  = ""
    access_token = ""
    refresh_token = None

    # ── Last.fm ────────────────────────────────────────────────────
    if service == "lastfm":
        auth_token = token or code  # Last.fm uses 'token' param
        if not auth_token:
            return RedirectResponse(f"{FRONTEND_URL}?service_error=lastfm&reason=no_token")
        try:
            params = {
                "method":  "auth.getSession",
                "api_key": LASTFM_API_KEY,
                "token":   auth_token,
            }
            params["api_sig"] = _lastfm_sign(params)
            params["format"]  = "json"
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://ws.audioscrobbler.com/2.0/", params=params, timeout=10)
            data = resp.json()
            if "error" in data:
                logger.error(f"[Services] Last.fm getSession error: {data}")
                return RedirectResponse(f"{FRONTEND_URL}?service_error=lastfm&reason=session_failed")
            session     = data["session"]
            provider_id  = session["name"]          # Last.fm username
            access_token = session["key"]            # session key (permanent)
        except Exception as e:
            logger.error(f"[Services] Last.fm callback error: {e}")
            return RedirectResponse(f"{FRONTEND_URL}?service_error=lastfm&reason=server_error")

    # ── Deezer ────────────────────────────────────────────────────
    elif service == "deezer":
        if not code:
            return RedirectResponse(f"{FRONTEND_URL}?service_error=deezer&reason=no_code")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://connect.deezer.com/oauth/access_token.php",
                    params={"app_id": DEEZER_APP_ID, "secret": DEEZER_APP_SECRET, "code": code, "output": "json"},
                    timeout=10,
                )
            # Deezer returns form-encoded or JSON depending on output param
            try:
                data = resp.json()
            except Exception:
                # fallback: parse as query string
                from urllib.parse import parse_qs
                data = {k: v[0] for k, v in parse_qs(resp.text).items()}
            if "access_token" not in data:
                logger.error(f"[Services] Deezer token exchange failed: {resp.text[:200]}")
                return RedirectResponse(f"{FRONTEND_URL}?service_error=deezer&reason=token_exchange")
            access_token  = data["access_token"]
            # Get Deezer user ID
            me_resp = await httpx.AsyncClient().get(
                "https://api.deezer.com/user/me",
                params={"access_token": access_token},
                timeout=8,
            )
            me = me_resp.json()
            provider_id = str(me.get("id", ""))
        except Exception as e:
            logger.error(f"[Services] Deezer callback error: {e}")
            return RedirectResponse(f"{FRONTEND_URL}?service_error=deezer&reason=server_error")

    # ── SoundCloud ────────────────────────────────────────────────
    elif service == "soundcloud":
        if not code:
            return RedirectResponse(f"{FRONTEND_URL}?service_error=soundcloud&reason=no_code")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.soundcloud.com/oauth2/token",
                    data={
                        "client_id":     SOUNDCLOUD_CLIENT_ID,
                        "client_secret": SOUNDCLOUD_CLIENT_SECRET,
                        "grant_type":    "authorization_code",
                        "code":          code,
                        "redirect_uri":  _callback_url(service),
                    },
                    timeout=10,
                )
            data = resp.json()
            if "access_token" not in data:
                return RedirectResponse(f"{FRONTEND_URL}?service_error=soundcloud&reason=token_exchange")
            access_token  = data["access_token"]
            refresh_token = data.get("refresh_token")
            # Get SC user ID
            me_resp = await httpx.AsyncClient().get(
                "https://api.soundcloud.com/me",
                headers={"Authorization": f"OAuth {access_token}"},
                timeout=8,
            )
            me = me_resp.json()
            provider_id = str(me.get("id", ""))
        except Exception as e:
            logger.error(f"[Services] SoundCloud callback error: {e}")
            return RedirectResponse(f"{FRONTEND_URL}?service_error=soundcloud&reason=server_error")

    # ── YouTube / Google ─────────────────────────────────────────
    elif service == "youtube":
        if not code:
            return RedirectResponse(f"{FRONTEND_URL}?service_error=youtube&reason=no_code")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id":     GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "code":          code,
                        "grant_type":    "authorization_code",
                        "redirect_uri":  _callback_url(service),
                    },
                    timeout=10,
                )
            data = resp.json()
            if "access_token" not in data:
                return RedirectResponse(f"{FRONTEND_URL}?service_error=youtube&reason=token_exchange")
            access_token  = data["access_token"]
            refresh_token = data.get("refresh_token")
            # Get Google user ID
            me_resp = await httpx.AsyncClient().get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=8,
            )
            me = me_resp.json()
            provider_id = me.get("sub", "")
        except Exception as e:
            logger.error(f"[Services] YouTube callback error: {e}")
            return RedirectResponse(f"{FRONTEND_URL}?service_error=youtube&reason=server_error")

    # ── Upsert OAuthIdentity ──────────────────────────────────────
    try:
        existing = await _db.oauthidentity.find_first(
            where={"userId": user_id, "providerName": service}
        )
        if existing:
            await _db.oauthidentity.update(
                where={"id": existing.id},
                data={
                    "accessToken":  access_token,
                    "providerId":   provider_id,
                    **({"refreshToken": refresh_token} if refresh_token else {}),
                }
            )
        else:
            await _db.oauthidentity.create(data={
                "providerName": service,
                "providerId":   provider_id,
                "accessToken":  access_token,
                "refreshToken": refresh_token,
                "userId":       user_id,
            })
        logger.info(f"[Services] {service} connected for user {user_id[:8]}... (id={provider_id})")
    except Exception as e:
        logger.error(f"[Services] DB upsert error for {service}: {e}")
        return RedirectResponse(f"{FRONTEND_URL}?service_error={service}&reason=db_error")

    return RedirectResponse(f"{FRONTEND_URL}?service_connected={service}&provider_id={quote(provider_id, safe='')}")


# ═══════════════════════════════════════════════════════════════════
# DISCONNECT
# ═══════════════════════════════════════════════════════════════════

@router.delete("/api/services/{service}/disconnect")
async def service_disconnect(service: str, authorization: str = Query(...)):
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)
    await _db.oauthidentity.delete_many(
        where={"userId": user_id, "providerName": service}
    )
    return {"disconnected": True, "service": service}


# ═══════════════════════════════════════════════════════════════════
# LAST.FM ACTIONS
# ═══════════════════════════════════════════════════════════════════

class LastfmTrackRequest(BaseModel):
    title:  str
    artist: str

@router.post("/api/services/lastfm/love")
async def lastfm_love_track(body: LastfmTrackRequest, authorization: str = Query(...)):
    """Love a track on Last.fm."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "lastfm"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="Last.fm not connected")

    params = {
        "method":  "track.love",
        "track":   body.title,
        "artist":  body.artist,
        "api_key": LASTFM_API_KEY,
        "sk":      identity.accessToken,
    }
    params["api_sig"] = _lastfm_sign(params)
    params["format"]  = "json"

    async with httpx.AsyncClient() as client:
        resp = await client.post("https://ws.audioscrobbler.com/2.0/", data=params, timeout=10)
    data = resp.json()
    if data.get("error"):
        raise HTTPException(status_code=502, detail=f"Last.fm error: {data.get('message')}")
    logger.info(f"[Services] Last.fm loved '{body.title}' for user {user_id[:8]}...")
    return {"loved": True}

@router.post("/api/services/lastfm/scrobble")
async def lastfm_scrobble(body: LastfmTrackRequest, authorization: str = Query(...)):
    """Scrobble a track on Last.fm."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "lastfm"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="Last.fm not connected")

    timestamp = int(time.time())
    params = {
        "method":     "track.scrobble",
        "track[0]":   body.title,
        "artist[0]":  body.artist,
        "timestamp[0]": str(timestamp),
        "api_key":    LASTFM_API_KEY,
        "sk":         identity.accessToken,
    }
    params["api_sig"] = _lastfm_sign(params)
    params["format"]  = "json"

    async with httpx.AsyncClient() as client:
        resp = await client.post("https://ws.audioscrobbler.com/2.0/", data=params, timeout=10)
    data = resp.json()
    if data.get("error"):
        raise HTTPException(status_code=502, detail=f"Last.fm error: {data.get('message')}")
    logger.info(f"[Services] Last.fm scrobbled '{body.title}' for user {user_id[:8]}...")
    return {"scrobbled": True}


# ═══════════════════════════════════════════════════════════════════
# DEEZER ACTIONS
# ═══════════════════════════════════════════════════════════════════

class DeezerTrackRequest(BaseModel):
    title:  str
    artist: str

class DeezerPlaylistRequest(BaseModel):
    name:   str
    tracks: list[dict]  # [{title, artist}, ...]

async def _deezer_search_track(access_token: str, title: str, artist: str) -> Optional[str]:
    """Search Deezer for a track, return track ID."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.deezer.com/search",
                params={"q": f'track:"{title}" artist:"{artist}"', "limit": 1, "access_token": access_token},
                timeout=8,
            )
        data = resp.json()
        items = data.get("data", [])
        return str(items[0]["id"]) if items else None
    except Exception:
        return None

@router.post("/api/services/deezer/love")
async def deezer_love_track(body: DeezerTrackRequest, authorization: str = Query(...)):
    """Add a track to the user's Deezer favorites."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "deezer"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="Deezer not connected")

    track_id = await _deezer_search_track(identity.accessToken, body.title, body.artist)
    if not track_id:
        raise HTTPException(status_code=404, detail=f"Track not found on Deezer: {body.title}")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.deezer.com/user/me/tracks",
            params={"access_token": identity.accessToken, "track_id": track_id},
            timeout=10,
        )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"Deezer add failed ({resp.status_code})")
    logger.info(f"[Services] Deezer loved '{body.title}' for user {user_id[:8]}...")
    return {"loved": True, "deezer_id": track_id}

@router.post("/api/services/deezer/playlist")
async def deezer_create_playlist(body: DeezerPlaylistRequest, authorization: str = Query(...)):
    """Create a Deezer playlist and add tracks."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "deezer"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="Deezer not connected")

    sp = identity.accessToken
    async with httpx.AsyncClient() as client:
        # 1. Create playlist
        create_resp = await client.post(
            "https://api.deezer.com/user/me/playlists",
            params={"access_token": sp, "title": body.name[:255]},
            timeout=10,
        )
        if create_resp.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Deezer playlist create failed")
        playlist_id = create_resp.json().get("id")

        # 2. Resolve track IDs
        track_ids = []
        for t in body.tracks[:50]:  # cap at 50
            tid = await _deezer_search_track(sp, t.get("title", ""), t.get("artist", ""))
            if tid:
                track_ids.append(tid)

        # 3. Add tracks
        if track_ids:
            songs = ",".join(track_ids)
            await client.post(
                f"https://api.deezer.com/playlist/{playlist_id}/tracks",
                params={"access_token": sp, "songs": songs},
                timeout=15,
            )

    playlist_url = f"https://www.deezer.com/playlist/{playlist_id}"
    logger.info(f"[Services] Deezer playlist '{body.name}' created ({len(track_ids)} tracks) for user {user_id[:8]}...")
    return {"playlist_id": playlist_id, "playlist_url": playlist_url, "tracks_added": len(track_ids)}


# ═══════════════════════════════════════════════════════════════════
# SOUNDCLOUD ACTIONS
# ═══════════════════════════════════════════════════════════════════

class SCTrackRequest(BaseModel):
    title:  str
    artist: str

class SCPlaylistRequest(BaseModel):
    name:   str
    tracks: list[dict]

async def _sc_search_track(access_token: str, title: str, artist: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.soundcloud.com/tracks",
                headers={"Authorization": f"OAuth {access_token}"},
                params={"q": f"{title} {artist}", "limit": 1},
                timeout=8,
            )
        items = resp.json() if resp.status_code == 200 else []
        return str(items[0]["id"]) if items else None
    except Exception:
        return None

@router.post("/api/services/soundcloud/like")
async def soundcloud_like_track(body: SCTrackRequest, authorization: str = Query(...)):
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "soundcloud"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="SoundCloud not connected")

    track_id = await _sc_search_track(identity.accessToken, body.title, body.artist)
    if not track_id:
        raise HTTPException(status_code=404, detail="Track not found on SoundCloud")

    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"https://api.soundcloud.com/me/likes/tracks/{track_id}",
            headers={"Authorization": f"OAuth {identity.accessToken}"},
            timeout=10,
        )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"SoundCloud like failed ({resp.status_code})")
    return {"liked": True, "sc_track_id": track_id}

@router.post("/api/services/soundcloud/playlist")
async def soundcloud_create_playlist(body: SCPlaylistRequest, authorization: str = Query(...)):
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "soundcloud"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="SoundCloud not connected")

    track_ids = []
    for t in body.tracks[:50]:
        tid = await _sc_search_track(identity.accessToken, t.get("title",""), t.get("artist",""))
        if tid:
            track_ids.append({"id": int(tid)})

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.soundcloud.com/playlists",
            headers={"Authorization": f"OAuth {identity.accessToken}", "Content-Type": "application/json"},
            json={"playlist": {"title": body.name, "sharing": "public", "tracks": track_ids}},
            timeout=15,
        )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"SoundCloud playlist create failed ({resp.status_code})")
    data = resp.json()
    return {"playlist_id": data.get("id"), "playlist_url": data.get("permalink_url"), "tracks_added": len(track_ids)}


# ═══════════════════════════════════════════════════════════════════
# YOUTUBE ACTIONS
# ═══════════════════════════════════════════════════════════════════

# ── YouTube search cache (7-day TTL to save quota) ──────────────────
import time as _time
_YT_SEARCH_CACHE = {}  # {f"{title}|{artist}": {"video_id": "...", "ts": time.time()}}
_YT_CACHE_TTL    = 7 * 24 * 3600  # 7 days in seconds

def _yt_cache_key(title: str, artist: str) -> str:
    """Generate cache key from title+artist."""
    return f"{title.lower()}|{artist.lower()}".replace(" ", "_")

def _yt_cache_get(title: str, artist: str) -> Optional[str]:
    """Get cached video_id, return None if not found or expired."""
    key = _yt_cache_key(title, artist)
    if key not in _YT_SEARCH_CACHE:
        return None
    entry = _YT_SEARCH_CACHE[key]
    if _time.time() - entry["ts"] > _YT_CACHE_TTL:
        del _YT_SEARCH_CACHE[key]
        return None
    return entry["video_id"]

def _yt_cache_set(title: str, artist: str, video_id: str) -> None:
    """Store video_id in cache with timestamp."""
    key = _yt_cache_key(title, artist)
    _YT_SEARCH_CACHE[key] = {"video_id": video_id, "ts": _time.time()}

@router.get("/api/services/youtube/cache-stats")
async def youtube_cache_stats():
    """Returns YouTube search cache stats — for monitoring quota savings."""
    now   = _time.time()
    valid = sum(1 for v in _YT_SEARCH_CACHE.values() if now - v["ts"] <= _YT_CACHE_TTL)
    return {
        "total_entries":    len(_YT_SEARCH_CACHE),
        "valid_entries":    valid,
        "ttl_days":         7,
        "quota_saved_est":  valid * 100,
    }
async def youtube_search(q: str = Query(...), title: str = Query(None), artist: str = Query(None)):
    """
    Search YouTube for a track — returns {video_id, title, thumbnail}.
    No user auth needed, just YOUTUBE_API_KEY.
    Pass title+artist for cache lookup (saves 100 quota units per hit).
    """
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YouTube API key not configured")

    # Cache check
    if title and artist:
        cached = _yt_cache_get(title, artist)
        if cached:
            return {"found": True, "video_id": cached, "cached": True}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"key": YOUTUBE_API_KEY, "q": q, "type": "video", "part": "snippet", "maxResults": 1},
                timeout=8,
            )
        data = resp.json()

        if "error" in data:
            if data["error"].get("code") == 403:
                logger.warning(f"[Services] YT quota exceeded on search")
                return {"found": False, "quota_exceeded": True}
            return {"found": False}

        items = data.get("items", [])
        if not items:
            return {"found": False}

        item     = items[0]
        video_id = item["id"]["videoId"]

        if title and artist:
            _yt_cache_set(title, artist, video_id)

        return {
            "found":     True,
            "video_id":  video_id,
            "title":     item["snippet"]["title"],
            "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
            "channel":   item["snippet"]["channelTitle"],
        }
    except Exception as e:
        logger.error(f"[Services] YouTube search error: {e}")
        return {"found": False}


class YTPlaylistRequest(BaseModel):
    name:   str
    tracks: list[dict]  # [{title, artist}, ...]

async def _yt_refresh_token(identity) -> Optional[str]:
    if not identity.refreshToken:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id":     GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "refresh_token": identity.refreshToken,
                    "grant_type":    "refresh_token",
                },
                timeout=10,
            )
        data = resp.json()
        new_token = data.get("access_token")
        if new_token:
            await _db.oauthidentity.update(
                where={"id": identity.id},
                data={"accessToken": new_token}
            )
        return new_token
    except Exception:
        return None

@router.post("/api/services/youtube/playlist")
async def youtube_create_playlist(body: YTPlaylistRequest, authorization: str = Query(...)):
    """Create a YouTube playlist and add matching videos."""
    token   = authorization.replace("Bearer ", "")
    user_id = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "youtube"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="YouTube not connected")

    yt_token = identity.accessToken

    import asyncio

    async def _yt_req(c: httpx.AsyncClient, method: str, url: str, **kwargs):
        """Auth-aware YouTube API call with token refresh on 401."""
        nonlocal yt_token
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {yt_token}"
        resp = await getattr(c, method)(url, headers=headers, **kwargs)
        if resp.status_code == 401:
            yt_token = await _yt_refresh_token(identity)
            if not yt_token:
                raise HTTPException(status_code=401, detail="YouTube token expired — reconnect")
            headers["Authorization"] = f"Bearer {yt_token}"
            resp = await getattr(c, method)(url, headers=headers, **kwargs)
        return resp

    async with httpx.AsyncClient(timeout=15) as client:

        # 1. Create playlist
        create_resp = await _yt_req(
            client, "post",
            "https://www.googleapis.com/youtube/v3/playlists",
            params={"part": "snippet,status"},
            json={
                "snippet": {"title": body.name[:150], "description": "Created by VibeFinderAI"},
                "status":  {"privacyStatus": "private"},
            },
        )
        if create_resp.status_code not in (200, 201):
            logger.error(f"[Services] YT playlist create failed {create_resp.status_code}: {create_resp.text[:200]}")
            raise HTTPException(status_code=502, detail=f"YouTube playlist create failed ({create_resp.status_code}: {create_resp.text[:80]})")

        playlist_id  = create_resp.json()["id"]
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        tracks       = body.tracks[:50]
        logger.info(f"[Services] YT playlist {playlist_id} created — searching {len(tracks)} tracks (parallel + cache)")

        # 2. Search ALL tracks in parallel — cache hits cost 0 quota units
        async def search_one(t: dict):
            title  = t.get("title", "").strip()
            artist = t.get("artist", "").strip()
            # Check cache first — saves 100 quota units per hit
            cached = _yt_cache_get(title, artist)
            if cached:
                return cached
            # Not cached — search the API
            q = f"{title} {artist} official audio"
            try:
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={"key": YOUTUBE_API_KEY, "q": q, "type": "video", "part": "snippet", "maxResults": 1},
                )
                data = resp.json()
                if "error" in data:
                    if data["error"].get("code") == 403:
                        logger.warning("[Services] YT quota exceeded during playlist search")
                    return None
                items = data.get("items", [])
                if not items:
                    return None
                video_id = items[0]["id"]["videoId"]
                _yt_cache_set(title, artist, video_id)
                return video_id
            except Exception as e:
                logger.warning(f"[Services] YT search error for '{title}': {e}")
                return None

        video_ids  = await asyncio.gather(*[search_one(t) for t in tracks])
        found_ids  = [vid for vid in video_ids if vid]
        cache_hits = sum(1 for t in tracks if _yt_cache_get(t.get("title",""), t.get("artist","")))
        logger.info(f"[Services] YT search: {len(found_ids)}/{len(tracks)} found, {cache_hits} from cache")

        # 3. Add all found videos to playlist — SEQUENTIAL with delays to avoid 409 rate limits
        async def add_one(video_id: str, index: int, retry_count: int = 0) -> bool:
            try:
                # Stagger requests: 400ms delay + exponential backoff on retries
                base_delay = 0.4 + (retry_count * 0.5)
                await asyncio.sleep(index * base_delay)
                
                resp = await _yt_req(
                    client, "post",
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    params={"part": "snippet"},
                    json={"snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }},
                )
                if resp.status_code not in (200, 201):
                    if resp.status_code == 409 and retry_count < 3:
                        logger.info(f"[Services] YT add video {video_id} got 409 — retrying (attempt {retry_count + 2}/4)...")
                        await asyncio.sleep(2 ** retry_count)  # exponential backoff: 1s, 2s, 4s
                        return await add_one(video_id, index, retry_count + 1)
                    logger.warning(f"[Services] YT add video {video_id} failed: {resp.status_code}")
                    return False
                logger.info(f"[Services] YT added video {video_id}")
                return True
            except Exception as e:
                logger.error(f"[Services] YT add_one exception for {video_id}: {e}")
                return False

        # Add sequentially to avoid 409 conflicts
        results = []
        for idx, vid in enumerate(found_ids):
            result = await add_one(vid, idx)
            results.append(result)
        added   = sum(results)

    logger.info(f"[Services] ✓ YT playlist '{body.name}' done — {added}/{len(tracks)} tracks for user {user_id[:8]}...")
    return {"playlist_id": playlist_id, "playlist_url": playlist_url, "tracks_added": added, "cache_hits": cache_hits}
