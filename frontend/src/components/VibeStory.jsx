/**
 * VibeStory.jsx
 * VibeFinderAI Phase 9 — AI vibe explanation
 * Place in: frontend/src/components/VibeStory.jsx
 *
 * Fires a POST /api/vibe/story after results load and displays
 * a 2-sentence Gemini-generated explanation of why you got these results.
 * Non-blocking — results show immediately, story appears when ready.
 *
 * Usage:
 *   <VibeStory
 *     prompt={request.text}
 *     response={vibeResponse}
 *     token={authToken}
 *   />
 */

import React, { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function VibeStory({ prompt, response, token }) {
  const [story, setStory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [visible, setVisible] = useState(false);
  const fetchedRef = useRef(null);

  useEffect(() => {
    if (!response || !prompt || !token) return;

    // Deduplicate — don't refetch for the same request_id
    const key = response.request_id || prompt;
    if (fetchedRef.current === key) return;
    fetchedRef.current = key;

    setStory(null);
    setVisible(false);
    setLoading(true);

    const payload = {
      prompt,
      dominant_vibe: response.dominant_vibe || "",
      genres: response.genres || [],
      matched_keywords: response.matched_keywords || [],
      language: response.language || "Any",
      confidence: response.confidence || 0.5,
      tracks: (response.tracks || []).slice(0, 3).map((t) => ({
        title: t.title,
        artist: t.artist,
      })),
    };

    fetch(`${API_BASE}/api/vibe/story`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.story) {
          setStory(data.story);
          // Slight delay so it fades in after tracks settle
          setTimeout(() => setVisible(true), 200);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [response?.request_id, prompt, token]);

  if (!story && !loading) return null;

  return (
    <div
      style={{
        margin: "12px 0 4px",
        padding: "12px 16px",
        borderRadius: "10px",
        background: "var(--color-background-secondary, rgba(0,0,0,0.04))",
        borderLeft: "2px solid var(--color-border-secondary, rgba(0,0,0,0.15))",
        opacity: loading ? 0.4 : visible ? 1 : 0,
        transition: "opacity 0.4s ease",
        minHeight: loading ? "36px" : undefined,
      }}
    >
      {loading && !story ? (
        <span
          style={{
            fontSize: "12px",
            color: "var(--color-text-tertiary, #888)",
            fontStyle: "italic",
          }}
        >
          Reading the vibe…
        </span>
      ) : (
        <p
          style={{
            margin: 0,
            fontSize: "13px",
            lineHeight: 1.65,
            color: "var(--color-text-secondary, #555)",
          }}
        >
          {story}
        </p>
      )}
    </div>
  );
}
