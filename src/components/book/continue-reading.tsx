"use client";

import { useSyncExternalStore } from "react";
import { readProgress, subscribeProgress } from "@/lib/book/progress";

export function ContinueReading({ bookId, startSlug }: { bookId: string; startSlug: string }) {
  const entry = useSyncExternalStore(
    subscribeProgress,
    () => readProgress(bookId),
    () => null,
  );
  if (!entry?.title || entry.slug === startSlug) return null;

  return (
    <p className="catalog-continue">
      <a href={`/${bookId}#${entry.slug}`}>Continue: {entry.title}</a>
    </p>
  );
}
