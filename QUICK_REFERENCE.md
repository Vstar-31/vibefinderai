# VibeFinderAI — Quick Reference & Status

## 🎵 Current Feature Status

### Backend Services (✅ All Connected & Working)
| Service | Purpose | OAuth | Status |
|---------|---------|-------|--------|
| **Last.fm** | Metadata, artist data, ISRC mapping | ✅ | 🟢 Connected |
| **Spotify** | Track discovery, deep links, previews | ✅ | 🟢 Connected |
| **YouTube** | Full-length song embeds, OAuth playlists | ✅ | 🟢 Connected + Retry Logic |
| **Deezer** | Track enrichment, metadata fallback | ✅ | 🟢 Connected |
| **SoundCloud** | Music discovery, previews | ✅ | 🟢 Connected |
| **iTunes** | 30-second preview clips | ❌ | 🟢 Active |
| **Gemini AI** | NLP enhancement for prompts | ✅ | 🟢 Active (graceful fallback) |

---

## 🔌 Critical API Endpoints

### Vibe Analysis
```
POST /api/vibe/analyze
Body: { text, artist_focus, nicheness, bpm_focus, language, track_count }
Returns: { primary_vibe, secondary_vibe, tracks[], request_id }
```

### Music Services
```
GET  /api/spotify/auth        # Spotify OAuth callback
GET  /api/youtube/auth        # YouTube OAuth callback & playlist creation
POST /api/lastfm/proxy        # CORS-safe Last.fm API proxy
GET  /api/services/status     # Check which services are connected
```

### Playlist Management
```
POST /api/playlist/create     # Create a named playlist
GET  /api/playlist/{id}       # Get playlist details
POST /api/playlist/{id}/save  # Save to Spotify/YouTube/etc
```

### Metrics & Analytics
```
GET /api/analytics/dashboard  # Dashboard data (requires metrics token)
GET /api/analytics/live       # Live metrics stream
GET /api/analytics/vibes      # Vibe statistics
GET /api/analytics/export     # Full metrics export
POST /api/metrics/auth        # Exchange passphrase for 7-day JWT metrics token
```

### User Actions
```
POST /api/feedback                # Submit thumbs up/down on track
GET  /api/user/taste              # Get user's saved preferences
POST /auth/register, /auth/token  # Authentication
```

---

## 🎙️ Audio Playback System

### Three Audio Modes:
1. **Play All** — Queues all results with embeds in MusicPlayer (full-length via YouTube)
2. **Play** *(YouTube connected only)* — Single track in MusicPlayer for full playback
3. **Preview** — Inline 30-sec iTunes clip (no player needed)

### PlaylistPlayer vs MusicPlayer
- **MusicPlayer** (`frontend/src/MusicPlayer.jsx`) — Floating component, full-length track playback
- **Inline Preview** — HTML5 audio element for 30-sec clips

---

## 🔑 Environment Variables (.env)

Required for backend operation:
```bash
# Database
DATABASE_URL=postgresql://supabase_url
PRISMA_DATABASE_URL=postgresql://supabase_url

# OAuth Keys & Secrets
LASTFM_API_KEY=***
LASTFM_SHARED_SECRET=***
SPOTIFY_CLIENT_ID=***
SPOTIFY_CLIENT_SECRET=***
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/spotify/auth

YOUTUBE_CLIENT_ID=***
YOUTUBE_CLIENT_SECRET=***
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/youtube/auth

DEEZER_APP_ID=***
DEEZER_APP_SECRET=***

SOUNDCLOUD_CLIENT_ID=***

# AI & NLP
GEMINI_API_KEY=***

# JWT Secrets
SECRET_KEY=your_super_secret_key_change_in_production
ALGORITHM=HS256

# Metrics Authentication
METRICS_PASSPHRASE=your_metrics_passphrase

# Frontend URL
FRONTEND_URL_PROD=https://vibefinderai.netlify.app

# Server Config
CORS_ORIGINS=http://localhost:5173,https://vibefinderai.netlify.app
```

---

## 🚀 Development Setup

