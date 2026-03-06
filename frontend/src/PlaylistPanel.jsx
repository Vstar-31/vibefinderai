/**
 * PlaylistPanel.jsx
 * ─────────────────
 * VibeFinderAI — Playlist Save / Load / History / Share Panel
 * Place in: frontend/src/PlaylistPanel.jsx
 *
 * DROP-IN INTEGRATION into App.jsx:
 * ──────────────────────────────────
 * 1. Import at top:
 *      import PlaylistPanel from "./PlaylistPanel.jsx";
 *
 * 2. Add state in App():
 *      const [showPlaylistPanel, setShowPlaylistPanel] = useState(false);
 *
 * 3. Add trigger button (e.g. in the header area, near the auth button):
 *      {token && (
 *        <button style={S.authBtn(false)} onClick={() => setShowPlaylistPanel(true)}>
 *          ◎ Library
 *        </button>
 *      )}
 *
 * 4. Drop the panel just before </> closing:
 *      {token && showPlaylistPanel && (
 *        <PlaylistPanel
 *          token={token}
 *          currentResult={result}
 *          currentPrompt={prompt}
 *          buildApiUrl={buildApiUrl}
 *          onClose={() => setShowPlaylistPanel(false)}
 *          onLoadPlaylist={(tracks) => {
 *            // Optional: pre-fill the result with a saved playlist
 *            setResult({ ...result, tracks });
 *          }}
 *        />
 *      )}
 *
 * FEATURES
 * ────────
 *  • Save current result as a named playlist (with vibe tag + track count)
 *  • Browse + load saved playlists (inline preview)
 *  • Delete playlists with confirm guard
 *  • Toggle public/private + copy share URL
 *  • History tab: past vibe analyses with re-run link
 *  • Zero external deps — pure React + inline styles matching amber aesthetic
 */

import { useState, useEffect, useRef, useCallback } from "react";

/* ─── ICONS (self-contained SVG — no lucide needed) ─────────────── */
const Ico = {
  save:    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>,
  trash:   <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>,
  share:   <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>,
  load:    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 11 12 6 7 11"/><line x1="12" y1="18" x2="12" y2="6"/></svg>,
  lock:    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>,
  globe:   <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
  history: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><line x1="12" y1="7" x2="12" y2="12"/><line x1="12" y1="12" x2="15" y2="14"/></svg>,
  playlist:<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  copy:    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>,
  x:       <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>,
  check:   <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>,
};

/* ─── VIBE COLORS ────────────────────────────────────────────────── */
const VIBE_COLORS = {
  hype:"#f87171", calm:"#34d399", intense:"#f97316", chill:"#60a5fa",
  focus:"#22d3ee", euphoric:"#e879f9", soulful:"#fbbf24", retro:"#818cf8",
  dreamy:"#c084fc", cinematic:"#fb923c", dark:"#9ca3af", heartbreak:"#f472b6",
  hyperpop:"#d946ef", party:"#ec4899", country:"#d97706", tropical:"#14b8a6",
  industrial:"#6b7280", desi:"#e11d48", punjabi:"#fbbf24", rock:"#f87171",
  indie_folk:"#86efac", ambient:"#67e8f9", romantic:"#f9a8d4", happy:"#fde68a",
};

const vibeColor = (v) => VIBE_COLORS[v] || "#d97706";

/* ─── MINI HELPERS ───────────────────────────────────────────────── */
const fmtDate = (iso) => {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
};

const TOAST_DURATION = 2000;

