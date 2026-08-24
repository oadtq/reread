"use client";

import { useEffect, useLayoutEffect, useSyncExternalStore } from "react";
import Link from "next/link";
import { ThemeToggle } from "@/components/book/theme-toggle";
import {
  getActiveSlug,
  ignoreSpy,
  isSpyIgnored,
  markSection,
  readProgress,
  subscribeActive,
} from "@/lib/book/progress";

function usesContainerScroll(main: HTMLElement) {
  return main.scrollHeight > main.clientHeight + 1;
}

function sectionAtReadLine(main: HTMLElement, windowScroll: boolean) {
  const sections = main.querySelectorAll<HTMLElement>("[data-slug]");
  const line = windowScroll ? 96 : main.getBoundingClientRect().top + 80;
  let current = "";
  for (const section of sections) {
    if (section.getBoundingClientRect().top <= line + 8) {
      current = section.dataset.slug ?? "";
    }
  }
  return current;
}

function scrollProgress(main: HTMLElement, windowScroll: boolean) {
  if (windowScroll) {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    return max <= 0 ? 0 : (window.scrollY / max) * 100;
  }
  const max = main.scrollHeight - main.clientHeight;
  return max <= 0 ? 0 : (main.scrollTop / max) * 100;
}

function slugFromHash() {
  const hash = location.hash.replace(/^#/, "");
  if (!hash) return "";
  try {
    return decodeURIComponent(hash);
  } catch {
    return hash;
  }
}

function sectionOf(el: Element | null) {
  const section = el?.closest<HTMLElement>("[data-slug]");
  if (!section) return null;
  return {
    slug: section.dataset.slug ?? section.id,
    title: section.dataset.title ?? section.dataset.slug ?? section.id,
  };
}

export function useActiveSection(bookId: string, startSlug: string) {
  return useSyncExternalStore(
    subscribeActive,
    () => getActiveSlug(bookId) || startSlug,
    () => startSlug,
  );
}

export function BookTopbar({ title }: { title: string }) {
  return (
    <header className="book-topbar">
      <div className="flex min-w-0 items-center gap-3">
        <Link href="/" className="brand">
          DeepRead
        </Link>
        <span className="hidden text-mute sm:inline" aria-hidden="true">
          /
        </span>
        <p className="hidden truncate text-sm text-mute sm:block">{title}</p>
      </div>
      <div className="flex items-center gap-3">
        <Link href="/" className="quiet-link">
          Library
        </Link>
        <ThemeToggle />
      </div>
      <span className="reading-progress" aria-hidden="true" />
    </header>
  );
}

export function BookSpy({ bookId, startSlug }: { bookId: string; startSlug: string }) {
  useLayoutEffect(() => {
    const main = document.getElementById("book-scroll");
    if (!main) return;
    const hash = slugFromHash();
    const hashEl = hash ? document.getElementById(hash) : null;
    const saved = readProgress(bookId)?.slug;
    const savedEl = saved ? document.getElementById(saved) : null;
    const startEl = document.getElementById(startSlug);
    const el = hashEl ?? savedEl ?? startEl;
    if (!el) return;
    el.scrollIntoView({ behavior: "instant", block: "start" });
    const section = sectionOf(el);
    if (!section) return;
    markSection(bookId, section.slug, section.title, hash ? "silent" : "replace");
  }, [bookId, startSlug]);

  useEffect(() => {
    const main = document.getElementById("book-scroll");
    if (!(main instanceof HTMLElement)) return;
    const bar = document.querySelector<HTMLElement>(".reading-progress");
    let frame = 0;

    const pick = () => {
      const windowScroll = !usesContainerScroll(main);
      if (bar) bar.style.width = `${scrollProgress(main, windowScroll)}%`;
      if (isSpyIgnored()) return;
      const slug = sectionAtReadLine(main, windowScroll);
      if (!slug || slug === getActiveSlug(bookId)) return;
      const section = main.querySelector<HTMLElement>(`[data-slug="${CSS.escape(slug)}"]`);
      markSection(bookId, slug, section?.dataset.title ?? slug, "replace");
    };

    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        pick();
      });
    };

    const observer = new IntersectionObserver(pick, {
      root: usesContainerScroll(main) ? main : null,
      rootMargin: "0px 0px -65% 0px",
      threshold: [0, 0.25, 0.5, 1],
    });
    for (const section of main.querySelectorAll("[data-slug]")) observer.observe(section);

    const scrollTarget: HTMLElement | Window = usesContainerScroll(main) ? main : window;
    scrollTarget.addEventListener("scroll", onScroll, { passive: true });
    pick();

    return () => {
      observer.disconnect();
      scrollTarget.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [bookId]);

  useEffect(() => {
    const onUrl = () => {
      const id = slugFromHash();
      const el = document.getElementById(id) ?? document.getElementById(startSlug);
      const section = sectionOf(el);
      if (!el || !section) return;
      ignoreSpy(400);
      el.scrollIntoView({ behavior: "instant", block: "start" });
      markSection(bookId, section.slug, section.title, "silent");
    };
    window.addEventListener("popstate", onUrl);
    window.addEventListener("hashchange", onUrl);
    return () => {
      window.removeEventListener("popstate", onUrl);
      window.removeEventListener("hashchange", onUrl);
    };
  }, [bookId, startSlug]);

  useEffect(() => {
    const app = document.querySelector(`.book-app[data-book="${CSS.escape(bookId)}"]`);
    if (!app) return;
    const onClick = (event: Event) => {
      const link = (event.target as HTMLElement | null)?.closest("a[href^='#']");
      if (!link || !app.contains(link)) return;
      const href = link.getAttribute("href") ?? "";
      const id = decodeURIComponent(href.slice(1));
      const el = document.getElementById(id);
      const section = sectionOf(el);
      if (!el || !section) return;
      event.preventDefault();
      ignoreSpy(700);
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      markSection(bookId, section.slug, section.title, link.hasAttribute("data-nav") ? "push" : "replace");
    };
    app.addEventListener("click", onClick);
    return () => app.removeEventListener("click", onClick);
  }, [bookId]);

  return null;
}
