# VibeFinderAI Analytics & Informatics System

Comprehensive real-time analytics and monitoring dashboard for tracking engine performance, user engagement, and data quality.

## Overview

The analytics system provides three layers:

1. **Backend Analytics Collector** (`backend/analytics.py`) - In-memory metrics collection
2. **API Routes** (`backend/analytics_routes.py`) - RESTful endpoints for data export
3. **Frontend Dashboard** (`frontend/src/AnalyticsDashboard.jsx`) - Real-time visualization

## Core Metrics Tracked

### 🎵 Search Metrics
- **Total searches**: Cumulative count of vibe analyses
- **Top vibes**: Most frequently searched vibe categories
- **Top languages**: Language filter preferences
- **Average nicheness**: User preference for obscure vs. mainstream tracks
- **Secondary vibe detection rate**: % of searches detecting multiple vibes

### ⚙️ Engine Performance
- **Average latency**: Mean response time (ms)
- **P95 latency**: 95th percentile response time
- **Average confidence**: AI confidence in vibe classification (0-1)
- **Sample count**: Number of searches tracked

### 👥 User Engagement
- **Preview clicks**: Track preview button interactions
- **Spotify link clicks**: Deep link engagement to Spotify
- **Pro Mode activations**: Advanced controls usage
- **Playlist saves**: Playlist persistence interactions
- **Manual overrides**: Which Pro Mode features used most

### 💬 Feedback Analysis
- **Thumbs up/down**: Recommendation quality ratings
- **Positive rate %**: Percentage of positive feedback
- **Total feedback events**: Cumulative feedback count

### 🔍 Data Quality
- **Enrichment completion %**: Metadata enrichment progress (0-100%)
- **Missing ISRCs**: Tracks without cross-platform identifiers
- **Cache hit rate %**: Cache effectiveness for API calls
- **API errors**: Failures by service (Last.fm, Spotify, etc.)

### 🔥 Real-Time Trending
- **Active users (1h)**: Users in rolling 1-hour window
- **Trending vibes**: Popular vibes in the last hour
- **Live searches**: Current search activity

## API Endpoints

### Dashboard & Summary
```
GET /api/analytics/dashboard
Returns lightweight dashboard data with live metrics

GET /api/analytics/summary
Returns comprehensive metrics summary (all tracked dimensions)
```

### Detailed Metrics
```
GET /api/analytics/searches?limit=50
Returns recent search history

GET /api/analytics/vibes
Vibe category statistics with percentages

GET /api/analytics/languages
Language preference breakdown

GET /api/analytics/performance
Detailed latency percentiles (p50, p75, p95, p99)

GET /api/analytics/engagement
User engagement & interaction metrics

GET /api/analytics/data-quality
Data enrichment and quality metrics
```

### Event Logging (from Backend)
```
POST /api/analytics/search
Log a search: vibe_description, primary_vibe, confidence, response_time_ms, etc.

POST /api/analytics/feedback
Log feedback: track_id, is_positive

POST /api/analytics/engagement
Log engagement: event_type (preview_click, spotify_click, pro_mode, playlist_save)

POST /api/analytics/api-error
Log external API error: api_name, error_type

POST /api/analytics/cache-event
Log cache hit/miss: is_hit (bool)
```

## Integration Guide

### 1. Import Analytics in main.py

```python
# In backend/main.py
from analytics import collector
from analytics_routes import router as analytics_router

# Add to FastAPI app
app.include_router(analytics_router)
```

### 2. Log Search Events

After successful vibe analysis, call:
```python
collector.log_search(
    vibe_description="midnight driving feeling",
    primary_vibe="chill",
    secondary_vibe="retro",
    confidence=0.87,
    response_time_ms=145.3,
    nicheness=0.65,
    language="en",
    track_count=10
)
```

### 3. Log User Interactions

From the backend when handling feedback/engagement:
```python
# Track feedback
collector.log_feedback(track_id="spotify:track:xyz", is_positive=True)

# Track engagement
collector.log_engagement("preview_click")
collector.log_engagement("spotify_click")
collector.log_engagement("pro_mode")
collector.log_engagement("playlist_save")
```

### 4. Track Data Quality

In enrichment scripts:
```python
# After enrichment batch completes
collector.set_enrichment_status(
    completion_pct=94.5,
    missing_isrc=1247
)
```

### 5. Add Dashboard to Frontend

Import and use in a new admin route:
```jsx
// frontend/src/pages/AdminDashboard.jsx
import AnalyticsDashboard from "../AnalyticsDashboard.jsx";

export default function AdminDashboard() {
  return <AnalyticsDashboard />;
}
```

Add to root routing (e.g., `/admin/analytics`)

## Dashboard Features

### Real-Time Updates
- Configurable refresh interval (2s, 5s, 10s, 30s)
- Live metric cards showing current activity
- Trending vibes (last hour)

### Data Visualization
- Bar charts for top vibes by search count
- Card-based KPI display
- Percentile latency breakdown
- Feedback sentiment analysis
- Error distribution

### Dark Theme
- Studio aesthetic matching app design
- Retro-futuristic color scheme
- High contrast for readability
- Monospace fonts

## Example Metrics Output

```json
{
  "timestamp": "2026-03-02T14:32:45.123456",
  "search_metrics": {
    "total_searches": 1847,
    "top_vibes": {
      "chill": 312,
      "melancholic": 198,
      "hype": 187,
      "ambient": 156
    },
    "top_languages": {
      "en": 1204,
      "es": 389,
      "hi": 254
    },
    "avg_nicheness": 0.58,
    "secondary_vibe_rate": 28.4
  },
  "engine_performance": {
    "avg_response_ms": 142.7,
    "p95_response_ms": 287.3,
    "avg_confidence": 0.823,
    "total_searches_tracked": 1847
  },
  "user_engagement": {
    "preview_clicks": 3421,
    "spotify_clicks": 2847,
    "pro_mode_activations": 234,
    "playlist_saves": 156,
    "top_overrides": {
      "artist_bypass": 87,
      "genre_bypass": 43
    }
  },
  "feedback": {
    "thumbs_up": 1289,
    "thumbs_down": 194,
    "total": 1483,
    "positive_rate_pct": 86.9
  },
  "data_quality": {
    "enrichment_completion_pct": 94.2,
    "missing_isrcs": 1847,
    "cache_hit_rate_pct": 73.4,
    "cache_hits": 14234,
    "cache_misses": 5162
  },
  "trending_vibes_1h": {
    "hyperpop": 34,
    "ambient": 29,
    "indie_rock": 23
  }
}
```

## Production Considerations

### In-Memory Storage
Current implementation uses Python in-memory storage. For production:
- ✅ Great for < 10k searches/day
- ⚠️ Data lost on restart
- Consider migration to:
  - **Redis**: Fast, distributed caching
  - **TimescaleDB**: Time-series metrics database
  - **InfluxDB**: Purpose-built metrics DB

### Data Retention
Implement retention policies:
- Keep detailed searches: 24 hours
- Keep summaries: 30 days
- Archive historical data to cold storage

### Sampling
For high-traffic scenarios:
- Sample 10% of searches for detailed tracking
- Aggregate counts separately
- Trade accuracy for performance

## Future Enhancements

- **Custom dashboards**: User-created metric views
- **Alerting**: Notifications for anomalies
- **Machine learning**: Trend prediction, anomaly detection
- **Export**: CSV/JSON export for external analysis
- **Comparison**: Day-over-day, week-over-week metrics
- **Funnel analysis**: Track user journey through vibe → results → playlist
- **A/B testing**: Experiment tracking integration
- **Error replay**: Detailed drill-down into failure cases
