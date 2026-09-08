import { useState, useEffect, useRef, useCallback } from "react";

const _VID_CACHE = new Map();
const _VID_FETCHING = new Set();
const keyOf = (t) => `${t?.title || ""}|${t?.artist || ""}`;
const getVid = (t) => _VID_CACHE.has(keyOf(t)) ? _VID_CACHE.get(keyOf(t)) : undefined;
const setVid = (t, v) => _VID_CACHE.set(keyOf(t), v);

// YouTube's IFrame API requires a real player viewport of at least 200x200.
// Keep the player visually transparent, but do not collapse it to 160x90/off-screen.
const ytSrc = (videoId) => {
  const params = new URLSearchParams({
    enablejsapi: "1",
    autoplay: "1",
    mute: "1",
    controls: "0",
    rel: "0",
    modestbranding: "1",
    playsinline: "1",
    origin: window.location.origin,
  });
  return `https://www.youtube.com/embed/${videoId}?${params.toString()}`;
};

const fmt = (s) => {
  if (!Number.isFinite(s) || s < 0) return "0:00";
  const sec = Math.floor(s);
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
};

const shuffleArray = (arr) => {
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
};

const Icon = ({ children, size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">{children}</svg>
);
const Play = () => <Icon><polygon points="7,4 20,12 7,20" /></Icon>;
const Pause = () => <Icon><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></Icon>;
const Prev = () => <Icon><polygon points="18,4 9,12 18,20"/><rect x="5" y="5" width="2" height="14" rx="1"/></Icon>;
const Next = () => <Icon><polygon points="6,4 15,12 6,20"/><rect x="17" y="5" width="2" height="14" rx="1"/></Icon>;
const Disc = () => <Icon size={18}><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2"/><circle cx="12" cy="12" r="3"/></Icon>;
const Close = () => <Icon><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round"/></Icon>;

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
  visibleServices = {},
  onServiceAction,
}) {
  const useYT = Boolean(visibleServices?.youtube && servicesConnected?.youtube);

  const [queue, setQueue] = useState(() => tracks.map((t, i) => ({ ...t, _origIdx: i })));
  const [queueIdx, setQueueIdx] = useState(() => Math.max(0, Math.min(initialIndex, Math.max(tracks.length - 1, 0))));
  const [isPlaying, setIsPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.7);
  const [muted, setMuted] = useState(false);
  const [shuffle, setShuffle] = useState(false);
  const [repeat, setRepeat] = useState("off");
  const [showQueue, setShowQueue] = useState(false);
  const [minimised, setMinimised] = useState(false);
  const [ytSearching, setYtSearching] = useState(false);
  const [currentVideoId, setCurrentVideoId] = useState(undefined);
  const [exporting, setExporting] = useState(false);
  const [toast, setToast] = useState("");

  const iframeRef = useRef(null);
  const audioRef = useRef(null);
  const ytReadyRef = useRef(false);
  const desiredPlayingRef = useRef(false);
  const queuedCommandsRef = useRef([]);
  const queueIdxRef = useRef(queueIdx);
  const queueRef = useRef(queue);
  const repeatRef = useRef(repeat);
  const isPlayingRef = useRef(isPlaying);
  const durationRef = useRef(duration);
  const elapsedRef = useRef(elapsed);
  const queryTimerRef = useRef(null);

  useEffect(() => { queueIdxRef.current = queueIdx; }, [queueIdx]);
  useEffect(() => { queueRef.current = queue; }, [queue]);
  useEffect(() => { repeatRef.current = repeat; }, [repeat]);
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { durationRef.current = duration; }, [duration]);
  useEffect(() => { elapsedRef.current = elapsed; }, [elapsed]);

  const track = queue[queueIdx] || queue[0] || null;

  const fetchVideoId = useCallback(async (t, priority = false) => {
    if (!buildApiUrl || !t) return null;
    const cached = getVid(t);
    if (cached !== undefined) return cached;
    const key = keyOf(t);
    if (_VID_FETCHING.has(key)) return null;
    _VID_FETCHING.add(key);
    if (priority) setYtSearching(true);
    try {
      const url = buildApiUrl(`/api/services/youtube/search?title=${encodeURIComponent(t.title)}&artist=${encodeURIComponent(t.artist)}&q=${encodeURIComponent(`${t.title} ${t.artist} official audio`)}`);
      const res = await fetch(url);
      if (!res.ok) {
        setVid(t, null);
        return null;
      }
      const data = await res.json();
      const id = data?.found && data?.video_id ? data.video_id : null;
      setVid(t, id);
      return id;
    } catch {
      setVid(t, null);
      return null;
    } finally {
      _VID_FETCHING.delete(key);
      if (priority) setYtSearching(false);
    }
  }, [buildApiUrl]);

  // Prefetch a small runway so next/previous never feel like they wait on search.
  useEffect(() => {
    if (!useYT) return;
    const end = Math.min(queue.length, queueIdx + 4);
    for (let i = queueIdx; i < end; i++) {
      const t = queue[i];
      if (getVid(t) === undefined && !_VID_FETCHING.has(keyOf(t))) {
        window.setTimeout(() => { void fetchVideoId(t); }, Math.max(0, i - queueIdx) * 200);
      }
    }
  }, [queueIdx, queue, useYT, fetchVideoId]);

  const postYt = useCallback((func, args = []) => {
    const frame = iframeRef.current;
    if (!frame || !frame.src.includes("youtube.com") || !frame.contentWindow) return false;
    const message = JSON.stringify({ event: "command", func, args });
    if (!ytReadyRef.current) {
      // Keep only the latest transport command of the same type. This prevents a stale
      // play from being replayed after the user has already pressed pause during loading.
      if (func === "playVideo" || func === "pauseVideo") {
        queuedCommandsRef.current = queuedCommandsRef.current.filter(c => c.func !== "playVideo" && c.func !== "pauseVideo");
      }
      queuedCommandsRef.current.push({ message, origin: "https://www.youtube.com" });
      return false;
    }
    try {
      frame.contentWindow.postMessage(message, "https://www.youtube.com");
      return true;
    } catch {
      return false;
    }
  }, []);

  const flushYt = useCallback(() => {
    const frame = iframeRef.current;
    if (!frame?.contentWindow) return;
    const commands = queuedCommandsRef.current.splice(0);
    for (const { message, origin } of commands) {
      try { frame.contentWindow.postMessage(message, origin); } catch {}
    }
    try {
      frame.contentWindow.postMessage(JSON.stringify({ event: "command", func: "setVolume", args: [muted ? 0 : Math.round(volume * 100)] }), "https://www.youtube.com");
      if (muted) frame.contentWindow.postMessage(JSON.stringify({ event: "command", func: "mute", args: [] }), "https://www.youtube.com");
      else frame.contentWindow.postMessage(JSON.stringify({ event: "command", func: "unMute", args: [] }), "https://www.youtube.com");
      frame.contentWindow.postMessage(JSON.stringify({ event: "command", func: desiredPlayingRef.current ? "playVideo" : "pauseVideo", args: [] }), "https://www.youtube.com");
    } catch {}
  }, [muted, volume]);

  const loadYouTube = useCallback((t, shouldPlay) => {
    if (!iframeRef.current || !t) return;
    const vid = getVid(t);
    if (!vid) {
      setCurrentVideoId(vid === null ? null : undefined);
      setIsPlaying(false);
      ytReadyRef.current = false;
      iframeRef.current.src = "about:blank";
      return;
    }
    desiredPlayingRef.current = shouldPlay;
    ytReadyRef.current = false;
    queuedCommandsRef.current = [];
    setCurrentVideoId(vid);
    setElapsed(0);
    setDuration(0);
    setIsPlaying(false);
    iframeRef.current.src = ytSrc(vid);
  }, []);

  // React to queue changes. A next/prev click inherits the previous playing intent.
  useEffect(() => {
    if (!useYT || !track) return;
    let active = true;
    const shouldPlay = desiredPlayingRef.current || queueIdx === initialIndex && isPlayingRef.current;
    const vid = getVid(track);
    if (vid === undefined) {
      desiredPlayingRef.current = shouldPlay;
      void fetchVideoId(track, true).then(id => {
        if (active && id) loadYouTube(track, shouldPlay);
      });
    } else {
      loadYouTube(track, shouldPlay);
    }
    return () => { active = false; };
  }, [queueIdx, track, useYT, fetchVideoId, loadYouTube, initialIndex]);

  // YouTube transport event listener. The source check stops stale iframes from changing UI state.
  useEffect(() => {
    if (!useYT) return;
    const handler = (event) => {
      if (event.origin !== "https://www.youtube.com") return;
      if (iframeRef.current?.contentWindow && event.source !== iframeRef.current.contentWindow) return;
      try {
        const data = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
        if (!data) return;
        if (data.event === "onReady") {
          ytReadyRef.current = true;
          flushYt();
          return;
        }
        if (data.event === "onAutoplayBlocked") {
          desiredPlayingRef.current = false;
          setIsPlaying(false);
          setToast("YouTube blocked autoplay — press play once to start audio.");
          window.setTimeout(() => setToast(""), 3500);
          return;
        }
        if (data.event === "onStateChange") {
          const state = Number(data.info);
          if (state === 1) {
            setIsPlaying(true);
            isPlayingRef.current = true;
            desiredPlayingRef.current = true;
          } else if (state === 2) {
            setIsPlaying(false);
            isPlayingRef.current = false;
          } else if (state === 0) {
            const idx = queueIdxRef.current;
            const q = queueRef.current;
            const rep = repeatRef.current;
            if (rep === "one") {
              desiredPlayingRef.current = true;
              loadYouTube(q[idx], true);
            } else if (idx < q.length - 1) {
              desiredPlayingRef.current = true;
              setQueueIdx(idx + 1);
            } else if (rep === "all") {
              desiredPlayingRef.current = true;
              setQueueIdx(0);
            } else {
              desiredPlayingRef.current = false;
              setIsPlaying(false);
            }
          }
          return;
        }
        if (data.event === "infoDelivery" && data.info) {
          const nextDuration = Number(data.info.duration);
          const nextTime = Number(data.info.currentTime);
          if (Number.isFinite(nextDuration) && nextDuration > 0) setDuration(nextDuration);
          if (Number.isFinite(nextTime) && nextTime >= 0) setElapsed(nextTime);
        }
      } catch {}
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [useYT, flushYt, loadYouTube]);

  // Poll actual YouTube time instead of estimating from wall clock. This also acts as a
  // lightweight readiness probe for embeds that do not emit an initial infoDelivery packet.
  useEffect(() => {
    window.clearInterval(queryTimerRef.current);
    if (!useYT) return;
    queryTimerRef.current = window.setInterval(() => {
      if (!ytReadyRef.current) return;
      postYt("getCurrentTime");
      postYt("getDuration");
    }, 800);
    return () => window.clearInterval(queryTimerRef.current);
  }, [useYT, postYt]);

  useEffect(() => () => window.clearInterval(queryTimerRef.current), []);

  // Native 30-second preview fallback when YouTube is unavailable.
  useEffect(() => {
    if (useYT) return;
    const audio = new Audio();
    audio.preload = "auto";
    audio.volume = muted ? 0 : volume;
    audioRef.current = audio;
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onTime = () => setElapsed(audio.currentTime || 0);
    const onDuration = () => setDuration(Number.isFinite(audio.duration) ? audio.duration : 0);
    const onEnded = () => {
      const idx = queueIdxRef.current;
      const q = queueRef.current;
      const rep = repeatRef.current;
      if (rep === "one") { audio.currentTime = 0; void audio.play().catch(() => {}); }
      else if (idx < q.length - 1) setQueueIdx(idx + 1);
      else if (rep === "all") setQueueIdx(0);
      else setIsPlaying(false);
    };
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("durationchange", onDuration);
    audio.addEventListener("ended", onEnded);
    if (track?.preview_url) {
      audio.src = track.preview_url;
      void audio.play().catch(() => {});
    }
    return () => {
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("durationchange", onDuration);
      audio.removeEventListener("ended", onEnded);
      audio.pause();
      audio.src = "";
      audioRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (useYT || !audioRef.current) return;
    const audio = audioRef.current;
    if (!track?.preview_url) {
      audio.pause();
      audio.removeAttribute("src");
      setIsPlaying(false);
      setElapsed(0);
      setDuration(0);
      return;
    }
    audio.src = track.preview_url;
    audio.volume = muted ? 0 : volume;
    if (desiredPlayingRef.current || isPlayingRef.current) void audio.play().catch(() => {});
  }, [queueIdx, queue, useYT, track, muted, volume]);

  useEffect(() => {
    const v = muted ? 0 : volume;
    if (audioRef.current) audioRef.current.volume = v;
    if (useYT) {
      postYt("setVolume", [Math.round(v * 100)]);
      postYt(muted ? "mute" : "unMute");
    }
  }, [volume, muted, useYT, postYt]);

  const setPlayingIntent = useCallback((next) => {
    desiredPlayingRef.current = next;
    setIsPlaying(next);
    if (useYT) {
      postYt(next ? "unMute" : "pauseVideo");
      postYt("setVolume", [muted ? 0 : Math.round(volume * 100)]);
      if (next) postYt("playVideo");
    } else if (audioRef.current) {
      if (next) void audioRef.current.play().catch(() => setIsPlaying(false));
      else audioRef.current.pause();
    }
  }, [useYT, postYt, muted, volume]);

  const togglePlay = useCallback(() => {
    setPlayingIntent(!isPlayingRef.current);
  }, [setPlayingIntent]);

  const handleNext = useCallback(() => {
    const q = queueRef.current;
    if (!q.length) return;
    desiredPlayingRef.current = isPlayingRef.current;
    setQueueIdx(i => {
      if (repeatRef.current === "one") return i;
      if (i < q.length - 1) return i + 1;
      return repeatRef.current === "all" ? 0 : i;
    });
  }, []);

  const handlePrev = useCallback(() => {
    if (elapsedRef.current > 3) {
      if (useYT) postYt("seekTo", [0, true]);
      else if (audioRef.current) audioRef.current.currentTime = 0;
      setElapsed(0);
      return;
    }
    desiredPlayingRef.current = isPlayingRef.current;
    setQueueIdx(i => Math.max(0, i - 1));
  }, [useYT, postYt]);

  const seekTo = useCallback((event) => {
    if (!durationRef.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const next = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)) * durationRef.current;
    setElapsed(next);
    if (useYT) postYt("seekTo", [next, true]);
    else if (audioRef.current) audioRef.current.currentTime = next;
  }, [useYT, postYt]);

  const toggleShuffle = () => {
    const current = queueRef.current[queueIdxRef.current];
    if (!current) return;
    if (!shuffle) {
      const rest = queueRef.current.filter((_, i) => i !== queueIdxRef.current);
      setQueue([current, ...shuffleArray(rest)]);
      setQueueIdx(0);
    } else {
      setQueue(tracks.map((t, i) => ({ ...t, _origIdx: i })));
      setQueueIdx(current._origIdx ?? 0);
    }
    setShuffle(s => !s);
  };

  const cycleRepeat = () => setRepeat(r => r === "off" ? "all" : r === "all" ? "one" : "off");

  const handleExport = async () => {
    if (!onExportSpotify) return;
    setExporting(true);
    try { await onExportSpotify(tracks); setToast("Exported to Spotify"); }
    catch { setToast("Spotify export failed"); }
    finally { setExporting(false); window.setTimeout(() => setToast(""), 2500); }
  };

  const serviceAction = async (service, action) => {
    try { await onServiceAction?.(service, action, track); setToast(`♥ ${action}`); }
    catch { setToast("Action failed"); }
    window.setTimeout(() => setToast(""), 2200);
  };

  useEffect(() => {
    if (!window.chrome?.webview) return;
    const payload = JSON.stringify({
      type: "VIBEFINDER_STATE",
      isPlaying,
      title: track?.title || "—",
      artist: track?.artist || "—",
      coverArt: track?.cover_art || null,
      previewUrl: track?.preview_url || null,
      currentTime: elapsed,
      duration,
    });
    try { window.chrome.webview.postMessage(payload); } catch {}
  }, [isPlaying, track, elapsed, duration]);

  useEffect(() => {
    if (!window.chrome?.webview) return;
    const handler = (event) => {
      try {
        const msg = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
        if (msg?.command === "playpause") togglePlay();
        else if (msg?.command === "next") handleNext();
        else if (msg?.command === "prev") handlePrev();
      } catch {}
    };
    window.chrome.webview.addEventListener("message", handler);
    return () => window.chrome.webview.removeEventListener("message", handler);
  }, [togglePlay, handleNext, handlePrev]);

  const progress = duration > 0 ? Math.min(1, elapsed / duration) : 0;
  const vid = track ? getVid(track) : undefined;
  const canPlay = useYT ? Boolean(vid || ytSearching) : Boolean(track?.preview_url);

  const playerStyles = {
    shell: { position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 200, padding: "10px 14px 12px", background: "linear-gradient(180deg, rgba(10,5,0,.98), rgba(4,2,0,.99))", borderTop: `1px solid ${activeColor}44`, boxShadow: "0 -12px 40px rgba(0,0,0,.72)", color: "#fde68a", fontFamily: "system-ui, sans-serif" },
    row: { maxWidth: 980, margin: "0 auto", display: "flex", alignItems: "center", gap: 10 },
    btn: { border: 0, background: "transparent", color: "rgba(230,200,150,.72)", display: "grid", placeItems: "center", width: 32, height: 32, borderRadius: 9, cursor: "pointer" },
  };

  if (minimised) return (
    <>
      {useYT && <iframe ref={iframeRef} src="about:blank" title="vibefinder-youtube" allow="autoplay; encrypted-media; picture-in-picture" style={{ position: "fixed", width: 200, height: 200, right: 2, bottom: 2, opacity: 0.01, border: 0, pointerEvents: "none", zIndex: 1 }} onLoad={() => {
        const frame = iframeRef.current;
        if (!frame?.src.includes("youtube.com") || !frame.contentWindow) return;
        ytReadyRef.current = true;
        try { frame.contentWindow.postMessage(JSON.stringify({ event: "listening", id: 1 }), "https://www.youtube.com"); } catch {}
        flushYt();
      }} />}
      <div style={{ ...playerStyles.shell, left: "50%", right: "auto", bottom: 16, transform: "translateX(-50%)", width: "min(520px, 92vw)", border: `1px solid ${activeColor}44`, borderRadius: 18 }}>
        <div style={playerStyles.row}>
          {track?.cover_art ? <img src={track.cover_art} alt="" style={{ width: 34, height: 34, borderRadius: 6, objectFit: "cover" }} /> : <div style={{ width: 34, height: 34, display: "grid", placeItems: "center" }}><Disc /></div>}
          <div style={{ flex: 1, minWidth: 0 }}><div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontSize: 12 }}>{track?.title || "Nothing playing"}</div><div style={{ opacity: .52, fontSize: 10, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{track?.artist || ""}</div></div>
          <button style={playerStyles.btn} onClick={togglePlay}>{isPlaying ? <Pause /> : <Play />}</button>
          <button style={playerStyles.btn} onClick={handleNext}><Next /></button>
          <button style={playerStyles.btn} onClick={() => setMinimised(false)}>⌃</button>
        </div>
      </div>
    </>
  );

  return (
    <div style={playerStyles.shell}>
      {useYT && <iframe ref={iframeRef} src="about:blank" title="vibefinder-youtube" allow="autoplay; encrypted-media; picture-in-picture" onLoad={() => {
        const frame = iframeRef.current;
        if (!frame?.src.includes("youtube.com") || !frame.contentWindow) return;
        ytReadyRef.current = true;
        try { frame.contentWindow.postMessage(JSON.stringify({ event: "listening", id: 1 }), "https://www.youtube.com"); } catch {}
        flushYt();
      }} style={{ position: "fixed", width: 200, height: 200, right: 2, bottom: 2, opacity: 0.01, border: 0, pointerEvents: "none", zIndex: 1 }} />}

      <div onClick={seekTo} style={{ height: 4, maxWidth: 980, margin: "0 auto 10px", background: "rgba(160,110,30,.18)", borderRadius: 99, cursor: "pointer", position: "relative" }}>
        <div style={{ height: "100%", width: `${progress * 100}%`, borderRadius: 99, background: `linear-gradient(90deg, ${activeColor}88, ${activeColor})` }} />
      </div>

      <div style={playerStyles.row}>
        {track?.cover_art ? <img src={track.cover_art} alt="" style={{ width: 50, height: 50, borderRadius: 8, objectFit: "cover", boxShadow: `0 0 16px ${activeColor}33` }} /> : <div style={{ width: 50, height: 50, borderRadius: 8, display: "grid", placeItems: "center", background: "rgba(120,80,20,.16)" }}><Disc /></div>}
        <div style={{ width: 175, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{track?.title || "—"}</div>
          <div style={{ opacity: .55, fontSize: 10, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{track?.artist || ""}</div>
          <div style={{ opacity: .35, fontSize: 9, marginTop: 2 }}>{fmt(elapsed)} / {fmt(duration)}{useYT ? ` · ${vid === null ? "no YouTube match" : ytSearching ? "searching…" : "YouTube"}` : " · preview"}</div>
        </div>

        <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center", gap: 4 }}>
          <button style={playerStyles.btn} onClick={toggleShuffle} title="Shuffle">⇄</button>
          <button style={playerStyles.btn} onClick={handlePrev} title="Previous"><Prev /></button>
          <button disabled={!canPlay} style={{ ...playerStyles.btn, width: 46, height: 46, borderRadius: "50%", background: canPlay ? activeColor : "rgba(90,60,15,.35)", color: canPlay ? "#140a00" : "rgba(255,255,255,.25)", boxShadow: canPlay ? `0 0 22px ${activeColor}44` : "none" }} onClick={togglePlay} title={canPlay ? (isPlaying ? "Pause" : "Play") : "No playable source"}>
            {ytSearching ? "…" : isPlaying ? <Pause /> : <Play />}
          </button>
          <button style={playerStyles.btn} onClick={handleNext} title="Next"><Next /></button>
          <button style={{ ...playerStyles.btn, position: "relative", color: repeat !== "off" ? activeColor : undefined }} onClick={cycleRepeat} title={`Repeat: ${repeat}`}>↻{repeat === "one" ? <span style={{ position: "absolute", top: 1, right: 3, fontSize: 7 }}>1</span> : null}</button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <button style={playerStyles.btn} onClick={() => setMuted(m => !m)}>{muted ? "🔇" : "🔊"}</button>
          <input type="range" min="0" max="1" step="0.05" value={muted ? 0 : volume} onChange={e => { setVolume(Number(e.target.value)); setMuted(false); }} style={{ width: 65, accentColor: activeColor }} />
          <button style={playerStyles.btn} onClick={() => setShowQueue(s => !s)} title="Queue">☷</button>
          {spotifyConnected && <button style={{ ...playerStyles.btn, width: 58, fontSize: 9 }} disabled={exporting} onClick={handleExport}>{exporting ? "…" : "Spotify"}</button>}
          {visibleServices?.lastfm && servicesConnected?.lastfm && <button style={{ ...playerStyles.btn, width: 48, fontSize: 9 }} onClick={() => serviceAction("lastfm", "love")}>♥</button>}
          <button style={playerStyles.btn} onClick={() => setMinimised(true)}>⌄</button>
          <button style={playerStyles.btn} onClick={onClose}><Close /></button>
        </div>
      </div>

      {showQueue && <div style={{ maxWidth: 980, margin: "10px auto 0", paddingTop: 8, borderTop: "1px solid rgba(160,110,30,.16)", maxHeight: 210, overflow: "auto" }}>
        {queue.map((t, i) => <button key={`${t.title}|${i}`} onClick={() => { desiredPlayingRef.current = isPlayingRef.current; setQueueIdx(i); }} style={{ width: "100%", border: 0, background: i === queueIdx ? `${activeColor}14` : "transparent", color: "inherit", textAlign: "left", padding: "6px 4px", cursor: "pointer", display: "flex", gap: 8, alignItems: "center", borderRadius: 7 }}>
          <span style={{ width: 18, opacity: .4, fontSize: 9 }}>{i === queueIdx ? "▶" : i + 1}</span>
          {t.cover_art ? <img src={t.cover_art} alt="" style={{ width: 26, height: 26, borderRadius: 4, objectFit: "cover" }} /> : <div style={{ width: 26, height: 26, borderRadius: 4, background: "rgba(120,80,20,.14)" }} />}
          <span style={{ minWidth: 0, flex: 1 }}><span style={{ display: "block", fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.title}</span><span style={{ display: "block", fontSize: 9, opacity: .38, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.artist}</span></span>
        </button>)}
      </div>}

      {toast && <div style={{ maxWidth: 980, margin: "7px auto 0", fontSize: 10, color: activeColor, opacity: .85 }}>{toast}</div>}
    </div>
  );
}
