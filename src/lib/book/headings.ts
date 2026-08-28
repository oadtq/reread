export type PageHeading = {
  id: string;
  title: string;
  line: number;
  level: number;
};

/**
 * Collects the h2/h3 headings inside a section body and assigns each a stable,
 * section-scoped id so the whole book can share one document without collisions.
 */
export function headingsFromBody(body: string, prefix = ""): PageHeading[] {
  const headings: PageHeading[] = [];
  const seen = new Map<string, number>();
  for (const match of body.matchAll(/^(#{2,3})\s+(.+)$/gm)) {
    const level = match[1].length;
    const title = match[2].trim();
    const base = title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
    const occurrence = (seen.get(base) ?? 0) + 1;
    seen.set(base, occurrence);
    const raw = occurrence === 1 ? base : `${base}-${occurrence}`;
    const id = prefix ? `${prefix}--${raw}` : raw;
    const line = body.slice(0, match.index).split("\n").length;
    if (raw) headings.push({ id, title, line, level });
  }
  return headings;
}
