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

  // `signals` measures observed interaction volume, not preference polarity.
  next.signals += Math.max(1, Math.abs(amount));

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

export function recommendationHints(profile) {
  const source = profile || DEFAULT_PROFILE;
  const positive = (bucket) => rankProfile(bucket).filter((item) => item.score > 0);
  const negative = (bucket) => rankProfile(bucket).filter((item) => item.score < 0);

  return {
    likedArtists: positive(source.artists)
      .slice(0, 6)
      .map(({ value }) => value),
    preferredGenres: positive(source.genres)
      .slice(0, 6)
      .map(({ value }) => value),
    preferredMoods: positive(source.moods)
      .slice(0, 4)
      .map(({ value }) => value),
    dislikedArtists: negative(source.artists)
      .slice(0, 8)
      .map(({ value }) => value),
    excludedContexts: (source.recentContexts || [])
      .filter((item) => ["track_dislike", "track_remove"].includes(item.value))
      .slice(0, 6)
      .map(({ value }) => value),
    focusBoosts: {
      artist: clamp((positive(source.artists)[0]?.score || 0) * 8, 0, 35),
      nicheness: clamp((positive(source.genres)[0]?.score || 0) * 5, 0, 25),
      bpm: clamp((positive(source.moods)[0]?.score || 0) * 3, 0, 20),
    },
  };
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
