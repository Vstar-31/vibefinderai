/**
 * VibeStory.jsx — VibeFinderAI Phase 9
 * Full dark aesthetic — amber/gold, DM Mono header, matches panel-card style.
 * Place in: frontend/src/components/VibeStory.jsx
 */
import React, { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function VibeStory({ prompt, response, token, activeColor = "#d97706" }) {
  const [story, setStory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [visible, setVisible] = useState(false);
  const fetchedRef = useRef(null);

  useEffect(() => {
    if (!response || !prompt || !token) return;
    const key = response.request_id || prompt;
    if (fetchedRef.current === key) return;
    fetchedRef.current = key;

    setStory(null); setVisible(false); setLoading(true);

    fetch(`${API_BASE}/api/vibe/story`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        prompt,
        dominant_vibe: response.dominant_vibe || "",
        genres: response.genres || [],
        matched_keywords: response.matched_keywords || [],
        language: response.language || "Any",
        confidence: response.confidence || 0.5,
        tracks: (response.tracks || []).slice(0, 3).map(t => ({ title: t.title, artist: t.artist })),
      }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.story) {
          setStory(data.story);
          setTimeout(() => setVisible(true), 150);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [response?.request_id, prompt, token]);

  if (!story && !loading) return null;

  return (
    <div style={{
      margin: "12px 0 0",
      padding: "12px 16px",
      borderRadius: "8px",
      background: "rgba(12,7,2,0.5)",
      border: `1px solid ${activeColor}22`,
      borderLeft: `2px solid ${activeColor}55`,
      opacity: loading ? 0.5 : visible ? 1 : 0,
      transition: "opacity 0.4s ease",
      minHeight: loading ? "34px" : undefined,
    }}>
      {loading && !story ? (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{ width: "8px", height: "8px", borderRadius: "50%", border: `1.5px solid ${activeColor}44`, borderTopColor: activeColor, animation: "spin 0.8s linear infinite", flexShrink: 0 }} />
          <span style={{ fontSize: "10px", color: "rgba(180,140,80,0.4)", fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em" }}>
            Reading the vibe…
          </span>
        </div>
      ) : (
        <p style={{ margin: 0, fontSize: "12px", lineHeight: 1.7, color: "rgba(200,170,110,0.8)", fontStyle: "italic" }}>
          {story}
        </p>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
