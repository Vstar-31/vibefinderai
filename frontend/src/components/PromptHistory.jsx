/**
 * PromptHistory.jsx
 * VibeFinderAI Phase 9 — Recent searches panel
 * Place in: frontend/src/components/PromptHistory.jsx
 *
 * Fetches the last 10 vibe requests from GET /api/vibe/history
 * and displays them as a collapsible panel with one-click re-run.
 *
 * Usage:
 *   <PromptHistory
 *     token={authToken}
 *     onRerun={(prompt) => handleSubmit(prompt)}
 *     refreshTrigger={lastRequestId}   // increment to force refresh
 *   />
 */

import React, { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const VIBE_COLORS = {
  party:      "#D85A30",
  hype:       "#BA7517",
  heartbreak: "#D4537E",
  romantic:   "#D4537E",
  chill:      "#1D9E75",
  calm:       "#1D9E75",
  focus:      "#378ADD",
  dreamy:     "#7F77DD",
  dark:       "#5F5E5A",
  intense:    "#A32D2D",
  rock:       "#993C1D",
  indie_folk: "#3B6D11",
  soulful:    "#854F0B",
  euphoric:   "#7F77DD",
  happy:      "#639922",
  retro:      "#888780",
  cinematic:  "#534AB7",
  ambient:    "#0F6E56",
  hyperpop:   "#993556",
  default:    "#888780",
};

const LABEL_ICONS = {
  "nailed it":  "●",
  "best guess": "◐",
  "exploring":  "○",
};

function HistoryItem({ item, onRerun }) {
  const dotColor = VIBE_COLORS[item.dominant_vibe] || VIBE_COLORS.default;
  const icon = LABEL_ICONS[item.confidence_label] || "○";

  const timeAgo = (isoStr) => {
    if (!isoStr) return "";
    const diff = Date.now() - new Date(isoStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "10px",
        padding: "10px 0",
        borderTop: "0.5px solid var(--color-border-tertiary, rgba(0,0,0,0.08))",
        cursor: "pointer",
      }}
      onClick={() => onRerun(item.prompt)}
      title="Click to re-run this search"
    >
      {/* Vibe dot */}
      <span
        style={{
          fontSize: "10px",
          color: dotColor,
          marginTop: "3px",
          flexShrink: 0,
          width: "12px",
          textAlign: "center",
        }}
      >
        {icon}
      </span>

      {/* Prompt + meta */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: "13px",
            color: "var(--color-text-primary, #000)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {item.prompt}
        </div>
        <div
          style={{
            fontSize: "11px",
            color: "var(--color-text-tertiary, #888)",
            marginTop: "2px",
            display: "flex",
            gap: "8px",
            alignItems: "center",
          }}
        >
          <span style={{ color: dotColor, fontWeight: 500 }}>
            {item.dominant_vibe.replace("_", " ")}
          </span>
          {item.genres[0] && (
            <>
              <span style={{ opacity: 0.4 }}>·</span>
              <span>{item.genres[0]}</span>
            </>
          )}
          <span style={{ opacity: 0.4 }}>·</span>
          <span>{item.track_count} tracks</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>{timeAgo(item.created_at)}</span>
        </div>
      </div>

      {/* Re-run arrow */}
      <span
        style={{
          fontSize: "12px",
          color: "var(--color-text-tertiary, #888)",
          flexShrink: 0,
          marginTop: "2px",
          opacity: 0,
          transition: "opacity 0.15s",
        }}
        className="rerun-arrow"
      >
        ↗
      </span>

      <style>{`
        div:hover > .rerun-arrow { opacity: 1 !important; }
      `}</style>
    </div>
  );
}

export default function PromptHistory({ token, onRerun, refreshTrigger, style = {} }) {
  const [history, setHistory] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchHistory = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/vibe/history?limit=10`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      setHistory(data.history || []);
    } catch (_) {
      // Silently fail
    } finally {
      setLoading(false);
    }
  };

  // Fetch on mount and when a new request completes
  useEffect(() => {
    fetchHistory();
  }, [token, refreshTrigger]);

  if (history.length === 0 && !loading) return null;

  return (
    <div style={{ marginTop: "20px", ...style }}>
      {/* Toggle header */}
      <button
        onClick={() => {
          setOpen((v) => !v);
          if (!open) fetchHistory();
        }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          background: "none",
          border: "none",
          padding: "0",
          cursor: "pointer",
          color: "var(--color-text-secondary, #555)",
          fontSize: "12px",
          fontWeight: 500,
          fontFamily: "inherit",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
        }}
      >
        <span style={{ fontSize: "10px", transition: "transform 0.2s", display: "inline-block", transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>
          ▶
        </span>
        Recent searches
        {history.length > 0 && (
          <span
            style={{
              fontSize: "10px",
              padding: "1px 7px",
              borderRadius: "99px",
              background: "var(--color-background-secondary, rgba(0,0,0,0.06))",
              color: "var(--color-text-tertiary, #888)",
            }}
          >
            {history.length}
          </span>
        )}
      </button>

      {/* History list */}
      {open && (
        <div style={{ marginTop: "8px" }}>
          {loading && history.length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--color-text-tertiary, #888)", padding: "8px 0" }}>
              Loading…
            </div>
          ) : (
            history.map((item) => (
              <HistoryItem key={item.id} item={item} onRerun={onRerun} />
            ))
          )}
          {history.length === 0 && !loading && (
            <div style={{ fontSize: "12px", color: "var(--color-text-tertiary, #888)", padding: "8px 0" }}>
              No recent searches yet.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
