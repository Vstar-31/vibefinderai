/**
 * ConfidenceBadge.jsx
 * VibeFinderAI Phase 9 — Confidence indicator
 * Place in: frontend/src/components/ConfidenceBadge.jsx
 *
 * Shows the engine's confidence in the vibe detection.
 * Three levels: "nailed it" / "best guess" / "exploring"
 *
 * Usage:
 *   <ConfidenceBadge label={response.confidence_label} confidence={response.confidence} />
 */

import React from "react";

const CONFIG = {
  "nailed it": {
    color: "#1D9E75",
    bg: "rgba(29,158,117,0.1)",
    dot: "#1D9E75",
    tooltip: "The engine is highly confident about this vibe.",
  },
  "best guess": {
    color: "#BA7517",
    bg: "rgba(186,117,23,0.1)",
    dot: "#EF9F27",
    tooltip: "Solid match — try refining if it's not quite right.",
  },
  exploring: {
    color: "#888780",
    bg: "rgba(136,135,128,0.1)",
    dot: "#B4B2A9",
    tooltip: "Unusual prompt — results may be eclectic. Try adding more detail.",
  },
};

export default function ConfidenceBadge({ label = "exploring", confidence = 0, style = {} }) {
  const cfg = CONFIG[label] || CONFIG.exploring;
  const pct = Math.round(confidence * 100);

  return (
    <span
      title={cfg.tooltip}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: "3px 10px",
        borderRadius: "99px",
        background: cfg.bg,
        fontSize: "11px",
        fontWeight: 500,
        color: cfg.color,
        cursor: "default",
        userSelect: "none",
        letterSpacing: "0.2px",
        ...style,
      }}
    >
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          background: cfg.dot,
          flexShrink: 0,
        }}
      />
      {label}
      <span style={{ opacity: 0.6, fontSize: "10px", marginLeft: "1px" }}>
        {pct}%
      </span>
    </span>
  );
}
