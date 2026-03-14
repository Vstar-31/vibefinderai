/**
 * MusicPlayer.jsx
 * ───────────────
 * VibeFinderAI — Full-featured floating music player
 *
 * FEATURES
 * ────────
 *  • Play / Pause / Previous / Next
 *  • Shuffle mode (randomises queue order)
 *  • Repeat (off → repeat-all → repeat-one)
 *  • Scrubable progress bar with elapsed / remaining time
 *  • Volume slider with mute toggle
 *  • Mini album art + track info
 *  • Queue view (tap track to jump)
 *  • Spotify export button (if connected)
 *  • Collapses to mini bar when minimised
 *
 * PROPS
 * ─────
 *  tracks         – array of track objects from result
 *  initialIndex   – which track to start on (default 0)
 *  activeColor    – theme accent colour
 *  onClose        – called when player is dismissed
 *  token          – VibeFinder JWT (for Spotify export)
 *  buildApiUrl    – URL builder
 *  spotifyConnected – bool
 *  onExportSpotify  – called with tracks array to trigger export flow
 *
 * USAGE
 * ─────
 *  import MusicPlayer from "./MusicPlayer.jsx";
 *  <MusicPlayer tracks={result.tracks} activeColor={activeColor} onClose={...} />
 */

import { useState, useEffect, useRef, useCallback } from "react";

/* ── ICONS ─────────────────────────────────────────────────────── */
const Ic = {
  play:    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>,
  pause:   <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>,
  prev:    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>,
  next:    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>,
  shuffle: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>,
  repeat:  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>,
  repeat1: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/><text x="11" y="13" fontSize="7" fill="currentColor" stroke="none" fontWeight="bold">1</text></svg>,
  volHigh: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>,
  volMute: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>,
  queue:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  spotify: <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>,
  close:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>,
  chevron: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="18 15 12 9 6 15"/></svg>,
  disc:    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>,
};

