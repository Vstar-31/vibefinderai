/**
 * RefinementBar.jsx
 * VibeFinderAI Phase 9 — Conversational refinement
 * Place in: frontend/src/components/RefinementBar.jsx
 *
 * Appears below results and lets users refine without retyping.
 * Two interaction modes:
 *   1. Quick gesture pills — contextual shortcuts based on current vibe
 *   2. Free-text refinement input — "more underground", "only Hindi", etc.
 *
 * Usage:
 *   <RefinementBar
 *     originalPrompt={request.text}
 *     currentVibe={response.dominant_vibe}
 *     currentLanguage={currentLanguage}
 *     onRefine={(newRequest) => handleSubmit(newRequest)}
 *   />
 *
 * onRefine receives a partial VibeRequest object with:
 *   { text, refinement_of, refinement_instruction, language?, nicheness? }
 * Merge this with your existing VibeRequest before POSTing.
 */

import React, { useState, useRef } from "react";

// Contextual quick gestures — vary by dominant_vibe
const GESTURE_MAP = {
  party:      ["More underground", "Slower tempo", "Add chill", "Less mainstream"],
  hype:       ["More aggressive", "Slow it down", "Add bass", "More niche"],
  indie_folk: ["More acoustic", "Add dark", "More upbeat", "Deeper cuts only"],
  chill:      ["More dreamy", "Add jazz", "Late night only", "More lo-fi"],
  heartbreak: ["Less sad", "Add anger", "More bittersweet", "Slow and raw"],
  romantic:   ["More dreamy", "Add heartbreak", "Instrumental only", "Deeper cuts"],
  dark:       ["Less intense", "Add ambience", "More electronic", "Experimental only"],
  dreamy:     ["More ethereal", "Add melancholy", "Less ambient", "Vocals upfront"],
  focus:      ["More ambient", "No vocals", "Add energy", "Deeper cuts"],
  soulful:    ["More vintage", "Add jazz", "More emotional", "Live recordings"],
  intense:    ["Less aggressive", "Add melody", "More technical", "Underground only"],
  rock:       ["More aggressive", "Add acoustic", "More obscure", "Less mainstream"],
  euphoric:   ["More building", "Add darkness", "Less anthem", "Festival ready"],
  happy:      ["More upbeat", "Add nostalgia", "More indie", "Party ready"],
  retro:      ["More obscure", "Add modern", "Specific decade?", "Deeper cuts"],
  cinematic:  ["More epic", "Add darkness", "Instrumental only", "Less mainstream"],
  ambient:    ["Add rhythm", "More drone", "Less ambient", "Nature sounds"],
  hyperpop:   ["More chaotic", "Less distorted", "Add melody", "Deeper cuts"],
  calm:       ["More ambient", "Add piano", "More meditative", "No vocals"],
  default:    ["More underground", "Slower", "More energetic", "Different language"],
};

// Language quick-switch pills (show if prompt has no specific language)
const LANG_GESTURES = [
  "Hindi only", "English only", "Korean only", "Tamil only",
  "Japanese only", "Punjabi only", "Arabic only", "Spanish only",
];

function GesturePill({ label, onClick, active }) {
  return (
    <button
      onClick={() => onClick(label)}
      style={{
        padding: "5px 12px",
        borderRadius: "99px",
        border: active
          ? "1.5px solid var(--color-border-info, #378ADD)"
          : "0.5px solid var(--color-border-secondary, rgba(0,0,0,0.2))",
        background: active
          ? "var(--color-background-info, rgba(55,138,221,0.08))"
          : "var(--color-background-primary, #fff)",
        color: active
          ? "var(--color-text-info, #185FA5)"
          : "var(--color-text-secondary, #555)",
        fontSize: "12px",
        cursor: "pointer",
        whiteSpace: "nowrap",
        transition: "all 0.15s",
        fontFamily: "inherit",
      }}
    >
      {label}
    </button>
  );
}

