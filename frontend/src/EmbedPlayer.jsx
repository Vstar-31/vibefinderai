/**
 * EmbedPlayer.jsx  — VibeFinderAI
 * ────────────────────────────────
 * Route: /embed/player
 *
 * A stripped-down page meant to be loaded inside something much smaller than
 * a browser tab — originally Themed.AI's "VibeFinder Playlist" desktop
 * widget, via a real WebView2 control (see ThemeManager.WinUI's
 * SkinHostWindow.BuildWebEmbedVisual). No nav bar, no landing hero, no
 * marketing copy — just a mood search box and the same MusicPlayer.jsx
 * component the main site's own player uses, so an embed of this really is
 * "the engine," not a native re-implementation of a slice of it.
 *
 * Auth: deliberately does NOT have its own login form. It reads the same
 * "vf_token" localStorage key the main app writes on sign-in. WebView2
 * controls that share one environment (the default one, with no custom
 * CoreWebView2EnvironmentOptions) share one browser profile — so if the
 * account was ever signed in through *any* WebView2 using that default
 * profile (e.g. Themed.AI's own VibeFinderAIPage, which embeds the full
 * site), this page finds that same token already sitting in localStorage
 * with no extra step. If it isn't there, this shows a short "sign in
 * elsewhere first" message rather than duplicating the real login flow.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import MusicPlayer from "./MusicPlayer.jsx";

const API_BASE_URL = import.meta.env.VITE_API_URL || "";
const buildApiUrl = (path) => (API_BASE_URL ? `${API_BASE_URL}${path}` : path);

const S = {
  root: {
    minHeight: "100vh",
    boxSizing: "border-box",
    padding: "10px 10px 14px",
    background: "linear-gradient(160deg, #120900 0%, #060300 100%)",
    fontFamily: "'DM Mono', 'Fira Code', monospace",
    color: "#e8d5a3",
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  title: {
    fontFamily: "'Playfair Display', serif",
    fontSize: 13,
    fontWeight: 900,
    color: "#e8d5a3",
    letterSpacing: "-0.01em",
  },
  sub: {
    fontSize: 8,
    color: "rgba(180,140,80,0.5)",
    letterSpacing: "0.15em",
    textTransform: "uppercase",
    marginTop: 1,
  },
  textarea: {
    width: "100%",
    boxSizing: "border-box",
    height: 46,
    resize: "none",
    background: "rgba(5,3,1,0.8)",
    border: "1px solid rgba(160,110,30,0.42)",
    borderRadius: 8,
    padding: "8px 10px",
    color: "#e8d5a3",
    fontFamily: "'DM Mono', monospace",
    fontSize: 11,
    lineHeight: 1.4,
    outline: "none",
  },
  runBtn: (disabled) => ({
    padding: "7px 14px",
    background: disabled ? "rgba(50,30,8,0.4)" : "linear-gradient(135deg, #92400e 0%, #b45309 50%, #d97706 100%)",
    border: "1px solid " + (disabled ? "rgba(80,50,10,0.3)" : "rgba(251,191,36,0.3)"),
    borderRadius: 8,
    color: disabled ? "rgba(120,80,20,0.5)" : "#fef3c7",
    fontFamily: "'DM Mono', monospace",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    cursor: disabled ? "not-allowed" : "pointer",
    alignSelf: "flex-start",
  }),
  error: {
    fontSize: 10,
    color: "#f87171",
    lineHeight: 1.4,
  },
  status: {
    fontSize: 10,
    color: "rgba(180,140,80,0.6)",
  },
  signInBox: {
    marginTop: 10,
    padding: "12px 14px",
    background: "rgba(20,12,4,0.6)",
    border: "1px solid rgba(180,120,40,0.3)",
    borderRadius: 10,
    fontSize: 11,
    lineHeight: 1.5,
    color: "rgba(220,190,140,0.85)",
  },
  vibeLabel: {
    fontSize: 9,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    color: "rgba(180,140,80,0.55)",
  },
  dominantVibe: {
    fontFamily: "'Playfair Display', serif",
    fontSize: 16,
    fontWeight: 700,
    color: "#fde68a",
  },
  // Bottom padding so page content isn't hidden behind MusicPlayer's fixed bar once it appears.
  playerSpacer: { height: 92 },
};

export default function EmbedPlayer() {
  const [token] = useState(() => {
    try { return localStorage.getItem("vf_token") || null; }
    catch { return null; }
  });

  const initialVibe = useState(() => {
    try { return new URLSearchParams(window.location.search).get("vibe") || ""; }
    catch { return ""; }
  })[0];

  const [prompt, setPrompt] = useState(initialVibe);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const [servicesStatus, setServicesStatus] = useState({});
  const [tokenInvalid, setTokenInvalid] = useState(false);

  const autoRunRef = useRef(false);

  const runAnalyze = useCallback(async (text) => {
    if (!token || !text.trim() || loading) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(buildApiUrl("/api/vibe/analyze"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          text: text.trim(),
          artist_focus: 50,
          nicheness: 50,
          bpm_focus: 50,
          track_limit: 10,
          use_secondary_vibe: false,
          override_genre: null,
          override_artist: null,
          language: null,
          dismiss_detected_artist: false,
          excluded_tracks: null,
          liked_artists: [],
          refinement_of: null,
          refinement_instruction: null,
        }),
      });

      if (res.status === 401) { setTokenInvalid(true); throw new Error("Session expired"); }
      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Analysis failed.");
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, [token, loading]);

  // A ?vibe= query param (set by Themed.AI when it builds this meter's URL) auto-runs once on
  // load — otherwise this panel would sit on an empty search box until someone types into a
  // ~260px-wide widget by hand. A blank param just leaves the box empty, same as opening the
  // page directly.
  useEffect(() => {
    if (!autoRunRef.current && token && initialVibe.trim()) {
      autoRunRef.current = true;
      runAnalyze(initialVibe);
    }
  }, [token, initialVibe, runAnalyze]);

  useEffect(() => {
    if (!token) return;
    fetch(buildApiUrl(`/api/services/status?authorization=${encodeURIComponent("Bearer " + token)}`))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setServicesStatus(d); })
      .catch(() => {});
  }, [token]);

  if (!token || tokenInvalid) {
    return (
      <div style={S.root}>
        <div>
          <div style={S.title}>VibeFinderAI</div>
          <div style={S.sub}>Engine</div>
        </div>
        <div style={S.signInBox}>
          {tokenInvalid ? "Your session expired. " : "Not signed in. "}
          Open VibeFinderAI's own page in Themed.AI and sign in there once —
          this panel shares that same session automatically.
        </div>
      </div>
    );
  }

  const tracks = result?.tracks || [];

  return (
    <div style={S.root}>
      <div>
        <div style={S.title}>VibeFinderAI</div>
        <div style={S.sub}>Engine</div>
      </div>

      <textarea
        style={S.textarea}
        value={prompt}
        placeholder="Describe a mood, moment, or vibe…"
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runAnalyze(prompt); }
        }}
      />

      <button
        style={S.runBtn(loading || !prompt.trim())}
        disabled={loading || !prompt.trim()}
        onClick={() => runAnalyze(prompt)}
      >
        {loading ? "Finding…" : "Find the vibe"}
      </button>

      {error && <div style={S.error}>{error}</div>}

      {result?.dominant_vibe && (
        <div>
          <div style={S.vibeLabel}>Dominant vibe</div>
          <div style={S.dominantVibe}>{result.dominant_vibe}</div>
        </div>
      )}

      {tracks.length === 0 && !loading && !error && (
        <div style={S.status}>Results appear here — and in the player below.</div>
      )}

      {/* Reserve room so the fixed-position player bar below never sits over the search box. */}
      {tracks.length > 0 && <div style={S.playerSpacer} />}

      {tracks.length > 0 && (
        <MusicPlayer
          tracks={tracks}
          initialIndex={0}
          activeColor="#d97706"
          token={token}
          buildApiUrl={buildApiUrl}
          spotifyConnected={!!servicesStatus?.spotify?.connected}
          servicesConnected={Object.fromEntries(Object.entries(servicesStatus).map(([k, v]) => [k, !!v?.connected]))}
          visibleServices={{ lastfm: true, youtube: true }}
        />
      )}
    </div>
  );
}
