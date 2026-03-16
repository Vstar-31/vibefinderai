"""
analytics_routes.py
───────────────────
VibeFinderAI — Analytics API Routes (Real DB Data)
Place in: backend/routes/analytics_routes.py

All metrics are derived live from the Prisma DB. Designed to be fast
enough for the 5s polling interval in AnalyticsDashboard.jsx.

Endpoints:
  GET /api/analytics/dashboard  — Full dashboard snapshot
  GET /api/analytics/live       — Just the live metrics (1h window)
  GET /api/analytics/export     — CSV dump for offline analysis

Register in main.py:
  from routes.analytics_routes import router as analytics_router, set_db as analytics_set_db
  analytics_set_db(db)
  app.include_router(analytics_router, prefix="/api")
"""

import json
import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse

try:
    from routes.metrics_auth import require_metrics_token
    _METRICS_AUTH_AVAILABLE = True
except ImportError:
    _METRICS_AUTH_AVAILABLE = False
    require_metrics_token = None
import jwt
from prisma import Prisma

logger = logging.getLogger("VibeFinderEngine")

router = APIRouter()

SECRET_KEY    = os.getenv("SECRET_KEY", "super_secret_student_budget_key_dont_leak_this")
ALGORITHM     = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)

_db: Optional[Prisma] = None

def set_db(instance: Prisma):
    global _db
    _db = instance

def get_db() -> Prisma:
    if _db is None:
        raise RuntimeError("DB not initialised")
    return _db


