import { useEffect, useState } from "react";

export function useLibraryCollection(url, token, field, label, refreshKey = 0) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    setItems([]);
    setError("");
    setLoading(true);
    const timer = setTimeout(() => controller.abort(), 20000);
    (async () => {
      try {
        if (!token) throw new Error("Sign in again to load your library.");
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` }, signal: controller.signal,
        });
        if (response.status === 401 || response.status === 403)
          throw new Error("Your session has expired. Sign in again to load your library.");
        if (!response.ok) throw new Error(`Could not load ${label} (HTTP ${response.status}). Try again.`);
        const data = await response.json();
        if (!Array.isArray(data[field])) throw new Error(`The server returned an invalid ${label} response. Try again.`);
        if (!disposed) setItems(data[field]);
      } catch (e) {
        if (!disposed) setError(controller.signal.aborted
          ? `Loading ${label} timed out. Try again.`
          : e instanceof TypeError ? `Could not connect to load ${label}. Check your connection and try again.` : e.message);
      } finally {
        clearTimeout(timer);
        if (!disposed) setLoading(false);
      }
    })();
    return () => { disposed = true; clearTimeout(timer); controller.abort(); };
  }, [url, token, field, label, attempt, refreshKey]);
  return { items, setItems, loading, error, retry: () => setAttempt(v => v + 1) };
}
