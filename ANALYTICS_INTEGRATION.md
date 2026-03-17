# VibeFinderAI Analytics Integration — Current Status

✅ **FULLY INTEGRATED** — All analytics endpoints are live and operational.

## Current Integration

Analytics have been successfully integrated into the application:

### Backend ✅
- `core/analytics.py` — Metrics collection and in-memory storage
- `routes/analytics_routes.py` — API endpoints for dashboard and exports
- `routes/metrics_auth.py` — Authentication via passphrase → 7-day JWT token

### Frontend ✅
- `src/AnalyticsDashboard.jsx` — Real-time visualization of metrics
- Dashboard accessible via passphrase authentication

### Database ✅
- Prisma schema includes tables for metrics tracking
- Automatic data persistence

---

## Available Endpoints

### Authentication
```bash
POST /api/metrics/auth
Body: { "passphrase": "your_metrics_passphrase" }
Returns: { "token": "jwt_token", "expires_in_days": 7 }
```

### Dashboard & Metrics (require metrics token)
```bash
GET /api/analytics/dashboard         # Main dashboard data
GET /api/analytics/live              # Live metrics stream
GET /api/analytics/vibes             # Vibe statistics
GET /api/analytics/export            # Full export
```

### Usage

1. **Get Metrics Token:**
   ```bash
   curl -X POST http://localhost:8000/api/metrics/auth \
     -H "Content-Type: application/json" \
     -d '{"passphrase":"YOUR_METRICS_PASSPHRASE"}'
   ```

2. **Query Metrics (with token):**
   ```bash
   curl -X GET http://localhost:8000/api/analytics/dashboard \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
   ```

3. **Frontend Access:**
   - Visit the app and navigate to metrics/analytics section
   - Enter passphrase when prompted
   - Token auto-refreshes every 6.5 days

---

## What's Tracked

### Search Metrics
- Vibe descriptions and classifications
- Primary/secondary vibe detection
- Confidence scores
- Response times (latency)
- Track count per search
- Language selections
- Nicheness preferences

### User Engagement
- Preview button clicks
- Play button interactions
- Playlist saves
- Service connections
- Pro Mode activations

### Feedback Data
- Thumbs up/down ratings
- Track-level satisfaction
- Position in playlist (when rated)

### System Performance
- Average latency (ms)
- P95, P99 percentiles
- API error rates by service
- Cache hit rates

---

## Key Implementation Notes

### Authentication
- Passphrase-based access (not user OAuth)
- JWT token valid for 7 days
- Constant-time HMAC comparison prevents brute-force
- 1.5-second failure delay on wrong passphrase

### Security
- Metrics endpoints protected by metrics token (separate from user auth)
- Passphrase should be kept secret (set in `.env` → `METRICS_PASSPHRASE`)
- All metrics are opt-in and anonymized

### Performance
- In-memory metrics storage (no DB hits for analytics queries)
- Automatic cleanup of old data
- Real-time streaming of live metrics

### Graceful Fallback
- If `METRICS_PASSPHRASE` not set, metrics auth disabled
- All other endpoints continue working
- Analytics collection continues regardless

---

## Configuration

Set in `.env`:
```bash
METRICS_PASSPHRASE=your_secret_passphrase
```

The passphrase should be:
- Strong (12+ characters)
- Not shared publicly
- Rotated periodically
- Different from API keys

---

## Testing

```bash
# 1. Get token
curl -X POST http://localhost:8000/api/metrics/auth \
  -H "Content-Type: application/json" \
  -d '{"passphrase":"your_metrics_passphrase"}'

# 2. Use token to query
TOKEN="..."
curl -X GET http://localhost:8000/api/analytics/dashboard \
  -H "Authorization: Bearer $TOKEN"

# 3. Check live metrics
curl -X GET http://localhost:8000/api/analytics/live \
  -H "Authorization: Bearer $TOKEN"
```

---

## Related Files

- [ANALYTICS.md](ANALYTICS.md) — Detailed metrics reference
- [ANALYTICS_OVERVIEW.md](ANALYTICS_OVERVIEW.md) — High-level architecture
- `backend/routes/metrics_auth.py` — Token authentication
- `backend/routes/analytics_routes.py` — Endpoint definitions
- `frontend/src/AnalyticsDashboard.jsx` — Frontend visualization
    
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
