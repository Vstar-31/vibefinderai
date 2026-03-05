import { useState, useEffect, useRef } from "react";
import LandingPage from "./LandingPage.jsx";
import PlaylistPanel from "./PlaylistPanel.jsx";

/* ─── API CONFIGURATION ─────────────────────────────────────── */
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const buildApiUrl = (path) => {
  if (API_BASE_URL) return `${API_BASE_URL}${path}`;
  return path;
};

/* ─── SVG ICONS ─────────────────────────────────────────────── */
const IconLock    = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>;
const IconUnlock  = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>;
const IconPlay    = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>;
const IconPause   = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>;
const IconUser    = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
const IconMail    = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>;
const IconX       = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>;
const IconWave    = () => <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>;
const IconDisc    = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>;
const IconFilter  = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>;
const IconRefresh = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>;
const IconThumbUp   = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/></svg>;
const IconThumbDown = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/></svg>;
/* NEW: Library icon for the playlist panel button */
const IconLibrary = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm-8 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>;
const IconBookmark = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/></svg>;
const IconBrain    = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.88A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.88A2.5 2.5 0 0 0 14.5 2Z"/></svg>;
const IconHistory  = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>;
const IconStar     = () => <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>;
const IconHelpCircle = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>;

/* ─── WAVEFORM VISUALISER ────────────────────────────────────── */
function WaveformBars({ active, count = 28 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "3px", height: "32px" }}>
      {Array.from({ length: count }).map((_, i) => {
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
    <div title="Neural Waveform Monitor — Visual Only" style={{
      background: "rgba(16,10,4,0.80)",
      border: "1px solid rgba(120,80,20,0.4)",
      borderRadius: "8px",
      padding: "6px 10px",
      display: "flex",
      alignItems: "center",
      gap: "8px",
      cursor: "default",
      userSelect: "none",
      pointerEvents: "none",
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
          background: "rgba(14,9,3,0.72)",
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

/* ─── INTERACTIVE KNOB ───────────────────────────────────────── */
function Knob({ label, value, onChange }) {
  const [isDragging, setIsDragging] = useState(false);
  const [localVal, setLocalVal] = useState(value);
  const [showTooltip, setShowTooltip] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, val: 0 });

  useEffect(() => {
    const handleMove = (clientX, clientY) => {
      const deltaX = clientX - dragStart.current.x;
      const deltaY = dragStart.current.y - clientY;
      const delta = Math.abs(deltaX) > Math.abs(deltaY) ? deltaX : deltaY;
      let newVal = Math.max(0, Math.min(100, dragStart.current.val + delta * 0.7));
      setLocalVal(newVal);
      onChange(newVal);
    };

    const handleMouseMove = (e) => { if (isDragging) handleMove(e.clientX, e.clientY); };
    const handleTouchMove = (e) => {
      if (isDragging && e.touches[0]) {
        e.preventDefault();
        handleMove(e.touches[0].clientX, e.touches[0].clientY);
      }
    };
    const handleUp = () => { setIsDragging(false); };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleUp);
      window.addEventListener('touchmove', handleTouchMove, { passive: false });
      window.addEventListener('touchend', handleUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleUp);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleUp);
    };
  }, [isDragging, onChange]);

  const startDrag = (clientX, clientY) => {
    setIsDragging(true);
    setShowTooltip(true);
    dragStart.current = { x: clientX, y: clientY, val: localVal };
  };
  const handleMouseDown = (e) => startDrag(e.clientX, e.clientY);
  const handleTouchStart = (e) => { if (e.touches[0]) startDrag(e.touches[0].clientX, e.touches[0].clientY); };

  const renderTicks = () => {
    const ticks = [];
    const totalTicks = 11;
    for (let i = 0; i < totalTicks; i++) {
      const pct = i / (totalTicks - 1);
      const deg = -135 + (pct * 270);
      const isActive = pct * 100 <= localVal;
      const isMajor = i === 0 || i === 5 || i === 10;
      ticks.push(
        <div key={i} style={{
          position: 'absolute', top: '50%', left: '50%',
          width: isMajor ? '2px' : '1.5px', height: isMajor ? '8px' : '5px',
          background: isActive ? 'rgba(217,119,6,0.95)' : 'rgba(180,140,80,0.25)',
          boxShadow: isActive ? '0 0 6px rgba(217,119,6,0.6)' : 'none',
          transform: `translate(-50%, -50%) rotate(${deg}deg) translateY(-23px)`,
          borderRadius: '1px', transition: 'all 0.15s ease'
        }} />
      );
    }
    return ticks;
  };

  const rotation = -135 + (localVal / 100) * 270;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
      <div style={{ position: 'relative', width: '56px', height: '56px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {renderTicks()}
        {(showTooltip || isDragging) && (
          <div style={{
            position: 'absolute', top: '-28px', left: '50%', transform: 'translateX(-50%)',
            background: 'rgba(20,12,4,0.95)', border: '1px solid rgba(217,119,6,0.4)',
            borderRadius: '4px', padding: '2px 7px', fontSize: '10px',
            fontFamily: "'DM Mono', monospace", color: '#fde68a',
            whiteSpace: 'nowrap', pointerEvents: 'none', zIndex: 10,
            boxShadow: '0 2px 8px rgba(0,0,0,0.6)',
          }}>
            {Math.round(localVal)}
          </div>
        )}
        <div
          onMouseDown={handleMouseDown}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => { if (!isDragging) setShowTooltip(false); }}
          onTouchStart={handleTouchStart}
          className="knob"
          style={{
            transform: `rotate(${rotation}deg)`,
            cursor: isDragging ? 'grabbing' : 'grab',
            position: 'absolute', zIndex: 2, width: '32px', height: '32px',
            boxShadow: isDragging ? '0 6px 12px rgba(0,0,0,0.9), inset 0 1px 2px rgba(255,200,80,0.3)' : '',
            touchAction: 'none',
          }}
          title={`${label}: ${Math.round(localVal)} — drag up/down or left/right`}
        />
      </div>
      <span style={{ fontSize: "10px", color: "rgba(180,140,80,0.6)", letterSpacing: "0.15em", textTransform: "uppercase", userSelect: "none", fontWeight: 600 }}>{label}</span>
    </div>
  );
}

/* ─── SKELETON TRACK CARD ─────────────────────────────────── */
function SkeletonTrackCard() {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      flexWrap: "wrap", gap: "14px", padding: "14px 18px",
      background: "rgba(8,5,2,0.6)", border: "1px solid rgba(120,80,20,0.25)",
      borderRadius: "10px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        <div style={{ width: 44, height: 44, borderRadius: 6, background: "rgba(120,80,20,0.15)", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg, transparent 0%, rgba(217,119,6,0.07) 50%, transparent 100%)", animation: "shimmer 1.4s ease-in-out infinite" }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <div style={{ width: 160, height: 14, borderRadius: 4, background: "rgba(120,80,20,0.2)", position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg, transparent, rgba(217,119,6,0.07), transparent)", animation: "shimmer 1.4s ease-in-out infinite" }} />
          </div>
          <div style={{ width: 100, height: 10, borderRadius: 4, background: "rgba(120,80,20,0.12)", position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg, transparent, rgba(217,119,6,0.07), transparent)", animation: "shimmer 1.4s ease-in-out 0.2s infinite" }} />
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: "8px" }}>
        {[32, 32, 72, 72].map((w, i) => (
          <div key={i} style={{ width: w, height: 32, borderRadius: 8, background: "rgba(120,80,20,0.12)", position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg, transparent, rgba(217,119,6,0.07), transparent)", animation: `shimmer 1.4s ease-in-out ${i * 0.1}s infinite` }} />
          </div>
        ))}
      </div>
      <style>{`
        @keyframes shimmer {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
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
        background: #17110b;
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
        transition: transform 0.12s, box-shadow 0.12s, border-color 0.2s;
        border: none;
        outline: none;
      }
      .dial-btn:hover  { transform: scale(1.04); }
      .dial-btn:active { transform: scale(0.97); }

      .panel-card {
        background: linear-gradient(160deg, rgba(44,30,12,0.92) 0%, rgba(24,15,5,0.96) 100%);
        border: 1px solid rgba(160,110,30,0.42);
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
        border-radius: 50%;
        background: radial-gradient(circle at 35% 35%, #5a3a18, #1a0e04);
        border: 2px solid rgba(120,80,20,0.5);
        box-shadow: 0 3px 8px rgba(0,0,0,0.6), inset 0 1px 2px rgba(255,200,80,0.1);
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

      /* ── PLAYLIST PANEL ANIMATIONS ─────────────────────────────── */
      @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to   { transform: translateX(0);    opacity: 1; }
      }
      @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
      }

      /* ── MOBILE RESPONSIVE ─────────────────────────────────── */
      @media (max-width: 600px) {
        .app-header { padding-bottom: 16px !important; margin-bottom: 20px !important; }
        .app-header-osc { display: none !important; }
        .app-logo-sub { display: none !important; }

        .app-panel { padding: 16px !important; }
        .app-knob-row { flex-direction: column !important; gap: 0 !important; }
        .app-knob-strip { justify-content: space-around !important; width: 100% !important; }
        .app-knob-label { display: none !important; }
        .app-vumeter { display: none !important; }
        .app-bottom-row { flex-direction: column !important; gap: 10px !important; align-items: stretch !important; }
        .app-track-controls { justify-content: space-between !important; width: 100% !important; }
        .app-run-btn { width: 100% !important; justify-content: center !important; }
        .app-signal-row { display: none !important; }
        .app-lang-row { flex-wrap: wrap !important; }

        .app-result-grid { grid-template-columns: 1fr !important; }
        .app-result-stat-grid { grid-template-columns: 1fr 1fr !important; }

        .app-track-row { flex-wrap: wrap !important; gap: 8px !important; padding: 12px 14px !important; }
        .app-track-meta { flex: 1 1 calc(100% - 60px) !important; order: -1 !important; min-width: 0 !important; overflow: hidden !important; }
        .app-track-art { width: 36px !important; height: 36px !important; flex-shrink: 0 !important; }
        .app-track-actions { width: 100% !important; justify-content: flex-end !important; gap: 5px !important; flex-wrap: wrap !important; flex-shrink: 0 !important; }
        .app-track-actions button,
        .app-track-actions a { padding: 6px 10px !important; font-size: 9px !important; }

        .app-overrides { flex-direction: column !important; }
        .app-overrides input { width: 100% !important; box-sizing: border-box !important; }
      }

      @media (max-width: 380px) {
        .app-track-actions .app-track-preview { display: none !important; }
      }
    `}</style>
  );
}

