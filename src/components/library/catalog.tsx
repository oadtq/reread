"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ContinueReading } from "@/components/book/continue-reading";
import type { CatalogBook } from "@/lib/book/load";

function haystack(book: CatalogBook) {
  return [book.title, book.subtitle, book.author, ...book.topics].join(" ").toLowerCase();
}

export function Catalog({ books }: { books: CatalogBook[] }) {
  const [query, setQuery] = useState("");

  const normalized = query.trim().toLowerCase();
  const visible = useMemo(
    () => (normalized ? books.filter((book) => haystack(book).includes(normalized)) : books),
    [books, normalized],
  );

  return (
    <section>
      <div className="library-controls">
        <label className="library-search">
          <span className="sr-only">Search the library</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") setQuery("");
            }}
            type="search"
            placeholder="Search titles, authors, topics"
            className="field"
          />
        </label>
        {normalized ? (
          <span className="library-count" role="status">
            {visible.length} of {books.length}
          </span>
        ) : null}
      </div>

      {visible.length === 0 ? (
        <p className="catalog-empty">
          {books.length === 0
            ? "No books yet. Extract a PDF you own — see the README."
            : "No books match."}
        </p>
      ) : (
        <div className="catalog-list">
          {visible.map((book) => (
            <article key={book.id} className="catalog-row">
              <Link href={`/${book.id}`} className="catalog-cover" aria-label={book.title} tabIndex={-1}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={book.cover} alt="" />
              </Link>
              <div className="catalog-copy">
                <h2>
                  <Link href={`/${book.id}`}>{book.title}</Link>
                </h2>
                <p className="catalog-subtitle">{book.subtitle}</p>
                <p className="catalog-facts">
                  <b>{book.author}</b>, {book.year} · {book.pages.toLocaleString()} pages ·{" "}
                  {book.sections.toLocaleString()} sections · {book.figures.toLocaleString()} figures
                </p>
                <p className="catalog-topics">{book.topics.join(" · ")}</p>
                <div className="catalog-actions">
                  <Link href={`/${book.id}`} className="btn-read">
                    Read
                  </Link>
                  <ContinueReading bookId={book.id} startSlug={book.startSlug} />
                  {book.sourceUrl ? (
                    <a href={book.sourceUrl} target="_blank" rel="noreferrer" className="catalog-source">
                      {book.sourceLabel ?? book.sourceUrl}
                    </a>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
