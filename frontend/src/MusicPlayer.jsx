/**
 * MusicPlayer.jsx  — VibeFinderAI
 * ────────────────────────────────
 * PRIMARY  : YouTube IFrame API — full-length playback when YT connected
 * FALLBACK : HTML Audio — 30s previews
 *
 * KEY FIX: Video ID cache is MODULE-LEVEL (outside the component).
 * This means:
 *  - No duplicate fetch requests across re-renders
 *  - Cache persists when the player is closed/reopened
 *  - Multiple component instances share the same cache
 *  - fetchingSet prevents concurrent fetches for the same track
 */

import { useState, useEffect, useRef, useCallback } from "react";

/* ══════════════════════════════════════════════════════════════
   MODULE-LEVEL VIDEO ID CACHE
   Lives outside the component — survives re-renders and remounts
══════════════════════════════════════════════════════════════ */
const _VIDEO_CACHE   = new Map();   // "title|artist" → videoId
const _FETCHING_KEYS = new Set();   // keys currently in-flight

function _cacheKey(t) { return `${t.title}|${t.artist}`; }
function _cacheGet(t)  { return _VIDEO_CACHE.get(_cacheKey(t)) || null; }
function _cacheSet(t, vid) { _VIDEO_CACHE.set(_cacheKey(t), vid); }
function _isFetching(t){ return _FETCHING_KEYS.has(_cacheKey(t)); }

/* ── Icons ─────────────────────────────────────────────────── */
const Ic = {
  play:    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>,
  pause:   <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>,
  prev:    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>,
  next:    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>,
  shuffle: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>,
  repeat:  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>,
  repeat1: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>,
  volHigh: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>,
  volMute: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>,
  queue:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  spotify: <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>,
  close:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>,
  chevron: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="18 15 12 9 6 15"/></svg>,
  disc:    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>,
  yt:      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>,
};

