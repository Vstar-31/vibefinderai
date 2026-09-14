import { useEffect, useRef } from "react";

const postHost = (message) => {
  try {
    if (window.chrome?.webview) {
      window.chrome.webview.postMessage(JSON.stringify(message));
    }
  } catch {
    // chrome.webview only exists inside WebView2; normal browser usage is unaffected.
  }
};

const getTrackRows = () => [...document.querySelectorAll(".app-track-row")];

const getTrack = (row) => {
  if (!row) return null;
  const spans = [...row.querySelectorAll(".app-track-meta span")].filter((el) => el.textContent?.trim());
  const title = spans[0]?.textContent?.trim() || null;
  const artist = spans[1]?.textContent?.trim() || null;
  const img = row.querySelector(".app-track-art");
  return title && artist ? { title, artist, cover_art: img?.src || null, preview_url: null } : null;
};

const findPlayerButton = (kind) => {
  const buttons = [...document.querySelectorAll("button")];
  if (kind === "next") return buttons.find((b) => b.title === "Next") || buttons.find((b) => b.textContent?.trim() === "Next");
  if (kind === "prev") return buttons.find((b) => b.title === "Previous") || buttons.find((b) => b.textContent?.trim() === "Previous");
  if (kind === "playpause") {
    return buttons.find((b) => b.title === "Pause") ||
      buttons.find((b) => b.title === "Play full track") ||
      buttons.find((b) => b.title === "Play 30s preview") ||
      buttons.find((b) => b.title === "Playing");
  }
  return null;
};

const findRowPlayButton = (row) => {
  if (!row) return null;
  const buttons = [...row.querySelectorAll("button")];
  return buttons.find((b) => b.title === "Play full song in embedded player") ||
    buttons.find((b) => b.title === "Play 30s preview") ||
    buttons.find((b) => b.title === "Play") || null;
};

export default function ThemedAIHostBridge() {
  const currentIndexRef = useRef(0);
  const stateTimerRef = useRef(null);
  const resultTimerRef = useRef(null);

  useEffect(() => {
    postHost({
      type: "VIBEFINDER_APP_READY",
      hasToken: (() => {
        try { return Boolean(localStorage.getItem("vf_token")); }
        catch { return false; }
      })(),
    });

    const publishResults = () => {
      const tracks = getTrackRows().map(getTrack).filter(Boolean);
      if (tracks.length === 0) return;
      currentIndexRef.current = Math.min(currentIndexRef.current, tracks.length - 1);
      postHost({ type: "VIBEFINDER_RESULTS", tracks });
    };

    const publishState = () => {
      const rows = getTrackRows();
      if (rows.length === 0) return;
      const index = Math.max(0, Math.min(currentIndexRef.current, rows.length - 1));
      const track = getTrack(rows[index]);
      if (!track) return;

      const pauseButton = findPlayerButton("playpause");
      const isPlaying = Boolean(pauseButton && (pauseButton.title === "Pause" || pauseButton.textContent?.includes("Pause")));
      postHost({
        type: "VIBEFINDER_STATE",
        state: {
          isPlaying,
          title: track.title,
          artist: track.artist,
          coverArt: track.cover_art,
          previewUrl: track.preview_url,
          currentTime: 0,
          duration: 0,
        },
      });
    };

    const runBridge = () => {
      publishResults();
      publishState();
    };

    const onHostMessage = (event) => {
      let message = event?.data;
      if (typeof message === "string") {
        try { message = JSON.parse(message); } catch { return; }
      }
      if (!message || typeof message !== "object") return;

      const command = message.command || message.type;
      if (!(command === "playpause" || command === "next" || command === "prev" || command === "previous")) return;

      const rows = getTrackRows();
      if (rows.length === 0) {
        postHost({ type: "VIBEFINDER_COMMAND_RESULT", command, success: false, reason: "no_results" });
        return;
      }

      const normalised = command === "previous" ? "prev" : command;
      let ok = false;

      if (normalised === "next" || normalised === "prev") {
        const existingPlayerButton = findPlayerButton(normalised);
        if (existingPlayerButton) {
          existingPlayerButton.click();
          ok = true;
          if (normalised === "next") currentIndexRef.current = Math.min(currentIndexRef.current + 1, rows.length - 1);
          else currentIndexRef.current = Math.max(currentIndexRef.current - 1, 0);
        } else {
          currentIndexRef.current = normalised === "next"
            ? (currentIndexRef.current + 1) % rows.length
            : (currentIndexRef.current - 1 + rows.length) % rows.length;
          const playButton = findRowPlayButton(rows[currentIndexRef.current]);
          if (playButton) {
            playButton.click();
            ok = true;
          }
        }
      } else {
        const existingPlayButton = findPlayerButton("playpause");
        if (existingPlayButton) {
          existingPlayButton.click();
          ok = true;
        } else {
          const rowButton = findRowPlayButton(rows[currentIndexRef.current]);
          if (rowButton) {
            rowButton.click();
            ok = true;
          }
        }
      }

      postHost({ type: "VIBEFINDER_COMMAND_RESULT", command, success: ok, reason: ok ? null : "player_not_available" });
      setTimeout(runBridge, 80);
    };

    if (window.chrome?.webview) window.chrome.webview.addEventListener("message", onHostMessage);
    else window.addEventListener("message", onHostMessage);

    resultTimerRef.current = window.setInterval(publishResults, 1200);
    stateTimerRef.current = window.setInterval(publishState, 500);
    const observer = new MutationObserver(runBridge);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    runBridge();

    return () => {
      if (window.chrome?.webview) window.chrome.webview.removeEventListener("message", onHostMessage);
      else window.removeEventListener("message", onHostMessage);
      if (resultTimerRef.current) window.clearInterval(resultTimerRef.current);
      if (stateTimerRef.current) window.clearInterval(stateTimerRef.current);
      observer.disconnect();
    };
  }, []);

  return null;
}
