import { useState, useEffect, useRef } from "react";

const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const buildApiUrl = (path) => API_BASE_URL ? `${API_BASE_URL}${path}` : path;

const vibeColors = {
  hype: '#f87171', calm: '#34d399', intense: '#f97316', chill: '#60a5fa',
  focus: '#22d3ee', euphoric: '#e879f9', soulful: '#fbbf24', retro: '#818cf8',
  dreamy: '#c084fc', cinematic: '#fb923c', dark: '#9ca3af', heartbreak: '#f472b6',
  hyperpop: '#d946ef', party: '#ec4899', country: '#d97706', tropical: '#14b8a6',
  industrial: '#6b7280', desi: '#e11d48', happy: '#facc15', neutral: '#d97706',
};

const IconPlay   = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>;
const IconPause  = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>;
const IconDisc   = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>;
const IconShare  = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>;
const IconWave   = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>;

function Vinyl({ spinning, color = "#d97706" }) {
  return (
    <div style={{
      width: 48, height: 48, borderRadius: "50%", flexShrink: 0,
      background: "conic-gradient(from 0deg, #1a1008, #2e1f0d, #1a1008, #2e1f0d, #1a1008, #2e1f0d, #1a1008, #2e1f0d)",
      boxShadow: `0 0 0 2px rgba(180,140,80,0.3), 0 4px 16px rgba(0,0,0,0.7)`,
      display: "flex", alignItems: "center", justifyContent: "center",
      animation: spinning ? "spin 2.4s linear infinite" : "none",
    }}>
      <div style={{ width: 13, height: 13, borderRadius: "50%", background: `radial-gradient(circle, ${color} 40%, #7a4f12 100%)`, boxShadow: `0 0 6px ${color}88` }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function WaveformBars({ active, count = 18 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "3px", height: "28px" }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{
          width: "3px", borderRadius: "2px",
          minHeight: "4px", maxHeight: "28px",
          background: active ? `hsl(${38 + i * 1.5}, 80%, ${48 + (i % 4) * 5}%)` : "rgba(180,140,80,0.2)",
          animationName: active ? "barDance" : "none",
          animationDuration: `${350 + (i % 7) * 80}ms`,
          animationDelay: `${(i * 40) % 700}ms`,
          animationTimingFunction: "ease-in-out",
          animationIterationCount: "infinite",
          animationDirection: "alternate",
        }} />
      ))}
      <style>{`@keyframes barDance { from { height: 4px; } to { height: 26px; } }`}</style>
    </div>
  );
}

