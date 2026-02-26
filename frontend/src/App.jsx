import { useState, useEffect, useRef } from "react";

/* ─── SVG ICONS ─────────────────────────────────────────────── */
const IconLock    = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>;
const IconUnlock  = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>;
const IconPlay    = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>;
const IconUser    = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
const IconMail    = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>;
const IconX       = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>;
const IconWave    = () => <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>;

/* ─── WAVEFORM VISUALISER (pure CSS bars) ────────────────────── */
function WaveformBars({ active, count = 28 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "3px", height: "32px" }}>
      {Array.from({ length: count }).map((_, i) => {
        const h = active ? Math.random() * 28 + 4 : 8;
        const delay = (i * 40) % 700;
        return (
          <div
            key={i}
            style={{
              width: "3px",
              height: active ? undefined : "8px",
              minHeight: "4px",
              maxHeight: "32px",
              borderRadius: "2px",
              background: active
                ? `hsl(${38 + i * 1.2}, 80%, ${48 + (i % 4) * 5}%)`
                : "rgba(180,140,80,0.25)",
              animationName: active ? "barDance" : "none",
              animationDuration: `${350 + (i % 7) * 80}ms`,
              animationDelay: `${delay}ms`,
              animationTimingFunction: "ease-in-out",
              animationIterationCount: "infinite",
              animationDirection: "alternate",
            }}
          />
        );
      })}
      <style>{`
        @keyframes barDance {
          from { height: 4px; }
          to   { height: 30px; }
        }
      `}</style>
    </div>
  );
}

/* ─── VU METER ───────────────────────────────────────────────── */
function VuMeter({ value = 0 }) {
  const segments = 14;
  const lit = Math.round(value * segments);
  return (
    <div style={{ display: "flex", gap: "2px", alignItems: "flex-end" }}>
      {Array.from({ length: segments }).map((_, i) => {
        const isLit = i < lit;
        const isRed = i >= 11;
        const isYellow = i >= 8 && i < 11;
        return (
          <div key={i} style={{
            width: "6px",
            height: `${10 + i * 1.5}px`,
            borderRadius: "2px",
            background: isLit
              ? isRed ? "#ef4444" : isYellow ? "#f59e0b" : "#d97706"
              : "rgba(120,80,20,0.2)",
            boxShadow: isLit && !isRed ? "0 0 6px rgba(217,119,6,0.6)" : isLit ? "0 0 6px rgba(239,68,68,0.6)" : "none",
            transition: "background 0.1s, box-shadow 0.1s",
          }} />
        );
      })}
    </div>
  );
}

/* ─── OSCILLOSCOPE CANVAS ────────────────────────────────────── */
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
          ? H / 2 + Math.sin((x / W) * Math.PI * 4 + t * 0.05) * 14
            + Math.sin((x / W) * Math.PI * 9 + t * 0.08) * 6
            + Math.sin((x / W) * Math.PI * 17 + t * 0.03) * 3
          : H / 2 + Math.sin((x / W) * Math.PI * 2) * 3;
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
    <div title="Neural Waveform Monitor (Visual Only)" style={{
      background: "rgba(8,5,2,0.8)",
      border: "1px solid rgba(120,80,20,0.4)",
      borderRadius: "8px",
      padding: "6px 10px",
      display: "flex",
      alignItems: "center",
      gap: "8px",
      cursor: "help" // UX Improvement
    }}>
      <span style={{ fontSize: "9px", fontFamily: "monospace", color: "rgba(180,140,80,0.5)", letterSpacing: "0.1em", textTransform: "uppercase" }}>OSC</span>
      <canvas ref={canvasRef} width={180} height={36} style={{ display: "block" }} />
    </div>
  );
}

