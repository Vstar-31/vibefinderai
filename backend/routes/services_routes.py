"""
services_routes.py
──────────────────
VibeFinderAI — Multi-Service Music Integration

SERVICES
────────
  Last.fm     — Love tracks, scrobble listens. Free, no caps.
  Deezer      — Add to library, create playlists. Free OAuth, no user caps.
  SoundCloud  — Like tracks, create playlists. Free OAuth.
  YouTube     — Create playlists, add videos. Free (10k quota/day).

CHANGES v2
──────────
  - YouTube search cache is now persistent: backed by ThinPoolCache table
    (cacheKey prefix "yt:") in addition to an in-process L1 dict. Cache
    survives Render deploys and cold starts. 7-day TTL unchanged.
    - Cache access is shared through core.youtube_cache.

ENV VARS NEEDED
───────────────
  LASTFM_API_KEY, LASTFM_SHARED_SECRET
  DEEZER_APP_ID, DEEZER_APP_SECRET
  SOUNDCLOUD_CLIENT_ID, SOUNDCLOUD_CLIENT_SECRET
  YOUTUBE_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
  FRONTEND_URL, BACKEND_URL
"""

import os
import hashlib
import json
import base64
import logging
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
import jwt as _jwt
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from core.youtube_cache import (
    init as init_youtube_cache,
    yt_cache_get,
    yt_cache_set,
    yt_cache_stats as get_youtube_cache_stats,
)

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
    init_youtube_cache(instance)

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
    sig_str = "".join(f"{k}{v}" for k, v in sorted(params.items()) if k != "format")
    sig_str += LASTFM_SHARED_SECRET
    return hashlib.md5(sig_str.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════
# STATUS — all services at once
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/services/status")
async def services_status(authorization: str = Query(...)):
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
    token:   str = Query(None),
    state:   str = Query(None),
    error:   str = Query(None),
):
    if service not in SUPPORTED_SERVICES:
        return RedirectResponse(f"{FRONTEND_URL}?service_error={service}&reason=unknown_service")

    if error:
        return RedirectResponse(f"{FRONTEND_URL}?service_error={service}&reason={error}")

    try:
        vf_token = base64.urlsafe_b64decode(state.encode()).decode()
        user_id  = _get_user_id(vf_token)
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}?service_error={service}&reason=bad_state")

    provider_id   = ""
    access_token  = ""
    refresh_token = None

    # ── Last.fm ────────────────────────────────────────────────────
    if service == "lastfm":
        auth_token = token or code
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
            session      = data["session"]
            provider_id  = session["name"]
            access_token = session["key"]
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
            try:
                data = resp.json()
            except Exception:
                from urllib.parse import parse_qs
                data = {k: v[0] for k, v in parse_qs(resp.text).items()}
            if "access_token" not in data:
                logger.error(f"[Services] Deezer token exchange failed: {resp.text[:200]}")
                return RedirectResponse(f"{FRONTEND_URL}?service_error=deezer&reason=token_exchange")
            access_token = data["access_token"]
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
    token    = authorization.replace("Bearer ", "")
    user_id  = _get_user_id(token)
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
    import time as _t
    token    = authorization.replace("Bearer ", "")
    user_id  = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "lastfm"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="Last.fm not connected")

    timestamp = int(_t.time())
    params = {
        "method":       "track.scrobble",
        "track[0]":     body.title,
        "artist[0]":    body.artist,
        "timestamp[0]": str(timestamp),
        "api_key":      LASTFM_API_KEY,
        "sk":           identity.accessToken,
    }
    params["api_sig"] = _lastfm_sign(params)
    params["format"]  = "json"

    async with httpx.AsyncClient() as client:
        resp = await client.post("https://ws.audioscrobbler.com/2.0/", data=params, timeout=10)
    data = resp.json()
    if data.get("error"):
        raise HTTPException(status_code=502, detail=f"Last.fm error: {data.get('message')}")
    return {"scrobbled": True}


# ═══════════════════════════════════════════════════════════════════
# DEEZER ACTIONS
# ═══════════════════════════════════════════════════════════════════

class DeezerTrackRequest(BaseModel):
    title:  str
    artist: str

class DeezerPlaylistRequest(BaseModel):
    name:   str
    tracks: list[dict]

async def _deezer_search_track(access_token: str, title: str, artist: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.deezer.com/search",
                params={"q": f'track:"{title}" artist:"{artist}"', "limit": 1, "access_token": access_token},
                timeout=8,
            )
        data  = resp.json()
        items = data.get("data", [])
        return str(items[0]["id"]) if items else None
    except Exception:
        return None

@router.post("/api/services/deezer/love")
async def deezer_love_track(body: DeezerTrackRequest, authorization: str = Query(...)):
    token    = authorization.replace("Bearer ", "")
    user_id  = _get_user_id(token)
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
            "https://api.deezer.com/user/me/tracks",
            params={"access_token": identity.accessToken, "track_id": track_id},
            timeout=10,
        )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"Deezer add failed ({resp.status_code})")
    return {"loved": True, "deezer_id": track_id}

