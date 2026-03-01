"""
VibeFinderAI Analytics Integration Checklist
Step-by-step guide to add analytics to main.py
"""

# ============================================================================
# STEP 1: Add imports at the top of main.py
# ============================================================================

# Add these lines near the top, after existing imports:

from analytics import collector
from analytics_routes import router as analytics_router

# ============================================================================
# STEP 2: Register analytics routes with FastAPI app
# ============================================================================

# Add this line after app = FastAPI() definition:

app.include_router(analytics_router)

# ============================================================================
# STEP 3: Log search events in get_vibes endpoint
# ============================================================================

# In the get_vibes endpoint, after successful vibe analysis, add:

import time

@app.post("/api/get_vibes")
async def get_vibes(request: VibeRequest, current_user: dict = Depends(get_current_user)):
    """Main vibe analysis endpoint."""
    
    start_time = time.time()  # Measure latency
    
    try:
        # ... existing vibe analysis code ...
        
        # After getting results and before returning:
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Log the search
        collector.log_search(
            vibe_description=request.description,
            primary_vibe=primary_vibe,  # from vibe_engine
            secondary_vibe=secondary_vibe,  # could be None
            confidence=confidence_score,  # AI confidence (0-1)
            response_time_ms=elapsed_ms,
            nicheness=request.nicheness,  # 0-1
            language=request.language,
            track_count=len(results.tracks)
        )
        
        return {
            "status": "success",
            "primary_vibe": primary_vibe,
            "secondary_vibe": secondary_vibe,
            "confidence": confidence_score,
            "tracks": results.tracks,
            "neural_match": results.keywords
        }
    
    except Exception as e:
        # Log API errors
        collector.log_api_error("vibe_engine", str(type(e).__name__))
        raise


# ============================================================================
# STEP 4: Log feedback in rating endpoint
# ============================================================================

@app.post("/api/feedback")
async def submit_feedback(feedback: FeedbackRequest, current_user: dict = Depends(get_current_user)):
    """User rates a recommendation."""
    
    try:
        # ... save feedback to DB ...
        
        # Log to analytics
        collector.log_feedback(feedback.track_id, feedback.is_positive)
        
        return {"status": "feedback_recorded"}
    
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise


# ============================================================================
# STEP 5: Log UI engagement from frontend
# ============================================================================

# Frontend calls POST /api/analytics/engagement when user:
# - Clicks "Preview" button
# - Clicks "Open in Spotify" button  
# - Activates Pro Mode
# - Saves a playlist

# The analytics route handler already exists, just need frontend to call:

# In frontend (App.jsx):
async function trackEngagement(eventType) {
  const url = buildApiUrl("/api/analytics/engagement");
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_type: eventType })
  });
}

// Then call in handlers:
onClick={() => {
  trackEngagement("preview_click");
  playPreview(track);
}}


# ============================================================================
# STEP 6: Log data enrichment progress
# ============================================================================

# In enrichment scripts (enrich_tracks.py, enrich_artists.py):

from analytics import collector

def enrichment_complete():
    """Called after enrichment batch completes."""
    
    # Query database for completion metrics
    total_tracks = db.query("SELECT COUNT(*) FROM tracks").scalar()
    with_isrc = db.query("SELECT COUNT(*) FROM tracks WHERE isrc IS NOT NULL").scalar()
    missing_isrc = total_tracks - with_isrc
    completion_pct = (with_isrc / total_tracks * 100) if total_tracks > 0 else 0
    
    # Log to analytics
    collector.set_enrichment_status(
        completion_pct=completion_pct,
        missing_isrc=missing_isrc
    )


# ============================================================================
# STEP 7: Log API errors and cache events (optional but recommended)
# ============================================================================

# When calling external APIs, log errors:

def fetch_lastfm_metadata(track_id):
    try:
        response = requests.get(LASTFM_API_URL, params={"track_id": track_id})
        response.raise_for_status()
        collector.log_cache_event(is_hit=True)  # or False for miss
        return response.json()
    except Exception as e:
        collector.log_api_error("lastfm", str(type(e).__name__))
        raise


# ============================================================================
# STEP 8: Add admin dashboard route (optional)
# ============================================================================

# In frontend, add a new route protected by admin auth:

# frontend/src/pages/AdminAnalytics.jsx
import AnalyticsDashboard from "../AnalyticsDashboard.jsx";

export default function AdminAnalytics() {
  // Add auth check here
  return (
    <div>
      <h1>Admin Analytics</h1>
      <AnalyticsDashboard />
    </div>
  );
}


# ============================================================================
# VERIFICATION CHECKLIST
# ============================================================================

# ✓ Import analytics and router in main.py
# ✓ Register analytics_router with FastAPI app
# ✓ Add latency tracking to get_vibes endpoint
# ✓ Call collector.log_search() after vibe analysis
# ✓ Call collector.log_feedback() in feedback endpoint
# ✓ Frontend calls POST /api/analytics/engagement on button clicks
# ✓ Enrichment scripts call collector.set_enrichment_status()
# ✓ API error handlers call collector.log_api_error()
# ✓ Test GET /api/analytics/dashboard returns data
# ✓ Add AnalyticsDashboard to frontend routes
# ✓ Verify dashboard displays metrics


# ============================================================================
# TESTING
# ============================================================================

# Test locally:
# 1. Start backend: python main.py
# 2. Trigger some vibe searches via frontend
# 3. Check: curl http://localhost:8000/api/analytics/summary | jq
# 4. View dashboard: http://localhost:5173/admin/analytics


# ============================================================================
# EXPECTED OUTPUT (after integration)
# ============================================================================

# curl http://localhost:8000/api/analytics/dashboard | jq

# {
#   "status": "success",
#   "data": {
#     "live_metric": {
#       "active_users_1h": 5,
#       "searches_this_hour": 12,
#       "avg_response_ms": 145.2
#     },
#     "summary": {
#       "timestamp": "2026-03-02T14:32:45.123456",
#       "search_metrics": {
#         "total_searches": 47,
#         "top_vibes": { "chill": 12, "hype": 8, "melancholic": 7 },
#         ...
#       },
#       ...
#     },
#     "recent_searches": [...]
#   }
# }
