# VibeFinderAI Analytics - Quick Reference Card

## 📝 Copy-Paste Integration Snippets

### 1️⃣ Add to main.py (Top of file with imports)
```python
import time
from analytics import collector
from analytics_routes import router as analytics_router
```

### 2️⃣ Register Router (After `app = FastAPI()`)
```python
app.include_router(analytics_router)
```

### 3️⃣ Log Search Metric (In get_vibes endpoint)
```python
@app.post("/api/get_vibes")
async def get_vibes(request: VibeRequest, current_user: dict = Depends(get_current_user)):
    start_time = time.time()
    
    try:
        # ... existing vibe analysis code ...
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        collector.log_search(
            vibe_description=request.description,
            primary_vibe=primary_vibe,
            secondary_vibe=secondary_vibe,
            confidence=confidence_score,
            response_time_ms=elapsed_ms,
            nicheness=request.nicheness,
            language=request.language,
            track_count=len(results.tracks)
        )
        
        return {
            "status": "success",
            "primary_vibe": primary_vibe,
            "tracks": results.tracks
        }
    except Exception as e:
        collector.log_api_error("vibe_engine", str(type(e).__name__))
        raise
```

### 4️⃣ Log Feedback (In feedback endpoint)
```python
@app.post("/api/feedback")
async def submit_feedback(feedback: FeedbackRequest, current_user: dict = Depends(get_current_user)):
    # ... save to DB ...
    
    collector.log_feedback(feedback.track_id, feedback.is_positive)
    
    return {"status": "feedback_recorded"}
```

### 5️⃣ Frontend Engagement Tracking (In App.jsx)
```jsx
// Add this helper function
const trackEngagement = async (eventType) => {
  try {
    const url = buildApiUrl("/api/analytics/engagement");
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_type: eventType })
    });
  } catch (err) {
    console.error("Analytics error:", err);
  }
};

// Use in onClick handlers
onClick={() => {
  trackEngagement("preview_click");
  playPreview(track);
}}

onClick={() => {
  trackEngagement("spotify_click");
  window.location.href = spotifyUrl;
}}

onClick={() => {
  trackEngagement("playlist_save");
  savePlaylist();
}}

onClick={() => {
  trackEngagement("pro_mode");
  toggleProMode();
}}
```

### 6️⃣ Add Dashboard Route (In frontend App.jsx or router)
```jsx
import AnalyticsDashboard from "./AnalyticsDashboard.jsx";

// Add to your routing:
{
  path: "/admin/analytics",
  element: <AnalyticsDashboard />
}
```

---

## 🔗 API Endpoints Reference

### GET Endpoints (Read-Only)
```bash
# Main dashboard (for frontend)
GET /api/analytics/dashboard

# Complete summary (all metrics)
GET /api/analytics/summary

# Recent searches (last 50)
GET /api/analytics/searches?limit=50

# Vibe statistics
GET /api/analytics/vibes

# Language preferences
GET /api/analytics/languages

# Performance percentiles
GET /api/analytics/performance

# Engagement & feedback
GET /api/analytics/engagement

# Data quality metrics
GET /api/analytics/data-quality
```

### POST Endpoints (Write-Only)
```bash
# Backend logs a search
POST /api/analytics/search
{
  "vibe_description": "midnight driving",
  "primary_vibe": "chill",
  "secondary_vibe": "retro",
  "confidence": 0.87,
  "response_time_ms": 145.3,
  "nicheness": 0.65,
  "language": "en",
  "track_count": 10
}

# Log feedback rating
POST /api/analytics/feedback
{ "track_id": "spotify:track:xyz", "is_positive": true }

# Log UI engagement
POST /api/analytics/engagement
{ "event_type": "preview_click" }
# event_type: preview_click, spotify_click, pro_mode, playlist_save

# Log API error
POST /api/analytics/api-error
{ "api_name": "lastfm", "error_type": "timeout" }

# Log cache hit/miss
POST /api/analytics/cache-event
{ "is_hit": true }
```

---

## 📊 Metrics Summary

### Search Metrics
- `total_searches` - Cumulative count
- `top_vibes` - Dict of vibe → count
- `top_languages` - Dict of language → count
- `avg_nicheness` - 0-1 preference for obscure tracks
- `secondary_vibe_rate` - % of searches with 2+ vibes

