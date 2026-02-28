import { useState, useEffect, useRef } from "react";

/* ─── WAVEFORM BARS (same as App.jsx) ─────────────────────── */
function WaveformBars({ active = true, count = 22 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "3px", height: "32px" }}>
      {Array.from({ length: count }).map((_, i) => {
        const delay = (i * 40) % 700;
        return (
          <div key={i} style={{
            width: "3px", minHeight: "4px", maxHeight: "32px", borderRadius: "2px",
            background: active
              ? `hsl(${38 + i * 1.2}, 80%, ${48 + (i % 4) * 5}%)`
              : "rgba(180,140,80,0.15)",
            animationName: active ? "barDance" : "none",
            animationDuration: `${350 + (i % 7) * 80}ms`,
            animationDelay: `${delay}ms`,
            animationTimingFunction: "ease-in-out",
            animationIterationCount: "infinite",
            animationDirection: "alternate",
            height: active ? undefined : "6px",
          }} />
        );
      })}
    </div>
  );
}

/* ─── OSCILLOSCOPE (same as App.jsx) ──────────────────────── */
function Oscilloscope({ active }) {
  const canvasRef = useRef(null);
  const frameRef  = useRef(null);
  const tRef      = useRef(0);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      ctx.strokeStyle = active ? "rgba(217,119,6,0.85)" : "rgba(120,80,20,0.25)";
      ctx.lineWidth = active ? 1.5 : 1;
      ctx.shadowBlur = active ? 8 : 0;
      ctx.shadowColor = "rgba(217,119,6,0.6)";
      ctx.beginPath();
      for (let x = 0; x < W; x++) {
        const t = tRef.current;
        const y = active
          ? H/2 + Math.sin((x/W)*Math.PI*4 + t*0.05)*14
              + Math.sin((x/W)*Math.PI*9 + t*0.08)*6
              + Math.sin((x/W)*Math.PI*17 + t*0.03)*3
          : H/2 + Math.sin((x/W)*Math.PI*2)*3;
        x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.stroke();
      if (active) tRef.current++;
      frameRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(frameRef.current);
  }, [active]);
  return (
    <div style={{
      background: "rgba(8,5,2,0.8)", border: "1px solid rgba(120,80,20,0.4)",
      borderRadius: 8, padding: "6px 10px",
      display: "flex", alignItems: "center", gap: 8,
    }}>
      <span style={{ fontSize: 9, fontFamily: "monospace", color: "rgba(180,140,80,0.5)", letterSpacing: "0.1em", textTransform: "uppercase" }}>OSC</span>
      <canvas ref={canvasRef} width={160} height={34} style={{ display: "block" }} />
    </div>
  );
}

/* ─── STEP ────────────────────────────────────────────────── */
function Step({ num, title, desc, tip, tag }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "56px 1fr", gap: "1.4rem",
      padding: "1.8rem 0", borderBottom: "1px solid rgba(120,80,20,0.2)",
    }}>
      <div style={{
        width: 44, height: 44, flexShrink: 0,
        background: "rgba(28,18,6,0.8)", border: "1px solid rgba(120,80,20,0.35)",
        borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "'DM Mono', monospace", fontSize: 11, color: "rgba(180,140,80,0.6)",
        letterSpacing: "0.1em",
      }}>{num}</div>
      <div>
        <div style={{
          fontFamily: "'Cormorant Garamond', serif", fontWeight: 600,
          fontSize: 16, color: "#e8d5a3", marginBottom: 6, letterSpacing: "0.03em",
        }}>{title}</div>
        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "rgba(180,140,80,0.65)", lineHeight: 1.75 }}>{desc}</div>
        {tip && (
          <div style={{
            marginTop: 10, padding: "10px 14px",
            background: "rgba(8,5,2,0.6)", borderLeft: "2px solid rgba(217,119,6,0.6)",
            borderRadius: "0 6px 6px 0",
            fontFamily: "'DM Mono', monospace", fontStyle: "italic",
            fontSize: 11, color: "rgba(180,140,80,0.55)", lineHeight: 1.7,
          }}>{tip}</div>
        )}
        {tag && (
          <span className="freq-tag" style={{ display: "inline-block", marginTop: 10 }}>{tag}</span>
        )}
      </div>
    </div>
  );
}

