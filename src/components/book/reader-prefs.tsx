"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import {
  DEFAULT_PREFS,
  readPrefs,
  subscribePrefs,
  writePrefs,
  type Face,
  type Prefs,
  type Size,
  type Theme,
  type Width,
} from "@/lib/book/prefs";

const THEMES: Array<[Theme, string]> = [
  ["light", "Light"],
  ["dark", "Dark"],
];

const SIZES: Array<[Size, string]> = [
  ["s", "S"],
  ["m", "M"],
  ["l", "L"],
  ["xl", "XL"],
];

const WIDTHS: Array<[Width, string]> = [
  ["narrow", "Narrow"],
  ["comfortable", "Default"],
  ["wide", "Wide"],
  ["full", "Full"],
];

const FACES: Array<[Face, string]> = [
  ["sans", "Sans"],
  ["serif", "Serif"],
];

function Row<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Array<[T, string]>;
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <div className="popover-row">
      <span className="kicker">{label}</span>
      <div className="segmented" role="group" aria-label={label}>
        {options.map(([option, text]) => (
          <button key={option} type="button" aria-pressed={value === option} onClick={() => onChange(option)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ReaderPrefs() {
  const prefs = useSyncExternalStore<Prefs>(subscribePrefs, readPrefs, () => DEFAULT_PREFS);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        className="btn btn-ghost"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">Aa</span>
        <span className="sr-only">Reading settings</span>
      </button>
      {open ? (
        <div className="popover" role="dialog" aria-label="Reading settings">
          <Row label="Theme" options={THEMES} value={prefs.theme} onChange={(theme) => writePrefs({ theme })} />
          <Row label="Text size" options={SIZES} value={prefs.size} onChange={(size) => writePrefs({ size })} />
          <Row label="Column width" options={WIDTHS} value={prefs.width} onChange={(width) => writePrefs({ width })} />
          <Row label="Typeface" options={FACES} value={prefs.face} onChange={(face) => writePrefs({ face })} />
        </div>
      ) : null}
    </div>
  );
}
