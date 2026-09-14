import { useCallback, useEffect, useState } from "react";
import App from "./App.jsx";
import ThemedAIEmbed from "./ThemedAIEmbed.jsx";

const postToThemedAIHost = (message) => {
  try {
    if (window.chrome?.webview) {
      window.chrome.webview.postMessage(JSON.stringify(message));
    }
  } catch {
    // Normal browsers do not expose chrome.webview; the app remains fully functional there.
  }
};

const setReactTextAreaValue = (element, value) => {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
  if (setter) setter.call(element, value);
  else element.value = value;
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
};

export default function AppWithThemedAI({ onNavigate }) {
  const [themedOpen, setThemedOpen] = useState(false);
  const [currentPrompt, setCurrentPrompt] = useState("");
  const [lastThemedState, setLastThemedState] = useState(null);

  useEffect(() => {
    // Tell WebView2 immediately that the VibeFinder app is alive. The desktop host uses this
    // instead of guessing whether the embedded page has actually mounted.
    postToThemedAIHost({
      type: "VIBEFINDER_APP_READY",
      hasToken: Boolean(localStorage.getItem("vf_token")),
    });

    // Commands from Themed.AI arrive through the WebView2 message channel. Keep this bridge at
    // the wrapper level so prompt/analyze commands work even when the full MusicPlayer is closed.
    const onHostMessage = (event) => {
      let message = event?.data;
      if (typeof message === "string") {
        try { message = JSON.parse(message); } catch { return; }
      }
      if (!message || typeof message !== "object") return;

      const command = message.command || message.type;
      if (command === "setPrompt") {
        const textarea = document.querySelector(".app-panel textarea");
        if (textarea instanceof HTMLTextAreaElement && typeof message.text === "string") {
          setReactTextAreaValue(textarea, message.text);
          textarea.focus();
          setCurrentPrompt(message.text);
          postToThemedAIHost({ type: "VIBEFINDER_COMMAND_RESULT", command: "setPrompt", success: true });
        }
        return;
      }

      if (command === "setTrackLimit") {
        const value = Number(message.value);
        if (!Number.isFinite(value)) return;
        const buttons = [...document.querySelectorAll(".app-track-controls button")];
        const trackButton = buttons.find((button) => button.textContent?.trim() === String(value));
        if (trackButton instanceof HTMLButtonElement && !trackButton.disabled) trackButton.click();
        return;
      }

      if (command === "runAnalysis") {
        const runButton = document.querySelector(".app-run-btn");
        if (runButton instanceof HTMLButtonElement) {
          if (runButton.disabled) {
            postToThemedAIHost({ type: "VIBEFINDER_COMMAND_RESULT", command: "runAnalysis", success: false, reason: "not_ready" });
          } else {
            runButton.click();
            postToThemedAIHost({ type: "VIBEFINDER_COMMAND_RESULT", command: "runAnalysis", success: true });
          }
        }
      }
    };

    if (window.chrome?.webview) window.chrome.webview.addEventListener("message", onHostMessage);
    else window.addEventListener("message", onHostMessage);

    return () => {
      if (window.chrome?.webview) window.chrome.webview.removeEventListener("message", onHostMessage);
      else window.removeEventListener("message", onHostMessage);
    };
  }, []);

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
    const open = () => setThemedOpen(true);
    window.addEventListener("vibefinder:open-themedai", open);
    return () => window.removeEventListener("vibefinder:open-themedai", open);
  }, []);

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
    postToThemedAIHost({
      type: "VIBEFINDER_ANALYSIS_COMPLETE",
      vibe: message.vibe || null,
      tracks: Number(message.tracks) || 0,
    });
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
