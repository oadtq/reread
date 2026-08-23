"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { NavNode } from "@/lib/book/load";

function contains(node: NavNode, slug: string): boolean {
  if (node.slug === slug) return true;
  return node.children.some((child) => contains(child, slug));
}

function matches(node: NavNode, query: string): boolean {
  if (node.title.toLowerCase().includes(query)) return true;
  return node.children.some((child) => matches(child, query));
}

function titleFor(nodes: NavNode[], slug: string): string | null {
  for (const node of nodes) {
    if (node.slug === slug) return node.title;
    const childTitle = titleFor(node.children, slug);
    if (childTitle) return childTitle;
  }
  return null;
}

function Tree({
  nodes,
  bookId,
  active,
  query,
  depth = 0,
}: {
  nodes: NavNode[];
  bookId: string;
  active: string;
  query: string;
  depth?: number;
}) {
  return (
    <ul className={cn(depth > 0 && "ml-3")}>
      {nodes.map((node) => (
        <TreeItem
          key={node.slug}
          node={node}
          bookId={bookId}
          active={active}
          query={query}
          depth={depth}
        />
      ))}
    </ul>
  );
}

function TreeItem({
  node,
  bookId,
  active,
  query,
  depth,
}: {
  node: NavNode;
  bookId: string;
  active: string;
  query: string;
  depth: number;
}) {
  const inPath = contains(node, active);
  const [open, setOpen] = useState(inPath);
  if (query && !matches(node, query)) return null;
  const current = node.slug === active;
  const chapter = node.level <= 2;
  const expanded = Boolean(query) || open || inPath;

  return (
    <li className="mt-0.5">
      <div className="flex items-start gap-0.5">
        {node.children.length > 0 ? (
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={expanded ? `Collapse ${node.title}` : `Expand ${node.title}`}
            onClick={() => setOpen((value) => !value)}
            className="mt-0.5 flex size-6 shrink-0 items-center justify-center text-sm text-faint"
          >
            {expanded ? "−" : "+"}
          </button>
        ) : (
          <span className="mt-0.5 size-6 shrink-0" />
        )}
        <Link
          href={`/${bookId}/${node.slug}`}
          data-active={current ? "true" : undefined}
          aria-current={current ? "page" : undefined}
          className={cn(
            "toc-link block flex-1 rounded-md px-2 py-1.5 text-[0.8125rem] leading-snug",
            chapter ? "font-medium" : "font-normal",
            current ? "bg-press text-ink" : chapter ? "text-ink" : "text-mute",
          )}
        >
          {node.title}
        </Link>
      </div>
      {expanded && node.children.length > 0 ? (
        <Tree nodes={node.children} bookId={bookId} active={active} query={query} depth={depth + 1} />
      ) : null}
    </li>
  );
}

export function Sidebar({
  bookId,
  tree,
  active,
}: {
  bookId: string;
  tree: NavNode[];
  active: string;
}) {
  const [query, setQuery] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const normalized = query.trim().toLowerCase();
  const hasResults = !normalized || tree.some((node) => matches(node, normalized));

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const nav = navRef.current;
    const current = nav?.querySelector<HTMLElement>("[data-active='true']");
    if (!nav || !current) return;
    const top =
      current.getBoundingClientRect().top - nav.getBoundingClientRect().top + nav.scrollTop - nav.clientHeight / 3;
    nav.scrollTo({ top: Math.max(0, top) });
  }, [active]);

  return (
    <aside className="book-sidebar" data-open={mobileOpen ? "true" : undefined}>
      <button
        type="button"
        className="sidebar-mobile-toggle"
        aria-expanded={mobileOpen}
        aria-controls="book-contents"
        onClick={() => setMobileOpen((value) => !value)}
      >
        <span>
          <span className="kicker">Contents</span>
          <span className="sidebar-current">{titleFor(tree, active) ?? "Browse this book"}</span>
        </span>
        <span className="sidebar-toggle-icon" aria-hidden="true">{mobileOpen ? "Close" : "Open"}</span>
      </button>
      <div id="book-contents" className="sidebar-panel">
      <div className="shrink-0 px-3 pt-3 pb-2">
        <label className="block">
          <span className="sr-only">Search sections</span>
          <span className="field-wrap">
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search sections"
              type="search"
              className="field"
            />
            <kbd className="field-kbd">⌘K</kbd>
          </span>
        </label>
      </div>
      <nav ref={navRef} className="book-toc px-2 py-3 pb-10">
        {hasResults ? (
          <Tree nodes={tree} bookId={bookId} active={active} query={normalized} />
        ) : (
          <p className="toc-empty" role="status">No matching sections</p>
        )}
      </nav>
      </div>
    </aside>
  );
}
