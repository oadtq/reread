"use client";

import { useSyncExternalStore } from "react";

type Theme = "light" | "night";

function subscribe(onStoreChange: () => void) {
  window.addEventListener("ie-theme", onStoreChange);
  window.addEventListener("storage", onStoreChange);
  return () => {
    window.removeEventListener("ie-theme", onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "night" ? "night" : "light";
}

function setTheme(next: Theme) {
  document.documentElement.dataset.theme = next === "night" ? "night" : "";
  window.localStorage.setItem("ie-theme", next);
  window.dispatchEvent(new Event("ie-theme"));
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, currentTheme, () => "light" as Theme);

  return (
    <div className="segmented" role="group" aria-label="Color theme">
      {(
        [
          ["light", "Light"],
          ["night", "Night"],
        ] as const
      ).map(([value, label]) => (
        <button key={value} type="button" aria-pressed={theme === value} onClick={() => setTheme(value)}>
          {label}
        </button>
      ))}
    </div>
  );
}