/* ═══════════════════════════════════════════════════════════════════
   SAVE MODAL
═══════════════════════════════════════════════════════════════════ */
function SaveModal({ result, prompt, token, buildApiUrl, onSaved, onClose, filteredTracks }) {
  const tracksToSave = filteredTracks || result?.tracks || [];
  const [name, setName] = useState(
    result?.dominant_vibe
      ? `${result.dominant_vibe.charAt(0).toUpperCase() + result.dominant_vibe.slice(1)} Mix`
      : "My Playlist"
  );
  const [isPublic, setIsPublic] = useState(false);
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState("");

  const handleSave = async () => {
    if (!name.trim()) { setError("Give your playlist a name"); return; }
    setSaving(true); setError("");
    try {
      const res = await fetch(buildApiUrl("/api/playlist/save"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          name:         name.trim(),
          prompt:       prompt || null,
          dominant_vibe: result?.dominant_vibe || null,
          language:     result?.language || null,
          tracks:       tracksToSave,
          is_public:    isPublic,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || "Failed to save");
      }
      const saved = await res.json();
      onSaved(saved);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={S.modalOverlay} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={S.modal}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:20 }}>
          <div>
            <div style={S.modalTitle}>Save Playlist</div>
            <div style={S.modalSub}>{tracksToSave.length} tracks • {result?.dominant_vibe || "vibe"}{filteredTracks ? " · custom selection" : ""}</div>
          </div>
          <button onClick={onClose} style={S.iconBtn}>{Ico.x}</button>
        </div>

        <label style={S.formLabel}>Playlist Name</label>
        <input
          style={S.input}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          maxLength={80}
          autoFocus
          placeholder="Give it a name..."
        />

        <div style={{ display:"flex", alignItems:"center", gap:10, margin:"16px 0", cursor:"pointer" }}
             onClick={() => setIsPublic(p => !p)}>
          <div style={{
            width:18, height:18, borderRadius:4,
            background: isPublic ? "#d97706" : "transparent",
            border: `2px solid ${isPublic ? "#d97706" : "rgba(180,140,80,0.35)"}`,
            display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0,
            transition:"all 0.15s",
          }}>
            {isPublic && <span style={{color:"#000",fontSize:11,fontWeight:"bold"}}>✓</span>}
          </div>
          <div>
            <div style={{ fontSize:12, color:"#e8d5a3", fontFamily:"'DM Mono', monospace" }}>Make public</div>
            <div style={{ fontSize:10, color:"rgba(180,140,80,0.4)", letterSpacing:"0.05em" }}>
              Generates a shareable link anyone can view
            </div>
          </div>
          <span style={{ marginLeft:"auto", opacity:0.4 }}>{isPublic ? Ico.globe : Ico.lock}</span>
        </div>

        {error && <div style={S.errorMsg}>{error}</div>}

        <button
          onClick={handleSave}
          disabled={saving}
          style={S.primaryBtn(saving)}
        >
          {saving ? "Saving..." : "Save Playlist"}
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   PLAYLIST CARD
═══════════════════════════════════════════════════════════════════ */
function PlaylistCard({ playlist, onLoad, onDelete, onTogglePublic, buildApiUrl }) {
  const [expanded,   setExpanded]   = useState(false);
  const [shareToast, setShareToast] = useState(false);
  const [delConfirm, setDelConfirm] = useState(false);
  const [toggling,   setToggling]   = useState(false);
  const toastRef = useRef(null);

  const color = vibeColor(playlist.dominant_vibe);

  const copyShare = () => {
    const url = playlist.share_url || `${window.location.origin}/playlist/${playlist.share_token}`;
    navigator.clipboard?.writeText(url).then(() => {
      setShareToast(true);
      clearTimeout(toastRef.current);
      toastRef.current = setTimeout(() => setShareToast(false), TOAST_DURATION);
    });
  };

  const togglePublic = async () => {
    setToggling(true);
    await onTogglePublic(playlist.id, !playlist.is_public);
    setToggling(false);
  };

  return (
    <div style={{ ...S.card, borderLeftColor: color }}>
      {/* Header row */}
      <div style={{ display:"flex", alignItems:"center", gap:10, cursor:"pointer" }}
           onClick={() => setExpanded(e => !e)}>
        {/* Vibe dot */}
        <div style={{
          width:8, height:8, borderRadius:"50%",
          background: color, boxShadow:`0 0 8px ${color}88`, flexShrink:0,
        }} />

        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:13, fontFamily:"'DM Mono', monospace", color:"#e8d5a3",
                        fontWeight:600, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
            {playlist.name}
          </div>
          <div style={{ fontSize:10, color:"rgba(180,140,80,0.45)", letterSpacing:"0.08em",
                        display:"flex", gap:8, alignItems:"center", marginTop:2 }}>
            <span style={{ color, opacity:0.8 }}>{playlist.dominant_vibe || "—"}</span>
            <span>·</span>
            <span>{playlist.track_count} tracks</span>
            <span>·</span>
            <span>{fmtDate(playlist.created_at)}</span>
          </div>
        </div>

        {/* Privacy badge */}
        <span style={{ opacity:0.35, flexShrink:0 }}>
          {playlist.is_public ? Ico.globe : Ico.lock}
        </span>
      </div>

      {/* Expanded preview */}
      {expanded && (
        <div style={{ marginTop:12, paddingTop:12, borderTop:"1px solid rgba(120,80,20,0.2)" }}>
          {/* Track preview list (first 4) */}
          <div style={{ display:"flex", flexDirection:"column", gap:5, marginBottom:12 }}>
            {(playlist.tracks || []).slice(0, 4).map((t, i) => (
              <div key={i} style={{ display:"flex", alignItems:"center", gap:8 }}>
                <div style={{ width:18, height:18, borderRadius:3, overflow:"hidden", flexShrink:0,
                              background:"rgba(80,50,10,0.3)" }}>
                  {t.cover_art && <img src={t.cover_art} alt="" style={{width:"100%",height:"100%",objectFit:"cover"}} />}
                </div>
                <div style={{ flex:1, minWidth:0 }}>
                  <span style={{ fontSize:11, color:"#e8d5a3", fontFamily:"'DM Mono',monospace",
                                 overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
                                 display:"block" }}>
                    {t.title}
                  </span>
                  <span style={{ fontSize:10, color:"rgba(180,140,80,0.4)" }}>{t.artist}</span>
                </div>
              </div>
            ))}
            {playlist.track_count > 4 && (
              <div style={{ fontSize:10, color:"rgba(180,140,80,0.35)", paddingLeft:26 }}>
                +{playlist.track_count - 4} more tracks
              </div>
            )}
          </div>

          {/* Prompt snippet */}
          {playlist.prompt && (
            <div style={{ fontSize:10, color:"rgba(180,140,80,0.35)", fontStyle:"italic",
                          marginBottom:12, lineHeight:1.5,
                          overflow:"hidden", display:"-webkit-box",
                          WebkitLineClamp:2, WebkitBoxOrient:"vertical" }}>
              "{playlist.prompt}"
            </div>
          )}

          {/* Action row */}
          <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
            <button style={S.actionBtn(color)} onClick={() => onLoad(playlist)}>
              {Ico.load} Load
            </button>

            {playlist.is_public && (
              <button style={S.actionBtn(shareToast ? "#34d399" : "#d97706")} onClick={copyShare}>
                {shareToast ? Ico.check : Ico.copy}
                {shareToast ? "Copied!" : "Copy Link"}
              </button>
            )}

            <button
              style={{ ...S.actionBtn("rgba(180,140,80,0.3)"), opacity: toggling ? 0.5 : 1 }}
              onClick={togglePublic}
              disabled={toggling}
              title={playlist.is_public ? "Make private" : "Make public"}
            >
              {playlist.is_public ? Ico.lock : Ico.globe}
              {playlist.is_public ? "Private" : "Public"}
            </button>

            {!delConfirm ? (
              <button style={{ ...S.actionBtn("rgba(239,68,68,0.15)"), color:"#ef4444",
                               marginLeft:"auto" }} onClick={() => setDelConfirm(true)}>
                {Ico.trash}
              </button>
            ) : (
              <div style={{ display:"flex", gap:6, marginLeft:"auto", alignItems:"center" }}>
                <span style={{ fontSize:10, color:"#ef4444" }}>Delete?</span>
                <button style={{ ...S.actionBtn("#ef4444"), padding:"4px 10px" }}
                        onClick={() => { setDelConfirm(false); onDelete(playlist.id); }}>
                  Yes
                </button>
                <button style={{ ...S.actionBtn("rgba(180,140,80,0.2)"), padding:"4px 10px" }}
                        onClick={() => setDelConfirm(false)}>
                  No
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   HISTORY ITEM
═══════════════════════════════════════════════════════════════════ */
function HistoryItem({ entry, onReRun }) {
  const color = vibeColor(entry.dominant_vibe);
  return (
    <div style={{ ...S.card, borderLeftColor: color, padding:"12px 14px" }}>
      <div style={{ display:"flex", alignItems:"flex-start", gap:10 }}>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:11, color:"rgba(180,140,80,0.4)", marginBottom:4,
                        letterSpacing:"0.05em", textTransform:"uppercase",
                        display:"flex", gap:8, alignItems:"center" }}>
            <span style={{ color, opacity:0.9 }}>{entry.dominant_vibe}</span>
            {entry.secondary_vibe && <><span>·</span><span style={{opacity:0.6}}>{entry.secondary_vibe}</span></>}
            <span style={{ marginLeft:"auto" }}>{fmtDate(entry.created_at)}</span>
          </div>
          <div style={{ fontSize:12, color:"#e8d5a3", fontFamily:"'DM Mono',monospace",
                        lineHeight:1.5, overflow:"hidden", display:"-webkit-box",
                        WebkitLineClamp:2, WebkitBoxOrient:"vertical" }}>
            "{entry.prompt}"
          </div>
          <div style={{ fontSize:10, color:"rgba(180,140,80,0.35)", marginTop:4 }}>
            {entry.track_count} tracks
            {entry.detected_artist && ` · Artist: ${entry.detected_artist}`}
            {entry.used_fallback && " · ⚠ fallback"}
          </div>
        </div>

        <button
          style={{ ...S.actionBtn(color), flexShrink:0, padding:"5px 10px" }}
          onClick={() => onReRun(entry.prompt)}
          title="Re-run this prompt"
        >
          ↺
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   MAIN PANEL
═══════════════════════════════════════════════════════════════════ */
export default function PlaylistPanel({
  token,
  currentResult,
  currentPrompt,
  buildApiUrl,
  onClose,
  onLoadPlaylist,
  onReRunPrompt,
  selectedTracks,   // Set of "title|artist" keys — if non-empty, save only these
  activeColor,
}) {
  const [tab,         setTab]         = useState("playlists");   // "playlists" | "history"
  const [playlists,   setPlaylists]   = useState([]);
  const [history,     setHistory]     = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState("");
  const [showSave,    setShowSave]    = useState(false);

  // If caller passed a selection set, filter currentResult down to only those tracks
  const filteredTracks = (selectedTracks && selectedTracks.size > 0)
    ? (currentResult?.tracks || []).filter(t => selectedTracks.has(`${t.title}|${t.artist}`))
    : null;
  const [saveToast,   setSaveToast]   = useState(false);
  const saveToastRef                  = useRef(null);

  // ── Vibe of the Day ───────────────────────────────────────
  const [vibeOfDay,   setVibeOfDay]   = useState(null);  // {prompt, dominant_vibe, share_url, name}
  const [recentVibes, setRecentVibes] = useState([]);    // public feed — [{prompt, dominant_vibe, name, share_url}]

  // Scroll lock on mount
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  const fetchPlaylists = useCallback(async () => {
    try {
      const res = await fetch(buildApiUrl("/api/playlist/list?limit=50"), {
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load playlists");
      const data = await res.json();
      setPlaylists(data.playlists || []);
    } catch (e) {
      setError(e.message);
    }
  }, [token, buildApiUrl]);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(buildApiUrl("/api/user/history?limit=30"), {
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load history");
      const data = await res.json();
      setHistory(data.history || []);
    } catch (e) {
      setError(e.message);
    }
  }, [token, buildApiUrl]);

  useEffect(() => {
    setLoading(true);
    setError("");
    const load = async () => {
      await Promise.all([fetchPlaylists(), fetchHistory()]);
      // Vibe of day + recent public feed — fire and forget, no loading gate
      fetch(buildApiUrl("/api/vibes/today"))
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setVibeOfDay(d); })
        .catch(() => {});
      fetch(buildApiUrl("/api/vibes/feed?limit=6"))
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.vibes) setRecentVibes(d.vibes); })
        .catch(() => {});
      setLoading(false);
    };
    load();
  }, [fetchPlaylists, fetchHistory]);

  const handleSaved = (playlist) => {
    setPlaylists(prev => [playlist, ...prev]);
    setShowSave(false);
    setSaveToast(true);
    clearTimeout(saveToastRef.current);
    saveToastRef.current = setTimeout(() => setSaveToast(false), TOAST_DURATION);
  };

  const handleDelete = async (id) => {
    try {
      await fetch(buildApiUrl(`/api/playlist/${id}`), {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` },
      });
      setPlaylists(prev => prev.filter(p => p.id !== id));
    } catch (e) {
      setError("Delete failed");
    }
  };

  const handleTogglePublic = async (id, isPublic) => {
    try {
      const res = await fetch(buildApiUrl(`/api/playlist/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ is_public: isPublic }),
      });
      if (!res.ok) throw new Error("Update failed");
      const updated = await res.json();
      setPlaylists(prev => prev.map(p => p.id === id ? updated : p));
    } catch (e) {
      setError("Could not update visibility");
    }
  };

  const handleLoadPlaylist = (playlist) => {
    if (onLoadPlaylist) onLoadPlaylist(playlist.tracks);
    onClose();
  };

  const handleReRun = (prompt) => {
    if (onReRunPrompt) onReRunPrompt(prompt);
    onClose();
  };

  return (
    <>
      {/* ── BACKDROP ── */}
      <div style={S.backdrop} onClick={onClose} />

      {/* ── DRAWER ── */}
      <div style={S.drawer}>

        {/* Header */}
        <div style={S.drawerHeader}>
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <div style={S.headerIcon}>{tab === "playlists" ? Ico.playlist : Ico.history}</div>
            <div>
              <div style={S.drawerTitle}>Library</div>
              <div style={S.drawerSub}>
                {tab === "playlists"
                  ? `${playlists.length} saved playlists`
                  : `${history.length} analyses`}
              </div>
            </div>
          </div>
          <button style={S.iconBtn} onClick={onClose}>{Ico.x}</button>
        </div>

        {/* Tab bar */}
        <div style={S.tabBar}>
          {[["playlists", Ico.playlist, "Playlists"], ["history", Ico.history, "History"]].map(
            ([key, icon, label]) => (
              <button
                key={key}
                style={S.tab(tab === key)}
                onClick={() => setTab(key)}
              >
                {icon} {label}
              </button>
            )
          )}
        </div>

        {/* ── VIBE OF THE DAY ────────────────────────────────── */}
        {tab === "playlists" && vibeOfDay && (
          <div style={{ margin: "0 20px 12px", padding: "12px 14px", background: `${vibeColor(vibeOfDay.dominant_vibe)}0d`, border: `1px solid ${vibeColor(vibeOfDay.dominant_vibe)}33`, borderRadius: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: vibeColor(vibeOfDay.dominant_vibe), boxShadow: `0 0 6px ${vibeColor(vibeOfDay.dominant_vibe)}` }} />
              <span style={{ fontSize: 9, color: "rgba(180,140,80,0.45)", letterSpacing: "0.2em", textTransform: "uppercase" }}>Vibe of the Day</span>
            </div>
            <div style={{ fontSize: 12, color: "#e8d5a3", fontFamily: "'DM Mono', monospace", lineHeight: 1.5, marginBottom: 8, fontStyle: "italic" }}>
              "{vibeOfDay.prompt}"
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 10, color: vibeColor(vibeOfDay.dominant_vibe), letterSpacing: "0.08em" }}>{vibeOfDay.dominant_vibe}</span>
              {vibeOfDay.share_url && (
                <a href={vibeOfDay.share_url} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", letterSpacing: "0.1em", textTransform: "uppercase", textDecoration: "none", border: "1px solid rgba(120,80,20,0.3)", padding: "3px 8px", borderRadius: 4 }}>
                  Listen →
                </a>
              )}
            </div>
          </div>
        )}

        {/* ── WHAT PEOPLE ARE VIBING TO (public feed) ────────── */}
        {tab === "playlists" && recentVibes.length > 0 && (
          <div style={{ margin: "0 20px 12px" }}>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.3)", letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 8 }}>
              What people are vibing to
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {recentVibes.map((v, i) => (
                <a key={i} href={v.share_url || "#"} target="_blank" rel="noopener noreferrer"
                  style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 10px", background: `${vibeColor(v.dominant_vibe)}0d`, border: `1px solid ${vibeColor(v.dominant_vibe)}2a`, borderRadius: 20, textDecoration: "none", transition: "all 0.15s" }}>
                  <div style={{ width: 5, height: 5, borderRadius: "50%", background: vibeColor(v.dominant_vibe), flexShrink: 0 }} />
                  <span style={{ fontSize: 10, color: "rgba(180,140,80,0.6)", fontFamily: "'DM Mono', monospace", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {v.prompt?.length > 35 ? v.prompt.slice(0, 35) + "…" : v.prompt}
                  </span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Save current button — only on playlists tab and when we have results */}
        {tab === "playlists" && currentResult?.tracks?.length > 0 && (
          <div style={{ padding:"0 20px 16px" }}>
            <button style={S.saveCurrentBtn} onClick={() => setShowSave(true)}>
              {Ico.save}
              {filteredTracks ? `Save ${filteredTracks.length} selected tracks` : "Save current playlist"}
              <span style={{ marginLeft:"auto", fontSize:10, opacity:0.5 }}>
                {filteredTracks ? `${filteredTracks.length} / ${currentResult.tracks.length}` : `${currentResult.tracks.length} tracks`}
              </span>
            </button>
          </div>
        )}

        {/* Save toast */}
        {saveToast && (
          <div style={S.toast}>
            {Ico.check} Playlist saved!
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ ...S.errorMsg, margin:"0 20px 12px" }}>
            {error}
          </div>
        )}

        {/* Body */}
        <div style={S.body}>
          {loading ? (
            <div style={S.empty}>Loading...</div>
          ) : tab === "playlists" ? (
            playlists.length === 0 ? (
              <div style={S.emptyState}>
                <div style={{ fontSize:32, marginBottom:12, opacity:0.3 }}>◎</div>
                <div style={{ fontSize:13, color:"rgba(180,140,80,0.5)", fontFamily:"'DM Mono',monospace" }}>
                  No saved playlists yet
                </div>
                {currentResult?.tracks?.length > 0 && (
                  <div style={{ fontSize:11, color:"rgba(180,140,80,0.3)", marginTop:6 }}>
                    Run an analysis and hit "Save current playlist" to start
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                {playlists.map(p => (
                  <PlaylistCard
                    key={p.id}
                    playlist={p}
                    buildApiUrl={buildApiUrl}
                    onLoad={handleLoadPlaylist}
                    onDelete={handleDelete}
                    onTogglePublic={handleTogglePublic}
                  />
                ))}
              </div>
            )
          ) : (
            history.length === 0 ? (
              <div style={S.emptyState}>
                <div style={{ fontSize:32, marginBottom:12, opacity:0.3 }}>◷</div>
                <div style={{ fontSize:13, color:"rgba(180,140,80,0.5)", fontFamily:"'DM Mono',monospace" }}>
                  No analysis history yet
                </div>
              </div>
            ) : (
              <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                {history.map(h => (
                  <HistoryItem key={h.id} entry={h} onReRun={handleReRun} />
                ))}
              </div>
            )
          )}
        </div>

        {/* Footer */}
        <div style={S.footer}>
          <span>
            {tab === "playlists"
              ? `${playlists.length}/50 playlists used`
              : `${history.length} past analyses`}
          </span>
          {tab === "playlists" && playlists.length > 0 && (
            <span style={{ opacity:0.4 }}>
              {playlists.reduce((s, p) => s + p.track_count, 0)} total tracks
            </span>
          )}
        </div>
      </div>

      {/* Save modal */}
      {showSave && (
        <SaveModal
          result={currentResult}
          prompt={currentPrompt}
          token={token}
          buildApiUrl={buildApiUrl}
          onSaved={handleSaved}
          onClose={() => setShowSave(false)}
          filteredTracks={filteredTracks}
        />
      )}
    </>
  );
}

/* ─── STYLES ─────────────────────────────────────────────────────── */
const S = {
  backdrop: {
    position: "fixed", inset: 0, zIndex: 40,
    background: "rgba(4,2,1,0.6)", backdropFilter: "blur(4px)",
  },
  drawer: {
    position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 41,
    width: "min(420px, 100vw)",
    background: "linear-gradient(180deg, #0d0700 0%, #0a0500 100%)",
    borderLeft: "1px solid rgba(120,80,20,0.35)",
    display: "flex", flexDirection: "column",
    boxShadow: "-20px 0 60px rgba(0,0,0,0.7)",
    animation: "slideIn 0.22s cubic-bezier(0.23,1,0.32,1)",
  },
  drawerHeader: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "24px 20px 16px",
    borderBottom: "1px solid rgba(120,80,20,0.2)",
  },
  headerIcon: {
    width: 34, height: 34, borderRadius: 8,
    background: "rgba(180,140,80,0.08)",
    border: "1px solid rgba(120,80,20,0.25)",
    display: "flex", alignItems: "center", justifyContent: "center",
    color: "#d97706",
  },
  drawerTitle: {
    fontFamily: "'Playfair Display', serif",
    fontSize: 18, fontWeight: 700, color: "#fde68a",
  },
  drawerSub: {
    fontSize: 10, color: "rgba(180,140,80,0.4)",
    letterSpacing: "0.15em", textTransform: "uppercase", marginTop: 2,
  },
  tabBar: {
    display: "flex", padding: "12px 20px 0",
    gap: 8, borderBottom: "1px solid rgba(120,80,20,0.15)",
  },
  tab: (active) => ({
    display: "flex", alignItems: "center", gap: 6,
    padding: "8px 14px", borderRadius: "8px 8px 0 0",
    fontFamily: "'DM Mono', monospace", fontSize: 11,
    letterSpacing: "0.1em", textTransform: "uppercase",
    cursor: "pointer", border: "none",
    background: active ? "rgba(180,140,80,0.1)" : "transparent",
    color: active ? "#d97706" : "rgba(180,140,80,0.4)",
    borderBottom: active ? "2px solid #d97706" : "2px solid transparent",
    transition: "all 0.15s",
  }),
  saveCurrentBtn: {
    width: "100%", display: "flex", alignItems: "center", gap: 8,
    padding: "10px 14px",
    background: "rgba(180,140,80,0.06)",
    border: "1px dashed rgba(180,140,80,0.3)", borderRadius: 8,
    color: "rgba(180,140,80,0.7)", fontFamily: "'DM Mono', monospace",
    fontSize: 11, letterSpacing: "0.08em", cursor: "pointer",
    transition: "all 0.15s",
  },
  toast: {
    display: "flex", alignItems: "center", gap: 6,
    margin: "0 20px 12px",
    padding: "8px 12px", borderRadius: 6,
    background: "rgba(52,211,153,0.1)",
    border: "1px solid rgba(52,211,153,0.3)",
    color: "#34d399", fontSize: 11,
    fontFamily: "'DM Mono', monospace",
    animation: "fadeIn 0.2s ease",
  },
  body: {
    flex: 1, overflowY: "auto", padding: "16px 20px 8px",
    scrollbarWidth: "thin", scrollbarColor: "rgba(120,80,20,0.3) transparent",
  },
  card: {
    padding: "12px 14px",
    background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(120,80,20,0.2)",
    borderLeft: "3px solid #d97706",
    borderRadius: 8, cursor: "default",
    transition: "border-color 0.2s",
  },
  actionBtn: (color) => ({
    display: "flex", alignItems: "center", gap: 5,
    padding: "5px 10px", borderRadius: 5,
    background: `${color}15`,
    border: `1px solid ${color}40`,
    color: color, fontFamily: "'DM Mono', monospace",
    fontSize: 10, letterSpacing: "0.08em",
    cursor: "pointer", transition: "all 0.15s",
  }),
  iconBtn: {
    display: "flex", alignItems: "center", justifyContent: "center",
    width: 30, height: 30, borderRadius: 6,
    background: "transparent", border: "1px solid rgba(120,80,20,0.25)",
    color: "rgba(180,140,80,0.5)", cursor: "pointer",
    transition: "all 0.15s",
  },
  emptyState: {
    display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center",
    padding: "48px 20px", textAlign: "center",
  },
  empty: {
    padding: "40px", textAlign: "center",
    color: "rgba(180,140,80,0.4)",
    fontFamily: "'DM Mono', monospace", fontSize: 12,
  },
  footer: {
    display: "flex", justifyContent: "space-between",
    padding: "12px 20px",
    borderTop: "1px solid rgba(120,80,20,0.15)",
    fontSize: 10, color: "rgba(180,140,80,0.35)",
    fontFamily: "'DM Mono', monospace",
    letterSpacing: "0.08em",
  },
  // Save modal
  modalOverlay: {
    position: "fixed", inset: 0, zIndex: 60,
    display: "flex", alignItems: "center", justifyContent: "center",
    padding: 16, background: "rgba(4,2,1,0.88)", backdropFilter: "blur(8px)",
  },
  modal: {
    width: "100%", maxWidth: 380,
    padding: "28px 24px",
    background: "linear-gradient(160deg, #120900, #0a0500)",
    border: "1px solid rgba(180,140,80,0.25)",
    borderRadius: 12,
    boxShadow: "0 20px 60px rgba(0,0,0,0.8)",
  },
  modalTitle: {
    fontFamily: "'Playfair Display', serif",
    fontSize: 20, fontWeight: 700, color: "#fde68a",
  },
  modalSub: {
    fontSize: 10, color: "rgba(180,140,80,0.4)",
    letterSpacing: "0.12em", textTransform: "uppercase", marginTop: 4,
  },
  formLabel: {
    display: "block", fontSize: 10, letterSpacing: "0.18em",
    textTransform: "uppercase", color: "rgba(180,140,80,0.5)",
    marginBottom: 6, fontFamily: "'DM Mono', monospace",
  },
  input: {
    width: "100%", padding: "10px 12px",
    background: "rgba(5,3,1,0.8)",
    border: "1px solid rgba(160,110,30,0.4)",
    borderRadius: 8, color: "#e8d5a3",
    fontFamily: "'DM Mono', monospace", fontSize: 13,
    outline: "none",
    boxSizing: "border-box",
  },
  errorMsg: {
    padding: "8px 12px", borderRadius: 6,
    background: "rgba(60,10,10,0.5)",
    border: "1px solid rgba(180,40,40,0.3)",
    color: "#f87171", fontSize: 11,
    fontFamily: "'DM Mono', monospace",
  },
  primaryBtn: (disabled) => ({
    width: "100%", padding: "11px",
    background: disabled ? "rgba(50,30,8,0.4)" : "linear-gradient(135deg, #92400e, #d97706)",
    border: "1px solid rgba(251,191,36,0.25)",
    borderRadius: 8, color: disabled ? "rgba(120,80,20,0.5)" : "#fef3c7",
    fontFamily: "'DM Mono', monospace", fontSize: 11,
    fontWeight: 500, letterSpacing: "0.15em", textTransform: "uppercase",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "opacity 0.2s",
    marginTop: 20,
  }),
};

/*
 * Add this CSS somewhere global (e.g. index.css) for the slide animation:
 *
 * @keyframes slideIn {
 *   from { transform: translateX(100%); opacity: 0; }
 *   to   { transform: translateX(0);    opacity: 1; }
 * }
 * @keyframes fadeIn {
 *   from { opacity: 0; }
 *   to   { opacity: 1; }
 * }
 */