/* ─── VINYL SPINNER ──────────────────────────────────────────── */
function Vinyl({ spinning, labelColor = "#c8922a" }) {
  return (
    <div style={{
      width: "52px", height: "52px", borderRadius: "50%",
      background: "conic-gradient(from 0deg, #1a1008, #2e1f0d, #1a1008, #2e1f0d, #1a1008, #2e1f0d, #1a1008, #2e1f0d)",
      boxShadow: "0 0 0 2px rgba(180,140,80,0.3), 0 4px 16px rgba(0,0,0,0.7)",
      position: "relative", flexShrink: 0,
      animationName: spinning ? "spin" : "none",
      animationDuration: "2.4s",
      animationTimingFunction: "linear",
      animationIterationCount: "infinite",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        width: "14px", height: "14px", borderRadius: "50%",
        background: `radial-gradient(circle, ${labelColor} 40%, #7a4f12 100%)`,
        boxShadow: `0 0 6px ${labelColor}88`,
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

/* ─── CONFIDENCE METER ───────────────────────────────────────── */
function ConfidenceMeter({ value, vibeColor = "#d97706" }) {
  return (
    <div style={{ width: "100%" }}>
      <div style={{
        height: "6px", borderRadius: "3px",
        background: "rgba(80,50,10,0.4)",
        overflow: "hidden", marginTop: "12px",
        boxShadow: "inset 0 1px 3px rgba(0,0,0,0.5)",
      }}>
        <div style={{
          height: "100%",
          width: `${value * 100}%`,
          background: `linear-gradient(90deg, #92400e, ${vibeColor}, #fbbf24)`,
          borderRadius: "3px",
          boxShadow: `0 0 10px ${vibeColor}88`,
          transition: "width 1.2s cubic-bezier(0.23,1,0.32,1)",
        }} />
      </div>
    </div>
  );
}

/* ─── INPUT FIELD ────────────────────────────────────────────── */
function AudioInput({ icon, ...props }) {
  return (
    <div style={{ position: "relative" }}>
      <div style={{
        position: "absolute", top: "50%", left: "14px",
        transform: "translateY(-50%)",
        color: "rgba(180,140,80,0.5)", pointerEvents: "none",
      }}>
        {icon}
      </div>
      <input
        {...props}
        style={{
          width: "100%", boxSizing: "border-box",
          background: "rgba(8,5,2,0.7)",
          border: "1px solid rgba(120,80,20,0.4)",
          borderRadius: "8px",
          padding: "10px 14px 10px 40px",
          color: "#e8d5a3",
          fontFamily: "'DM Mono', 'Fira Code', monospace",
          fontSize: "13px",
          outline: "none",
          transition: "border-color 0.2s, box-shadow 0.2s",
        }}
        onFocus={e => {
          e.target.style.borderColor = "rgba(217,119,6,0.7)";
          e.target.style.boxShadow = "0 0 0 2px rgba(217,119,6,0.15)";
        }}
        onBlur={e => {
          e.target.style.borderColor = "rgba(120,80,20,0.4)";
          e.target.style.boxShadow = "none";
        }}
      />
    </div>
  );
}

/* ─── GLOBAL STYLES INJECTOR ─────────────────────────────────── */
function GlobalStyles() {
  return (
    <style>{`
      @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Cormorant+Garamond:wght@400;600&display=swap');

      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
      html { scroll-behavior: smooth; }

      body {
        background: #0a0602;
        background-image:
          radial-gradient(ellipse 80% 60% at 50% -10%, rgba(120,60,10,0.18) 0%, transparent 70%),
          url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
        min-height: 100vh;
        color: #e8d5a3;
        font-family: 'DM Mono', monospace;
      }

      ::selection { background: rgba(217,119,6,0.25); color: #fde68a; }

      input::placeholder { color: rgba(180,140,80,0.25); }
      textarea::placeholder { color: rgba(180,140,80,0.25); }
      textarea { resize: none; }

      .dial-btn {
        cursor: pointer;
        transition: transform 0.12s, box-shadow 0.12s;
        border: none;
        outline: none;
      }
      .dial-btn:hover  { transform: scale(1.04); }
      .dial-btn:active { transform: scale(0.97); }

      .panel-card {
        background: linear-gradient(160deg, rgba(28,18,6,0.9) 0%, rgba(14,9,3,0.95) 100%);
        border: 1px solid rgba(120,80,20,0.35);
        border-radius: 16px;
        position: relative;
        overflow: hidden;
      }
      .panel-card::before {
        content: '';
        position: absolute; inset: 0;
        background: linear-gradient(135deg, rgba(255,200,80,0.03) 0%, transparent 50%);
        pointer-events: none;
        border-radius: inherit;
      }

      .screws::before, .screws::after {
        content: '';
        position: absolute;
        width: 8px; height: 8px;
        border-radius: 50%;
        background: radial-gradient(circle, #4a3010 40%, #1a0e04 100%);
        border: 1px solid rgba(120,80,20,0.4);
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.8);
        z-index: 1;
      }
      .screws::before { top: 10px; left: 10px; }
      .screws::after  { top: 10px; right: 10px; }

      @keyframes fadeSlide {
        from { opacity: 0; transform: translateY(18px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      .animate-in { animation: fadeSlide 0.5s ease forwards; }

      @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 4px rgba(217,119,6,0.4); }
        50%       { box-shadow: 0 0 12px rgba(217,119,6,0.8); }
      }
      .pulsing { animation: pulse-glow 1.8s ease-in-out infinite; }

      .knob {
        width: 36px; height: 36px; border-radius: 50%;
        background: radial-gradient(circle at 35% 35%, #5a3a18, #1a0e04);
        border: 2px solid rgba(120,80,20,0.5);
        box-shadow: 0 3px 8px rgba(0,0,0,0.6), inset 0 1px 2px rgba(255,200,80,0.1);
        position: relative; cursor: help; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
      }
      .knob::after {
        content: '';
        width: 2px; height: 10px;
        background: rgba(217,119,6,0.9);
        border-radius: 1px;
        position: absolute; top: 4px;
        box-shadow: 0 0 4px rgba(217,119,6,0.6);
      }

      .freq-tag {
        padding: 4px 10px;
        background: rgba(120,60,10,0.2);
        border: 1px solid rgba(180,120,40,0.25);
        border-radius: 20px;
        font-size: 11px;
        font-family: 'DM Mono', monospace;
        letter-spacing: 0.08em;
        color: rgba(217,160,60,0.8);
        text-transform: uppercase;
      }
    `}</style>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN APP
═══════════════════════════════════════════════════════════════ */
export default function App() {
  const [token, setToken]             = useState(null);
  const [prompt, setPrompt]           = useState("");
  const [result, setResult]           = useState(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isLoginView, setIsLoginView] = useState(true);
  const [authForm, setAuthForm]       = useState({ email: "", username: "", password: "" });
  const [vuLevel, setVuLevel]         = useState(0);
  const vuRef = useRef(null);

  // Expanded Vibe Colors to match backend UI overhaul
  const vibeColors = {
    hype: '#f87171',
    calm: '#34d399',
    intense: '#f97316',
    chill: '#60a5fa',
    focus: '#22d3ee',
    euphoric: '#e879f9',
    soulful: '#fbbf24',
    retro: '#818cf8',
    dreamy: '#c084fc',
    cinematic: '#fb923c', 
    dark: '#9ca3af',      
    heartbreak: '#f472b6', 
    hyperpop: '#d946ef',  
    party: '#ec4899',     
    country: '#d97706',   
    tropical: '#14b8a6',  
    industrial: '#6b7280',
    desi: '#e11d48', // Strong rose/red for Bollywood energy     
    neutral: '#d97706'
  };

  const activeColor = result ? (vibeColors[result.dominant_vibe] || vibeColors.neutral) : vibeColors.neutral;

  /* Animate VU meter while loading */
  useEffect(() => {
    if (loading) {
      vuRef.current = setInterval(() => {
        setVuLevel(0.3 + Math.random() * 0.65);
      }, 120);
    } else {
      clearInterval(vuRef.current);
      setVuLevel(result ? result.confidence : 0);
    }
    return () => clearInterval(vuRef.current);
  }, [loading, result]);

  const handleAuthChange = (e) => setAuthForm({ ...authForm, [e.target.name]: e.target.value });

  const submitAuth = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      if (!isLoginView) {
        const regRes = await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: authForm.email, username: authForm.username, password: authForm.password }),
        });
        if (!regRes.ok) { const d = await regRes.json(); throw new Error(d.detail || "Registration failed"); }
      }
      const fd = new URLSearchParams();
      fd.append("username", authForm.username); fd.append("password", authForm.password);
      const logRes = await fetch("/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: fd,
      });
      if (!logRes.ok) throw new Error("Authentication failed — check credentials");
      const data = await logRes.json();
      setToken(data.access_token);
      setShowAuthModal(false);
      setAuthForm({ email: "", username: "", password: "" });
      setIsLoginView(true);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const handleLogout = () => { setToken(null); setResult(null); setPrompt(""); setVuLevel(0); };

  const analyzeVibe = async () => {
    if (!prompt.trim()) return;
    try {
      setLoading(true); setError("");
      const res = await fetch("/api/vibe/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ text: prompt }),
      });
      if (res.status === 401) { handleLogout(); throw new Error("Session expired — re-authenticate"); }
      if (!res.ok) throw new Error("Analysis failed");
      const data = await res.json();
      setResult(data);
      
      // Auto-scroll to results for better UX
      setTimeout(() => {
        document.getElementById('results-section')?.scrollIntoView({ behavior: 'smooth' });
      }, 150);

    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  /* ── STYLES (inline for portability) ── */
  const S = {
    root: {
      minHeight: "100vh",
      padding: "24px 16px 60px",
      fontFamily: "'DM Mono', monospace",
    },
    inner: { maxWidth: "860px", margin: "0 auto" },

    /* Header */
    header: {
      display: "flex", alignItems: "center", justifyContent: "space-between",
      paddingBottom: "24px",
      borderBottom: "1px solid rgba(120,80,20,0.3)",
      marginBottom: "32px",
    },
    logoWrap: { display: "flex", alignItems: "center", gap: "14px" },
    logoDisc: {
      width: "42px", height: "42px", borderRadius: "50%",
      background: "conic-gradient(from 0deg, #1a1008, #3d2510, #1a1008, #2e1a0a, #1a1008)",
      border: "2px solid rgba(180,140,80,0.4)",
      boxShadow: `0 0 18px ${activeColor}44, inset 0 0 10px rgba(0,0,0,0.5)`,
      display: "flex", alignItems: "center", justifyContent: "center",
      flexShrink: 0,
      transition: "box-shadow 0.5s ease"
    },
    logoDiscInner: {
      width: "10px", height: "10px", borderRadius: "50%",
      background: `radial-gradient(circle, ${activeColor}, #7a4f12)`,
      transition: "background 0.5s ease"
    },
    logoText: {
      fontFamily: "'Playfair Display', serif",
      fontSize: "22px", fontWeight: 900,
      color: "#e8d5a3",
      letterSpacing: "-0.01em",
      lineHeight: 1.1,
    },
    logoSub: {
      fontSize: "10px",
      fontFamily: "'DM Mono', monospace",
      color: "rgba(180,140,80,0.5)",
      letterSpacing: "0.25em",
      textTransform: "uppercase",
    },

    /* Auth btn */
    authBtn: (hasToken) => ({
      display: "flex", alignItems: "center", gap: "8px",
      padding: "8px 18px",
      borderRadius: "8px",
      fontFamily: "'DM Mono', monospace",
      fontSize: "12px",
      fontWeight: 500,
      letterSpacing: "0.08em",
      textTransform: "uppercase",
      cursor: "pointer",
      transition: "all 0.2s",
      background: hasToken ? "rgba(40,20,5,0.8)" : "linear-gradient(135deg, #92400e, #d97706)",
      color: hasToken ? "rgba(180,140,80,0.7)" : "#fef3c7",
      border: hasToken ? "1px solid rgba(120,80,20,0.4)" : "1px solid rgba(251,191,36,0.3)",
      boxShadow: hasToken ? "none" : "0 0 20px rgba(217,119,6,0.25)",
    }),

    /* Signal status */
    signalRow: { display: "flex", alignItems: "center", gap: "20px", flexWrap: "wrap" },
    signalDot: (on) => ({
      width: "7px", height: "7px", borderRadius: "50%",
      background: on ? activeColor : "rgba(80,50,10,0.5)",
      boxShadow: on ? `0 0 8px ${activeColor}` : "none",
      flexShrink: 0,
      transition: "background 0.3s, box-shadow 0.3s"
    }),
    signalLabel: { fontSize: "10px", letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.5)" },

    /* Error */
    errorBox: {
      display: "flex", alignItems: "center", gap: "10px",
      padding: "12px 16px",
      background: "rgba(60,10,10,0.5)",
      border: "1px solid rgba(180,40,40,0.3)",
      borderRadius: "10px",
      color: "#f87171",
      fontSize: "12px",
      marginBottom: "20px",
    },

    /* Textarea */
    textareaWrap: { position: "relative" },
    textarea: {
      width: "100%",
      height: "130px",
      background: "rgba(5,3,1,0.8)",
      border: "1px solid rgba(120,80,20,0.35)",
      borderRadius: "10px",
      padding: "16px",
      color: "#e8d5a3",
      fontFamily: "'DM Mono', monospace",
      fontSize: "14px",
      lineHeight: "1.6",
      outline: "none",
      transition: "border-color 0.2s, box-shadow 0.2s",
    },
    lockOverlay: {
      position: "absolute", inset: 0,
      background: "rgba(5,3,1,0.75)",
      backdropFilter: "blur(4px)",
      borderRadius: "10px",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 10,
    },
    lockBtn: {
      display: "flex", alignItems: "center", gap: "8px",
      padding: "10px 22px",
      background: "rgba(20,12,4,0.9)",
      border: "1px solid rgba(180,120,40,0.35)",
      borderRadius: "30px",
      color: "rgba(180,140,80,0.8)",
      fontSize: "12px",
      cursor: "pointer",
      letterSpacing: "0.1em",
      textTransform: "uppercase",
      fontFamily: "'DM Mono', monospace",
      transition: "border-color 0.2s, color 0.2s",
    },

    /* Run btn */
    runBtn: (disabled) => ({
      display: "flex", alignItems: "center", gap: "10px",
      padding: "12px 28px",
      background: disabled
        ? "rgba(50,30,8,0.4)"
        : "linear-gradient(135deg, #92400e 0%, #b45309 50%, #d97706 100%)",
      border: "1px solid " + (disabled ? "rgba(80,50,10,0.3)" : "rgba(251,191,36,0.3)"),
      borderRadius: "10px",
      color: disabled ? "rgba(120,80,20,0.5)" : "#fef3c7",
      fontFamily: "'DM Mono', monospace",
      fontSize: "12px",
      fontWeight: 500,
      letterSpacing: "0.15em",
      textTransform: "uppercase",
      cursor: disabled ? "not-allowed" : "pointer",
      boxShadow: disabled ? "none" : `0 4px 20px ${activeColor}44`,
      transition: "all 0.2s",
    }),

    /* Result cards */
    grid: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
      gap: "16px",
    },
    resultCard: {
      padding: "24px",
      display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center",
      gap: "8px",
    },
    cardLabel: { fontSize: "10px", letterSpacing: "0.25em", textTransform: "uppercase", color: "rgba(180,140,80,0.45)" },
    cardValue: {
      fontFamily: "'Playfair Display', serif",
      fontSize: "30px", fontWeight: 700,
      color: "#fde68a",
      textShadow: `0 0 20px ${activeColor}44`,
    },
    cardSub: { fontSize: "11px", color: "rgba(180,140,80,0.5)", letterSpacing: "0.1em" },

    /* Modal */
    modalOverlay: {
      position: "fixed", inset: 0, zIndex: 50,
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "16px",
      background: "rgba(4,2,1,0.88)",
      backdropFilter: "blur(8px)",
    },
    modal: {
      width: "100%", maxWidth: "420px",
      padding: "36px 32px 28px",
      position: "relative",
    },
    modalTitle: {
      fontFamily: "'Playfair Display', serif",
      fontSize: "24px", fontWeight: 900,
      color: "#fde68a",
      marginBottom: "8px",
    },
    modalSub: { fontSize: "11px", color: "rgba(180,140,80,0.45)", letterSpacing: "0.1em", marginBottom: "28px" },
    formLabel: { fontSize: "10px", letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.5)", marginBottom: "6px", display: "block" },
    submitBtn: {
      width: "100%", padding: "12px",
      marginTop: "24px",
      background: "linear-gradient(135deg, #92400e, #d97706)",
      border: "1px solid rgba(251,191,36,0.25)",
      borderRadius: "8px",
      color: "#fef3c7",
      fontFamily: "'DM Mono', monospace",
      fontSize: "12px",
      fontWeight: 500,
      letterSpacing: "0.18em",
      textTransform: "uppercase",
      cursor: "pointer",
      boxShadow: "0 4px 20px rgba(180,100,10,0.3)",
      transition: "opacity 0.2s",
    },
  };

  return (
    <>
      <GlobalStyles />
      <div style={S.root}>

        {/* ── AUTH MODAL ─────────────────────────────────────── */}
        {showAuthModal && (
          <div style={S.modalOverlay}>
            <div className="panel-card screws animate-in" style={S.modal}>
              <button
                onClick={() => setShowAuthModal(false)}
                style={{ position: "absolute", top: "16px", right: "16px", background: "none", border: "none", color: "rgba(180,140,80,0.4)", cursor: "pointer" }}
              >
                <IconX />
              </button>

              {/* decorative groove lines */}
              <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 5px, rgba(120,80,20,0.04) 5px, rgba(120,80,20,0.04) 6px)", borderRadius: "16px", pointerEvents: "none" }} />

              <div style={{ position: "relative" }}>
                <p style={S.modalTitle}>{isLoginView ? "Signal Authenticated" : "New Listener"}</p>
                <p style={S.modalSub}>{isLoginView ? "// ACCESS CONTROL SYSTEM" : "// REGISTER NEW ACCOUNT"}</p>

                {error && (
                  <div style={{ ...S.errorBox, marginBottom: "20px" }}>
                    <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#ef4444", flexShrink: 0 }} />
                    {error}
                  </div>
                )}

                <form onSubmit={submitAuth} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                  {!isLoginView && (
                    <div>
                      <label style={S.formLabel}>Email Address</label>
                      <AudioInput icon={<IconMail />} type="email" name="email" value={authForm.email} onChange={handleAuthChange} required placeholder="listener@analog.audio" />
                    </div>
                  )}
                  <div>
                    <label style={S.formLabel}>Username</label>
                    <AudioInput icon={<IconUser />} type="text" name="username" value={authForm.username} onChange={handleAuthChange} required placeholder="audiophile_001" />
                  </div>
                  <div>
                    <label style={S.formLabel}>Passphrase</label>
                    <AudioInput icon={<IconLock />} type="password" name="password" value={authForm.password} onChange={handleAuthChange} required placeholder="••••••••••••" />
                  </div>
                  <button type="submit" disabled={loading} className="dial-btn" style={{ ...S.submitBtn, opacity: loading ? 0.5 : 1 }}>
                    {loading ? "Handshaking..." : isLoginView ? "Authenticate" : "Initialize Account"}
                  </button>
                </form>

                <p style={{ textAlign: "center", marginTop: "18px", fontSize: "11px", color: "rgba(180,140,80,0.4)", letterSpacing: "0.05em" }}>
                  {isLoginView ? "No account? " : "Have access? "}
                  <button
                    type="button"
                    onClick={() => { setIsLoginView(!isLoginView); setError(""); setAuthForm({ email: "", username: "", password: "" }); }}
                    style={{ background: "none", border: "none", color: "#d97706", cursor: "pointer", fontFamily: "'DM Mono', monospace", fontSize: "11px" }}
                  >
                    {isLoginView ? "Register" : "Sign in"}
                  </button>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── INNER LAYOUT ───────────────────────────────────── */}
        <div style={S.inner}>

          {/* ── HEADER ─── */}
          <header style={S.header}>
            <div style={S.logoWrap}>
              <div style={S.logoDisc}><div style={S.logoDiscInner} /></div>
              <div>
                <div style={S.logoText}>VibeFinder</div>
                <div style={S.logoSub}>Acoustic Intelligence Engine</div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
              <Oscilloscope active={loading} />
              <button
                onClick={token ? handleLogout : () => setShowAuthModal(true)}
                className="dial-btn"
                style={S.authBtn(!!token)}
              >
                {token ? <IconUnlock /> : <IconLock />}
                {token ? "Disconnect" : "Authenticate"}
              </button>
            </div>
          </header>

          {/* ── ERROR ─── */}
          {error && !showAuthModal && (
            <div style={S.errorBox} className="animate-in">
              <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#ef4444", flexShrink: 0, animation: "pulse-glow 1.2s infinite" }} />
              {error}
            </div>
          )}

          {/* ── INPUT PANEL ─── */}
          <div className="panel-card screws" style={{ padding: "28px", marginBottom: "24px" }}>
            {/* horizontal groove lines */}
            <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 7px, rgba(120,80,20,0.03) 7px, rgba(120,80,20,0.03) 8px)", pointerEvents: "none", borderRadius: "16px" }} />

            <div style={{ position: "relative" }}>
              {/* Panel top row */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px", flexWrap: "wrap", gap: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <div style={{ display: "flex", gap: "6px" }}>
                    {/* Tooltips added to knobs */}
                    <div className="knob" title="Acoustic Calibration (Auto-Tuned by AI)" />
                    <div className="knob" style={{ transform: "rotate(45deg)" }} title="Acoustic Calibration (Auto-Tuned by AI)" />
                    <div className="knob" style={{ transform: "rotate(-30deg)" }} title="Acoustic Calibration (Auto-Tuned by AI)" />
                  </div>
                  <div>
                    <div style={{ fontSize: "13px", fontFamily: "'Cormorant Garamond', serif", fontWeight: 600, color: "#e8d5a3", letterSpacing: "0.04em" }}>Describe the Vibe</div>
                    <div style={{ fontSize: "10px", color: "rgba(180,140,80,0.4)", letterSpacing: "0.15em", textTransform: "uppercase" }}>// Acoustic descriptor input</div>
                  </div>
                </div>
                <VuMeter value={vuLevel} vibeColor={activeColor} />
              </div>

              {/* Textarea */}
              <div style={S.textareaWrap}>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder={"Ex: Late night drive through rain-slicked streets, JBL 4343s, single malt in hand..."}
                  style={S.textarea}
                  disabled={!token || loading}
                  onFocus={e => { e.target.style.borderColor = activeColor; e.target.style.boxShadow = `0 0 0 2px ${activeColor}33`; }}
                  onBlur={e => { e.target.style.borderColor = "rgba(120,80,20,0.35)"; e.target.style.boxShadow = "none"; }}
                />
                {!token && (
                  <div style={S.lockOverlay}>
                    <button onClick={() => setShowAuthModal(true)} style={S.lockBtn}>
                      <IconLock /> Authentication Required
                    </button>
                  </div>
                )}
              </div>

              {/* Bottom row */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "16px", flexWrap: "wrap", gap: "12px" }}>
                <div style={S.signalRow}>
                  <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
                    <div style={S.signalDot(!!token)} className={token ? "pulsing" : ""} />
                    <span style={S.signalLabel}>{token ? "Signal Active" : "No Signal"}</span>
                  </div>
                  <WaveformBars active={loading} count={22} vibeColor={activeColor} />
                </div>

                <button
                  onClick={analyzeVibe}
                  disabled={!token || loading || !prompt.trim()}
                  className="dial-btn"
                  style={S.runBtn(!token || loading || !prompt.trim())}
                >
                  {loading && token
                    ? <><div style={{ width: "14px", height: "14px", border: "2px solid rgba(251,191,36,0.3)", borderTopColor: "#fbbf24", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} /> Analyzing…</>
                    : <><IconPlay /> Run Analysis</>
                  }
                </button>
              </div>
            </div>
          </div>

          {/* ── RESULTS ─── */}
          {result && (
            <div id="results-section" className="animate-in" style={{ scrollMarginTop: "24px" }}>
              {/* Results header */}
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px", paddingLeft: "4px" }}>
                <div style={{ width: "24px", height: "1px", background: activeColor }} />
                <span style={{ fontSize: "10px", letterSpacing: "0.3em", textTransform: "uppercase", color: "rgba(180,140,80,0.4)" }}>Analysis Complete</span>
                <div style={{ flex: 1, height: "1px", background: `linear-gradient(90deg, ${activeColor}88, transparent)` }} />
              </div>

              <div style={S.grid}>
                {/* Dominant Vibe with Secondary Signature Fallback */}
                <div className="panel-card" style={S.resultCard}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                    <IconWave />
                    <span style={S.cardLabel}>Dominant Vibe</span>
                  </div>
                  <div style={{ ...S.cardValue, color: activeColor }}>{result.dominant_vibe}</div>
                  <ConfidenceMeter value={result.confidence} vibeColor={activeColor} />
                  <div style={S.cardSub}>Confidence: {Math.round(result.confidence * 100)}%</div>
                  
                  {/* Secondary Signature Display */}
                  {result.secondary_vibe && (
                    <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid rgba(180,140,80,0.15)", width: "100%", display: "flex", flexDirection: "column", gap: "4px" }}>
                      <span style={{ fontSize: "9px", textTransform: "uppercase", color: "rgba(180,140,80,0.4)", letterSpacing: "0.1em" }}>Secondary Signature</span>
                      <div style={{ fontSize: "14px", fontFamily: "'Playfair Display', serif", color: vibeColors[result.secondary_vibe] || "#e8d5a3", fontStyle: "italic", textShadow: `0 0 10px ${vibeColors[result.secondary_vibe]}44` }}>
                        {result.secondary_vibe} <span style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", opacity: 0.6 }}>({Math.round(result.secondary_confidence * 100)}%)</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* BPM */}
                <div className="panel-card" style={S.resultCard}>
                  <div style={{ marginBottom: "4px" }}>
                    <Vinyl spinning={true} labelColor={activeColor} />
                  </div>
                  <span style={S.cardLabel}>Target Tempo</span>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
                    <span style={S.cardValue}>{result.bpm_range}</span>
                    <span style={{ fontSize: "13px", color: "rgba(180,140,80,0.5)" }}>BPM</span>
                  </div>
                  <div style={S.cardSub}>Rhythmic Pulse</div>
                </div>

                {/* Genres */}
                <div className="panel-card" style={{ ...S.resultCard, justifyContent: "flex-start", paddingTop: "28px" }}>
                  <span style={S.cardLabel}>Genre Mapping</span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center", marginTop: "10px" }}>
                    {result.genres.map(g => (
                      <span key={g} className="freq-tag" style={{ color: activeColor, borderColor: `${activeColor}44` }}>{g}</span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Keyword breakdown */}
              <div className="panel-card" style={{ padding: "24px", marginTop: "16px" }}>
                <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(90deg, transparent, transparent 11px, rgba(120,80,20,0.025) 11px, rgba(120,80,20,0.025) 12px)", pointerEvents: "none", borderRadius: "16px" }} />
                <div style={{ position: "relative" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                    <span style={S.cardLabel}>Neural Match Breakdown</span>
                    <div style={{ flex: 1, height: "1px", background: "linear-gradient(90deg, rgba(120,80,20,0.5), transparent)" }} />
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    {result.matched_keywords.length > 0
                      ? result.matched_keywords.map(kw => (
                        <span key={kw} style={{
                          padding: "5px 12px",
                          background: "rgba(8,5,2,0.8)",
                          border: `1px solid ${activeColor}44`,
                          borderRadius: "6px",
                          fontSize: "11px",
                          fontFamily: "'DM Mono', monospace",
                          color: "rgba(180,140,80,0.85)",
                          letterSpacing: "0.05em",
                          transition: "border-color 0.2s",
                        }}>
                          #{kw}
                        </span>
                      ))
                      : <span style={{ fontSize: "12px", color: "rgba(120,80,20,0.5)", fontStyle: "italic" }}>Universal mood detected — falling back to ambient processing.</span>
                    }
                  </div>
                </div>
              </div>

              {/* Footer tape reel decorative strip */}
              <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "28px", opacity: 0.4 }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", border: "1px solid rgba(120,80,20,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: activeColor }} />
                </div>
                <div style={{ flex: 1, height: "6px", borderRadius: "3px", background: "rgba(80,50,10,0.4)", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: "100%", background: `repeating-linear-gradient(90deg, ${activeColor}66 0px, ${activeColor}66 2px, transparent 2px, transparent 10px)` }} />
                </div>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", border: "1px solid rgba(120,80,20,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: activeColor }} />
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </>
  );
}