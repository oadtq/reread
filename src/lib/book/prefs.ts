export const PREFS_KEY = "deepread-reader:v1";
export const PREFS_EVENT = "deepread-prefs";

export type Theme = "light" | "dark";
export type Size = "s" | "m" | "l" | "xl";
export type Width = "narrow" | "comfortable" | "wide" | "full";
export type Face = "sans" | "serif";

export type Prefs = {
  theme: Theme;
  size: Size;
  width: Width;
  face: Face;
};

export const DEFAULT_PREFS: Prefs = {
  theme: "light",
  size: "m",
  width: "comfortable",
  face: "sans",
};

let snapshotKey = "";
let snapshot: Prefs = DEFAULT_PREFS;

/**
 * The document element is the source of truth: the boot script in the root
 * layout writes it before first paint, so reads here never flash a default.
 * The result is memoised because useSyncExternalStore compares snapshots by
 * identity and would loop forever on a fresh object each call.
 */
export function readPrefs(): Prefs {
  const data = document.documentElement.dataset;
  const theme = (data.theme as Theme) || DEFAULT_PREFS.theme;
  const size = (data.size as Size) || DEFAULT_PREFS.size;
  const width = (data.width as Width) || DEFAULT_PREFS.width;
  const face = (data.face as Face) || DEFAULT_PREFS.face;
  const key = `${theme}|${size}|${width}|${face}`;
  if (key !== snapshotKey) {
    snapshotKey = key;
    snapshot = { theme, size, width, face };
  }
  return snapshot;
}

export function writePrefs(patch: Partial<Prefs>) {
  const next = { ...readPrefs(), ...patch };
  const data = document.documentElement.dataset;
  data.theme = next.theme;
  data.size = next.size;
  data.width = next.width;
  data.face = next.face;
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(next));
  } catch {
    // private mode, quota, or disabled storage
  }
  window.dispatchEvent(new Event(PREFS_EVENT));
}

export function subscribePrefs(onStoreChange: () => void) {
  window.addEventListener(PREFS_EVENT, onStoreChange);
  window.addEventListener("storage", onStoreChange);
  return () => {
    window.removeEventListener(PREFS_EVENT, onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}