### Backend (Python)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev  # Runs on http://localhost:5173
```

### Database Migrations (Prisma)
```bash
cd backend
npx prisma migrate dev --name "description"
npx prisma studio  # Open GUI DB browser
```

---

## 💾 Current Database Schema

**Key Tables:**
- `User` — Authentication and profile
- `VibeRequest` — Search history
- `TrackFeedback` — Like/dislike ratings
- `Playlist` — Saved playlists
- `PlaylistTrack` — Playlist membership
- `TrackFeatureCache` — Pre-computed audio features
- `ArtistDirectory` — Artist metadata
- `LastFmArtistLinks` — Cross-reference to Last.fm

---

## ✅ Production Deployment Checklist

- [ ] Backend running on Render (auto-deploy from `main` branch)
- [ ] Frontend deployed on Netlify (auto-deploy from `main` branch)
- [ ] All environment variables set in Render dashboard
- [ ] CORS hardcoded fallback to Netlify production URL
- [ ] Database backups enabled in Supabase
- [ ] SSL/TLS certificates auto-renewed
- [ ] API rate limiting (slowapi) active
- [ ] Metrics authentication passphrase set
- [ ] All service OAuth clients updated with production URLs

---

## 📊 Key Changes (Latest Session)

✅ **Fixed** — All music service OAuth connections (Last.fm, Spotify, YouTube, Deezer, SoundCloud)
✅ **Added** — `/api/lastfm/proxy` endpoint for CORS-safe Last.fm access
✅ **Implemented** — YouTube playlist creation with exponential backoff retry logic (up to 4 attempts per video on 409 errors)
✅ **Split** — Audio playback into Play All (embeds), Play (single track), and Preview (30-sec clip)
✅ **Added** — Metrics authentication framework (passphrase → 7-day JWT token)
✅ **Fixed** — CORS configuration for production Netlify deployment
✅ **Added** — YouTube search result cache (7-day TTL)

---

## 🔗 Quick API Test Commands

```bash
# Test vibe analysis
curl -X POST http://localhost:8000/api/vibe/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"late night drive","artist_focus":50,"nicheness":50,"bpm_focus":50,"language":"en","track_count":10}'

# Get metrics (need passphrase-derived token)
curl -X GET http://localhost:8000/api/analytics/dashboard \
  -H "Authorization: Bearer YOUR_METRICS_TOKEN"

# Test Last.fm proxy
curl "http://localhost:8000/api/lastfm/proxy?method=artist.search&artist=Dua%20Lipa"

# Check service status
curl http://localhost:8000/api/services/status

# Health check
curl http://localhost:8000/health
```

---

## 📁 Important File Locations

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app entry point, route registration, CORS setup |
| `backend/routes/services_routes.py` | OAuth integrations (Last.fm, YouTube, Spotify, etc.) |
| `backend/routes/metrics_auth.py` | Metrics authentication (passphrase → JWT) |
| `backend/routes/analytics_routes.py` | Analytics endpoints (dashboard, live, vibes) |
| `backend/core/vibe_engine.py` | Core NLP vibe analysis engine |
| `backend/core/gemini_vibe.py` | Gemini AI enhancement (graceful fallback) |
| `backend/analyzers/semantic_search.py` | Semantic ranking (graceful fallback if torch unavailable) |
| `frontend/src/App.jsx` | Main React app, search interface, results display |
| `frontend/src/MusicPlayer.jsx` | Full-length track player component |
| `backend/schema.prisma` | Database schema definition |

---

## 🧪 Testing & Debugging

### Run Backend Tests
```bash
cd backend
python testing/health_check.py
python testing/batch_tester.py
python testing/batch_tester_v10k_2.py  # Large-scale test
```

### View Database
```bash
cd backend
npx prisma studio
```

### Check Logs
```bash
tail -f backend/vibefinder_engine.log  # Backend logs
# Frontend logs in browser console (F12)
```

### Monitor Services
```bash
# Last.fm connection
curl "http://localhost:8000/api/lastfm/proxy?method=artist.search&artist=Test"

# YouTube playlist creation test
# (Requires YouTube OAuth token)
curl -X POST http://localhost:8000/api/youtube/create_playlist \
  -H "Authorization: Bearer YOUR_YOUTUBE_TOKEN"
```

---

## 🐛 Common Issues & Fixes

| Issue | Solution |
|-------|----------|
| `.env` not loading | Verify `dotenv_path` in main.py points to correct location, ensure `load_dotenv()` called BEFORE route imports |
| Service OAuth 503 | Check if `.env` variables are set, verify OAuth redirect URIs match config |
| YouTube 409 errors | Retry logic is active; check backend logs for "YT add video got 409 — retrying" messages |
| CORS errors on frontend | Check `CORS_ORIGINS` env var includes your frontend URL; verify production URL in main.py |
| Metrics auth fails | Confirm `METRICS_PASSPHRASE` is set in `.env`, ensure token hasn't expired (7 days) |
| Import errors | Verify all modules in `backend/` have `__init__.py` files |

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
