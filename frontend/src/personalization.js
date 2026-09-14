const STORAGE_KEY = "vf_personalization_v1";

const DEFAULT_PROFILE = {
  version: 1,
  signals: 0,
  moods: {},
  artists: {},
  genres: {},
  languages: {},
  interface: {
    themes: {},
    density: {},
    widgets: {},
    ambience: {},
  },
  recentContexts: [],
};

function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, value));
}

export function loadPersonalizationProfile() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_PROFILE);
    const parsed = JSON.parse(raw);
    return {
      ...structuredClone(DEFAULT_PROFILE),
      ...parsed,
      interface: {
        ...structuredClone(DEFAULT_PROFILE.interface),
        ...(parsed.interface || {}),
      },
    };
  } catch {
    return structuredClone(DEFAULT_PROFILE);
  }
}

export function savePersonalizationProfile(profile) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile)); } catch {}
  return profile;
}

export function recordPersonalizationSignal(profile, signal = {}) {
  const next = structuredClone(profile || DEFAULT_PROFILE);
  const amount = Number.isFinite(signal.weight) ? signal.weight : 1;
  next.signals += amount;

  const bump = (bucket, key, delta = amount) => {
    if (!key) return;
    bucket[key] = clamp((bucket[key] || 0) + delta, -1000, 1000);
  };

  if (signal.mood) bump(next.moods, signal.mood);
  if (signal.artist) bump(next.artists, signal.artist);
  if (signal.genre) bump(next.genres, signal.genre);
  if (signal.language) bump(next.languages, signal.language);

  const category = signal.interfaceCategory;
  if (category && signal.interfaceValue) {
    bump(next.interface[category] || (next.interface[category] = {}), signal.interfaceValue);
  }

  if (signal.context) {
    next.recentContexts = [
      { value: signal.context, at: Date.now() },
      ...next.recentContexts.filter((item) => item.value !== signal.context),
    ].slice(0, 12);
  }

  return savePersonalizationProfile(next);
}

export function rankProfile(bucket = {}) {
  return Object.entries(bucket)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([value, score]) => ({ value, score }));
}

export function profileSummary(profile) {
  return {
    signals: profile?.signals || 0,
    topMoods: rankProfile(profile?.moods),
    topArtists: rankProfile(profile?.artists),
    topGenres: rankProfile(profile?.genres),
    topLanguages: rankProfile(profile?.languages),
    interface: {
      themes: rankProfile(profile?.interface?.themes),
      density: rankProfile(profile?.interface?.density),
      widgets: rankProfile(profile?.interface?.widgets),
      ambience: rankProfile(profile?.interface?.ambience),
    },
    recentContexts: profile?.recentContexts || [],
  };
}

export function clearPersonalizationProfile() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
  return structuredClone(DEFAULT_PROFILE);
}