### Engine Performance
- `avg_response_ms` - Mean latency
- `p95_response_ms` - 95th percentile
- `avg_confidence` - Mean confidence score (0-1)

### User Engagement
- `preview_clicks` - Preview button interactions
- `spotify_clicks` - Open in Spotify clicks
- `pro_mode_activations` - Pro Mode uses
- `playlist_saves` - Playlist persistence
- `top_overrides` - Most used Pro Mode features

### Feedback
- `thumbs_up` - Positive ratings
- `thumbs_down` - Negative ratings
- `positive_rate_pct` - % positive

### Data Quality
- `enrichment_completion_pct` - Metadata coverage 0-100%
- `missing_isrcs` - Tracks without cross-platform IDs
- `cache_hit_rate_pct` - Cache effectiveness
- `api_errors` - Dict of error → count

### Real-Time (1h)
- `active_users_1h` - Count of unique searches
- `trending_vibes_1h` - Dict of vibe → count

---

## 🧪 Testing Commands

### Test Health Check
```bash
cd backend
python health_check.py --all
```

### Test Analytics Endpoint
```bash
curl http://localhost:8000/api/analytics/summary | jq

# Pretty print specific metric
curl http://localhost:8000/api/analytics/vibes | jq '.data.vibes'
```

### Simulate Search
```bash
curl -X POST http://localhost:8000/api/analytics/search \
  -H "Content-Type: application/json" \
  -d '{
    "vibe_description": "chill",
    "primary_vibe": "chill",
    "secondary_vibe": null,
    "confidence": 0.85,
    "response_time_ms": 150,
    "nicheness": 0.5,
    "language": "en",
    "track_count": 10
  }'
```

---

## ✅ Verification Checklist

```
Backend Integration:
☐ analytics.py in backend/ directory
☐ analytics_routes.py in backend/ directory
☐ Import statements added to main.py
☐ analytics_router registered with FastAPI
☐ log_search() calls added to get_vibes
☐ log_feedback() calls added to feedback endpoint
☐ Restarted backend server

Frontend Integration:
☐ AnalyticsDashboard.jsx in frontend/src/
☐ trackEngagement() helper added
☐ Event tracking calls added to button handlers
☐ Dashboard route added (/admin/analytics)
☐ Restarted frontend dev server

Testing:
☐ curl /api/analytics/summary returns data
☐ Dashboard page loads at /admin/analytics
☐ Metrics update after test searches
☐ Refresh interval selector works
☐ Charts/cards render without errors
```

---

## 🎨 Dashboard URL

- **Development**: `http://localhost:5173/admin/analytics`
- **Production**: `https://vibefinderai.netlify.app/admin/analytics`

(Adjust port/domain as needed for your setup)

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `ANALYTICS.md` | Complete API & metrics reference |
| `ANALYTICS_INTEGRATION.md` | Detailed integration steps |
| `ANALYTICS_OVERVIEW.md` | Project overview & learning guide |
| `ANALYTICS_ARCHITECTURE.txt` | Data flow diagrams |
| `backend/health_check.py` | CLI diagnostics tool |

---

## 🚨 Troubleshooting

**Dashboard shows no data?**
→ Execute test searches and verify collector.log_search() is called

**404 /api/analytics/dashboard?**
→ Check that app.include_router(analytics_router) is in main.py

**CORS error?**
→ Ensure frontend is calling correct API URL (check buildApiUrl())

**High latency (>500ms)?**
→ Check vibe_engine performance, database queries

**Cache hit rate 0%?**
→ Caching logic may not be implemented yet

---

## 💡 Pro Tips

1. **Monitor in real-time**: Open dashboard while running batch tests
2. **Export metrics**: Use `GET /api/analytics/summary` for reports
3. **Health checks**: Run `python health_check.py` before deployments
4. **Trending analysis**: Check trending_vibes_1h for real-time insights
5. **Performance tuning**: Use p95 latency, not just average
6. **Feedback loop**: Use positive_rate_pct to measure recommendation quality

---

## 📞 Next Steps

1. **Read**: ANALYTICS_INTEGRATION.md for detailed steps
2. **Implement**: Copy snippets above into main.py
3. **Test**: Run health_check.py and access dashboard
4. **Monitor**: Use dashboard during development
5. **Optimize**: Based on metrics, identify bottlenecks
