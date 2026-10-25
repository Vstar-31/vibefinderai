// YouTube sends state both as events and in its periodic info snapshots.
export function readYouTubeMessage(event, playerWindow) {
  if (!playerWindow || event.source !== playerWindow || event.origin !== 'https://www.youtube.com') return null;
  try {
    const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
    if (!data || typeof data !== 'object') return null;
    const state = data.event === 'onStateChange' ? data.info
      : data.event === 'infoDelivery' || data.event === 'initialDelivery' ? data.info?.playerState
      : undefined;
    return { ...data, state: [-1, 0, 1, 2, 3, 5].includes(state) ? state : undefined };
  } catch {
    return null;
  }
}
