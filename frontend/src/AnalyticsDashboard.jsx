import { useState, useEffect } from "react";

export default function AnalyticsDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(5000); // 5s

  const API_BASE_URL = import.meta.env.VITE_API_URL || '';
  
  const buildApiUrl = (path) => {
    if (API_BASE_URL) return `${API_BASE_URL}${path}`;
    return path;
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(buildApiUrl("/api/analytics/dashboard"));
        if (!response.ok) throw new Error("Failed to fetch analytics");
        const result = await response.json();
        setData(result);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  if (loading) return <div style={styles.container}><p>Loading analytics...</p></div>;
  if (error) return <div style={styles.container}><p style={{ color: "red" }}>Error: {error}</p></div>;
  if (!data) return <div style={styles.container}><p>No data available</p></div>;

  const summary = data.summary || {};
  const live = data.live_metric || {};

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1>⚡ VibeFinderAI Analytics Dashboard</h1>
        <p>Real-time engine & user metrics</p>
      </header>

      {/* LIVE METRICS */}
      <section style={styles.section}>
        <h2>🔴 LIVE METRICS</h2>
        <div style={styles.gridLive}>
          <Card title="Active Users (1h)" value={live.active_users_1h || 0} />
          <Card title="Searches (1h)" value={live.searches_this_hour || 0} />
          <Card title="Avg Response" value={`${live.avg_response_ms?.toFixed(1) || 0}ms`} />
        </div>
      </section>

      {/* SEARCH METRICS */}
      <section style={styles.section}>
        <h2>🎵 SEARCH METRICS</h2>
        <div style={styles.grid}>
          <Card title="Total Searches" value={summary.search_metrics?.total_searches || 0} />
          <Card title="Avg Confidence" value={`${(summary.engine_performance?.avg_confidence || 0).toFixed(3)}`} />
          <Card title="Secondary Vibe Rate" value={`${summary.search_metrics?.secondary_vibe_rate || 0}%`} />
          <Card title="Avg Nicheness" value={`${summary.search_metrics?.avg_nicheness || 0.5}`} />
        </div>
      </section>

      {/* ENGINE PERFORMANCE */}
      <section style={styles.section}>
        <h2>⚙️ ENGINE PERFORMANCE</h2>
        <div style={styles.grid}>
          <Card title="P95 Latency" value={`${summary.engine_performance?.p95_response_ms?.toFixed(1) || 0}ms`} />
          <Card title="Avg Latency" value={`${summary.engine_performance?.avg_response_ms?.toFixed(1) || 0}ms`} />
          <Card title="Searches Tracked" value={summary.engine_performance?.total_searches_tracked || 0} />
        </div>
      </section>

      {/* TOP VIBES & LANGUAGES */}
      <section style={styles.section}>
        <h2>📊 TOP VIBES</h2>
        <div style={styles.chartContainer}>
          {Object.entries(summary.search_metrics?.top_vibes || {}).map(([vibe, count]) => (
            <div key={vibe} style={styles.chartBar}>
              <span style={styles.barLabel}>{vibe}</span>
              <div style={{ ...styles.bar, width: `${(count / Object.values(summary.search_metrics?.top_vibes || {})[0] || 1) * 100}%` }}>
                <span style={styles.barValue}>{count}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* USER ENGAGEMENT */}
      <section style={styles.section}>
        <h2>👥 USER ENGAGEMENT</h2>
        <div style={styles.grid}>
          <Card title="Preview Clicks" value={summary.user_engagement?.preview_clicks || 0} />
          <Card title="Spotify Links" value={summary.user_engagement?.spotify_clicks || 0} />
          <Card title="Pro Mode Uses" value={summary.user_engagement?.pro_mode_activations || 0} />
          <Card title="Playlists Saved" value={summary.user_engagement?.playlist_saves || 0} />
        </div>
      </section>

      {/* FEEDBACK ANALYSIS */}
      <section style={styles.section}>
        <h2>💬 FEEDBACK</h2>
        <div style={styles.grid}>
          <Card title="👍 Thumbs Up" value={summary.feedback?.thumbs_up || 0} color="#4ade80" />
          <Card title="👎 Thumbs Down" value={summary.feedback?.thumbs_down || 0} color="#ef4444" />
          <Card title="Positive Rate" value={`${summary.feedback?.positive_rate_pct || 0}%`} />
          <Card title="Total Feedback" value={summary.feedback?.total_feedback || 0} />
        </div>
      </section>

      {/* DATA QUALITY */}
      <section style={styles.section}>
        <h2>🔍 DATA QUALITY</h2>
        <div style={styles.grid}>
          <Card 
            title="Enrichment" 
            value={`${summary.data_quality?.enrichment_completion_pct || 0}%`}
            color={summary.data_quality?.enrichment_completion_pct > 90 ? "#4ade80" : "#f59e0b"}
          />
          <Card title="Missing ISRCs" value={summary.data_quality?.missing_isrcs || 0} color="#ef4444" />
          <Card title="Cache Hit Rate" value={`${summary.data_quality?.cache_hit_rate_pct || 0}%`} />
          <Card title="Cache Hits" value={summary.data_quality?.cache_hits || 0} />
        </div>
      </section>

      {/* API ERRORS */}
      {Object.keys(summary.api_errors || {}).length > 0 && (
        <section style={styles.section}>
          <h2>⚠️ API ERRORS</h2>
          <div style={styles.errorList}>
            {Object.entries(summary.api_errors || {}).map(([error, count]) => (
              <div key={error} style={styles.errorItem}>
                <span>{error}</span>
                <span style={{ color: "#ef4444", fontWeight: "bold" }}>{count}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TRENDING VIBES (1H) */}
      {Object.keys(summary.trending_vibes_1h || {}).length > 0 && (
        <section style={styles.section}>
          <h2>🔥 TRENDING (LAST HOUR)</h2>
          <div style={styles.trendingContainer}>
            {Object.entries(summary.trending_vibes_1h || {})
              .sort(([, a], [, b]) => b - a)
              .map(([vibe, count], idx) => (
                <div key={vibe} style={styles.trendingItem}>
                  <span style={styles.rank}>#{idx + 1}</span>
                  <span>{vibe}</span>
                  <span style={styles.trendCount}>{count} searches</span>
                </div>
              ))}
          </div>
        </section>
      )}

      {/* FOOTER */}
      <footer style={styles.footer}>
        <p>Last updated: {new Date(summary.timestamp).toLocaleTimeString()}</p>
        <label style={styles.refreshLabel}>
          Refresh interval:
          <select 
            value={refreshInterval} 
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            style={styles.selectInput}
          >
            <option value={2000}>2 seconds</option>
            <option value={5000}>5 seconds</option>
            <option value={10000}>10 seconds</option>
            <option value={30000}>30 seconds</option>
          </select>
        </label>
      </footer>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────── CARD COMPONENT */
function Card({ title, value, color = "#3b82f6" }) {
  return (
    <div style={{ ...styles.card, borderLeftColor: color }}>
      <div style={styles.cardTitle}>{title}</div>
      <div style={{ ...styles.cardValue, color }}>{value}</div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────── STYLES */
const styles = {
  container: {
    padding: "2rem",
    maxWidth: "1400px",
    margin: "0 auto",
    background: "#0f172a",
    color: "#e2e8f0",
    fontFamily: "'Courier New', monospace",
    minHeight: "100vh",
  },
  header: {
    marginBottom: "2rem",
    paddingBottom: "1rem",
    borderBottom: "2px solid #1e293b",
  },
  header_h1: {
    margin: 0,
    fontSize: "2rem",
  },
  section: {
    marginBottom: "2rem",
    padding: "1.5rem",
    background: "#1e293b",
    borderRadius: "8px",
    border: "1px solid #334155",
  },
  sectionH2: {
    margin: "0 0 1rem 0",
    fontSize: "1.3rem",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "1rem",
  },
  gridLive: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "1rem",
  },
  card: {
    padding: "1.5rem",
    background: "#0f172a",
    borderLeft: "4px solid #3b82f6",
    borderRadius: "4px",
    border: "1px solid #334155",
  },
  cardTitle: {
    fontSize: "0.9rem",
    textTransform: "uppercase",
    opacity: 0.7,
    marginBottom: "0.5rem",
    letterSpacing: "0.05em",
  },
  cardValue: {
    fontSize: "1.8rem",
    fontWeight: "bold",
  },
  chartContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  chartBar: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
  },
  barLabel: {
    width: "120px",
    textAlign: "right",
    fontSize: "0.9rem",
    fontWeight: "bold",
  },
  bar: {
    height: "28px",
    background: "linear-gradient(90deg, #3b82f6, #8b5cf6)",
    borderRadius: "4px",
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-end",
    paddingRight: "0.75rem",
    minWidth: "100px",
  },
  barValue: {
    fontSize: "0.85rem",
    fontWeight: "bold",
    color: "#fff",
  },
  errorList: {
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
  },
  errorItem: {
    display: "flex",
    justifyContent: "space-between",
    padding: "0.75rem",
    background: "#0f172a",
    borderLeft: "3px solid #ef4444",
    borderRadius: "4px",
    fontSize: "0.9rem",
  },
  trendingContainer: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "0.75rem",
  },
  trendingItem: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    padding: "0.75rem 1rem",
    background: "#0f172a",
    borderLeft: "3px solid #f59e0b",
    borderRadius: "4px",
    fontWeight: "bold",
  },
  rank: {
    fontSize: "1.2rem",
    color: "#f59e0b",
  },
  trendCount: {
    marginLeft: "auto",
    fontSize: "0.85rem",
    opacity: 0.7,
  },
  footer: {
    marginTop: "2rem",
    paddingTop: "1rem",
    borderTop: "1px solid #334155",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    fontSize: "0.9rem",
    opacity: 0.7,
  },
  refreshLabel: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    cursor: "pointer",
  },
  selectInput: {
    padding: "0.25rem 0.5rem",
    background: "#0f172a",
    color: "#e2e8f0",
    border: "1px solid #334155",
    borderRadius: "4px",
    fontFamily: "'Courier New', monospace",
    cursor: "pointer",
  },
};
