/**
 * PromptHistory.jsx — VibeFinderAI Phase 9
 * Dark amber hardware aesthetic — DM Mono, amber/gold, panel-card style.
 * Place in: frontend/src/components/PromptHistory.jsx
 *
 * FIX: accepts `buildApiUrl` prop instead of hardcoding API_BASE.
 * App.jsx passes it as: <PromptHistory buildApiUrl={buildApiUrl} ... />
 */
import React, { useEffect, useState } from "react";

const VIBE_COLORS = {
  party: "#d97706", hype: "#b45309", heartbreak: "#be185d", romantic: "#db2777",
  chill: "#059669", calm: "#10b981", focus: "#3b82f6", dreamy: "#7c3aed",
  dark: "#4b5563", intense: "#dc2626", rock: "#b45309", indie_folk: "#16a34a",
  soulful: "#d97706", euphoric: "#7c3aed", happy: "#16a34a", retro: "#6b7280",
  cinematic: "#6d28d9", ambient: "#0d9488", hyperpop: "#db2777", default: "rgba(180,140,80,0.6)",
};

const LABEL_DOTS = { "nailed it": "●", "best guess": "◐", "exploring": "○" };

function HistoryRow({ item, onRerun }) {
  const col = VIBE_COLORS[item.dominant_vibe] || VIBE_COLORS.default;
  const dot = LABEL_DOTS[item.confidence_label] || "○";

  const timeAgo = (iso) => {
    if (!iso) return "";
    const m = Math.floor((Date.now() - new Date(iso)) / 60000);
    if (m < 1) return "now";
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
  };

  return (
    <div
      onClick={() => onRerun(item.prompt)}
      title={`Re-run: "${item.prompt}"`}
      style={{
        display: "flex", alignItems: "center", gap: "10px",
        padding: "7px 0",
        borderTop: "1px solid rgba(120,80,20,0.15)",
        cursor: "pointer", transition: "background 0.1s",
      }}
      onMouseEnter={e => e.currentTarget.style.background = "rgba(120,80,20,0.06)"}
      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
    >
      <span style={{ fontSize: "9px", color: col, width: "10px", textAlign: "center", flexShrink: 0 }}>
        {dot}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: "11px", color: "rgba(220,190,140,0.85)",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {item.prompt}
        </div>
        <div style={{
          fontSize: "9px", color: "rgba(120,80,20,0.6)",
          fontFamily: "'DM Mono', monospace", marginTop: "2px",
          display: "flex", gap: "6px",
        }}>
          <span style={{ color: col }}>{item.dominant_vibe.replace("_", " ")}</span>
          {item.genres[0] && <><span>·</span><span>{item.genres[0]}</span></>}
          <span>·</span><span>{item.track_count}trk</span>
          <span>·</span><span>{timeAgo(item.created_at)}</span>
        </div>
      </div>
      <span style={{ fontSize: "10px", color: "rgba(180,140,80,0.3)", flexShrink: 0 }}>↗</span>
    </div>
  );
}

export default function PromptHistory({ token, onRerun, refreshTrigger, buildApiUrl, style = {} }) {
  const [history, setHistory] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // Fallback: if buildApiUrl not passed, derive from env
  const apiUrl = buildApiUrl
    ? buildApiUrl
    : (path) => {
        const base = import.meta.env.VITE_API_URL || "";
        return base ? `${base}${path}` : path;
      };

  const fetchHistory = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(apiUrl("/api/vibe/history?limit=10"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.history || []);
      }
    } catch (_) {}
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchHistory();
  }, [token, refreshTrigger]); // eslint-disable-line

  if (history.length === 0 && !loading) return null;

  return (
    <div style={{ marginTop: "10px", ...style }}>
      <button
        onClick={() => {
          setOpen(v => !v);
          if (!open) fetchHistory();
        }}
        style={{
          display: "flex", alignItems: "center", gap: "6px",
          background: "none", border: "none", padding: "0", cursor: "pointer",
          color: "rgba(120,80,20,0.5)", fontFamily: "'DM Mono', monospace",
          fontSize: "9px", letterSpacing: "0.2em", textTransform: "uppercase",
        }}
      >
        <span style={{
          fontSize: "8px", transition: "transform 0.2s",
          display: "inline-block",
          transform: open ? "rotate(90deg)" : "rotate(0deg)",
        }}>▶</span>
        Recent searches
        {history.length > 0 && (
          <span style={{
            fontSize: "8px", padding: "1px 6px", borderRadius: "3px",
            background: "rgba(120,80,20,0.15)", color: "rgba(180,140,80,0.5)",
          }}>
            {history.length}
          </span>
        )}
      </button>

      {open && (
        <div style={{ marginTop: "6px" }}>
          {loading && history.length === 0 ? (
            <div style={{
              fontSize: "10px", color: "rgba(120,80,20,0.4)",
              fontFamily: "'DM Mono', monospace", padding: "6px 0",
            }}>Loading…</div>
          ) : (
            history.map(item => (
              <HistoryRow key={item.id} item={item} onRerun={onRerun} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
