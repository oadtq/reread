"use client";

import { useSyncExternalStore } from "react";
import { DEFAULT_PREFS, readPrefs, subscribePrefs, writePrefs, type Theme } from "@/lib/book/prefs";

const THEMES: Array<[Theme, string]> = [
  ["light", "Light"],
  ["dark", "Dark"],
];

export function ThemeToggle() {
  const theme = useSyncExternalStore(
    subscribePrefs,
    () => readPrefs().theme,
    () => DEFAULT_PREFS.theme,
  );

  return (
    <div className="segmented" role="group" aria-label="Colour theme">
      {THEMES.map(([value, label]) => (
        <button
          key={value}
          type="button"
          aria-pressed={theme === value}
          onClick={() => writePrefs({ theme: value })}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