/* ─── FEATURE CARD ────────────────────────────────────────── */
function FeatureCard({ icon, title, desc, badge }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      className="panel-card"
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "1.8rem 1.6rem",
        background: hov
          ? "linear-gradient(160deg, rgba(36,22,7,0.95), rgba(18,11,3,0.98))"
          : "linear-gradient(160deg, rgba(28,18,6,0.9), rgba(14,9,3,0.95))",
        transition: "background .2s",
      }}
    >
      <div style={{ fontSize: 22, marginBottom: 10 }}>{icon}</div>
      <div style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 600, fontSize: 15, color: "#e8d5a3", marginBottom: 8 }}>{title}</div>
      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "rgba(180,140,80,0.6)", lineHeight: 1.75, marginBottom: 14 }}>{desc}</div>
      <span className="freq-tag" style={{ color: "rgba(217,160,60,0.9)", borderColor: "rgba(180,120,40,0.4)" }}>{badge}</span>
    </div>
  );
}

/* ─── KNOB DISPLAY (visual only) ─────────────────────────── */
function KnobDisplay({ emoji, name, desc }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        flex: 1, minWidth: 180,
        background: "linear-gradient(160deg, rgba(28,18,6,0.9), rgba(14,9,3,0.95))",
        border: `1px solid ${hov ? "rgba(217,119,6,0.5)" : "rgba(120,80,20,0.35)"}`,
        borderRadius: 14, padding: "1.6rem 1.4rem", textAlign: "center",
        transition: "border-color .2s",
      }}
    >
      <div style={{
        width: 52, height: 52, borderRadius: "50%", margin: "0 auto 14px",
        background: "radial-gradient(circle at 35% 35%, #5a3a18, #1a0e04)",
        border: "2px solid rgba(120,80,20,0.5)",
        boxShadow: hov ? "0 0 18px rgba(217,119,6,0.4), 0 3px 8px rgba(0,0,0,0.6)" : "0 3px 8px rgba(0,0,0,0.6)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 20, position: "relative", transition: "box-shadow .2s",
      }}>
        <div style={{
          position: "absolute", top: 5, left: "50%", transform: "translateX(-50%)",
          width: 2, height: 12, background: "rgba(217,119,6,0.9)",
          borderRadius: 1, boxShadow: "0 0 4px rgba(217,119,6,0.6)",
        }} />
        {emoji}
      </div>
      <div style={{
        fontFamily: "'DM Mono', monospace", fontSize: 11,
        letterSpacing: "0.18em", textTransform: "uppercase",
        color: "rgba(217,160,60,0.8)", marginBottom: 8, fontWeight: 600,
      }}>{name}</div>
      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "rgba(180,140,80,0.55)", lineHeight: 1.7 }}>{desc}</div>
    </div>
  );
}

/* ─── USE CASE CARD ───────────────────────────────────────── */
function UseCaseCard({ emoji, title, desc, example }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      className="panel-card"
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "1.6rem",
        border: `1px solid ${hov ? "rgba(217,119,6,0.4)" : "rgba(120,80,20,0.3)"}`,
        transform: hov ? "translateY(-2px)" : "none",
        transition: "border-color .2s, transform .15s",
      }}
    >
      <div style={{ fontSize: 22, marginBottom: 10 }}>{emoji}</div>
      <div style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 600, fontSize: 15, color: "#e8d5a3", marginBottom: 8 }}>{title}</div>
      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "rgba(180,140,80,0.6)", lineHeight: 1.65 }}>{desc}</div>
      <div style={{
        marginTop: 12, padding: "9px 12px",
        background: "rgba(8,5,2,0.7)", borderLeft: "2px solid rgba(217,119,6,0.5)",
        borderRadius: "0 6px 6px 0",
        fontFamily: "'DM Mono', monospace", fontStyle: "italic",
        fontSize: 11, color: "rgba(180,140,80,0.5)", lineHeight: 1.6,
      }}>"{example}"</div>
    </div>
  );
}

