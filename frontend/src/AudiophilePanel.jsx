/**
 * AudiophilePanel.jsx
 * ───────────────────
 * VibeFinderAI — Audiophile info panel
 *
 * Three tabs:
 *  ① VIBE — Last.fm tag info, top tracks & artists for current vibe
 *  ② ARTIST — bio + similar artists when an artist was detected
 *  ③ FACTS — rotating music trivia & "did you know" tips
 *
 * PROPS
 * ─────
 *  onClose        – dismiss panel
 *  result         – current vibe result (dominant_vibe, detected_artist, tracks, keywords)
 *  activeColor    – theme accent
 *  buildApiUrl    – URL builder fn (for Last.fm proxy)
 *  token          – VibeFinder JWT (optional, for authenticated endpoints)
 */

import { useState, useEffect, useRef } from "react";

const LASTFM_API = "https://ws.audioscrobbler.com/2.0/";

/* ── Static music trivia ─────────────────────────────────────── */
const MUSIC_FACTS = [
  { fact: "The human ear can distinguish over 400,000 different sounds.", tag: "physiology" },
  { fact: "Vinyl records outsold CDs for the first time since 1987 in 2020.", tag: "industry" },
  { fact: "A song is defined as 'viral' on Spotify when it crosses 1M streams in 24 hours.", tag: "streaming" },
  { fact: "The most covered song in history is 'Yesterday' by The Beatles — over 2,200 recorded versions.", tag: "records" },
  { fact: "Brian Eno coined the term 'ambient music' in 1978 after mishearing a record playing too quietly in a hospital.", tag: "genre origins" },
  { fact: "Cymatics is the study of visible sound patterns — sand on a vibrating plate forms geometric shapes at specific frequencies.", tag: "physics" },
  { fact: "The 'loudness war' peaked around 2008 when albums were mastered so hot that dynamic range fell below 6dB on average.", tag: "mastering" },
  { fact: "Robert Johnson's entire recorded output is 29 songs. His influence on rock is immeasurable.", tag: "blues" },
  { fact: "The sitar has between 18–21 strings. Only 6–7 are played; the rest vibrate sympathetically.", tag: "instruments" },
  { fact: "Music in a minor key consistently triggers feelings of sadness or tension across cultures — even in listeners with no Western music exposure.", tag: "psychology" },
  { fact: "A typical pop song uses only 3–4 chords. Most classical compositions use dozens.", tag: "theory" },
  { fact: "Bhangra originated as harvest celebration music in the Punjab region — the dhol drum's rhythm mirrors the physical motion of harvesting wheat.", tag: "desi music" },
  { fact: "Lo-fi hip-hop's characteristic crackle and warmth comes from sampling vinyl records — deliberately including the imperfections.", tag: "production" },
  { fact: "The raga system in Indian classical music has specific ragas prescribed for specific times of day and seasons.", tag: "indian classical" },
  { fact: "Spotify's 'Discover Weekly' algorithm uses collaborative filtering — your listening habits are compared against 400M+ user patterns.", tag: "algorithms" },
  { fact: "808 in music refers to the Roland TR-808 drum machine (1980) — its bass kick is still the backbone of hip-hop and trap.", tag: "gear" },
  { fact: "The word 'album' comes from the Latin for 'white tablet' — the blank white pages record companies used to package multiple 78rpm singles.", tag: "history" },
  { fact: "Carnatic music uses 72 parent scales (melakarta ragas) — Western music uses only 2 (major and minor).", tag: "indian classical" },
  { fact: "Songs with tempos between 120–140 BPM trigger the strongest urge to move — matching average running cadence.", tag: "psychology" },
  { fact: "The Loudest band ever recorded is Manowar at 139 dB — louder than a jet engine at takeoff.", tag: "records" },
];