const fmt = (ms) => {
  if (!ms || isNaN(ms)) return "0:00";
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

// ── Shuffle helper ─────────────────────────────────────────────────
const shuffleArray = (arr) => {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

export default function MusicPlayer({
  tracks = [],
  initialIndex = 0,
  activeColor = "#d97706",
  onClose,
  token,
  buildApiUrl,
  spotifyConnected = false,
  onExportSpotify,
  // Services integration
  servicesConnected = {},   // {lastfm, youtube}
  visibleServices   = {},   // which to show buttons for
  onServiceAction,          // fn(service, action, track) → Promise
}) {
  const audioRef    = useRef(null);
  const progressRef = useRef(null);

  const [queue, setQueue]           = useState(() => tracks.map((t, i) => ({ ...t, _origIdx: i })));
  const [queueIdx, setQueueIdx]     = useState(initialIndex);
  const [isPlaying, setIsPlaying]   = useState(false);
  const [progress, setProgress]     = useState(0);       // 0–1
  const [duration, setDuration]     = useState(0);       // ms
  const [elapsed, setElapsed]       = useState(0);       // ms
  const [volume, setVolume]         = useState(0.7);
  const [muted, setMuted]           = useState(false);
  const [shuffle, setShuffle]       = useState(false);
  const [repeat, setRepeat]         = useState("off");   // off | all | one
  const [showQueue, setShowQueue]   = useState(false);
  const [minimised, setMinimised]   = useState(false);
  const [exporting, setExporting]   = useState(false);
  const [exportDone, setExportDone] = useState(null);    // {url} | null
  const [ytVideoId,  setYtVideoId]  = useState(null);    // YouTube video ID for full-length mode
  const [ytLoading,  setYtLoading]  = useState(false);   // searching YouTube
  const [serviceToast, setServiceToast] = useState(null);

  const track = queue[queueIdx] || queue[0];

  // ── Load + play track when queueIdx changes ──────────────────────
  useEffect(() => {
    if (!audioRef.current || !track?.preview_url) {
      setIsPlaying(false);
      return;
    }
    audioRef.current.src    = track.preview_url;
    audioRef.current.volume = muted ? 0 : volume;
    audioRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
  }, [queueIdx, queue]);

  // ── Audio element setup ──────────────────────────────────────────
  useEffect(() => {
    const audio = new Audio();
    audio.volume = volume;
    audioRef.current = audio;

    audio.addEventListener("timeupdate", () => {
      setElapsed(audio.currentTime * 1000);
      setProgress(audio.duration ? audio.currentTime / audio.duration : 0);
    });
    audio.addEventListener("durationchange", () => {
      setDuration(audio.duration * 1000);
    });
    audio.addEventListener("ended", () => {
      handleNext();
    });
    audio.addEventListener("pause",  () => setIsPlaying(false));
    audio.addEventListener("play",   () => setIsPlaying(true));

    // Auto-start on mount
    if (tracks[initialIndex]?.preview_url) {
      audio.src = tracks[initialIndex].preview_url;
      audio.play().catch(() => {});
    }

    return () => {
      audio.pause();
      audio.src = "";
    };
  }, []);

  // ── Sync volume ──────────────────────────────────────────────────
  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = muted ? 0 : volume;
  }, [volume, muted]);

  // ── Shuffle: rebuild queue keeping current track first ───────────
  const toggleShuffle = () => {
    const currentTrack = queue[queueIdx];
    if (!shuffle) {
      const rest = queue.filter((_, i) => i !== queueIdx);
      const newQ = [currentTrack, ...shuffleArray(rest)];
      setQueue(newQ);
      setQueueIdx(0);
    } else {
      // Restore original order
      const restored = [...tracks].map((t, i) => ({ ...t, _origIdx: i }));
      const origIdx  = currentTrack._origIdx;
      setQueue(restored);
      setQueueIdx(origIdx);
    }
    setShuffle(s => !s);
  };

  const handleNext = useCallback(() => {
    setQueueIdx(i => {
      if (repeat === "one") return i; // stays on same track
      if (i >= queue.length - 1) {
        return repeat === "all" ? 0 : i; // loop or stop
      }
      return i + 1;
    });
  }, [queue.length, repeat]);

  const handlePrev = () => {
    if (audioRef.current && audioRef.current.currentTime > 3) {
      audioRef.current.currentTime = 0;
      return;
    }
    setQueueIdx(i => Math.max(0, i - 1));
  };

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (!track?.preview_url) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      if (!audioRef.current.src) audioRef.current.src = track.preview_url;
      audioRef.current.play().catch(() => {});
    }
  };

  const seekTo = (e) => {
    if (!audioRef.current || !audioRef.current.duration) return;
    const rect = progressRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audioRef.current.currentTime = ratio * audioRef.current.duration;
  };

  const cycleRepeat = () => {
    setRepeat(r => r === "off" ? "all" : r === "all" ? "one" : "off");
  };

  const handleExport = async () => {
    if (!onExportSpotify) return;
    setExporting(true);
    try {
      const result = await onExportSpotify(tracks);
      setExportDone(result);
    } catch (e) {
      setExportDone({ error: e.message });
    } finally {
      setExporting(false);
    }
  };

  // ── YouTube full-length playback ────────────────────────────────
  const loadYouTube = async (t) => {
    if (!buildApiUrl || ytLoading) return;
    setYtLoading(true);
    setYtVideoId(null);
    try {
      const q = encodeURIComponent(`${t.title} ${t.artist} official audio`);
      const res = await fetch(buildApiUrl(`/api/services/youtube/search?q=${q}`));
      const data = await res.json();
      if (data.found) setYtVideoId(data.video_id);
    } catch {}
    setYtLoading(false);
  };

  // Load YouTube when track changes if YouTube is visible
  useEffect(() => {
    if (visibleServices?.youtube && track) {
      loadYouTube(track);
    } else {
      setYtVideoId(null);
    }
  }, [queueIdx]); // eslint-disable-line

  // ── Service quick actions (love, like, scrobble) ──────────────
  const serviceAction = async (service, action) => {
    if (!onServiceAction) return;
    try {
      await onServiceAction(service, action, track);
      setServiceToast(`♥ ${action === "love" ? "Loved" : action === "scrobble" ? "Scrobbled" : "Saved"} on ${service}`);
      setTimeout(() => setServiceToast(null), 2500);
    } catch (e) {
      setServiceToast(`⚠ ${service} action failed`);
      setTimeout(() => setServiceToast(null), 3000);
    }
  };

  const hasPreview = !!track?.preview_url;

  // ── MINIMISED BAR ────────────────────────────────────────────────
  if (minimised) {
    return (
      <div style={{
        position: "fixed", bottom: 16, left: "50%", transform: "translateX(-50%)",
        zIndex: 200, display: "flex", alignItems: "center", gap: "10px",
        padding: "8px 16px",
        background: "linear-gradient(135deg, #120900, #0a0500)",
        border: `1px solid ${activeColor}55`,
        borderRadius: "40px",
        boxShadow: `0 8px 32px rgba(0,0,0,0.8), 0 0 20px ${activeColor}22`,
        backdropFilter: "blur(12px)",
        cursor: "pointer",
        maxWidth: "90vw",
      }}>
        {track?.cover_art
          ? <img src={track.cover_art} alt="" style={{ width: 28, height: 28, borderRadius: 4, flexShrink: 0 }} />
          : <div style={{ width: 28, height: 28, borderRadius: 4, background: "rgba(120,80,20,0.3)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{Ic.disc}</div>
        }
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, color: "#fde68a", fontFamily: "'Playfair Display', serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 140 }}>{track?.title}</div>
          <div style={{ fontSize: 9, color: "rgba(180,140,80,0.5)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 140 }}>{track?.artist}</div>
        </div>
        <button onClick={(e) => { e.stopPropagation(); togglePlay(); }} style={{ ...S.ctrl, width: 28, height: 28 }}>
          {isPlaying ? Ic.pause : Ic.play}
        </button>
        <button onClick={(e) => { e.stopPropagation(); handleNext(); }} style={{ ...S.ctrl, width: 24, height: 24 }}>
          {Ic.next}
        </button>
        <button onClick={() => setMinimised(false)} style={{ ...S.ctrl, opacity: 0.5, width: 22, height: 22 }}>
          {Ic.chevron}
        </button>
      </div>
    );
  }

  // ── FULL PLAYER ──────────────────────────────────────────────────
  return (
    <div style={{
      position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 200,
      background: "linear-gradient(180deg, rgba(10,5,0,0.97) 0%, #060300 100%)",
      borderTop: `1px solid ${activeColor}44`,
      boxShadow: `0 -8px 40px rgba(0,0,0,0.8), 0 0 30px ${activeColor}18`,
      backdropFilter: "blur(20px)",
      padding: "0 0 env(safe-area-inset-bottom, 0)",
    }}>
      {/* ── PROGRESS BAR ── */}
      <div
        ref={progressRef}
        onClick={seekTo}
        style={{
          height: 3, background: "rgba(120,80,20,0.2)", cursor: "pointer",
          position: "relative",
        }}
      >
        <div style={{
          height: "100%", width: `${progress * 100}%`,
          background: `linear-gradient(90deg, ${activeColor}88, ${activeColor})`,
          transition: "width 0.1s linear",
        }} />
        <div style={{
          position: "absolute", top: -3, left: `${progress * 100}%`,
          transform: "translateX(-50%)",
          width: 9, height: 9, borderRadius: "50%",
          background: activeColor,
          boxShadow: `0 0 6px ${activeColor}`,
          transition: "left 0.1s linear",
        }} />
      </div>

      <div style={{ padding: "10px 20px 12px", maxWidth: 900, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>

          {/* ── ALBUM ART ── */}
          <div style={{ position: "relative", flexShrink: 0 }}>
            {track?.cover_art
              ? <img src={track.cover_art} alt="" style={{
                  width: 48, height: 48, borderRadius: 6,
                  boxShadow: `0 0 12px ${activeColor}44`,
                  border: `1px solid ${activeColor}33`,
                }} />
              : <div style={{
                  width: 48, height: 48, borderRadius: 6,
                  background: "rgba(120,80,20,0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "rgba(180,140,80,0.4)",
                  border: `1px solid rgba(120,80,20,0.3)`,
                }}>{Ic.disc}</div>
            }
            {isPlaying && (
              <div style={{
                position: "absolute", inset: 0, borderRadius: 6,
                border: `1.5px solid ${activeColor}66`,
                animation: "pulseRing 2s ease infinite",
              }} />
            )}
          </div>

          {/* ── TRACK INFO ── */}
          <div style={{ flex: "0 0 auto", minWidth: 0, maxWidth: 160 }}>
            <div style={{
              fontSize: 13, fontWeight: 700, color: "#fde68a",
              fontFamily: "'Playfair Display', serif",
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            }}>{track?.title || "—"}</div>
            <div style={{
              fontSize: 10, color: "rgba(180,140,80,0.6)",
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              letterSpacing: "0.04em",
            }}>{track?.artist || ""}</div>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.3)", marginTop: 1 }}>
              {fmt(elapsed)} / {fmt(duration || track?.duration_ms)}
            </div>
          </div>

          {/* ── CENTRE CONTROLS ── */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {/* Shuffle */}
              <button
                onClick={toggleShuffle}
                style={{ ...S.ctrl, color: shuffle ? activeColor : "rgba(180,140,80,0.35)" }}
                title="Shuffle"
              >{Ic.shuffle}</button>

              {/* Prev */}
              <button onClick={handlePrev} style={S.ctrl} title="Previous">{Ic.prev}</button>

              {/* Play/Pause */}
              <button
                onClick={togglePlay}
                disabled={!hasPreview}
                style={{
                  ...S.ctrl,
                  width: 42, height: 42, borderRadius: "50%",
                  background: hasPreview
                    ? `linear-gradient(135deg, ${activeColor}cc, ${activeColor})`
                    : "rgba(60,40,10,0.4)",
                  border: `1px solid ${activeColor}55`,
                  color: hasPreview ? "#000" : "rgba(120,80,20,0.3)",
                  boxShadow: hasPreview ? `0 0 16px ${activeColor}44` : "none",
                  fontSize: 16,
                  opacity: hasPreview ? 1 : 0.5,
                }}
                title={hasPreview ? (isPlaying ? "Pause" : "Play") : "No preview available"}
              >
                {isPlaying ? Ic.pause : Ic.play}
              </button>

              {/* Next */}
              <button onClick={handleNext} style={S.ctrl} title="Next">{Ic.next}</button>

              {/* Repeat */}
              <button
                onClick={cycleRepeat}
                style={{ ...S.ctrl, color: repeat !== "off" ? activeColor : "rgba(180,140,80,0.35)", position: "relative" }}
                title={`Repeat: ${repeat}`}
              >
                {repeat === "one" ? Ic.repeat1 : Ic.repeat}
                {repeat === "one" && (
                  <span style={{ position: "absolute", top: -4, right: -4, fontSize: 7, color: activeColor, fontWeight: "bold" }}>1</span>
                )}
              </button>
            </div>

            {/* No preview notice */}
            {!hasPreview && !ytVideoId && (
              <div style={{ fontSize: 9, color: "rgba(180,140,80,0.3)", letterSpacing: "0.06em" }}>
                {ytLoading ? "Finding on YouTube…" : "No preview available"}
              </div>
            )}
          </div>

          {/* ── RIGHT CONTROLS ── */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            {/* Volume */}
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <button
                onClick={() => setMuted(m => !m)}
                style={{ ...S.ctrl, color: muted ? "rgba(180,140,80,0.3)" : "rgba(180,140,80,0.6)" }}
              >
                {muted ? Ic.volMute : Ic.volHigh}
              </button>
              <input
                type="range" min="0" max="1" step="0.05"
                value={muted ? 0 : volume}
                onChange={e => { setVolume(+e.target.value); setMuted(false); }}
                style={{ width: 60, accentColor: activeColor, cursor: "pointer" }}
              />
            </div>

            {/* Queue toggle */}
            <button
              onClick={() => setShowQueue(s => !s)}
              style={{ ...S.ctrl, color: showQueue ? activeColor : "rgba(180,140,80,0.4)" }}
              title="Queue"
            >{Ic.queue}</button>

            {/* Spotify export */}
            {spotifyConnected && (
              <button
                onClick={handleExport}
                disabled={exporting}
                style={{
                  ...S.ctrl,
                  padding: "5px 10px", borderRadius: 6,
                  background: exporting ? "rgba(29,185,84,0.1)" : "rgba(29,185,84,0.15)",
                  border: "1px solid rgba(29,185,84,0.4)",
                  color: exportDone?.url ? "#34d399" : "#1db954",
                  fontSize: 10, fontFamily: "'DM Mono', monospace",
                  letterSpacing: "0.06em", display: "flex", alignItems: "center", gap: 5,
                  opacity: exporting ? 0.6 : 1,
                }}
                title="Export to Spotify"
              >
                {Ic.spotify}
                {exporting ? "Exporting…" : exportDone?.url ? "Exported!" : "Export"}
              </button>
            )}

            {/* Last.fm love */}
            {visibleServices?.lastfm && servicesConnected?.lastfm && (
              <button
                onClick={() => serviceAction("lastfm", "love")}
                style={{
                  ...S.ctrl, padding: "4px 8px", borderRadius: 6,
                  background: "rgba(213,16,7,0.12)", border: "1px solid rgba(213,16,7,0.3)",
                  color: "#d51007", fontSize: 10, fontFamily: "'DM Mono', monospace",
                  letterSpacing: "0.05em", display: "flex", alignItems: "center", gap: 4,
                }}
                title="Love on Last.fm"
              >
                ♥ Last.fm
              </button>
            )}



            {/* Service toast */}
            {serviceToast && (
              <span style={{ fontSize: 9, color: serviceToast.startsWith("⚠") ? "#f87171" : "#34d399", fontFamily: "'DM Mono', monospace" }}>
                {serviceToast}
              </span>
            )}

            {/* Minimise */}
            <button
              onClick={() => setMinimised(true)}
              style={{ ...S.ctrl, opacity: 0.4, transform: "rotate(180deg)" }}
              title="Minimise player"
            >{Ic.chevron}</button>

            {/* Close */}
            <button onClick={onClose} style={{ ...S.ctrl, opacity: 0.4 }} title="Close player">
              {Ic.close}
            </button>
          </div>
        </div>

        {/* ── QUEUE PANEL ── */}
        {showQueue && (
          <div style={{
            marginTop: 10, paddingTop: 10,
            borderTop: "1px solid rgba(120,80,20,0.2)",
            maxHeight: 220, overflowY: "auto",
            scrollbarWidth: "thin",
            scrollbarColor: `${activeColor}44 transparent`,
          }}>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: 8 }}>
              Queue — {queue.length} tracks {shuffle ? "· shuffled" : ""}
            </div>
            {queue.map((t, i) => (
              <div
                key={`${t.title}|${t.artist}|${i}`}
                onClick={() => setQueueIdx(i)}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "5px 6px", borderRadius: 6, cursor: "pointer",
                  background: i === queueIdx ? `${activeColor}18` : "transparent",
                  border: `1px solid ${i === queueIdx ? activeColor + "44" : "transparent"}`,
                  transition: "all 0.15s",
                  marginBottom: 2,
                }}
              >
                <span style={{ fontSize: 9, color: "rgba(180,140,80,0.3)", width: 16, textAlign: "right", flexShrink: 0 }}>
                  {i === queueIdx ? "▶" : i + 1}
                </span>
                {t.cover_art
                  ? <img src={t.cover_art} alt="" style={{ width: 24, height: 24, borderRadius: 3, flexShrink: 0 }} />
                  : <div style={{ width: 24, height: 24, borderRadius: 3, background: "rgba(120,80,20,0.2)", flexShrink: 0 }} />
                }
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 11, color: i === queueIdx ? "#fde68a" : "rgba(220,190,140,0.8)",
                    fontFamily: "'Playfair Display', serif",
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>{t.title}</div>
                  <div style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.artist}</div>
                </div>
                {!t.preview_url && (
                  <span style={{ fontSize: 8, color: "rgba(180,140,80,0.2)", flexShrink: 0 }}>no preview</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ── YouTube full-length embed ── */}
        {ytVideoId && (
          <div style={{ marginTop: 10, borderRadius: 8, overflow: "hidden", position: "relative" }}>
            <div style={{
              fontSize: 9, color: "rgba(180,140,80,0.3)", fontFamily: "'DM Mono', monospace",
              letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4,
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span>▶ Full track via YouTube</span>
              <button
                onClick={() => setYtVideoId(null)}
                style={{ background: "none", border: "none", color: "rgba(180,140,80,0.3)", cursor: "pointer", fontSize: 12, padding: 0 }}
              >✕</button>
            </div>
            <iframe
              width="100%"
              height="80"
              src={`https://www.youtube.com/embed/${ytVideoId}?autoplay=1&controls=1`}
              style={{ border: "none", borderRadius: 6, display: "block" }}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope"
              allowFullScreen
            />
          </div>
        )}

        {/* Export result */}
        {exportDone && !exportDone.error && exportDone.url && (
          <div style={{ marginTop: 8, fontSize: 10, color: "#34d399", display: "flex", alignItems: "center", gap: 8 }}>
            ✓ Exported to Spotify!
            <a href={exportDone.url} target="_blank" rel="noopener noreferrer"
              style={{ color: "#1db954", textDecoration: "underline" }}>
              Open playlist
            </a>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulseRing {
          0%   { opacity: 0.8; transform: scale(1); }
          50%  { opacity: 0.3; transform: scale(1.04); }
          100% { opacity: 0.8; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}

/* ── STYLES ──────────────────────────────────────────────────────── */
const S = {
  ctrl: {
    display: "flex", alignItems: "center", justifyContent: "center",
    width: 32, height: 32, borderRadius: 8,
    background: "transparent", border: "none",
    color: "rgba(180,140,80,0.7)", cursor: "pointer",
    transition: "all 0.15s",
    flexShrink: 0,
  },
};
