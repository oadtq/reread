export const PROGRESS_KEY = "deepread-progress:v1";
export const PROGRESS_EVENT = "deepread-progress";

export type ProgressEntry = {
  slug: string;
  title: string;
  at: number;
};

export type ProgressMap = Record<string, ProgressEntry>;

function parseMap(raw: string | null): ProgressMap {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const map: ProgressMap = {};
    for (const [bookId, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (!value || typeof value !== "object" || Array.isArray(value)) continue;
      const entry = value as { slug?: unknown; title?: unknown; at?: unknown };
      if (typeof entry.slug !== "string" || !entry.slug) continue;
      map[bookId] = {
        slug: entry.slug,
        title: typeof entry.title === "string" ? entry.title : entry.slug,
        at: typeof entry.at === "number" ? entry.at : 0,
      };
    }
    return map;
  } catch {
    return {};
  }
}

let snapshotRaw: string | null | undefined;
let snapshotMap: ProgressMap = {};

export function readProgressMap(): ProgressMap {
  try {
    const raw = window.localStorage.getItem(PROGRESS_KEY);
    if (raw === snapshotRaw) return snapshotMap;
    snapshotRaw = raw;
    snapshotMap = parseMap(raw);
    return snapshotMap;
  } catch {
    return snapshotMap;
  }
}

export function readProgress(bookId: string): ProgressEntry | null {
  return readProgressMap()[bookId] ?? null;
}

export function writeProgress(bookId: string, slug: string, title: string) {
  try {
    const all = readProgressMap();
    const previous = all[bookId];
    if (previous?.slug === slug && previous.title === title) {
      all[bookId] = { ...previous, at: Date.now() };
    } else {
      all[bookId] = { slug, title, at: Date.now() };
    }
    window.localStorage.setItem(PROGRESS_KEY, JSON.stringify(all));
    window.dispatchEvent(new Event(PROGRESS_EVENT));
  } catch {
    // private mode, quota, or disabled storage
  }
}

const activeSlugs: Record<string, string> = {};
const activeListeners = new Set<() => void>();
let ignoreSpyUntil = 0;

export function ignoreSpy(ms: number) {
  ignoreSpyUntil = Date.now() + ms;
}

export function isSpyIgnored() {
  return Date.now() < ignoreSpyUntil;
}

export function getActiveSlug(bookId: string) {
  return activeSlugs[bookId] ?? "";
}

export function subscribeActive(onStoreChange: () => void) {
  activeListeners.add(onStoreChange);
  return () => activeListeners.delete(onStoreChange);
}

export function markSection(
  bookId: string,
  slug: string,
  title: string,
  mode: "replace" | "push" | "silent",
) {
  const changed = activeSlugs[bookId] !== slug;
  activeSlugs[bookId] = slug;
  writeProgress(bookId, slug, title);
  if (changed) {
    for (const listener of activeListeners) listener();
  }
  if (mode === "silent") return;
  const next = `#${slug}`;
  if (mode === "push") {
    history.pushState(null, "", next);
    return;
  }
  if (location.hash !== next) history.replaceState(null, "", next);
}

export function subscribeProgress(onStoreChange: () => void) {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(PROGRESS_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(PROGRESS_EVENT, onStoreChange);
  };
}