const FEATURE_TIPS = [
  { tip: "Use the NICHENESS knob at 80+ to discover tracks with under 10,000 Last.fm listeners.", icon: "🔍" },
  { tip: "Type a scene description instead of a mood — 'monsoon evening, chai, old radio' beats just 'chill'.", icon: "✍️" },
  { tip: "Pro Mode > Similar to Artist seeds the pool from ListenBrainz's social graph — different from just mentioning an artist.", icon: "🎛️" },
  { tip: "The Secondary Vibe flip is most useful when confidence is below 60%. The AI detected two moods — try the other one.", icon: "🔄" },
  { tip: "Language routing is semantic, not just a filter. 'Dard' in Hindi will route differently than 'pain' in English.", icon: "🌐" },
  { tip: "Connect YouTube to unlock full-length playback for every track in your results — no account required.", icon: "▶️" },
  { tip: "Save a playlist and share the link — recipients can preview every track without an account.", icon: "💾" },
  { tip: "Genre tags on your results are clickable — tap one to hard-filter the whole pool to that genre.", icon: "🏷️" },
  { tip: "Connect Last.fm to scrobble and love tracks. Your listening history builds up automatically.", icon: "♥" },
  { tip: "Use 'Force Artist Bypass' in Pro Mode to pull only from that artist's discography regardless of your vibe.", icon: "🔒" },
];