/* ─── COPY PLAYLIST BUTTON ───────────────────────────────────── */
function CopyPlaylistButton({ tracks, activeColor }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const text = tracks.map((t, i) => `${i + 1}. ${t.title} — ${t.artist}`).join("\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      const el = document.createElement("textarea");
      el.value = text;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <button
      onClick={handleCopy}
      className="dial-btn"
      title="Copy track list to clipboard"
      style={{
        display: "flex", alignItems: "center", gap: "5px",
        padding: "5px 10px", borderRadius: "6px", fontSize: "10px",
        fontFamily: "'DM Mono', monospace", letterSpacing: "0.06em",
        textTransform: "uppercase", cursor: "pointer",
        background: copied ? "rgba(52,211,153,0.12)" : "rgba(120,80,20,0.15)",
        border: `1px solid ${copied ? "rgba(52,211,153,0.4)" : "rgba(160,110,30,0.35)"}`,
        color: copied ? "#34d399" : "rgba(180,140,80,0.7)",
        transition: "all 0.2s",
      }}
    >
      {copied ? (
        <><span>✓</span> Copied!</>
      ) : (
        <><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> Copy</>
      )}
    </button>
  );
}


/* ═══════════════════════════════════════════════════════════════
   MAIN APP
═══════════════════════════════════════════════════════════════ */
export default function App() {
  const [showLanding, setShowLanding] = useState(true);
  const [token, setToken] = useState(() => {
    try { return localStorage.getItem("vf_token") || null; }
    catch { return null; }
  });
  const [prompt, setPrompt]           = useState("");
  const [lastPrompt, setLastPrompt]   = useState("");
  const [result, setResult]           = useState(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isLoginView, setIsLoginView] = useState(true);
  const [authForm, setAuthForm]       = useState({ email: "", username: "", password: "" });
  const [vuLevel, setVuLevel]         = useState(0);
  const [isSkeletonLoading, setIsSkeletonLoading] = useState(false);
  const [loadReason, setLoadReason] = useState(null);

  const [knobs, setKnobs]             = useState({ artist: 50, nicheness: 50, bpm: 50 });
  const [trackLimit, setTrackLimit]   = useState(5);
  const [language, setLanguage]       = useState("Any");

  // Override & Pro Mode State
  const [showOverrides, setShowOverrides]     = useState(false);
  const [overrideArtist, setOverrideArtist]   = useState("");
  const [overrideGenre, setOverrideGenre]     = useState("");
  const [useSecondaryVibe, setUseSecondaryVibe] = useState(false);

  // Custom Audio Player State
  const [playingTrack, setPlayingTrack] = useState(null);
  const audioRef = useRef(null);
  const vuRef = useRef(null);

  // Detected artist unlock state
  const [artistUnlocked, setArtistUnlocked] = useState(false);

  // Feedback state
  const [feedbackGiven, setFeedbackGiven] = useState({});
  const [feedbackToast, setFeedbackToast] = useState(false);
  const feedbackToastTimer = useRef(null);

  // ── NEW: Playlist Panel State ─────────────────────────────────
  const [showPlaylistPanel, setShowPlaylistPanel] = useState(false);
  // Increments when a playlist is saved — triggers PlaylistPanel to refresh its list
  const [playlistSaveCount, setPlaylistSaveCount] = useState(0);

  // PHASE 8: Personalisation State
  const [tasteProfile, setTasteProfile] = useState({
    likedArtists: {},
    dislikedArtists: {},
    likedVibes: {},
    suppressedTracks: {},
    totalSignals: 0,
  });
  const [showTasteProfile, setShowTasteProfile] = useState(false);
  const [vibeHistory, setVibeHistory] = useState([]);
  const [hoveredTrackIdx, setHoveredTrackIdx] = useState(null);

  // ── Track checklist selection (manual playlist curation) ──────
  const [selectedTracks, setSelectedTracks] = useState(new Set()); // "title|artist" keys
  const [selectionMode, setSelectionMode]   = useState(false);

  // ── Remove track + retry ──────────────────────────────────────
  const [removedTracks, setRemovedTracks]   = useState([]);
  const [retryingTrack, setRetryingTrack]   = useState(null);
  const retryToastTimer = useRef(null);

  const vibeColors = {
    hype: '#f87171', calm: '#34d399', intense: '#f97316', chill: '#60a5fa', focus: '#22d3ee',
    euphoric: '#e879f9', soulful: '#fbbf24', retro: '#818cf8', dreamy: '#c084fc', cinematic: '#fb923c',
    dark: '#9ca3af', heartbreak: '#f472b6', hyperpop: '#d946ef', party: '#ec4899', country: '#d97706',
    tropical: '#14b8a6', industrial: '#6b7280', desi: '#e11d48', neutral: '#d97706',
    'Direct Search': '#facc15'
  };

  const activeColor = result ? (vibeColors[useSecondaryVibe ? result.secondary_vibe : result.dominant_vibe] || vibeColors.neutral) : vibeColors.neutral;

  /* Initialize Audio Object */
  useEffect(() => {
    audioRef.current = new Audio();
    audioRef.current.volume = 0.6;
    audioRef.current.onended = () => setPlayingTrack(null);
    return () => {
      audioRef.current.pause();
      audioRef.current.src = "";
    };
  }, []);

  /* Toggle the In-App Preview Player */
  const togglePlay = (url) => {
    if (!url) return;
    if (playingTrack === url) {
      audioRef.current.pause();
      setPlayingTrack(null);
    } else {
      audioRef.current.src = url;
      audioRef.current.play();
      setPlayingTrack(url);
    }
  };

  /* Animate VU meter while loading or playing music */
  useEffect(() => {
    if (loading || playingTrack) {
      vuRef.current = setInterval(() => {
        setVuLevel(0.3 + Math.random() * 0.65);
      }, 120);
    } else {
      clearInterval(vuRef.current);
      setVuLevel(result ? result.confidence : 0);
    }
    return () => clearInterval(vuRef.current);
  }, [loading, result, playingTrack]);

  const handleAuthChange = (e) => setAuthForm({ ...authForm, [e.target.name]: e.target.value });

  const submitAuth = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      if (!isLoginView) {
        const regRes = await fetch(buildApiUrl("/auth/register"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: authForm.email, username: authForm.username, password: authForm.password }),
        });
        if (!regRes.ok) { const d = await regRes.json(); throw new Error(d.detail || "Registration failed"); }
      }
      const fd = new URLSearchParams();
      fd.append("username", authForm.username); fd.append("password", authForm.password);
      const logRes = await fetch(buildApiUrl("/auth/token"), {
        method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: fd,
      });
      if (!logRes.ok) throw new Error("Authentication failed — check credentials");
      const data = await logRes.json();
      try { localStorage.setItem("vf_token", data.access_token); } catch {}
      setToken(data.access_token);
      setShowAuthModal(false);
      setAuthForm({ email: "", username: "", password: "" });
      setIsLoginView(true);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const handleLogout = () => {
    try { localStorage.removeItem("vf_token"); } catch {}
    setToken(null); setResult(null); setPrompt(""); setVuLevel(0);
    setShowPlaylistPanel(false);
  };

  const analyzeVibe = async (config = {}) => {
    if (!prompt.trim()) return;
    try {
      setLoading(true); setError(""); setIsSkeletonLoading(true);
      if (config.targetSecondary !== undefined) setLoadReason("pivot");
      else if (config.targetGenre !== undefined) setLoadReason("genre");
      else setLoadReason("main");

      let finalSecondary = useSecondaryVibe;
      let finalGenre = overrideGenre;
      let finalArtist = overrideArtist;

      if (config.isFilterClick) {
          if (config.targetSecondary !== undefined) finalSecondary = config.targetSecondary;
          if (config.targetGenre !== undefined) finalGenre = config.targetGenre;
      } else {
          if (prompt !== lastPrompt) {
              finalSecondary = false;
              if (!showOverrides) {
                  finalGenre = "";
                  finalArtist = "";
              }
          }
      }

      setUseSecondaryVibe(finalSecondary);
      setOverrideGenre(finalGenre);
      setOverrideArtist(finalArtist);
      setLastPrompt(prompt);

      const res = await fetch(buildApiUrl("/api/vibe/analyze"), {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          text: prompt,
          artist_focus: Math.round(knobs.artist),
          nicheness: Math.round(knobs.nicheness),
          bpm_focus: Math.round(knobs.bpm),
          track_limit: trackLimit,
          use_secondary_vibe: finalSecondary,
          override_genre: finalGenre.trim() || null,
          override_artist: finalArtist.trim() || null,
          language: language !== "Any" ? language : null,
          dismiss_detected_artist: artistUnlocked,
          excluded_tracks: removedTracks.length > 0 ? removedTracks : null,
          liked_artists: Object.entries(tasteProfile.likedArtists)
            .filter(([, count]) => count >= 2)
            .map(([artist]) => artist),
        }),
      });

      if (res.status === 401) { handleLogout(); throw new Error("Session expired — re-authenticate"); }

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Analysis failed due to server error.");
      }

      const data = await res.json();
      setResult(data);
      setArtistUnlocked(false);
      // PHASE 8: Record vibe history
      if (data.dominant_vibe && data.dominant_vibe !== 'Direct Search') {
        setVibeHistory(prev => {
          const entry = { vibe: data.dominant_vibe, prompt: prompt.trim(), timestamp: Date.now() };
          const filtered = prev.filter(h => h.vibe !== data.dominant_vibe);
          return [entry, ...filtered].slice(0, 8);
        });
      }
      setIsSkeletonLoading(false);
      setSelectedTracks(new Set());
      setSelectionMode(false);
      setTimeout(() => { document.getElementById('results-section')?.scrollIntoView({ behavior: 'smooth' }); }, 150);
    } catch (err) { setError(err.message); setIsSkeletonLoading(false); }
    finally { setLoading(false); setLoadReason(null); }
  };

  // FULL ENGINE KILL SWITCH
  const resetEngine = () => {
      setPrompt("");
      setLastPrompt("");
      setResult(null);
      setOverrideGenre("");
      setOverrideArtist("");
      setUseSecondaryVibe(false);
      setError("");
      setFeedbackGiven({});
      setArtistUnlocked(false);
      setSelectedTracks(new Set());
      setSelectionMode(false);
      setRemovedTracks([]);
  };

  // REMOVE TRACK + PULL REPLACEMENT
  const removeTrackAndRetry = async (track) => {
    const key = `${track.title}|${track.artist}`;
    setResult(prev => prev ? {
      ...prev,
      tracks: prev.tracks.filter(t => `${t.title}|${t.artist}` !== key)
    } : prev);
    setRemovedTracks(prev => [...prev, { title: track.title, artist: track.artist }]);
    clearTimeout(retryToastTimer.current);
    setRetryingTrack(track.title);
    retryToastTimer.current = setTimeout(() => setRetryingTrack(null), 2800);
    await submitFeedback(track, 0, -1);
  };

  // FEEDBACK SUBMISSION
  const submitFeedback = async (track, position, signal) => {
    const key = `${track.title}|${track.artist}`;
    const current = feedbackGiven[key];
    const newSignal = current === signal ? 0 : signal;
    setFeedbackGiven(prev => ({ ...prev, [key]: newSignal }));

    if (newSignal !== 0) {
      setFeedbackToast(true);
      clearTimeout(feedbackToastTimer.current);
      feedbackToastTimer.current = setTimeout(() => setFeedbackToast(false), 2200);

      // PHASE 8: Update session taste profile
      setTasteProfile(prev => {
        const updated = { ...prev, totalSignals: prev.totalSignals + 1 };
        const artist = track.artist;
        if (newSignal === 1) {
          updated.likedArtists = { ...prev.likedArtists, [artist]: (prev.likedArtists[artist] || 0) + 1 };
          if (result?.dominant_vibe) {
            updated.likedVibes = { ...prev.likedVibes, [result.dominant_vibe]: (prev.likedVibes[result.dominant_vibe] || 0) + 1 };
          }
        } else if (newSignal === -1) {
          const dislikes = (prev.dislikedArtists[artist] || 0) + 1;
          updated.dislikedArtists = { ...prev.dislikedArtists, [artist]: dislikes };
          // Auto-suppress after 3 downvotes on same track
          const trackDislikes = (prev.suppressedTracks[key] || 0) + 1;
          updated.suppressedTracks = { ...prev.suppressedTracks, [key]: trackDislikes };
        }
        return updated;
      });
    }

    try {
      await fetch(buildApiUrl("/api/feedback"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          request_id:      result?.request_id ?? "unlogged",
          track_title:     track.title,
          track_artist:    track.artist,
          signal:          newSignal,
          position:        position,
          preview_seconds: null,
        }),
      });
    } catch (err) {
      console.warn("Feedback submission failed:", err);
    }
  };

  /* ── STYLES ── */
  const S = {
    root: { minHeight: "100vh", padding: "24px 16px 60px", fontFamily: "'DM Mono', monospace" },
    inner: { maxWidth: "860px", margin: "0 auto" },
    header: { display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: "24px", borderBottom: "1px solid rgba(155,105,28,0.38)", marginBottom: "32px" },
    logoWrap: { display: "flex", alignItems: "center", gap: "14px" },
    logoDisc: { width: "42px", height: "42px", borderRadius: "50%", background: "conic-gradient(from 0deg, #1a1008, #3d2510, #1a1008, #2e1a0a, #1a1008)", border: "2px solid rgba(180,140,80,0.4)", boxShadow: `0 0 18px ${activeColor}44, inset 0 0 10px rgba(0,0,0,0.5)`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "box-shadow 0.5s ease" },
    logoDiscInner: { width: "10px", height: "10px", borderRadius: "50%", background: `radial-gradient(circle, ${activeColor}, #7a4f12)`, transition: "background 0.5s ease" },
    logoText: { fontFamily: "'Playfair Display', serif", fontSize: "22px", fontWeight: 900, color: "#e8d5a3", letterSpacing: "-0.01em", lineHeight: 1.1 },
    logoSub: { fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "rgba(180,140,80,0.5)", letterSpacing: "0.25em", textTransform: "uppercase" },
    authBtn: (hasToken) => ({ display: "flex", alignItems: "center", gap: "8px", padding: "8px 18px", borderRadius: "8px", fontFamily: "'DM Mono', monospace", fontSize: "12px", fontWeight: 500, letterSpacing: "0.08em", textTransform: "uppercase", cursor: "pointer", transition: "all 0.2s", background: hasToken ? "rgba(40,20,5,0.8)" : "linear-gradient(135deg, #92400e, #d97706)", color: hasToken ? "rgba(180,140,80,0.7)" : "#fef3c7", border: hasToken ? "1px solid rgba(120,80,20,0.4)" : "1px solid rgba(251,191,36,0.3)", boxShadow: hasToken ? "none" : "0 0 20px rgba(217,119,6,0.25)" }),
    signalRow: { display: "flex", alignItems: "center", gap: "20px", flexWrap: "wrap" },
    signalDot: (on) => ({ width: "7px", height: "7px", borderRadius: "50%", background: on ? activeColor : "rgba(80,50,10,0.5)", boxShadow: on ? `0 0 8px ${activeColor}` : "none", flexShrink: 0, transition: "background 0.3s, box-shadow 0.3s" }),
    signalLabel: { fontSize: "10px", letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.5)" },
    errorBox: { display: "flex", alignItems: "center", gap: "10px", padding: "12px 16px", background: "rgba(60,10,10,0.5)", border: "1px solid rgba(180,40,40,0.3)", borderRadius: "10px", color: "#f87171", fontSize: "12px", marginBottom: "20px", lineHeight: "1.4" },
    textareaWrap: { position: "relative" },
    textarea: { width: "100%", height: "130px", background: "rgba(5,3,1,0.8)", border: "1px solid rgba(160,110,30,0.42)", borderRadius: "10px", padding: "16px", color: "#e8d5a3", fontFamily: "'DM Mono', monospace", fontSize: "14px", lineHeight: "1.6", outline: "none", transition: "border-color 0.2s, box-shadow 0.2s" },
    lockOverlay: { position: "absolute", inset: 0, background: "rgba(5,3,1,0.75)", backdropFilter: "blur(4px)", borderRadius: "10px", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 },
    lockBtn: { display: "flex", alignItems: "center", gap: "8px", padding: "10px 22px", background: "rgba(20,12,4,0.9)", border: "1px solid rgba(180,120,40,0.35)", borderRadius: "30px", color: "rgba(180,140,80,0.8)", fontSize: "12px", cursor: "pointer", letterSpacing: "0.1em", textTransform: "uppercase", fontFamily: "'DM Mono', monospace", transition: "border-color 0.2s, color 0.2s" },
    runBtn: (disabled) => ({ display: "flex", alignItems: "center", gap: "10px", padding: "12px 28px", background: disabled ? "rgba(50,30,8,0.4)" : "linear-gradient(135deg, #92400e 0%, #b45309 50%, #d97706 100%)", border: "1px solid " + (disabled ? "rgba(80,50,10,0.3)" : "rgba(251,191,36,0.3)"), borderRadius: "10px", color: disabled ? "rgba(120,80,20,0.5)" : "#fef3c7", fontFamily: "'DM Mono', monospace", fontSize: "12px", fontWeight: 500, letterSpacing: "0.15em", textTransform: "uppercase", cursor: disabled ? "not-allowed" : "pointer", boxShadow: disabled ? "none" : `0 4px 20px ${activeColor}44`, transition: "all 0.2s" }),
    grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "16px" },
    resultCard: { padding: "24px", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: "8px" },
    cardLabel: { fontSize: "10px", letterSpacing: "0.25em", textTransform: "uppercase", color: "rgba(180,140,80,0.45)" },
    cardValue: { fontFamily: "'Playfair Display', serif", fontSize: "30px", fontWeight: 700, color: "#fde68a", textShadow: `0 0 20px ${activeColor}44` },
    cardSub: { fontSize: "11px", color: "rgba(180,140,80,0.5)", letterSpacing: "0.1em" },
    modalOverlay: { position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: "16px", background: "rgba(4,2,1,0.88)", backdropFilter: "blur(8px)" },
    modal: { width: "100%", maxWidth: "420px", padding: "36px 32px 28px", position: "relative" },
    modalTitle: { fontFamily: "'Playfair Display', serif", fontSize: "24px", fontWeight: 900, color: "#fde68a", marginBottom: "8px" },
    modalSub: { fontSize: "11px", color: "rgba(180,140,80,0.45)", letterSpacing: "0.1em", marginBottom: "28px" },
    formLabel: { fontSize: "10px", letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.5)", marginBottom: "6px", display: "block" },
    submitBtn: { width: "100%", padding: "12px", marginTop: "24px", background: "linear-gradient(135deg, #92400e, #d97706)", border: "1px solid rgba(251,191,36,0.25)", borderRadius: "8px", color: "#fef3c7", fontFamily: "'DM Mono', monospace", fontSize: "12px", fontWeight: 500, letterSpacing: "0.18em", textTransform: "uppercase", cursor: "pointer", boxShadow: "0 4px 20px rgba(180,100,10,0.3)", transition: "opacity 0.2s" },
  };

  // Browser back navigation
  useEffect(() => {
    if (!showLanding) window.history.pushState({ page: "engine" }, "");
    const handlePop = () => setShowLanding(true);
    window.addEventListener("popstate", handlePop);
    return () => window.removeEventListener("popstate", handlePop);
  }, [showLanding]);

  if (showLanding) return <LandingPage onLaunch={() => setShowLanding(false)} />;

  return (
    <>
      <GlobalStyles />
      <div style={S.root}>

        {/* ── AUTH MODAL ─────────────────────────────────────── */}
        {showAuthModal && (
          <div style={S.modalOverlay}>
            <div className="panel-card screws animate-in" style={S.modal}>
              <button onClick={() => setShowAuthModal(false)} style={{ position: "absolute", top: "16px", right: "16px", background: "none", border: "none", color: "rgba(180,140,80,0.4)", cursor: "pointer" }}><IconX /></button>
              <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 5px, rgba(120,80,20,0.04) 5px, rgba(120,80,20,0.04) 6px)", borderRadius: "16px", pointerEvents: "none" }} />
              <div style={{ position: "relative" }}>
                <p style={S.modalTitle}>{isLoginView ? "Welcome Back" : "Create Account"}</p>
                <p style={S.modalSub}>{isLoginView ? "Sign in to continue" : "// CREATE YOUR ACCOUNT"}</p>
                {error && <div style={{ ...S.errorBox, marginBottom: "20px" }}><div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#ef4444", flexShrink: 0 }} />{error}</div>}
                <form onSubmit={submitAuth} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                  {!isLoginView && <div><label style={S.formLabel}>Email Address</label><AudioInput icon={<IconMail />} type="email" name="email" value={authForm.email} onChange={handleAuthChange} required placeholder="listener@analog.audio" /></div>}
                  <div><label style={S.formLabel}>Username</label><AudioInput icon={<IconUser />} type="text" name="username" value={authForm.username} onChange={handleAuthChange} required placeholder="audiophile_001" /></div>
                  <div><label style={S.formLabel}>Passphrase</label><AudioInput icon={<IconLock />} type="password" name="password" value={authForm.password} onChange={handleAuthChange} required placeholder="••••••••••••" /></div>
                  <button type="submit" disabled={loading} className="dial-btn" style={{ ...S.submitBtn, opacity: loading ? 0.5 : 1 }}>{loading ? "Handshaking..." : isLoginView ? "Sign In" : "Create Account"}</button>
                </form>
                <p style={{ textAlign: "center", marginTop: "18px", fontSize: "11px", color: "rgba(180,140,80,0.4)", letterSpacing: "0.05em" }}>
                  {isLoginView ? "New here? " : "Already have an account? "}
                  <button type="button" onClick={() => { setIsLoginView(!isLoginView); setError(""); setAuthForm({ email: "", username: "", password: "" }); }} style={{ background: "none", border: "none", color: "#d97706", cursor: "pointer", fontFamily: "'DM Mono', monospace", fontSize: "11px" }}>{isLoginView ? "Create one" : "Sign in"}</button>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── INNER LAYOUT ───────────────────────────────────── */}
        <div style={S.inner}>

          {/* ── HEADER ─── */}
          <header className="app-header" style={S.header}>
            <div style={S.logoWrap}>
              <button
                onClick={() => setShowLanding(true)}
                title="Back to Home"
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  color: "rgba(180,140,80,0.45)", fontSize: "11px",
                  fontFamily: "'DM Mono', monospace", letterSpacing: "0.1em",
                  textTransform: "uppercase", display: "flex", alignItems: "center",
                  gap: "5px", padding: "4px 10px 4px 0", transition: "color 0.2s",
                }}
                onMouseOver={e => e.currentTarget.style.color = "#e8d5a3"}
                onMouseOut={e => e.currentTarget.style.color = "rgba(180,140,80,0.45)"}
              >
                &#8592; Home
              </button>
              <div style={S.logoDisc}><div style={S.logoDiscInner} /></div>
              <div><div style={S.logoText}>VibeFinder</div><div className="app-logo-sub" style={S.logoSub}>Acoustic Intelligence Engine</div></div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div className="app-header-osc"><Oscilloscope active={loading || !!playingTrack} /></div>

              {/* ── NEW: LIBRARY / PLAYLIST PANEL BUTTON ── */}
              {token && (
                <button
                  onClick={() => setShowPlaylistPanel(true)}
                  className="dial-btn"
                  title="My Playlists & History"
                  style={{
                    display: "flex", alignItems: "center", gap: "7px",
                    padding: "8px 14px", borderRadius: "8px",
                    fontFamily: "'DM Mono', monospace", fontSize: "11px",
                    fontWeight: 500, letterSpacing: "0.08em", textTransform: "uppercase",
                    cursor: "pointer", transition: "all 0.2s",
                    background: "rgba(40,20,5,0.8)",
                    color: "rgba(180,140,80,0.7)",
                    border: "1px solid rgba(120,80,20,0.4)",
                  }}
                >
                  <IconLibrary /> Library
                </button>
              )}

              <button onClick={token ? handleLogout : () => setShowAuthModal(true)} className="dial-btn" style={S.authBtn(!!token)}>{token ? <IconUnlock /> : <IconLock />}{token ? "Sign Out" : "Sign In"}</button>
            </div>
          </header>

          {/* ── ERROR ─── */}
          {error && !showAuthModal && !result && (
            <div style={S.errorBox} className="animate-in"><div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#ef4444", flexShrink: 0, animation: "pulse-glow 1.2s infinite" }} />{error}</div>
          )}

          {/* ── INPUT PANEL ─── */}
          <div className="panel-card screws app-panel" style={{ padding: "28px", marginBottom: "24px" }}>
            <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 7px, rgba(120,80,20,0.03) 7px, rgba(120,80,20,0.03) 8px)", pointerEvents: "none", borderRadius: "16px" }} />
            <div style={{ position: "relative" }}>
              <div className="app-knob-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px", flexWrap: "wrap", gap: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
                  <div className="app-knob-strip" style={{ display: "flex", gap: "16px" }}>
                    <Knob label="Artist" value={knobs.artist} onChange={v => setKnobs(prev => ({...prev, artist: v}))} />
                    <Knob label="Nicheness" value={knobs.nicheness} onChange={v => setKnobs(prev => ({...prev, nicheness: v}))} />
                    <Knob label="BPM" value={knobs.bpm} onChange={v => setKnobs(prev => ({...prev, bpm: v}))} />
                  </div>
                  <div className="app-knob-label" style={{ marginLeft: "8px" }}>
                    <div style={{ fontSize: "15px", fontFamily: "'Cormorant Garamond', serif", fontWeight: 600, color: "#e8d5a3", letterSpacing: "0.04em" }}>Describe the Vibe</div>
                    <div style={{ fontSize: "10px", color: "rgba(180,140,80,0.4)", letterSpacing: "0.15em", textTransform: "uppercase" }}>// Acoustic descriptor input</div>
                  </div>
                </div>
                <div className="app-vumeter"><VuMeter value={vuLevel} vibeColor={activeColor} /></div>
              </div>

              <div style={S.textareaWrap}>
                <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder={"Ex: Late night drive through rain-slicked streets, Travis Scott on the radio..."}
                    style={S.textarea}
                    disabled={!token || loading}
                    onFocus={e => { e.target.style.borderColor = activeColor; e.target.style.boxShadow = `0 0 0 2px ${activeColor}22`; }}
                    onBlur={e => { e.target.style.borderColor = "rgba(160,110,30,0.42)"; e.target.style.boxShadow = "none"; }}
                />
                <div style={{ position: "absolute", bottom: "10px", right: "14px", display: "flex", alignItems: "center", gap: "8px", pointerEvents: "none" }}>
                  {prompt.length > 0 && (
                    <span style={{
                      fontSize: "9px", fontFamily: "'DM Mono', monospace",
                      color: prompt.length < 15 ? "rgba(251,191,36,0.6)"
                           : prompt.length > 300 ? "rgba(248,113,113,0.6)"
                           : "rgba(180,140,80,0.3)",
                      letterSpacing: "0.05em",
                    }}>
                      {prompt.length < 15 ? "↑ add more detail" : prompt.length > 300 ? "trim for best results" : `${prompt.length} chars`}
                    </span>
                  )}
                </div>
                {!token && <div style={S.lockOverlay}><button onClick={() => setShowAuthModal(true)} style={S.lockBtn}><IconLock /> Authentication Required</button></div>}
              </div>

              {/* Language Selector */}
              <div className="app-lang-row" style={{ marginTop: "14px", display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <span style={{ fontSize: "9px", color: "rgba(200,160,90,0.6)", textTransform: "uppercase", letterSpacing: "0.15em" }}>Language</span>
                <select
                  value={language}
                  onChange={e => setLanguage(e.target.value)}
                  disabled={!token || loading}
                  style={{
                    background: "rgba(14,9,3,0.72)", border: "1px solid rgba(160,110,30,0.42)",
                    borderRadius: "8px", padding: "7px 14px", color: "#e8d5a3",
                    fontFamily: "'DM Mono', monospace", fontSize: "12px",
                    outline: "none", cursor: token ? "pointer" : "default", opacity: token ? 1 : 0.5,
                  }}
                  onFocus={e => { e.target.style.borderColor = "rgba(217,119,6,0.7)"; }}
                  onBlur={e => { e.target.style.borderColor = "rgba(160,110,30,0.42)"; }}
                >
                  {["Any","English","Hindi","Punjabi","Tamil","Telugu","Kannada","Malayalam","Bengali","Urdu","Korean","Japanese","Spanish","Portuguese","French","Arabic","Afrobeats"].map(l => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
                {language !== "Any" && <span style={{ fontSize: "9px", color: "rgba(217,160,60,0.7)", letterSpacing: "0.1em", textTransform: "uppercase" }}>{language} pool active</span>}
              </div>

              {/* ── PRO MODE OVERRIDES ── */}
              <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <button
                  onClick={() => setShowOverrides(!showOverrides)}
                  disabled={!token}
                  style={{ background: "none", border: "none", color: "rgba(180,140,80,0.6)", fontSize: "10px", letterSpacing: "0.1em", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "6px", cursor: token ? "pointer" : "default", fontFamily: "'DM Mono', monospace", alignSelf: "flex-start", opacity: token ? 1 : 0.5 }}
                >
                  <IconFilter /> {showOverrides ? "Hide Overrides" : "Manual Overrides // Pro Mode"}
                </button>

                {showOverrides && token && (
                  <div className="animate-in app-overrides" style={{ display: "flex", gap: "16px", flexWrap: "wrap", padding: "16px", background: "rgba(10,5,2,0.6)", border: "1px dashed rgba(180,140,80,0.25)", borderRadius: "8px" }}>
                    <div style={{ flex: 1, minWidth: "160px" }}>
                       <label style={{ fontSize: "9px", color: "rgba(180,140,80,0.5)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "6px", display: "block" }}>Force Artist Filter</label>
                       <input type="text" value={overrideArtist} onChange={e => setOverrideArtist(e.target.value)} placeholder="e.g. Deftones" style={{ width: "100%", background: "rgba(0,0,0,0.4)", border: "1px solid rgba(120,80,20,0.4)", borderRadius: "6px", padding: "8px 12px", color: "#e8d5a3", fontSize: "12px", fontFamily: "'DM Mono', monospace", outline: "none", transition: "border-color 0.2s" }} onFocus={e => e.target.style.borderColor = "#d97706"} onBlur={e => e.target.style.borderColor = "rgba(120,80,20,0.4)"} />
                    </div>
                    <div style={{ flex: 1, minWidth: "160px" }}>
                       <label style={{ fontSize: "9px", color: "rgba(180,140,80,0.5)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "6px", display: "block" }}>Force Genre Filter</label>
                       <input type="text" value={overrideGenre} onChange={e => setOverrideGenre(e.target.value)} placeholder="e.g. shoegaze" style={{ width: "100%", background: "rgba(0,0,0,0.4)", border: "1px solid rgba(120,80,20,0.4)", borderRadius: "6px", padding: "8px 12px", color: "#e8d5a3", fontSize: "12px", fontFamily: "'DM Mono', monospace", outline: "none", transition: "border-color 0.2s" }} onFocus={e => e.target.style.borderColor = "#d97706"} onBlur={e => e.target.style.borderColor = "rgba(120,80,20,0.4)"} />
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "18px", cursor: "pointer", width: "100%" }} onClick={() => setUseSecondaryVibe(!useSecondaryVibe)}>
                      <div style={{ width: "36px", height: "18px", borderRadius: "9px", background: useSecondaryVibe ? "rgba(217,119,6,0.6)" : "rgba(80,50,10,0.4)", position: "relative", transition: "background 0.2s", border: "1px solid rgba(155,105,28,0.38)" }}>
                         <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: useSecondaryVibe ? "#fde68a" : "rgba(180,140,80,0.6)", position: "absolute", top: "2px", left: useSecondaryVibe ? "20px" : "3px", transition: "left 0.2s, background 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.5)" }} />
                      </div>
                      <span style={{ fontSize: "10px", color: useSecondaryVibe ? "#fde68a" : "rgba(180,140,80,0.5)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Hard-Switch to Secondary Vibe</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="app-bottom-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "20px", flexWrap: "wrap", gap: "12px" }}>
                <div className="app-signal-row" style={S.signalRow}>
                  <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
                    <div style={S.signalDot(!!token)} className={token ? "pulsing" : ""} />
                    <span style={S.signalLabel}>{token ? "Signal Active" : "No Signal"}</span>
                  </div>
                  <WaveformBars active={loading || !!playingTrack} count={22} vibeColor={activeColor} />
                </div>

                <div className="app-track-controls" style={{ display: "flex", alignItems: "center", gap: "12px" }}>

                  {result && (
                      <button
                          onClick={resetEngine}
                          disabled={loading}
                          title="Clear all filters and drop results"
                          style={{ background: "none", border: "none", color: "rgba(180,140,80,0.4)", fontSize: "10px", textTransform: "uppercase", cursor: "pointer", letterSpacing: "0.1em", display: "flex", alignItems: "center", gap: "4px", padding: "8px", transition: "color 0.2s" }}
                          onMouseOver={e => e.currentTarget.style.color = "#ef4444"}
                          onMouseOut={e => e.currentTarget.style.color = "rgba(180,140,80,0.4)"}
                      >
                          <IconRefresh /> Reset Engine
                      </button>
                  )}

                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "10px", color: "rgba(180,140,80,0.5)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Tracks:</span>
                    <div style={{ display: "flex", background: "rgba(10,5,2,0.6)", border: "1px solid rgba(155,105,28,0.38)", borderRadius: "6px", overflow: "hidden" }}>
                      {[5, 10, 20, 50].map(num => (
                        <button
                          key={num}
                          onClick={() => setTrackLimit(num)}
                          disabled={!token || loading}
                          style={{
                            background: trackLimit === num ? "rgba(217,119,6,0.25)" : "transparent",
                            color: trackLimit === num ? "#fde68a" : "rgba(180,140,80,0.6)",
                            border: "none",
                            padding: "8px 12px",
                            fontSize: "11px",
                            fontFamily: "'DM Mono', monospace",
                            cursor: token && !loading ? "pointer" : "default",
                            transition: "all 0.2s"
                          }}
                        >
                          {num}
                        </button>
                      ))}
                    </div>
                  </div>

                  <button onClick={() => analyzeVibe()} disabled={!token || loading || !prompt.trim()} className="dial-btn app-run-btn" style={S.runBtn(!token || loading || !prompt.trim())}>
                    {loading && token ? <><div style={{ width: "14px", height: "14px", border: "2px solid rgba(251,191,36,0.3)", borderTopColor: "#fbbf24", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} /> Analyzing…</> : <><IconPlay /> Run Analysis</>}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* ── SKELETON LOADING PLAYLIST ─── */}
          {isSkeletonLoading && !result && (
            <div className="animate-in" style={{ marginTop: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px", paddingLeft: "4px" }}>
                <div style={{ width: "24px", height: "1px", background: "rgba(217,119,6,0.4)" }} />
                <span style={{ fontSize: "10px", letterSpacing: "0.3em", textTransform: "uppercase", color: "rgba(180,140,80,0.4)" }}>Processing Signal…</span>
                <div style={{ flex: 1, height: "1px", background: "linear-gradient(90deg, rgba(217,119,6,0.4), transparent)" }} />
              </div>
              <div className="panel-card screws" style={{ padding: "24px" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {Array.from({ length: trackLimit }).map((_, i) => (
                    <SkeletonTrackCard key={i} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ── RESULTS ─── */}
          {result && (
            <div id="results-section" className="animate-in" style={{ scrollMarginTop: "24px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px", paddingLeft: "4px" }}>
                <div style={{ width: "24px", height: "1px", background: `${activeColor}88` }} />
                <span style={{ fontSize: "10px", letterSpacing: "0.3em", textTransform: "uppercase", color: "rgba(180,140,80,0.4)" }}>Analysis Complete</span>
                {tasteProfile.totalSignals >= 2 && (
                  <span style={{ fontSize: "9px", display: "flex", alignItems: "center", gap: "4px", padding: "2px 8px", background: `${activeColor}11`, border: `1px solid ${activeColor}33`, borderRadius: "20px", color: activeColor, fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em", flexShrink: 0 }}>
                    <IconBrain /> PERSONALISED
                  </span>
                )}
                <div style={{ flex: 1, height: "1px", background: `linear-gradient(90deg, ${activeColor}66, transparent)` }} />
              </div>

              {/* ── ARTIST DETECTION WARNING BANNER ── */}
              {result.detected_artist && !artistUnlocked && (
                <div style={{
                  display: "flex", alignItems: "flex-start", gap: "12px",
                  background: `${activeColor}0d`, border: `1px solid ${activeColor}33`,
                  borderRadius: "6px", padding: "10px 14px", marginBottom: "16px",
                  fontSize: "11px", color: "rgba(220,190,140,0.85)", lineHeight: "1.5",
                }}>
                  <span style={{ fontSize: "16px", lineHeight: 1, marginTop: "1px", flexShrink: 0 }}>🔒</span>
                  <div style={{ flex: 1 }}>
                    <span style={{ color: activeColor, fontWeight: 600, letterSpacing: "0.05em" }}>
                      Artist detected: {result.detected_artist}
                    </span>
                    {result.detected_song && (
                      <span style={{ color: "rgba(180,140,80,0.7)", marginLeft: "6px" }}>
                        ({result.detected_song})
                      </span>
                    )}
                    <br />
                    <span style={{ opacity: 0.75 }}>
                      The engine has locked onto this artist from your description. If that wasn't your intention —
                      tap <strong style={{ color: activeColor }}>✕</strong> on the tag below to unlock and re-run for a pure vibe search.
                    </span>
                  </div>
                </div>
              )}

              <div className="app-result-grid" style={S.grid}>
                <div className="panel-card" style={S.resultCard}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}><IconWave /><span style={S.cardLabel}>Dominant Vibe</span></div>
                  <div style={{ ...S.cardValue, color: activeColor }}>
                    {useSecondaryVibe ? result.secondary_vibe || result.dominant_vibe : result.dominant_vibe}
                  </div>

                  {result.dominant_vibe === 'Direct Search' && !useSecondaryVibe && (
                     <div style={{ fontSize: "10px", background: "rgba(250,204,21,0.15)", color: "#facc15", padding: "4px 8px", borderRadius: "4px", border: "1px solid rgba(250,204,21,0.3)", marginTop: "4px" }}>
                       FALLBACK MODE ACTIVE
                     </div>
                  )}

                  <ConfidenceMeter value={useSecondaryVibe ? result.secondary_confidence : result.confidence} vibeColor={activeColor} />
                  <div style={S.cardSub}>Confidence: {Math.round((useSecondaryVibe ? result.secondary_confidence : result.confidence) * 100)}%</div>

                  {(result.secondary_vibe || useSecondaryVibe) &&
                   result.dominant_vibe !== 'Direct Search' &&
                   (useSecondaryVibe || (result.secondary_confidence || 0) >= 0.50) && (
                    <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid rgba(180,140,80,0.15)", width: "100%", display: "flex", flexDirection: "column", gap: "8px", alignItems: "center" }}>
                      <span style={{ fontSize: "9px", textTransform: "uppercase", color: "rgba(180,140,80,0.4)", letterSpacing: "0.1em" }}>
                        {useSecondaryVibe ? "Primary Signature Available" : "Secondary Signature Detected"}
                      </span>
                      <button
                        onClick={() => analyzeVibe({ isFilterClick: true, targetSecondary: !useSecondaryVibe })}
                        disabled={loading}
                        className="dial-btn"
                        style={{ background: "rgba(20,10,5,0.6)", border: `1px dashed ${vibeColors[useSecondaryVibe ? result.dominant_vibe : result.secondary_vibe]}66`, padding: "6px 12px", borderRadius: "6px", color: vibeColors[useSecondaryVibe ? result.dominant_vibe : result.secondary_vibe] || "#e8d5a3", fontSize: "11px", fontFamily: "'DM Mono', monospace", display: "flex", alignItems: "center", gap: "6px", width: "100%", justifyContent: "center", opacity: loading ? 0.7 : 1 }}
                      >
                        {loading && loadReason === "pivot" ? (
                          <>
                            <div style={{ width: "10px", height: "10px", border: "1.5px solid rgba(251,191,36,0.3)", borderTopColor: "#fbbf24", borderRadius: "50%", animation: "spin 0.7s linear infinite", flexShrink: 0 }} />
                            Pivoting to <span style={{ fontFamily: "'Playfair Display', serif", fontSize: "13px", fontStyle: "italic", marginLeft: "4px" }}>{useSecondaryVibe ? result.dominant_vibe : result.secondary_vibe}</span>…
                          </>
                        ) : (
                          <>Pivot Engine to: <span style={{ fontFamily: "'Playfair Display', serif", fontSize: "13px", fontStyle: "italic" }}>{useSecondaryVibe ? result.dominant_vibe : result.secondary_vibe}</span></>
                        )}
                      </button>
                    </div>
                  )}
                </div>

                <div className="panel-card" style={S.resultCard}>
                  <div style={{ marginBottom: "4px" }}><Vinyl spinning={!!playingTrack || loading} labelColor={activeColor} /></div>
                  <span style={S.cardLabel}>Target Tempo</span>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}><span style={S.cardValue}>{result.bpm_range}</span><span style={{ fontSize: "13px", color: "rgba(180,140,80,0.5)" }}>BPM</span></div>
                  <div style={S.cardSub}>Rhythmic Pulse</div>
                </div>

                <div className="panel-card" style={{ ...S.resultCard, justifyContent: "flex-start", paddingTop: "28px" }}>
                  <span style={S.cardLabel}>Engine State</span>
                  <span style={{ fontSize: "9px", color: "rgba(180,140,80,0.4)", textTransform: "uppercase", letterSpacing: "0.1em", marginTop: "-4px" }}>[ Click Genres to Hard-Filter ]</span>

                  <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "10px", width: "100%", alignItems: "center" }}>
                    {result.detected_artist && !artistUnlocked && (
                      <span className="freq-tag" style={{ color: activeColor, borderColor: `${activeColor}44`, background: `${activeColor}11`, display: "inline-flex", alignItems: "center", gap: "6px" }}>
                        🔒 {result.detected_artist}
                        <button
                          onClick={() => setArtistUnlocked(true)}
                          title="Dismiss artist lock"
                          style={{ background: "none", border: "none", cursor: "pointer", color: activeColor, opacity: 0.7, fontSize: "13px", lineHeight: 1, padding: "0 2px", display: "flex", alignItems: "center" }}
                        >✕</button>
                      </span>
                    )}
                    {result.detected_song && <span className="freq-tag" style={{ color: "#fde68a", borderColor: "rgba(253,230,138,0.4)" }}>TRACK: {result.detected_song}</span>}
                    {overrideGenre && <span className="freq-tag" style={{ color: "#d97706", borderColor: "rgba(217,119,6,0.4)" }}>OVERRIDE: {overrideGenre}</span>}

                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", justifyContent: "center", marginTop: "4px" }}>
                        {result.genres.map((g, idx) => {
                            if (result.dominant_vibe === 'Direct Search') return null;
                            const isSelected = overrideGenre.toLowerCase() === g.toLowerCase();
                            const isApplying = loading && loadReason === "genre" && isSelected;
                            return (
                                <button
                                    key={idx}
                                    onClick={() => { analyzeVibe({ isFilterClick: true, targetGenre: isSelected ? "" : g }); }}
                                    disabled={loading}
                                    className="freq-tag dial-btn"
                                    title={isSelected ? "Click to remove filter — will re-run" : `Re-run filtered strictly by ${g}`}
                                    style={{
                                        color: isSelected ? "#1a0e04" : "rgba(180,140,80,0.7)",
                                        borderColor: isSelected ? "#d97706" : "rgba(180,140,80,0.3)",
                                        background: isSelected ? "#d97706" : "transparent",
                                        cursor: loading ? "default" : "pointer",
                                        boxShadow: isSelected ? "0 0 10px rgba(217,119,6,0.5)" : "none",
                                        transition: "all 0.2s ease",
                                        display: "flex", alignItems: "center", gap: "5px",
                                        opacity: loading && !isApplying ? 0.5 : 1,
                                    }}
                                >
                                    {isApplying && (
                                      <div style={{ width: "8px", height: "8px", border: "1.5px solid rgba(26,14,4,0.4)", borderTopColor: "#1a0e04", borderRadius: "50%", animation: "spin 0.7s linear infinite", flexShrink: 0 }} />
                                    )}
                                    {isSelected ? `✓ ${g}` : g}
                                </button>
                            );
                        })}
                    </div>
                    {result.genres.length > 0 && result.dominant_vibe !== 'Direct Search' && !loading && (
                      <span style={{ fontSize: "8px", color: "rgba(180,140,80,0.3)", letterSpacing: "0.08em", marginTop: "2px" }}>
                        ↑ click any genre to re-run with that filter
                      </span>
                    )}
                    {loading && loadReason === "genre" && (
                      <span style={{ fontSize: "8px", color: "rgba(217,160,60,0.6)", letterSpacing: "0.08em", marginTop: "2px" }}>
                        Re-fetching with genre filter…
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* ── GENERATED PLAYLIST UI ── */}
              {result.tracks && result.tracks.length > 0 && (
                <div className="panel-card screws" style={{ padding: "24px", marginTop: "16px" }}>
                  <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(120,80,20,0.015) 10px, rgba(120,80,20,0.015) 11px)", pointerEvents: "none", borderRadius: "16px" }} />
                  <div style={{ position: "relative" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", flexWrap: "wrap", gap: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <IconDisc />
                        <span style={S.cardLabel}>Generated Playlist</span>
                        {tasteProfile.totalSignals >= 2 && (
                          <span style={{ fontSize: "9px", padding: "2px 7px", borderRadius: "4px", background: `${activeColor}18`, border: `1px solid ${activeColor}44`, color: activeColor, fontFamily: "'DM Mono', monospace", letterSpacing: "0.1em" }}>
                            <IconBrain /> PERSONALISED
                          </span>
                        )}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                        <span style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "rgba(180,140,80,0.5)" }}>
                          {selectionMode && selectedTracks.size > 0
                            ? `${selectedTracks.size} / ${result.tracks.length} SELECTED`
                            : `${result.tracks.length} TRACKS`}
                        </span>

                        {/* Select mode toggle */}
                        <button
                          onClick={() => { setSelectionMode(m => !m); setSelectedTracks(new Set()); }}
                          className="dial-btn"
                          title={selectionMode ? "Exit selection mode" : "Select tracks to save"}
                          style={{
                            display: "flex", alignItems: "center", gap: "5px",
                            padding: "5px 10px", borderRadius: "6px", fontSize: "10px",
                            fontFamily: "'DM Mono', monospace", letterSpacing: "0.06em",
                            textTransform: "uppercase", cursor: "pointer", transition: "all 0.2s",
                            background: selectionMode ? `${activeColor}22` : "rgba(120,80,20,0.1)",
                            border: `1px solid ${selectionMode ? activeColor : "rgba(120,80,20,0.3)"}`,
                            color: selectionMode ? activeColor : "rgba(180,140,80,0.55)",
                          }}
                        >
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                          {selectionMode ? "Done" : "Select"}
                        </button>

                        {token && (
                          <button
                            onClick={() => setShowPlaylistPanel(true)}
                            className="dial-btn"
                            title={selectionMode && selectedTracks.size > 0 ? `Save ${selectedTracks.size} selected` : "Save this playlist"}
                            style={{
                              display: "flex", alignItems: "center", gap: "5px",
                              padding: "5px 10px", borderRadius: "6px", fontSize: "10px",
                              fontFamily: "'DM Mono', monospace", letterSpacing: "0.06em",
                              textTransform: "uppercase", cursor: "pointer",
                              background: "rgba(217,119,6,0.12)",
                              border: "1px solid rgba(217,119,6,0.35)",
                              color: "#d97706", transition: "all 0.2s",
                            }}
                          >
                            <IconBookmark />
                            {selectionMode && selectedTracks.size > 0 ? `Save (${selectedTracks.size})` : "Save"}
                          </button>
                        )}

                        <CopyPlaylistButton
                          tracks={selectionMode && selectedTracks.size > 0
                            ? result.tracks.filter(t => selectedTracks.has(`${t.title}|${t.artist}`))
                            : result.tracks}
                          activeColor={activeColor}
                        />
                        <a
                          href={`https://open.spotify.com/search/${encodeURIComponent(
                            result.tracks.slice(0, 1).map(t => `${t.title} ${t.artist}`).join(" ")
                          )}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          title="Search this playlist on Spotify"
                          className="dial-btn"
                          style={{
                            display: "flex", alignItems: "center", gap: "5px",
                            padding: "5px 10px", borderRadius: "6px", fontSize: "10px",
                            fontFamily: "'DM Mono', monospace", letterSpacing: "0.06em",
                            textDecoration: "none", textTransform: "uppercase",
                            background: "rgba(29,185,84,0.12)",
                            border: "1px solid rgba(29,185,84,0.35)",
                            color: "#1db954",
                          }}
                        >
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
                          Spotify
                        </a>
                      </div>
                    </div>

                    {/* Feedback micro-toast */}
                    {feedbackToast && (
                      <div className="animate-in" style={{
                        fontSize: "10px", color: "#34d399", fontFamily: "'DM Mono', monospace",
                        letterSpacing: "0.08em", marginBottom: "10px", marginTop: "-6px",
                        display: "flex", alignItems: "center", gap: "6px",
                      }}>
                        <span style={{ fontSize: "12px" }}>✓</span> Noted — improving future results
                      </div>
                    )}

                    {/* Remove + retry toast */}
                    {retryingTrack && (
                      <div className="animate-in" style={{
                        fontSize: "10px", color: "#fb923c", fontFamily: "'DM Mono', monospace",
                        letterSpacing: "0.08em", marginBottom: "10px", marginTop: "-6px",
                        display: "flex", alignItems: "center", gap: "6px",
                      }}>
                        <span style={{ fontSize: "12px" }}>✕</span>
                        Removed <strong style={{ color: "#fde68a" }}>{retryingTrack}</strong> — run again to pull a replacement
                      </div>
                    )}

                    {/* Selection mode hint */}
                    {selectionMode && (
                      <div style={{
                        fontSize: "10px", color: activeColor, fontFamily: "'DM Mono', monospace",
                        letterSpacing: "0.08em", marginBottom: "10px", marginTop: "-4px",
                        display: "flex", alignItems: "center", gap: "6px",
                        padding: "6px 10px", background: `${activeColor}0d`,
                        border: `1px solid ${activeColor}30`, borderRadius: "6px",
                      }}>
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                        Tap tracks to select — only selected tracks will be saved
                      </div>
                    )}

                    {/* ── LANGUAGE MISMATCH WARNING ── */}
                    {(() => {
                      const selectedLang = language;
                      const nonEnglishLangs = ["Hindi","Punjabi","Tamil","Telugu","Kannada","Malayalam","Bengali","Urdu","Korean","Japanese","Spanish","Portuguese","French","Arabic","Afrobeats"];
                      const isNonEnglish = nonEnglishLangs.includes(selectedLang);
                      const englishHeavyVibes = ["chill","calm","ambient","focus","dreamy","cinematic","indie_folk","heartbreak","dark","retro"];
                      const isEnglishHeavyVibe = englishHeavyVibes.includes(result.dominant_vibe);
                      const noArtistLock = !result.detected_artist;
                      const showMismatchWarning = isNonEnglish && isEnglishHeavyVibe && noArtistLock;

                      if (!showMismatchWarning) return null;
                      return (
                        <div style={{
                          display: "flex", alignItems: "flex-start", gap: "10px",
                          padding: "12px 14px", marginBottom: "16px",
                          background: "rgba(180,120,0,0.08)",
                          border: "1px solid rgba(217,119,6,0.25)",
                          borderRadius: "8px",
                        }}>
                          <span style={{ fontSize: "14px", flexShrink: 0 }}>⚠</span>
                          <div style={{ fontSize: "11px", color: "rgba(217,160,60,0.85)", lineHeight: "1.6", fontFamily: "'DM Mono', monospace" }}>
                            <strong style={{ color: "#fde68a" }}>Limited {selectedLang} pool for this vibe.</strong>
                            {" "}The "{result.dominant_vibe}" mood has sparse coverage in {selectedLang} on Last.fm — showing closest global matches instead.
                            <br />
                            <span style={{ color: "rgba(180,140,80,0.6)", fontSize: "10px" }}>
                              Try: switching Language → <strong>Any</strong>, or use Pro Mode to force a {selectedLang} artist directly.
                            </span>
                          </div>
                        </div>
                      );
                    })()}

                    <div style={{ height: "1px", background: `linear-gradient(90deg, ${activeColor}33, transparent)`, marginBottom: "16px" }} />

                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {result.tracks.map((track, i) => {
                        const trackKey    = `${track.title}|${track.artist}`;
                        const isPlaying   = playingTrack === track.preview_url;
                        const isSelected  = selectedTracks.has(trackKey);
                        const isSuppressed  = (tasteProfile.suppressedTracks[trackKey] || 0) >= 3;
                        const isLikedArtist = (tasteProfile.likedArtists[track.artist] || 0) >= 2;
                        const isHovered   = hoveredTrackIdx === i;
                        // Build "why this track" reason string
                        const whyReasons = [];
                        if (isLikedArtist) whyReasons.push(`You liked ${track.artist} before`);
                        if (track.vibe_score) whyReasons.push(`Vibe match: ${Math.round(track.vibe_score * 100)}%`);
                        if (result.detected_artist) whyReasons.push(`Artist locked: ${result.detected_artist}`);
                        if (track.mood_match) whyReasons.push(track.mood_match);
                        return (
                          <div
                            key={trackKey}
                            className="app-track-row"
                            onMouseEnter={() => setHoveredTrackIdx(i)}
                            onMouseLeave={() => setHoveredTrackIdx(null)}
                            style={{
                              display: "flex", alignItems: "center", gap: "8px", flexWrap: "nowrap",
                              padding: "12px 16px",
                              background: isSelected ? `${activeColor}0d` : isSuppressed ? "rgba(60,10,10,0.4)" : "rgba(8,5,2,0.6)",
                              border: `1px solid ${isPlaying ? activeColor : isSelected ? activeColor : isLikedArtist ? `${activeColor}55` : isSuppressed ? 'rgba(180,40,40,0.2)' : 'rgba(120,80,20,0.25)'}`,
                              borderRadius: "10px", transition: "all 0.2s", minHeight: 0, position: "relative",
                            }}>

                            {/* ── CHECKBOX (selection mode only) ── */}
                            {selectionMode && (
                              <button
                                onClick={() => setSelectedTracks(prev => {
                                  const next = new Set(prev);
                                  next.has(trackKey) ? next.delete(trackKey) : next.add(trackKey);
                                  return next;
                                })}
                                style={{
                                  flexShrink: 0, width: 20, height: 20, borderRadius: 5,
                                  border: `2px solid ${isSelected ? activeColor : "rgba(160,110,30,0.4)"}`,
                                  background: isSelected ? activeColor : "transparent",
                                  display: "flex", alignItems: "center", justifyContent: "center",
                                  cursor: "pointer", transition: "all 0.15s",
                                }}
                              >
                                {isSelected && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="3" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>}
                              </button>
                            )}
                            {/* PHASE 8: Personalisation badges */}
                            {isLikedArtist && (
                              <div style={{ position: "absolute", top: 6, right: 8, display: "flex", gap: "4px", alignItems: "center" }}>
                                <span style={{ fontSize: "9px", color: activeColor, fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em", opacity: 0.8 }}>LIKED ARTIST</span>
                                <span style={{ color: "#fbbf24" }}><IconStar /></span>
                              </div>
                            )}
                            {isSuppressed && (
                              <div style={{ position: "absolute", top: 6, right: 8 }}>
                                <span style={{ fontSize: "9px", color: "#f87171", fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em" }}>AUTO-SUPPRESSED</span>
                              </div>
                            )}
                            {/* PHASE 8: Why this track tooltip */}
                            {isHovered && whyReasons.length > 0 && (
                              <div style={{
                                position: "absolute", bottom: "calc(100% + 6px)", left: "16px", zIndex: 50,
                                background: "rgba(12,7,2,0.95)", border: `1px solid ${activeColor}44`,
                                borderRadius: "8px", padding: "8px 12px", minWidth: "180px", maxWidth: "280px",
                                boxShadow: `0 4px 20px rgba(0,0,0,0.8), 0 0 10px ${activeColor}22`,
                                pointerEvents: "none",
                              }}>
                                <div style={{ fontSize: "9px", color: "rgba(180,140,80,0.5)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: "6px", display: "flex", alignItems: "center", gap: "5px" }}>
                                  <IconHelpCircle /> Why this track?
                                </div>
                                {whyReasons.map((r, ri) => (
                                  <div key={ri} style={{ fontSize: "11px", color: "rgba(220,190,140,0.85)", lineHeight: "1.5", display: "flex", alignItems: "center", gap: "5px" }}>
                                    <span style={{ color: activeColor, fontSize: "8px" }}>▸</span> {r}
                                  </div>
                                ))}
                              </div>
                            )}
                            {/* Track Info & Cover Art */}
                            <div
                              className="app-track-meta"
                              style={{ display: "flex", alignItems: "center", gap: "12px", flex: "1 1 0", minWidth: 0, overflow: "hidden", cursor: selectionMode ? "pointer" : "default" }}
                              onClick={selectionMode ? () => setSelectedTracks(prev => {
                                const next = new Set(prev);
                                next.has(trackKey) ? next.delete(trackKey) : next.add(trackKey);
                                return next;
                              }) : undefined}
                            >
                              {track.cover_art ? (
                                <img src={track.cover_art} alt="Cover" className="app-track-art" style={{ width: 44, height: 44, borderRadius: 6, boxShadow: '0 2px 8px rgba(0,0,0,0.5)', flexShrink: 0, objectFit: "cover" }} />
                              ) : (
                                <div className="app-track-art" style={{ width: 44, height: 44, borderRadius: 6, background: 'rgba(120,80,20,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><IconDisc /></div>
                              )}
                              <div style={{ display: "flex", flexDirection: "column", gap: "3px", minWidth: 0, flex: 1, overflow: "hidden" }}>
                                <span style={{ fontSize: "14px", fontWeight: 700, color: "#fde68a", fontFamily: "'Playfair Display', serif", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>{track.title}</span>
                                <span style={{ fontSize: "11px", color: "rgba(180,140,80,0.7)", letterSpacing: "0.05em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>{track.artist}</span>
                              </div>
                            </div>

                            {/* Track Actions */}
                            <div className="app-track-actions" style={{ display: "flex", gap: "6px", alignItems: "center", flexShrink: 0, flexWrap: "nowrap" }}>
                              {(() => {
                                const fbKey = `${track.title}|${track.artist}`;
                                const given = feedbackGiven[fbKey];
                                return (
                                  <div style={{ display: "flex", gap: "4px" }}>
                                    <button
                                      onClick={() => submitFeedback(track, i + 1, 1)}
                                      className="dial-btn"
                                      title="Good match"
                                      style={{
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        width: "32px", height: "32px", borderRadius: "8px", border: "1px solid",
                                        background: given === 1 ? "rgba(52,211,153,0.2)" : "rgba(120,80,20,0.1)",
                                        borderColor: given === 1 ? "#34d399" : "rgba(160,110,30,0.42)",
                                        color: given === 1 ? "#34d399" : "rgba(180,140,80,0.4)",
                                        cursor: "pointer", transition: "all 0.15s",
                                        boxShadow: given === 1 ? "0 0 8px rgba(52,211,153,0.3)" : "none",
                                      }}
                                    >
                                      <IconThumbUp />
                                    </button>
                                    <button
                                      onClick={() => submitFeedback(track, i + 1, -1)}
                                      className="dial-btn"
                                      title="Bad match"
                                      style={{
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        width: "32px", height: "32px", borderRadius: "8px", border: "1px solid",
                                        background: given === -1 ? "rgba(248,113,113,0.2)" : "rgba(120,80,20,0.1)",
                                        borderColor: given === -1 ? "#f87171" : "rgba(160,110,30,0.42)",
                                        color: given === -1 ? "#f87171" : "rgba(180,140,80,0.4)",
                                        cursor: "pointer", transition: "all 0.15s",
                                        boxShadow: given === -1 ? "0 0 8px rgba(248,113,113,0.3)" : "none",
                                      }}
                                    >
                                      <IconThumbDown />
                                    </button>
                                  </div>
                                );
                              })()}

                              <button
                                onClick={() => togglePlay(track.preview_url)}
                                disabled={!track.preview_url}
                                className="dial-btn app-track-preview"
                                style={{
                                  ...S.authBtn(false),
                                  padding: "8px 14px",
                                  background: isPlaying ? "rgba(217,119,6,0.2)" : "rgba(120,80,20,0.15)",
                                  borderColor: isPlaying ? "#d97706" : "rgba(120,80,20,0.4)",
                                  color: isPlaying ? "#fde68a" : "rgba(180,140,80,0.8)",
                                  opacity: track.preview_url ? 1 : 0.4
                                }}
                              >
                                {isPlaying ? <IconPause /> : <IconPlay />}
                                {isPlaying ? "Playing" : "Preview"}
                              </button>

                              <a
                                href={track.spotify_uri}
                                className="dial-btn"
                                style={{
                                  ...S.authBtn(false),
                                  padding: "8px 14px",
                                  textDecoration: "none",
                                  background: "rgba(29, 185, 84, 0.15)",
                                  borderColor: "rgba(29, 185, 84, 0.4)",
                                  color: "#1db954"
                                }}
                              >
                                Spotify
                              </a>

                              {/* ── REMOVE BUTTON ── */}
                              {!selectionMode && (
                                <button
                                  onClick={() => removeTrackAndRetry(track)}
                                  className="dial-btn"
                                  title="Remove this track — run again to get a replacement"
                                  style={{
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    width: 30, height: 30, borderRadius: 7, flexShrink: 0,
                                    border: "1px solid rgba(248,113,113,0.25)",
                                    background: "rgba(248,113,113,0.07)",
                                    color: "rgba(248,113,113,0.55)",
                                    cursor: "pointer", transition: "all 0.15s",
                                  }}
                                >
                                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* NEURAL BREAKDOWN */}
              {result.dominant_vibe !== 'Direct Search' && (
                <div className="panel-card" style={{ padding: "24px", marginTop: "16px" }}>
                  <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(90deg, transparent, transparent 11px, rgba(120,80,20,0.025) 11px, rgba(120,80,20,0.025) 12px)", pointerEvents: "none", borderRadius: "16px" }} />
                  <div style={{ position: "relative" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <span style={S.cardLabel}>Neural Match Breakdown</span>
                      </div>
                    </div>
                    <div style={{ height: "1px", background: `linear-gradient(90deg, ${activeColor}33, transparent)`, marginBottom: "16px", width: "100%" }} />

                    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                      {(result.matched_keywords || []).length > 0
                        ? (result.matched_keywords || []).map((kw, idx) => (
                            <span
                              key={idx}
                              style={{
                                padding: "5px 12px",
                                background: "rgba(16,10,4,0.80)",
                                border: `1px solid ${activeColor}33`,
                                borderRadius: "6px",
                                fontSize: "11px",
                                fontFamily: "'DM Mono', monospace",
                                color: "rgba(180,140,80,0.75)",
                                letterSpacing: "0.05em",
                              }}>
                                #{kw}
                            </span>
                          ))
                        : <span style={{ fontSize: "12px", color: "rgba(120,80,20,0.5)", fontStyle: "italic" }}>Universal mood detected — falling back to ambient processing.</span>
                      }
                    </div>
                  </div>
                </div>
              )}

              {/* PHASE 8: TASTE PROFILE PANEL */}
              {tasteProfile.totalSignals >= 2 && (
                <div className="panel-card" style={{ padding: "20px", marginTop: "16px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ color: activeColor }}><IconBrain /></span>
                      <span style={{ fontSize: "10px", letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.6)", fontFamily: "'DM Mono', monospace" }}>Session Taste Profile</span>
                    </div>
                    <button
                      onClick={() => setShowTasteProfile(p => !p)}
                      className="dial-btn"
                      style={{ background: "none", border: `1px solid rgba(120,80,20,0.3)`, borderRadius: "4px", padding: "3px 8px", fontSize: "9px", color: "rgba(180,140,80,0.5)", fontFamily: "'DM Mono', monospace", letterSpacing: "0.1em", cursor: "pointer" }}
                    >
                      {showTasteProfile ? "HIDE" : "SHOW"}
                    </button>
                  </div>
                  <div style={{ height: "1px", background: `linear-gradient(90deg, ${activeColor}33, transparent)`, marginBottom: "14px" }} />
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
                    <span style={{ fontSize: "10px", color: "rgba(120,80,20,0.6)", fontFamily: "'DM Mono', monospace" }}>{tasteProfile.totalSignals} signal{tasteProfile.totalSignals !== 1 ? "s" : ""} logged</span>
                    {Object.entries(tasteProfile.likedArtists).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([artist, count]) => (
                      <span key={artist} style={{ padding: "3px 10px", background: `${activeColor}11`, border: `1px solid ${activeColor}33`, borderRadius: "20px", fontSize: "10px", color: activeColor, fontFamily: "'DM Mono', monospace", display: "flex", alignItems: "center", gap: "4px" }}>
                        <IconStar /> {artist} ×{count}
                      </span>
                    ))}
                    {Object.keys(tasteProfile.suppressedTracks).filter(k => tasteProfile.suppressedTracks[k] >= 3).length > 0 && (
                      <span style={{ padding: "3px 10px", background: "rgba(180,40,40,0.1)", border: "1px solid rgba(180,40,40,0.25)", borderRadius: "20px", fontSize: "10px", color: "#f87171", fontFamily: "'DM Mono', monospace" }}>
                        {Object.keys(tasteProfile.suppressedTracks).filter(k => tasteProfile.suppressedTracks[k] >= 3).length} suppressed
                      </span>
                    )}
                  </div>
                  {showTasteProfile && (
                    <div style={{ marginTop: "14px", display: "flex", flexDirection: "column", gap: "10px" }}>
                      {Object.keys(tasteProfile.likedVibes).length > 0 && (
                        <div>
                          <div style={{ fontSize: "9px", color: "rgba(120,80,20,0.5)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: "6px" }}>Favoured Vibes</div>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                            {Object.entries(tasteProfile.likedVibes).sort((a,b)=>b[1]-a[1]).map(([vibe, count]) => (
                              <span key={vibe} style={{ padding: "3px 10px", background: "rgba(120,80,20,0.12)", border: "1px solid rgba(180,140,80,0.2)", borderRadius: "20px", fontSize: "10px", color: "rgba(220,190,140,0.8)", fontFamily: "'DM Mono', monospace" }}>
                                {vibe} ({count})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {Object.entries(tasteProfile.dislikedArtists).filter(([,v])=>v>=2).length > 0 && (
                        <div>
                          <div style={{ fontSize: "9px", color: "rgba(120,80,20,0.5)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: "6px" }}>Low Signal Artists</div>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                            {Object.entries(tasteProfile.dislikedArtists).filter(([,v])=>v>=2).map(([artist, count]) => (
                              <span key={artist} style={{ padding: "3px 10px", background: "rgba(60,10,10,0.2)", border: "1px solid rgba(180,40,40,0.2)", borderRadius: "20px", fontSize: "10px", color: "rgba(180,80,80,0.7)", fontFamily: "'DM Mono', monospace" }}>
                                {artist} (−{count})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      <button
                        onClick={() => setTasteProfile({ likedArtists: {}, dislikedArtists: {}, likedVibes: {}, suppressedTracks: {}, totalSignals: 0 })}
                        className="dial-btn"
                        style={{ alignSelf: "flex-start", background: "none", border: "1px solid rgba(120,80,20,0.25)", borderRadius: "4px", padding: "4px 10px", fontSize: "9px", color: "rgba(120,80,20,0.6)", fontFamily: "'DM Mono', monospace", letterSpacing: "0.1em", cursor: "pointer" }}
                      >
                        RESET PROFILE
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* PHASE 8: VIBE HISTORY CHIPS */}
              {vibeHistory.length >= 2 && (
                <div style={{ marginTop: "16px", display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                  <span style={{ fontSize: "9px", color: "rgba(120,80,20,0.5)", letterSpacing: "0.15em", textTransform: "uppercase", fontFamily: "'DM Mono', monospace", display: "flex", alignItems: "center", gap: "5px" }}>
                    <IconHistory /> Recent
                  </span>
                  {vibeHistory.slice(0, 6).map((h, idx) => (
                    <button
                      key={idx}
                      onClick={() => { setPrompt(h.prompt); }}
                      className="dial-btn"
                      title={`Re-run: "${h.prompt}"`}
                      style={{
                        padding: "3px 10px", background: "rgba(20,12,4,0.6)",
                        border: `1px solid ${vibeColors[h.vibe] || 'rgba(120,80,20,0.3)'}44`,
                        borderRadius: "20px", fontSize: "10px",
                        color: vibeColors[h.vibe] || "rgba(180,140,80,0.6)",
                        fontFamily: "'DM Mono', monospace", cursor: "pointer",
                        opacity: idx === 0 ? 1 : 0.6 - idx * 0.05,
                      }}
                    >
                      {h.vibe}
                    </button>
                  ))}
                </div>
              )}

              <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "28px", opacity: 0.4 }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", border: "1px solid rgba(120,80,20,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}><div style={{ width: "8px", height: "8px", borderRadius: "50%", background: activeColor }} /></div>
                <div style={{ flex: 1, height: "6px", borderRadius: "3px", background: "rgba(80,50,10,0.4)", overflow: "hidden" }}><div style={{ height: "100%", width: "100%", background: `repeating-linear-gradient(90deg, ${activeColor}33 0px, ${activeColor}33 2px, transparent 2px, transparent 10px)` }} /></div>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", border: "1px solid rgba(120,80,20,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}><div style={{ width: "8px", height: "8px", borderRadius: "50%", background: activeColor }} /></div>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* ── PLAYLIST PANEL (slide-in drawer) ─────────────────────── */}
      {showPlaylistPanel && (
        <PlaylistPanel
          token={token}
          buildApiUrl={buildApiUrl}
          onClose={() => setShowPlaylistPanel(false)}
          currentResult={result}
          currentPrompt={prompt}
          onLoadPrompt={(p) => { setPrompt(p); setShowPlaylistPanel(false); }}
          onPlaylistSaved={() => setPlaylistSaveCount(c => c + 1)}
          saveCount={playlistSaveCount}
          activeColor={activeColor}
          selectedTracks={selectionMode && selectedTracks.size > 0 ? selectedTracks : null}
        />
      )}
    </>
  );
}
