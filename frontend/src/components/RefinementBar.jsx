/**
 * RefinementBar.jsx — VibeFinderAI Phase 9
 * Matches the app's dark hardware aesthetic — amber/gold, DM Mono, panel-card.
 */
import React, { useState, useRef } from "react";

const GESTURE_MAP = {
  party:      ["More underground", "Slower", "Add chill", "Less mainstream"],
  hype:       ["More aggressive", "Slow it down", "Add bass", "More niche"],
  indie_folk: ["More acoustic", "Add dark edge", "More upbeat", "Deeper cuts"],
  chill:      ["More dreamy", "Add jazz", "Late night only", "More lo-fi"],
  heartbreak: ["Less sad", "Add anger", "More bittersweet", "Slow and raw"],
  romantic:   ["More dreamy", "Add heartbreak", "Instrumental only", "Deeper cuts"],
  dark:       ["Less intense", "More ambient", "More electronic", "Experimental only"],
  dreamy:     ["More ethereal", "Add melancholy", "Less ambient", "Vocals upfront"],
  focus:      ["More ambient", "No vocals", "Add energy", "Deeper cuts"],
  soulful:    ["More vintage", "Add jazz", "More emotional", "Live recordings"],
  intense:    ["Less aggressive", "Add melody", "More technical", "Underground only"],
  rock:       ["More aggressive", "Add acoustic", "More obscure", "Less mainstream"],
  euphoric:   ["More building", "Add darkness", "Less anthem", "Festival ready"],
  happy:      ["More upbeat", "Add nostalgia", "More indie", "Party ready"],
  retro:      ["More obscure", "Add modern feel", "Specific decade?", "Deeper cuts"],
  cinematic:  ["More epic", "Add darkness", "Instrumental only", "Less mainstream"],
  ambient:    ["Add rhythm", "More drone", "Less ambient", "More texture"],
  hyperpop:   ["More chaotic", "Less distorted", "Add melody", "Deeper cuts"],
  calm:       ["More ambient", "Add piano", "More meditative", "No vocals"],
  default:    ["More underground", "Slower", "More energetic", "Different language"],
};

const LANG_GESTURES = [
  "Hindi only", "English only", "Korean only", "Tamil only",
  "Japanese only", "Punjabi only", "Arabic only", "Spanish only",
];

function GesturePill({ label, onClick, active, activeColor }) {
  const col = activeColor || "#d97706";
  return (
    <button
      onClick={() => onClick(label)}
      style={{
        padding: "4px 12px", borderRadius: "4px",
        border: active ? `1px solid ${col}` : "1px solid rgba(120,80,20,0.35)",
        background: active ? `${col}22` : "rgba(20,12,4,0.5)",
        color: active ? col : "rgba(180,140,80,0.65)",
        fontSize: "10px", fontFamily: "'DM Mono', monospace",
        letterSpacing: "0.05em", cursor: "pointer",
        whiteSpace: "nowrap", transition: "all 0.15s", textTransform: "uppercase",
      }}
    >{label}</button>
  );
}

export default function RefinementBar({
  originalPrompt, currentVibe = "default",
  currentLanguage = "Any", activeColor = "#d97706", onRefine,
}) {
  const [inputValue, setInputValue] = useState("");
  const [activePill, setActivePill] = useState(null);
  const [showLang, setShowLang] = useState(false);
  const inputRef = useRef(null);
  const gestures = GESTURE_MAP[currentVibe] || GESTURE_MAP.default;

  const handleGesture = (g) => {
    if (activePill === g) { setActivePill(null); setInputValue(""); return; }
    setActivePill(g); setInputValue(g.toLowerCase());
    onRefine({ text: originalPrompt, refinement_of: originalPrompt, refinement_instruction: g.toLowerCase() });
  };

  const handleSubmit = () => {
    const inst = inputValue.trim();
    if (!inst) return;
    setActivePill(null);
    onRefine({ text: originalPrompt, refinement_of: originalPrompt, refinement_instruction: inst });
    setInputValue("");
  };

  if (!originalPrompt) return null;

  return (
    <div className="panel-card" style={{ padding: "14px 18px", marginTop: "16px", borderRadius: "12px", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(120,80,20,0.012) 10px, rgba(120,80,20,0.012) 11px)", pointerEvents: "none", borderRadius: "12px" }} />
      <div style={{ position: "relative" }}>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
          <span style={{ fontSize: "9px", letterSpacing: "0.2em", textTransform: "uppercase", color: "rgba(180,140,80,0.5)", fontFamily: "'DM Mono', monospace" }}>
            Refine this
          </span>
          <div style={{ flex: 1, height: "1px", background: `linear-gradient(90deg, ${activeColor}33, transparent)` }} />
        </div>

        {/* Quick pills */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "10px" }}>
          {gestures.map(g => (
            <GesturePill key={g} label={g} active={activePill === g} activeColor={activeColor} onClick={handleGesture} />
          ))}
          {currentLanguage === "Any" && (
            <GesturePill label="Language..." active={showLang} activeColor={activeColor} onClick={() => setShowLang(v => !v)} />
          )}
        </div>

        {/* Language sub-pills */}
        {showLang && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "10px", paddingLeft: "10px", borderLeft: `2px solid ${activeColor}33` }}>
            {LANG_GESTURES.map(g => (
              <GesturePill key={g} label={g} active={activePill === g} activeColor={activeColor} onClick={handleGesture} />
            ))}
          </div>
        )}

        {/* Free-text row */}
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <input
            ref={inputRef} type="text" value={inputValue}
            onChange={e => { setInputValue(e.target.value); if (activePill) setActivePill(null); }}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); handleSubmit(); } }}
            placeholder={'Or describe it… "more raw", "only 90s", "skip ballads"'}
            style={{
              flex: 1, padding: "7px 12px", fontSize: "11px",
              fontFamily: "'DM Mono', monospace", borderRadius: "6px",
              border: "1px solid rgba(120,80,20,0.3)", background: "rgba(10,6,2,0.6)",
              color: "rgba(220,190,140,0.9)", outline: "none", letterSpacing: "0.02em",
            }}
          />
          <button
            onClick={handleSubmit} disabled={!inputValue.trim()} className="dial-btn"
            style={{
              padding: "7px 14px", borderRadius: "6px",
              border: `1px solid ${inputValue.trim() ? activeColor : "rgba(120,80,20,0.3)"}`,
              background: inputValue.trim() ? `${activeColor}22` : "transparent",
              color: inputValue.trim() ? activeColor : "rgba(120,80,20,0.4)",
              fontSize: "10px", fontFamily: "'DM Mono', monospace",
              letterSpacing: "0.08em", textTransform: "uppercase",
              cursor: inputValue.trim() ? "pointer" : "default",
              transition: "all 0.15s", whiteSpace: "nowrap",
              display: "flex", alignItems: "center", gap: "5px",
            }}
          >
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="5 12 19 12"/><polyline points="12 5 19 12 12 19"/></svg>
            Refine
          </button>
        </div>
      </div>
    </div>
  );
}
