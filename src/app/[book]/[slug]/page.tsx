import Link from "next/link";
import { notFound } from "next/navigation";
import { BookArticle } from "@/components/book/article";
import { BookFrame } from "@/components/book/book-frame";
import { headingsFromBody, PageRail } from "@/components/book/page-rail";
import { findNode, imageDimensionsFromBody, loadCatalog, loadNav, loadPage, neighbors } from "@/lib/book/load";

type PageProps = {
  params: Promise<{ book: string; slug: string }>;
};

export function generateStaticParams() {
  return loadCatalog().books.flatMap((book) => {
    try {
      const nav = loadNav(book.id);
      return nav.pagesMeta.map((page) => ({ book: book.id, slug: page.slug }));
    } catch {
      return [];
    }
  });
}

export async function generateMetadata({ params }: PageProps) {
  const { book, slug } = await params;
  try {
    const page = loadPage(book, slug);
    const nav = loadNav(book);
    return { title: page ? `${page.title} · ${nav.title}` : nav.title };
  } catch {
    return { title: "DeepRead" };
  }
}

export default async function SectionPage({ params }: PageProps) {
  const { book, slug } = await params;
  if (!loadCatalog().books.some((item) => item.id === book)) notFound();
  const page = loadPage(book, slug);
  if (!page) notFound();
  const { prev, next } = neighbors(book, slug);
  const headings = headingsFromBody(page.body);
  const nav = loadNav(book);
  const children = findNode(nav.tree, slug)?.children ?? [];
  const position = nav.pagesMeta.findIndex((item) => item.slug === slug) + 1;
  const imageDimensions = imageDimensionsFromBody(page.body);
  const firstImage = page.body.match(/!\[[^\]]*\]\((\/books\/[^)]+)\)/);
  const eagerImage = firstImage && firstImage.index !== undefined && page.body.slice(0, firstImage.index).split(/\s+/).length < 180
    ? firstImage[1]
    : undefined;

  return (
    <BookFrame bookId={book} active={slug}>
      <div className="book-article">
        <article>
          <header className="reader-heading">
            <p className="kicker reader-meta">
              <span>Print p. {page.page}</span>
              <span aria-hidden="true">·</span>
              <span>Section {position} of {nav.pagesMeta.length}</span>
            </p>
            <h1>{page.title}</h1>
          </header>
          <div className="reader-body">
            {page.body ? (
              <BookArticle
                body={page.body}
                glossary={page.slug.includes("glossary")}
                headings={headings}
                imageDimensions={imageDimensions}
                eagerImage={eagerImage}
              />
            ) : children.length > 0 ? (
              <ul className="section-children">
                {children.map((child) => (
                  <li key={child.slug}>
                    <Link href={`/${book}/${child.slug}`}>{child.title}</Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <nav className="pager">
            {prev ? (
              <Link href={`/${book}/${prev.slug}`}>
                <span className="kicker">Previous</span>
                {prev.title}
              </Link>
            ) : (
              <span />
            )}
            {next ? (
              <Link href={`/${book}/${next.slug}`} className="pager-next">
                <span className="kicker">Next</span>
                {next.title}
              </Link>
            ) : (
              <span />
            )}
          </nav>
        </article>
        <PageRail headings={headings} />
      </div>
    </BookFrame>
  );
}
