import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MusicPlayer from "./MusicPlayer.jsx";
import "./ThemedApp.css";

const API_BASE_URL = import.meta.env.VITE_API_URL || "";
const api = (path) => (API_BASE_URL ? `${API_BASE_URL}${path}` : path);

const VIBES = {
  hype: "#ff5c7a", calm: "#67e8a5", intense: "#ff8a4c", chill: "#66b5ff", focus: "#42d9e8",
  euphoric: "#df7cff", soulful: "#f7c65f", retro: "#8d82ff", dreamy: "#c38cff", cinematic: "#ff9a5c",
  dark: "#a9b2c3", heartbreak: "#ff6fa8", hyperpop: "#e95dff", party: "#ff55b5", country: "#d99a4b",
  tropical: "#38d6bc", industrial: "#8e98a8", desi: "#ff526f", neutral: "#f6a64a", "Direct Search": "#f6d365",
};

const DEMOS = [
  "late night drive through neon rain",
  "warm indie morning with coffee and sunlight",
  "deep focus, minimal vocals, futuristic textures",
  "2000s Bollywood party but make it glossy",
];

const Icons = {
  Spark: () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 1.65 6.35L20 10l-6.35 1.65L12 18l-1.65-6.35L4 10l6.35-1.65L12 2Z"/><path d="m19 15 .8 3.2L23 19l-3.2.8L19 23l-.8-3.2L15 19l3.2-.8L19 15Z"/></svg>,
  Play: () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 11 7-11 7V5Z"/></svg>,
  Library: () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H21v14H6.5A2.5 2.5 0 0 0 4 19.5V5.5Z"/><path d="M4 19.5V21h14"/></svg>,
  User: () => <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>,
  X: () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>,
  Arrow: () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>,
  Clock: () => <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>,
  Save: () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h11l3 3v15H4V3h2Z"/><path d="M8 3v6h8V3M8 21v-7h8v7"/></svg>,
};

function emitHost(message) {
  try {
    if (window.chrome?.webview) window.chrome.webview.postMessage(message);
  } catch {}
}

function AuthModal({ mode, setMode, form, setForm, onSubmit, loading, error, onClose }) {
  const login = mode === "login";
  return (
    <div className="ta-overlay" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="ta-auth-card">
        <button className="ta-icon-btn ta-close" onClick={onClose} aria-label="Close"><Icons.X /></button>
        <span className="ta-eyebrow">VIBEFINDER / THEMED.AI</span>
        <h2>{login ? "Welcome back." : "Create your vibe identity."}</h2>
        <p className="ta-muted">{login ? "Your library, history and preferences are waiting." : "A lightweight account unlocks saved playlists and history."}</p>
        {error && <div className="ta-error">{error}</div>}
        <form onSubmit={onSubmit} className="ta-form">
          {!login && <input aria-label="Email" type="email" required placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
          <input aria-label="Username" required placeholder="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          <input aria-label="Password" type="password" required placeholder="Password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <button className="ta-primary" disabled={loading}>{loading ? "Connecting…" : login ? "Sign in" : "Create account"}</button>
        </form>
        <button className="ta-link" onClick={() => setMode(login ? "signup" : "login")}>
          {login ? "New here? Create an account" : "Already have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}

function Library({ token, refreshKey, onLoad, onClose }) {
  const [saved, setSaved] = useState([]);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("saved");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true); setError("");
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [savedRes, historyRes] = await Promise.all([
        fetch(api("/api/playlist/list?limit=50"), { headers }),
        fetch(api("/api/user/history?limit=30"), { headers }),
      ]);
      if (savedRes.status === 401 || historyRes.status === 401) throw new Error("SESSION_EXPIRED");
      if (!savedRes.ok) throw new Error("Could not load saved playlists");
      const savedData = await savedRes.json();
      const historyData = historyRes.ok ? await historyRes.json() : [];
      setSaved(savedData.playlists || savedData || []);
      setHistory(historyData.history || historyData || []);
    } catch (e) {
      setError(e.message === "SESSION_EXPIRED" ? "Your session expired. Sign in again." : e.message);
    } finally { setBusy(false); }
  }, [token, refreshKey]);

  useEffect(() => { load(); }, [load]);

  const rows = tab === "saved" ? saved : history;
  return (
    <aside className="ta-library">
      <div className="ta-library-head">
        <div><span className="ta-eyebrow">YOUR SPACE</span><h3>Library</h3></div>
        <button className="ta-icon-btn" onClick={onClose} aria-label="Close library"><Icons.X /></button>
      </div>
      <div className="ta-tabs">
        <button className={tab === "saved" ? "active" : ""} onClick={() => setTab("saved")}>Saved</button>
        <button className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>History</button>
      </div>
      {busy ? <div className="ta-library-empty">Loading your space…</div> : error ? <div className="ta-library-empty"><p>{error}</p><button className="ta-secondary" onClick={load}>Retry</button></div> : rows.length === 0 ? <div className="ta-library-empty"><p>{tab === "saved" ? "No saved playlists yet." : "No vibe history yet."}</p><span>Run a vibe and it will show up here.</span></div> : (
        <div className="ta-library-list">
          {rows.map((item, index) => {
            const label = item.name || item.prompt || `Vibe ${index + 1}`;
            const subtitle = item.prompt || item.dominant_vibe || item.created_at || "Saved vibe";
            const tracks = item.tracks || item.track_count || 0;
            return (
              <button key={item.id || item.playlist_id || item.request_id || index} className="ta-library-row" onClick={() => onLoad(item)}>
                <div className="ta-cover" style={{ background: `linear-gradient(145deg, ${VIBES[item.dominant_vibe] || "#7558ff"}, rgba(10,12,20,.35))` }}><Icons.Play /></div>
                <div className="ta-row-copy"><strong>{label}</strong><span>{subtitle}</span></div>
                <small>{typeof tracks === "number" ? `${tracks} tracks` : "Open"}</small>
              </button>
            );
          })}
        </div>
      )}
    </aside>
  );
}

