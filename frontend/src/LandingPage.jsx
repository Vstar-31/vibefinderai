import { useState, useEffect, useRef } from "react";

/* ─── WAVEFORM BARS ──────────────────────────────────────────── */
function WaveformBars({ active = true, count = 16 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "3px", height: "28px" }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{
          width: "3px", minHeight: "4px", maxHeight: "28px", borderRadius: "2px",
          background: active
            ? `hsl(${36 + i * 1.5}, 75%, ${50 + (i % 4) * 5}%)`
            : "rgba(180,140,80,0.12)",
          animationName: active ? "barDance" : "none",
          animationDuration: `${380 + (i % 7) * 80}ms`,
          animationDelay: `${(i * 45) % 700}ms`,
          animationTimingFunction: "ease-in-out",
          animationIterationCount: "infinite",
          animationDirection: "alternate",
          height: active ? undefined : "5px",
        }} />
      ))}
    </div>
  );
}

/* ─── OSCILLOSCOPE ───────────────────────────────────────────── */
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
      ctx.strokeStyle = active ? "rgba(217,119,6,0.8)" : "rgba(120,80,20,0.2)";
      ctx.lineWidth = active ? 1.5 : 1;
      ctx.shadowBlur = active ? 6 : 0;
      ctx.shadowColor = "rgba(217,119,6,0.5)";
      ctx.beginPath();
      for (let x = 0; x < W; x++) {
        const t = tRef.current;
        const y = active
          ? H/2 + Math.sin((x/W)*Math.PI*4 + t*0.05)*12
              + Math.sin((x/W)*Math.PI*9 + t*0.08)*5
              + Math.sin((x/W)*Math.PI*17 + t*0.03)*2
          : H/2 + Math.sin((x/W)*Math.PI*2)*2;
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
      background: "rgba(20,13,5,0.7)", border: "1px solid rgba(120,80,20,0.3)",
      borderRadius: 7, padding: "5px 10px", display: "flex", alignItems: "center", gap: 7,
    }}>
      <span style={{ fontSize: 8, fontFamily: "monospace", color: "rgba(180,140,80,0.4)", letterSpacing: "0.12em", textTransform: "uppercase" }}>OSC</span>
      <canvas ref={canvasRef} width={120} height={28} style={{ display: "block" }} />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN LANDING PAGE
