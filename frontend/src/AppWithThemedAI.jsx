import { useCallback, useEffect, useState } from "react";
import App from "./App.jsx";
import ThemedAIEmbed from "./ThemedAIEmbed.jsx";

export default function AppWithThemedAI({ onNavigate }) {
  const [themedOpen, setThemedOpen] = useState(false);
  const [currentPrompt, setCurrentPrompt] = useState("");
  const [lastThemedState, setLastThemedState] = useState(null);

  useEffect(() => {
    const syncPrompt = (event) => {
      const target = event.target;
      if (!(target instanceof HTMLTextAreaElement)) return;
      if (!target.closest(".app-panel")) return;
      setCurrentPrompt(target.value);
    };
    document.addEventListener("input", syncPrompt, true);
    return () => document.removeEventListener("input", syncPrompt, true);
  }, []);

  useEffect(() => {
    if (!themedOpen) return;
    const textarea = document.querySelector(".app-panel textarea");
    if (textarea instanceof HTMLTextAreaElement) setCurrentPrompt(textarea.value);
  }, [themedOpen]);

  useEffect(() => {
    const onKey = (event) => {
      if (themedOpen) return;
      if (!event.ctrlKey && !event.metaKey) return;
      if (!event.shiftKey || event.key.toLowerCase() !== "t") return;
      event.preventDefault();
      setThemedOpen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [themedOpen]);

  useEffect(() => {
    const open = () => setThemedOpen(true);
    window.addEventListener("vibefinder:open-themedai", open);
    return () => window.removeEventListener("vibefinder:open-themedai", open);
  }, []);

  const handleThemedMessage = useCallback((message) => {
    if (message.type === "VIBEFINDER_STATE") setLastThemedState(message.state || null);
  }, []);

  const handleThemedAnalysis = useCallback((message) => {
    setLastThemedState((prev) => ({
      ...(prev || {}),
      vibe: message.vibe,
      trackCount: message.tracks || 0,
      loading: false,
    }));
  }, []);

  const handleThemedTheme = useCallback((accent) => {
    if (typeof accent === "string") document.documentElement.style.setProperty("--themedai-accent", accent);
  }, []);

  return (
    <>
      <App onNavigate={onNavigate} />

      <button
        type="button"
        className="vf-themedai-launcher"
        onClick={() => setThemedOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={themedOpen}
        title="Open Themed.AI workspace"
      >
        <span aria-hidden="true">✦</span>
        <span>Themed.AI</span>
        {lastThemedState?.trackCount ? <small>{lastThemedState.trackCount} live</small> : <small>Ctrl⇧T</small>}
      </button>

      <ThemedAIEmbed
        open={themedOpen}
        onClose={() => setThemedOpen(false)}
        initialPrompt={currentPrompt}
        onMessage={handleThemedMessage}
        onAnalysisComplete={handleThemedAnalysis}
        onThemeChange={handleThemedTheme}
      />
    </>
  );
}
