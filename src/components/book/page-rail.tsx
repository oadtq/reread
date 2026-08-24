export type PageHeading = {
  id: string;
  title: string;
  line: number;
};

export function headingsFromBody(body: string, prefix = ""): PageHeading[] {
  const headings: PageHeading[] = [];
  const seen = new Map<string, number>();
  for (const match of body.matchAll(/^##\s+(.+)$/gm)) {
    const title = match[1].trim();
    const base = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const occurrence = (seen.get(base) ?? 0) + 1;
    seen.set(base, occurrence);
    const raw = occurrence === 1 ? base : `${base}-${occurrence}`;
    const id = prefix ? `${prefix}--${raw}` : raw;
    const line = body.slice(0, match.index).split("\n").length;
    if (raw) headings.push({ id, title, line });
  }
  return headings;
}
