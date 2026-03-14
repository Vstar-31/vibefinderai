/**
 * ServicesPanel.jsx
 * ─────────────────
 * VibeFinderAI — Music Service Integrations Panel
 *
 * Shows as a tab inside PlaylistPanel ("Services").
 * Lets users connect Last.fm and YouTube
 * and toggle which service buttons appear on tracks.
 *
 * PROPS
 * ─────
 *  token          — VibeFinder JWT
 *  buildApiUrl    — URL builder fn
 *  servicesStatus — { lastfm: {connected, provider_id}, youtube: {...} }
 *  visibleServices — { lastfm: bool, youtube: bool } from localStorage
 *  onStatusChange  — called after connect/disconnect to refresh status
 *  onVisibilityChange — called when a toggle changes
 */

import { useState } from "react";

const SERVICE_META = {
  lastfm: {
    label:   "Last.fm",
    color:   "#d51007",
    bg:      "rgba(213,16,7,0.08)",
    border:  "rgba(213,16,7,0.3)",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm-1.47 16.517c-2.13 0-3.445-1.393-3.445-3.168 0-1.79 1.303-3.18 3.445-3.18 1.06 0 1.803.304 2.37.71l-.574.724c-.45-.358-1.01-.568-1.796-.568-1.393 0-2.303.96-2.303 2.314 0 1.34.894 2.328 2.303 2.328.718 0 1.278-.2 1.695-.52v-.945h-1.772v-.853h2.71v2.21c-.58.52-1.464.948-2.633.948zm5.44-.075h-.955V9.44h.955v7.002z"/>
      </svg>
    ),
    tagline: "Track what you love. Build your music identity.",
    what:    ["Love tracks", "Scrobble listens", "Build listening history"],
  },
  youtube: {
    label:   "YouTube",
    color:   "#ff0000",
    bg:      "rgba(255,0,0,0.08)",
    border:  "rgba(255,0,0,0.3)",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
      </svg>
    ),
    tagline: "Full-length playback and playlists — no limits.",
    what:    ["Full-length playback", "Create playlists", "Free for everyone"],
  },
};

