"""
playlist_routes.py
──────────────────
VibeFinderAI — Playlist CRUD + User History API Routes
Place in: backend/routes/playlist_routes.py

Then register in main.py:
  from routes.playlist_routes import router as playlist_router
  app.include_router(playlist_router, prefix="/api")

PRISMA SCHEMA ADDITIONS NEEDED
-------------------------------
Add to schema.prisma before running `prisma db push`:

  model SavedPlaylist {
    id            String    @id @default(cuid())
    userId        String
    name          String
    dominantVibe  String?
    prompt        String?
    language      String?
    tracks        String    // JSON array of {title, artist, spotify_uri, apple_uri, preview_url, cover_art}
    isPublic      Boolean   @default(false)
    shareToken    String?   @unique @default(cuid())
    createdAt     DateTime  @default(now())
    updatedAt     DateTime  @updatedAt
    user          User      @relation(fields: [userId], references: [id], onDelete: Cascade)

    @@index([userId])
    @@index([shareToken])
  }

  // Add to User model:
  //   savedPlaylists  SavedPlaylist[]
"""

import json
import logging
import os
import secrets
from datetime import datetime
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from prisma import Prisma

logger = logging.getLogger("VibeFinderEngine")

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_student_budget_key_dont_leak_this")
ALGORITHM  = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Prisma instance — injected from main.py via dependency
# In main.py, add: from routes.playlist_routes import set_db; set_db(db)
_db: Optional[Prisma] = None

def set_db(prisma_instance: Prisma):
    global _db
    _db = prisma_instance

def get_db() -> Prisma:
    if _db is None:
        raise RuntimeError("DB not initialised — call set_db(db) in main.py lifespan")
    return _db


# ─── AUTH HELPER ─────────────────────────────────────────────────────────────

