import Link from "next/link";

export default function NotFound() {
  return (
    <div className="library-shell">
      <main className="library-main">
        <header className="library-intro">
          <h1>Not found</h1>
          <p className="library-summary">That book or section is not in this library.</p>
          <p className="catalog-actions">
            <Link href="/" className="btn-read">
              Back to the library
            </Link>
          </p>
        </header>
      </main>
    </div>
  );
}
