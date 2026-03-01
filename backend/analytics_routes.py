"""
Analytics API Routes for VibeFinderAI
FastAPI endpoints for serving dashboard and analytics data
"""

from fastapi import APIRouter, HTTPException
from analytics import get_analytics_summary, get_dashboard_data, collector
import logging

logger = logging.getLogger("VibeFinderEngine")

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard():
    """
    GET /api/analytics/dashboard
    Returns lightweight, dashboard-formatted analytics data
    Includes live metrics, summary, and recent searches
    """
    try:
        data = get_dashboard_data()
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")


@router.get("/summary")
async def get_summary():
    """
    GET /api/analytics/summary
    Returns comprehensive analytics summary
    Individual metrics for all tracked dimensions
    """
    try:
        summary = get_analytics_summary()
        return {
            "status": "success",
            "data": summary
        }
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics summary")


@router.get("/searches")
async def get_recent_searches(limit: int = 50):
    """
    GET /api/analytics/searches?limit=50
    Returns recent search history with details
    """
    data = collector.search_history[-limit:]
    return {
        "status": "success",
        "count": len(data),
        "data": data
    }


@router.get("/vibes")
async def get_vibe_statistics():
    """
    GET /api/analytics/vibes
    Returns vibe category statistics (counts, percentages)
    """
    total = collector.total_searches or 1
    vibes = {
        vibe: {
            "count": count,
            "percentage": round(count / total * 100, 1)
        }
        for vibe, count in collector.vibe_counter.most_common()
    }
    return {
        "status": "success",
        "total_searches": collector.total_searches,
        "vibes": vibes
    }


@router.get("/languages")
async def get_language_statistics():
    """
    GET /api/analytics/languages
    Returns language preference statistics
    """
    total = collector.total_searches or 1
    languages = {
        lang: {
            "count": count,
            "percentage": round(count / total * 100, 1)
        }
        for lang, count in collector.language_counter.most_common()
    }
    return {
        "status": "success",
        "languages": languages
    }


@router.get("/performance")
async def get_performance_metrics():
    """
    GET /api/analytics/performance
    Returns detailed performance metrics (latency, confidence, etc)
    """
    response_times = collector.search_response_times
    confidence_scores = collector.confidence_scores
    
    if not response_times:
        return {
            "status": "success",
            "message": "No performance data yet",
            "data": {}
        }
    
    sorted_response_times = sorted(response_times)
    
    # Percentile calculations
    p50 = sorted_response_times[len(sorted_response_times) // 2]
    p75 = sorted_response_times[int(len(sorted_response_times) * 0.75)]
    p95 = sorted_response_times[int(len(sorted_response_times) * 0.95)]
    p99 = sorted_response_times[int(len(sorted_response_times) * 0.99)] if len(sorted_response_times) > 100 else p95
    
    avg_response = sum(response_times) / len(response_times)
    min_response = min(response_times)
    max_response = max(response_times)
    
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
    
    return {
        "status": "success",
        "latency_ms": {
            "min": round(min_response, 1),
            "avg": round(avg_response, 1),
            "p50": round(p50, 1),
            "p75": round(p75, 1),
            "p95": round(p95, 1),
            "p99": round(p99, 1),
            "max": round(max_response, 1)
        },
        "confidence": {
            "avg": round(avg_confidence, 3),
            "min": round(min(confidence_scores), 3) if confidence_scores else 0,
            "max": round(max(confidence_scores), 3) if confidence_scores else 1
        },
        "sample_count": len(response_times)
    }


@router.get("/engagement")
async def get_engagement_metrics():
    """
    GET /api/analytics/engagement
    Returns user engagement and interaction metrics
    """
    thumbs_up = collector.feedback_ratings.get("thumbs_up", 0)
    thumbs_down = collector.feedback_ratings.get("thumbs_down", 0)
    total_feedback = thumbs_up + thumbs_down
    
    return {
        "status": "success",
        "engagement": {
            "preview_clicks": collector.track_preview_clicks,
            "spotify_links_opened": collector.spotify_link_clicks,
            "pro_mode_activations": collector.pro_mode_activations,
            "playlist_saves": collector.playlist_saves,
            "ctr_preview": round(collector.track_preview_clicks / max(1, collector.total_searches) * 100, 1),
            "ctr_spotify": round(collector.spotify_link_clicks / max(1, collector.total_searches) * 100, 1)
        },
        "feedback": {
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "total": total_feedback,
            "positive_rate_pct": round(thumbs_up / max(1, total_feedback) * 100, 1)
        },
        "overrides": dict(collector.manual_override_uses.most_common(10))
    }


@router.get("/data-quality")
async def get_data_quality():
    """
    GET /api/analytics/data-quality
    Returns data enrichment and quality metrics
    """
    cache_total = collector.cache_hits + collector.cache_misses
    cache_hit_rate = (collector.cache_hits / cache_total * 100) if cache_total > 0 else 0
    
    return {
        "status": "success",
        "enrichment": {
            "completion_pct": collector.enrichment_completion_pct,
            "missing_isrcs": collector.missing_isrc_count
        },
        "cache": {
            "hits": collector.cache_hits,
            "misses": collector.cache_misses,
            "total_requests": cache_total,
            "hit_rate_pct": round(cache_hit_rate, 1)
        },
        "api_errors": dict(collector.api_errors.most_common(15)) if collector.api_errors else {}
    }


@router.post("/search")
async def log_search_event(
    vibe_description: str,
    primary_vibe: str,
    secondary_vibe: str = None,
    confidence: float = 0.5,
    response_time_ms: float = 0,
    nicheness: float = 0.5,
    language: str = "en",
    track_count: int = 10
):
    """
    POST /api/analytics/search
    Backend should call this after each successful vibe analysis
    """
    try:
        collector.log_search(
            vibe_description, primary_vibe, secondary_vibe,
            confidence, response_time_ms, nicheness, language, track_count
        )
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Error logging search: {e}")
        raise HTTPException(status_code=400, detail="Failed to log search")


@router.post("/feedback")
async def log_feedback_event(track_id: str, is_positive: bool):
    """
    POST /api/analytics/feedback
    Frontend should call when user rates a track
    """
    try:
        collector.log_feedback(track_id, is_positive)
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Error logging feedback: {e}")
        raise HTTPException(status_code=400, detail="Failed to log feedback")


@router.post("/engagement")
async def log_engagement_event(event_type: str):
    """
    POST /api/analytics/engagement
    Frontend logs UI interactions (preview_click, spotify_click, etc)
    """
    try:
        collector.log_engagement(event_type)
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Error logging engagement: {e}")
        raise HTTPException(status_code=400, detail="Failed to log engagement")


@router.post("/api-error")
async def log_api_error(api_name: str, error_type: str):
    """
    POST /api/analytics/api-error
    Backend logs external API failures
    """
    try:
        collector.log_api_error(api_name, error_type)
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Error logging API error: {e}")
        raise HTTPException(status_code=400, detail="Failed to log error")


@router.post("/cache-event")
async def log_cache_event(is_hit: bool):
    """
    POST /api/analytics/cache-event
    Backend logs cache hits/misses for performance optimization
    """
    try:
        collector.log_cache_event(is_hit)
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Error logging cache event: {e}")
        raise HTTPException(status_code=400, detail="Failed to log cache event")