/* ── Last.fm proxy fetcher ───────────────────────────────────── */
async function lastfmFetch(buildApiUrl, method, params) {
  try {
    const qs = Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
    // Use backend proxy to keep API key server-side
    const res = await fetch(buildApiUrl(`/api/lastfm/proxy?method=${method}&${qs}`));
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

/* ═══════════════════════════════════════════════════════════════
   MAIN COMPONENT
═══════════════════════════════════════════════════════════════ */
export default function AudiophilePanel({ onClose, result, activeColor = "#d97706", buildApiUrl, token }) {
  const [tab,         setTab]         = useState("vibe");
  const [vibeInfo,    setVibeInfo]    = useState(null);
  const [topTracks,   setTopTracks]   = useState([]);
  const [topArtists,  setTopArtists]  = useState([]);
  const [artistInfo,  setArtistInfo]  = useState(null);
  const [similarArtists, setSimilarArtists] = useState([]);
  const [loading,     setLoading]     = useState(false);
  const [factIdx,     setFactIdx]     = useState(() => Math.floor(Math.random() * MUSIC_FACTS.length));
  const [tipIdx,      setTipIdx]      = useState(() => Math.floor(Math.random() * FEATURE_TIPS.length));
  const factTimer = useRef(null);

  const vibe         = result?.dominant_vibe || "chill";
  const detectedArtist = result?.detected_artist;
  const topGenreTag  = result?.keywords?.[0] || vibe;
  const mono         = "'DM Mono', monospace";
  const serif        = "'Playfair Display', serif";
  const amber        = "#d97706";

  // Rotate facts every 8s
  useEffect(() => {
    factTimer.current = setInterval(() => {
      setFactIdx(i => (i + 1) % MUSIC_FACTS.length);
    }, 8000);
    return () => clearInterval(factTimer.current);
  }, []);

  // Fetch vibe tab data
  useEffect(() => {
    if (tab !== "vibe" || !buildApiUrl) return;
    setLoading(true);
    Promise.all([
      lastfmFetch(buildApiUrl, "tag.getinfo",       { tag: vibe }),
      lastfmFetch(buildApiUrl, "tag.gettoptracks",  { tag: vibe, limit: 6 }),
      lastfmFetch(buildApiUrl, "tag.gettopartists", { tag: vibe, limit: 5 }),
    ]).then(([info, tracks, artists]) => {
      setVibeInfo(info?.tag || null);
      setTopTracks(tracks?.tracks?.track || []);
      setTopArtists(artists?.topartists?.artist || []);
    }).finally(() => setLoading(false));
  }, [tab, vibe, buildApiUrl]);

  // Fetch artist tab data
  useEffect(() => {
    if (tab !== "artist" || !detectedArtist || !buildApiUrl) return;
    setLoading(true);
    Promise.all([
      lastfmFetch(buildApiUrl, "artist.getinfo",    { artist: detectedArtist, autocorrect: 1 }),
      lastfmFetch(buildApiUrl, "artist.getsimilar", { artist: detectedArtist, limit: 5, autocorrect: 1 }),
    ]).then(([info, similar]) => {
      setArtistInfo(info?.artist || null);
      setSimilarArtists(similar?.similarartists?.artist || []);
    }).finally(() => setLoading(false));
  }, [tab, detectedArtist, buildApiUrl]);

  const tabs = [
    { id: "vibe",   label: `// ${vibe.toUpperCase()}` },
    { id: "artist", label: "// ARTIST", disabled: !detectedArtist },
    { id: "facts",  label: "// FACTS" },
  ];

  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 300, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          position: "absolute", top: 0, right: 0, bottom: 0,
          width: "min(420px, 100vw)",
          background: "linear-gradient(180deg, #120900 0%, #0a0500 100%)",
          borderLeft: "1px solid rgba(155,105,28,0.3)",
          display: "flex", flexDirection: "column",
          boxShadow: "-8px 0 40px rgba(0,0,0,0.6)",
          overflowY: "hidden",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 20px 14px", borderBottom: "1px solid rgba(155,105,28,0.2)", flexShrink: 0 }}>
          <div>
            <div style={{ fontFamily: mono, fontSize: 13, fontWeight: 600, color: "#ead9a8", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              🎧 Audiophile
            </div>
            <div style={{ fontFamily: mono, fontSize: 9, color: "rgba(180,140,80,0.4)", letterSpacing: "0.12em", textTransform: "uppercase", marginTop: 2 }}>
              vibe intel · music facts · tips
            </div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "rgba(180,140,80,0.4)", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: 4 }}>✕</button>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", padding: "0 20px", borderBottom: "1px solid rgba(155,105,28,0.15)", flexShrink: 0 }}>
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => !t.disabled && setTab(t.id)}
              disabled={t.disabled}
              style={{
                padding: "10px 14px 9px", border: "none", background: "none", cursor: t.disabled ? "not-allowed" : "pointer",
                fontFamily: mono, fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase",
                color: t.disabled ? "rgba(120,80,20,0.25)" : tab === t.id ? amber : "rgba(180,140,80,0.4)",
                borderBottom: `2px solid ${tab === t.id ? amber : "transparent"}`,
                transition: "color 0.2s, border-color 0.2s",
              }}
            >{t.label}</button>
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "18px 20px", scrollbarWidth: "thin", scrollbarColor: `${activeColor}22 transparent` }}>

          {/* ── VIBE TAB ── */}
          {tab === "vibe" && (
            <div>
              {loading ? (
                <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(180,140,80,0.3)", padding: "20px 0" }}>Loading vibe data…</div>
              ) : (
                <>
                  {/* Tag description */}
                  {vibeInfo?.wiki?.summary && (
                    <div style={{ marginBottom: 20 }}>
                      <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 8 }}>About "{vibe}"</div>
                      <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(190,155,90,0.6)", lineHeight: 1.75 }}>
                        {vibeInfo.wiki.summary.replace(/<[^>]+>/g, "").split(". ").slice(0, 3).join(". ").trim()}.
                      </div>
                    </div>
                  )}

                  {/* Top tracks */}
                  {topTracks.length > 0 && (
                    <div style={{ marginBottom: 20 }}>
                      <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 10 }}>Top tracks tagged "{vibe}"</div>
                      {topTracks.map((t, i) => (
                        <a
                          key={i}
                          href={t.url}
                          target="_blank" rel="noopener noreferrer"
                          style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 8, marginBottom: 4, background: "rgba(20,12,4,0.6)", border: "1px solid rgba(120,80,20,0.15)", textDecoration: "none", transition: "border-color 0.2s" }}
                          onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(217,119,6,0.3)"}
                          onMouseLeave={e => e.currentTarget.style.borderColor = "rgba(120,80,20,0.15)"}
                        >
                          <span style={{ fontFamily: mono, fontSize: 9, color: "rgba(180,140,80,0.25)", width: 16, textAlign: "right", flexShrink: 0 }}>{i + 1}</span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontFamily: serif, fontSize: 12, color: "#fde68a", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.name}</div>
                            <div style={{ fontFamily: mono, fontSize: 10, color: "rgba(180,140,80,0.45)" }}>{t.artist?.name}</div>
                          </div>
                          <span style={{ fontSize: 10, color: "rgba(180,140,80,0.2)" }}>↗</span>
                        </a>
                      ))}
                    </div>
                  )}

                  {/* Top artists */}
                  {topArtists.length > 0 && (
                    <div>
                      <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 10 }}>Top artists</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
                        {topArtists.map((a, i) => (
                          <a
                            key={i}
                            href={a.url}
                            target="_blank" rel="noopener noreferrer"
                            style={{ padding: "4px 10px", borderRadius: 20, background: "rgba(20,12,4,0.7)", border: "1px solid rgba(155,105,28,0.25)", fontFamily: mono, fontSize: 10, color: "rgba(210,165,60,0.75)", textDecoration: "none", letterSpacing: "0.06em", transition: "border-color 0.2s" }}
                            onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(217,119,6,0.4)"}
                            onMouseLeave={e => e.currentTarget.style.borderColor = "rgba(155,105,28,0.25)"}
                          >{a.name}</a>
                        ))}
                      </div>
                    </div>
                  )}

                  {!vibeInfo && topTracks.length === 0 && (
                    <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(180,140,80,0.3)", padding: "20px 0" }}>
                      No Last.fm data for "{vibe}" yet. Try searching a more common vibe tag.
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── ARTIST TAB ── */}
          {tab === "artist" && (
            <div>
              {!detectedArtist ? (
                <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(180,140,80,0.3)", padding: "20px 0" }}>
                  No artist detected in your last search. Mention an artist in your vibe description to unlock this tab.
                </div>
              ) : loading ? (
                <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(180,140,80,0.3)", padding: "20px 0" }}>Loading artist info…</div>
              ) : (
                <>
                  <div style={{ fontFamily: serif, fontSize: 18, color: "#fde68a", marginBottom: 4 }}>{detectedArtist}</div>

                  {artistInfo?.stats && (
                    <div style={{ display: "flex", gap: 16, marginBottom: 14 }}>
                      <div>
                        <div style={{ fontFamily: mono, fontSize: 9, color: "rgba(180,140,80,0.35)", letterSpacing: "0.12em", textTransform: "uppercase" }}>Listeners</div>
                        <div style={{ fontFamily: mono, fontSize: 13, color: amber, fontWeight: 600 }}>{parseInt(artistInfo.stats.listeners || 0).toLocaleString()}</div>
                      </div>
                      <div>
                        <div style={{ fontFamily: mono, fontSize: 9, color: "rgba(180,140,80,0.35)", letterSpacing: "0.12em", textTransform: "uppercase" }}>Scrobbles</div>
                        <div style={{ fontFamily: mono, fontSize: 13, color: "rgba(180,140,80,0.7)", fontWeight: 600 }}>{parseInt(artistInfo.stats.playcount || 0).toLocaleString()}</div>
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {artistInfo?.tags?.tag?.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
                      {artistInfo.tags.tag.slice(0, 6).map((t, i) => (
                        <span key={i} style={{ padding: "3px 9px", borderRadius: 20, background: "rgba(20,12,4,0.7)", border: "1px solid rgba(155,105,28,0.28)", fontFamily: mono, fontSize: 9, color: "rgba(210,165,60,0.7)", letterSpacing: "0.08em" }}>
                          {t.name}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Bio */}
                  {artistInfo?.bio?.summary && (
                    <div style={{ marginBottom: 18 }}>
                      <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 8 }}>Bio</div>
                      <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(190,155,90,0.6)", lineHeight: 1.75 }}>
                        {artistInfo.bio.summary.replace(/<[^>]+>/g, "").split(". ").slice(0, 4).join(". ").trim()}.
                      </div>
                    </div>
                  )}

                  {/* Similar artists */}
                  {similarArtists.length > 0 && (
                    <div>
                      <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 10 }}>Similar artists</div>
                      {similarArtists.map((a, i) => (
                        <a
                          key={i} href={a.url} target="_blank" rel="noopener noreferrer"
                          style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 10px", borderRadius: 8, marginBottom: 4, background: "rgba(20,12,4,0.6)", border: "1px solid rgba(120,80,20,0.15)", textDecoration: "none", transition: "border-color 0.2s" }}
                          onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(217,119,6,0.3)"}
                          onMouseLeave={e => e.currentTarget.style.borderColor = "rgba(120,80,20,0.15)"}
                        >
                          <span style={{ fontFamily: mono, fontSize: 11, color: "#ead9a8" }}>{a.name}</span>
                          <span style={{ fontFamily: mono, fontSize: 9, color: "rgba(180,140,80,0.3)" }}>
                            {Math.round((parseFloat(a.match || 0)) * 100)}% match ↗
                          </span>
                        </a>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── FACTS TAB ── */}
          {tab === "facts" && (
            <div>
              {/* Current rotating fact */}
              <div style={{ marginBottom: 22, padding: "18px 16px", background: "rgba(20,12,4,0.8)", border: `1px solid ${activeColor}33`, borderLeft: `3px solid ${activeColor}`, borderRadius: 8 }}>
                <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 8 }}>
                  Did you know · {MUSIC_FACTS[factIdx].tag}
                </div>
                <div style={{ fontFamily: mono, fontSize: 12, color: "#ead9a8", lineHeight: 1.8 }}>
                  {MUSIC_FACTS[factIdx].fact}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  <button onClick={() => setFactIdx(i => (i - 1 + MUSIC_FACTS.length) % MUSIC_FACTS.length)}
                    style={{ background: "none", border: "1px solid rgba(155,105,28,0.25)", borderRadius: 6, padding: "4px 10px", fontFamily: mono, fontSize: 10, color: "rgba(180,140,80,0.4)", cursor: "pointer" }}>← prev</button>
                  <button onClick={() => setFactIdx(i => (i + 1) % MUSIC_FACTS.length)}
                    style={{ background: "none", border: "1px solid rgba(155,105,28,0.25)", borderRadius: 6, padding: "4px 10px", fontFamily: mono, fontSize: 10, color: "rgba(180,140,80,0.4)", cursor: "pointer" }}>next →</button>
                  <span style={{ fontFamily: mono, fontSize: 9, color: "rgba(120,80,20,0.4)", marginLeft: "auto", alignSelf: "center" }}>{factIdx + 1} / {MUSIC_FACTS.length}</span>
                </div>
              </div>

              {/* Feature tips */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 12 }}>Pro tips</div>
                {FEATURE_TIPS.map((t, i) => (
                  <div
                    key={i}
                    style={{ display: "flex", gap: 10, padding: "10px 12px", borderRadius: 8, marginBottom: 6, background: "rgba(20,12,4,0.5)", border: "1px solid rgba(120,80,20,0.12)", transition: "border-color 0.2s", cursor: "default" }}
                    onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(155,105,28,0.3)"}
                    onMouseLeave={e => e.currentTarget.style.borderColor = "rgba(120,80,20,0.12)"}
                  >
                    <span style={{ fontSize: 14, flexShrink: 0, lineHeight: 1.5 }}>{t.icon}</span>
                    <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(190,155,90,0.6)", lineHeight: 1.7 }}>{t.tip}</div>
                  </div>
                ))}
              </div>

              {/* All facts list */}
              <div>
                <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 12 }}>Music trivia</div>
                {MUSIC_FACTS.map((f, i) => (
                  <div
                    key={i}
                    onClick={() => setFactIdx(i)}
                    style={{ padding: "9px 12px", borderRadius: 8, marginBottom: 5, background: i === factIdx ? `${activeColor}12` : "rgba(14,9,3,0.5)", border: `1px solid ${i === factIdx ? activeColor + "33" : "rgba(120,80,20,0.1)"}`, cursor: "pointer", transition: "all 0.15s" }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontFamily: mono, fontSize: 8, letterSpacing: "0.12em", textTransform: "uppercase", color: i === factIdx ? activeColor : "rgba(155,105,28,0.4)" }}>{f.tag}</span>
                    </div>
                    <div style={{ fontFamily: mono, fontSize: 10, color: i === factIdx ? "#ead9a8" : "rgba(190,155,90,0.5)", lineHeight: 1.65 }}>{f.fact}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
