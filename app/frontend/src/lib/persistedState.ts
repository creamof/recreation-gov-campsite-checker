/**
 * Thin, defensive wrapper around localStorage.
 *
 * Private browsing modes, storage quotas, disabled storage, and hand-edited
 * or stale-schema JSON can all make localStorage throw or return garbage.
 * None of that should ever crash the app — persistence here is a nice-to-have,
 * not a requirement, so every operation degrades to a no-op/fallback instead
 * of throwing.
 */

const isBrowser = typeof window !== "undefined";

/** Read and JSON-parse a value from localStorage, or return `fallback` on any failure. */
export function loadPersisted<T>(key: string, fallback: T): T {
  if (!isBrowser) return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/** JSON-stringify and write a value to localStorage. Silently no-ops on failure. */
export function savePersisted<T>(key: string, value: T): void {
  if (!isBrowser) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Quota exceeded, storage disabled, private browsing, etc. — ignore.
  }
}

/** Remove a persisted key. Silently no-ops on failure. */
export function clearPersisted(key: string): void {
  if (!isBrowser) return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}