async def _get_user_id(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ─── PYDANTIC MODELS ─────────────────────────────────────────────────────────

class TrackItem(BaseModel):
    title:       str
    artist:      str
    spotify_uri: str
    apple_uri:   str
    preview_url: Optional[str] = None
    cover_art:   Optional[str] = None

class SavePlaylistRequest(BaseModel):
    name:         str
    prompt:       Optional[str]   = None
    dominant_vibe: Optional[str]  = None
    language:     Optional[str]   = None
    tracks:       list[TrackItem]
    is_public:    bool             = False

class UpdatePlaylistRequest(BaseModel):
    name:      Optional[str]  = None
    is_public: Optional[bool] = None

class PlaylistResponse(BaseModel):
    id:            str
    name:          str
    prompt:        Optional[str]
    dominant_vibe: Optional[str]
    language:      Optional[str]
    tracks:        list[dict]
    is_public:     bool
    share_token:   Optional[str]
    share_url:     Optional[str]
    track_count:   int
    created_at:    str
    updated_at:    str


def _make_share_url(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    frontend = os.getenv("FRONTEND_URL_PROD", "http://localhost:5173")
    return f"{frontend}/playlist/{token}"


def _row_to_response(row) -> dict:
    tracks = json.loads(row.tracks) if isinstance(row.tracks, str) else row.tracks
    return {
        "id":            row.id,
        "name":          row.name,
        "prompt":        row.prompt,
        "dominant_vibe": row.dominantVibe,
        "language":      row.language,
        "tracks":        tracks,
        "is_public":     row.isPublic,
        "share_token":   row.shareToken,
        "share_url":     _make_share_url(row.shareToken) if row.isPublic else None,
        "track_count":   len(tracks),
        "created_at":    row.createdAt.isoformat(),
        "updated_at":    row.updatedAt.isoformat(),
    }


# ─── ROUTES ──────────────────────────────────────────────────────────────────

@router.post("/playlist/save", status_code=201)
async def save_playlist(
    body: SavePlaylistRequest,
    token: str = Depends(oauth2_scheme),
):
    """
    Save a generated playlist. Returns the saved playlist ID and share URL.
    Users can save up to 50 playlists (free tier limit).
    """
    db      = get_db()
    user_id = await _get_user_id(token)

    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Playlist name cannot be empty")
    if not body.tracks:
        raise HTTPException(status_code=422, detail="Cannot save an empty playlist")
    if len(body.tracks) > 100:
        raise HTTPException(status_code=422, detail="Max 100 tracks per playlist")

    # Enforce 50-playlist cap (generous free tier)
    try:
        count = await db.savedplaylist.count(where={"userId": user_id})
        if count >= 50:
            raise HTTPException(
                status_code=400,
                detail="Playlist limit reached (50). Delete some playlists to save new ones."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[Playlist] Count check failed: {e}")

    share_token = secrets.token_urlsafe(12) if body.is_public else None
    tracks_json = json.dumps([t.dict() for t in body.tracks])

    try:
        row = await db.savedplaylist.create(data={
            "userId":       user_id,
            "name":         body.name.strip()[:80],
            "prompt":       (body.prompt or "")[:500] or None,
            "dominantVibe": body.dominant_vibe,
            "language":     body.language,
            "tracks":       tracks_json,
            "isPublic":     body.is_public,
            "shareToken":   share_token,
        })
        logger.info(f"[Playlist] Saved '{row.name}' ({len(body.tracks)} tracks) for user {user_id[:8]}...")
        return _row_to_response(row)

    except Exception as e:
        logger.error(f"[Playlist] Save failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to save playlist")


@router.get("/playlist/list")
async def list_playlists(
    token: str = Depends(oauth2_scheme),
    limit: int = 20,
    offset: int = 0,
):
    """List all playlists for the authenticated user, newest first."""
    db      = get_db()
    user_id = await _get_user_id(token)

    try:
        rows = await db.savedplaylist.find_many(
            where={"userId": user_id},
            order={"createdAt": "desc"},
            take=min(limit, 50),
            skip=offset,
        )
        total = await db.savedplaylist.count(where={"userId": user_id})
        return {
            "playlists": [_row_to_response(r) for r in rows],
            "total":     total,
            "limit":     limit,
            "offset":    offset,
        }
    except Exception as e:
        logger.error(f"[Playlist] List failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch playlists")


@router.get("/playlist/{playlist_id}")
async def get_playlist(playlist_id: str, token: str = Depends(oauth2_scheme)):
    """Fetch a single playlist by ID. Must be owner or playlist must be public."""
    db      = get_db()
    user_id = await _get_user_id(token)

    try:
        row = await db.savedplaylist.find_unique(where={"id": playlist_id})
    except Exception as e:
        logger.error(f"[Playlist] Fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not row:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if row.userId != user_id and not row.isPublic:
        raise HTTPException(status_code=403, detail="Not authorised")

    return _row_to_response(row)


@router.get("/playlist/share/{share_token}")
async def get_shared_playlist(share_token: str):
    """
    Public endpoint — fetch a shared playlist by its share token.
    No auth required. Only works if isPublic=True.
    """
    db = get_db()
    try:
        row = await db.savedplaylist.find_unique(where={"shareToken": share_token})
    except Exception as e:
        logger.error(f"[Playlist] Share fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not row:
        raise HTTPException(status_code=404, detail="Shared playlist not found")
    if not row.isPublic:
        raise HTTPException(status_code=403, detail="This playlist is private")

    return _row_to_response(row)


@router.patch("/playlist/{playlist_id}")
async def update_playlist(
    playlist_id: str,
    body: UpdatePlaylistRequest,
    token: str = Depends(oauth2_scheme),
):
    """Rename a playlist or toggle its public/private status."""
    db      = get_db()
    user_id = await _get_user_id(token)

    try:
        row = await db.savedplaylist.find_unique(where={"id": playlist_id})
        if not row:
            raise HTTPException(status_code=404, detail="Playlist not found")
        if row.userId != user_id:
            raise HTTPException(status_code=403, detail="Not your playlist")

        update_data: dict = {}
        if body.name is not None:
            if not body.name.strip():
                raise HTTPException(status_code=422, detail="Name cannot be empty")
            update_data["name"] = body.name.strip()[:80]

        if body.is_public is not None:
            update_data["isPublic"] = body.is_public
            if body.is_public and not row.shareToken:
                update_data["shareToken"] = secrets.token_urlsafe(12)
            elif not body.is_public:
                update_data["shareToken"] = None

        updated = await db.savedplaylist.update(
            where={"id": playlist_id},
            data=update_data,
        )
        return _row_to_response(updated)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Playlist] Update failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update playlist")


@router.delete("/playlist/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: str,
    token: str = Depends(oauth2_scheme),
):
    """Delete a playlist. Only the owner can delete."""
    db      = get_db()
    user_id = await _get_user_id(token)

    try:
        row = await db.savedplaylist.find_unique(where={"id": playlist_id})
        if not row:
            raise HTTPException(status_code=404, detail="Playlist not found")
        if row.userId != user_id:
            raise HTTPException(status_code=403, detail="Not your playlist")

        await db.savedplaylist.delete(where={"id": playlist_id})
        logger.info(f"[Playlist] Deleted '{row.name}' for user {user_id[:8]}...")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Playlist] Delete failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete playlist")


# ─── USER HISTORY ─────────────────────────────────────────────────────────────

@router.get("/user/history")
async def get_user_history(
    token: str = Depends(oauth2_scheme),
    limit: int = 20,
    offset: int = 0,
):
    """
    Returns the authenticated user's past vibe analyses (VibeRequest history).
    Each entry shows: prompt, dominant vibe, confidence, returned tracks, timestamp.
    Used to power the History drawer in the frontend.
    """
    db      = get_db()
    user_id = await _get_user_id(token)

    try:
        rows = await db.viberequest.find_many(
            where={"userId": user_id},
            order={"createdAt": "desc"},
            take=min(limit, 50),
            skip=offset,
        )
        total = await db.viberequest.count(where={"userId": user_id})

        history = []
        for r in rows:
            tracks = json.loads(r.returnedTracks) if r.returnedTracks else []
            history.append({
                "id":              r.id,
                "prompt":          r.promptText,
                "dominant_vibe":   r.dominantVibe,
                "secondary_vibe":  r.secondaryVibe,
                "confidence":      float(r.confidence) if r.confidence else 0.0,
                "bpm_range":       r.bpmRange,
                "detected_artist": r.detectedArtist,
                "language":        None,   # add language field to schema if needed
                "track_count":     len(tracks),
                "tracks":          tracks[:3],    # preview — first 3 only for compactness
                "used_fallback":   r.usedFallback,
                "created_at":      r.createdAt.isoformat(),
            })

        return {
            "history": history,
            "total":   total,
            "limit":   limit,
            "offset":  offset,
        }

    except Exception as e:
        logger.error(f"[History] Fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


@router.delete("/user/history/{request_id}", status_code=204)
async def delete_history_entry(
    request_id: str,
    token: str = Depends(oauth2_scheme),
):
    """Delete a single history entry. User must own it."""
    db      = get_db()
    user_id = await _get_user_id(token)

    try:
        row = await db.viberequest.find_unique(where={"id": request_id})
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        if row.userId != user_id:
            raise HTTPException(status_code=403, detail="Not your entry")

        await db.viberequest.delete(where={"id": request_id})
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[History] Delete failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete history entry")