export default function RefinementBar({
  originalPrompt,
  currentVibe = "default",
  currentLanguage = "Any",
  onRefine,
  style = {},
}) {
  const [inputValue, setInputValue] = useState("");
  const [activePill, setActivePill] = useState(null);
  const [showLangGestures, setShowLangGestures] = useState(false);
  const inputRef = useRef(null);

  const gestures = GESTURE_MAP[currentVibe] || GESTURE_MAP.default;

  const handleGesture = (gesture) => {
    if (activePill === gesture) {
      // Toggle off
      setActivePill(null);
      setInputValue("");
      return;
    }
    setActivePill(gesture);
    setInputValue(gesture.toLowerCase());

    // Auto-submit pill gestures immediately
    onRefine({
      text: originalPrompt,
      refinement_of: originalPrompt,
      refinement_instruction: gesture.toLowerCase(),
    });
  };

  const handleInputSubmit = () => {
    const instruction = inputValue.trim();
    if (!instruction) return;
    setActivePill(null);
    onRefine({
      text: originalPrompt,
      refinement_of: originalPrompt,
      refinement_instruction: instruction,
    });
    setInputValue("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleInputSubmit();
    }
  };

  if (!originalPrompt) return null;

  return (
    <div
      style={{
        marginTop: "16px",
        paddingTop: "14px",
        borderTop: "0.5px solid var(--color-border-tertiary, rgba(0,0,0,0.1))",
        ...style,
      }}
    >
      <div
        style={{
          fontSize: "11px",
          fontWeight: 500,
          color: "var(--color-text-tertiary, #888)",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
          marginBottom: "8px",
        }}
      >
        Refine this
      </div>

      {/* Quick gesture pills */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "6px",
          marginBottom: "10px",
        }}
      >
        {gestures.map((g) => (
          <GesturePill
            key={g}
            label={g}
            active={activePill === g}
            onClick={handleGesture}
          />
        ))}
        {currentLanguage === "Any" && (
          <GesturePill
            label="Language..."
            active={showLangGestures}
            onClick={() => setShowLangGestures((v) => !v)}
          />
        )}
      </div>

      {/* Language sub-gestures */}
      {showLangGestures && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "6px",
            marginBottom: "10px",
            paddingLeft: "8px",
            borderLeft: "2px solid var(--color-border-tertiary, rgba(0,0,0,0.08))",
          }}
        >
          {LANG_GESTURES.map((g) => (
            <GesturePill
              key={g}
              label={g}
              active={activePill === g}
              onClick={handleGesture}
            />
          ))}
        </div>
      )}

      {/* Free-text refinement input */}
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            if (activePill) setActivePill(null);
          }}
          onKeyDown={handleKeyDown}
          placeholder='Or type anything… "more raw", "only from the 90s", "skip the ballads"'
          style={{
            flex: 1,
            padding: "8px 12px",
            fontSize: "13px",
            borderRadius: "8px",
            border: "0.5px solid var(--color-border-secondary, rgba(0,0,0,0.2))",
            background: "var(--color-background-primary, #fff)",
            color: "var(--color-text-primary, #000)",
            fontFamily: "inherit",
            outline: "none",
          }}
        />
        <button
          onClick={handleInputSubmit}
          disabled={!inputValue.trim()}
          style={{
            padding: "8px 16px",
            borderRadius: "8px",
            border: "0.5px solid var(--color-border-secondary, rgba(0,0,0,0.2))",
            background: inputValue.trim()
              ? "var(--color-text-primary, #000)"
              : "var(--color-background-secondary, #f5f5f5)",
            color: inputValue.trim()
              ? "var(--color-background-primary, #fff)"
              : "var(--color-text-tertiary, #888)",
            fontSize: "13px",
            cursor: inputValue.trim() ? "pointer" : "not-allowed",
            fontFamily: "inherit",
            transition: "all 0.15s",
            whiteSpace: "nowrap",
          }}
        >
          Refine ↗
        </button>
      </div>
    </div>
  );
}
