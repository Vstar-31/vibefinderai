import { useEffect } from "react";
import {
  loadPersonalizationProfile,
  profileSummary,
  recommendationHints,
  recordPersonalizationSignal,
} from "./personalization.js";

const getTrackContext = (element) => {
  const row = element?.closest?.(".app-track-row, .ta-track-card");
  if (!row) return {};
  const spans = [...row.querySelectorAll(".app-track-meta span, .ta-track-copy span")].filter((el) => el.textContent?.trim());
  const artist = spans[1]?.textContent?.trim() || row.querySelector(".ta-track-copy > span:last-child")?.textContent?.trim() || "";
  const title = row.querySelector(".ta-track-copy strong, .app-track-title")?.textContent?.trim() || "";
  return { artist, title };
};

const getCurrentVibe = () => {
  const text = [...document.querySelectorAll(".app-result-card, #results-section, .ta-result")]
    .map((el) => el.textContent || "")
    .join(" ");
  const match = text.match(/(?:Dominant Vibe|YOUR VIBE)\s+([A-Za-z][A-Za-z0-9 _-]{1,40})/i);
  return match?.[1]?.trim() || null;
};

const emitFeedback = (detail) => {
  window.dispatchEvent(new CustomEvent("vibefinder:feedback", { detail }));
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

    const onInterfaceSignal = (event) => {
      const signal = event?.detail;
      if (!signal || typeof signal !== "object") return;
      onSignal({ detail: { ...signal, context: signal.context || "interface_feedback" } });
    };

    const onClick = (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const { artist, title } = getTrackContext(target);
      const button = target.closest("button");
      const buttonTitle = button?.title || "";
      const buttonText = button?.textContent?.trim() || "";
      const vibe = getCurrentVibe();

      if (buttonTitle === "Good match") {
        emitFeedback({ artist, mood: vibe, weight: 2, context: "track_like" });
        return;
      }

      if (buttonTitle === "Bad match") {
        emitFeedback({ artist, mood: vibe, weight: -2, context: "track_dislike", track: { title, artist } });
        return;
      }

      if (buttonTitle.includes("Play full song") || buttonTitle.includes("Play 30s preview") || buttonText === "Playing") {
        emitFeedback({ artist, mood: vibe, weight: 0.5, context: "track_play" });
        return;
      }

      if (buttonTitle.includes("Remove this track")) {
        emitFeedback({ artist, mood: vibe, weight: -1.5, context: "track_remove", track: { title, artist } });
        return;
      }

      if (target.closest(".freq-tag")) {
        const genre = buttonText.replace(/^✓\s*/, "").trim();
        if (genre) emitFeedback({ artist, genre, mood: vibe, weight: 1.25, context: "genre_select" });
      }
    };

    const onChange = (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement)) return;

      const colorInput = target.type === "color" && target.closest(".ta-controls");
      if (colorInput) {
        emitFeedback({
          interfaceCategory: "themes",
          interfaceValue: target.value,
          weight: 1.5,
          context: "interface_theme_change",
        });
        return;
      }

      if (target.type !== "range") return;
      const label = target.closest("label")?.textContent?.toLowerCase() || "";
      const value = Number(target.value);
      if (!Number.isFinite(value)) return;

      if (label.includes("artist familiarity")) {
        emitFeedback({ interfaceCategory: "density", interfaceValue: "artist-familiar", weight: value >= 60 ? 0.5 : -0.25, context: "artist_familiarity_control" });
      } else if (label.includes("nicheness")) {
        emitFeedback({ interfaceCategory: "density", interfaceValue: "niche", weight: value >= 60 ? 0.75 : -0.25, context: "nicheness_control" });
      } else if (label.includes("bpm bias")) {
        emitFeedback({ interfaceCategory: "ambience", interfaceValue: value >= 60 ? "high-energy" : value <= 40 ? "low-energy" : "balanced", weight: value >= 60 || value <= 40 ? 0.5 : 0.15, context: "bpm_control" });
      }
    };

    const originalFetch = window.fetch.bind(window);
    const personalizedFetch = async (input, init = {}) => {
      const url = typeof input === "string" ? input : input?.url || "";
      if (!url.includes("/api/vibe/analyze") || !init?.body || typeof init.body !== "string") {
        return originalFetch(input, init);
      }

      try {
        const payload = JSON.parse(init.body);
        const profile = loadPersonalizationProfile();
        const hints = recommendationHints(profile);
        if (!profile.signals) return originalFetch(input, init);

        const currentExcluded = Array.isArray(payload.excluded_tracks) ? payload.excluded_tracks : [];
        const learnedExcluded = hints.dislikedArtists.map((artist) => ({ title: "", artist }));
        const excluded = [...currentExcluded, ...learnedExcluded]
          .filter((item, index, rows) => rows.findIndex((candidate) => `${candidate.title || ""}|${candidate.artist || ""}` === `${item.title || ""}|${item.artist || ""}`) === index)
          .slice(0, 24);

        const mergedPayload = {
          ...payload,
          artist_focus: Math.min(100, Math.round((payload.artist_focus ?? 50) + hints.focusBoosts.artist)),
          nicheness: Math.min(100, Math.round((payload.nicheness ?? 50) + hints.focusBoosts.nicheness)),
          bpm_focus: Math.min(100, Math.round((payload.bpm_focus ?? 50) + hints.focusBoosts.bpm)),
          excluded_tracks: excluded.length ? excluded : null,
          liked_artists: [...new Set([...(Array.isArray(payload.liked_artists) ? payload.liked_artists : []), ...hints.likedArtists])].slice(0, 12),
        };

        return originalFetch(input, { ...init, body: JSON.stringify(mergedPayload) });
      } catch {
        return originalFetch(input, init);
      }
    };

    window.fetch = personalizedFetch;
    window.addEventListener("vibefinder:feedback", onSignal);
    window.addEventListener("themedai:interface-feedback", onInterfaceSignal);
    document.addEventListener("click", onClick, true);
    document.addEventListener("change", onChange, true);
    publish();

    return () => {
      window.fetch = originalFetch;
      window.removeEventListener("vibefinder:feedback", onSignal);
      window.removeEventListener("themedai:interface-feedback", onInterfaceSignal);
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("change", onChange, true);
    };
  }, []);

  return null;
}