async def _require_admin(token: Optional[str]) -> bool:
    """
    Simple admin gate: check token is valid AND user has admin flag.
    For now (student project), any valid token can view analytics.
    Swap to a role check when you add admin roles to the User model.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── DASHBOARD ENDPOINT ───────────────────────────────────────────────────────

@router.get("/analytics/dashboard")
async def get_analytics_dashboard(
    _: None = Depends(require_metrics_token) if _METRICS_AUTH_AVAILABLE else None,
):
    """
    Full analytics snapshot. Polled every 5s by AnalyticsDashboard.jsx.
    All numbers are derived from real DB data.
    """
    db = get_db()

    now      = datetime.now(timezone.utc)
    one_hour = now - timedelta(hours=1)
    one_day  = now - timedelta(hours=24)

    try:
        # ── Parallel DB queries ──────────────────────────────────────────────
        all_requests = await db.viberequest.find_many(
            order={"createdAt": "desc"},
            take=5000,   # Cap for performance — latest 5k requests
        )
        recent_requests = [r for r in all_requests if r.createdAt >= one_hour]
        daily_requests  = [r for r in all_requests if r.createdAt >= one_day]

        all_feedback    = await db.trackfeedback.find_many(
            order={"createdAt": "desc"},
            take=10000,
        )
        recent_feedback = [f for f in all_feedback if f.createdAt >= one_hour]

        # ── User metrics ─────────────────────────────────────────────────────
        total_users = await db.user.count()
        # Active: users who made a request in the last hour
        active_user_ids = {r.userId for r in recent_requests if r.userId}

        # ── Search metrics ────────────────────────────────────────────────────
        total_searches = len(all_requests)

        vibe_counter: Counter = Counter()
        for r in all_requests:
            if r.dominantVibe:
                vibe_counter[r.dominantVibe] += 1

        secondary_count = sum(1 for r in all_requests if r.secondaryVibe)
        secondary_rate  = round(secondary_count / max(total_searches, 1) * 100, 1)

        # Average nicheness (stored in knob state we log in DB)
        # If nicheness not in schema, default to 50
        niches = []
        for r in all_requests:
            try:
                v = getattr(r, "nicheness", None)
                if v is not None:
                    niches.append(float(v))
            except Exception:
                pass
        avg_nicheness = round(sum(niches) / len(niches), 2) if niches else 0.5

        # ── Engine performance ────────────────────────────────────────────────
        # Response times — stored in VibeRequest.responseMs if available,
        # otherwise estimated from createdAt - (next request start, approximate)
        # We read from DB field if it exists, fall back to null
        response_times = []
        for r in all_requests:
            try:
                ms = getattr(r, "responseMs", None)
                if ms is not None:
                    response_times.append(float(ms))
            except Exception:
                pass

        if response_times:
            sorted_rt   = sorted(response_times)
            avg_resp_ms = round(sum(response_times) / len(response_times), 1)
            p95_idx     = int(len(sorted_rt) * 0.95)
            p95_resp_ms = sorted_rt[min(p95_idx, len(sorted_rt) - 1)]
        else:
            avg_resp_ms = 0.0
            p95_resp_ms = 0.0

        fallback_count  = sum(1 for r in all_requests if getattr(r, "usedFallback", False))
        semantic_count  = sum(1 for r in all_requests if getattr(r, "usedSemantic", False))
        avg_confidence  = (
            sum(float(r.confidence) for r in all_requests if r.confidence)
            / max(total_searches, 1)
        )

        # ── Feedback metrics ──────────────────────────────────────────────────
        thumbs_up   = sum(1 for f in all_feedback if f.signal == 1)
        thumbs_down = sum(1 for f in all_feedback if f.signal == -1)
        total_fb    = len(all_feedback)
        pos_rate    = round(thumbs_up / max(total_fb, 1) * 100, 1)

        # ── User engagement (all time) ────────────────────────────────────────
        # These require specific tracking fields. We compute what we can from
        # the data we definitely have, and default the rest to 0 gracefully.
        preview_clicks = 0   # Would need a /api/track/preview-click event endpoint
        spotify_clicks = 0   # Would need a /api/track/spotify-click event endpoint
        pro_mode_uses  = sum(
            1 for r in all_requests
            if getattr(r, "overrideGenre", None) or getattr(r, "overrideArtist", None)
        )

        try:
            playlist_saves = await db.savedplaylist.count()
        except Exception:
            playlist_saves = 0

        # ── Data quality ──────────────────────────────────────────────────────
        try:
            total_cache_rows = await db.trackfeaturecache.count()
            enriched_rows    = await db.trackfeaturecache.count(
                where={"energy": {"not": None}}
            )
            enrichment_pct = round(enriched_rows / max(total_cache_rows, 1) * 100, 1)

            missing_isrcs = await db.trackfeaturecache.count(
                where={"isrc": None}
            )
        except Exception:
            total_cache_rows = 0
            enrichment_pct   = 0.0
            missing_isrcs    = 0

        # Cache hit rate (approximated: requests where fallback=False → likely cache hit)
        cache_hits = total_searches - fallback_count
        cache_hit_pct = round(cache_hits / max(total_searches, 1) * 100, 1)

        # ── API errors (parse from DB if error field exists) ──────────────────
        api_errors: dict = {}
        # Add real error tracking when you add an ErrorLog table

        # ── Trending vibes (last 1h) ──────────────────────────────────────────
        trending: Counter = Counter()
        for r in recent_requests:
            if r.dominantVibe:
                trending[r.dominantVibe] += 1

        # ── Assemble response ─────────────────────────────────────────────────
        return {
            "summary": {
                "timestamp": now.isoformat(),
                "search_metrics": {
                    "total_searches":       total_searches,
                    "secondary_vibe_rate":  secondary_rate,
                    "avg_nicheness":        avg_nicheness,
                    "fallback_rate_pct":    round(fallback_count / max(total_searches, 1) * 100, 1),
                    "semantic_rate_pct":    round(semantic_count / max(total_searches, 1) * 100, 1),
                    "top_vibes":            dict(vibe_counter.most_common(10)),
                },
                "engine_performance": {
                    "avg_confidence":          round(avg_confidence, 3),
                    "avg_response_ms":         avg_resp_ms,
                    "p95_response_ms":         p95_resp_ms,
                    "total_searches_tracked":  total_searches,
                    "fallback_searches":       fallback_count,
                },
                "user_engagement": {
                    "total_users":         total_users,
                    "preview_clicks":      preview_clicks,
                    "spotify_clicks":      spotify_clicks,
                    "pro_mode_activations": pro_mode_uses,
                    "playlist_saves":      playlist_saves,
                },
                "feedback": {
                    "thumbs_up":        thumbs_up,
                    "thumbs_down":      thumbs_down,
                    "total_feedback":   total_fb,
                    "positive_rate_pct": pos_rate,
                },
                "data_quality": {
                    "total_cached_tracks":       total_cache_rows,
                    "enrichment_completion_pct": enrichment_pct,
                    "missing_isrcs":             missing_isrcs,
                    "cache_hits":                cache_hits,
                    "cache_hit_rate_pct":        cache_hit_pct,
                },
                "api_errors":        api_errors,
                "trending_vibes_1h": dict(trending.most_common(8)),
            },
            "live_metric": {
                "active_users_1h":    len(active_user_ids),
                "searches_this_hour": len(recent_requests),
                "feedback_this_hour": len(recent_feedback),
                "avg_response_ms":    avg_resp_ms,   # reuse — no live timing available
            },
        }

    except Exception as e:
        logger.error(f"[Analytics] Dashboard build failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analytics engine error")


# ─── LIVE METRICS ONLY (lightweight poll) ────────────────────────────────────

@router.get("/analytics/live")
async def get_live_metrics(
    _: None = Depends(require_metrics_token) if _METRICS_AUTH_AVAILABLE else None,
):
    """
    Lightweight endpoint for the live metrics bar.
    Returns only the last-hour window — much cheaper than full dashboard.
    """
    db = get_db()

    now      = datetime.now(timezone.utc)
    one_hour = now - timedelta(hours=1)

    try:
        recent_requests = await db.viberequest.find_many(
            where={"createdAt": {"gte": one_hour}},
        )
        recent_feedback = await db.trackfeedback.find_many(
            where={"createdAt": {"gte": one_hour}},
        )

        active_users = {r.userId for r in recent_requests if r.userId}
        vibe_counter = Counter(r.dominantVibe for r in recent_requests if r.dominantVibe)

        return {
            "active_users_1h":    len(active_users),
            "searches_this_hour": len(recent_requests),
            "feedback_this_hour": len(recent_feedback),
            "top_vibe_1h":        vibe_counter.most_common(1)[0][0] if vibe_counter else None,
            "timestamp":          now.isoformat(),
        }
    except Exception as e:
        logger.error(f"[Analytics] Live metrics failed: {e}")
        raise HTTPException(status_code=500, detail="Live metrics error")


# ─── VIBE BREAKDOWN ──────────────────────────────────────────────────────────

@router.get("/analytics/vibes")
async def get_vibe_breakdown(
    days: int = 7,
    _: None = Depends(require_metrics_token) if _METRICS_AUTH_AVAILABLE else None,
):
    """
    Returns vibe distribution over the last N days.
    Used to power the Top Vibes chart and can power a future trend graph.
    """
    db = get_db()

    since = datetime.now(timezone.utc) - timedelta(days=min(days, 90))

    try:
        rows = await db.viberequest.find_many(
            where={"createdAt": {"gte": since}},
        )

        dominant_counter  = Counter(r.dominantVibe for r in rows if r.dominantVibe)
        secondary_counter = Counter(r.secondaryVibe for r in rows if r.secondaryVibe)
        language_counter  = Counter()  # language not stored in VibeRequest yet — placeholder

        # Daily breakdown
        daily: dict[str, Counter] = {}
        for r in rows:
            day_key = r.createdAt.strftime("%Y-%m-%d")
            daily.setdefault(day_key, Counter())[r.dominantVibe or "unknown"] += 1

        return {
            "period_days":    days,
            "total_searches": len(rows),
            "dominant_vibes": dict(dominant_counter.most_common(20)),
            "secondary_vibes": dict(secondary_counter.most_common(10)),
            "daily_breakdown": {
                day: dict(counter.most_common(5))
                for day, counter in sorted(daily.items())[-days:]
            },
        }
    except Exception as e:
        logger.error(f"[Analytics] Vibe breakdown failed: {e}")
        raise HTTPException(status_code=500, detail="Vibe breakdown error")


# ─── CSV EXPORT ───────────────────────────────────────────────────────────────

@router.get("/analytics/export")
async def export_analytics_csv(
    _: None = Depends(require_metrics_token) if _METRICS_AUTH_AVAILABLE else None,
):
    """
    Export full VibeRequest history as CSV for offline analysis.
    Useful for QA analysis scripts (qa_analyzer.py, advanced_analyzer.py).
    """
    db = get_db()

    try:
        rows = await db.viberequest.find_many(
            order={"createdAt": "desc"},
            take=10000,
        )

        def _generate():
            header = "id,prompt,dominant_vibe,secondary_vibe,confidence,bpm_range,detected_artist,track_count,used_fallback,created_at\n"
            yield header
            for r in rows:
                try:
                    tracks = json.loads(r.returnedTracks) if r.returnedTracks else []
                except Exception:
                    tracks = []
                # Escape commas in prompt text
                prompt_safe = (r.promptText or "").replace('"', '""')
                line = (
                    f'"{r.id}",'
                    f'"{prompt_safe}",'
                    f'"{r.dominantVibe or ""}",'
                    f'"{r.secondaryVibe or ""}",'
                    f'{float(r.confidence) if r.confidence else 0.0:.3f},'
                    f'"{r.bpmRange or ""}",'
                    f'"{r.detectedArtist or ""}",'
                    f'{len(tracks)},'
                    f'{r.usedFallback},'
                    f'"{r.createdAt.isoformat()}"\n'
                )
                yield line

        return StreamingResponse(
            _generate(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=vibefinder_analytics.csv"},
        )
    except Exception as e:
        logger.error(f"[Analytics] CSV export failed: {e}")
        raise HTTPException(status_code=500, detail="Export failed")
