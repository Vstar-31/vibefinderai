/**
 * MusicPlayer.jsx  — VibeFinderAI
 * ────────────────────────────────
 * APPROACH: Plain <iframe> embed, NO YT.Player() widget API.
 *
 * Why: The widget API (YT.Player) requires YouTube's script to load
 * inside the iframe and post back to the parent — blocked cross-origin
 * in production. Direct iframes with ?enablejsapi=1 + postMessage work
 * in every browser without any handshaking.
 *
 * How playback works:
 *  1. Swap iframe src to load a new video (autoplay=1 in URL)
 *  2. Send play/pause/seek via iframe.contentWindow.postMessage()
 *  3. Receive state (playing/paused/ended) via window.addEventListener('message')
 *  4. Advance queue automatically on 'ended' state
 *  5. Progress tracked client-side with elapsed timer (no getCurrentTime needed)
 *
 * FALLBACK: HTML Audio for 30s previews when YouTube not connected.
 *
 * Module-level video ID cache — zero duplicate requests.
 */

import { useState, useEffect, useRef, useCallback } from "react";

/* ══════════════════════════════════════════════════════════════
   MODULE-LEVEL CACHE  (survives re-renders, remounts, HMR)
══════════════════════════════════════════════════════════════ */
const _VID_CACHE    = new Map();   // "title|artist" → videoId | null (null = not found)
const _VID_FETCHING = new Set();   // keys currently in-flight

const _key    = (t) => `${t.title}|${t.artist}`;
const _getVid = (t) => _VID_CACHE.has(_key(t)) ? _VID_CACHE.get(_key(t)) : undefined;
const _setVid = (t, v) => _VID_CACHE.set(_key(t), v); // v = videoId string | null
const _busy   = (t) => _VID_FETCHING.has(_key(t));

/* ── YouTube embed URL builder ───────────────────────────────── */
const ytSrc = (videoId, autoplay = true) =>
  `https://www.youtube.com/embed/${videoId}` +
  `?enablejsapi=1` +
  `&autoplay=${autoplay ? 1 : 0}` +
  `&controls=0` +
  `&rel=0` +
  `&modestbranding=1` +
  `&playsinline=1` +
  `&origin=${encodeURIComponent(window.location.origin)}`;

/* ── Icons ─────────────────────────────────────────────────────── */
const Ic = {
  play:    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>,
  pause:   <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>,
  prev:    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>,
  next:    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>,
  shuffle: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>,
  repeat:  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>,
  volHigh: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>,
  volMute: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>,
  queue:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  spotify: <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>,
  close:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>,
  chevron: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="18 15 12 9 6 15"/></svg>,
  disc:    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>,
  yt:      <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>,
};

const fmt = (s) => {
  if (!s || isNaN(s)) return "0:00";
  const sec = Math.floor(s);
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
};

