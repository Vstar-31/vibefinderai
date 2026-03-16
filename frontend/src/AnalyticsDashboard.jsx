import { useState, useEffect, useCallback } from "react";

/* ─── Token helpers ──────────────────────────────────────────────
   Token is stored in localStorage as JSON { token, exp }.
   exp is a Unix ms timestamp (matches what the backend returns as
   expires_at). Token is scoped to "metrics" type only.
──────────────────────────────────────────────────────────────── */
const STORAGE_KEY = "vf_mt";   // deliberately terse

function loadStoredToken() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const { token, exp } = JSON.parse(raw);
    if (!token || Date.now() >= exp) { localStorage.removeItem(STORAGE_KEY); return null; }
    return token;
  } catch { return null; }
}

function saveToken(token, exp) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, exp })); } catch {}
}

function clearToken() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
}

/* ─── API helpers ────────────────────────────────────────────── */
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const buildApiUrl  = (path) => API_BASE_URL ? `${API_BASE_URL}${path}` : path;

/* ═══════════════════════════════════════════════════════════════
   PASSPHRASE GATE
═══════════════════════════════════════════════════════════════ */
function PassphraseGate({ onSuccess }) {
  const [value,   setValue]   = useState("");
  const [status,  setStatus]  = useState("idle"); // idle | checking | denied
  const [shake,   setShake]   = useState(false);

  const submit = async () => {
    if (!value.trim() || status === "checking") return;
    setStatus("checking");

    try {
      const res = await fetch(buildApiUrl("/api/metrics/auth"), {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ passphrase: value }),
      });

      if (!res.ok) {
        // Use the artificial server-side delay — don't add more on top
        setStatus("denied");
        setValue("");
        setShake(true);
        setTimeout(() => { setShake(false); setStatus("idle"); }, 1800);
        return;
      }

      const { token, expires_at } = await res.json();
      saveToken(token, expires_at);
      onSuccess(token);
    } catch {
      setStatus("denied");
      setValue("");
      setShake(true);
      setTimeout(() => { setShake(false); setStatus("idle"); }, 1800);
    }
  };

  const handleKey = (e) => { if (e.key === "Enter") submit(); };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 100,
      background: "#0a0500",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "'Courier New', monospace",
    }}>
      {/* Subtle grid texture */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "linear-gradient(rgba(120,80,20,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(120,80,20,0.04) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
      }} />

      <div style={{
        position: "relative", zIndex: 1,
        width: "min(400px, 92vw)",
        padding: "40px 36px",
        background: "#0f1623",
        border: "1px solid #1e293b",
        borderRadius: 8,
        animation: shake ? "gateShake 0.4s ease" : "none",
      }}>
        <style>{`
          @keyframes gateShake {
            0%,100% { transform: translateX(0); }
            20%     { transform: translateX(-8px); }
            40%     { transform: translateX( 8px); }
            60%     { transform: translateX(-5px); }
            80%     { transform: translateX( 5px); }
          }
        `}</style>

        {/* Header */}
        <div style={{ marginBottom: "1.8rem", textAlign: "center" }}>
          <div style={{ fontSize: "1.6rem", marginBottom: 8 }}>⚡</div>
          <div style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#e2e8f0", letterSpacing: "0.04em" }}>
            VibeFinderAI Metrics
          </div>
          <div style={{ fontSize: "0.75rem", color: "#475569", marginTop: 4, letterSpacing: "0.08em", textTransform: "uppercase" }}>
            Restricted access
          </div>
        </div>

        {/* Input */}
        <div style={{ marginBottom: "1.2rem" }}>
          <input
            type="password"
            autoFocus
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Access key"
            disabled={status === "checking"}
            style={{
              width: "100%", boxSizing: "border-box",
              padding: "11px 14px",
              background: "#0f172a",
              border: `1px solid ${status === "denied" ? "#ef4444" : "#334155"}`,
              borderRadius: 4,
              color: "#e2e8f0",
              fontFamily: "'Courier New', monospace",
              fontSize: "0.9rem",
              outline: "none",
              letterSpacing: "0.04em",
              transition: "border-color 0.2s",
            }}
          />
          {status === "denied" && (
            <div style={{ marginTop: 6, fontSize: "0.75rem", color: "#ef4444", letterSpacing: "0.04em" }}>
              Access denied.
            </div>
          )}
        </div>

        {/* Submit */}
        <button
          onClick={submit}
          disabled={!value.trim() || status === "checking"}
          style={{
            width: "100%", padding: "11px",
            background: status === "checking" ? "#1e293b" : "#3b82f6",
            border: "none", borderRadius: 4,
            color: status === "checking" ? "#475569" : "#fff",
            fontFamily: "'Courier New', monospace",
            fontSize: "0.85rem", fontWeight: "bold",
            letterSpacing: "0.08em", textTransform: "uppercase",
            cursor: status === "checking" || !value.trim() ? "not-allowed" : "pointer",
            transition: "background 0.2s",
          }}
        >
          {status === "checking" ? "Verifying..." : "Authenticate"}
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN DASHBOARD
═══════════════════════════════════════════════════════════════ */
export default function AnalyticsDashboard() {
  const [metricsToken,     setMetricsToken]     = useState(loadStoredToken);
  const [data,             setData]             = useState(null);
  const [loading,          setLoading]          = useState(false);
  const [error,            setError]            = useState(null);
  const [refreshInterval,  setRefreshInterval]  = useState(5000);

  /* ── Authenticated fetch ── */
  const authFetch = useCallback(async (path) => {
    const res = await fetch(buildApiUrl(path), {
      headers: { "Authorization": `Bearer ${metricsToken}` },
    });
    if (res.status === 401) {
      clearToken();
      setMetricsToken(null);
      throw new Error("Token expired — re-authenticate");
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }, [metricsToken]);

  /* ── Poll dashboard data ── */
  useEffect(() => {
    if (!metricsToken) return;

    const fetchData = async () => {
      try {
        setLoading(true);
        const result = await authFetch("/api/analytics/dashboard");
        setData(result);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const iv = setInterval(fetchData, refreshInterval);
    return () => clearInterval(iv);
  }, [metricsToken, refreshInterval, authFetch]);

  /* ── Gate: not authenticated yet ── */
  if (!metricsToken) {
    return <PassphraseGate onSuccess={(token) => setMetricsToken(token)} />;
  }

  /* ── Loading / error states ── */
  if (loading && !data) return (
    <div style={styles.container}>
      <p style={{ color: "#64748b" }}>Loading analytics...</p>
    </div>
  );
  if (error && !data) return (
    <div style={styles.container}>
      <p style={{ color: "#ef4444" }}>Error: {error}</p>
      <button
        onClick={() => { clearToken(); setMetricsToken(null); }}
        style={{ marginTop: 12, padding: "8px 16px", background: "#1e293b", border: "1px solid #334155", borderRadius: 4, color: "#e2e8f0", cursor: "pointer", fontFamily: "'Courier New', monospace", fontSize: "0.8rem" }}
      >Re-authenticate</button>
    </div>
  );
  if (!data) return <div style={styles.container}><p style={{ color: "#64748b" }}>No data available</p></div>;

  const summary = data.summary || {};
  const live    = data.live_metric || {};

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: "1.6rem", color: "#e2e8f0" }}>⚡ VibeFinderAI Analytics</h1>
            <p style={{ margin: "4px 0 0", color: "#475569", fontSize: "0.85rem" }}>Real-time engine &amp; user metrics</p>
          </div>
          <button
            onClick={() => { clearToken(); setMetricsToken(null); }}
            style={{ padding: "6px 14px", background: "transparent", border: "1px solid #334155", borderRadius: 4, color: "#475569", cursor: "pointer", fontFamily: "'Courier New', monospace", fontSize: "0.75rem", letterSpacing: "0.06em" }}
          >Lock</button>
        </div>
      </header>

      {/* LIVE */}
      <section style={styles.section}>
        <h2 style={styles.sectionH2}>🔴 LIVE</h2>
        <div style={styles.gridLive}>
          <Card title="Active Users (1h)"  value={live.active_users_1h || 0} />
          <Card title="Searches (1h)"      value={live.searches_this_hour || 0} />
          <Card title="Avg Response"       value={`${live.avg_response_ms?.toFixed(1) || 0}ms`} />
        </div>
      </section>

      {/* SEARCH */}
      <section style={styles.section}>
        <h2 style={styles.sectionH2}>🎵 SEARCH METRICS</h2>
        <div style={styles.grid}>
          <Card title="Total Searches"       value={summary.search_metrics?.total_searches || 0} />
          <Card title="Avg Confidence"       value={(summary.engine_performance?.avg_confidence || 0).toFixed(3)} />
          <Card title="Secondary Vibe Rate"  value={`${summary.search_metrics?.secondary_vibe_rate || 0}%`} />
          <Card title="Avg Nicheness"        value={`${summary.search_metrics?.avg_nicheness || 0.5}`} />
        </div>
      </section>

      {/* ENGINE */}
      <section style={styles.section}>
        <h2 style={styles.sectionH2}>⚙️ ENGINE PERFORMANCE</h2>
        <div style={styles.grid}>
          <Card title="P95 Latency"          value={`${summary.engine_performance?.p95_response_ms?.toFixed(1) || 0}ms`} />
          <Card title="Avg Latency"          value={`${summary.engine_performance?.avg_response_ms?.toFixed(1) || 0}ms`} />
          <Card title="Searches Tracked"     value={summary.engine_performance?.total_searches_tracked || 0} />
        </div>
      </section>

      {/* TOP VIBES */}
      <section style={styles.section}>
        <h2 style={styles.sectionH2}>📊 TOP VIBES</h2>
        <div style={styles.chartContainer}>
          {Object.entries(summary.search_metrics?.top_vibes || {}).map(([vibe, count]) => {
            const maxCount = Object.values(summary.search_metrics?.top_vibes || {})[0] || 1;
            return (
              <div key={vibe} style={styles.chartBar}>
                <span style={styles.barLabel}>{vibe}</span>
                <div style={{ ...styles.bar, width: `${(count / maxCount) * 100}%` }}>
                  <span style={styles.barValue}>{count}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ENGAGEMENT */}
      <section style={styles.section}>
        <h2 style={styles.sectionH2}>👥 USER ENGAGEMENT</h2>
        <div style={styles.grid}>
          <Card title="Preview Clicks"       value={summary.user_engagement?.preview_clicks || 0} />
          <Card title="Spotify Links"        value={summary.user_engagement?.spotify_clicks || 0} />
          <Card title="Pro Mode Uses"        value={summary.user_engagement?.pro_mode_activations || 0} />
          <Card title="Playlists Saved"      value={summary.user_engagement?.playlist_saves || 0} />
        </div>
      </section>

      {/* FEEDBACK */}
      <section style={styles.section}>
        <h2 style={styles.sectionH2}>💬 FEEDBACK</h2>
        <div style={styles.grid}>
          <Card title="👍 Thumbs Up"    value={summary.feedback?.thumbs_up || 0}    color="#4ade80" />
          <Card title="👎 Thumbs Down"  value={summary.feedback?.thumbs_down || 0}  color="#ef4444" />
          <Card title="Positive Rate"   value={`${summary.feedback?.positive_rate_pct || 0}%`} />
          <Card title="Total Feedback"  value={summary.feedback?.total_feedback || 0} />
        </div>
      </section>

      {/* DATA QUALITY */}
      <section style={styles.section}>
        <h2 style={styles.sectionH2}>🔍 DATA QUALITY</h2>
        <div style={styles.grid}>
          <Card
            title="Enrichment"
            value={`${summary.data_quality?.enrichment_completion_pct || 0}%`}
            color={(summary.data_quality?.enrichment_completion_pct || 0) > 90 ? "#4ade80" : "#f59e0b"}
          />
          <Card title="Missing ISRCs"   value={summary.data_quality?.missing_isrcs || 0}             color="#ef4444" />
          <Card title="Cache Hit Rate"  value={`${summary.data_quality?.cache_hit_rate_pct || 0}%`} />
          <Card title="Cache Hits"      value={summary.data_quality?.cache_hits || 0} />
        </div>
      </section>

      {/* API ERRORS */}
      {Object.keys(summary.api_errors || {}).length > 0 && (
        <section style={styles.section}>
          <h2 style={styles.sectionH2}>⚠️ API ERRORS</h2>
          <div style={styles.errorList}>
            {Object.entries(summary.api_errors || {}).map(([err, count]) => (
              <div key={err} style={styles.errorItem}>
                <span>{err}</span>
                <span style={{ color: "#ef4444", fontWeight: "bold" }}>{count}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TRENDING */}
      {Object.keys(summary.trending_vibes_1h || {}).length > 0 && (
        <section style={styles.section}>
          <h2 style={styles.sectionH2}>🔥 TRENDING (LAST HOUR)</h2>
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
        <p>Last updated: {summary.timestamp ? new Date(summary.timestamp).toLocaleTimeString() : "—"}</p>
        <label style={styles.refreshLabel}>
          Refresh:
          <select
            value={refreshInterval}
            onChange={e => setRefreshInterval(Number(e.target.value))}
            style={styles.selectInput}
          >
            <option value={2000}>2s</option>
            <option value={5000}>5s</option>
            <option value={10000}>10s</option>
            <option value={30000}>30s</option>
          </select>
        </label>
      </footer>
    </div>
  );
}

/* ─── Card component ─────────────────────────────────────────── */
function Card({ title, value, color = "#3b82f6" }) {
  return (
    <div style={{ ...styles.card, borderLeftColor: color }}>
      <div style={styles.cardTitle}>{title}</div>
      <div style={{ ...styles.cardValue, color }}>{value}</div>
    </div>
  );
}

/* ─── Styles ─────────────────────────────────────────────────── */
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
  section: {
    marginBottom: "2rem",
    padding: "1.5rem",
    background: "#1e293b",
    borderRadius: "8px",
    border: "1px solid #334155",
  },
  sectionH2: {
    margin: "0 0 1rem 0",
    fontSize: "1.1rem",
    color: "#94a3b8",
    letterSpacing: "0.04em",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "1rem",
  },
  gridLive: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "1rem",
  },
  card: {
    padding: "1.2rem",
    background: "#0f172a",
    borderLeft: "4px solid #3b82f6",
    borderRadius: "4px",
    border: "1px solid #334155",
  },
  cardTitle: {
    fontSize: "0.8rem",
    textTransform: "uppercase",
    opacity: 0.6,
    marginBottom: "0.5rem",
    letterSpacing: "0.06em",
  },
  cardValue: {
    fontSize: "1.7rem",
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
    fontSize: "0.85rem",
    fontWeight: "bold",
    flexShrink: 0,
  },
  bar: {
    height: "26px",
    background: "linear-gradient(90deg, #3b82f6, #8b5cf6)",
    borderRadius: "4px",
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-end",
    paddingRight: "0.75rem",
    minWidth: "80px",
    transition: "width 0.6s ease",
  },
  barValue: {
    fontSize: "0.8rem",
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
    fontSize: "0.85rem",
  },
  trendingContainer: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
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
    fontSize: "0.85rem",
  },
  rank: {
    fontSize: "1.1rem",
    color: "#f59e0b",
    flexShrink: 0,
  },
  trendCount: {
    marginLeft: "auto",
    fontSize: "0.8rem",
    opacity: 0.6,
  },
  footer: {
    marginTop: "2rem",
    paddingTop: "1rem",
    borderTop: "1px solid #334155",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
    fontSize: "0.85rem",
    color: "#475569",
  },
  refreshLabel: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    cursor: "pointer",
  },
  selectInput: {
    padding: "0.2rem 0.4rem",
    background: "#0f172a",
    color: "#e2e8f0",
    border: "1px solid #334155",
    borderRadius: "4px",
    fontFamily: "'Courier New', monospace",
    cursor: "pointer",
    fontSize: "0.8rem",
  },
};