@router.post("/api/services/deezer/playlist")
async def deezer_create_playlist(body: DeezerPlaylistRequest, authorization: str = Query(...)):
    token    = authorization.replace("Bearer ", "")
    user_id  = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "deezer"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="Deezer not connected")

    sp = identity.accessToken
    async with httpx.AsyncClient() as client:
        create_resp = await client.post(
            "https://api.deezer.com/user/me/playlists",
            params={"access_token": sp, "title": body.name[:255]},
            timeout=10,
        )
        if create_resp.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail="Deezer playlist create failed")
        playlist_id = create_resp.json().get("id")

        track_ids = []
        for t in body.tracks[:50]:
            tid = await _deezer_search_track(sp, t.get("title", ""), t.get("artist", ""))
            if tid:
                track_ids.append(tid)

        if track_ids:
            songs = ",".join(track_ids)
            await client.post(
                f"https://api.deezer.com/playlist/{playlist_id}/tracks",
                params={"access_token": sp, "songs": songs},
                timeout=15,
            )

    return {
        "playlist_id":  playlist_id,
        "playlist_url": f"https://www.deezer.com/playlist/{playlist_id}",
        "tracks_added": len(track_ids),
    }


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
    token    = authorization.replace("Bearer ", "")
    user_id  = _get_user_id(token)
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
    token    = authorization.replace("Bearer ", "")
    user_id  = _get_user_id(token)
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

@router.get("/api/services/youtube/cache-stats")
async def youtube_cache_stats():
    """Returns YouTube search cache stats."""
    return await get_youtube_cache_stats()


@router.get("/api/services/youtube/search")
async def youtube_search(q: str = Query(...), title: str = Query(None), artist: str = Query(None)):
    """
    Search YouTube for a track. Checks persistent cache (L1 + DB) before
    hitting the API. Cache survives Render deploys.
    """
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YouTube API key not configured")

    # Cache check (async — may hit DB)
    if title and artist:
        cached = await yt_cache_get(title, artist)
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
                logger.warning("[Services] YT quota exceeded on search")
                return {"found": False, "quota_exceeded": True}
            return {"found": False}

        items = data.get("items", [])
        if not items:
            return {"found": False}

        item     = items[0]
        video_id = item["id"]["videoId"]

        if title and artist:
            await yt_cache_set(title, artist, video_id)

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
    tracks: list[dict]

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
    import asyncio

    token    = authorization.replace("Bearer ", "")
    user_id  = _get_user_id(token)
    identity = await _db.oauthidentity.find_first(
        where={"userId": user_id, "providerName": "youtube"}
    )
    if not identity:
        raise HTTPException(status_code=403, detail="YouTube not connected")

    yt_token = identity.accessToken

    async def _yt_req(c: httpx.AsyncClient, method: str, url: str, **kwargs):
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
            raise HTTPException(status_code=502, detail=f"YouTube playlist create failed ({create_resp.status_code})")

        playlist_id  = create_resp.json()["id"]
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        tracks       = body.tracks[:50]
        logger.info(f"[Services] YT playlist {playlist_id} created — searching {len(tracks)} tracks")

        # 2. Search all tracks in parallel — persistent cache hits cost 0 quota
        async def search_one(t: dict):
            title  = t.get("title", "").strip()
            artist = t.get("artist", "").strip()
            cached = await yt_cache_get(title, artist)
            if cached:
                return cached
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
                await yt_cache_set(title, artist, video_id)
                return video_id
            except Exception as e:
                logger.warning(f"[Services] YT search error for '{title}': {e}")
                return None

        video_ids  = await asyncio.gather(*[search_one(t) for t in tracks])
        found_ids  = [vid for vid in video_ids if vid]
        logger.info(f"[Services] YT search: {len(found_ids)}/{len(tracks)} found")

        # 3. Add found videos sequentially with staggered delays
        async def add_one(video_id: str, index: int, retry_count: int = 0) -> bool:
            try:
                await asyncio.sleep(index * (0.4 + retry_count * 0.5))
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
                        await asyncio.sleep(2 ** retry_count)
                        return await add_one(video_id, index, retry_count + 1)
                    logger.warning(f"[Services] YT add video {video_id} failed: {resp.status_code}")
                    return False
                return True
            except Exception as e:
                logger.error(f"[Services] YT add_one exception for {video_id}: {e}")
                return False

        results = []
        for idx, vid in enumerate(found_ids):
            result = await add_one(vid, idx)
            results.append(result)
        added = sum(results)

    logger.info(f"[Services] YT playlist '{body.name}' done — {added}/{len(tracks)} tracks")
    return {"playlist_id": playlist_id, "playlist_url": playlist_url, "tracks_added": added}
