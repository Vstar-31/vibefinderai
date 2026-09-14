import { useCallback, useEffect, useState } from "react";
import App from "./App.jsx";
import ThemedAIEmbed from "./ThemedAIEmbed.jsx";
import ThemedAIHostBridge from "./ThemedAIHostBridge.jsx";
import { loadPersonalizationProfile, profileSummary, recordPersonalizationSignal } from "./personalization.js";

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
    postToThemedAIHost({
      type: "VIBEFINDER_APP_READY",
      hasToken: (() => {
        try { return Boolean(localStorage.getItem("vf_token")); }
        catch { return false; }
      })(),
    });
    postToThemedAIHost({ type: "VIBEFINDER_PROFILE", profile: profileSummary(loadPersonalizationProfile()) });

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
        } else {
          postToThemedAIHost({ type: "VIBEFINDER_COMMAND_RESULT", command: "setPrompt", success: false, reason: "input_not_ready" });
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
    // Convert meaningful music/interface interactions into durable personalization signals.
    // This deliberately sits at the wrapper level so future interface controls can participate
    // without coupling the research model to individual components.
    const onClick = (event) => {
      const button = event.target?.closest?.("button, a");
      if (!button) return;
      const title = (button.getAttribute("title") || "").toLowerCase();
      const text = (button.textContent || "").trim().toLowerCase();
      let signal = null;

      if (text.includes("good match") || title.includes("good match")) signal = { weight: 1 };
      else if (text.includes("bad match") || title.includes("bad match")) signal = { weight: -1 };
      else if (title.includes("play 30s preview")) signal = { weight: 0.25 };
      else if (title.includes("play full song") || title === "play full track") signal = { weight: 0.5 };
      else if (title === "next" || title === "previous" || title === "prev") signal = { weight: -0.1 };
      else if (text === "reset engine") signal = { weight: 0.05 };
      else if (text === "dark" || text === "minimal" || text.includes("ambience")) signal = { weight: 0.25, interfaceCategory: "themes", interfaceValue: text };

      if (!signal) return;
      const updated = recordPersonalizationSignal(loadPersonalizationProfile(), {
        ...signal,
        context: currentPrompt.trim() || undefined,
      });
      postToThemedAIHost({ type: "VIBEFINDER_PROFILE", profile: profileSummary(updated) });
    };

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [currentPrompt]);

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
    if (message.type === "VIBEFINDER_PROFILE" && message.profile) setLastThemedState((prev) => ({ ...(prev || {}), profile: message.profile }));
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
    const updated = recordPersonalizationSignal(loadPersonalizationProfile(), {
      interfaceCategory: "themes",
      interfaceValue: accent,
      context: currentPrompt.trim() || undefined,
      weight: 0.5,
    });
    postToThemedAIHost({ type: "VIBEFINDER_PROFILE", profile: profileSummary(updated) });
  }, [currentPrompt]);

  return (
    <>
      <ThemedAIHostBridge />
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