export default function SharedPlaylist() {
  const [playlist, setPlaylist]   = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");
  const [playingUrl, setPlayingUrl] = useState(null);
  const [copied, setCopied]         = useState(false);
  const [views, setViews]           = useState(null);
  const audioRef = useRef(null);

  // Extract share token from URL path: /playlist/:token
  const token = window.location.pathname.split("/playlist/")[1]?.split("/")[0];
  const activeColor = playlist ? (vibeColors[playlist.dominant_vibe] || vibeColors.neutral) : vibeColors.neutral;

  const [forking, setForking] = useState(false);
  const [forkSuccess, setForkSuccess] = useState(false);

  const forkPlaylist = async () => {
    // If not on app with a token, they'll need to auth. For Phase 9 anonymous forking we can 
    // handle a redirect to /app with a fork intent, or if we have a token, do it directly.
    const userToken = localStorage.getItem("vf_token");
    if (!userToken) {
      alert("You need to login first to fork playlists (Phase 9 feature under development)");
      return;
    }
    
    setForking(true);
    try {
      const r = await fetch(buildApiUrl(`/api/playlist/${token}/fork`), {
        method: "POST",
        headers: { "Authorization": `Bearer ${userToken}` }
      });
      if (!r.ok) throw new Error("Failed to fork playlist");
      setForkSuccess(true);
      setTimeout(() => setForkSuccess(false), 3000);
    } catch (e) {
      alert(e.message);
    } finally {
      setForking(false);
    }
  };

  useEffect(() => {
    if (!token) { setError("Invalid playlist link."); setLoading(false); return; }
    fetch(buildApiUrl(`/api/playlist/share/${token}`))
      .then(r => { if (!r.ok) throw new Error(r.status === 404 ? "Playlist not found or is private." : "Failed to load playlist."); return r.json(); })
      .then(data => {
        setPlaylist(data);
        setViews(data.view_count ?? null);
        setLoading(false);
        // Silently increment view count
        fetch(buildApiUrl(`/api/playlist/share/${token}/view`), { method: "POST" }).catch(() => {});
      })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [token]);

  useEffect(() => {
    audioRef.current = new Audio();
    audioRef.current.volume = 0.6;
    audioRef.current.onended = () => setPlayingUrl(null);
    return () => { audioRef.current.pause(); audioRef.current.src = ""; };
  }, []);

  const togglePlay = (url) => {
    if (!url) return;
    if (playingUrl === url) { audioRef.current.pause(); setPlayingUrl(null); }
    else { audioRef.current.src = url; audioRef.current.play(); setPlayingUrl(url); }
  };

  const shareLink = () => {
    const shareData = {
      title: playlist?.name || "VibeFinder Playlist",
      text: playlist?.prompt ? `"${playlist.prompt}" — ${playlist.track_count} tracks on VibeFinder` : `Check out this playlist on VibeFinder`,
      url: window.location.href,
    };
    if (navigator.share && navigator.canShare?.(shareData)) {
      navigator.share(shareData).catch(() => {});
    } else {
      navigator.clipboard.writeText(window.location.href).then(() => {
        setCopied(true); setTimeout(() => setCopied(false), 2500);
      });
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Mono:wght@400;500&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body {
          background: #17110b;
          background-image: radial-gradient(ellipse 80% 60% at 50% -10%, rgba(120,60,10,0.18) 0%, transparent 70%);
          min-height: 100vh;
          color: #e8d5a3;
          font-family: 'DM Mono', monospace;
        }
        @keyframes fadeSlide { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
        .fade-in { animation: fadeSlide 0.5s ease forwards; }
        .fade-in-2 { animation: fadeSlide 0.5s ease 0.15s both; }
        .fade-in-3 { animation: fadeSlide 0.5s ease 0.3s both; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
        .track-row { transition: background 0.2s, border-color 0.2s; }
        .track-row:hover { background: rgba(30,18,6,0.8) !important; }
        @keyframes spin360 { to { transform: rotate(360deg); } }
      `}</style>

      <div style={{ minHeight: "100vh", padding: "32px 16px 80px" }}>
        <div style={{ maxWidth: "760px", margin: "0 auto" }}>

          {/* ── HEADER ── */}
          <div className="fade-in" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "36px", paddingBottom: "20px", borderBottom: "1px solid rgba(155,105,28,0.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div style={{ width: 36, height: 36, borderRadius: "50%", background: "conic-gradient(from 0deg, #1a1008, #3d2510, #1a1008)", border: `2px solid ${activeColor}44`, boxShadow: `0 0 16px ${activeColor}33`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div style={{ width: 9, height: 9, borderRadius: "50%", background: activeColor }} />
              </div>
              <div>
                <div style={{ fontFamily: "'Playfair Display', serif", fontSize: "18px", fontWeight: 900, color: "#e8d5a3", lineHeight: 1 }}>VibeFinder</div>
                <div style={{ fontSize: "9px", color: "rgba(180,140,80,0.45)", letterSpacing: "0.2em", textTransform: "uppercase" }}>Shared Playlist</div>
              </div>
            </div>
            <a href="/" style={{ fontSize: "11px", color: "rgba(180,140,80,0.5)", textDecoration: "none", letterSpacing: "0.1em", textTransform: "uppercase", border: "1px solid rgba(120,80,20,0.3)", padding: "7px 14px", borderRadius: "7px", transition: "color 0.2s, border-color 0.2s" }}
              onMouseOver={e => { e.currentTarget.style.color="#e8d5a3"; e.currentTarget.style.borderColor="rgba(180,140,80,0.5)"; }}
              onMouseOut={e => { e.currentTarget.style.color="rgba(180,140,80,0.5)"; e.currentTarget.style.borderColor="rgba(120,80,20,0.3)"; }}>
              Try VibeFinder →
            </a>
          </div>

          {/* ── LOADING ── */}
          {loading && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "20px", padding: "80px 0" }}>
              <Vinyl spinning color={activeColor} />
              <div style={{ fontSize: "11px", color: "rgba(180,140,80,0.4)", letterSpacing: "0.2em", textTransform: "uppercase", animation: "pulse 1.5s ease-in-out infinite" }}>Loading Playlist…</div>
            </div>
          )}

          {/* ── ERROR ── */}
          {error && !loading && (
            <div style={{ textAlign: "center", padding: "80px 0" }}>
              <div style={{ fontSize: "40px", marginBottom: "16px" }}>📡</div>
              <div style={{ fontFamily: "'Playfair Display', serif", fontSize: "22px", color: "#fde68a", marginBottom: "8px" }}>Signal Lost</div>
              <div style={{ fontSize: "12px", color: "rgba(180,140,80,0.5)", marginBottom: "28px" }}>{error}</div>
              <a href="/" style={{ display: "inline-block", padding: "10px 24px", background: "linear-gradient(135deg, #92400e, #d97706)", border: "1px solid rgba(251,191,36,0.3)", borderRadius: "8px", color: "#fef3c7", fontSize: "11px", fontFamily: "'DM Mono', monospace", letterSpacing: "0.12em", textTransform: "uppercase", textDecoration: "none" }}>
                Go to VibeFinder
              </a>
            </div>
          )}

          {/* ── PLAYLIST ── */}
          {playlist && !loading && (
            <>
              {/* Meta card */}
              <div className="fade-in" style={{ background: "linear-gradient(160deg, rgba(44,30,12,0.92) 0%, rgba(24,15,5,0.96) 100%)", border: `1px solid ${activeColor}33`, borderRadius: "16px", padding: "28px 28px 24px", marginBottom: "20px", position: "relative", overflow: "hidden" }}>
                <div style={{ position: "absolute", inset: 0, background: `radial-gradient(ellipse 60% 50% at 10% 0%, ${activeColor}08, transparent)`, pointerEvents: "none" }} />
                <div style={{ position: "relative" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "16px", flexWrap: "wrap" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                      <Vinyl spinning={!!playingUrl} color={activeColor} />
                      <div>
                        <div style={{ fontFamily: "'Playfair Display', serif", fontSize: "26px", fontWeight: 900, color: "#fde68a", lineHeight: 1.1, marginBottom: "6px" }}>{playlist.name}</div>
                        {playlist.prompt && (
                          <div style={{ fontSize: "12px", color: "rgba(180,140,80,0.55)", fontStyle: "italic", maxWidth: "420px", lineHeight: 1.5 }}>"{playlist.prompt}"</div>
                        )}
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "8px" }}>
                      {playlist.dominant_vibe && (
                        <div style={{ padding: "5px 12px", background: `${activeColor}18`, border: `1px solid ${activeColor}44`, borderRadius: "20px", fontSize: "11px", color: activeColor, letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 500 }}>
                          {playlist.dominant_vibe}
                        </div>
                      )}
                      <div style={{ fontSize: "10px", color: "rgba(180,140,80,0.4)", letterSpacing: "0.1em" }}>
                        {playlist.track_count} TRACKS
                      </div>
                    </div>
                  </div>

                  {/* Stats row */}
                  <div style={{ display: "flex", alignItems: "center", gap: "20px", marginTop: "20px", paddingTop: "16px", borderTop: "1px solid rgba(120,80,20,0.2)", flexWrap: "wrap" }}>
                    <WaveformBars active={!!playingUrl} count={16} />
                    <div style={{ display: "flex", gap: "12px", marginLeft: "auto", flexWrap: "wrap", alignItems: "center" }}>
                      {/* View count */}
                      {views !== null && (
                        <span style={{ fontSize: "9px", color: "rgba(180,140,80,0.3)", letterSpacing: "0.12em", textTransform: "uppercase" }}>
                          {views} {views === 1 ? "view" : "views"}
                        </span>
                      )}
                      
                      {/* Phase 9 Anonymous Forking */}
                      <button 
                        onClick={forkPlaylist}
                        disabled={forking}
                        style={{ 
                          display: "flex", alignItems: "center", gap: "6px", padding: "7px 14px", 
                          background: forkSuccess ? "rgba(52, 211, 153, 0.12)" : "rgba(180,140,80,0.1)", 
                          border: `1px solid ${forkSuccess ? "rgba(52, 211, 153, 0.4)" : "rgba(180,140,80,0.3)"}`, 
                          borderRadius: "7px", 
                          color: forkSuccess ? "#34d399" : "#e8d5a3", 
                          fontSize: "10px", fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em", textTransform: "uppercase", 
                          cursor: forking ? "wait" : "pointer", transition: "all 0.2s" 
                        }}
                      >
                        <IconDisc />
                        {forking ? "Forking..." : forkSuccess ? "Saved!" : "Fork to Library"}
                      </button>

                      {/* Native share / copy link */}
                      <button onClick={shareLink} style={{ display: "flex", alignItems: "center", gap: "6px", padding: "7px 14px", background: copied ? "rgba(52,211,153,0.12)" : "rgba(120,80,20,0.15)", border: `1px solid ${copied ? "rgba(52,211,153,0.4)" : "rgba(160,110,30,0.35)"}`, borderRadius: "7px", color: copied ? "#34d399" : "rgba(180,140,80,0.7)", fontSize: "10px", fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em", textTransform: "uppercase", cursor: "pointer", transition: "all 0.2s" }}>
                        <IconShare /> {copied ? "Copied!" : "Share"}
                      </button>
                      <a href={`https://open.spotify.com/search/${encodeURIComponent(playlist.tracks?.[0] ? `${playlist.tracks[0].title} ${playlist.tracks[0].artist}` : playlist.name)}`}
                        target="_blank" rel="noopener noreferrer"
                        style={{ display: "flex", alignItems: "center", gap: "6px", padding: "7px 14px", background: "rgba(29,185,84,0.12)", border: "1px solid rgba(29,185,84,0.35)", borderRadius: "7px", color: "#1db954", fontSize: "10px", fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em", textTransform: "uppercase", textDecoration: "none" }}>
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
                        Spotify
                      </a>
                    </div>
                  </div>
                </div>
              </div>

              {/* Track list */}
              <div className="fade-in-2" style={{ background: "linear-gradient(160deg, rgba(44,30,12,0.92), rgba(24,15,5,0.96))", border: "1px solid rgba(160,110,30,0.35)", borderRadius: "16px", padding: "20px", marginBottom: "20px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                  <IconDisc />
                  <span style={{ fontSize: "10px", letterSpacing: "0.25em", textTransform: "uppercase", color: "rgba(180,140,80,0.45)" }}>Tracks</span>
                  <div style={{ flex: 1, height: "1px", background: `linear-gradient(90deg, ${activeColor}44, transparent)` }} />
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {playlist.tracks.map((track, i) => {
                    const isPlaying = playingUrl === track.preview_url;
                    return (
                      <div key={i} className="track-row" style={{ display: "flex", alignItems: "center", gap: "14px", padding: "12px 14px", background: isPlaying ? `${activeColor}0d` : "rgba(8,5,2,0.5)", border: `1px solid ${isPlaying ? activeColor + "44" : "rgba(120,80,20,0.2)"}`, borderRadius: "10px" }}>
                        <div style={{ width: "20px", textAlign: "center", fontSize: "10px", color: "rgba(180,140,80,0.3)", flexShrink: 0 }}>{i + 1}</div>
                        {track.cover_art
                          ? <img src={track.cover_art} alt="" style={{ width: 40, height: 40, borderRadius: 6, objectFit: "cover", flexShrink: 0, boxShadow: "0 2px 8px rgba(0,0,0,0.5)" }} />
                          : <div style={{ width: 40, height: 40, borderRadius: 6, background: "rgba(120,80,20,0.2)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><IconDisc /></div>
                        }
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: "14px", fontWeight: 700, fontFamily: "'Playfair Display', serif", color: "#fde68a", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{track.title}</div>
                          <div style={{ fontSize: "11px", color: "rgba(180,140,80,0.6)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{track.artist}</div>
                        </div>
                        <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "3px" }}>
                            <button onClick={() => togglePlay(track.preview_url)} disabled={!track.preview_url} style={{ display: "flex", alignItems: "center", gap: "5px", padding: "7px 12px", background: isPlaying ? `${activeColor}22` : "rgba(120,80,20,0.15)", border: `1px solid ${isPlaying ? activeColor : "rgba(120,80,20,0.4)"}`, borderRadius: "7px", color: isPlaying ? activeColor : "rgba(180,140,80,0.7)", fontSize: "10px", fontFamily: "'DM Mono', monospace", letterSpacing: "0.05em", textTransform: "uppercase", cursor: track.preview_url ? "pointer" : "default", opacity: track.preview_url ? 1 : 0.35, transition: "all 0.15s" }}>
                              {isPlaying ? <IconPause /> : <IconPlay />}
                            </button>
                            {track.preview_url
                              ? <span style={{ fontSize: "8px", color: "rgba(180,140,80,0.3)", letterSpacing: "0.06em" }}>30s</span>
                              : <span style={{ fontSize: "8px", color: "rgba(180,140,80,0.2)", letterSpacing: "0.06em" }}>n/a</span>
                            }
                          </div>
                          <a href={track.spotify_uri} style={{ display: "flex", alignItems: "center", padding: "7px 12px", background: "rgba(29,185,84,0.12)", border: "1px solid rgba(29,185,84,0.35)", borderRadius: "7px", color: "#1db954", fontSize: "10px", fontFamily: "'DM Mono', monospace", letterSpacing: "0.05em", textTransform: "uppercase", textDecoration: "none" }}>
                            Spotify
                          </a>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Preview notice */}
              <div className="fade-in-3" style={{ background: "rgba(120,80,20,0.08)", border: "1px solid rgba(120,80,20,0.2)", borderRadius: "10px", padding: "12px 16px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "16px" }}>🎧</span>
                <div>
                  <div style={{ fontSize: "11px", color: "rgba(180,140,80,0.7)", fontFamily: "'DM Mono', monospace", letterSpacing: "0.06em" }}>
                    Previews are 30 seconds — connect Spotify to hear the full tracks
                  </div>
                </div>
              </div>

              {/* CTA */}
              <div className="fade-in-3" style={{ background: "linear-gradient(160deg, rgba(44,30,12,0.95), rgba(20,12,4,0.98))", border: `1px solid ${activeColor}22`, borderRadius: "16px", padding: "28px 24px", textAlign: "center", marginBottom: "8px" }}>
                <div style={{ fontFamily: "'Playfair Display', serif", fontSize: "20px", fontWeight: 900, color: "#fde68a", marginBottom: "8px", lineHeight: 1.2 }}>
                  Spotify knows what you like.<br />
                  <span style={{ color: activeColor }}>VibeFinder knows how you feel.</span>
                </div>
                <div style={{ fontSize: "11px", color: "rgba(180,140,80,0.45)", letterSpacing: "0.08em", marginBottom: "20px", lineHeight: 1.6 }}>
                  Describe any feeling, mood, or moment — get a playlist that actually fits.
                </div>
                <a href="/" style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "13px 32px", background: "linear-gradient(135deg, #92400e, #d97706)", border: "1px solid rgba(251,191,36,0.3)", borderRadius: "10px", color: "#fef3c7", fontSize: "12px", fontFamily: "'DM Mono', monospace", letterSpacing: "0.15em", textTransform: "uppercase", textDecoration: "none", boxShadow: "0 4px 20px rgba(180,100,10,0.35)" }}>
                  <IconWave /> Find Your Vibe
                </a>
                <div style={{ fontSize: "9px", color: "rgba(180,140,80,0.25)", marginTop: "14px", letterSpacing: "0.1em", textTransform: "uppercase" }}>
                  Free · No account needed to start
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
