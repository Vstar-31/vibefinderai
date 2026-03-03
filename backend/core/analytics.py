"""
VibeFinderAI Analytics Module
Tracks vibe engine performance, user engagement, API metrics, and data quality.
"""

import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger("VibeFinderAnalytics")

# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY METRICS STORE
# (For production, migrate to Redis or TimescaleDB)
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsCollector:
    """Collects real-time metrics for the vibe engine and user interactions."""
    
    def __init__(self):
        # Search metrics
        self.total_searches = 0
        self.vibe_counter = Counter()  # Which vibes users search for most
        self.language_counter = Counter()  # Language filter usage
        self.nicheness_values = []  # Track nicheness knob usage patterns
        
        # Engine performance
        self.search_response_times = []  # Latency tracking
        self.confidence_scores = []  # Distribution of AI confidence
        self.secondary_vibe_triggers = 0  # How often secondary vibes detected
        
        # Track quality
        self.search_history = []  # Last N searches (for trending)
        self.feedback_ratings = Counter()  # Thumbs up/down
        self.track_preview_clicks = 0
        self.spotify_link_clicks = 0
        
        # Data quality
        self.missing_isrc_count = 0
        self.enrichment_completion_pct = 0
        self.api_errors = Counter()  # API error types
        self.cache_hits = 0
        self.cache_misses = 0
        
        # User behavior
        self.unique_session_count = 0
        self.playlist_saves = 0
        self.pro_mode_activations = 0
        self.manual_override_uses = Counter()  # Which overrides used most
        
        # Real-time activity (last 1 hour rolling window)
        self.active_searches_1h = []
        
    def log_search(self, vibe_description: str, primary_vibe: str, secondary_vibe: Optional[str],
                   confidence: float, response_time_ms: float, nicheness: float = 0.5, 
                   language: str = "en", track_count: int = 10):
        """Log a new vibe search."""
        self.total_searches += 1
        self.vibe_counter[primary_vibe] += 1
        if secondary_vibe:
            self.secondary_vibe_triggers += 1
        
        self.language_counter[language] += 1
        self.nicheness_values.append(nicheness)
        self.search_response_times.append(response_time_ms)
        self.confidence_scores.append(confidence)
        
        # Add to history (keep last 1000)
        self.search_history.append({
            "timestamp": datetime.now().isoformat(),
            "vibe": primary_vibe,
            "secondary": secondary_vibe,
            "confidence": confidence,
            "response_ms": response_time_ms,
            "nicheness": nicheness,
            "language": language,
            "track_count": track_count
        })
        if len(self.search_history) > 1000:
            self.search_history = self.search_history[-1000:]
        
        # Rolling window (1 hour)
        self.active_searches_1h.append({
            "time": datetime.now(),
            "vibe": primary_vibe
        })
        hourago = datetime.now() - timedelta(hours=1)
        self.active_searches_1h = [s for s in self.active_searches_1h if s["time"] > hourago]
        
        logger.info(f"Search logged: {primary_vibe} (confidence: {confidence:.2f}, latency: {response_time_ms:.0f}ms)")
    
    def log_feedback(self, track_id: str, is_positive: bool):
        """Log user feedback on a track recommendation."""
        rating = "thumbs_up" if is_positive else "thumbs_down"
        self.feedback_ratings[rating] += 1
        logger.info(f"Feedback: {rating} for track {track_id}")
    
    def log_engagement(self, event_type: str):
        """Log UI engagement events."""
        if event_type == "preview_click":
            self.track_preview_clicks += 1
        elif event_type == "spotify_click":
            self.spotify_link_clicks += 1
        elif event_type == "pro_mode":
            self.pro_mode_activations += 1
        elif event_type == "playlist_save":
            self.playlist_saves += 1
        logger.info(f"Engagement: {event_type}")
    
    def log_override(self, override_type: str):
        """Log Pro Mode manual overrides."""
        self.manual_override_uses[override_type] += 1
        logger.info(f"Override used: {override_type}")
    
    def log_api_error(self, api_name: str, error_type: str):
        """Log API errors."""
        key = f"{api_name}:{error_type}"
        self.api_errors[key] += 1
        logger.warning(f"API Error: {key}")
    
    def log_cache_event(self, is_hit: bool):
        """Log cache hit/miss."""
        if is_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def set_enrichment_status(self, completion_pct: float, missing_isrc: int = 0):
        """Update data enrichment metrics."""
        self.enrichment_completion_pct = completion_pct
        self.missing_isrc_count = missing_isrc
        logger.info(f"Enrichment status: {completion_pct:.1f}%, Missing ISRCs: {missing_isrc}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a comprehensive analytics summary."""
        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / cache_total * 100) if cache_total > 0 else 0
        
        response_times = self.search_response_times
        avg_response_ms = sum(response_times) / len(response_times) if response_times else 0
        p95_response_ms = sorted(response_times)[int(len(response_times) * 0.95)] if len(response_times) > 20 else avg_response_ms
        
        confidence_avg = sum(self.confidence_scores) / len(self.confidence_scores) if self.confidence_scores else 0
        nicheness_avg = sum(self.nicheness_values) / len(self.nicheness_values) if self.nicheness_values else 0.5
        
        thumbs_up = self.feedback_ratings.get("thumbs_up", 0)
        thumbs_down = self.feedback_ratings.get("thumbs_down", 0)
        feedback_total = thumbs_up + thumbs_down
        positive_rate = (thumbs_up / feedback_total * 100) if feedback_total > 0 else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "search_metrics": {
                "total_searches": self.total_searches,
                "top_vibes": dict(self.vibe_counter.most_common(10)),
                "top_languages": dict(self.language_counter.most_common(5)),
                "avg_nicheness": round(nicheness_avg, 2),
                "secondary_vibe_rate": round(self.secondary_vibe_triggers / max(1, self.total_searches) * 100, 1)
            },
            "engine_performance": {
                "avg_response_ms": round(avg_response_ms, 1),
                "p95_response_ms": round(p95_response_ms, 1),
                "avg_confidence": round(confidence_avg, 3),
                "total_searches_tracked": len(self.search_response_times)
            },
            "user_engagement": {
                "preview_clicks": self.track_preview_clicks,
                "spotify_clicks": self.spotify_link_clicks,
                "pro_mode_activations": self.pro_mode_activations,
                "playlist_saves": self.playlist_saves,
                "top_overrides": dict(self.manual_override_uses.most_common(5)) if self.manual_override_uses else {}
            },
            "feedback": {
                "total_feedback": feedback_total,
                "thumbs_up": thumbs_up,
                "thumbs_down": thumbs_down,
                "positive_rate_pct": round(positive_rate, 1)
            },
            "data_quality": {
                "enrichment_completion_pct": self.enrichment_completion_pct,
                "missing_isrcs": self.missing_isrc_count,
                "cache_hit_rate_pct": round(cache_hit_rate, 1),
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses
            },
            "api_errors": dict(self.api_errors.most_common(10)) if self.api_errors else {},
            "trending_vibes_1h": dict(Counter([s["vibe"] for s in self.active_searches_1h]).most_common(5))
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get lightweight data formatted for dashboard display."""
        summary = self.get_summary()
        return {
            "live_metric": {
                "active_users_1h": len(self.active_searches_1h),
                "searches_this_hour": len(self.active_searches_1h),
                "avg_response_ms": summary["engine_performance"]["avg_response_ms"]
            },
            "summary": summary,
            "recent_searches": self.search_history[-50:]  # Last 50 searches
        }


# Global collector instance
collector = AnalyticsCollector()


def get_analytics_summary() -> Dict[str, Any]:
    """Export analytics summary."""
    return collector.get_summary()


def get_dashboard_data() -> Dict[str, Any]:
    """Export dashboard-formatted data."""
    return collector.get_dashboard_data()
