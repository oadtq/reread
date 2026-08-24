"use client";

import { useEffect, useRef, useState } from "react";
import { useActiveSection } from "@/components/book/book-reader";
import { cn } from "@/lib/cn";
import type { NavNode } from "@/lib/book/load";

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
  active,
  query,
  onNavigate,
  depth = 0,
}: {
  nodes: NavNode[];
  active: string;
  query: string;
  onNavigate: () => void;
  depth?: number;
}) {
  return (
    <ul className={cn(depth > 0 && "pl-3")}>
      {nodes.map((node) => (
        <TreeItem
          key={node.slug}
          node={node}
          active={active}
          query={query}
          onNavigate={onNavigate}
          depth={depth}
        />
      ))}
    </ul>
  );
}

function TreeItem({
  node,
  active,
  query,
  onNavigate,
  depth,
}: {
  node: NavNode;
  active: string;
  query: string;
  onNavigate: () => void;
  depth: number;
}) {
  if (query && !matches(node, query)) return null;
  const current = node.slug === active;
  const top = depth === 0;

  return (
    <li className={cn(top ? "mt-2 first:mt-0" : "mt-px")}>
      <a
        href={`#${node.slug}`}
        data-nav="toc"
        data-active={current ? "true" : undefined}
        aria-current={current ? "page" : undefined}
        onClick={onNavigate}
        className={cn(
          "toc-link block rounded-md px-2 py-1 text-[0.8125rem] leading-snug",
          top ? "font-medium" : "font-normal",
          current ? "bg-press text-ink" : depth >= 2 ? "text-mute" : "text-ink",
        )}
      >
        {node.title}
      </a>
      {node.children.length > 0 && (!query || node.children.some((child) => matches(child, query))) ? (
        <Tree nodes={node.children} active={active} query={query} onNavigate={onNavigate} depth={depth + 1} />
      ) : null}
    </li>
  );
}

export function Sidebar({
  bookId,
  tree,
  startSlug,
}: {
  bookId: string;
  tree: NavNode[];
  startSlug: string;
}) {
  const active = useActiveSection(bookId, startSlug);
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
          <Tree nodes={tree} active={active} query={normalized} onNavigate={() => setMobileOpen(false)} />
        ) : (
          <p className="toc-empty" role="status">No matching sections</p>
        )}
      </nav>
      </div>
    </aside>
  );
}
