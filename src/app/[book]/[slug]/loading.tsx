export default function ReaderLoading() {
  return (
    <div className="reader-loading" aria-label="Loading section" aria-busy="true">
      <div className="reader-loading-bar" />
      <div className="reader-loading-grid">
        <aside>
          <span className="skeleton skeleton-field" />
          {Array.from({ length: 9 }, (_, index) => (
            <span key={index} className="skeleton skeleton-nav" style={{ width: `${62 + (index % 3) * 9}%` }} />
          ))}
        </aside>
        <main>
          <span className="skeleton skeleton-meta" />
          <span className="skeleton skeleton-title" />
          <span className="skeleton skeleton-line" />
          <span className="skeleton skeleton-line short" />
          <span className="skeleton skeleton-line" />
        </main>
      </div>
    </div>
  );
}