const shuffleArray = (arr) => {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

/* ═══════════════════════════════════════════════════════════════
   COMPONENT
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

  /* ── Queue ───────────────────────────────────────────────────── */
  const [queue,    setQueue]    = useState(() => tracks.map((t, i) => ({ ...t, _origIdx: i })));
  const [queueIdx, setQueueIdx] = useState(initialIndex);

  /* ── Playback ────────────────────────────────────────────────── */
  const [isPlaying,  setIsPlaying]  = useState(false);
  const [elapsed,    setElapsed]    = useState(0);    // seconds, client-tracked
  const [duration,   setDuration]   = useState(0);    // seconds
  const [volume,     setVolume]     = useState(0.7);
  const [muted,      setMuted]      = useState(false);
  const [shuffle,    setShuffle]    = useState(false);
  const [repeat,     setRepeat]     = useState("off");
  const [showQueue,  setShowQueue]  = useState(false);
  const [minimised,  setMinimised]  = useState(false);

  /* ── Video ID state ──────────────────────────────────────────── */
  const [cacheVer,   setCacheVer]   = useState(0);    // bump to re-render on new cache entry
  const [ytSearching, setYtSearching] = useState(false);

  /* ── Export / services ───────────────────────────────────────── */
  const [exporting,    setExporting]    = useState(false);
  const [exportDone,   setExportDone]   = useState(null);
  const [serviceToast, setServiceToast] = useState(null);

  /* ── Refs ────────────────────────────────────────────────────── */
  const iframeRef   = useRef(null);   // YT iframe element
  const audioRef    = useRef(null);   // HTML Audio element (preview fallback)
  const progressRef = useRef(null);   // progress bar div
  const tickRef     = useRef(null);   // setInterval for elapsed time
  const startRef    = useRef(null);   // wall-clock time when play started (for elapsed calc)
  const elapsedBase = useRef(0);      // elapsed at last play event (for resume accuracy)

  // Stable refs for callbacks
  const repeatRef   = useRef(repeat);
  const queueIdxRef = useRef(queueIdx);
  const queueRef    = useRef(queue);
  useEffect(() => { repeatRef.current   = repeat;   }, [repeat]);
  useEffect(() => { queueIdxRef.current = queueIdx; }, [queueIdx]);
  useEffect(() => { queueRef.current    = queue;    }, [queue]);

  const track      = queue[queueIdx] || queue[0];
  const currentVid = track ? _getVid(track) : undefined; // undefined=unknown, null=not found, str=found

  /* ════════════════════════════════════════════════════════════
     VIDEO ID FETCHING  (module-level cache, no duplicates)
  ════════════════════════════════════════════════════════════ */
  const fetchVideoId = useCallback(async (t, isPriority = false) => {
    if (!buildApiUrl || !t) return null;
    const cached = _getVid(t);
    if (cached !== undefined) return cached; // null or videoId — already resolved
    if (_busy(t)) return null;

    _VID_FETCHING.add(_key(t));
    if (isPriority) setYtSearching(true);
    try {
      const url = buildApiUrl(
        `/api/services/youtube/search` +
        `?title=${encodeURIComponent(t.title)}` +
        `&artist=${encodeURIComponent(t.artist)}` +
        `&q=${encodeURIComponent(`${t.title} ${t.artist} official audio`)}`
      );
      const res  = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        const vid  = data.found ? data.video_id : null;
        _setVid(t, vid);
        setCacheVer(v => v + 1);
        return vid;
      }
      _setVid(t, null);
      return null;
    } catch {
      _setVid(t, null);
      return null;
    } finally {
      _VID_FETCHING.delete(_key(t));
      if (isPriority) setYtSearching(false);
    }
  }, [buildApiUrl]);

  /* ── Pre-fetch next 4 ───────────────────────────────────────── */
  useEffect(() => {
    if (!useYT || !buildApiUrl) return;
    const end = Math.min(queueIdx + 4, queue.length);
    for (let i = queueIdx; i < end; i++) {
      const t = queue[i];
      if (_getVid(t) === undefined && !_busy(t)) {
        setTimeout(() => fetchVideoId(t), (i - queueIdx) * 400);
      }
    }
  }, [queueIdx, useYT]); // eslint-disable-line

  /* ════════════════════════════════════════════════════════════
     postMessage → iframe (send command)
  ════════════════════════════════════════════════════════════ */
  const ytCommand = useCallback((func, args = []) => {
    try {
      iframeRef.current?.contentWindow?.postMessage(
        JSON.stringify({ event: "command", func, args }),
        "https://www.youtube.com"
      );
    } catch {}
  }, []);

  /* ════════════════════════════════════════════════════════════
     postMessage ← iframe (receive state)
  ════════════════════════════════════════════════════════════ */
  useEffect(() => {
    if (!useYT) return;
    const handler = (e) => {
      if (e.origin !== "https://www.youtube.com") return;
      try {
        const d = typeof e.data === "string" ? JSON.parse(e.data) : e.data;
        if (d.event === "onStateChange") {
          const state = d.info;
          if (state === 1) {
            // Playing
            setIsPlaying(true);
            startRef.current = Date.now();
            clearInterval(tickRef.current);
            tickRef.current = setInterval(() => {
              const secs = elapsedBase.current + (Date.now() - startRef.current) / 1000;
              setElapsed(secs);
              if (duration > 0) {} // duration set separately
            }, 500);
          } else if (state === 2) {
            // Paused — save elapsed so resume is accurate
            setIsPlaying(false);
            clearInterval(tickRef.current);
            if (startRef.current) {
              elapsedBase.current += (Date.now() - startRef.current) / 1000;
              startRef.current = null;
            }
          } else if (state === 0) {
            // Ended — advance queue
            setIsPlaying(false);
            clearInterval(tickRef.current);
            elapsedBase.current = 0;
            setElapsed(0);
            const idx = queueIdxRef.current;
            const q   = queueRef.current;
            const rep = repeatRef.current;
            if (rep === "one") {
              loadTrackIntoIframe(q[idx]);
            } else if (idx < q.length - 1) {
              setQueueIdx(idx + 1);
            } else if (rep === "all") {
              setQueueIdx(0);
            } else {
              setIsPlaying(false);
            }
          } else if (state === 3) {
            // Buffering — keep isPlaying true visually
          }
        } else if (d.event === "infoDelivery" && d.info?.duration) {
          setDuration(d.info.duration);
        }
      } catch {}
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [useYT, duration]); // eslint-disable-line

  /* ════════════════════════════════════════════════════════════
     Load track into iframe
  ════════════════════════════════════════════════════════════ */
  const loadTrackIntoIframe = useCallback((t) => {
    if (!iframeRef.current || !t) return;
    const vid = _getVid(t);
    if (vid) {
      iframeRef.current.src = ytSrc(vid, true);
      elapsedBase.current   = 0;
      setElapsed(0);
      setDuration(0);
      setIsPlaying(true); // will be confirmed by postMessage state=1
    }
  }, []);

  /* ── Load new track when queueIdx changes (YT mode) ────────── */
  useEffect(() => {
    if (!useYT || !track) return;
    clearInterval(tickRef.current);
    elapsedBase.current = 0;
    setElapsed(0);
    setDuration(0);

    const vid = _getVid(track);
    if (vid === undefined) {
      // Not fetched yet — priority fetch then load
      fetchVideoId(track, true).then(id => {
        if (id && iframeRef.current) {
          iframeRef.current.src = ytSrc(id, true);
          setIsPlaying(true);
        }
      });
    } else if (vid) {
      // Already cached
      if (iframeRef.current) {
        iframeRef.current.src = ytSrc(vid, true);
        setIsPlaying(true);
      }
    } else {
      // null = not found — just show "not found" UI, don't load
      setIsPlaying(false);
      if (iframeRef.current) iframeRef.current.src = "about:blank";
    }
  }, [queueIdx, useYT, cacheVer]); // eslint-disable-line

  /* ── Cleanup on unmount ─────────────────────────────────────── */
  useEffect(() => () => clearInterval(tickRef.current), []);

  /* ════════════════════════════════════════════════════════════
     HTML AUDIO (preview fallback)
  ════════════════════════════════════════════════════════════ */
  useEffect(() => {
    if (useYT) return;
    const audio = new Audio();
    audio.volume = muted ? 0 : volume;
    audioRef.current = audio;
    audio.addEventListener("timeupdate",     () => { setElapsed(audio.currentTime); });
    audio.addEventListener("durationchange", () => setDuration(audio.duration || 0));
    audio.addEventListener("ended",          () => advanceAudio());
    audio.addEventListener("pause",          () => setIsPlaying(false));
    audio.addEventListener("play",           () => setIsPlaying(true));
    if (tracks[initialIndex]?.preview_url) { audio.src = tracks[initialIndex].preview_url; audio.play().catch(() => {}); }
    return () => { audio.pause(); audio.src = ""; clearInterval(tickRef.current); };
  }, []); // eslint-disable-line

  useEffect(() => {
    if (useYT || !audioRef.current || !track?.preview_url) { if (!useYT) setIsPlaying(false); return; }
    audioRef.current.src    = track.preview_url;
    audioRef.current.volume = muted ? 0 : volume;
    audioRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
  }, [queueIdx, queue, useYT]); // eslint-disable-line

  const advanceAudio = useCallback(() => {
    const idx = queueIdxRef.current;
    const q   = queueRef.current;
    const rep = repeatRef.current;
    if (rep === "one") { if (audioRef.current) { audioRef.current.currentTime = 0; audioRef.current.play().catch(() => {}); } return; }
    if (idx < q.length - 1) setQueueIdx(idx + 1);
    else if (rep === "all") setQueueIdx(0);
  }, []);

  /* ── Sync volume ─────────────────────────────────────────────── */
  useEffect(() => {
    const v = muted ? 0 : volume;
    if (audioRef.current) audioRef.current.volume = v;
    // For YT: use postMessage volume command
    if (useYT) {
      ytCommand("setVolume", [Math.round(v * 100)]);
      if (muted) ytCommand("mute"); else ytCommand("unMute");
    }
  }, [volume, muted, useYT, ytCommand]);

  /* ════════════════════════════════════════════════════════════
     CONTROLS
  ════════════════════════════════════════════════════════════ */
  const handleNext = useCallback(() => {
    setQueueIdx(i => {
      if (repeat === "one") return i;
      if (i >= queue.length - 1) return repeat === "all" ? 0 : i;
      return i + 1;
    });
  }, [queue.length, repeat]);

  const handlePrev = () => {
    if (elapsed > 3) {
      if (useYT) {
        ytCommand("seekTo", [0, true]);
        elapsedBase.current = 0;
        setElapsed(0);
      } else if (audioRef.current) {
        audioRef.current.currentTime = 0;
      }
      return;
    }
    setQueueIdx(i => Math.max(0, i - 1));
  };

  const togglePlay = () => {
    if (useYT) {
      isPlaying ? ytCommand("pauseVideo") : ytCommand("playVideo");
    } else {
      if (!audioRef.current || !track?.preview_url) return;
      if (isPlaying) audioRef.current.pause();
      else { if (!audioRef.current.src) audioRef.current.src = track.preview_url; audioRef.current.play().catch(() => {}); }
    }
  };

  const seekTo = (e) => {
    if (!progressRef.current || !duration) return;
    const rect  = progressRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const secs  = ratio * duration;
    if (useYT) {
      ytCommand("seekTo", [secs, true]);
      elapsedBase.current = secs;
      startRef.current    = Date.now();
      setElapsed(secs);
    } else if (audioRef.current?.duration) {
      audioRef.current.currentTime = secs;
    }
  };

  const toggleShuffle = () => {
    const cur = queue[queueIdx];
    if (!shuffle) { const rest = queue.filter((_, i) => i !== queueIdx); setQueue([cur, ...shuffleArray(rest)]); setQueueIdx(0); }
    else { setQueue([...tracks].map((t, i) => ({ ...t, _origIdx: i }))); setQueueIdx(cur._origIdx ?? 0); }
    setShuffle(s => !s);
  };

  const cycleRepeat = () => setRepeat(r => r === "off" ? "all" : r === "all" ? "one" : "off");

  const handleExport = async () => {
    if (!onExportSpotify) return;
    setExporting(true);
    try { setExportDone(await onExportSpotify(tracks)); }
    catch (e) { setExportDone({ error: e.message }); }
    finally { setExporting(false); }
  };

  const serviceAction = async (service, action) => {
    try { await onServiceAction?.(service, action, track); setServiceToast(`♥ Loved`); }
    catch { setServiceToast("⚠ Failed"); }
    setTimeout(() => setServiceToast(null), 2500);
  };

  /* ── Derived ─────────────────────────────────────────────────── */
  const progress   = duration > 0 ? Math.min(elapsed / duration, 1) : 0;
  const vidFound   = currentVid !== undefined && currentVid !== null;
  const vidMissing = currentVid === null;
  const canPlay    = useYT ? (vidFound || ytSearching) : !!track?.preview_url;

  /* ════════════════════════════════════════════════════════════
     MINIMISED BAR
  ════════════════════════════════════════════════════════════ */
  if (minimised) {
    return (
      <>
        {useYT && (
          <iframe ref={iframeRef} src="about:blank" title="yt-player"
            style={{ position: "fixed", bottom: -300, right: -300, width: 160, height: 90, border: "none", pointerEvents: "none", zIndex: -1 }}
            allow="autoplay; encrypted-media"
          />
        )}
        <div style={{ position: "fixed", bottom: 16, left: "50%", transform: "translateX(-50%)", zIndex: 200, display: "flex", alignItems: "center", gap: 10, padding: "8px 16px", background: "linear-gradient(135deg, #120900, #0a0500)", border: `1px solid ${activeColor}55`, borderRadius: 40, boxShadow: `0 8px 32px rgba(0,0,0,0.8)`, backdropFilter: "blur(12px)", maxWidth: "90vw" }}>
          {track?.cover_art ? <img src={track.cover_art} alt="" style={{ width: 28, height: 28, borderRadius: 4, flexShrink: 0 }} /> : <div style={{ width: 28, height: 28, borderRadius: 4, background: "rgba(120,80,20,0.3)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{Ic.disc}</div>}
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11, color: "#fde68a", fontFamily: "'Playfair Display', serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 140 }}>{track?.title}</div>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.5)", display: "flex", alignItems: "center", gap: 3 }}>{useYT && <>{Ic.yt}&nbsp;</>}{track?.artist}</div>
          </div>
          <button onClick={(e) => { e.stopPropagation(); togglePlay(); }} style={{ ...S.ctrl, width: 28, height: 28 }}>{isPlaying ? Ic.pause : Ic.play}</button>
          <button onClick={(e) => { e.stopPropagation(); handleNext(); }} style={{ ...S.ctrl, width: 24, height: 24 }}>{Ic.next}</button>
          <button onClick={() => setMinimised(false)} style={{ ...S.ctrl, opacity: 0.5, width: 22, height: 22 }}>{Ic.chevron}</button>
        </div>
      </>
    );
  }

  /* ════════════════════════════════════════════════════════════
     FULL PLAYER
  ════════════════════════════════════════════════════════════ */
  return (
    <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 200, background: "linear-gradient(180deg, rgba(10,5,0,0.97) 0%, #060300 100%)", borderTop: `1px solid ${activeColor}44`, boxShadow: `0 -8px 40px rgba(0,0,0,0.8)`, backdropFilter: "blur(20px)", padding: "0 0 env(safe-area-inset-bottom, 0)" }}>

      {/* Hidden YouTube iframe — off-screen, real dimensions for autoplay to work */}
      {useYT && (
        <iframe
          ref={iframeRef}
          src="about:blank"
          title="vf-yt-player"
          allow="autoplay; encrypted-media"
          style={{
            position: "fixed",
            bottom: -300, right: -300,
            width: 160, height: 90,
            border: "none", pointerEvents: "none", zIndex: -1,
          }}
        />
      )}

      {/* Progress bar */}
      <div ref={progressRef} onClick={seekTo} style={{ height: 3, background: "rgba(120,80,20,0.2)", cursor: "pointer", position: "relative" }}>
        <div style={{ height: "100%", width: `${progress * 100}%`, background: `linear-gradient(90deg, ${activeColor}88, ${activeColor})`, transition: "width 0.5s linear" }} />
        <div style={{ position: "absolute", top: -3, left: `${progress * 100}%`, transform: "translateX(-50%)", width: 9, height: 9, borderRadius: "50%", background: activeColor, boxShadow: `0 0 6px ${activeColor}`, transition: "left 0.5s linear" }} />
      </div>

      <div style={{ padding: "10px 16px 12px", maxWidth: 900, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "nowrap" }}>

          {/* Album art */}
          <div style={{ position: "relative", flexShrink: 0 }}>
            {track?.cover_art
              ? <img src={track.cover_art} alt="" style={{ width: 48, height: 48, borderRadius: 6, boxShadow: `0 0 12px ${activeColor}44`, border: `1px solid ${activeColor}33` }} />
              : <div style={{ width: 48, height: 48, borderRadius: 6, background: "rgba(120,80,20,0.2)", display: "flex", alignItems: "center", justifyContent: "center", color: "rgba(180,140,80,0.4)" }}>{Ic.disc}</div>
            }
            {isPlaying && <div style={{ position: "absolute", inset: 0, borderRadius: 6, border: `1.5px solid ${activeColor}66`, animation: "pulseRing 2s ease infinite" }} />}
          </div>

          {/* Track info */}
          <div style={{ flex: "0 0 auto", minWidth: 0, maxWidth: 150 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#fde68a", fontFamily: "'Playfair Display', serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{track?.title || "—"}</div>
            <div style={{ fontSize: 10, color: "rgba(180,140,80,0.6)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{track?.artist || ""}</div>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.3)", marginTop: 1, display: "flex", alignItems: "center", gap: 4 }}>
              {fmt(elapsed)} / {fmt(duration || 0)}
              {useYT && (
                <span style={{ display: "flex", alignItems: "center", gap: 2, color: vidMissing ? "rgba(180,80,80,0.4)" : ytSearching ? "rgba(217,119,6,0.5)" : "rgba(255,80,80,0.55)" }}>
                  {Ic.yt} {ytSearching ? "searching…" : vidMissing ? "no video" : ""}
                </span>
              )}
              {!useYT && <span style={{ opacity: 0.5 }}>30s preview</span>}
            </div>
          </div>

          {/* Controls */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <button onClick={toggleShuffle} style={{ ...S.ctrl, color: shuffle ? activeColor : "rgba(180,140,80,0.35)" }} title="Shuffle">{Ic.shuffle}</button>
              <button onClick={handlePrev} style={S.ctrl} title="Previous">{Ic.prev}</button>

              <button
                onClick={togglePlay}
                disabled={!canPlay}
                title={useYT ? (ytSearching ? "Searching YouTube…" : vidMissing ? "No video found for this track" : isPlaying ? "Pause" : "Play full track") : (track?.preview_url ? "Play 30s preview" : "No preview available")}
                style={{ ...S.ctrl, width: 42, height: 42, borderRadius: "50%", background: canPlay ? `linear-gradient(135deg, ${activeColor}cc, ${activeColor})` : "rgba(60,40,10,0.4)", border: `1px solid ${activeColor}55`, color: canPlay ? "#000" : "rgba(120,80,20,0.3)", boxShadow: canPlay ? `0 0 16px ${activeColor}44` : "none", opacity: canPlay ? 1 : 0.5 }}
              >
                {ytSearching
                  ? <div style={{ width: 14, height: 14, border: `2px solid ${activeColor}44`, borderTopColor: activeColor, borderRadius: "50%", animation: "mpSpin 0.8s linear infinite" }} />
                  : isPlaying ? Ic.pause : Ic.play}
              </button>

              <button onClick={handleNext} style={S.ctrl} title="Next">{Ic.next}</button>
              <button onClick={cycleRepeat} style={{ ...S.ctrl, color: repeat !== "off" ? activeColor : "rgba(180,140,80,0.35)", position: "relative" }} title={`Repeat: ${repeat}`}>
                {Ic.repeat}
                {repeat === "one" && <span style={{ position: "absolute", top: -4, right: -4, fontSize: 7, color: activeColor, fontWeight: "bold" }}>1</span>}
              </button>
            </div>

            <div style={{ fontSize: 8, letterSpacing: "0.1em", textTransform: "uppercase", display: "flex", alignItems: "center", gap: 3, color: useYT ? "rgba(255,80,80,0.5)" : "rgba(180,140,80,0.2)" }}>
              {useYT ? <>{Ic.yt} Full length · YouTube</> : "Connect YouTube for full tracks"}
            </div>
          </div>

          {/* Right controls */}
          <div style={{ display: "flex", alignItems: "center", gap: 5, flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <button onClick={() => setMuted(m => !m)} style={{ ...S.ctrl, color: muted ? "rgba(180,140,80,0.3)" : "rgba(180,140,80,0.6)" }}>{muted ? Ic.volMute : Ic.volHigh}</button>
              <input type="range" min="0" max="1" step="0.05" value={muted ? 0 : volume} onChange={e => { setVolume(+e.target.value); setMuted(false); }} style={{ width: 55, accentColor: activeColor, cursor: "pointer" }} />
            </div>

            <button onClick={() => setShowQueue(s => !s)} style={{ ...S.ctrl, color: showQueue ? activeColor : "rgba(180,140,80,0.4)" }} title={`Queue (${queue.length})`}>{Ic.queue}</button>

            {spotifyConnected && (
              <button onClick={handleExport} disabled={exporting} style={{ ...S.ctrl, padding: "4px 8px", borderRadius: 6, background: "rgba(29,185,84,0.15)", border: "1px solid rgba(29,185,84,0.4)", color: exportDone?.url ? "#34d399" : "#1db954", fontSize: 10, fontFamily: "'DM Mono', monospace", display: "flex", alignItems: "center", gap: 4, opacity: exporting ? 0.6 : 1 }} title="Export to Spotify">
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
            <button onClick={onClose} style={{ ...S.ctrl, opacity: 0.4 }} title="Close player">{Ic.close}</button>
          </div>
        </div>

        {/* Queue */}
        {showQueue && (
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(120,80,20,0.2)", maxHeight: 200, overflowY: "auto", scrollbarWidth: "thin", scrollbarColor: `${activeColor}44 transparent` }}>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: 8, fontFamily: "'DM Mono', monospace" }}>
              Queue — {queue.length} tracks {shuffle ? "· shuffled" : ""} {useYT ? "· full length · YouTube" : "· 30s previews"}
            </div>
            {queue.map((t, i) => {
              const vid = _getVid(t);
              return (
                <div key={`${t.title}|${i}`} onClick={() => setQueueIdx(i)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 6px", borderRadius: 6, cursor: "pointer", background: i === queueIdx ? `${activeColor}18` : "transparent", border: `1px solid ${i === queueIdx ? activeColor + "44" : "transparent"}`, transition: "all 0.15s", marginBottom: 2 }}>
                  <span style={{ fontSize: 9, color: "rgba(180,140,80,0.3)", width: 16, textAlign: "right", flexShrink: 0 }}>{i === queueIdx ? "▶" : i + 1}</span>
                  {t.cover_art ? <img src={t.cover_art} alt="" style={{ width: 24, height: 24, borderRadius: 3, flexShrink: 0 }} /> : <div style={{ width: 24, height: 24, borderRadius: 3, background: "rgba(120,80,20,0.2)", flexShrink: 0 }} />}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: i === queueIdx ? "#fde68a" : "rgba(220,190,140,0.8)", fontFamily: "'Playfair Display', serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.title}</div>
                    <div style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.artist}</div>
                  </div>
                  {useYT && (
                    <span style={{ fontSize: 8, flexShrink: 0, color: vid ? "rgba(255,80,80,0.6)" : _busy(t) ? "rgba(217,119,6,0.4)" : vid === null ? "rgba(120,80,20,0.3)" : "rgba(120,80,20,0.2)" }}>
                      {vid ? "▶" : _busy(t) ? "…" : vid === null ? "✕" : "–"}
                    </span>
                  )}
                  {!useYT && !t.preview_url && <span style={{ fontSize: 8, color: "rgba(180,140,80,0.2)", flexShrink: 0 }}>no preview</span>}
                </div>
              );
            })}
          </div>
        )}

        {exportDone && !exportDone.error && exportDone.url && (
          <div style={{ marginTop: 8, fontSize: 10, color: "#34d399", display: "flex", gap: 8, fontFamily: "'DM Mono', monospace" }}>
            ✓ Exported! <a href={exportDone.url} target="_blank" rel="noopener noreferrer" style={{ color: "#1db954" }}>Open in Spotify ↗</a>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulseRing { 0%,100%{opacity:.8;transform:scale(1);} 50%{opacity:.3;transform:scale(1.04);} }
        @keyframes mpSpin    { to{transform:rotate(360deg);} }
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
