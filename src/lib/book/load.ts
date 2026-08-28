import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import matter from "gray-matter";

export type NavNode = {
  title: string;
  slug: string;
  level: number;
  children: NavNode[];
};

export type PageMeta = {
  title: string;
  slug: string;
  level: number;
  page: number;
  file: string;
  order: number;
};

export type BookNav = {
  id: string;
  title: string;
  author: string;
  subtitle: string;
  year: number;
  topics: string[];
  pages: number;
  cover: string;
  printPages?: boolean;
  tree: NavNode[];
  pagesMeta: PageMeta[];
};

export type CatalogBook = {
  id: string;
  title: string;
  author: string;
  subtitle: string;
  year: number;
  topics: string[];
  pages: number;
  sections: number;
  figures: number;
  cover: string;
  startSlug: string;
  sourceUrl?: string;
  sourceLabel?: string;
};

export type Catalog = {
  name: string;
  kicker: string;
  books: CatalogBook[];
};

export type BookPage = {
  title: string;
  slug: string;
  level: number;
  page: number;
  order: number;
  body: string;
};

export type ImageDimensions = Record<string, { width: number; height: number }>;

function dimensionsFromBuffer(buffer: Buffer): { width: number; height: number } | null {
  const pngSignature = "89504e470d0a1a0a";
  if (buffer.length >= 24 && buffer.subarray(0, 8).toString("hex") === pngSignature) {
    return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
  }

  if (buffer.length >= 4 && buffer[0] === 0xff && buffer[1] === 0xd8) {
    let offset = 2;
    while (offset + 9 < buffer.length) {
      if (buffer[offset] !== 0xff) {
        offset += 1;
        continue;
      }
      const marker = buffer[offset + 1];
      const segmentLength = buffer.readUInt16BE(offset + 2);
      if (marker >= 0xc0 && marker <= 0xc3) {
        return { height: buffer.readUInt16BE(offset + 5), width: buffer.readUInt16BE(offset + 7) };
      }
      if (segmentLength < 2) break;
      offset += segmentLength + 2;
    }
  }

  return null;
}

const ROOT = path.join(process.cwd(), "content");

function readCatalogFile(name: string): Catalog | null {
  const file = path.join(ROOT, name);
  if (!existsSync(file)) return null;
  return JSON.parse(readFileSync(file, "utf8")) as Catalog;
}

export function loadCatalog(): Catalog {
  const base = readCatalogFile("catalog.json") ?? {
    name: "DeepRead",
    kicker: "Technical library",
    books: [],
  };
  const local = readCatalogFile("catalog.local.json");
  if (!local?.books.length) return base;

  const byId = new Map(base.books.map((book) => [book.id, book]));
  for (const book of local.books) byId.set(book.id, book);

  const books: CatalogBook[] = [];
  const seen = new Set<string>();
  for (const book of base.books) {
    books.push(byId.get(book.id)!);
    seen.add(book.id);
  }
  for (const book of local.books) {
    if (!seen.has(book.id)) {
      books.push(book);
      seen.add(book.id);
    }
  }
  return { ...base, books };
}

export function loadNav(bookId: string): BookNav {
  return JSON.parse(readFileSync(path.join(ROOT, bookId, "nav.json"), "utf8")) as BookNav;
}

function pageFromFile(bookId: string, meta: PageMeta): BookPage {
  const parsed = matter(readFileSync(path.join(ROOT, bookId, "pages", meta.file), "utf8"));
  return {
    title: String(parsed.data.title),
    slug: String(parsed.data.slug),
    level: Number(parsed.data.level),
    page: Number(parsed.data.page),
    order: Number(parsed.data.order),
    body: parsed.content.trim(),
  };
}

export function loadPage(bookId: string, slug: string): BookPage | null {
  const nav = loadNav(bookId);
  const meta = nav.pagesMeta.find((page) => page.slug === slug);
  if (!meta) return null;
  return pageFromFile(bookId, meta);
}

export function loadPages(bookId: string): BookPage[] {
  const nav = loadNav(bookId);
  return nav.pagesMeta.map((meta) => pageFromFile(bookId, meta));
}

export function imageDimensionsFromBody(body: string): ImageDimensions {
  const dimensions: ImageDimensions = {};
  const sources = [...body.matchAll(/!\[[^\]]*\]\((\/books\/[^)]+)\)/g)].map((match) => match[1]);

  for (const source of new Set(sources)) {
    const file = path.join(process.cwd(), "public", source.replace(/^\/+/, ""));
    try {
      const size = dimensionsFromBuffer(readFileSync(file));
      if (size) dimensions[source] = size;
    } catch {
      // Markdown rendering remains resilient if a source image cannot be inspected.
    }
  }

  return dimensions;
}

export function findNode(nodes: NavNode[], slug: string): NavNode | null {
  for (const node of nodes) {
    if (node.slug === slug) return node;
    const nested = findNode(node.children, slug);
    if (nested) return nested;
  }
  return null;
}

export function neighbors(bookId: string, slug: string) {
  const list = loadNav(bookId).pagesMeta;
  const index = list.findIndex((item) => item.slug === slug);
  return {
    prev: index > 0 ? list[index - 1] : null,
    next: index >= 0 && index < list.length - 1 ? list[index + 1] : null,
  };
}
