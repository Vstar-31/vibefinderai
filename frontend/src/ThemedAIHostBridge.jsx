import { useEffect } from "react";

// App owns commands/results; MusicPlayer owns playback snapshots. DOM scraping
// here used to execute transport commands twice and flood the host while typing.
export default function ThemedAIHostBridge() {
  useEffect(() => {
    const publishProfile = (event) => {
      window.chrome?.webview?.postMessage(JSON.stringify({
        type: "VIBEFINDER_PROFILE", profile: event.detail || null,
      }));
    };
    window.addEventListener("vibefinder:profile", publishProfile);
    return () => window.removeEventListener("vibefinder:profile", publishProfile);
  }, []);
  return null;
}