export default function ServicesPanel({
  token,
  buildApiUrl,
  servicesStatus   = {},
  visibleServices  = {},
  onStatusChange,
  onVisibilityChange,
}) {
  const [loading, setLoading] = useState({});
  const [toast,   setToast]   = useState(null);

  const showToast = (msg, isError = false) => {
    setToast({ msg, isError });
    setTimeout(() => setToast(null), 3500);
  };

  const connect = async (service) => {
    setLoading(l => ({ ...l, [service]: true }));
    try {
      const res = await fetch(
        buildApiUrl(`/api/services/${service}/authorize?token=${encodeURIComponent(token)}`)
      );
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || "Not configured");
      }
      const { url } = await res.json();
      window.location.href = url;
    } catch (e) {
      showToast(`${SERVICE_META[service].label}: ${e.message}`, true);
      setLoading(l => ({ ...l, [service]: false }));
    }
  };

  const disconnect = async (service) => {
    setLoading(l => ({ ...l, [service]: true }));
    try {
      await fetch(
        buildApiUrl(`/api/services/${service}/disconnect?authorization=${encodeURIComponent("Bearer " + token)}`),
        { method: "DELETE" }
      );
      onStatusChange?.();
      showToast(`${SERVICE_META[service].label} disconnected`);
    } catch (e) {
      showToast(`Disconnect failed`, true);
    } finally {
      setLoading(l => ({ ...l, [service]: false }));
    }
  };

  const toggleVisible = (service) => {
    onVisibilityChange?.(service, !visibleServices[service]);
  };

  return (
    <div style={{ padding: "0 20px 20px" }}>
      <div style={{
        fontSize: 9, letterSpacing: "0.18em", color: "rgba(180,140,80,0.4)",
        textTransform: "uppercase", marginBottom: 14,
      }}>
        Connect services to love tracks, play full-length, and build playlists
      </div>

      {Object.entries(SERVICE_META).map(([key, meta]) => {
        const status    = servicesStatus[key] || { connected: false };
        const isVisible = visibleServices[key] !== false; // default visible
        const isLoading = loading[key];

        return (
          <div key={key} style={{
            marginBottom: 12,
            background: status.connected ? meta.bg : "rgba(20,12,4,0.6)",
            border: `1px solid ${status.connected ? meta.border : "rgba(120,80,20,0.2)"}`,
            borderRadius: 10,
            padding: "12px 14px",
            transition: "all 0.2s",
          }}>
            {/* Header row */}
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ color: status.connected ? meta.color : "rgba(180,140,80,0.3)", flexShrink: 0 }}>
                {meta.icon}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 12, fontFamily: "'DM Mono', monospace", letterSpacing: "0.06em",
                  color: status.connected ? meta.color : "rgba(180,140,80,0.6)",
                  textTransform: "uppercase", fontWeight: 500,
                }}>
                  {meta.label}
                  {status.connected && status.provider_id && (
                    <span style={{ fontSize: 9, color: "rgba(180,140,80,0.4)", marginLeft: 8, textTransform: "none" }}>
                      · {status.provider_id}
                    </span>
                  )}
                </div>
                {/* Features */}
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                  {meta.what.map(w => (
                    <span key={w} style={{
                      fontSize: 9, color: "rgba(180,140,80,0.45)",
                      fontFamily: "'DM Mono', monospace",
                    }}>· {w}</span>
                  ))}
                </div>
              </div>

              {/* Connect / Disconnect */}
              <button
                onClick={() => status.connected ? disconnect(key) : connect(key)}
                disabled={isLoading}
                style={{
                  padding: "5px 12px", borderRadius: 6, fontSize: 10,
                  fontFamily: "'DM Mono', monospace", letterSpacing: "0.08em",
                  textTransform: "uppercase", cursor: isLoading ? "not-allowed" : "pointer",
                  opacity: isLoading ? 0.5 : 1, flexShrink: 0,
                  background: status.connected ? "rgba(248,113,113,0.1)" : meta.bg,
                  border: `1px solid ${status.connected ? "rgba(248,113,113,0.35)" : meta.border}`,
                  color: status.connected ? "#f87171" : meta.color,
                  transition: "all 0.2s",
                }}
              >
                {isLoading ? "…" : status.connected ? "Disconnect" : "Connect"}
              </button>
            </div>

            {/* Show on tracks toggle — only when connected */}
            {status.connected && (
              <div
                style={{
                  display: "flex", alignItems: "center", gap: 8, marginTop: 10,
                  paddingTop: 10, borderTop: `1px solid ${meta.border}`,
                  cursor: "pointer",
                }}
                onClick={() => toggleVisible(key)}
              >
                {/* Toggle pill */}
                <div style={{
                  width: 32, height: 18, borderRadius: 9,
                  background: isVisible ? meta.color : "rgba(120,80,20,0.2)",
                  border: `1px solid ${isVisible ? meta.color : "rgba(120,80,20,0.3)"}`,
                  position: "relative", transition: "all 0.2s", flexShrink: 0,
                }}>
                  <div style={{
                    position: "absolute", top: 2,
                    left: isVisible ? 15 : 2,
                    width: 12, height: 12, borderRadius: "50%",
                    background: "#fff", transition: "left 0.2s",
                  }} />
                </div>
                <span style={{
                  fontSize: 9, fontFamily: "'DM Mono', monospace",
                  letterSpacing: "0.1em", textTransform: "uppercase",
                  color: isVisible ? "rgba(180,140,80,0.7)" : "rgba(180,140,80,0.3)",
                }}>
                  {isVisible ? "Showing on tracks" : "Hidden from tracks"}
                </span>
              </div>
            )}

            {/* Tagline when not connected */}
            {!status.connected && meta.tagline && (
              <div style={{
                marginTop: 8, fontSize: 10, color: "rgba(180,140,80,0.4)",
                fontFamily: "'DM Mono', monospace", lineHeight: 1.5, fontStyle: "italic",
              }}>
                {meta.tagline}
              </div>
            )}
          </div>
        );
      })}

      {/* Toast */}
      {toast && (
        <div style={{
          marginTop: 8, padding: "8px 12px", borderRadius: 6,
          background: toast.isError ? "rgba(248,113,113,0.1)" : "rgba(52,211,153,0.1)",
          border: `1px solid ${toast.isError ? "rgba(248,113,113,0.3)" : "rgba(52,211,153,0.3)"}`,
          color: toast.isError ? "#f87171" : "#34d399",
          fontSize: 10, fontFamily: "'DM Mono', monospace",
        }}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
