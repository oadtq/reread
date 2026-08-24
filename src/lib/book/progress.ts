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

export function restorePositionScript(): string {
  return `(function(){var root=document.getElementById("book-scroll");if(!root)return;var bookId=root.getAttribute("data-book-id")||"";var start=root.getAttribute("data-start-slug")||"";var hash=location.hash.replace(/^#/,"");try{hash=decodeURIComponent(hash)}catch(e){}var all={};var saved="";try{all=JSON.parse(localStorage.getItem(${JSON.stringify(PROGRESS_KEY)})||"{}")||{};if(all[bookId]&&typeof all[bookId].slug==="string")saved=all[bookId].slug}catch(e){}var id=hash||saved||start;if(!id)return;var el=document.getElementById(id);if(!el&&saved)el=document.getElementById(saved);if(!el&&start)el=document.getElementById(start);if(!el)return;el.scrollIntoView({behavior:"instant",block:"start"});var section=el.closest("[data-slug]")||el;var slug=section.getAttribute("data-slug")||el.id;var title=section.getAttribute("data-title")||slug;try{all[bookId]={slug:slug,title:title,at:Date.now()};localStorage.setItem(${JSON.stringify(PROGRESS_KEY)},JSON.stringify(all))}catch(e){}if(!hash){try{history.replaceState(null,"","#"+slug)}catch(e){}}})();`;
}