/* ─── RESULT PREVIEW PANEL ────────────────────────────────── */
function ResultPreview() {
  return (
    <div className="panel-card screws" style={{ overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 7px, rgba(120,80,20,0.03) 7px, rgba(120,80,20,0.03) 8px)", pointerEvents: "none", borderRadius: 16 }} />
      <div style={{ position: "relative" }}>
        <div style={{ borderBottom: "1px solid rgba(120,80,20,0.3)", padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(5,3,1,0.5)" }}>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.5)" }}>// ANALYSIS COMPLETE</span>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#34d399", boxShadow: "0 0 6px #34d399", animation: "pulse-glow 1.8s infinite" }} />
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#34d399", letterSpacing: "0.1em" }}>LIVE</span>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "rgba(120,80,20,0.15)", margin: "0 0 1px" }}>
          {[
            { label: "Dominant Vibe", value: "CHILL",  sub: "Secondary → Heartbreak", conf: 0.53, color: "#60a5fa" },
            { label: "Target Tempo",  value: "70–100", sub: "Rhythmic Pulse",          bpm: true,  color: "#d97706" },
          ].map((cell, i) => (
            <div key={i} style={{ background: "linear-gradient(160deg, rgba(28,18,6,0.9), rgba(14,9,3,0.95))", padding: "20px 22px" }}>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, letterSpacing: "0.25em", textTransform: "uppercase", color: "rgba(180,140,80,0.45)", marginBottom: 6 }}>{cell.label}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                <span style={{ fontFamily: "'Playfair Display', serif", fontSize: 28, fontWeight: 700, color: "#fde68a", textShadow: `0 0 20px ${cell.color}44` }}>{cell.value}</span>
                {cell.bpm && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: "rgba(180,140,80,0.5)" }}>BPM</span>}
              </div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "rgba(180,140,80,0.45)", letterSpacing: "0.08em", marginTop: 3 }}>{cell.sub}</div>
              {cell.conf && (
                <div style={{ height: 5, borderRadius: 3, background: "rgba(80,50,10,0.4)", overflow: "hidden", marginTop: 10, boxShadow: "inset 0 1px 3px rgba(0,0,0,0.5)" }}>
                  <div style={{ height: "100%", width: `${cell.conf * 100}%`, background: "linear-gradient(90deg, #92400e, #d97706, #fbbf24)", borderRadius: 3, boxShadow: "0 0 10px rgba(217,119,6,0.5)" }} />
                </div>
              )}
            </div>
          ))}
        </div>
        <div style={{ padding: "14px 20px", borderBottom: "1px solid rgba(120,80,20,0.25)", display: "flex", flexWrap: "wrap", gap: 6 }}>
          <span className="freq-tag" style={{ color: "#d97706", borderColor: "rgba(217,119,6,0.45)" }}>⚡ LOCKED: TRAVIS SCOTT</span>
          {["NEO-SOUL", "INDIE R&B", "CHILLWAVE", "LO-FI HIP HOP", "TRIP HOP", "VAPORWAVE"].map(t => (
            <span key={t} className="freq-tag">{t}</span>
          ))}
        </div>
        {[
          { color: "#c8922a", title: "Neon Glow",      artist: "Artist Name · Album Title" },
          { color: "#9333ea", title: "Midnight Signal", artist: "Another Artist · EP Title" },
        ].map((track, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 20px", borderBottom: "1px solid rgba(120,80,20,0.15)", background: i === 0 ? "rgba(217,119,6,0.04)" : "transparent" }}>
            <div style={{ width: 42, height: 42, borderRadius: 6, flexShrink: 0, background: `conic-gradient(from 0deg, #1a1008, ${track.color}44, #1a1008, #2e1f0d)`, border: "1px solid rgba(180,140,80,0.25)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 2px 8px rgba(0,0,0,0.5)" }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: `radial-gradient(circle, ${track.color}, #7a4f12)` }} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 15, fontWeight: 700, color: "#fde68a" }}>{track.title}</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "rgba(180,140,80,0.6)", marginTop: 3 }}>{track.artist}</div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              {["👍", "👎", "▶ Preview"].map(act => (
                <button key={act} style={{ background: "rgba(8,5,2,0.6)", border: "1px solid rgba(120,80,20,0.35)", borderRadius: 6, padding: "5px 10px", fontFamily: "'DM Mono', monospace", fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", color: "rgba(180,140,80,0.55)", cursor: "pointer" }}>{act}</button>
              ))}
              <button style={{ background: "rgba(8,5,2,0.6)", border: "1px solid rgba(30,215,96,0.35)", borderRadius: 6, padding: "5px 10px", fontFamily: "'DM Mono', monospace", fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", color: "#1ed760", cursor: "pointer" }}>Spotify</button>
            </div>
          </div>
        ))}
        <div style={{ padding: "10px 20px", fontFamily: "'DM Mono', monospace", fontSize: 11, color: "rgba(120,80,20,0.7)" }}>
          NEURAL MATCH →
          <span style={{ color: "rgba(180,140,80,0.55)", marginLeft: 8 }}>#late night &nbsp; #night drive &nbsp; #rain &nbsp; #travis scott &nbsp; #dark chill</span>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN LANDING PAGE
═══════════════════════════════════════════════════════════════ */
export default function LandingPage({ onLaunch }) {
  const [navSolid, setNavSolid] = useState(false);
  const [typed, setTyped]       = useState("");
  const fullText = `"Late night drive through rain-slicked streets, Travis Scott on the radio, city lights bleeding in the fog..."`;

  useEffect(() => {
    const fn = () => setNavSolid(window.scrollY > 40);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  useEffect(() => {
    if (typed.length >= fullText.length) return;
    const t = setTimeout(() => setTyped(fullText.slice(0, typed.length + 1)), 42);
    return () => clearTimeout(t);
  }, [typed, fullText]);

  const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  const amberBtnBase = {
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 10,
    background: "linear-gradient(135deg, #92400e 0%, #b45309 50%, #d97706 100%)",
    border: "1px solid rgba(251,191,36,0.3)", color: "#fef3c7",
    fontFamily: "'DM Mono', monospace", fontSize: 12, letterSpacing: "0.15em",
    textTransform: "uppercase", fontWeight: 500, cursor: "pointer", borderRadius: 10,
    boxShadow: "0 4px 20px rgba(180,100,10,0.35)",
    transition: "opacity .2s, transform .15s, box-shadow .2s",
  };

  const S = {
    divider:      { border: "none", height: 1, margin: 0, background: "linear-gradient(90deg, transparent, rgba(120,80,20,0.4), transparent)" },
    container:    { maxWidth: 1080, margin: "0 auto", padding: "0 2rem" },
    sectionLabel: { fontFamily: "'DM Mono', monospace", fontSize: 10, letterSpacing: "0.25em", textTransform: "uppercase", color: "rgba(180,140,80,0.5)", marginBottom: 6 },
    sectionTitle: { fontFamily: "'Playfair Display', serif", fontSize: "clamp(1.6rem,3vw,2.4rem)", fontWeight: 700, color: "#e8d5a3", marginBottom: "0.8rem", lineHeight: 1.2 },
    sectionDesc:  { fontFamily: "'DM Mono', monospace", fontSize: 13, color: "rgba(180,140,80,0.6)", lineHeight: 1.8, maxWidth: 580, marginBottom: "2.8rem" },
  };

  return (
    <>
      {/* ── FONTS + KEYFRAMES ── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Cormorant+Garamond:wght@400;600&display=swap');
        @keyframes barDance  { from { height: 4px; } to { height: 30px; } }
        @keyframes lpFadeUp  { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: none; } }
        @keyframes lpPulse   { 0%,100%{ opacity:1; transform:scale(1); } 50%{ opacity:.4; transform:scale(1.5); } }
        @keyframes lpBlink   { 50% { opacity: 0; } }
      `}</style>

      {/* ── NAV ──────────────────────────────────────────── */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100, height: 58,
        background: navSolid ? "rgba(8,5,1,0.97)" : "rgba(8,5,1,0.85)",
        backdropFilter: "blur(12px)", borderBottom: "1px solid rgba(120,80,20,0.3)",
        padding: "0 2rem", display: "flex", alignItems: "center", justifyContent: "space-between",
        transition: "background .3s", fontFamily: "'DM Mono', monospace",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 34, height: 34, borderRadius: "50%", background: "conic-gradient(from 0deg, #1a1008, #3d2510, #1a1008, #2e1a0a, #1a1008)", border: "2px solid rgba(180,140,80,0.4)", boxShadow: "0 0 14px rgba(217,119,6,0.35)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ width: 9, height: 9, borderRadius: "50%", background: "radial-gradient(circle, #d97706, #7a4f12)" }} />
          </div>
          <div>
            <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 17, fontWeight: 900, color: "#e8d5a3", letterSpacing: "-0.01em", lineHeight: 1 }}>VibeFinderAI</div>
            <div style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", letterSpacing: "0.25em", textTransform: "uppercase" }}>Acoustic Intelligence</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "1.4rem" }}>
          {[["How It Works","how-it-works"],["Features","features"],["Languages","languages"],["Use Cases","use-cases"]].map(([label, id]) => (
            <button key={id} onClick={() => scrollTo(id)} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(180,140,80,0.5)", fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", fontFamily: "'DM Mono', monospace", transition: "color .2s" }}
              onMouseEnter={e => e.target.style.color = "#e8d5a3"}
              onMouseLeave={e => e.target.style.color = "rgba(180,140,80,0.5)"}
            >{label}</button>
          ))}
          <button onClick={onLaunch} className="dial-btn" style={{ ...amberBtnBase, padding: "8px 20px" }}
            onMouseEnter={e => { e.currentTarget.style.opacity = ".85"; e.currentTarget.style.transform = "translateY(-1px)"; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = "1";   e.currentTarget.style.transform = "none"; }}
          >⚡ Launch App</button>
        </div>
      </nav>

      {/* ── HERO ─────────────────────────────────────────── */}
      <section style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "100px 2rem 80px", position: "relative", overflow: "hidden", background: "#0a0602" }}>
        <div style={{ position: "absolute", inset: 0, zIndex: 0, backgroundImage: "linear-gradient(rgba(120,80,20,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(120,80,20,0.06) 1px, transparent 1px)", backgroundSize: "48px 48px" }} />
        <div style={{ position: "absolute", width: 600, height: 600, borderRadius: "50%", background: "radial-gradient(ellipse, rgba(180,100,10,0.1), transparent 70%)", top: "50%", left: "50%", transform: "translate(-50%,-55%)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", inset: 0, zIndex: 1, pointerEvents: "none", backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 5px, rgba(0,0,0,0.06) 5px, rgba(0,0,0,0.06) 6px)" }} />

        <div style={{ position: "relative", zIndex: 2, textAlign: "center", maxWidth: 840, animation: "lpFadeUp .7s ease both" }}>
          {/* Signal badge */}
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(120,60,10,0.2)", border: "1px solid rgba(180,120,40,0.35)", padding: "5px 16px", borderRadius: 20, fontFamily: "'DM Mono', monospace", fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", color: "rgba(217,160,60,0.8)", marginBottom: "1.8rem" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34d399", boxShadow: "0 0 6px #34d399", display: "inline-block", animation: "lpPulse 1.8s infinite" }} />
            Neural Engine Active — v8.0
          </div>

          <h1 style={{ fontFamily: "'Playfair Display', serif", fontWeight: 900, fontSize: "clamp(2.2rem,5.5vw,4rem)", lineHeight: 1.1, color: "#e8d5a3", marginBottom: "1.2rem", letterSpacing: "-0.01em" }}>
            Describe a feeling.<br />
            <span style={{ color: "#d97706" }}>Discover the perfect</span>{" "}
            <span style={{ fontStyle: "italic", color: "#fde68a" }}>soundtrack.</span>
          </h1>

          <p style={{ fontFamily: "'DM Mono', monospace", fontSize: "clamp(13px,2vw,15px)", color: "rgba(180,140,80,0.65)", maxWidth: 580, margin: "0 auto 2.4rem", lineHeight: 1.85 }}>
            VibeFinderAI is a mood-first music discovery engine. Instead of searching by genre or artist —
            describe the moment, and the AI finds songs that match the exact feeling.
          </p>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 20, marginBottom: "2.4rem", flexWrap: "wrap" }}>
            <WaveformBars active={true} count={18} />
            <Oscilloscope active={true} />
            <WaveformBars active={true} count={18} />
          </div>

          {/* ── BIG CTA BOX ─────────────────────────────── */}
          <div className="panel-card screws" style={{ padding: "2.6rem 2.8rem", maxWidth: 700, margin: "0 auto", position: "relative" }}>
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: "linear-gradient(90deg, #92400e, #d97706, #fbbf24, #d97706, #92400e)", borderRadius: "16px 16px 0 0" }} />
            <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 7px, rgba(120,80,20,0.03) 7px, rgba(120,80,20,0.03) 8px)", pointerEvents: "none", borderRadius: 16 }} />
            <div style={{ position: "relative" }}>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.4)", textAlign: "left", marginBottom: 8 }}>// ACOUSTIC DESCRIPTOR INPUT</div>
              <div style={{ background: "rgba(5,3,1,0.8)", border: "1px solid rgba(120,80,20,0.35)", borderRadius: 10, padding: "16px", fontFamily: "'DM Mono', monospace", fontSize: 13, color: "rgba(180,140,80,0.7)", lineHeight: 1.65, textAlign: "left", minHeight: 72, marginBottom: "1.6rem", fontStyle: "italic" }}>
                {typed}
                <span style={{ display: "inline-block", width: 8, height: 14, background: "rgba(217,119,6,0.9)", marginLeft: 2, animation: "lpBlink 1s step-end infinite", verticalAlign: "text-bottom", boxShadow: "0 0 6px rgba(217,119,6,0.6)" }} />
              </div>
              <button onClick={onLaunch} className="dial-btn" style={{ ...amberBtnBase, padding: "14px 32px", width: "100%", fontSize: 13, letterSpacing: "0.18em" }}
                onMouseEnter={e => { e.currentTarget.style.opacity = ".88"; e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 30px rgba(180,100,10,0.55)"; }}
                onMouseLeave={e => { e.currentTarget.style.opacity = "1";   e.currentTarget.style.transform = "none"; e.currentTarget.style.boxShadow = "0 4px 20px rgba(180,100,10,0.35)"; }}
              >
                <span>⚡</span> Analyse My Vibe — Launch App <span>→</span>
              </button>
              <p style={{ marginTop: 10, fontFamily: "'DM Mono', monospace", fontSize: 10, color: "rgba(120,80,20,0.6)", textAlign: "center", letterSpacing: "0.08em" }}>
                Free to use · No account needed ·{" "}
                <button onClick={() => scrollTo("how-it-works")} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(217,160,60,0.7)", fontFamily: "'DM Mono', monospace", fontSize: 10, padding: 0, textDecoration: "underline" }}>See how it works ↓</button>
              </p>
            </div>
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ── HOW IT WORKS ──────────────────────────────────── */}
      <section id="how-it-works" style={{ padding: "80px 2rem", background: "#0a0602" }}>
        <div style={S.container}>
          <p style={S.sectionLabel}>// Engine Protocol</p>
          <h2 style={S.sectionTitle}>How it works</h2>
          <p style={S.sectionDesc}>Six steps from description to playlist. The whole thing takes about 3–5 seconds.</p>
          <div style={{ borderTop: "1px solid rgba(120,80,20,0.2)" }}>
            <Step num="01" title="Describe the Vibe"
              desc="Type any mood, scene, activity, or feeling. You can be as specific or abstract as you want — the AI handles both."
              tip={<>"2am, can't sleep, soft piano, city rain outside the window"<br />"hard gym session, angry phonk, no thoughts just lifting"<br />"heartbreak road trip, indie folk, crying with sunglasses on"</>}
            />
            <Step num="02" title="Tune the Knobs (optional)"
              desc="ARTIST controls how closely results sound like a reference artist. NICHENESS slides from mainstream hits to deep underground cuts. BPM sets target energy and tempo."
              tag="Default settings work great for most prompts"
            />
            <Step num="03" title="Select Language"
              desc="Each language routes to its own dedicated tag pool — a Hindi heartbreak prompt returns Bollywood sad songs, not generic western indie pop."
              tag="16 Languages Supported"
            />
            <Step num="04" title="Set Track Count & Run Analysis"
              desc="Choose 5, 10, 20, or 50 tracks. The neural engine classifies your vibe, extracts semantic keywords, maps to genre tags, fetches and scores a matched pool of tracks."
              tag="~3–5 second processing time"
            />
            <Step num="05" title="Read the Analysis"
              desc="The engine surfaces a Dominant Vibe with confidence score, a Secondary Signature you can pivot to, a BPM range, and clickable genre tags to hard-filter results."
              tag="Full transparency on how your vibe was interpreted"
            />
            <Step num="06" title="Listen, Preview, Open on Spotify"
              desc="Every track has inline preview playback, a direct Spotify link, and 👍 / 👎 feedback. Pivot to the secondary vibe or tweak knobs and re-run if needed."
              tag="No Spotify account required to preview"
            />
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ── KNOBS ─────────────────────────────────────────── */}
      <section style={{ padding: "80px 2rem", background: "rgba(14,9,3,0.95)" }}>
        <div style={S.container}>
          <p style={S.sectionLabel}>// Acoustic Parameters</p>
          <h2 style={S.sectionTitle}>The three knobs</h2>
          <p style={S.sectionDesc}>Fine-tune the engine without changing your description. Each knob maps to a specific axis of the recommendation space.</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "1.2rem" }}>
            <KnobDisplay emoji="🎤" name="Artist"    desc="How closely results sound like a specific artist. Dial up to stay close to a reference. Dial down for broader, mood-only matching." />
            <KnobDisplay emoji="🔍" name="Nicheness" desc="Slides between mainstream (0) and deep cuts (100). High nicheness surfaces underground and lesser-known tracks. Low for recognisable hits." />
            <KnobDisplay emoji="⚡" name="BPM"       desc="Controls target tempo and energy. Low BPM for slow, ambient, sleeping. High BPM for workouts, raves, and hype sessions." />
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ── FEATURES ─────────────────────────────────────── */}
      <section id="features" style={{ padding: "80px 2rem", background: "#0a0602" }}>
        <div style={S.container}>
          <p style={S.sectionLabel}>// Engine Capabilities</p>
          <h2 style={S.sectionTitle}>What makes it different</h2>
          <p style={S.sectionDesc}>Not a playlist generator. Not a genre picker. An acoustic intelligence layer that maps language to sound.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 1, background: "rgba(120,80,20,0.2)", border: "1px solid rgba(120,80,20,0.35)", borderRadius: 16, overflow: "hidden" }}>
            <FeatureCard icon="🧠" title="Natural Language Vibe Analysis"  desc="Describe a moment, emotion, or scene in plain language. The AI extracts semantic concepts, dominant moods, and audio attributes from your text." badge="Gemini AI" />
            <FeatureCard icon="🎯" title="Artist & Genre Anchoring"         desc="Mention an artist in your description and the engine locks onto their sonic profile. Genre tags in the results are clickable hard filters." badge="Smart Detection" />
            <FeatureCard icon="🌐" title="16-Language Support"              desc="Deep routing for Indian regional music — Hindi, Punjabi, Tamil, Telugu, Kannada, Malayalam, Bengali, Urdu — plus Korean, Japanese, Spanish, Arabic and more." badge="Regional Music" />
            <FeatureCard icon="🎛️" title="Pro Mode Overrides"               desc="Force a specific artist, lock to a genre, or hard-switch to the secondary vibe. Designed for power users who want full control." badge="Pro Mode" />
            <FeatureCard icon="▶️" title="Inline Previews + Spotify"        desc="Preview tracks without leaving the app. Every result links directly to Spotify with album art, artist info, and 👍/👎 feedback buttons." badge="Spotify API" />
            <FeatureCard icon="🔬" title="Neural Match Breakdown"           desc="See exactly which semantic keywords the AI extracted — like #late night #rain #travis scott — so you know how it interpreted your vibe." badge="Full Transparency" />
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ── RESULT ANATOMY ────────────────────────────────── */}
      <section style={{ padding: "80px 2rem", background: "rgba(14,9,3,0.95)" }}>
        <div style={S.container}>
          <p style={S.sectionLabel}>// Output Anatomy</p>
          <h2 style={S.sectionTitle}>What you get back</h2>
          <p style={S.sectionDesc}>Every analysis returns a full breakdown — not just a playlist. Here's a live example of what an analysis output looks like.</p>
          <ResultPreview />
        </div>
      </section>
      <hr style={S.divider} />

      {/* ── PRO MODE ─────────────────────────────────────── */}
      <section style={{ padding: "80px 2rem", background: "#0a0602" }}>
        <div style={S.container}>
          <p style={S.sectionLabel}>// Advanced Controls</p>
          <h2 style={S.sectionTitle}>Pro Mode overrides</h2>
          <p style={S.sectionDesc}>For power users who want to combine AI vibe matching with manual constraints. Expand the Pro Mode panel after any analysis.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
            {[
              { title: "⚡ Force Artist Bypass",        desc: "Lock all results to a specific artist's discography or sonic profile — type \"Deftones\" to only get Deftones-adjacent tracks regardless of vibe." },
              { title: "🎛️ Force Genre Bypass",          desc: "Override the AI's genre inference and lock to a genre directly — \"shoegaze\", \"bhangra\", \"drum and bass\" — bypasses vibe detection entirely." },
              { title: "🔄 Hard-Switch Secondary Vibe",  desc: "When the AI detects overlapping vibes, toggle to force the secondary vibe as primary — useful when the dominant classification isn't what you wanted." },
            ].map(card => (
              <div key={card.title} className="panel-card" style={{ padding: "1.4rem", borderLeft: "3px solid rgba(217,119,6,0.6)" }}>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase", color: "rgba(217,160,60,0.85)", marginBottom: 10 }}>{card.title}</div>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "rgba(180,140,80,0.6)", lineHeight: 1.75 }}>{card.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ── LANGUAGES ─────────────────────────────────────── */}
      <section id="languages" style={{ padding: "80px 2rem", background: "rgba(14,9,3,0.95)" }}>
        <div style={S.container}>
          <p style={S.sectionLabel}>// Language Routing</p>
          <h2 style={S.sectionTitle}>16 languages, regional-aware routing</h2>
          <p style={S.sectionDesc}>Most music apps treat language as a metadata filter. VibeFinderAI routes each language to dedicated Last.fm tag pools — so a Hindi heartbreak prompt actually returns Bollywood sad songs.</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: "1.6rem" }}>
            {["Hindi","Punjabi","Tamil","Telugu","Kannada","Malayalam","Bengali","Urdu"].map(l => (
              <span key={l} className="freq-tag" style={{ color: "#d97706", borderColor: "rgba(217,119,6,0.45)", background: "rgba(120,60,10,0.25)" }}>{l}</span>
            ))}
            {["English","Korean","Japanese","Spanish","Portuguese","French","Arabic","Afrobeats"].map(l => (
              <span key={l} className="freq-tag">{l}</span>
            ))}
          </div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "rgba(180,140,80,0.6)", borderLeft: "2px solid rgba(217,119,6,0.5)", paddingLeft: 14, lineHeight: 1.8 }}>
            Indian languages are highlighted — VibeFinderAI was built with South Asian music discovery as a first-class use case.
            Describe a shaadi vibe, a heartbreak in Hindi, a bhangra session, or a late-night sufi moment — and get the right regional pool back.
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ── USE CASES ─────────────────────────────────────── */}
      <section id="use-cases" style={{ padding: "80px 2rem", background: "#0a0602" }}>
        <div style={S.container}>
          <p style={S.sectionLabel}>// Scenarios</p>
          <h2 style={S.sectionTitle}>What people use it for</h2>
          <p style={S.sectionDesc}>Anything that has a feeling but doesn't map neatly to a genre.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem" }}>
            <UseCaseCard emoji="🌧️" title="Mood-based listening"         desc="You feel something but don't know what song fits. Just describe the feeling."   example="sad and numb but also kind of okay, november rain, slow indie" />
            <UseCaseCard emoji="💻" title="Activity playlists"            desc="Gaming, coding late night, gym, studying — describe the context."               example="3am coding session, lofi beats, hyperfocus, dark room, monitors glow" />
            <UseCaseCard emoji="🎸" title="Artist-inspired discovery"     desc="Mention a reference artist, crank Nicheness, find lesser-known gems."           example="sounds like Radiohead but more ambient, deep cuts only, post-2000" />
            <UseCaseCard emoji="🪘" title="Indian regional discovery"     desc="Desi vibes, regional emotions, Bollywood moods — fully supported."             example="sufi night, rooftop, chai, Nusrat Fateh Ali Khan energy, ghazal" />
            <UseCaseCard emoji="🎉" title="Event & party playlists"       desc="Shaadi, birthday, pre-drinks, sangeet — describe the occasion."                 example="sangeet night, full crowd, bhangra energy, everyone on the dancefloor" />
            <UseCaseCard emoji="🌅" title="Scene & cinematic vibes"       desc="Describe a scene or visual and let the AI find the perfect score."              example="watching the sun go down from a moving train, bittersweet, orchestral" />
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ── FINAL CTA ─────────────────────────────────────── */}
      <section style={{ padding: "100px 2rem", background: "rgba(14,9,3,0.97)", textAlign: "center", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", fontFamily: "'Playfair Display', serif", fontSize: "clamp(60px,12vw,130px)", color: "rgba(120,60,10,0.04)", fontWeight: 900, top: "50%", left: "50%", transform: "translate(-50%,-50%)", whiteSpace: "nowrap", pointerEvents: "none", userSelect: "none" }}>VibeFinderAI</div>
        <div style={{ position: "relative", zIndex: 1 }}>
          <p style={S.sectionLabel}>// Ready?</p>
          <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: "clamp(1.6rem,4vw,2.8rem)", fontWeight: 900, color: "#e8d5a3", marginBottom: "1rem", lineHeight: 1.2 }}>
            Stop searching.<br /><span style={{ fontStyle: "italic", color: "#fde68a" }}>Start describing.</span>
          </h2>
          <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: "rgba(180,140,80,0.6)", maxWidth: 460, margin: "0 auto 2.4rem", lineHeight: 1.8 }}>
            Type a feeling. The engine handles the rest.<br />No account, no sign-up — just launch and run your first analysis.
          </p>
          <button onClick={onLaunch} className="dial-btn" style={{ ...amberBtnBase, padding: "16px 44px", fontSize: 13, letterSpacing: "0.2em" }}
            onMouseEnter={e => { e.currentTarget.style.opacity = ".88"; e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 32px rgba(180,100,10,0.55)"; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = "1";   e.currentTarget.style.transform = "none"; e.currentTarget.style.boxShadow = "0 4px 20px rgba(180,100,10,0.35)"; }}
          >⚡ Launch VibeFinderAI →</button>
        </div>
      </section>

      {/* ── FOOTER ───────────────────────────────────────── */}
      <footer style={{ borderTop: "1px solid rgba(120,80,20,0.3)", padding: "1.6rem 2rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, fontFamily: "'DM Mono', monospace", fontSize: 11, color: "rgba(120,80,20,0.6)", background: "#0a0602" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 22, height: 22, borderRadius: "50%", background: "conic-gradient(from 0deg, #1a1008, #3d2510, #1a1008)", border: "1px solid rgba(180,140,80,0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "radial-gradient(circle, #d97706, #7a4f12)" }} />
          </div>
          <span style={{ letterSpacing: "0.15em", textTransform: "uppercase", fontFamily: "'Playfair Display', serif", fontSize: 12, color: "#e8d5a3" }}>VibeFinderAI</span>
        </div>
        <span style={{ letterSpacing: "0.06em" }}>Neural engine v8.0 · Gemini + Last.fm + Spotify</span>
        <div style={{ display: "flex", gap: "1.2rem" }}>
          {[["App", onLaunch], ["How It Works", () => scrollTo("how-it-works")], ["Features", () => scrollTo("features")]].map(([label, fn]) => (
            <button key={label} onClick={fn} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(120,80,20,0.6)", fontFamily: "'DM Mono', monospace", fontSize: 11, letterSpacing: "0.08em" }}
              onMouseEnter={e => e.target.style.color = "rgba(180,140,80,0.7)"}
              onMouseLeave={e => e.target.style.color = "rgba(120,80,20,0.6)"}
            >{label}</button>
          ))}
        </div>
      </footer>
    </>
  );
}
