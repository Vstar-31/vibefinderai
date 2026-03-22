/**
 * ConfidenceBadge.jsx — VibeFinderAI Phase 9
 * Dark amber aesthetic, matches the app's hardware panel style.
 * Place in: frontend/src/components/ConfidenceBadge.jsx
 */
import React from "react";

const CONFIG = {
  "nailed it": { color: "#4ade80", bg: "rgba(74,222,128,0.1)", dot: "#4ade80", label: "nailed it" },
  "best guess": { color: "#fbbf24", bg: "rgba(251,191,36,0.1)", dot: "#fbbf24", label: "best guess" },
  "exploring":  { color: "rgba(180,140,80,0.5)", bg: "rgba(120,80,20,0.12)", dot: "rgba(180,140,80,0.35)", label: "exploring" },
};

export default function ConfidenceBadge({ label = "exploring", confidence = 0, style = {} }) {
  const cfg = CONFIG[label] || CONFIG.exploring;
  const pct = Math.round(confidence * 100);

  return (
    <span
      title={
        label === "nailed it"  ? "Engine is highly confident — these results should be spot on." :
        label === "best guess" ? "Good match — refine if it's not quite right." :
        "Unusual prompt — results may vary. Try adding more detail."
      }
      style={{
        display: "inline-flex", alignItems: "center", gap: "5px",
        padding: "2px 8px", borderRadius: "4px",
        background: cfg.bg,
        border: `1px solid ${cfg.color}33`,
        fontSize: "9px", fontWeight: 500, color: cfg.color,
        fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em",
        textTransform: "uppercase", cursor: "default", userSelect: "none",
        ...style,
      }}
    >
      <span style={{ width: "5px", height: "5px", borderRadius: "50%", background: cfg.dot, flexShrink: 0 }} />
      {cfg.label}
      <span style={{ opacity: 0.55, fontSize: "8px" }}>{pct}%</span>
    </span>
  );
}
