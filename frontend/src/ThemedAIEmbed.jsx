import { useEffect, useMemo, useState } from "react";
import ThemedApp from "./ThemedApp.jsx";
import "./ThemedAIEmbed.css";

const BRIDGE_NAME = "Themed.AI";

function parseMessage(message) {
  if (typeof message === "string") {
    try { return JSON.parse(message); } catch { return { type: "THEMEDAI_HOST_MESSAGE", value: message }; }
  }
  return message && typeof message === "object" ? message : null;
}

function sendCommand(message) {
  try { window.postMessage(message, "*"); } catch {}
}

export default function ThemedAIEmbed({
  open,
  onClose,
  initialPrompt = "",
  onMessage,
  onAnalysisComplete,
  onThemeChange,
}) {
  const [ready, setReady] = useState(false);
  const [liveState, setLiveState] = useState({ vibe: "neutral", prompt: "", trackCount: 0, loading: false });
  const [signedIn, setSignedIn] = useState(false);

  const statusLabel = useMemo(() => {
    if (!ready) return "booting bridge";
    if (liveState.loading) return "finding your vibe";
    if (liveState.trackCount) return `${liveState.trackCount} tracks live`;
    return "host linked";
  }, [ready, liveState]);

  useEffect(() => {
    if (!open) return undefined;

    let chromeCreated = false;
    let webviewCreated = false;
    let originalPostMessage = null;
    let webview = null;

    const forward = (message) => {
      const data = parseMessage(message);
      if (!data) return;
      onMessage?.(data);
      if (data.type === "THEMEDAI_READY") setReady(true);
      if (data.type === "VIBEFINDER_STATE") setLiveState((prev) => ({ ...prev, ...(data.state || {}) }));
      if (data.type === "THEMEDAI_THEME") onThemeChange?.(data.accent);
      if (data.type === "THEMEDAI_ANALYSIS_COMPLETE") onAnalysisComplete?.(data);
    };

    // ThemedApp was designed to speak to WinUI WebView2 through
    // window.chrome.webview. In the browser we provide the same tiny surface,
    // while preserving a native WebView2 bridge when one already exists.
    try {
      if (!window.chrome) {
        window.chrome = {};
        chromeCreated = true;
      }
      if (!window.chrome.webview) {
        window.chrome.webview = {};
        webviewCreated = true;
      }
      webview = window.chrome.webview;
      originalPostMessage = webview.postMessage;
      webview.postMessage = (message) => {
        forward(message);
        if (typeof originalPostMessage === "function") originalPostMessage.call(webview, message);
      };
    } catch {
      // Browsers/hosts that expose a non-extensible chrome object still work
      // through the postMessage command path below.
    }

    const handleWindowMessage = (event) => {
      const data = parseMessage(event.data);
      if (data?.type === "THEMEDAI_READY") forward(data);
    };
    const handleStorage = (event) => {
      if (event.key === "vf_token") setSignedIn(Boolean(event.newValue));
    };

    window.addEventListener("message", handleWindowMessage);
    window.addEventListener("storage", handleStorage);
    setSignedIn(Boolean(localStorage.getItem("vf_token")));
    setReady(false);

    return () => {
      window.removeEventListener("message", handleWindowMessage);
      window.removeEventListener("storage", handleStorage);
      try {
        if (webview && originalPostMessage) webview.postMessage = originalPostMessage;
        if (webviewCreated && window.chrome?.webview === webview) delete window.chrome.webview;
        if (chromeCreated && window.chrome && Object.keys(window.chrome).length === 0) delete window.chrome;
      } catch {}
    };
  }, [open, onMessage, onAnalysisComplete, onThemeChange]);

  useEffect(() => {
    if (!open || !initialPrompt.trim()) return;
    sendCommand({ type: "THEMEDAI_CONTEXT", prompt: initialPrompt.trim() });
  }, [open, initialPrompt]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "t") {
        event.preventDefault();
        onClose?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const useCurrentPrompt = () => {
    if (!initialPrompt.trim()) return;
    sendCommand({ type: "THEMEDAI_ANALYZE", prompt: initialPrompt.trim() });
  };

  return (
    <div className="themedai-embed-shell" role="dialog" aria-modal="true" aria-label="Themed.AI embedded workspace">
      <div className="themedai-embed-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose?.()} />
      <section className="themedai-embed-drawer">
        <header className="themedai-embed-bar">
          <div className="themedai-embed-brand">
            <span className="themedai-embed-mark" aria-hidden="true">✦</span>
            <div>
              <strong>{BRIDGE_NAME}</strong>
              <span>inside VibeFinderAI</span>
            </div>
          </div>
          <div className="themedai-embed-meta" aria-live="polite">
            <span className={`themedai-status-dot ${ready ? "ready" : ""}`} />
            <span>{statusLabel}</span>
            <span className="themedai-auth-pill">{signedIn ? "session shared" : "sign in when needed"}</span>
            <button className="themedai-embed-action" onClick={useCurrentPrompt} disabled={!initialPrompt.trim()} title="Run the VibeFinderAI prompt in Themed.AI">
              Use current vibe
            </button>
            <button className="themedai-embed-close" onClick={onClose} aria-label="Close Themed.AI">×</button>
          </div>
        </header>
        <div className="themedai-embed-viewport">
          <ThemedApp />
        </div>
      </section>
    </div>
  );
}