═══════════════════════════════════════════════════════════════ */
export default function LandingPage({ onNavigate, onLaunch }) {
  // Accepts both new (onNavigate) and legacy (onLaunch) prop shapes
  const launch = () => {
    if (onNavigate) onNavigate('/app');
    else onLaunch?.();
  };

  const [navSolid,    setNavSolid]    = useState(false);
  const [menuOpen,    setMenuOpen]    = useState(false);
  const [typed,       setTyped]       = useState("");
  const [proExpanded, setProExpanded] = useState(false);

  const fullText = `"Late night drive through rain-slicked streets, the city bleeding through fog, something dark and cinematic..."`;

  useEffect(() => {
    const fn = () => { setNavSolid(window.scrollY > 40); };
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  useEffect(() => {
    if (typed.length >= fullText.length) return;
    const t = setTimeout(() => setTyped(fullText.slice(0, typed.length + 1)), 40);
    return () => clearTimeout(t);
  }, [typed, fullText]);

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    setMenuOpen(false);
  };

  /* ── Shared tokens ── */
  const amber = "#d97706";
  const amberBtn = {
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
    background: "linear-gradient(135deg, #92400e 0%, #b45309 50%, #d97706 100%)",
    border: "1px solid rgba(251,191,36,0.25)", color: "#fef3c7",
    fontFamily: "'DM Mono', monospace", fontSize: 12, letterSpacing: "0.14em",
    textTransform: "uppercase", fontWeight: 500, cursor: "pointer", borderRadius: 10,
    boxShadow: "0 4px 18px rgba(180,100,10,0.3)",
    transition: "opacity .2s, transform .15s, box-shadow .2s",
  };
  const mono  = "'DM Mono', monospace";
  const serif = "'Playfair Display', serif";
  const S = {
    divider:   { border: "none", height: 1, margin: 0, background: "linear-gradient(90deg, transparent, rgba(120,80,20,0.35), transparent)" },
    container: { maxWidth: 1040, margin: "0 auto", padding: "0 1.4rem" },
    label:     { fontFamily: mono, fontSize: 10, letterSpacing: "0.22em", textTransform: "uppercase", color: "rgba(180,140,80,0.45)", marginBottom: 6 },
    h2:        { fontFamily: serif, fontSize: "clamp(1.5rem,3vw,2.2rem)", fontWeight: 700, color: "#ead9a8", marginBottom: "0.7rem", lineHeight: 1.2 },
    body:      { fontFamily: mono, fontSize: 13, color: "rgba(190,155,90,0.65)", lineHeight: 1.8, maxWidth: 560, marginBottom: "2.4rem" },
  };

  const NAV_LINKS = [["How It Works","how-it-works"],["Features","features"],["Languages","languages"],["Use Cases","use-cases"]];

  return (
    <>
      {/* ── FONTS + GLOBAL STYLES ── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Cormorant+Garamond:wght@400;500;600&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body { background: #100b04; }

        @keyframes barDance   { from { height: 4px; } to { height: 26px; } }
        @keyframes fadeUp     { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: none; } }
        @keyframes pulse      { 0%,100%{ opacity:1; transform:scale(1); } 50%{ opacity:.35; transform:scale(1.5); } }
        @keyframes blink      { 50% { opacity: 0; } }
        @keyframes slideDown  { from { opacity:0; transform:translateY(-8px); } to { opacity:1; transform:none; } }

        .lp-card {
          background: linear-gradient(155deg, rgba(38,25,9,0.95), rgba(22,14,4,0.98));
          border: 1px solid rgba(155,105,28,0.32);
          border-radius: 14px;
          transition: border-color .2s, transform .15s;
        }
        .lp-card:hover { border-color: rgba(217,119,6,0.38); }

        .freq-tag {
          display: inline-block;
          padding: 3px 10px; border-radius: 20px;
          border: 1px solid rgba(155,105,28,0.38);
          background: rgba(28,18,6,0.6);
          font-family: 'DM Mono', monospace; font-size: 10px;
          letter-spacing: 0.1em; text-transform: uppercase;
          color: rgba(190,155,90,0.7);
        }

        /* ── Responsive nav ── */
        .nav-links    { display: flex; align-items: center; gap: 1.2rem; }
        .nav-hamburger{ display: none; }
        @media (max-width: 680px) {
          .nav-links    { display: none; }
          .nav-hamburger{ display: flex !important; }
        }

        /* ── Section padding ── */
        .lp-section { padding: 70px 1.4rem; }
        @media (max-width: 600px) { .lp-section { padding: 52px 1.2rem; } }

        /* ── Feature grid ── */
        .feature-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 1px;
          background: rgba(155,105,28,0.22);
          border: 1px solid rgba(155,105,28,0.32);
          border-radius: 14px;
          overflow: hidden;
        }
        @media (max-width: 540px) { .feature-grid { grid-template-columns: 1fr; } }

        /* ── Use-case grid ── */
        .usecase-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
        @media (max-width: 500px) { .usecase-grid { grid-template-columns: 1fr; } }

        /* ── Steps ── */
        .step-row {
          display: grid; grid-template-columns: 50px 1fr; gap: 1.2rem;
          padding: 1.6rem 0; border-bottom: 1px solid rgba(150,100,25,0.2);
        }

        /* ── Result preview inner grid ── */
        .rp-stat-grid { display: grid; grid-template-columns: 1fr 1fr; }
        @media (max-width: 420px) { .rp-stat-grid { grid-template-columns: 1fr; } }

        /* ── Pro mode grid ── */
        .pro-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
        @media (max-width: 900px) { .pro-grid { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 560px) { .pro-grid { grid-template-columns: 1fr; } }

        /* ── Knob row ── */
        .knob-row  { display: flex; gap: 1rem; flex-wrap: wrap; }
        .knob-item { flex: 1; min-width: 150px; }

        /* ── Mobile menu ── */
        .mobile-menu {
          display: none; position: fixed; top: 58px; left: 0; right: 0; z-index: 99;
          background: rgba(8,5,1,0.98); border-bottom: 1px solid rgba(155,105,28,0.3);
          padding: 1rem 1.4rem 1.4rem; flex-direction: column; gap: 0;
          animation: slideDown .18s ease;
        }
        .mobile-menu.open { display: flex; }
        .mobile-menu-link {
          padding: 13px 0; border-bottom: 1px solid rgba(120,80,20,0.15);
          font-family: 'DM Mono', monospace; font-size: 12px;
          letter-spacing: 0.12em; text-transform: uppercase;
          color: rgba(190,155,90,0.7);
          background: none; border-left: none; border-right: none; border-top: none;
          cursor: pointer; text-align: left; transition: color .15s;
        }
        .mobile-menu-link:last-child { border-bottom: none; margin-top: 12px; }
        .mobile-menu-link:hover { color: #ead9a8; }

        /* ── Pro Mode toggle button (mobile) ── */
        .pro-toggle {
          display: none;
          width: 100%; padding: 12px 16px; margin-bottom: 1rem;
          background: rgba(20,12,4,0.7); border: 1px solid rgba(155,105,28,0.3);
          border-radius: 10px; color: rgba(210,160,60,0.8);
          font-family: 'DM Mono', monospace; font-size: 11px; letter-spacing: 0.1em;
          text-transform: uppercase; cursor: pointer; text-align: left;
          justify-content: space-between; align-items: center;
        }
        @media (max-width: 600px) { .pro-toggle { display: flex; } }

        /* ── CTA buttons — bigger tap targets on mobile ── */
        @media (max-width: 600px) {
          .lp-cta-btn { padding: 16px 28px !important; font-size: 13px !important; width: 100% !important; }
          .lp-hero-cta { padding: 15px 22px !important; }
        }
      `}</style>

      {/* ══ NAV ══════════════════════════════════════════════════ */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100, height: 58,
        background: navSolid ? "rgba(7,4,1,0.98)" : "rgba(7,4,1,0.88)",
        backdropFilter: "blur(14px)", borderBottom: "1px solid rgba(155,105,28,0.3)",
        padding: "0 1.4rem", display: "flex", alignItems: "center", justifyContent: "space-between",
        transition: "background .3s",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <div style={{ width: 32, height: 32, borderRadius: "50%", background: "conic-gradient(from 0deg, #1a1008, #3d2510, #1a1008, #2e1a0a, #1a1008)", border: "2px solid rgba(180,140,80,0.35)", boxShadow: "0 0 12px rgba(217,119,6,0.3)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "radial-gradient(circle, #d97706, #7a4f12)" }} />
          </div>
          <div>
            <div style={{ fontFamily: serif, fontSize: 16, fontWeight: 900, color: "#ead9a8", letterSpacing: "-0.01em", lineHeight: 1 }}>VibeFinderAI</div>
            <div style={{ fontFamily: mono, fontSize: 8, color: "rgba(180,140,80,0.35)", letterSpacing: "0.22em", textTransform: "uppercase" }}>Acoustic Intelligence</div>
          </div>
        </div>

        {/* Desktop nav links */}
        <div className="nav-links">
          {NAV_LINKS.map(([label, id]) => (
            <button key={id} onClick={() => scrollTo(id)} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(180,140,80,0.5)", fontFamily: mono, fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", transition: "color .2s", padding: "4px 0" }}
              onMouseEnter={e => e.target.style.color = "#ead9a8"}
              onMouseLeave={e => e.target.style.color = "rgba(180,140,80,0.5)"}
            >{label}</button>
          ))}
          <button onClick={launch} style={{ ...amberBtn, padding: "8px 18px" }}
            onMouseEnter={e => { e.currentTarget.style.opacity = ".85"; e.currentTarget.style.transform = "translateY(-1px)"; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = "1";   e.currentTarget.style.transform = "none"; }}
          >⚡ Launch</button>
        </div>

        {/* Hamburger (mobile) */}
        <button className="nav-hamburger" onClick={() => setMenuOpen(o => !o)} style={{ display: "none", background: "none", border: "1px solid rgba(155,105,28,0.35)", borderRadius: 7, padding: "8px 12px", cursor: "pointer", color: "rgba(190,155,90,0.8)", fontFamily: mono, fontSize: 11, letterSpacing: "0.08em", gap: 7, alignItems: "center", minHeight: 44 }}>
          <span style={{ fontSize: 14, lineHeight: 1 }}>{menuOpen ? "✕" : "☰"}</span>
          <span style={{ fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase" }}>Menu</span>
        </button>
      </nav>

      {/* Mobile dropdown menu */}
      <div className={`mobile-menu${menuOpen ? " open" : ""}`}>
        {NAV_LINKS.map(([label, id]) => (
          <button key={id} className="mobile-menu-link" onClick={() => scrollTo(id)}>{label}</button>
        ))}
        <button onClick={() => { launch(); setMenuOpen(false); }} style={{ ...amberBtn, padding: "14px 20px", marginTop: 4, minHeight: 48 }}>⚡ Launch App →</button>
      </div>

      {/* ══ HERO ═════════════════════════════════════════════════ */}
      <section style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "100px 1.4rem 72px", position: "relative", overflow: "hidden", background: "linear-gradient(180deg, #0d0803 0%, #130d05 100%)" }}>
        {/* Grid texture */}
        <div style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(rgba(120,80,20,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(120,80,20,0.05) 1px, transparent 1px)", backgroundSize: "44px 44px", pointerEvents: "none" }} />
        {/* Glow */}
        <div style={{ position: "absolute", width: "min(500px, 80vw)", height: "min(500px, 80vw)", borderRadius: "50%", background: "radial-gradient(ellipse, rgba(180,100,10,0.09), transparent 70%)", top: "50%", left: "50%", transform: "translate(-50%,-55%)", pointerEvents: "none" }} />

        <div style={{ position: "relative", zIndex: 2, textAlign: "center", maxWidth: 780, width: "100%", animation: "fadeUp .65s ease both" }}>

          {/* Badge */}
          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, background: "rgba(110,55,8,0.18)", border: "1px solid rgba(180,120,40,0.28)", padding: "5px 14px", borderRadius: 20, fontFamily: mono, fontSize: 9, letterSpacing: "0.14em", textTransform: "uppercase", color: "rgba(210,160,60,0.75)", marginBottom: "1.6rem" }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#34d399", boxShadow: "0 0 6px #34d399", display: "inline-block", animation: "pulse 1.8s infinite" }} />
            Neural Engine Active — Phase 8
          </div>

          <h1 style={{ fontFamily: serif, fontWeight: 900, fontSize: "clamp(2rem,6vw,3.8rem)", lineHeight: 1.1, color: "#ead9a8", marginBottom: "1.1rem", letterSpacing: "-0.01em" }}>
            Describe a feeling.<br />
            <span style={{ color: amber }}>Discover the perfect</span>{" "}
            <span style={{ fontStyle: "italic", color: "#fde68a" }}>soundtrack.</span>
          </h1>

          <p style={{ fontFamily: mono, fontSize: "clamp(12px,1.8vw,14px)", color: "rgba(190,155,90,0.6)", maxWidth: 520, margin: "0 auto 2.2rem", lineHeight: 1.9 }}>
            A mood-first music discovery engine. Skip the genre dropdown —
            describe the moment, and the AI finds songs that match the exact feeling.
          </p>

          {/* Animated signal row */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, marginBottom: "2rem", flexWrap: "wrap" }}>
            <WaveformBars active={true} count={14} />
            <Oscilloscope active={true} />
            <WaveformBars active={true} count={14} />
          </div>

          {/* CTA card */}
          <div className="lp-card" style={{ padding: "clamp(1.6rem,4vw,2.4rem)", maxWidth: 660, margin: "0 auto", position: "relative" }}>
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: "linear-gradient(90deg, #92400e, #d97706, #fbbf24, #d97706, #92400e)", borderRadius: "14px 14px 0 0" }} />
            <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", textAlign: "left", marginBottom: 8 }}>// Acoustic Descriptor Input</div>
            <div style={{ background: "rgba(6,4,1,0.75)", border: "1px solid rgba(155,105,28,0.35)", borderRadius: 9, padding: "14px 16px", fontFamily: mono, fontSize: "clamp(11px,2vw,13px)", color: "rgba(190,155,90,0.65)", lineHeight: 1.7, textAlign: "left", minHeight: 66, marginBottom: "1.4rem", fontStyle: "italic" }}>
              {typed}
              <span style={{ display: "inline-block", width: 7, height: 13, background: "rgba(217,119,6,0.85)", marginLeft: 2, animation: "blink 1s step-end infinite", verticalAlign: "text-bottom" }} />
            </div>
            <button
              onClick={launch}
              className="lp-hero-cta"
              style={{ ...amberBtn, padding: "13px 28px", width: "100%", fontSize: "clamp(11px,2vw,13px)", letterSpacing: "0.16em", minHeight: 48 }}
              onMouseEnter={e => { e.currentTarget.style.opacity = ".86"; e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 28px rgba(180,100,10,0.5)"; }}
              onMouseLeave={e => { e.currentTarget.style.opacity = "1";   e.currentTarget.style.transform = "none"; e.currentTarget.style.boxShadow = "0 4px 18px rgba(180,100,10,0.3)"; }}
            >
              ⚡ Analyse My Vibe — Launch App →
            </button>
            <p style={{ marginTop: 9, fontFamily: mono, fontSize: 10, color: "rgba(120,80,20,0.55)", textAlign: "center", letterSpacing: "0.06em" }}>
              Free to use · No account needed to search ·{" "}
              <button onClick={() => scrollTo("how-it-works")} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(217,160,60,0.6)", fontFamily: mono, fontSize: 10, padding: 0, textDecoration: "underline" }}>How it works ↓</button>
            </p>
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ══ HOW IT WORKS ═════════════════════════════════════════ */}
      <section id="how-it-works" className="lp-section" style={{ background: "#0f0904" }}>
        <div style={S.container}>
          <p style={S.label}>// Engine Protocol</p>
          <h2 style={S.h2}>How it works</h2>
          <p style={S.body}>Six steps from description to playlist. Takes about 3–5 seconds.</p>
          <div style={{ borderTop: "1px solid rgba(150,100,25,0.2)" }}>
            {[
              { n: "01", title: "Describe the vibe", desc: "Type any mood, scene, activity, or feeling in plain language. Abstract or specific — the AI handles both.", tip: `"2am, can't sleep, soft piano, rain outside" or "gym rage session, phonk, no thoughts just lifting"` },
              { n: "02", title: "Tune the knobs", desc: "ARTIST — how closely to match a reference artist. NICHENESS — mainstream to deep cuts. BPM — chill to high energy.", tip: null, tag: "Optional — defaults work great" },
              { n: "03", title: "Pick a language", desc: "Each language routes to its own pool. Hindi heartbreak → Bollywood sad songs. Punjabi hype → bhangra. Not generic western indie.", tag: "18 languages · 10 Indian regional pools" },
              { n: "04", title: "Run the analysis", desc: "The engine classifies your vibe, extracts keywords, maps genre tags, fetches and scores a matched track pool.", tag: "~3–5 seconds" },
              { n: "05", title: "Check the artist banner", desc: "If the engine spotted an artist in your description, a banner tells you what was locked. Tap ✕ to dismiss and switch to pure vibe mode.", tag: "Artist transparency" },
              { n: "06", title: "Listen, refine & save", desc: "Preview tracks inline, open on YouTube or Spotify, rate with 👍/👎. Click genre tags to filter, pivot to secondary vibe, or tweak knobs and re-run. Save playlists and share with a public link.", tag: null },
            ].map(({ n, title, desc, tip, tag }) => (
              <div key={n} className="step-row">
                <div style={{ width: 40, height: 40, flexShrink: 0, background: "rgba(22,14,4,0.8)", border: "1px solid rgba(155,105,28,0.35)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: mono, fontSize: 10, color: "rgba(180,140,80,0.55)", letterSpacing: "0.08em" }}>{n}</div>
                <div>
                  <div style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 600, fontSize: 15, color: "#ead9a8", marginBottom: 5 }}>{title}</div>
                  <div style={{ fontFamily: mono, fontSize: 12, color: "rgba(190,155,90,0.6)", lineHeight: 1.75 }}>{desc}</div>
                  {tip && <div style={{ marginTop: 9, padding: "9px 12px", background: "rgba(10,6,2,0.6)", borderLeft: "2px solid rgba(217,119,6,0.5)", borderRadius: "0 6px 6px 0", fontFamily: mono, fontStyle: "italic", fontSize: 11, color: "rgba(180,140,80,0.5)", lineHeight: 1.65 }}>{tip}</div>}
                  {tag && <span className="freq-tag" style={{ marginTop: 9, display: "inline-block" }}>{tag}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ══ KNOBS ════════════════════════════════════════════════ */}
      <section className="lp-section" style={{ background: "rgba(20,13,5,0.97)" }}>
        <div style={S.container}>
          <p style={S.label}>// Acoustic Parameters</p>
          <h2 style={S.h2}>Three knobs. Full control.</h2>
          <p style={S.body}>Fine-tune results without rewriting your prompt. Each knob shifts a different dimension of the recommendation space.</p>
          <div className="knob-row">
            {[
              { emoji: "🎤", name: "Artist",    desc: "How tightly to match a reference artist's sound. High = close to the artist. Low = pure mood-based results." },
              { emoji: "🔍", name: "Nicheness", desc: "0 = recognisable mainstream. 100 = deep underground cuts. Crank it up to discover hidden gems." },
              { emoji: "⚡", name: "BPM",       desc: "Target tempo and energy. Low for slow ambient. High for raves, runs, and hype sessions." },
            ].map(({ emoji, name, desc }) => (
              <div key={name} className="lp-card knob-item" style={{ padding: "1.4rem 1.2rem", textAlign: "center" }}>
                <div style={{ width: 48, height: 48, borderRadius: "50%", margin: "0 auto 12px", background: "radial-gradient(circle at 35% 35%, #4a2e10, #180e04)", border: "2px solid rgba(120,80,20,0.45)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, position: "relative", boxShadow: "0 3px 10px rgba(0,0,0,0.5)" }}>
                  <div style={{ position: "absolute", top: 4, left: "50%", transform: "translateX(-50%)", width: 2, height: 10, background: "rgba(217,119,6,0.85)", borderRadius: 1 }} />
                  {emoji}
                </div>
                <div style={{ fontFamily: mono, fontSize: 10, letterSpacing: "0.16em", textTransform: "uppercase", color: "rgba(210,165,60,0.8)", marginBottom: 7, fontWeight: 600 }}>{name}</div>
                <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(190,155,90,0.55)", lineHeight: 1.7 }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ══ FEATURES ═════════════════════════════════════════════ */}
      <section id="features" className="lp-section" style={{ background: "#0f0904" }}>
        <div style={S.container}>
          <p style={S.label}>// Engine Capabilities</p>
          <h2 style={S.h2}>What makes it different</h2>
          <p style={S.body}>Not a playlist generator. An acoustic intelligence layer that maps language, mood, and context to sound.</p>
          <div className="feature-grid">
            {[
              { icon: "🧠", title: "Natural Language Analysis",   badge: "Core Engine",        desc: "Describe any moment in plain language. The AI extracts moods, semantic concepts, and audio attributes — including sensory metaphors — to build a matched pool." },
              { icon: "✨", title: "Gemini + Sentiment Layer",    badge: "Dual NLP",           desc: "Heuristic engine runs first. When confidence is low, Gemini Flash fires for deeper understanding. TextBlob sentiment analysis boosts study/focus intent and disambiguates emotional prompts." },
              { icon: "🔒", title: "Smart Artist Detection",      badge: "Artist Transparency", desc: "Mentions of artists auto-lock the pool. A banner tells you exactly what was detected, and a ✕ lets you dismiss it for pure vibe mode." },
              { icon: "🌐", title: "18 Languages",                badge: "Regional Music",     desc: "Deep routing for 10 Indian regional pools — Hindi, Punjabi, Tamil, Telugu, Marathi, Assamese and more — plus Korean, Arabic, Japanese, and Afrobeats." },
              { icon: "🎛️", title: "Pro Mode Overrides",          badge: "Power Users",        desc: "Force an artist, lock a genre, flip to secondary vibe, find artists similar to a reference, or lock strict discography mode." },
              { icon: "💾", title: "Playlists & Sharing",         badge: "Save & Share",       desc: "Save any result as a named playlist. Share it publicly with a single link — recipients see the full playlist with previews, no account needed." },
              { icon: "▶️", title: "Inline Previews + YouTube",   badge: "Full Playback",      desc: "Preview any track without leaving the app. Connect YouTube for full-length playback and playlist creation — no limits, free for everyone." },
              { icon: "🔬", title: "Neural Match Breakdown",      badge: "Transparency",       desc: "See the exact keywords the AI extracted — #late night #rain #dark chill — so you always know how your vibe was read." },
            ].map(({ icon, title, badge, desc }) => (
              <div key={title} className="lp-card" style={{ padding: "1.6rem 1.4rem", borderRadius: 0, border: "none", background: "linear-gradient(155deg, rgba(36,23,8,0.95), rgba(18,11,3,0.98))" }}>
                <div style={{ fontSize: 20, marginBottom: 10 }}>{icon}</div>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 600, fontSize: 14, color: "#ead9a8", marginBottom: 7 }}>{title}</div>
                <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(190,155,90,0.55)", lineHeight: 1.75, marginBottom: 12 }}>{desc}</div>
                <span className="freq-tag" style={{ color: "rgba(210,160,60,0.85)", borderColor: "rgba(180,120,40,0.35)" }}>{badge}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ══ RESULT PREVIEW ═══════════════════════════════════════ */}
      <section className="lp-section" style={{ background: "rgba(20,13,5,0.97)" }}>
        <div style={S.container}>
          <p style={S.label}>// Output Anatomy</p>
          <h2 style={S.h2}>What you get back</h2>
          <p style={S.body}>Not just a playlist — a full analysis with vibe data, genre tags, and a breakdown of how your prompt was interpreted.</p>

          <div className="lp-card" style={{ overflow: "hidden" }}>
            {/* Top bar */}
            <div style={{ borderBottom: "1px solid rgba(155,105,28,0.28)", padding: "11px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(5,3,1,0.5)" }}>
              <span style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.45)" }}>// Analysis Complete</span>
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#34d399", boxShadow: "0 0 5px #34d399", animation: "pulse 1.8s infinite" }} />
                <span style={{ fontFamily: mono, fontSize: 9, color: "#34d399", letterSpacing: "0.1em" }}>Live</span>
              </div>
            </div>

            {/* Artist detection banner */}
            <div style={{ margin: "12px 18px 0", display: "flex", alignItems: "flex-start", gap: 9, background: "rgba(217,119,6,0.06)", border: "1px solid rgba(217,119,6,0.2)", borderRadius: 6, padding: "9px 12px" }}>
              <span style={{ fontSize: 13, lineHeight: 1, marginTop: 1, flexShrink: 0 }}>🔒</span>
              <div>
                <span style={{ fontFamily: mono, fontSize: 10, color: amber, fontWeight: 600, letterSpacing: "0.04em" }}>Artist detected: Travis Scott</span>
                <br />
                <span style={{ fontFamily: mono, fontSize: 10, color: "rgba(190,155,90,0.55)", lineHeight: 1.6 }}>Not your intention? Tap ✕ on the tag below to unlock and re-run as a pure vibe search.</span>
              </div>
            </div>

            {/* Stat cards */}
            <div className="rp-stat-grid" style={{ gap: 1, background: "rgba(120,80,20,0.12)", margin: "12px 0 1px" }}>
              {[
                { label: "Dominant Vibe", value: "CHILL",   sub: "Secondary → Heartbreak", conf: 0.53 },
                { label: "Target Tempo",  value: "70–100",  sub: "BPM · Rhythmic Pulse",   bpm: true },
              ].map((c, i) => (
                <div key={i} style={{ background: "linear-gradient(155deg, rgba(40,26,10,0.95), rgba(20,12,3,0.98))", padding: "18px 20px" }}>
                  <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.22em", textTransform: "uppercase", color: "rgba(180,140,80,0.4)", marginBottom: 5 }}>{c.label}</div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
                    <span style={{ fontFamily: serif, fontSize: 26, fontWeight: 700, color: "#fde68a" }}>{c.value}</span>
                    {c.bpm && <span style={{ fontFamily: mono, fontSize: 12, color: "rgba(180,140,80,0.45)" }}>BPM</span>}
                  </div>
                  <div style={{ fontFamily: mono, fontSize: 10, color: "rgba(180,140,80,0.4)", marginTop: 2 }}>{c.sub}</div>
                  {c.conf && (
                    <div style={{ height: 4, borderRadius: 2, background: "rgba(80,50,10,0.4)", overflow: "hidden", marginTop: 9 }}>
                      <div style={{ height: "100%", width: `${c.conf * 100}%`, background: "linear-gradient(90deg, #92400e, #d97706, #fbbf24)", borderRadius: 2 }} />
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Genre tags row */}
            <div style={{ padding: "12px 18px", borderBottom: "1px solid rgba(120,80,20,0.18)", display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
              <span className="freq-tag" style={{ color: amber, borderColor: "rgba(217,119,6,0.4)", display: "inline-flex", alignItems: "center", gap: 5 }}>
                🔒 Travis Scott <span style={{ opacity: 0.7, cursor: "pointer" }}>✕</span>
              </span>
              {["Neo-Soul","Indie R&B","Chillwave","Lo-fi Hip Hop"].map(t => (
                <span key={t} className="freq-tag">{t}</span>
              ))}
            </div>

            {/* Track rows */}
            {[{ c: "#c8922a", t: "Neon Glow", a: "Artist · Album" }, { c: "#6366f1", t: "Midnight Signal", a: "Another Artist · EP" }].map((track, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 18px", borderBottom: "1px solid rgba(120,80,20,0.12)", background: i === 0 ? "rgba(217,119,6,0.03)" : "transparent", flexWrap: "wrap" }}>
                <div style={{ width: 38, height: 38, borderRadius: 6, flexShrink: 0, background: `conic-gradient(from 0deg, #1a1008, ${track.c}44, #1a1008)`, border: "1px solid rgba(180,140,80,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <div style={{ width: 9, height: 9, borderRadius: "50%", background: `radial-gradient(circle, ${track.c}, #7a4f12)` }} />
                </div>
                <div style={{ flex: 1, minWidth: 100 }}>
                  <div style={{ fontFamily: serif, fontSize: 14, fontWeight: 700, color: "#fde68a" }}>{track.t}</div>
                  <div style={{ fontFamily: mono, fontSize: 10, color: "rgba(180,140,80,0.55)", marginTop: 2 }}>{track.a}</div>
                </div>
                <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                  {["👍","👎","▶"].map(act => (
                    <button key={act} style={{ background: "rgba(14,9,3,0.6)", border: "1px solid rgba(155,105,28,0.35)", borderRadius: 6, padding: "6px 10px", fontFamily: mono, fontSize: 10, color: "rgba(180,140,80,0.5)", cursor: "pointer", minHeight: 36 }}>{act}</button>
                  ))}
                  <button style={{ background: "rgba(14,9,3,0.6)", border: "1px solid rgba(255,0,0,0.3)", borderRadius: 6, padding: "6px 10px", fontFamily: mono, fontSize: 10, color: "#ff6666", cursor: "pointer", minHeight: 36 }}>YouTube</button>
                </div>
              </div>
            ))}
            <div style={{ padding: "9px 18px", fontFamily: mono, fontSize: 10, color: "rgba(120,80,20,0.6)" }}>
              Neural Match → <span style={{ color: "rgba(190,155,90,0.5)", marginLeft: 6 }}>#late night &nbsp; #rain &nbsp; #travis scott &nbsp; #dark chill</span>
            </div>
            <div style={{ padding: "9px 18px 13px", borderTop: "1px solid rgba(120,80,20,0.12)", display: "flex", gap: 7, alignItems: "center", flexWrap: "wrap" }}>
              <button style={{ background: "rgba(14,9,3,0.6)", border: "1px solid rgba(217,119,6,0.35)", borderRadius: 6, padding: "6px 12px", fontFamily: mono, fontSize: 10, color: "rgba(217,119,6,0.75)", cursor: "pointer", letterSpacing: "0.06em", minHeight: 36 }}>💾 Save Playlist</button>
              <button style={{ background: "rgba(14,9,3,0.6)", border: "1px solid rgba(155,105,28,0.3)", borderRadius: 6, padding: "6px 12px", fontFamily: mono, fontSize: 10, color: "rgba(180,140,80,0.5)", cursor: "pointer", letterSpacing: "0.06em", minHeight: 36 }}>🔗 Share Link</button>
              <span style={{ fontFamily: mono, fontSize: 9, color: "rgba(120,80,20,0.45)", marginLeft: 2 }}>Public · No login required to view</span>
            </div>
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ══ PRO MODE ═════════════════════════════════════════════ */}
      <section className="lp-section" style={{ background: "#0f0904" }}>
        <div style={S.container}>
          <p style={S.label}>// Advanced Controls</p>
          <h2 style={S.h2}>Pro Mode overrides</h2>
          <p style={S.body}>For when you want full manual control on top of AI vibe matching. Expand the Pro Mode panel after any analysis.</p>

          {/* Mobile toggle — hidden on desktop via CSS */}
          <button
            className="pro-toggle"
            onClick={() => setProExpanded(p => !p)}
          >
            <span>{proExpanded ? "Hide overrides" : "Show overrides"}</span>
            <span style={{ fontSize: 16, lineHeight: 1 }}>{proExpanded ? "▲" : "▼"}</span>
          </button>

          {/* Cards — always visible on desktop, toggled on mobile */}
          <div className="pro-grid" style={{ display: undefined }}>
            <style>{`
              @media (max-width: 600px) {
                .pro-grid { display: ${proExpanded ? "grid" : "none"} !important; }
              }
            `}</style>
            {[
              { icon: "⚡", title: "Force Artist Bypass",     desc: "Lock all results to a specific artist's discography — type \"Deftones\" and every track comes from that sonic world." },
              { icon: "🎛️", title: "Force Genre Bypass",      desc: "Override AI genre inference entirely — type \"psytrance\", \"bhangra\", \"drum and bass\" — bypasses vibe detection. Tags update to match." },
              { icon: "🔄", title: "Flip Secondary Vibe",     desc: "When the AI detects two overlapping moods, toggle to force the secondary vibe as your main result — useful when the dominant pick was off." },
              { icon: "🔍", title: "Similar to Artist",       desc: "Seed the pool from an artist's sonic neighbourhood — ListenBrainz similar-artist data builds the pool without a cold API call." },
              { icon: "🔐", title: "Lock Artist Mode",        desc: "When an artist override is set, toggle Lock to get strict discography only — no vibe-pool mixing, just that artist's tracks." },
            ].map(card => (
              <div key={card.title} className="lp-card" style={{ padding: "1.3rem 1.2rem", borderLeft: "3px solid rgba(217,119,6,0.5)" }}>
                <div style={{ fontFamily: mono, fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "rgba(210,160,60,0.8)", marginBottom: 9 }}>{card.icon} {card.title}</div>
                <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(190,155,90,0.55)", lineHeight: 1.75 }}>{card.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ══ LANGUAGES ════════════════════════════════════════════ */}
      <section id="languages" className="lp-section" style={{ background: "rgba(20,13,5,0.97)" }}>
        <div style={S.container}>
          <p style={S.label}>// Language Routing</p>
          <h2 style={S.h2}>18 languages, native pools</h2>
          <p style={S.body}>Language isn't a filter here — it's a routing signal. Each language maps to its own tag pool, so a Hindi heartbreak prompt returns Bollywood sad songs, not western indie pop.</p>

          <div style={{ marginBottom: "1rem" }}>
            <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 8 }}>Indian Regional</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
              {["Hindi","Punjabi","Tamil","Telugu","Kannada","Malayalam","Bengali","Urdu"].map(l => (
                <span key={l} className="freq-tag" style={{ color: amber, borderColor: "rgba(217,119,6,0.38)", background: "rgba(100,50,8,0.2)" }}>{l}</span>
              ))}
              {["Marathi","Assamese"].map(l => (
                <span key={l} className="freq-tag" style={{ color: "#34d399", borderColor: "rgba(52,211,153,0.3)", background: "rgba(5,40,25,0.2)" }}>
                  {l} <span style={{ fontSize: 8, opacity: 0.8 }}>new</span>
                </span>
              ))}
            </div>
          </div>

          <div>
            <div style={{ fontFamily: mono, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", color: "rgba(180,140,80,0.35)", marginBottom: 8 }}>Global</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
              {["English","Korean","Japanese","Spanish","Portuguese","French","Arabic","Afrobeats"].map(l => (
                <span key={l} className="freq-tag">{l}</span>
              ))}
            </div>
          </div>

          <div style={{ marginTop: "1.6rem", fontFamily: mono, fontSize: 12, color: "rgba(190,155,90,0.55)", borderLeft: "2px solid rgba(217,119,6,0.4)", paddingLeft: 13, lineHeight: 1.85 }}>
            South Asian music discovery is a first-class use case. Bollywood sadness, bhangra energy, Navratri garba,
            late-night ghazal, Carnatic fusion, KGF mass BGM — every mood routes to the right native pool.
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ══ USE CASES ════════════════════════════════════════════ */}
      <section id="use-cases" className="lp-section" style={{ background: "#0f0904" }}>
        <div style={S.container}>
          <p style={S.label}>// Scenarios</p>
          <h2 style={S.h2}>What people use it for</h2>
          <p style={S.body}>Anything with a feeling that doesn't map neatly to a genre.</p>
          <div className="usecase-grid">
            {[
              { e: "🌧️", t: "Mood-based listening",    d: "Feel something but don't know what song fits. Describe the feeling and let the AI find it.", q: "sad and numb but kinda okay, november rain, slow indie, no lyrics please" },
              { e: "💻", t: "Study & focus sessions",   d: "Sentiment analysis detects study intent and routes to lo-fi, chillhop, and instrumental pools — not random dark tracks.", q: "late night study session, soft background, no distractions, lo-fi chill" },
              { e: "🎸", t: "Artist-led discovery",     d: "Mention a reference artist and crank Nicheness for lesser-known gems in that sonic zone.", q: "sounds like Cigarettes After Sex, hushed and aching, dark romance" },
              { e: "🪘", t: "Desi & regional moods",    d: "Bollywood, Punjabi, Tamil kuthu, Carnatic, ghazal — all natively routed.", q: "sufi night, rooftop, Nusrat Fateh Ali Khan energy, chai" },
              { e: "🎉", t: "Events & parties",         d: "Shaadi, sangeet, garba, birthday — describe the occasion and energy.", q: "Navratri garba remix, tabla meets EDM, spiritual but hype" },
              { e: "🌅", t: "Cinematic & scene vibes",  d: "Describe a visual or scene. Indian language prompts route to native BGM pools, not western orchestral.", q: "KGF Rocky Bhai energy, power walk moment, mass BGM" },
            ].map(({ e, t, d, q }) => (
              <div key={t} className="lp-card" style={{ padding: "1.4rem 1.3rem" }}>
                <div style={{ fontSize: 20, marginBottom: 9 }}>{e}</div>
                <div style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 600, fontSize: 14, color: "#ead9a8", marginBottom: 7 }}>{t}</div>
                <div style={{ fontFamily: mono, fontSize: 11, color: "rgba(190,155,90,0.55)", lineHeight: 1.7, marginBottom: 11 }}>{d}</div>
                <div style={{ padding: "8px 11px", background: "rgba(8,5,1,0.7)", borderLeft: "2px solid rgba(217,119,6,0.4)", borderRadius: "0 6px 6px 0", fontFamily: mono, fontStyle: "italic", fontSize: 10, color: "rgba(190,155,90,0.45)", lineHeight: 1.6 }}>"{q}"</div>
                <button
                  onClick={launch}
                  style={{ marginTop: 12, width: "100%", padding: "10px 14px", background: "rgba(20,12,4,0.8)", border: "1px solid rgba(155,105,28,0.3)", borderRadius: 8, fontFamily: mono, fontSize: 10, color: "rgba(210,160,60,0.7)", cursor: "pointer", letterSpacing: "0.08em", textTransform: "uppercase", transition: "border-color .2s, color .2s", minHeight: 40 }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(217,119,6,0.5)"; e.currentTarget.style.color = "#fde68a"; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(155,105,28,0.3)"; e.currentTarget.style.color = "rgba(210,160,60,0.7)"; }}
                >Try this prompt →</button>
              </div>
            ))}
          </div>
        </div>
      </section>
      <hr style={S.divider} />

      {/* ══ FINAL CTA ════════════════════════════════════════════ */}
      <section className="lp-section" style={{ background: "rgba(10,6,2,0.98)", textAlign: "center", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", fontFamily: serif, fontSize: "clamp(50px,11vw,120px)", color: "rgba(100,50,8,0.04)", fontWeight: 900, top: "50%", left: "50%", transform: "translate(-50%,-50%)", whiteSpace: "nowrap", pointerEvents: "none", userSelect: "none" }}>VibeFinderAI</div>
        <div style={{ position: "relative", zIndex: 1 }}>
          <p style={S.label}>// Ready?</p>
          <h2 style={{ fontFamily: serif, fontSize: "clamp(1.5rem,4vw,2.6rem)", fontWeight: 900, color: "#ead9a8", marginBottom: "0.9rem", lineHeight: 1.2 }}>
            Stop searching.<br /><span style={{ fontStyle: "italic", color: "#fde68a" }}>Start describing.</span>
          </h2>
          <p style={{ fontFamily: mono, fontSize: 13, color: "rgba(190,155,90,0.55)", maxWidth: 420, margin: "0 auto 2.2rem", lineHeight: 1.85 }}>
            Type a feeling. The engine handles the rest.<br />Free to use · Sign up to save & share playlists.
          </p>
          <button
            onClick={launch}
            className="lp-cta-btn"
            style={{ ...amberBtn, padding: "15px 40px", fontSize: 13, letterSpacing: "0.18em", minHeight: 52 }}
            onMouseEnter={e => { e.currentTarget.style.opacity = ".86"; e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 30px rgba(180,100,10,0.5)"; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = "1";   e.currentTarget.style.transform = "none"; e.currentTarget.style.boxShadow = "0 4px 18px rgba(180,100,10,0.3)"; }}
          >⚡ Launch VibeFinderAI →</button>
        </div>
      </section>

      {/* ══ FOOTER ═══════════════════════════════════════════════ */}
      <footer style={{ borderTop: "1px solid rgba(155,105,28,0.28)", padding: "1.4rem 1.4rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, fontFamily: mono, fontSize: 11, color: "rgba(120,80,20,0.55)", background: "#0a0602" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <div style={{ width: 20, height: 20, borderRadius: "50%", background: "conic-gradient(from 0deg, #1a1008, #3d2510, #1a1008)", border: "1px solid rgba(180,140,80,0.25)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "radial-gradient(circle, #d97706, #7a4f12)" }} />
          </div>
          <span style={{ fontFamily: serif, fontSize: 12, color: "#ead9a8", letterSpacing: "-0.01em" }}>VibeFinderAI</span>
        </div>
        <span>Phase 8 · 18 Languages · Last.fm + YouTube + Gemini</span>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          {[["App", launch], ["How It Works", () => scrollTo("how-it-works")], ["Features", () => scrollTo("features")]].map(([label, fn]) => (
            <button key={label} onClick={fn} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(120,80,20,0.55)", fontFamily: mono, fontSize: 11, letterSpacing: "0.06em", minHeight: 40, padding: "0 4px" }}
              onMouseEnter={e => e.target.style.color = "rgba(190,155,90,0.7)"}
              onMouseLeave={e => e.target.style.color = "rgba(120,80,20,0.55)"}
            >{label}</button>
          ))}
        </div>
      </footer>
    </>
  );
}