const fmt = (s) => {
  if (!s || isNaN(s)) return "0:00";
  const secs = Math.floor(s);
  return `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
};

const shuffleArray = (arr) => {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

/* ── YouTube IFrame API singleton loader ─────────────────────── */
let _ytApiState = "idle"; // idle | loading | ready
const _ytApiWaiters = [];

function ensureYtApi(cb) {
  if (_ytApiState === "ready") { cb(); return; }
  _ytApiWaiters.push(cb);
  if (_ytApiState === "loading") return;
  _ytApiState = "loading";
  window.onYouTubeIframeAPIReady = () => {
    _ytApiState = "ready";
    _ytApiWaiters.forEach(fn => fn());
    _ytApiWaiters.length = 0;
  };
  const s = document.createElement("script");
  s.src = "https://www.youtube.com/iframe_api";
  document.head.appendChild(s);
}

/* ═══════════════════════════════════════════════════════════════
   MAIN COMPONENT
═══════════════════════════════════════════════════════════════ */
export default function MusicPlayer({
  tracks = [],
  initialIndex = 0,
  activeColor = "#d97706",
  onClose,
  token,
  buildApiUrl,
  spotifyConnected = false,
  onExportSpotify,
  servicesConnected = {},
  visibleServices   = {},
  onServiceAction,
}) {
  const useYT = !!(visibleServices?.youtube && servicesConnected?.youtube);

  /* ── Queue ─────────────────────────────────────────────────── */
  const [queue,    setQueue]    = useState(() => tracks.map((t, i) => ({ ...t, _origIdx: i })));
  const [queueIdx, setQueueIdx] = useState(initialIndex);

  /* ── Playback state ────────────────────────────────────────── */
  const [isPlaying,  setIsPlaying]  = useState(false);
  const [progress,   setProgress]   = useState(0);
  const [elapsed,    setElapsed]    = useState(0);
  const [duration,   setDuration]   = useState(0);
  const [volume,     setVolume]     = useState(0.7);
  const [muted,      setMuted]      = useState(false);
  const [shuffle,    setShuffle]    = useState(false);
  const [repeat,     setRepeat]     = useState("off");
  const [showQueue,  setShowQueue]  = useState(false);
  const [minimised,  setMinimised]  = useState(false);

  /* ── Video ID ready state (triggers re-render when new ID arrives) */
  const [cacheVersion, setCacheVersion] = useState(0);
  const bumpCache = () => setCacheVersion(v => v + 1);

  /* ── YT player state ───────────────────────────────────────── */
  const [ytReady,   setYtReady]   = useState(false);
  const [ytLoading, setYtLoading] = useState(false);

  /* ── Export / service ──────────────────────────────────────── */
  const [exporting,    setExporting]    = useState(false);
  const [exportDone,   setExportDone]   = useState(null);
  const [serviceToast, setServiceToast] = useState(null);

  /* ── Refs ──────────────────────────────────────────────────── */
  const audioRef    = useRef(null);
  const ytPlayerRef = useRef(null);
  const progressRef = useRef(null);
  const pollRef     = useRef(null);

  // Stable refs for callbacks that mustn't cause re-renders
  const repeatRef   = useRef(repeat);
  const queueIdxRef = useRef(queueIdx);
  const queueRef    = useRef(queue);
  useEffect(() => { repeatRef.current   = repeat;   }, [repeat]);
  useEffect(() => { queueIdxRef.current = queueIdx; }, [queueIdx]);
  useEffect(() => { queueRef.current    = queue;    }, [queue]);

  const track      = queue[queueIdx] || queue[0];
  const currentVid = track ? _cacheGet(track) : null;

  /* ════════════════════════════════════════════════════════════
     VIDEO ID FETCHING
     Uses module-level cache + fetching set — zero duplicates
  ════════════════════════════════════════════════════════════ */
  const fetchVideoId = useCallback(async (t, isPriority = false) => {
    if (!buildApiUrl || !t) return null;
    const cached = _cacheGet(t);
    if (cached) return cached;
    if (_isFetching(t)) return null;

    const key = _cacheKey(t);
    _FETCHING_KEYS.add(key);
    if (isPriority) setYtLoading(true);

    try {
      const url = buildApiUrl(
        `/api/services/youtube/search` +
        `?title=${encodeURIComponent(t.title)}` +
        `&artist=${encodeURIComponent(t.artist)}` +
        `&q=${encodeURIComponent(`${t.title} ${t.artist} official audio`)}`
      );
      const res  = await fetch(url);
      if (!res.ok) return null;
      const data = await res.json();
      if (data.found && data.video_id) {
        _cacheSet(t, data.video_id);
        bumpCache(); // trigger re-render so UI reflects new ID
        return data.video_id;
      }
    } catch { /* swallow — no video found */ }
    finally {
      _FETCHING_KEYS.delete(key);
      if (isPriority) setYtLoading(false);
    }
    return null;
  }, [buildApiUrl]); // stable — only changes if buildApiUrl changes

  /* ── Background pre-fetch: next 4 tracks only ─────────────── */
  useEffect(() => {
    if (!useYT || !buildApiUrl) return;
    const start = queueIdx;
    const end   = Math.min(queueIdx + 4, queue.length);
    for (let i = start; i < end; i++) {
      const t = queue[i];
      if (!_cacheGet(t) && !_isFetching(t)) {
        const delay = (i - start) * 400; // 400ms stagger
        setTimeout(() => fetchVideoId(t), delay);
      }
    }
  }, [queueIdx, useYT]); // eslint-disable-line

  /* ════════════════════════════════════════════════════════════
     YOUTUBE IFRAME PLAYER SETUP
  ════════════════════════════════════════════════════════════ */
  useEffect(() => {
    if (!useYT) return;
    ensureYtApi(() => {
      if (ytPlayerRef.current) return;
      // Make sure the container div exists
      const container = document.getElementById("vf-yt-hidden");
      if (!container) return;

      ytPlayerRef.current = new window.YT.Player("vf-yt-hidden", {
        height: "1", width: "1",
        playerVars: { autoplay: 1, controls: 0, disablekb: 1, fs: 0, modestbranding: 1, rel: 0, origin: window.location.origin },
        events: {
          onReady: () => {
            setYtReady(true);
            ytPlayerRef.current.setVolume(Math.round(volume * 100));
          },
          onStateChange: (e) => {
            const YT = window.YT?.PlayerState;
            if (!YT) return;
            if (e.data === YT.PLAYING) { setIsPlaying(true); }
            else if (e.data === YT.PAUSED) { setIsPlaying(false); }
            else if (e.data === YT.ENDED) {
              const idx = queueIdxRef.current;
              const q   = queueRef.current;
              const rep = repeatRef.current;
              if (rep === "one") {
                ytPlayerRef.current?.seekTo(0);
                ytPlayerRef.current?.playVideo();
              } else if (idx < q.length - 1) {
                setQueueIdx(idx + 1);
              } else if (rep === "all") {
                setQueueIdx(0);
              } else {
                setIsPlaying(false);
              }
            }
          },
        },
      });
    });
    return () => {
      clearInterval(pollRef.current);
      ytPlayerRef.current?.destroy();
      ytPlayerRef.current = null;
    };
  }, [useYT]); // eslint-disable-line

  /* ── Load track into YT when queueIdx changes ─────────────── */
  useEffect(() => {
    if (!useYT || !ytReady || !track) return;
    const vid = _cacheGet(track);
    if (vid) {
      ytPlayerRef.current?.loadVideoById(vid);
    } else {
      // Priority fetch — load as soon as ID arrives
      fetchVideoId(track, true).then(id => {
        if (id) ytPlayerRef.current?.loadVideoById(id);
      });
    }
    setElapsed(0); setProgress(0); setDuration(0);
  }, [queueIdx, ytReady, cacheVersion, useYT]); // eslint-disable-line

  /* ── Poll YT progress ──────────────────────────────────────── */
  useEffect(() => {
    if (!useYT) return;
    clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      if (!ytPlayerRef.current?.getCurrentTime) return;
      try {
        const cur = ytPlayerRef.current.getCurrentTime() || 0;
        const dur = ytPlayerRef.current.getDuration()    || 0;
        setElapsed(cur);
        setDuration(dur);
        setProgress(dur > 0 ? cur / dur : 0);
      } catch {}
    }, 500);
    return () => clearInterval(pollRef.current);
  }, [useYT]);

  /* ── Sync volume ────────────────────────────────────────────── */
  useEffect(() => {
    const v = muted ? 0 : volume;
    if (audioRef.current) audioRef.current.volume = v;
    if (ytPlayerRef.current?.setVolume) ytPlayerRef.current.setVolume(Math.round(v * 100));
  }, [volume, muted]);

  /* ════════════════════════════════════════════════════════════
     HTML AUDIO (PREVIEW FALLBACK)
  ════════════════════════════════════════════════════════════ */
  useEffect(() => {
    if (useYT) return;
    const audio = new Audio();
    audio.volume = muted ? 0 : volume;
    audioRef.current = audio;
    audio.addEventListener("timeupdate",    () => { setElapsed(audio.currentTime); setProgress(audio.duration ? audio.currentTime / audio.duration : 0); });
    audio.addEventListener("durationchange",() => setDuration(audio.duration || 0));
    audio.addEventListener("ended",        () => advanceQueue());
    audio.addEventListener("pause",        () => setIsPlaying(false));
    audio.addEventListener("play",         () => setIsPlaying(true));
    if (tracks[initialIndex]?.preview_url) { audio.src = tracks[initialIndex].preview_url; audio.play().catch(() => {}); }
    return () => { audio.pause(); audio.src = ""; };
  }, []); // eslint-disable-line

  useEffect(() => {
    if (useYT || !audioRef.current || !track?.preview_url) { if (!useYT) setIsPlaying(false); return; }
    audioRef.current.src = track.preview_url;
    audioRef.current.volume = muted ? 0 : volume;
    audioRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
  }, [queueIdx, queue, useYT]); // eslint-disable-line

  /* ════════════════════════════════════════════════════════════
     CONTROLS
  ════════════════════════════════════════════════════════════ */
  const advanceQueue = useCallback(() => {
    const idx = queueIdxRef.current;
    const q   = queueRef.current;
    const rep = repeatRef.current;
    if (rep === "one") {
      if (audioRef.current) { audioRef.current.currentTime = 0; audioRef.current.play().catch(() => {}); }
      return;
    }
    if (idx < q.length - 1) setQueueIdx(idx + 1);
    else if (rep === "all") setQueueIdx(0);
  }, []);

  const handleNext = useCallback(() => {
    setQueueIdx(i => {
      if (repeat === "one") return i;
      if (i >= queue.length - 1) return repeat === "all" ? 0 : i;
      return i + 1;
    });
  }, [queue.length, repeat]);

  const handlePrev = () => {
    const cur = useYT ? ytPlayerRef.current?.getCurrentTime?.() : audioRef.current?.currentTime;
    if (cur > 3) {
      if (useYT) ytPlayerRef.current?.seekTo(0);
      else if (audioRef.current) audioRef.current.currentTime = 0;
      return;
    }
    setQueueIdx(i => Math.max(0, i - 1));
  };

  const togglePlay = () => {
    if (useYT) {
      if (!ytPlayerRef.current) return;
      isPlaying ? ytPlayerRef.current.pauseVideo() : ytPlayerRef.current.playVideo();
    } else {
      if (!audioRef.current || !track?.preview_url) return;
      if (isPlaying) audioRef.current.pause();
      else { if (!audioRef.current.src) audioRef.current.src = track.preview_url; audioRef.current.play().catch(() => {}); }
    }
  };

  const seekTo = (e) => {
    if (!progressRef.current) return;
    const rect  = progressRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    if (useYT && ytPlayerRef.current?.seekTo) ytPlayerRef.current.seekTo(ratio * (duration || 0));
    else if (audioRef.current?.duration) audioRef.current.currentTime = ratio * audioRef.current.duration;
  };

  const toggleShuffle = () => {
    const cur = queue[queueIdx];
    if (!shuffle) {
      const rest = queue.filter((_, i) => i !== queueIdx);
      setQueue([cur, ...shuffleArray(rest)]);
      setQueueIdx(0);
    } else {
      setQueue([...tracks].map((t, i) => ({ ...t, _origIdx: i })));
      setQueueIdx(cur._origIdx);
    }
    setShuffle(s => !s);
  };

  const cycleRepeat = () => setRepeat(r => r === "off" ? "all" : r === "all" ? "one" : "off");

  /* ── Export ─────────────────────────────────────────────────── */
  const handleExport = async () => {
    if (!onExportSpotify) return;
    setExporting(true);
    try   { setExportDone(await onExportSpotify(tracks)); }
    catch (e) { setExportDone({ error: e.message }); }
    finally   { setExporting(false); }
  };

  const serviceAction = async (service, action) => {
    try {
      await onServiceAction?.(service, action, track);
      setServiceToast(`♥ ${action === "love" ? "Loved" : "Scrobbled"}`);
    } catch { setServiceToast("⚠ Failed"); }
    setTimeout(() => setServiceToast(null), 2500);
  };

  /* ── Derived ─────────────────────────────────────────────────── */
  const hasAudio = useYT ? !!currentVid : !!track?.preview_url;
  const canPlay  = hasAudio || ytLoading;

  /* ═══════════════════════════════════════════════════════════
     MINIMISED BAR
  ═══════════════════════════════════════════════════════════ */
  if (minimised) {
    return (
      <>
        {useYT && <div id="vf-yt-hidden" style={{ position: "fixed", bottom: -200, right: -200, width: 160, height: 90, pointerEvents: "none", zIndex: -1 }} />}
        <div style={{ position: "fixed", bottom: 16, left: "50%", transform: "translateX(-50%)", zIndex: 200, display: "flex", alignItems: "center", gap: 10, padding: "8px 16px", background: "linear-gradient(135deg, #120900, #0a0500)", border: `1px solid ${activeColor}55`, borderRadius: 40, boxShadow: `0 8px 32px rgba(0,0,0,0.8), 0 0 20px ${activeColor}22`, backdropFilter: "blur(12px)", maxWidth: "90vw" }}>
          {track?.cover_art ? <img src={track.cover_art} alt="" style={{ width: 28, height: 28, borderRadius: 4, flexShrink: 0 }} /> : <div style={{ width: 28, height: 28, borderRadius: 4, background: "rgba(120,80,20,0.3)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{Ic.disc}</div>}
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11, color: "#fde68a", fontFamily: "'Playfair Display', serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 140 }}>{track?.title}</div>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.5)", display: "flex", alignItems: "center", gap: 3 }}>{useYT && Ic.yt}{track?.artist}</div>
          </div>
          <button onClick={(e) => { e.stopPropagation(); togglePlay(); }} style={{ ...S.ctrl, width: 28, height: 28 }}>{isPlaying ? Ic.pause : Ic.play}</button>
          <button onClick={(e) => { e.stopPropagation(); handleNext(); }} style={{ ...S.ctrl, width: 24, height: 24 }}>{Ic.next}</button>
          <button onClick={() => setMinimised(false)} style={{ ...S.ctrl, opacity: 0.5, width: 22, height: 22 }}>{Ic.chevron}</button>
        </div>
      </>
    );
  }

  /* ═══════════════════════════════════════════════════════════
     FULL PLAYER
  ═══════════════════════════════════════════════════════════ */
  return (
    <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 200, background: "linear-gradient(180deg, rgba(10,5,0,0.97) 0%, #060300 100%)", borderTop: `1px solid ${activeColor}44`, boxShadow: `0 -8px 40px rgba(0,0,0,0.8), 0 0 30px ${activeColor}18`, backdropFilter: "blur(20px)", padding: "0 0 env(safe-area-inset-bottom, 0)" }}>

      {/* Hidden YT player div */}
      {useYT && <div id="vf-yt-hidden" style={{ position: "fixed", bottom: -200, right: -200, width: 160, height: 90, pointerEvents: "none", zIndex: -1 }} />}

      {/* Progress bar */}
      <div ref={progressRef} onClick={seekTo} style={{ height: 3, background: "rgba(120,80,20,0.2)", cursor: "pointer", position: "relative" }}>
        <div style={{ height: "100%", width: `${progress * 100}%`, background: `linear-gradient(90deg, ${activeColor}88, ${activeColor})`, transition: "width 0.5s linear" }} />
        <div style={{ position: "absolute", top: -3, left: `${progress * 100}%`, transform: "translateX(-50%)", width: 9, height: 9, borderRadius: "50%", background: activeColor, boxShadow: `0 0 6px ${activeColor}`, transition: "left 0.5s linear" }} />
      </div>

      <div style={{ padding: "10px 16px 12px", maxWidth: 900, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>

          {/* Album art */}
          <div style={{ position: "relative", flexShrink: 0 }}>
            {track?.cover_art
              ? <img src={track.cover_art} alt="" style={{ width: 48, height: 48, borderRadius: 6, boxShadow: `0 0 12px ${activeColor}44`, border: `1px solid ${activeColor}33` }} />
              : <div style={{ width: 48, height: 48, borderRadius: 6, background: "rgba(120,80,20,0.2)", display: "flex", alignItems: "center", justifyContent: "center", color: "rgba(180,140,80,0.4)", border: `1px solid rgba(120,80,20,0.3)` }}>{Ic.disc}</div>
            }
            {isPlaying && <div style={{ position: "absolute", inset: 0, borderRadius: 6, border: `1.5px solid ${activeColor}66`, animation: "pulseRing 2s ease infinite" }} />}
          </div>

          {/* Track info */}
          <div style={{ flex: "0 0 auto", minWidth: 0, maxWidth: 150 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#fde68a", fontFamily: "'Playfair Display', serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{track?.title || "—"}</div>
            <div style={{ fontSize: 10, color: "rgba(180,140,80,0.6)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{track?.artist || ""}</div>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.3)", marginTop: 1, display: "flex", alignItems: "center", gap: 4 }}>
              {fmt(elapsed)} / {fmt(duration)}
              {useYT && (
                <span style={{ color: currentVid ? "rgba(255,80,80,0.6)" : "rgba(180,80,80,0.35)", display: "flex", alignItems: "center", gap: 2 }}>
                  {Ic.yt}{ytLoading ? " …" : !currentVid ? " searching" : ""}
                </span>
              )}
              {!useYT && <span style={{ opacity: 0.5 }}>preview</span>}
            </div>
          </div>

          {/* Centre controls */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <button onClick={toggleShuffle} style={{ ...S.ctrl, color: shuffle ? activeColor : "rgba(180,140,80,0.35)" }} title="Shuffle">{Ic.shuffle}</button>
              <button onClick={handlePrev} style={S.ctrl} title="Previous">{Ic.prev}</button>

              {/* Main play/pause */}
              <button
                onClick={togglePlay}
                disabled={!canPlay}
                title={useYT
                  ? (ytLoading ? "Finding on YouTube…" : !currentVid ? "No video found" : isPlaying ? "Pause" : "Play full track")
                  : (track?.preview_url ? "Play 30s preview" : "No preview")}
                style={{
                  ...S.ctrl, width: 42, height: 42, borderRadius: "50%",
                  background: canPlay ? `linear-gradient(135deg, ${activeColor}cc, ${activeColor})` : "rgba(60,40,10,0.4)",
                  border: `1px solid ${activeColor}55`,
                  color: canPlay ? "#000" : "rgba(120,80,20,0.3)",
                  boxShadow: canPlay ? `0 0 16px ${activeColor}44` : "none",
                  opacity: canPlay ? 1 : 0.5,
                }}
              >
                {ytLoading
                  ? <div style={{ width: 14, height: 14, border: `2px solid ${activeColor}44`, borderTopColor: activeColor, borderRadius: "50%", animation: "ytSpin 0.8s linear infinite" }} />
                  : isPlaying ? Ic.pause : Ic.play}
              </button>

              <button onClick={handleNext} style={S.ctrl} title="Next">{Ic.next}</button>
              <button onClick={cycleRepeat} style={{ ...S.ctrl, color: repeat !== "off" ? activeColor : "rgba(180,140,80,0.35)", position: "relative" }} title={`Repeat: ${repeat}`}>
                {Ic.repeat}
                {repeat === "one" && <span style={{ position: "absolute", top: -4, right: -4, fontSize: 7, color: activeColor, fontWeight: "bold" }}>1</span>}
              </button>
            </div>

            {/* Mode badge */}
            <div style={{ fontSize: 8, letterSpacing: "0.1em", textTransform: "uppercase", display: "flex", alignItems: "center", gap: 3, color: useYT ? "rgba(255,80,80,0.55)" : "rgba(180,140,80,0.25)" }}>
              {useYT ? <>{Ic.yt} Full length · YouTube</> : "30s preview mode · connect YouTube for full tracks"}
            </div>
          </div>

          {/* Right controls */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0, flexWrap: "wrap", justifyContent: "flex-end" }}>
            {/* Volume */}
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <button onClick={() => setMuted(m => !m)} style={{ ...S.ctrl, color: muted ? "rgba(180,140,80,0.3)" : "rgba(180,140,80,0.6)" }}>{muted ? Ic.volMute : Ic.volHigh}</button>
              <input type="range" min="0" max="1" step="0.05" value={muted ? 0 : volume} onChange={e => { setVolume(+e.target.value); setMuted(false); }} style={{ width: 55, accentColor: activeColor, cursor: "pointer" }} />
            </div>

            <button onClick={() => setShowQueue(s => !s)} style={{ ...S.ctrl, color: showQueue ? activeColor : "rgba(180,140,80,0.4)" }} title={`Queue (${queue.length})`}>{Ic.queue}</button>

            {spotifyConnected && (
              <button onClick={handleExport} disabled={exporting} style={{ ...S.ctrl, padding: "4px 8px", borderRadius: 6, background: "rgba(29,185,84,0.15)", border: "1px solid rgba(29,185,84,0.4)", color: exportDone?.url ? "#34d399" : "#1db954", fontSize: 10, fontFamily: "'DM Mono', monospace", display: "flex", alignItems: "center", gap: 4, opacity: exporting ? 0.6 : 1 }}>
                {Ic.spotify} {exporting ? "…" : exportDone?.url ? "✓" : "Export"}
              </button>
            )}

            {visibleServices?.lastfm && servicesConnected?.lastfm && (
              <button onClick={() => serviceAction("lastfm", "love")} style={{ ...S.ctrl, padding: "4px 8px", borderRadius: 6, background: "rgba(213,16,7,0.12)", border: "1px solid rgba(213,16,7,0.3)", color: "#d51007", fontSize: 10, fontFamily: "'DM Mono', monospace", display: "flex", alignItems: "center", gap: 3 }} title="Love on Last.fm">
                ♥ Last.fm
              </button>
            )}

            {serviceToast && <span style={{ fontSize: 9, color: serviceToast.startsWith("⚠") ? "#f87171" : "#34d399", fontFamily: "'DM Mono', monospace" }}>{serviceToast}</span>}

            <button onClick={() => setMinimised(true)} style={{ ...S.ctrl, opacity: 0.4, transform: "rotate(180deg)" }} title="Minimise">{Ic.chevron}</button>
            <button onClick={onClose} style={{ ...S.ctrl, opacity: 0.4 }} title="Close">{Ic.close}</button>
          </div>
        </div>

        {/* Queue panel */}
        {showQueue && (
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(120,80,20,0.2)", maxHeight: 200, overflowY: "auto", scrollbarWidth: "thin", scrollbarColor: `${activeColor}44 transparent` }}>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: 8, fontFamily: "'DM Mono', monospace" }}>
              Queue — {queue.length} tracks {shuffle ? "· shuffled" : ""} {useYT ? "· full-length YouTube" : "· 30s previews"}
            </div>
            {queue.map((t, i) => {
              const vid     = _cacheGet(t);
              const loading = _isFetching(t);
              return (
                <div key={`${t.title}|${i}`} onClick={() => setQueueIdx(i)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 6px", borderRadius: 6, cursor: "pointer", background: i === queueIdx ? `${activeColor}18` : "transparent", border: `1px solid ${i === queueIdx ? activeColor + "44" : "transparent"}`, transition: "all 0.15s", marginBottom: 2 }}>
                  <span style={{ fontSize: 9, color: "rgba(180,140,80,0.3)", width: 16, textAlign: "right", flexShrink: 0 }}>{i === queueIdx ? "▶" : i + 1}</span>
                  {t.cover_art ? <img src={t.cover_art} alt="" style={{ width: 24, height: 24, borderRadius: 3, flexShrink: 0 }} /> : <div style={{ width: 24, height: 24, borderRadius: 3, background: "rgba(120,80,20,0.2)", flexShrink: 0 }} />}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: i === queueIdx ? "#fde68a" : "rgba(220,190,140,0.8)", fontFamily: "'Playfair Display', serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.title}</div>
                    <div style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.artist}</div>
                  </div>
                  {useYT && (
                    <span style={{ fontSize: 8, flexShrink: 0, color: vid ? "rgba(255,80,80,0.6)" : loading ? "rgba(217,119,6,0.4)" : "rgba(120,80,20,0.3)" }}>
                      {vid ? "▶" : loading ? "…" : "–"}
                    </span>
                  )}
                  {!useYT && !t.preview_url && <span style={{ fontSize: 8, color: "rgba(180,140,80,0.2)", flexShrink: 0 }}>no preview</span>}
                </div>
              );
            })}
          </div>
        )}

        {exportDone && !exportDone.error && exportDone.url && (
          <div style={{ marginTop: 8, fontSize: 10, color: "#34d399", display: "flex", alignItems: "center", gap: 8, fontFamily: "'DM Mono', monospace" }}>
            ✓ Exported! <a href={exportDone.url} target="_blank" rel="noopener noreferrer" style={{ color: "#1db954" }}>Open in Spotify ↗</a>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulseRing { 0%,100%{opacity:.8;transform:scale(1);}50%{opacity:.3;transform:scale(1.04);} }
        @keyframes ytSpin    { to{transform:rotate(360deg);} }
      `}</style>
    </div>
  );
}

const S = {
  ctrl: {
    display: "flex", alignItems: "center", justifyContent: "center",
    width: 32, height: 32, borderRadius: 8,
    background: "transparent", border: "none",
    color: "rgba(180,140,80,0.7)", cursor: "pointer",
    transition: "all 0.15s", flexShrink: 0,
  },
};
