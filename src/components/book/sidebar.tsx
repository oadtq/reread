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

function countLeaves(nodes: NavNode[]): number {
  return nodes.reduce((total, node) => total + 1 + countLeaves(node.children), 0);
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
    <ul className={cn(depth > 0 && "toc-nest")}>
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

  return (
    <li className={depth === 0 ? "mt-3 first:mt-0" : "mt-px"}>
      <a
        href={`#${node.slug}`}
        data-nav="toc"
        data-depth={Math.min(depth, 3)}
        data-active={current ? "true" : undefined}
        aria-current={current ? "page" : undefined}
        onClick={onNavigate}
        className="toc-link"
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
  const total = countLeaves(tree);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setMobileOpen(true);
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Keep the active entry in view as the reader scrolls, but never fight the
  // user while they are filtering the list.
  useEffect(() => {
    if (normalized) return;
    const nav = navRef.current;
    const current = nav?.querySelector<HTMLElement>("[data-active='true']");
    if (!nav || !current) return;
    const top =
      current.getBoundingClientRect().top - nav.getBoundingClientRect().top + nav.scrollTop - nav.clientHeight / 3;
    nav.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }, [active, normalized]);

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
        <span className="sidebar-toggle-icon" aria-hidden="true">
          ▾
        </span>
      </button>
      <div id="book-contents" className="sidebar-panel">
        <div className="sidebar-head">
          <label className="block">
            <span className="sr-only">Search sections</span>
            <span className="field-wrap">
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") setQuery("");
                }}
                placeholder={`Search ${total} sections`}
                type="search"
                className="field"
              />
              <kbd className="field-kbd">⌘K</kbd>
            </span>
          </label>
        </div>
        <nav ref={navRef} className="book-toc" aria-label="Table of contents">
          {hasResults ? (
            <Tree nodes={tree} active={active} query={normalized} onNavigate={() => setMobileOpen(false)} />
          ) : (
            <p className="toc-empty" role="status">
              No sections match “{query.trim()}”.
            </p>
          )}
        </nav>
      </div>
    </aside>
  );
}
