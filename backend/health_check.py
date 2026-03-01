#!/usr/bin/env python3
"""
VibeFinderAI Health Check & Status Monitor
Simple scripts for system health and diagnostics
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"
ENDPOINTS = {
    "health": f"{API_BASE}/api/health",
    "analytics": f"{API_BASE}/api/analytics/summary",
    "performance": f"{API_BASE}/api/analytics/performance",
    "data_quality": f"{API_BASE}/api/analytics/data-quality",
    "engagement": f"{API_BASE}/api/analytics/engagement",
}


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

def check_api_health() -> Dict[str, Any]:
    """
    Check if API is responding and databases are accessible.
    Returns status and response times.
    """
    print("\n🔍 Checking API health...\n")
    
    results = {}
    total_time = 0
    
    for name, url in ENDPOINTS.items():
        try:
            start = datetime.now()
            response = requests.get(url, timeout=5)
            elapsed = (datetime.now() - start).total_seconds() * 1000
            total_time += elapsed
            
            results[name] = {
                "status": "✓" if response.status_code == 200 else "✗",
                "code": response.status_code,
                "latency_ms": round(elapsed, 1),
                "ok": response.status_code == 200
            }
            
            # Print status
            status = "✓" if response.status_code == 200 else "✗"
            print(f"{status} {name:20} - {response.status_code} ({elapsed:.1f}ms)")
        
        except requests.exceptions.Timeout:
            results[name] = {"status": "⏱", "error": "Timeout", "ok": False}
            print(f"⏱ {name:20} - TIMEOUT")
        
        except Exception as e:
            results[name] = {"status": "✗", "error": str(e), "ok": False}
            print(f"✗ {name:20} - ERROR: {e}")
    
    all_ok = all(r.get("ok", False) for r in results.values())
    
    print(f"\n{'='*50}")
    print(f"Overall: {'HEALTHY ✓' if all_ok else 'ISSUES DETECTED ✗'}")
    print(f"Total response time: {total_time:.1f}ms")
    print(f"{'='*50}\n")
    
    return results


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_analytics_summary():
    """
    Pretty-print analytics summary in terminal.
    """
    print("\n📊 Analytics Summary\n")
    
    try:
        response = requests.get(f"{API_BASE}/api/analytics/summary", timeout=5)
        response.raise_for_status()
        data = response.json()["data"]
        
        # Search Metrics
        search = data.get("search_metrics", {})
        print("🎵 SEARCH METRICS")
        print(f"   Total searches: {search.get('total_searches', 0)}")
        print(f"   Avg confidence: {search.get('avg_confidence', 'N/A')}")
        print(f"   Secondary vibe rate: {search.get('secondary_vibe_rate', 0)}%")
        print(f"   Top vibe: {list(search.get('top_vibes', {}).items())[0] if search.get('top_vibes') else 'N/A'}")
        
        # Performance
        perf = data.get("engine_performance", {})
        print(f"\n⚙️  ENGINE PERFORMANCE")
        print(f"   Avg latency: {perf.get('avg_response_ms', 'N/A')}ms")
        print(f"   P95 latency: {perf.get('p95_response_ms', 'N/A')}ms")
        
        # Engagement
        engaged = data.get("user_engagement", {})
        print(f"\n👥 ENGAGEMENT")
        print(f"   Preview clicks: {engaged.get('preview_clicks', 0)}")
        print(f"   Spotify opens: {engaged.get('spotify_clicks', 0)}")
        print(f"   Pro Mode uses: {engaged.get('pro_mode_activations', 0)}")
        
        # Feedback
        feedback = data.get("feedback", {})
        print(f"\n💬 FEEDBACK")
        print(f"   👍 Thumbs up: {feedback.get('thumbs_up', 0)}")
        print(f"   👎 Thumbs down: {feedback.get('thumbs_down', 0)}")
        print(f"   Positive rate: {feedback.get('positive_rate_pct', 0)}%")
        
        # Data Quality
        quality = data.get("data_quality", {})
        print(f"\n🔍 DATA QUALITY")
        print(f"   Enrichment: {quality.get('enrichment_completion_pct', 0)}%")
        print(f"   Missing ISRCs: {quality.get('missing_isrcs', 0)}")
        print(f"   Cache hit rate: {quality.get('cache_hit_rate_pct', 0)}%")
        
        print(f"\n{'='*50}\n")
    
    except Exception as e:
        print(f"Error fetching analytics: {e}\n")


# ─────────────────────────────────────────────────────────────────────────────
# DETAILED DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────

def print_detailed_report():
    """
    Print detailed diagnostic report (good for debugging).
    """
    print("\n📋 DETAILED DIAGNOSTICS\n")
    
    try:
        # Performance percentiles
        perf_response = requests.get(f"{API_BASE}/api/analytics/performance", timeout=5)
        perf_response.raise_for_status()
        perf = perf_response.json()["latency_ms"]
        
        print("Response Time Percentiles:")
        for key in ["min", "p50", "p75", "p95", "p99", "max"]:
            print(f"   {key:>4}: {perf.get(key, 'N/A')}ms")
        
        # Data quality details
        dq_response = requests.get(f"{API_BASE}/api/analytics/data-quality", timeout=5)
        dq_response.raise_for_status()
        dq = dq_response.json()
        
        print(f"\nCache Performance:")
        print(f"   Hits: {dq['cache']['hits']}")
        print(f"   Misses: {dq['cache']['misses']}")
        print(f"   Hit Rate: {dq['cache']['hit_rate_pct']}%")
        
        if dq.get("api_errors"):
            print(f"\nAPI Errors (Top 5):")
            for error, count in list(dq["api_errors"].items())[:5]:
                print(f"   {error}: {count}")
    
    except Exception as e:
        print(f"Error: {e}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VibeFinderAI Health Check")
    parser.add_argument("--summary", action="store_true", help="Show analytics summary")
    parser.add_argument("--detailed", action="store_true", help="Show detailed diagnostics")
    parser.add_argument("--health", action="store_true", help="Check API health")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    
    args = parser.parse_args()
    
    if args.all or (not args.summary and not args.detailed and not args.health):
        check_api_health()
        print_analytics_summary()
        print_detailed_report()
    else:
        if args.health:
            check_api_health()
        if args.summary:
            print_analytics_summary()
        if args.detailed:
            print_detailed_report()
