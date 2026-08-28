import Link from "next/link";
import { ThemeToggle } from "@/components/book/theme-toggle";
import { Catalog } from "@/components/library/catalog";
import { loadCatalog } from "@/lib/book/load";

export default function LibraryPage() {
  const catalog = loadCatalog();
  const { books } = catalog;

  const totals = books.reduce(
    (sum, book) => ({
      pages: sum.pages + book.pages,
      sections: sum.sections + book.sections,
      figures: sum.figures + book.figures,
    }),
    { pages: 0, sections: 0, figures: 0 },
  );

  return (
    <div className="library-shell">
      <header className="site-topbar">
        <div className="site-topbar-inner">
          <Link href="/" className="brand">
            DeepRead
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <main className="library-main">
        <header className="library-intro">
          <h1>Library</h1>
          <p className="library-summary">
            {books.length} {books.length === 1 ? "book" : "books"} · {totals.pages.toLocaleString()} pages ·{" "}
            {totals.sections.toLocaleString()} sections · {totals.figures.toLocaleString()} figures
          </p>
        </header>

        <Catalog books={books} />
      </main>

      <footer className="site-footer">
        <div className="site-footer-inner">
          Book text and figures remain under their original copyright.
        </div>
      </footer>
    </div>
  );
}
