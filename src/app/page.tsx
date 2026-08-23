import Link from "next/link";
import { loadCatalog } from "@/lib/book/load";
import { ThemeToggle } from "@/components/book/theme-toggle";

export default function LibraryPage() {
  const catalog = loadCatalog();
  const topics = catalog.books.flatMap((book) => book.topics).filter((topic, index, all) => all.indexOf(topic) === index);

  return (
    <div className="library-shell">
      <header className="book-topbar">
        <p className="brand">DeepRead</p>
        <ThemeToggle />
      </header>
      <main className="library-main">
        <header className="library-intro">
          <p className="kicker">{catalog.books.length} {catalog.books.length === 1 ? "volume" : "volumes"}</p>
          <h1>Technical library</h1>
          <p className="library-lede">
            Searchable editions of books you extract locally. DeepRead does not ship copyrighted books.
          </p>
        </header>

        <section className="library-catalog">
          <div className="catalog-list">
            {catalog.books.length === 0 ? (
              <p className="catalog-subtitle">
                No books on the shelf. Add the sample guide, or extract a PDF you own — see the README.
              </p>
            ) : null}
            {catalog.books.map((book) => (
              <article key={book.id} className="catalog-row">
                <Link href={`/${book.id}/${book.startSlug}`} className="catalog-cover" aria-label={book.title}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={book.cover} alt="" />
                </Link>
                <div className="catalog-copy">
                  <h2>
                    <Link href={`/${book.id}/${book.startSlug}`}>{book.title}</Link>
                  </h2>
                  <p className="catalog-subtitle">{book.subtitle}</p>
                  <p className="catalog-meta">
                    {book.author} · {book.year} · {book.pages} pages · {book.sections} sections · {book.figures} figures
                  </p>
                  <p className="catalog-meta">{book.topics.join(", ")}</p>
                  {book.sourceUrl ? (
                    <p className="catalog-source">
                      <a href={book.sourceUrl} target="_blank" rel="noreferrer">
                        {book.sourceLabel ?? book.sourceUrl}
                      </a>
                    </p>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
          <aside className="catalog-index">
            <p className="kicker">Topics</p>
            <ul>
              {topics.map((topic) => (
                <li key={topic}>{topic}</li>
              ))}
            </ul>
          </aside>
        </section>
      </main>
    </div>
  );
}
