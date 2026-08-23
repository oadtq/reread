export type PageHeading = {
  id: string;
  title: string;
  line: number;
};

export function headingsFromBody(body: string): PageHeading[] {
  const headings: PageHeading[] = [];
  const seen = new Map<string, number>();
  for (const match of body.matchAll(/^##\s+(.+)$/gm)) {
    const title = match[1].trim();
    const base = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const occurrence = (seen.get(base) ?? 0) + 1;
    seen.set(base, occurrence);
    const id = occurrence === 1 ? base : `${base}-${occurrence}`;
    const line = body.slice(0, match.index).split("\n").length;
    if (id) headings.push({ id, title, line });
  }
  return headings;
}

export function PageRail({ headings }: { headings: PageHeading[] }) {
  if (headings.length === 0) return null;
  return (
    <nav className="page-rail" aria-label="On this page">
      <p className="kicker mb-2">On this page</p>
      {headings.map((heading) => (
        <a key={heading.id} href={`#${heading.id}`}>
          {heading.title}
        </a>
      ))}
    </nav>
  );
}
