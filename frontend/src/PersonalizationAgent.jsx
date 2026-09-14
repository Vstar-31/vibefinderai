import { useEffect } from "react";
import {
  loadPersonalizationProfile,
  profileSummary,
  recordPersonalizationSignal,
} from "./personalization.js";

const getTrackContext = (element) => {
  const row = element?.closest?.(".app-track-row");
  if (!row) return {};
  const spans = [...row.querySelectorAll(".app-track-meta span")].filter((el) => el.textContent?.trim());
  const artist = spans[1]?.textContent?.trim() || "";
  return { artist };
};

const getCurrentVibe = () => {
  const text = [...document.querySelectorAll(".app-result-card, #results-section")]
    .map((el) => el.textContent || "")
    .join(" ");
  const match = text.match(/Dominant Vibe\s+([A-Za-z][A-Za-z0-9 _-]{1,40})/i);
  return match?.[1]?.trim() || null;
};

export default function PersonalizationAgent() {
  useEffect(() => {
    const publish = () => {
      window.dispatchEvent(new CustomEvent("vibefinder:profile", {
        detail: profileSummary(loadPersonalizationProfile()),
      }));
    };

    const onSignal = (event) => {
      const signal = event?.detail;
      if (!signal || typeof signal !== "object") return;
      recordPersonalizationSignal(loadPersonalizationProfile(), signal);
      publish();
    };

    const onClick = (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const { artist } = getTrackContext(target);
      const button = target.closest("button");
      const buttonTitle = button?.title || "";
      const buttonText = button?.textContent?.trim() || "";
      const vibe = getCurrentVibe();

      if (buttonTitle === "Good match") {
        window.dispatchEvent(new CustomEvent("vibefinder:feedback", {
          detail: { artist, mood: vibe, weight: 2, context: "track_like" },
        }));
        return;
      }

      if (buttonTitle === "Bad match") {
        window.dispatchEvent(new CustomEvent("vibefinder:feedback", {
          detail: { artist, mood: vibe, weight: -2, context: "track_dislike" },
        }));
        return;
      }

      if (buttonTitle.includes("Play full song") || buttonTitle.includes("Play 30s preview") || buttonText === "Playing") {
        window.dispatchEvent(new CustomEvent("vibefinder:feedback", {
          detail: { artist, mood: vibe, weight: 0.5, context: "track_play" },
        }));
        return;
      }

      if (buttonTitle.includes("Remove this track")) {
        window.dispatchEvent(new CustomEvent("vibefinder:feedback", {
          detail: { artist, mood: vibe, weight: -1.5, context: "track_remove" },
        }));
        return;
      }

      if (target.closest(".freq-tag")) {
        const genre = buttonText.replace(/^✓\s*/, "").trim();
        if (genre) {
          window.dispatchEvent(new CustomEvent("vibefinder:feedback", {
            detail: { artist, genre, mood: vibe, weight: 1.25, context: "genre_select" },
          }));
        }
      }
    };

    window.addEventListener("vibefinder:feedback", onSignal);
    document.addEventListener("click", onClick, true);
    publish();
    return () => {
      window.removeEventListener("vibefinder:feedback", onSignal);
      document.removeEventListener("click", onClick, true);
    };
  }, []);

  return null;
}