export default function ThemedApp() {
  const [token, setToken] = useState(() => { try { return localStorage.getItem("vf_token") || ""; } catch { return ""; } });
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [error, setError] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ email: "", username: "", password: "" });
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryRefresh, setLibraryRefresh] = useState(0);
  const [playerOpen, setPlayerOpen] = useState(false);
  const [playerTracks, setPlayerTracks] = useState([]);
  const [playerIndex, setPlayerIndex] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [intensity, setIntensity] = useState(50);
  const [nicheness, setNicheness] = useState(50);
  const [bpm, setBpm] = useState(50);
  const [trackCount, setTrackCount] = useState(8);
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem("themed_ai_accent") || "#a78bfa"; } catch { return "#a78bfa"; } });
  const formRef = useRef(null);
  const textareaRef = useRef(null);

  const vibe = result?.dominant_vibe || "neutral";
  const activeColor = VIBES[vibe] || theme;
  const tracks = result?.tracks || [];
  const confidence = Math.round((result?.confidence || 0) * 100);

  useEffect(() => {
    emitHost({ type: "THEMEDAI_READY", version: "1.1", capabilities: ["vibe_analysis", "library", "player", "theme_sync", "playlist_save"] });
  }, []);

  useEffect(() => {
    emitHost({ type: "VIBEFINDER_STATE", state: { vibe, prompt, trackCount: tracks.length, loading, hasResult: Boolean(result) } });
  }, [vibe, prompt, tracks.length, loading, result]);

  useEffect(() => {
    try { localStorage.setItem("themed_ai_accent", theme); } catch {}
    emitHost({ type: "THEMEDAI_THEME", accent: theme });
  }, [theme]);

  useEffect(() => {
    const handler = (event) => {
      const data = event.data;
      if (!data || typeof data !== "object") return;
      if (data.type === "THEMEDAI_THEME_SET" && typeof data.accent === "string") setTheme(data.accent);
      if (data.type === "THEMEDAI_ANALYZE" && typeof data.prompt === "string") {
        setPrompt(data.prompt);
        requestAnimationFrame(() => formRef.current?.requestSubmit());
      }
    };
    window.addEventListener("message", handler);
    const webview = window.chrome?.webview;
    webview?.addEventListener?.("message", handler);
    return () => {
      window.removeEventListener("message", handler);
      webview?.removeEventListener?.("message", handler);
    };
  }, []);

  useEffect(() => {
    const handler = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const submitAuth = async (e) => {
    e.preventDefault(); setLoading(true); setError("");
    try {
      if (authMode === "signup") {
        const r = await fetch(api("/auth/register"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(authForm) });
        if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || "Registration failed"); }
      }
      const fd = new URLSearchParams(); fd.append("username", authForm.username); fd.append("password", authForm.password);
      const r = await fetch(api("/auth/token"), { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: fd });
      if (!r.ok) throw new Error("Authentication failed — check your credentials.");
      const data = await r.json();
      localStorage.setItem("vf_token", data.access_token); setToken(data.access_token); setAuthOpen(false); setAuthForm({ email: "", username: "", password: "" });
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  };

  const analyze = async (e) => {
    e?.preventDefault();
    if (!prompt.trim()) { textareaRef.current?.focus(); return; }
    if (!token) { setAuthOpen(true); return; }
    setLoading(true); setError(""); setSaveMessage("");
    try {
      const r = await fetch(api("/api/vibe/analyze"), {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text: prompt.trim(), artist_focus: intensity, nicheness, bpm_focus: bpm, track_limit: trackCount, language: null, use_secondary_vibe: false, override_genre: null, override_artist: null, dismiss_detected_artist: false, excluded_tracks: null, liked_artists: [] }),
      });
      if (r.status === 401) { localStorage.removeItem("vf_token"); setToken(""); throw new Error("Session expired. Sign in again."); }
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || "The vibe engine could not complete that request."); }
      const data = await r.json(); setResult(data);
      emitHost({ type: "THEMEDAI_ANALYSIS_COMPLETE", vibe: data.dominant_vibe, requestId: data.request_id, tracks: data.tracks?.length || 0 });
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  };

  const saveCurrent = async () => {
    if (!token) { setAuthOpen(true); return; }
    if (!tracks.length || saving) return;
    setSaving(true); setSaveMessage("");
    try {
      const payloadTracks = tracks.map((track) => ({
        title: track.title || "Untitled",
        artist: track.artist || "Unknown artist",
        spotify_uri: track.spotify_uri || "",
        apple_uri: track.apple_uri || "",
        preview_url: track.preview_url || null,
        cover_art: track.cover_art || null,
      }));
      const r = await fetch(api("/api/playlist/save"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: prompt.trim() ? `Vibe — ${prompt.trim().slice(0, 56)}` : "Themed.AI Vibe",
          prompt: prompt.trim() || null,
          dominant_vibe: result?.dominant_vibe || null,
          language: null,
          tracks: payloadTracks,
          is_public: false,
        }),
      });
      if (r.status === 401) { localStorage.removeItem("vf_token"); setToken(""); throw new Error("Session expired. Sign in again."); }
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || "Could not save this vibe."); }
      await r.json();
      setSaveMessage("Saved to Library");
      setLibraryRefresh((x) => x + 1);
      emitHost({ type: "THEMEDAI_PLAYLIST_SAVED", tracks: tracks.length });
    } catch (e) {
      setSaveMessage(e.message);
    } finally {
      setSaving(false);
    }
  };

  const openPlayer = (idx = 0, list = tracks) => { if (!list?.length) return; setPlayerTracks(list); setPlayerIndex(idx); setPlayerOpen(true); };
  const logout = () => { localStorage.removeItem("vf_token"); setToken(""); setResult(null); setLibraryOpen(false); setPlayerOpen(false); setSaveMessage(""); };

  const loadLibraryItem = (item) => {
    const itemTracks = Array.isArray(item.tracks) ? item.tracks : [];
    if (itemTracks.length) {
      setResult((prev) => ({ ...(prev || {}), tracks: itemTracks, dominant_vibe: item.dominant_vibe || prev?.dominant_vibe || "neutral", prompt: item.prompt || prev?.prompt || "", confidence: prev?.confidence || 0 }));
      if (item.prompt) setPrompt(item.prompt);
      setLibraryOpen(false);
      return;
    }
    if (item.prompt) {
      setPrompt(item.prompt);
      setLibraryOpen(false);
      requestAnimationFrame(() => formRef.current?.requestSubmit());
      return;
    }
    setLibraryOpen(false);
  };

  const presets = useMemo(() => DEMOS.map((text, i) => ({ text, hue: ["#8b5cf6", "#f59e0b", "#22d3ee", "#f43f5e"][i] })), []);

  return (
    <main className="ta-app" style={{ "--accent": activeColor, "--user-accent": theme }}>
      <div className="ta-aurora ta-aurora-a" /><div className="ta-aurora ta-aurora-b" />
      <header className="ta-topbar">
        <button className="ta-brand" onClick={() => { setResult(null); setPrompt(""); setSaveMessage(""); }}>
          <span className="ta-brand-mark"><Icons.Spark /></span><span>vibefinder<span className="ta-brand-dot">.</span>ai</span><em>THEMED</em>
        </button>
        <div className="ta-top-actions">
          <button className={`ta-ghost ${libraryOpen ? "active" : ""}`} onClick={() => token ? setLibraryOpen(true) : setAuthOpen(true)}><Icons.Library /> Library</button>
          {token ? <button className="ta-avatar" title="Sign out" onClick={logout}><Icons.User /></button> : <button className="ta-login" onClick={() => setAuthOpen(true)}>Sign in</button>}
        </div>
      </header>

      <section className="ta-layout">
        <div className="ta-main-column">
          <div className="ta-hero">
            <span className="ta-eyebrow"><span className="ta-live-dot" /> THEMED.AI MUSIC INTELLIGENCE</span>
            <h1>Give it a feeling.<br /><span>We'll find the sound.</span></h1>
            <p>Describe a moment, a memory, a scene, or a completely unhinged mood. The engine turns it into a playable world.</p>
          </div>

          <form ref={formRef} className="ta-composer" onSubmit={analyze}>
            <div className="ta-composer-head"><span>VIBE PROMPT</span><span className="ta-kbd">ENTER ↵</span></div>
            <textarea ref={textareaRef} autoFocus rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="e.g. rainy neon city, 2am, cinematic but still danceable…" />
            <div className="ta-composer-foot"><div className="ta-chips">{presets.map((p) => <button key={p.text} type="button" style={{ "--chip": p.hue }} onClick={() => setPrompt(p.text)}>{p.text}</button>)}</div><button className="ta-generate" disabled={loading}>{loading ? <span className="ta-spinner" /> : <Icons.Spark />} {loading ? "Finding your vibe…" : "Find my vibe"}</button></div>
          </form>

          {error && <div className="ta-error ta-inline">{error}<button className="ta-link" onClick={() => setError("")}>dismiss</button></div>}

          {result && (
            <section className="ta-result" style={{ "--result-color": activeColor }}>
              <div className="ta-result-banner">
                <div><span className="ta-eyebrow">YOUR VIBE</span><h2>{result.dominant_vibe || "Unknown"}</h2><p>{result.explanation || "A custom sonic profile assembled from your prompt."}</p></div>
                <div className="ta-result-actions">
                  <div className="ta-confidence"><b>{confidence}%</b><span>confidence</span></div>
                  {tracks.length > 0 && <button className="ta-secondary ta-save" onClick={saveCurrent} disabled={saving}><Icons.Save /> {saving ? "Saving…" : "Save vibe"}</button>}
                </div>
              </div>
              {saveMessage && <div className={`ta-save-message ${saveMessage === "Saved to Library" ? "success" : ""}`}>{saveMessage}</div>}
              <div className="ta-track-grid">
                {tracks.map((track, idx) => (
                  <article className="ta-track-card" key={`${track.title}-${track.artist}-${idx}`}>
                    <button className="ta-art" onClick={() => openPlayer(idx)} aria-label={`Play ${track.title}`}>
                      {track.cover_art ? <img src={track.cover_art} alt="" /> : <div className="ta-art-fallback" style={{ background: `linear-gradient(135deg, ${activeColor}, #121526)` }}><Icons.Spark /></div>}
                      <span className="ta-art-play"><Icons.Play /></span>
                    </button>
                    <div className="ta-track-copy"><span className="ta-track-num">{String(idx + 1).padStart(2, "0")}</span><strong title={track.title}>{track.title}</strong><span>{track.artist || "Unknown artist"}</span></div>
                    <button className="ta-mini-play" onClick={() => openPlayer(idx)} aria-label={`Open player for ${track.title}`}><Icons.Play /></button>
                  </article>
                ))}
              </div>
              {tracks.length > 0 && <button className="ta-play-all" onClick={() => openPlayer(0)}><Icons.Play /> Play the whole vibe <span>{tracks.length} tracks</span></button>}
            </section>
          )}
        </div>

        <aside className="ta-rail">
          <div className="ta-panel">
            <div className="ta-panel-title"><span>Control room</span><button className="ta-panel-toggle" onClick={() => setSettingsOpen((v) => !v)}>{settingsOpen ? "Hide" : "Tune"}</button></div>
            <div className="ta-meter-card"><div className="ta-meter-ring" style={{ "--value": `${loading ? 62 : confidence}%`, "--ring": activeColor }}><div>{loading ? "…" : `${confidence}%`}</div></div><div><strong>{loading ? "Reading the room" : result ? "Signal locked" : "Ready for input"}</strong><span>{result ? `${tracks.length} tracks selected` : "Personalized to your prompt"}</span></div></div>
            {settingsOpen && <div className="ta-controls">
              <label>Artist familiarity <span>{intensity}</span><input type="range" min="0" max="100" value={intensity} onChange={(e) => setIntensity(+e.target.value)} /></label>
              <label>Nicheness <span>{nicheness}</span><input type="range" min="0" max="100" value={nicheness} onChange={(e) => setNicheness(+e.target.value)} /></label>
              <label>BPM bias <span>{bpm}</span><input type="range" min="0" max="100" value={bpm} onChange={(e) => setBpm(+e.target.value)} /></label>
              <label>Tracks <span>{trackCount}</span><input type="range" min="4" max="16" value={trackCount} onChange={(e) => setTrackCount(+e.target.value)} /></label>
              <label>Host accent <span className="ta-color-wrap"><input type="color" value={theme} onChange={(e) => setTheme(e.target.value)} /><code>{theme}</code></span></label>
            </div>}
          </div>
          <div className="ta-panel ta-philosophy"><span className="ta-eyebrow">MADE FOR THEMED.AI</span><h3>A music surface that belongs inside your desktop.</h3><p>No giant website chrome. No unnecessary navigation. Just the vibe engine, your library and a player that can speak to the host.</p><div className="ta-status"><span className="ta-live-dot" /> Host bridge ready</div></div>
          <div className="ta-panel ta-shortcuts"><div><span><Icons.Clock /> Fast launch</span><kbd>Ctrl K</kbd></div><div><span><Icons.Library /> Library</span><kbd>L</kbd></div></div>
        </aside>
      </section>

      <footer className="ta-footer"><span>VibeFinderAI × Themed.AI</span><span>frontend build 1.1</span></footer>

      {authOpen && <AuthModal mode={authMode} setMode={setAuthMode} form={authForm} setForm={setAuthForm} onSubmit={submitAuth} loading={loading} error={error} onClose={() => { setAuthOpen(false); setError(""); }} />}
      {libraryOpen && token && <Library token={token} refreshKey={libraryRefresh} onLoad={loadLibraryItem} onClose={() => setLibraryOpen(false)} />}
      {playerOpen && <MusicPlayer tracks={playerTracks} initialIndex={playerIndex} activeColor={activeColor} token={token} buildApiUrl={api} onClose={() => setPlayerOpen(false)} spotifyConnected={false} servicesConnected={{ youtube: true }} visibleServices={{ youtube: true }} />}
    </main>
  );
}
